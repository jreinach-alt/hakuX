#!/usr/bin/env bash
#
#   docs/lanes/turnipcost569/build_host_turnip.sh [--clean]
#
# Host (x86_64) build of Mesa's Turnip plus the freedreno noop drm-shim, so
# Turnip's compiler runs on this PC as if on an Adreno 740 (FD_GPU_ID=740).
#
# Same Mesa sha as tools/turnip/build.sh (main 2026-09-25, 26.3.0-devel). The
# fleet's T30 reports "26.3.0-devel (git-62ac221a33)"; 62ac221a33 is not on
# Mesa main (a fork commit), so this is the closest public tree of the same
# series. T30 has no nir_validate symbol (NDEBUG build), so this build is
# NDEBUG too, at -O2 with full debug info and frame pointers for the sampler.
#
# Reuses lane.turnipfork's host tools: its Mesa clone (read only, shared
# clone), meson venv, glslangValidator, and the nxdk bison/flex/ninja bundle.
# Everything this script writes is under $OUT (default: the lane's .scratch/,
# which is git-ignored).
set -euo pipefail

WORK="${WORK:-/home/justin/hakux-work}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$(realpath -m "${OUT:-$HERE/../../../.scratch}")"
MESA_SHA="4c18636110f0ef2e1d4cecdbfbf4b7126c1d22cc"
SRC_ORIGIN="$WORK/mesa-turnipfork"
SRC="$OUT/mesa"
BUILD="$OUT/mesa-build"
VENV="$WORK/turnipfork-venv"
TOOLS="${TOOLS:-/home/justin/.local/nxdk-tools/bin}"
export BISON_PKGDATADIR="${BISON_PKGDATADIR:-/home/justin/.local/nxdk-tools/root/usr/share/bison}"
export M4="${M4:-/home/justin/.local/nxdk-tools/root/usr/bin/m4}"
export PATH="$VENV/bin:$TOOLS:$WORK/turnipfork-glslang/install/bin:$PATH"

[ "${1:-}" = "--clean" ] && rm -rf "$BUILD"

if [ ! -d "$SRC/.git" ]; then
    git clone -q --shared --no-checkout "$SRC_ORIGIN" "$SRC"
fi
if [ ! -f "$SRC/meson.build" ] ||
   [ "$(git -C "$SRC" rev-parse HEAD 2>/dev/null)" != "$MESA_SHA" ]; then
    git -C "$SRC" checkout -q -f --detach "$MESA_SHA"
fi

for t in meson bison flex ninja glslangValidator; do
    command -v "$t" >/dev/null || { echo "missing $t" >&2; exit 2; }
done

if [ ! -f "$BUILD/build.ninja" ]; then
    meson setup "$BUILD" "$SRC" \
        -Dbuildtype=custom -Doptimization=2 -Ddebug=true -Db_ndebug=true \
        -Dc_args='-fno-omit-frame-pointer' -Dcpp_args='-fno-omit-frame-pointer' \
        -Dplatforms= \
        -Dgallium-drivers= \
        -Dvulkan-drivers=freedreno \
        -Dfreedreno-kmds=msm \
        -Dtools=drm-shim \
        -Dopengl=false -Degl=disabled -Dgles1=disabled -Dgles2=disabled -Dglx=disabled \
        -Dllvm=disabled -Dzstd=disabled -Dexpat=disabled -Dxmlconfig=disabled \
        -Dvalgrind=disabled -Dlibunwind=disabled \
        -Dbuild-tests=false -Db_lto=false -Dstrip=false
fi
ninja -C "$BUILD" src/freedreno/vulkan/libvulkan_freedreno.so \
    src/freedreno/drm-shim/libfreedreno_noop_drm_shim.so
echo "BUILD_OK $BUILD"
