#!/usr/bin/env bash
#
#   docs/lanes/turnipcost569/build_glslang.sh
#
# Host glslang at the commit the Android build pins
# (android/app/src/main/cpp/CMakeLists.txt:263), built twice:
#   $OUT/glslang-noopt  ENABLE_OPT=OFF, as the device ships it (:264)
#   $OUT/glslang-opt    ENABLE_OPT=ON with SPIRV-Tools from glslang's own
#                       known_good.json, for the optimizer leg
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$(realpath -m "${OUT:-$HERE/../../../.scratch}")"
REV=b5782e52ee2f7b3e40bb9c80d15b47016e008bc9
CMAKE="${CMAKE:-/home/justin/.local/nv2a-venv/bin/cmake}"
export PATH="/home/justin/.local/nxdk-tools/bin:$PATH"
SRC="$OUT/glslang-src"

if [ ! -d "$SRC/.git" ]; then
    git init -q "$SRC"
    git -C "$SRC" remote add origin https://github.com/KhronosGroup/glslang.git
fi
if [ "$(git -C "$SRC" rev-parse HEAD 2>/dev/null)" != "$REV" ]; then
    git -C "$SRC" fetch -q --depth 1 origin "$REV"
    git -C "$SRC" checkout -q -f FETCH_HEAD
fi

build() {  # dir opt
    local B="$OUT/$1"
    "$CMAKE" -S "$SRC" -B "$B/build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DENABLE_OPT="$2" -DENABLE_HLSL=OFF -DENABLE_GLSLANG_BINARIES=ON \
        -DENABLE_SPVREMAPPER=OFF -DENABLE_CTEST=OFF -DGLSLANG_TESTS=OFF \
        -DBUILD_SHARED_LIBS=OFF -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
        -DCMAKE_INSTALL_PREFIX="$B/install" >/dev/null
    ninja -C "$B/build" install >/dev/null
    echo "built $B"
}
build glslang-noopt OFF

if [ ! -d "$SRC/External/spirv-tools" ]; then
    (cd "$SRC" && python3 update_glslang_sources.py)
fi
build glslang-opt ON
