#!/usr/bin/env bash
# Generate the uber vertex prototypes (gen_uber_vs.py) and compile them to SPIR-V
# with turnipcost569's glslang (read-only). Output: ../build/uber_vs/.
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
TC=/home/justin/hakux-work/wt/turnipcost569/.scratch
GLSLANG="$TC/glslang-noopt/install/bin/glslangValidator"
O="$H/../build/uber_vs"
python3 "$H/gen_uber_vs.py" "$TC/out-base-noopt" "$O"
for v in vp ff both; do
    "$GLSLANG" -V --target-env vulkan1.1 -S vert -o "$O/vs_uber_$v.spv" \
        "$O/vs_uber_$v.glsl" > "$O/glslang_$v.log" 2>&1 \
        || { echo "glslang failed: $v"; head -20 "$O/glslang_$v.log"; exit 1; }
    echo "$v: $(stat -c %s "$O/vs_uber_$v.spv") B SPIR-V"
done
