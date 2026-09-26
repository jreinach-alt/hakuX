#!/bin/bash
# Compile every line-mode triangle geometry shader variant this lane adds
# with glslc: Vulkan and GL, cull face 0-3, front CW/CCW, flat/smooth.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
gd="$here/../../testing/geom_dump"
glslc=${GLSLC:-$HOME/Android/Sdk/ndk/29.0.14206865/shader-tools/linux-x86_64/glslc}
out=$(mktemp -d "$here/.check.XXXXXX")
trap 'rm -rf "$out"' EXIT

make -s -C "$gd"
cc -std=gnu11 -I"$gd/../psh_differ/shim" -I"$here/../../../include" \
   -I"$here/../../.." -I"$here/../../../hw/xbox/nv2a/pgraph/glsl" \
   $(pkg-config --cflags glib-2.0) -o "$out/cull_dump" "$here/cull_dump.c" \
   "$gd/build/geom.o" "$gd/build/common.o" $(pkg-config --libs glib-2.0) -lm

fail=0
n=0
for api in vk gl; do
    # GL GLSL declares no locations; SPIR-V wants them, the GL driver not.
    if [ "$api" = vk ]; then env=vulkan1.1; else env="opengl -fauto-map-locations"; fi
    for face in 0 1 2 3; do
        for ccw in 0 1; do
            for smooth in 0 1; do
                f="$out/${api}_${face}_${ccw}_${smooth}.geom"
                "$out/cull_dump" "$api" "$face" "$ccw" "$smooth" > "$f"
                n=$((n + 1))
                # shellcheck disable=SC2086
                if ! "$glslc" --target-env=$env -fshader-stage=geom \
                        -o /dev/null "$f"; then
                    echo "FAIL $f"
                    fail=1
                fi
            done
        done
    done
done
# One sample, so the reader sees what the face test compiles from.
"$out/cull_dump" vk 2 0 1 | sed -n '/^void main/,$p'
echo "compiled $n variants, fail=$fail"
exit $fail
