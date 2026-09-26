#!/usr/bin/env bash
# Build this worktree's desktop binary into build-linux/ (gitignored), with
# the desktop channel's rootless dependency prefix. The same configure line
# as desktop_channel.sh cmd_build; the tree is this one, not a private
# worktree, so what is built is exactly what is committed or edited here.
#
#   docs/lanes/ring53impl/dc_build.sh      -> prints NINJA_EXIT=<rc>
set -u
TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PREFIX="${DC_PREFIX:-/home/justin/hakux-work/desktop/deps/prefix}"
MULTIARCH="$(gcc -print-multiarch 2>/dev/null || echo x86_64-linux-gnu)"
NINJA=/home/justin/Android/Sdk/cmake/3.30.3/bin/ninja
[ -x "$NINJA" ] || NINJA="$(command -v ninja)"
MESON="$HOME/.local/bin/meson"
[ -x "$MESON" ] || MESON="$(command -v meson)"
export PKG_CONFIG_PATH="$PREFIX/usr/lib/$MULTIARCH/pkgconfig:$PREFIX/usr/share/pkgconfig:$PREFIX/usr/lib/pkgconfig:/usr/lib/$MULTIARCH/pkgconfig:/usr/share/pkgconfig:/usr/lib/pkgconfig"
export PATH="$(dirname "$NINJA"):$(dirname "$MESON"):$PATH"
CFL="-isystem $PREFIX/usr/include -isystem $PREFIX/usr/include/$MULTIARCH"
LDF="-L$PREFIX/usr/lib/$MULTIARCH -L$PREFIX/usr/lib"
export LD_LIBRARY_PATH="$PREFIX/usr/lib/$MULTIARCH:$PREFIX/usr/lib"
BUILD="$TREE/build-linux"
LOG="$TREE/docs/lanes/ring53impl/.build.log"
if [ ! -f "$BUILD/build.ninja" ]; then
    mkdir -p "$BUILD"
    ( cd "$BUILD" && ../configure --target-list=i386-softmmu \
        --extra-cflags="-DXBOX=1 $CFL" --extra-ldflags="$LDF" \
        --disable-werror --disable-docs --disable-guest-agent --disable-tools ) >"$LOG.configure" 2>&1
    echo "CONFIGURE_EXIT=$?"
fi
"$NINJA" -C "$BUILD" -j"$(nproc)" qemu-system-i386 >"$LOG" 2>&1
rc=$?
echo "NINJA_EXIT=$rc"
[ "$rc" -eq 0 ] || grep -E 'FAILED:|error:' "$LOG" | head -30
