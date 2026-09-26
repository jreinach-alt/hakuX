#!/usr/bin/env bash
#
#   tools/turnip/build.sh [--clean]
#
# Reproducible hakuX Turnip: Mesa's freedreno Vulkan driver, cross-built for
# Android arm64 with the NDK, packaged in the adrenotools shape the fleet's T30
# uses (meta.json + vulkan.<name>.so, zipped as .adpkg.zip).
#
# Everything that decides the binary is pinned here: the Mesa sha, the NDK,
# meson and mako versions, the meson options and the API level. The Mesa tree
# and the build live OUTSIDE the repository (the brief's rule), under
# $WORK/mesa-turnipfork and $WORK/turnipfork-build.
#
# Options mirror what T30 evidently is (docs/investigations/
# adreno-driver-feasibility.md): Mesa 26.3.0-devel, KGSL only, Vulkan 1.4
# exposed at minApi 30 -- which needs android-strict=false, because strict mode
# caps the API version by ANDROID_API_LEVEL -- and UNSTRIPPED, so a simpleperf
# capture taken with it installed symbolizes (tools/turnip/driver_share.py).
#
# PATCHES: every *.patch in tools/turnip/patches/ is applied, in name order,
# on a clean checkout of MESA_SHA. The control build has none; that is what
# makes it the control.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK:-/home/justin/hakux-work}"
MESA_URL="https://gitlab.freedesktop.org/mesa/mesa.git"
MESA_SHA="4c18636110f0ef2e1d4cecdbfbf4b7126c1d22cc"   # main, 2026-09-25, 26.3.0-devel
NDK="${NDK:-/home/justin/Android/Sdk/ndk/29.0.14206865}"
API=30
MESON_VER=1.9.1
MAKO_VER=1.3.10
NAME="${TURNIP_NAME:-hakux}"            # -> vulkan.$NAME.so
SRC="$WORK/mesa-turnipfork"
VENV="$WORK/turnipfork-venv"
OUT="$WORK/turnipfork-build"
BUILD="$OUT/build"
# bison, flex and ninja come from the nxdk tool bundle on this host.
TOOLS="${TOOLS:-/home/justin/.local/nxdk-tools/bin}"
export BISON_PKGDATADIR="${BISON_PKGDATADIR:-/home/justin/.local/nxdk-tools/root/usr/share/bison}"
# bison runs m4 (ir3_parser.y); the bundle has one but not on the tools PATH.
export M4="${M4:-/home/justin/.local/nxdk-tools/root/usr/bin/m4}"
export PATH="$VENV/bin:$TOOLS:$PATH"

[ "${1:-}" = "--clean" ] && rm -rf "$BUILD"

# --- sources -----------------------------------------------------------------
if [ ! -d "$SRC/.git" ]; then
    git clone --filter=blob:none --no-checkout "$MESA_URL" "$SRC"
fi
git -C "$SRC" cat-file -e "$MESA_SHA^{commit}" 2>/dev/null || git -C "$SRC" fetch origin
if [ -n "$(git -C "$SRC" status --porcelain --untracked-files=no)" ] ||
   [ "$(git -C "$SRC" rev-parse HEAD 2>/dev/null)" != "$MESA_SHA" ]; then
    git -C "$SRC" checkout -q -f --detach "$MESA_SHA"
fi
PATCHES=()
if compgen -G "$HERE/patches/*.patch" >/dev/null; then
    PATCHES=("$HERE"/patches/*.patch)
fi
for p in "${PATCHES[@]}"; do
    echo "applying $(basename "$p")"
    git -C "$SRC" apply --index "$p"
done

# --- host tools ----------------------------------------------------------------
if [ ! -x "$VENV/bin/meson" ] || [ "$("$VENV/bin/meson" --version)" != "$MESON_VER" ]; then
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q "meson==$MESON_VER" "mako==$MAKO_VER" pyyaml packaging
fi
for t in bison flex ninja; do command -v "$t" >/dev/null || { echo "missing $t" >&2; exit 2; }; done

# glslangValidator (Mesa compiles its internal GLSL shaders with it). Not on
# this host and not in the NDK, which ships glslc only; built once, pinned.
GLSLANG_TAG=15.4.0
GLSLANG="$WORK/turnipfork-glslang"
if [ ! -x "$GLSLANG/install/bin/glslangValidator" ]; then
    rm -rf "$GLSLANG"
    git clone -q --depth 1 --branch "$GLSLANG_TAG" \
        https://github.com/KhronosGroup/glslang.git "$GLSLANG/src"
    CMAKE="${CMAKE:-/home/justin/.local/nv2a-venv/bin/cmake}"
    "$CMAKE" -S "$GLSLANG/src" -B "$GLSLANG/build" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DENABLE_OPT=OFF -DGLSLANG_TESTS=OFF \
        -DENABLE_GLSLANG_BINARIES=ON -DCMAKE_INSTALL_PREFIX="$GLSLANG/install"
    ninja -C "$GLSLANG/build" install
fi
export PATH="$GLSLANG/install/bin:$PATH"

# --- cross file ----------------------------------------------------------------
TC="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
mkdir -p "$OUT"
CROSS="$OUT/android-aarch64.ini"
cat > "$CROSS" <<EOF
[binaries]
ar = '$TC/llvm-ar'
c = ['$TC/aarch64-linux-android$API-clang']
cpp = ['$TC/aarch64-linux-android$API-clang++', '-fno-exceptions', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '-static-libstdc++']
c_ld = 'lld'
cpp_ld = 'lld'
strip = '$TC/llvm-strip'
pkg-config = ['env', 'PKG_CONFIG_LIBDIR=$OUT/pkgconfig-empty', '/usr/bin/pkg-config']

[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'armv8'
endian = 'little'
EOF
mkdir -p "$OUT/pkgconfig-empty"

# --- configure and build -------------------------------------------------------
if [ ! -f "$BUILD/build.ninja" ]; then
    meson setup "$BUILD" "$SRC" --cross-file "$CROSS" \
        -Dbuildtype=release \
        -Dplatforms=android \
        -Dplatform-sdk-version=$API \
        -Dandroid-stub=true \
        -Dandroid-strict=false \
        -Dandroid-libbacktrace=disabled \
        -Dgallium-drivers= \
        -Dvulkan-drivers=freedreno \
        -Dfreedreno-kmds=kgsl \
        -Dvulkan-beta=true \
        -Dopengl=false -Degl=disabled -Dgles1=disabled -Dgles2=disabled -Dglx=disabled \
        -Dllvm=disabled -Dzstd=disabled -Dexpat=disabled -Dxmlconfig=disabled \
        -Dbuild-tests=false -Db_lto=false -Dstrip=false \
        -Dcpp_args=-Wno-c++11-narrowing
    # ^ tu_cs.h:295 at MESA_SHA braces a size_t into uint16_t, which NDK
    #   clang++ rejects as an error; a flag, not a patch, keeps the control
    #   patch-free. The soname stays libvulkan_freedreno.so (T30's is
    #   vulkan.purple.so; tools/turnip/compare_pkg.sh shows both): setting
    #   -Dc_link_args/-Dcpp_link_args to change it dropped the android stub
    #   libraries from the link.
fi
ninja -C "$BUILD" src/freedreno/vulkan/libvulkan_freedreno.so

# --- package -------------------------------------------------------------------
SO="$BUILD/src/freedreno/vulkan/libvulkan_freedreno.so"
PKG="$OUT/pkg"
rm -rf "$PKG"; mkdir -p "$PKG"
cp "$SO" "$PKG/vulkan.$NAME.so"
PATCHSET="none"
if [ ${#PATCHES[@]} -gt 0 ]; then
    PATCHSET="$(cat "${PATCHES[@]}" | sha256sum | cut -c1-12)"
fi
VERSION="$(cat "$SRC/VERSION")"
python3 - "$PKG/meta.json" "$NAME" "$VERSION" "${MESA_SHA:0:12}" "$PATCHSET" "$API" <<'PY'
import json, sys
path, name, version, sha, patchset, api = sys.argv[1:]
json.dump({
    "schemaVersion": 1,
    "name": "hakuX Turnip (Mesa %s, patches %s)" % (sha, patchset),
    "description": "hakuX build of Mesa Turnip from tools/turnip/build.sh",
    "author": "hakuX",
    "packageVersion": "%s-%s" % (sha, patchset),
    "vendor": "Mesa",
    "driverVersion": "%s-%s" % (version, sha),
    "minApi": int(api),
    "libraryName": "vulkan.%s.so" % name,
}, open(path, "w"), indent=2)
PY
ZIP="$OUT/turnip_${NAME}_${MESA_SHA:0:12}_${PATCHSET}.adpkg.zip"
rm -f "$ZIP"
(cd "$PKG" && python3 -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1],'w',zipfile.ZIP_DEFLATED); [z.write(f) for f in ('meta.json', sys.argv[2])]" "$ZIP" "vulkan.$NAME.so")
echo "built $ZIP"
sha256sum "$PKG/vulkan.$NAME.so" "$ZIP"
