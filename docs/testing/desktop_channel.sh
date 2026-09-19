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
    env)   shift; cmd_env   "$@" ;;
    *) sed -n '/^# Usage:/,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
