#!/usr/bin/env bash
#   run_harness.sh <manifest> <reps> [samples.bin]  -> TSV on stdout
# Runs vkharness against the host Turnip through the Adreno 740 drm-shim,
# with every cache off so each rep is a cold compile.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$(realpath -m "${OUT:-$HERE/../../../.scratch}")"
B="$S/mesa-build"
gcc -O2 -g -Wall -I"$S/mesa/include" -o "$S/vkharness" "$HERE/vkharness.c" -ldl
exec env LD_PRELOAD="$B/src/freedreno/drm-shim/libfreedreno_noop_drm_shim.so" \
    FD_GPU_ID=740 VK_ENABLE_PIPELINE_CACHE=false MESA_SHADER_CACHE_DISABLE=true \
    "$S/vkharness" "$B/src/freedreno/vulkan/libvulkan_freedreno.so" "$@"
