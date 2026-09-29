#!/usr/bin/env bash
# Dump lavapipe's NIR and LLVM IR for one render_check pair's two shaders.
#   nirdump.sh ID [TEXKINDS]   -> build/nir_ID.{spec,uber}.txt
set -u
H="$(cd "$(dirname "$0")" && pwd)"
ID=$(printf %04d "$((10#$1))")
K="${2:-2222}"
R="$H/build/render"
for kind in spec uber; do
    env NIR_DEBUG=print_fs GALLIVM_DEBUG=ir \
        VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json \
        "$H/build/render_bin" "$R/$ID.vert.spv" "$R/$ID.$kind.spv" \
        "$R/$ID.$kind.ubo" "$K" "$H/build/nir_$ID.$kind.raw" \
        > "$H/build/nir_$ID.$kind.txt" 2>&1
    echo "$kind: $(wc -l < "$H/build/nir_$ID.$kind.txt") lines"
done
