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
#   desktop_channel.sh serve           service the queue as the `desktop` lane
#   desktop_channel.sh claims <req>    exit 0 if `serve` would claim that request
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

# PINNED, not left to the default, and the pin is load-bearing on THIS channel
# specifically. surface_download_to_buffer() branches three ways for a swizzled
# download and the third -- generic, surface_scale_factor != 1 -- is
# assert(surface->pitch >= surface->width * bpp), which ABORTS on an undersized
# pitch. That is a live condition on the disc (Surface_pitch/Swizzle programs a
# 128x128 A8R8G8B8 surface at pitch 256), and it is reachable only from a
# scaled DESKTOP GL run: the Android path returns earlier through the RGBA8
# transfer branch, so neither handheld can hit it. config_spec.yml:237 defaults
# this to 1 today, so writing it changes nothing about what runs now -- it
# stops a future default change from turning every GL run on this channel into
# an abort whose cause is three files away.
[display.quality]
surface_scale = 1

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

# ------------------------------------------------------------------ serve
#
# THE WORKER. Everything above this line was reachable only by a human typing
# it. `lane.desktopchannel` built and folded the channel (PR #149) and left it
# connected to nothing: no serve mode, no unit, no `lanes/desktop`, so an
# explicit `--device desktop` request -- the ONLY route onto this target, by
# affinity.py's OFFPOOL -- sat in the queue unclaimed forever and nothing said
# so. A capability nothing can address is indistinguishable from an absent one.
#
# THE PROTOCOL IS THE HANDHELD WORKERS', DELIBERATELY AND EXACTLY.
# `affinity.py`'s serving() tests liveness with `kill -0` on the pid in
# `lanes/<label>` and nothing else, so this registers the same way, re-asserts
# every tick for the same reason (a `rm` by any actor cost five hours of
# unpinned pairs on 2026-09-19 because the file was written once per process),
# and releases only a file that still holds ITS OWN pid -- a trap that removes
# by name deletes its live successor's registration.
#
# WHAT IS DIFFERENT FROM A HANDHELD WORKER, AND WHY EACH DIFFERENCE IS THERE:
#
#   1. IT CLAIMS ONLY AN EXPLICIT DESKTOP PIN. dispatcher.sh's serve_one takes
#      a request when affinity says its own label OR says nothing; an empty
#      answer means "free, anyone may take it". This must NOT do that. A free
#      request is a request nobody asked to run on OpenGL/llvmpipe, and a
#      desktop worker that took one would score an Adreno-Vulkan golden against
#      a different renderer, driver and rasteriser -- the failure with no
#      symptom that OFFPOOL exists to prevent, reintroduced on the claim side.
#      So the test is equality with `desktop`, never emptiness. affinity.py is
#      still the single authority (rule 2 may legitimately answer `desktop` for
#      an arm whose sibling ran here); this only refuses to treat "" as yes.
#
#   2. IT SCORES NOTHING. The handheld path runs score_sweep.py against
#      /home/justin/goldens/results. Those goldens were captured on an Adreno
#      running Vulkan and a desktop GL capture that differs from them is
#      evidence about the renderer before it is evidence about xemu. So the
#      result carries `runs: []` and ab_compare.py REFUSES it -- which is the
#      correct outcome and is left exactly as it is. What the result does carry
#      is a per-capture sha256 per repeat, which is a desktop-against-desktop
#      instrument and the only sound one this channel has.
#
#   3. IT RUNS NAMED TESTS, NOT SUITES. cmd_run builds a one-test isolation
#      disc (make_isolation_discs.py --build-one), so a request must name its
#      tests in `only_tests`. A request naming only `suites` is REFUSED with an
#      ERROR rather than served with one test or with none: a desktop result
#      covering 1 capture where 236 were asked for is the shape of failure this
#      whole tree keeps paying for.
#
#   4. IT DOES NOT RE-EXEC ITSELF ON A SOURCE CHANGE. dispatcher.sh re-execs a
#      snapshot, which it can because the scripts it depends on are copied
#      wholesale; this one resolves $REPO, $DC_TESTING and its sibling Python
#      tools from its own path, so a snapshot outside the repo would break the
#      build and the disc builder. Instead the sha256 of the file that actually
#      ran is written into every result. A stale worker is then VISIBLE in the
#      artifact rather than silent -- the same trade `scorer_sha256` makes in
#      dispatcher.sh, where the recorded hash is the fact and the git revision
#      is the guess. A fold that touches this file needs
#      `systemctl --user restart hakux-desktop` to take effect.

DC_DEVICE_LABEL="desktop"
DC_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
DC_TESTING="$(dirname "$DC_SELF")"
DC_D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"

dc_log() {
    mkdir -p "$DC_D/logs" 2>/dev/null
    echo "$(date '+%m-%d %H:%M:%S') desktop: $*" \
        | tee -a "$DC_D/logs/desktop.log" >&2
}

# Scalar and list readers over a request. Same shape as dispatcher.sh's
# jq_get, kept here rather than sourced: dispatcher.sh runs device_env at
# import time and would exit 2 on a host with no matching serial.
dc_get() {
    python3 -c 'import json,sys
r=json.load(open(sys.argv[1]))
v=r.get(sys.argv[2])
print(sys.argv[3] if v in (None, "") else v)' "$1" "$2" "${3:-}" 2>/dev/null
}
dc_list() {
    python3 -c 'import json,sys
for x in (json.load(open(sys.argv[1])).get(sys.argv[2]) or []): print(x)' \
        "$1" "$2" 2>/dev/null
}

# WHICH RENDERER, AND WHY IT COMES OUT OF `env`. The renderer is an xemu.toml
# key and request.sh has no selector for it -- which is the stated blocker on
# `undersized-pitch-swizzle-layout.json`, whose two arms differ in NOTHING BUT
# the renderer and whose a_ref is consequently the unresolvable prose string
# "4129a349e6 with xemu.toml [display] renderer = OpenGL". request.sh DOES
# already carry `--env KEY=VALUE` through to the request, so this reads
# HAKUX_RENDERER from there and needs no change to a file this lane does not
# own. Default OPENGL: that is the renderer neither handheld can run and the
# only reason this channel exists.
dc_renderer() {
    local v
    v="$(python3 -c 'import json,sys
e=json.load(open(sys.argv[1])).get("env") or []
if isinstance(e, dict): e=["%s=%s"%(k,x) for k,x in e.items()]
for item in e:
    k,_,val = str(item).partition("=")
    if k.strip()=="HAKUX_RENDERER": print(val.strip().upper())' "$1" 2>/dev/null)"
    case "$v" in
        OPENGL|VULKAN) printf '%s\n' "$v" ;;
        "")            printf 'OPENGL\n' ;;
        *)             printf 'BAD:%s\n' "$v" ;;
    esac
}

dc_lane_file() { printf '%s\n' "$DC_D/lanes/$DC_DEVICE_LABEL"; }

dc_lane_claim() {
    local f; f="$(dc_lane_file)"
    [ "$(cat "$f" 2>/dev/null)" = "$$" ] && return 0
    mkdir -p "$DC_D/lanes" 2>/dev/null
    printf '%s\n' "$$" > "$f" 2>/dev/null
}

dc_lane_release() {
    local f; f="$(dc_lane_file)"
    # Only if it still holds MY pid. A worker outliving its supervisor, a
    # fresh worker registering under the same label, and the old one's EXIT
    # trap firing afterwards is the one mechanism that fits every observation
    # of the 2026-09-19 outage -- and a trap that removes by name cannot tell
    # that case from a clean exit.
    [ "$(cat "$f" 2>/dev/null)" = "$$" ] || return 0
    rm -f "$f"
}

# Would `serve` claim this request? EQUALITY, never emptiness -- see (1) above.
dc_would_claim() {   # <dispatch-dir> <request.req>
    local want
    want="$(python3 "$DC_TESTING/affinity.py" "$1" "$2" 2>/dev/null)"
    [ "$want" = "$DC_DEVICE_LABEL" ]
}

cmd_claims() {
    local req="${1:?usage: $0 claims <request.req>}"
    [ -f "$req" ] || die "no such request: $req"
    dc_would_claim "$DC_D" "$req"
}

# Hand the request back as a finished result. Every post-claim exit goes
# through this: dispatcher.sh grew seven exits that each forgot the owner file
# and running/ filled with markers for finished work.
dc_finish() {   # <id> <rdir> <running-req>
    mv "$3" "$2/request.json" 2>/dev/null
    rm -f "$DC_D/running/$1.owner"
    touch "$2/DONE"
}

dc_refuse() {   # <id> <rdir> <running-req> <message...>
    local id="$1" rdir="$2" req="$3"; shift 3
    printf '%s\n' "$*" > "$rdir/ERROR"
    dc_log "  REFUSED $id: $*"
    dc_finish "$id" "$rdir" "$req"
}

dc_serve_one() {   # <queued request path> ; 0 = served, 1 = not mine
    local req="$1" id rdir
    id="$(basename "$req" .req)"
    dc_would_claim "$DC_D" "$req" || return 1
    # Claiming is `mv`, an atomic rename that either wins or returns non-zero.
    # Losing it means somebody else got there first, which is the mutex working.
    mv "$req" "$DC_D/running/$id.req" 2>/dev/null || return 1
    printf '%s\n' "$DC_DEVICE_LABEL" > "$DC_D/running/$id.owner"
    req="$DC_D/running/$id.req"
    rdir="$DC_D/results/$id"; mkdir -p "$rdir"

    local ref requester purpose runs renderer title
    ref="$(dc_get "$req" ref HEAD)"
    requester="$(dc_get "$req" requester unknown)"
    purpose="$(dc_get "$req" purpose "")"
    runs="$(dc_get "$req" runs 1)"
    title="$(dc_get "$req" title "")"
    renderer="$(dc_renderer "$req")"
    local only=(); mapfile -t only < <(dc_list "$req" only_tests)
    dc_log "request $id from $requester: $purpose (ref=$ref renderer=$renderer runs=$runs)"

    case "$renderer" in
        BAD:*) dc_refuse "$id" "$rdir" "$req" \
            "env HAKUX_RENDERER=${renderer#BAD:} is not OPENGL or VULKAN; refusing rather than falling back to a renderer nobody asked for"
            return 0 ;;
    esac
    if [ -n "$title" ]; then
        dc_refuse "$id" "$rdir" "$req" \
            "this is a soak request (title=$title). The desktop channel has no title library and no lease; soaks belong on a handheld."
        return 0
    fi
    if [ "${#only[@]}" -eq 0 ] || [ -z "${only[0]:-}" ]; then
        dc_refuse "$id" "$rdir" "$req" \
"no only_tests. The desktop channel builds a ONE-TEST isolation disc per run
(make_isolation_discs.py --build-one), so it cannot serve a request that names
only suites -- and serving one test where a whole suite was asked for would
produce a plausible result about the wrong thing. Re-queue with
  request.sh --device desktop --only-tests 'Suite::Test[,Suite::Test...]'
Running a multi-suite disc here needs make_test_iso.py wired into cmd_run; see
docs/lanes/glchannel/NOTES.md."
        return 0
    fi

    # THE BUILD, under a lock and in a SUBSHELL. cmd_build and cmd_run both
    # call die(), which is `exit 2` -- called directly from this loop that
    # would take the whole worker down on the first bad request, and the lane
    # file would go with it. The lock is against a human running
    # `desktop_channel.sh build` by hand: there is one $BUILD directory and two
    # configures in it produce whichever binary finished last, silently.
    local buildlog="$LOGS/serve-$id-build.log"
    mkdir -p "$LOGS"
    ( flock 9; cmd_build "$ref" ) 9>"$DC_ROOT/.build.lock" >"$buildlog" 2>&1
    local rc=$?
    if [ "$rc" -ne 0 ]; then
        { echo "build failed for ref $ref (code $rc)"
          grep -m5 -hE 'REFUSING:|FAILED:|error:|CONFIGURE_EXIT|NINJA_EXIT|MISSING RUNTIME' \
               "$buildlog" 2>/dev/null | cut -c1-200 | sed 's/^/  /'
          echo "  full log: $buildlog"
        } > "$rdir/ERROR"
        dc_log "  BUILD FAILED (code $rc); see $buildlog"
        dc_finish "$id" "$rdir" "$req"
        return 0
    fi
    local binsha xemusha
    binsha="$(sha256sum "$BUILD/qemu-system-i386" 2>/dev/null | cut -c1-12)"
    xemusha="$(git -C "$TREE" rev-parse --short=10 HEAD 2>/dev/null || echo unknown)"
    dc_log "  binary $binsha (xemu $xemusha)"

    local n t tag slug rundir failed=0
    for n in $(seq 1 "$runs"); do
        for t in "${only[@]}"; do
            [ -n "$t" ] || continue
            slug="$(printf '%s' "$t" | tr -c 'A-Za-z0-9' '_')"
            tag="$id.r$n.$slug"
            rundir="$DC_ROOT/runs/$tag"
            dc_log "  run $n: $t"
            ( cmd_run "$t" "$tag" "$renderer" ) >"$rdir/$tag.log" 2>&1 || failed=$((failed + 1))
            mkdir -p "$rdir/$tag"
            cp "$rundir/result.json" "$rundir/run.log" "$rdir/$tag/" 2>/dev/null
            [ -d "$rundir/out" ] && cp -r "$rundir/out" "$rdir/$tag/out" 2>/dev/null
            # THE DISK IMAGE GOES, AND THIS IS NOT TIDINESS. Every run copies a
            # fresh multi-GB hdd.img (it must: a reused disk lets run N extract
            # run N-1's captures and look healthy doing it). A dynamically
            # expanding WSL VHDX never returns deleted blocks to the host and
            # 12 GB in an afternoon killed the VM once already, so a worker
            # that keeps one per run per request fills the disk in a night.
            rm -rf "$rundir"
        done
    done

    # A QUOTED heredoc. This source carries quotes, backslashes and `$`, and a
    # `python3 -c "..."` shell string exposes every one of them to the shell
    # before Python sees it -- which is how the disc_id block in dispatcher.sh
    # came to be running command substitution over its own comments.
    DC_SELFSHA="$(sha256sum "$DC_SELF" | cut -c1-12)" \
    python3 - "$rdir" "$id" "$renderer" "$ref" "$xemusha" "$binsha" \
                "$requester" "$purpose" "$failed" "$runs" <<'PYRES'
import hashlib, json, os, sys

(rdir, rid, renderer, ref, xemusha, binsha, who, purpose, failed,
 runs) = sys.argv[1:11]

# Each run's own result.json, written by cmd_run, is the record of what that
# invocation actually did -- including renderer_used, which is checked against
# renderer_asked there because asking for one renderer and silently getting
# the other is #29 and cost a whole set of results believed to be Vulkan.
per_run = []
for tag in sorted(os.listdir(rdir)):
    p = os.path.join(rdir, tag, "result.json")
    if not os.path.isfile(p):
        continue
    try:
        with open(p) as fh:
            r = json.load(fh)
    except Exception as e:
        per_run.append({"tag": tag, "ok": False, "error": "unreadable: %s" % e})
        continue
    r["tag"] = tag
    r["ok"] = bool(r.get("captures"))
    per_run.append(r)

# THE ONLY SOUND INSTRUMENT THIS CHANNEL HAS: desktop against desktop. A
# capture is compared with the SAME capture from another repeat of this
# request, by sha256, and nothing here is ever compared with
# /home/justin/goldens/results -- those were captured on an Adreno running
# Vulkan, and a GL/llvmpipe capture that differs from them is evidence about
# the renderer, the driver and the rasteriser before it is evidence about
# xemu. `agreement` counts DISTINCT shas per capture name: 1 means every
# repeat produced the byte-identical image, >1 names a capture that moved
# between repeats of one binary, which is a finding on its own.
shas = {}
for r in per_run:
    for name, sha in (r.get("captures") or {}).items():
        shas.setdefault(name, []).append(sha)
agreement = {k: len(set(v)) for k, v in sorted(shas.items())}

# disc_id, and what is deliberately NOT in it.
#
# IN: the test list, because a result over one test and a result over five are
# not the same experiment, and `desktop/`, because a desktop disc_id must
# never compare equal to a handheld one -- ab_compare refuses a pair whose
# disc_ids differ, and that refusal is the outer guard on the comparability
# rule this channel must not weaken.
#
# OUT: THE RENDERER. It is the independent variable of the one A/B this
# channel exists to make possible (undersized-pitch-swizzle-layout.json: two
# arms, one commit, GL against Vulkan), and folding an independent variable
# into the comparability key makes ab_compare refuse the very comparison the
# feature was added to enable. ab_compare.py makes exactly this argument about
# `env` and dispatcher.sh keeps env out of disc_id for exactly this reason.
tests = sorted({r.get("test", "") for r in per_run if r.get("test")})
disc = "desktop/only%d:%s" % (
    len(tests), hashlib.sha1(",".join(tests).encode()).hexdigest()[:8])

meta = {
    # `apk_sha` is a hash of the BINARY on the handheld path, not of the ref,
    # and the same must hold here or two builds of one sha would be
    # indistinguishable in every result. This is sha256(qemu-system-i386).
    "apk_sha": binsha,
    "kind": "desktop",
    "disc_id": disc,
    "requester": who,
    "purpose": purpose,
    "ref": ref,
    "xemu_commit": xemusha,
    "device_label": "desktop",
    "device_serial": "",
    "renderer_asked": renderer,
    "renderer_used": sorted({r.get("renderer_used", "") for r in per_run}),
    # WHAT CODE PRODUCED THIS. desktop_channel.sh does not re-exec itself on a
    # source change, so a fold can leave a running worker on older code; the
    # recorded hash makes that visible in the artifact instead of silent.
    "worker_sha256": os.environ.get("DC_SELFSHA", "unknown"),
    "tests": tests,
    "runs_requested": int(runs or 1),
    "runs_failed": int(failed or 0),
    "desktop_runs": per_run,
    "repeat_agreement": agreement,
    # EMPTY ON PURPOSE, AND THE REFUSAL IT CAUSES IS THE POINT. ab_compare.py
    # dies on an arm with no `runs`, and this channel has none because scoring
    # would mean score_sweep.py against the Adreno Vulkan goldens. Read
    # `repeat_agreement` and `desktop_runs[].captures` instead.
    "runs": [],
    "note": ("desktop GL/llvmpipe channel: NOT scored against "
             "/home/justin/goldens/results, which are Adreno Vulkan captures. "
             "ab_compare.py refuses this result and that is correct. The "
             "sound comparison is desktop against desktop: see "
             "repeat_agreement and desktop_runs[].captures."),
}
with open(os.path.join(rdir, "result.json"), "w") as fh:
    json.dump(meta, fh, indent=2, sort_keys=True)
print("wrote %s/result.json (%d run(s), %d capture name(s))"
      % (rdir, len(per_run), len(agreement)))
PYRES
    # Checked on its own line rather than as `<<'PYRES' \ || {...}`: a line
    # continuation after the heredoc operator moves where the BODY starts, so
    # the first two lines of the error handler become Python source. Caught by
    # `bash -n` here; it would otherwise be a syntax error in the daemon.
    if [ "$?" -ne 0 ]; then
        dc_log "  RESULT WRITER FAILED"
        echo "the result writer failed; the per-run dirs under $rdir are the evidence" \
            >> "$rdir/ERROR"
    fi
    dc_log "  done: $failed of $((runs * ${#only[@]})) run(s) failed -> $rdir"
    dc_finish "$id" "$rdir" "$req"
    return 0
}

cmd_serve() {
    mkdir -p "$DC_D"/{queue,running,results,lanes,logs,hold} "$DC_ROOT" "$LOGS" \
        || die "cannot create $DC_D"
    dc_lane_claim
    # BOTH TRAPS, and the second is not decoration: systemd stops a unit with
    # SIGTERM, and bash does not run an EXIT trap for a fatal signal it has no
    # handler for. Without this, every `systemctl --user stop hakux-desktop`
    # would leave `lanes/desktop` behind holding a dead pid. serving()'s
    # `kill -0` would still reject it, so the cost is not a wrong answer -- it
    # is a registration nobody can distinguish from a live one by looking, and
    # this directory has already cost five hours to exactly that kind of
    # ambiguity.
    trap dc_lane_release EXIT
    trap 'exit 0' TERM INT
    # Only OUR orphans. An owner-less entry in running/ is NOT ours by
    # default: treating one as ours is how a live run on another worker gets
    # requeued and served twice into one result id.
    local orphan oid owner
    for orphan in "$DC_D"/running/*.req; do
        [ -e "$orphan" ] || continue
        oid="$(basename "$orphan" .req)"
        owner="$(cat "$DC_D/running/$oid.owner" 2>/dev/null)"
        [ "$owner" = "$DC_DEVICE_LABEL" ] || continue
        dc_log "requeueing orphan $oid from a previous loop"
        rm -f "$DC_D/running/$oid.owner"
        mv "$orphan" "$DC_D/queue/" 2>/dev/null || true
    done
    dc_log "=== desktop channel serving; queue=$DC_D/queue self=$(sha256sum "$DC_SELF" | cut -c1-12) ==="
    local held=0 r reqs served
    while :; do
        shopt -s nullglob
        # A hold takes this target out of service without stopping the unit,
        # the same file and the same semantics as a handheld's. Checked BEFORE
        # the registration is re-asserted, or a held target would re-register
        # itself on the next tick and affinity would pin a pair to it.
        if [ -e "$DC_D/hold/$DC_DEVICE_LABEL" ]; then
            [ "$held" = 1 ] || dc_log "HELD by $DC_D/hold/$DC_DEVICE_LABEL; claiming nothing"
            held=1
            dc_lane_release
            sleep "${DC_POLL:-30}"
            [ "${DC_SERVE_ONCE:-0}" = 1 ] && return 0
            continue
        fi
        [ "$held" = 1 ] && { dc_log "hold released; serving again"; held=0; }
        dc_lane_claim
        reqs=("$DC_D"/queue/*.req)
        served=0
        # ${a[@]+"${a[@]}"} rather than "${a[@]}": `set -u` is in force at the
        # top of this file and an empty array under it is an unbound-variable
        # error on bash before 4.4. An empty queue is this loop's NORMAL state,
        # so getting that wrong would take the worker down on its first idle
        # tick on any host older than this one.
        for r in ${reqs[@]+"${reqs[@]}"}; do
            # Walk the whole queue rather than stopping at [0]: the head is
            # almost always a handheld's, and stopping there would idle this
            # target behind work it is not allowed to do.
            if dc_serve_one "$r"; then served=1; break; fi
        done
        # DC_SERVE_ONCE exists for the self-test, which cannot run a daemon
        # forever. It leaves the loop AFTER a full tick -- registration,
        # claim decision, service -- so the thing the test observes is the
        # thing production runs, not a reduced version of it.
        [ "${DC_SERVE_ONCE:-0}" = 1 ] && return 0
        [ "$served" = 1 ] || sleep "${DC_POLL:-10}"
    done
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
    serve) shift; cmd_serve "$@" ;;
    claims) shift; cmd_claims "$@" ;;
    env)   shift; cmd_env   "$@" ;;
    *) sed -n '/^# Usage:/,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
