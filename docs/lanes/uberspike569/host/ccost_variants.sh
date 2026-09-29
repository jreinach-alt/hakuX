#!/usr/bin/env bash
# C leg, interpreter designs compared: the specialised shader, the shipped
# ubershader (shape tree), v1 (one straight-line stage body, switch-based
# register access; variant_v1.py) and v3 (array register file, arithmetic
# mappings; variant_v3.py), each behind prog_pass with no GS so the fragment
# stage is most of the pipeline. Same harness and caveats as ccost.sh.
#
#   ccost_variants.sh [reps]   -> build/ccostv/ccostv.tsv, then a summary
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
S=/home/justin/hakux-work/wt/turnipcost569/.scratch
OUTD="$S/out-base-noopt"
GLSLANG="$S/glslang-noopt/install/bin/glslangValidator"
REPS="${1:-3}"
C="$H/build/ccostv"
mkdir -p "$C"
gcc -O2 -g -Wall -I"$S/mesa/include" -o "$C/vkharness" \
    "$H/../../turnipcost569/vkharness.c" -ldl

declare -A FS=([basic]=0060 [stages8]=0121 [textures]=0182 [border]=0365 [bumpenv]=0426)
: > "$C/manifest.txt"
for name in basic stages8 textures border bumpenv; do
    id=${FS[$name]}
    cp "$H/build/shaders/spec_$id.frag" "$C/spec_$name.frag"
    cp "$H/build/shaders/uber_$id.frag" "$C/uber_$name.frag"
    python3 "$H/variant_v1.py" "$C/uber_$name.frag" "$C/uberv1_$name.frag"
    python3 "$H/variant_v3.py" "$C/uber_$name.frag" "$C/uberv3_$name.frag"
    for kind in spec uber uberv1 uberv3; do
        "$GLSLANG" -V --target-env vulkan1.1 -S frag -o "$C/${kind}_$name.spv" \
            "$C/${kind}_$name.frag" > "$C/glslang_${kind}_$name.log" || {
                echo "glslang failed: ${kind}_$name"; tail -5 "$C/glslang_${kind}_$name.log"; exit 1; }
        echo "prog_pass+$name+$kind $OUTD/vs_prog_pass.spv $C/${kind}_$name.spv" \
            >> "$C/manifest.txt"
    done
done

env LD_PRELOAD="$S/mesa-build/src/freedreno/drm-shim/libfreedreno_noop_drm_shim.so" \
    FD_GPU_ID=740 VK_ENABLE_PIPELINE_CACHE=false MESA_SHADER_CACHE_DISABLE=true \
    "$C/vkharness" "$S/mesa-build/src/freedreno/vulkan/libvulkan_freedreno.so" \
    "$C/manifest.txt" "$REPS" > "$C/ccostv.tsv" 2> "$C/ccostv.err"

python3 - "$C" <<'PY'
import os, statistics, sys, collections
C = sys.argv[1]
rows = collections.defaultdict(list)
for line in open(os.path.join(C, "ccostv.tsv")):
    f = line.split()
    if len(f) < 8 or f[0] == "name":
        continue
    rows[f[0]].append(float(f[6]))
print("%-10s %10s %10s %10s %10s   %s" % ("state", "spec fs", "uber fs", "v1 fs", "v3 fs",
                                          "SPIR-V bytes spec/uber/v1/v3"))
for name in ("basic", "stages8", "textures", "border", "bumpenv"):
    med = {k: statistics.median(rows["prog_pass+%s+%s" % (name, k)])
           for k in ("spec", "uber", "uberv1", "uberv3")}
    sz = [os.path.getsize(os.path.join(C, "%s_%s.spv" % (k, name)))
          for k in ("spec", "uber", "uberv1", "uberv3")]
    print("%-10s %10.1f %10.1f %10.1f %10.1f   %s" % (
        name, med["spec"], med["uber"], med["uberv1"], med["uberv3"],
        "/".join(str(s) for s in sz)))
PY
