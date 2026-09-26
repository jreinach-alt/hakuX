#!/bin/sh
# Compile a GS with and without the gl_PointSize write; count GeometryPointSize.
cd "$(dirname "$0")"
G=${GLSLANG:-/home/justin/hakux-work/turnipfork-glslang/build/StandAlone/glslangValidator}
grep -v gl_PointSize a.geom > /tmp/vkps34-b.geom
for f in a.geom /tmp/vkps34-b.geom; do
    "$G" -V --target-env vulkan1.0 -H "$f" -o /dev/null > /tmp/vkps34.txt 2>&1
    rc=$?
    echo "$f exit=$rc GeometryPointSize=$(grep -c 'Capability GeometryPointSize' /tmp/vkps34.txt) PointSize-lines=$(grep -c PointSize /tmp/vkps34.txt)"
done
