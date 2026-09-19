#!/usr/bin/env bash
#
# The desktop execution channel: build xemu for this host and run the pgraph
# suite on it, with no device involved.
#
# WHY THIS EXISTS
#
# The fleet's two handhelds run the Vulkan path, so a GL-only defect is
# invisible to them. `territory.toml`'s [lane.remote] held "the desktop build
# and the GL renderer as a CAPABILITY" -- but that lane is a one-way remote
# session on a machine nobody here can reach, and its output is stranded. This
# host can do the same work; it had simply never been asked to. There was no
# build directory here beyond the `configure --help` log the board wrote while
# briefing this lane.
#
# WHAT IT IS NOT
#
# It is NOT a way to score a desktop capture against a handheld golden. See
# the "comparability" note in `docs/lanes/desktopchannel/NOTES.md` and the
# refusal in `ab_compare.py`. A desktop GL capture that differs from
# `/home/justin/goldens/results` is evidence of a different renderer, driver
# and rasteriser before it is evidence of anything about xemu. The only sound
# desktop measurement is desktop-against-desktop.
#
# Usage:
#   desktop_channel.sh deps            bootstrap the build dependencies
#   desktop_channel.sh build [<ref>]   build qemu-system-i386 (default: HEAD)
#   desktop_channel.sh smoke           start the built binary headless
#   desktop_channel.sh run <S::T> [tag] [OPENGL|VULKAN]
#                                      one test, one capture, one result.json
#   desktop_channel.sh env             print the environment the above use
#
# Everything lands under $DC_ROOT (default $WORK/desktop). Nothing is written
# to /home/justin/hakuX: that is the tree the dispatcher builds from, and a
# dirty tree there stalls the whole fleet.

set -uo pipefail

# ---------------------------------------------------------------- locations

WORK="${WORK:-/home/justin/hakux-work}"
DC_ROOT="${DC_ROOT:-$WORK/desktop}"
DEPS="$DC_ROOT/deps"
PREFIX="$DEPS/prefix"
DEBS="$DEPS/debs"
TREE="$DC_ROOT/tree"
BUILD="$TREE/build-linux"
LOGS="$DC_ROOT/logs"

# The repo this script lives in, derived from the script's own path rather
# than hard-coded: gate.sh carried a hard-coded /home/user/hakuX for a while
# and could only ever run on one machine.
REPO="${DC_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# The dispatcher's own tree. Refused as a build target, deliberately.
FORBIDDEN_TREE="/home/justin/hakuX"

# ------------------------------------------------------------------- tools
#
# ninja is NOT on PATH here, and it is not on PATH for a systemd user unit
# either -- that exact omission cost every uncached Android build on
# 2026-09-18 until the dispatcher unit gained an explicit PATH. So the path is
# searched here and never assumed from the caller's shell. Same for meson,
# which lives in ~/.local/bin.
find_tool() {
    local name="$1"; shift
    local c
    for c in "$@"; do
        [ -x "$c" ] && { printf '%s\n' "$c"; return 0; }
    done
    c="$(command -v "$name" 2>/dev/null)" && { printf '%s\n' "$c"; return 0; }
    return 1
}

NINJA="$(find_tool ninja \
    /home/justin/Android/Sdk/cmake/3.30.3/bin/ninja \
    /usr/bin/ninja /usr/local/bin/ninja "$HOME/.local/bin/ninja")" || true
MESON="$(find_tool meson "$HOME/.local/bin/meson" /usr/bin/meson)" || true

# The dev packages this host lacks. Measured, not copied from the CI workflow:
# glib, sdl2, pcre2, zlib and samplerate are already present system-wide, and
# listing them would only make the closure bigger. Of the first six, epoxy,
# gtk3 and vulkan are HARD requirements -- meson.build:1852 has
# `dependency('epoxy', required: true)`, :2007 forces gtk on Linux regardless
# of --disable-gtk, and :2360 has a bare `dependency('vulkan')`. pixman, png
# and slirp are optional but cheap once the mechanism exists.
#
# libssl-dev is NOT optional and is easy to miss, because the thing that wants
# it is not QEMU: with no system libcurl-dev, meson falls through to the
# BUNDLED curl subproject, and subprojects/curl-8.12.1/meson.build:532 hard
# -fails on `Dependency "openssl" not found`. That is what the first configure
# attempt here died on, ~200 checks in, long after epoxy/gtk/vulkan had all
# been satisfied. The rest of the line is desktop.yml's remainder: they cost
# a few hundred KB each and each one skipped is another configure round trip.
#
# libibverbs1 is a RUNTIME package, not a -dev one, and it is here because a
# -dev package dragged its NEEDED entry into the binary without its library.
# libpcap-dev depends on libibverbs-dev, `pcap.pc` puts -libverbs on the link
# line, and this host has the dev package's headers (via that dependency) but
# never had the runtime .so. The build linked clean and the binary died on
# `error while loading shared libraries: libibverbs.so.1`, which reads like a
# broken system rather than a missing dependency of ours.
DC_PKGS="libepoxy-dev libvulkan-dev libgtk-3-dev libpixman-1-dev libpng-dev libslirp-dev
         libssl-dev libgmp-dev libpcap-dev libcap-ng-dev libattr1-dev libdrm-dev
         libasound2-dev libpulse-dev nlohmann-json3-dev libibverbs1"

# The pkg-config modules those must end up providing. `deps` verifies each one
# rather than trusting that extraction worked.
DC_MODULES="epoxy vulkan gtk+-3.0 pixman-1 libpng slirp openssl gmp libcap-ng libdrm alsa libpulse"

MULTIARCH="$(gcc -print-multiarch 2>/dev/null || echo x86_64-linux-gnu)"

dc_pkg_config_path() {
    printf '%s' \
      "$PREFIX/usr/lib/$MULTIARCH/pkgconfig:$PREFIX/usr/share/pkgconfig:$PREFIX/usr/lib/pkgconfig:/usr/lib/$MULTIARCH/pkgconfig:/usr/share/pkgconfig:/usr/lib/pkgconfig"
}

dc_export_env() {
    export PKG_CONFIG_PATH="$(dc_pkg_config_path)"
    export PATH="$(dirname "${NINJA:-/usr/bin/ninja}"):$(dirname "${MESON:-/usr/bin/meson}"):$PATH"
    # Headers and libraries live under the private prefix. -isystem rather
    # than -I so a warning in gtk's headers is not our warning; the gate
    # counts warning sites and a dependency's are noise in that census.
    export DC_CFLAGS="-isystem $PREFIX/usr/include -isystem $PREFIX/usr/include/$MULTIARCH"
    export DC_LDFLAGS="-L$PREFIX/usr/lib/$MULTIARCH -L$PREFIX/usr/lib"
    # Runtime, not just link time. A rootless prefix holds shared objects the
    # dynamic loader has never been told about, so every invocation of the
    # built binary needs this -- including the ones made by other scripts.
    # `dc_run_env` below is the supported way for them to get it.
    export LD_LIBRARY_PATH="$PREFIX/usr/lib/$MULTIARCH:$PREFIX/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
}

# What an unmet NEEDED entry looks like, and which package would supply it.
# Called at the end of `build`, because a binary that links and cannot start
# is the failure this channel is most likely to hit again: the prefix is
# rootless, so a -dev package can contribute a link flag whose runtime half
# was never installed. The first time, the message was
# `error while loading shared libraries: libibverbs.so.1` at run time, forty
# minutes after the build that caused it.
check_runtime_libs() {
    local bin="$1" missing lib
    missing="$(ldd "$bin" 2>/dev/null | awk '/not found/{print $1}')"
    [ -z "$missing" ] && { say "runtime libraries: all resolved"; return 0; }
    say "MISSING RUNTIME LIBRARIES -- the binary will not start:"
    for lib in $missing; do
        printf '    %-24s provided by: %s\n' "$lib" \
            "$(apt-file search "$lib" 2>/dev/null | head -1 | cut -d: -f1 \
               || echo '(apt-file not installed; try `apt-cache search`)')"
    done
    say "  add the providing package to DC_PKGS and re-run '$0 deps'"
    return 1
}

say()  { printf '%s\n' "$*"; }
die()  { printf 'REFUSING: %s\n' "$*" >&2; exit 2; }

# ------------------------------------------------------------------- deps

cmd_deps() {
    command -v dpkg-deb >/dev/null || die "dpkg-deb is not available"
    mkdir -p "$DEBS" "$PREFIX" "$LOGS" || die "cannot create $DEPS"

    # --print-uris resolves the closure AGAINST WHAT IS ALREADY INSTALLED, so
    # this is the delta and not the whole gtk world. It needs no root.
    say "--- resolving the dependency closure ---"
    local uris="$DEPS/uris.txt"
    # shellcheck disable=SC2086
    apt-get install --print-uris -y --no-install-recommends $DC_PKGS \
        2>"$LOGS/apt-resolve.err" | grep -oE "^'http[^']+'" | tr -d "'" >"$uris"
    local n; n=$(wc -l <"$uris")
    if [ "$n" -eq 0 ]; then
        say "nothing to fetch (already satisfied?), or apt could not resolve:"
        tail -5 "$LOGS/apt-resolve.err" >&2
    fi
    say "$n package(s) to fetch"

    say "--- fetching ---"
    local u f got=0 skipped=0
    while read -r u; do
        [ -n "$u" ] || continue
        f="$DEBS/$(basename "$u")"
        if [ -s "$f" ]; then skipped=$((skipped + 1)); continue; fi
        if ! curl -fsSL --retry 3 -o "$f.part" "$u"; then
            rm -f "$f.part"
            die "could not fetch $u"
        fi
        mv "$f.part" "$f"
        got=$((got + 1))
    done <"$uris"
    say "fetched $got, already had $skipped"

    say "--- extracting into $PREFIX ---"
    for f in "$DEBS"/*.deb; do
        [ -e "$f" ] || continue
        dpkg-deb -x "$f" "$PREFIX" || die "dpkg-deb -x failed on $f"
    done

    # A Debian -dev package ships /usr/lib/<ma>/libfoo.so as a RELATIVE symlink
    # to libfoo.so.N, which lives in the runtime package and is therefore not
    # in our prefix. Extracted on its own the symlink dangles, and `-lfoo`
    # then fails at link with a message that blames the linker rather than the
    # extraction. Repoint every dangling symlink at the system copy.
    #
    # Only the library directories. The first version of this walked the whole
    # prefix and spent sixty lines complaining about `changelog.Debian.gz`
    # symlinks under usr/share/doc, which nothing links against -- noise that
    # buries the one line that matters.
    #
    # TWO PASSES, because the links form chains: libpng.so -> libpng16.so ->
    # libpng16.so.16, and only the last of those is in /usr. On a single pass
    # the outer link is tested BEFORE the inner one is repaired and is
    # reported broken when it is about to be fine. Loop until a pass changes
    # nothing, so the chain length is not a parameter anyone has to know.
    say "--- repointing dangling symlinks at the system libraries ---"
    local l t fixed=0 broken=0 pass
    for pass in 1 2 3; do
        broken=0
        while IFS= read -r l; do
            [ -e "$l" ] && continue          # resolves fine, leave it
            t="$(readlink "$l")"
            t="${t##*/}"
            if [ -e "/usr/lib/$MULTIARCH/$t" ]; then
                ln -sf "/usr/lib/$MULTIARCH/$t" "$l"; fixed=$((fixed + 1))
            elif [ -e "/usr/lib/$t" ]; then
                ln -sf "/usr/lib/$t" "$l"; fixed=$((fixed + 1))
            else
                broken=$((broken + 1))
            fi
        done < <(find "$PREFIX/usr/lib" -type l 2>/dev/null)
        [ "$broken" -eq 0 ] && break
    done
    say "repointed $fixed, still dangling $broken"
    if [ "$broken" -gt 0 ]; then
        say "  the ones that could not be resolved:"
        find "$PREFIX/usr/lib" -type l ! -exec test -e {} \; -print 2>/dev/null | sed 's/^/    /'
    fi

    # .pc files say prefix=/usr, which would point every -I and -L at the
    # system tree that does not have these headers. Rewrite to our prefix.
    # Done on a copy-free in-place sed of only the `prefix=` assignment: the
    # other variables are expressed in terms of it.
    say "--- rewriting .pc prefixes ---"
    local pc pcs=0
    while IFS= read -r pc; do
        sed -i -E "s|^prefix=/usr\$|prefix=$PREFIX/usr|" "$pc"
        # A few Debian .pc files hard-code the multiarch libdir or includedir
        # instead of deriving it. Catch those too, but only when the path does
        # not already point into the prefix.
        sed -i -E "s|=/usr/(lib/$MULTIARCH\|include)|=$PREFIX/usr/\1|g" "$pc"
        pcs=$((pcs + 1))
    done < <(find "$PREFIX" -name '*.pc')
    say "rewrote $pcs"

    say "--- verifying ---"
    dc_export_env
    local m rc=0
    for m in $DC_MODULES; do
        if pkg-config --exists "$m"; then
            printf '  %-12s OK %s\n' "$m" "$(pkg-config --modversion "$m")"
        else
            printf '  %-12s MISSING\n' "$m"; rc=1
        fi
    done
    [ "$rc" -eq 0 ] && say "deps: all $(echo $DC_MODULES | wc -w) modules resolve"
    return "$rc"
}

# ------------------------------------------------------------------ build

ensure_tree() {
    local ref="$1"
    case "$TREE" in
        "$FORBIDDEN_TREE"|"$FORBIDDEN_TREE"/*)
            die "DC_ROOT points inside $FORBIDDEN_TREE, which the dispatcher builds from" ;;
    esac
    if [ ! -d "$TREE/.git" ] && [ ! -f "$TREE/.git" ]; then
        mkdir -p "$(dirname "$TREE")" || die "cannot create $(dirname "$TREE")"
        say "--- creating the private worktree at $TREE ---"
        git -C "$REPO" worktree add --detach "$TREE" "$ref" || die "worktree add failed"
    else
        # --detach always: a branch checked out in another worktree cannot be
        # checked out here, and this tree is never the place to hold a branch.
        git -C "$TREE" checkout --quiet --detach "$ref" || die "cannot check out $ref"
    fi
    git -C "$TREE" rev-parse --short=10 HEAD
}

cmd_build() {
    local ref="${1:-HEAD}"
    [ -n "$NINJA" ] || die "no ninja found (tried the Android SDK cmake copy and PATH)"
    [ -n "$MESON" ] || die "no meson found (tried ~/.local/bin and PATH)"
    mkdir -p "$LOGS"
    dc_export_env

    local m
    for m in $DC_MODULES; do
        pkg-config --exists "$m" || die "$m does not resolve; run '$0 deps' first"
    done

    local sha; sha="$(ensure_tree "$ref")" || exit 2
    say "building $ref at $sha in $BUILD"
    say "  ninja = $NINJA"
    say "  meson = $MESON"

    if [ ! -f "$BUILD/build.ninja" ]; then
        say "--- configure ---"
        mkdir -p "$BUILD" || die "cannot create $BUILD"
        # The flag set is desktop.yml's, plus the private prefix threaded in.
        # --disable-werror matters: this tree carries ~78 warning sites and
        # the point of the channel is to run, not to be pristine.
        ( cd "$BUILD" && ../configure \
            --target-list=i386-softmmu \
            --extra-cflags="-DXBOX=1 $DC_CFLAGS" \
            --extra-ldflags="$DC_LDFLAGS" \
            --disable-werror --disable-docs --disable-guest-agent --disable-tools \
        ) >"$LOGS/configure.log" 2>&1
        local crc=$?
        say "CONFIGURE_EXIT=$crc   (log: $LOGS/configure.log)"
        if [ "$crc" -ne 0 ]; then
            say "--- the last 40 lines ---"
            tail -40 "$LOGS/configure.log"
            return 1
        fi
    else
        say "--- already configured, reusing $BUILD ---"
    fi

    say "--- ninja ---"
    # Never pipe ninja. gate.sh's header explains why at length: ninja prints
    # a status line when it STARTS an edge, so a filtered log is consistent
    # with a link that failed, and $? from a pipeline is the grep's.
    "$NINJA" -C "$BUILD" -j"$(nproc)" qemu-system-i386 >"$LOGS/build.log" 2>&1
    local rc=$?
    say "NINJA_EXIT=$rc   (log: $LOGS/build.log)"
    if [ "$rc" -ne 0 ]; then
        say "--- FAILED/error lines ---"
        grep -E 'FAILED:|error:' "$LOGS/build.log" | head -30
        return 1
    fi
    [ -x "$BUILD/qemu-system-i386" ] || die "ninja succeeded but no binary at $BUILD/qemu-system-i386"
    say "binary: $(stat -c '%s bytes, mtime %y' "$BUILD/qemu-system-i386")"
    say "sha:    $sha"
    check_runtime_libs "$BUILD/qemu-system-i386" || return 1
}

# ------------------------------------------------------------------ smoke

cmd_smoke() {
    [ -x "$BUILD/qemu-system-i386" ] || die "no binary; run '$0 build' first"
    # The binary cannot start without LD_LIBRARY_PATH: libibverbs.so.1 lives
    # only in the rootless prefix. Omitting this call here is what made the
    # first smoke run fail with exit 127 AFTER the missing library had already
    # been fetched -- the fix was in place and the caller could not see it.
    dc_export_env
    mkdir -p "$LOGS"
    local log="$LOGS/smoke.log"
    say "--- starting headless, no disc (expect the timeout to kill it) ---"
    SDL_VIDEODRIVER=offscreen SDL_AUDIODRIVER=dummy \
        timeout -k 5 40 "$BUILD/qemu-system-i386" -machine xbox -display none \
        >"$log" 2>&1
    local rc=$?
    say "EXIT=$rc   (124 = the timeout killing a healthy long-running process)"
    if [ "$rc" -ne 124 ] && [ "$rc" -ne 0 ]; then
        grep -viE '^ALSA lib|snd_' "$log" | tail -30
        return 1
    fi
    grep -qiE 'Assertion|assert failed|Segmentation fault' "$log" && {
        say "CRASHED:"; grep -viE '^ALSA lib|snd_' "$log" | tail -30; return 1; }
    grep -E 'xemu_version|^nv2a: renderer:' "$log" | head -5
    grep -q 'xemu_version' "$log" || { say "no version banner"; tail -20 "$log"; return 1; }
}

# -------------------------------------------------------------------- run
#
# One test, one run, one capture, scored only against other desktop runs.
#
# THE HDD IS RAW, AND THAT IS NOT AN OVERSIGHT. `desktop-runs.md` says to use
# qcow2 because QEMU probes a raw image's format and restricts writes, so the
# run "completes and extracts nothing". That was worth testing rather than
# accepting, because xemu's own qemu-img cannot make a qcow2 on this host --
# it aborts on startup with
# `qemu-thread-posix.c:127: qemu_mutex_unlock_impl: Assertion
# 'mutex->initialized' failed`, the standalone tools not having survived the
# fork. Measured here: a raw copy of the Android backup's hdd.img runs, the
# guest writes land, and extract_results.py pulls the capture out. No probe
# warning appears in the run log at all. So the qcow2 requirement is not a
# property of raw images in general; treat that line in desktop-runs.md as
# scoped to the freshly-generated blank image it was measured on.
#
# A FRESH COPY OF THE DISK PER RUN. The guest writes its captures into it, so
# a reused disk means run N can extract run N-1's output and look perfectly
# healthy doing it. The copy costs about a second.

cmd_run() {
    local test="${1:?usage: $0 run <Suite::Test> [tag] [renderer]}"
    local tag="${2:-$(printf '%s' "$test" | tr -c 'A-Za-z0-9' '_')}"
    local renderer="${3:-OPENGL}"
    local rundir="$DC_ROOT/runs/$tag"
    local x1="${DC_X1BOX:-/home/justin/hakuX/hakux-backup/x1box}"
    local goldens="${GOLDENS:-/home/justin/goldens}/results"
    local base_iso="${DC_BASE_ISO:-/home/justin/nxdk_pgraph_tests_xiso.iso}"
    local testing; testing="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    [ -x "$BUILD/qemu-system-i386" ] || die "no binary; run '$0 build' first"
    local f
    for f in "$x1/mcpx.bin" "$x1/flash.bin" "$x1/eeprom.bin" "$x1/hdd.img" "$base_iso"; do
        [ -f "$f" ] || die "missing $f"
    done
    [ -d "$goldens" ] || die "no goldens at $goldens"
    dc_export_env

    rm -rf "$rundir"; mkdir -p "$rundir/empty-results" "$rundir/disc" || die "cannot create $rundir"
    cp "$x1/hdd.img" "$rundir/hdd.img"   || die "cannot copy the disk image"
    cp "$x1/eeprom.bin" "$rundir/eeprom.bin" || die "cannot copy the eeprom"

    say "--- building a disc that runs exactly $test ---"
    local plan
    plan="$(python3 "$testing/make_isolation_discs.py" /dev/null \
        --results "$rundir/empty-results" --goldens "$goldens" \
        --base "$base_iso" --out-dir "$rundir/disc" --build-one "$test")" \
        || die "could not build the disc"
    say "$plan"
    local guest iso
    guest="$(printf '%s' "$plan" | python3 -c 'import json,sys;print(json.load(sys.stdin)["guest_dir"])')"
    iso="$(printf '%s' "$plan" | python3 -c 'import json,sys;print(json.load(sys.stdin)["iso"])')"

    # XDG_DATA_HOME scopes the config to this run. Without it xemu writes to
    # ~/.local/share/xemu/xemu/xemu.toml, which two runs would share and a
    # human's own xemu would inherit.
    export XDG_DATA_HOME="$rundir/xdg"
    mkdir -p "$XDG_DATA_HOME/xemu/xemu"
    cat >"$XDG_DATA_HOME/xemu/xemu/xemu.toml" <<TOML
[general]
show_welcome = false
skip_boot_anim = true

[display]
renderer = '$renderer'

[net]
enable = false

[sys.files]
bootrom_path = '$x1/mcpx.bin'
flashrom_path = '$x1/flash.bin'
eeprom_path = '$rundir/eeprom.bin'
hdd_path = '$rundir/hdd.img'
dvd_path = '$iso'
TOML

    say "--- running ($renderer) ---"
    local t0; t0=$(date +%s)
    SDL_VIDEODRIVER=offscreen SDL_AUDIODRIVER=dummy \
        timeout -k 5 "${DC_TIMEOUT:-420}" "$BUILD/qemu-system-i386" \
        -machine xbox -display none >"$rundir/run.log" 2>&1
    local rc=$?
    say "RUN_EXIT=$rc  (0 = the guest powered off on completion)  $(( $(date +%s) - t0 ))s"
    if [ "$rc" -ne 0 ]; then
        tail -20 "$rundir/run.log"
        die "the run did not complete"
    fi

    # WHICH RENDERER ACTUALLY RAN. Asking for one and silently getting the
    # other is #29, and it cost a set of results that were believed to be
    # Vulkan. nv2a names the renderer it used; compare it, do not assume.
    local got; got="$(grep -m1 '^nv2a: renderer:' "$rundir/run.log" | cut -d' ' -f3-)"
    say "renderer in use: ${got:-<none>}"
    case "$renderer:$got" in
        OPENGL:OpenGL|VULKAN:Vulkan) ;;
        *) die "asked for $renderer and got '${got:-nothing}'" ;;
    esac
    grep -E '^GL_(VENDOR|RENDERER|VERSION):' "$rundir/run.log" | sed 's/^/  /'

    say "--- extracting e:/$guest ---"
    python3 "$testing/extract_results.py" "$rundir/hdd.img" \
        -o "$rundir/out" -d "$guest" 2>&1 | tail -5

    # THE PROGRESS LOG IS THE ONLY PROOF THE ASKED-FOR TEST IS WHAT RAN. A
    # disc that ran a different set answers a different question and the
    # mistake is invisible in the images.
    local plog="$rundir/out/pgraph_progress_log.txt"
    [ -f "$plog" ] || die "no progress log: the run wrote nothing extractable"
    say "--- progress log ---"
    sed 's/^/  /' "$plog"
    grep -q "Testing completed normally" "$plog" \
        || die "the progress log does not say the suite completed normally"

    say "--- captures ---"
    ( cd "$rundir/out" && for f in *.png; do
        [ -e "$f" ] || continue
        printf '  %s  %s  %s bytes\n' "$(sha256sum "$f" | cut -c1-16)" "$f" "$(stat -c %s "$f")"
      done )

    # A machine-readable record, with the two fields that decide whether this
    # result may be compared with anything: the renderer, and device_label.
    # device_label is `desktop` so that ab_compare.py's cross-device check
    # sees a desktop/handheld pair for what it is.
    python3 - "$rundir" "$test" "$renderer" "$got" "$guest" <<'PY'
import hashlib, json, os, subprocess, sys
rundir, test, asked, got, guest = sys.argv[1:6]
out = os.path.join(rundir, "out")
caps = {}
for n in sorted(os.listdir(out)):
    if n.endswith(".png"):
        caps[n[:-4]] = hashlib.sha256(open(os.path.join(out, n), "rb").read()).hexdigest()
log = open(os.path.join(rundir, "run.log"), errors="replace").read()
def line(pfx):
    for l in log.splitlines():
        if l.startswith(pfx):
            return l.split(":", 1)[1].strip()
    return ""
json.dump({"device_label": "desktop", "renderer_asked": asked,
           "renderer_used": got, "test": test, "guest_dir": guest,
           "xemu_commit": line("xemu_commit"), "gl_renderer": line("GL_RENDERER"),
           "gl_version": line("GL_VERSION"), "captures": caps},
          open(os.path.join(rundir, "result.json"), "w"), indent=2, sort_keys=True)
print("wrote %s/result.json (%d capture(s))" % (rundir, len(caps)))
PY
}

cmd_env() {
    dc_export_env
    say "DC_ROOT         = $DC_ROOT"
    say "PREFIX          = $PREFIX"
    say "TREE            = $TREE"
    say "BUILD           = $BUILD"
    say "NINJA           = ${NINJA:-<none>}"
    say "MESON           = ${MESON:-<none>}"
    say "MULTIARCH       = $MULTIARCH"
    say "PKG_CONFIG_PATH = $PKG_CONFIG_PATH"
}

case "${1:-}" in
    deps)  shift; cmd_deps  "$@" ;;
    build) shift; cmd_build "$@" ;;
    smoke) shift; cmd_smoke "$@" ;;
    run)   shift; cmd_run   "$@" ;;
    env)   shift; cmd_env   "$@" ;;
    *) sed -n '/^# Usage:/,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
