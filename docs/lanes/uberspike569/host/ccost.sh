#!/usr/bin/env bash
# The C leg on the host: Turnip's compile time for pipelines built on the
# specialised fragment shader vs the family ubershader, same VS/GS, through
# lane.turnipcost569's harness (PR #573: vkharness.c, the Adreno 740 drm-shim,
# every cache off). Its Mesa build and VS/GS SPIR-V are used read-only; the
# harness binary is built here, under build/.
#
#   ccost.sh [reps]     -> build/ccost/ccost.tsv, then a summary
#
# Needs uberhost's build/shaders (run_checks.sh). Pairs are adjacent in the
# manifest and reps run round-robin, so A and B of a pair share the host's
# load (turnipcost569 NOTES section 2: under ~1.15x is noise here).
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
TC=/home/justin/hakux-work/wt/turnipcost569
S="$TC/.scratch"
OUTD="$S/out-base-noopt"
GLSLANG="$S/glslang-noopt/install/bin/glslangValidator"
REPS="${1:-5}"
C="$H/build/ccost"
mkdir -p "$C"

gcc -O2 -g -Wall -I"$S/mesa/include" -o "$C/vkharness" \
    "$TC/docs/lanes/turnipcost569/vkharness.c" -ldl

# Baseline k=0 of each psh_differ baseline, by uberhost's manifest id.
declare -A FS=([basic]=0060 [stages8]=0121 [textures]=0182 [border]=0365 [bumpenv]=0426)
: > "$C/manifest.txt"
for name in basic stages8 textures border bumpenv; do
    id=${FS[$name]}
    for kind in spec uber; do
        "$GLSLANG" -V --target-env vulkan1.1 -S frag -o "$C/${kind}_$name.spv" \
            "$H/build/shaders/${kind}_$id.frag" > /dev/null
    done
    for vs in "prog_pass:vs_prog_pass.spv:" \
              "ff_unlit:vs_ff_unlit_pfx.spv:gs_tri_smooth.spv" \
              "ff_lit2:vs_ff_lit2_pfx.spv:gs_tri_smooth.spv"; do
        IFS=: read -r vname vspv gspv <<< "$vs"
        for kind in spec uber; do
            echo "$vname+$name+$kind $OUTD/$vspv $C/${kind}_$name.spv${gspv:+ $OUTD/$gspv}" \
                >> "$C/manifest.txt"
        done
    done
done

env LD_PRELOAD="$S/mesa-build/src/freedreno/drm-shim/libfreedreno_noop_drm_shim.so" \
    FD_GPU_ID=740 VK_ENABLE_PIPELINE_CACHE=false MESA_SHADER_CACHE_DISABLE=true \
    "$C/vkharness" "$S/mesa-build/src/freedreno/vulkan/libvulkan_freedreno.so" \
    "$C/manifest.txt" "$REPS" > "$C/ccost.tsv" 2> "$C/ccost.err"

python3 - "$C/ccost.tsv" <<'PY'
import statistics, sys, collections
rows = collections.defaultdict(list)
for line in open(sys.argv[1]):
    f = line.split()
    if len(f) < 8 or f[0] == "name":
        continue
    rows[f[0]].append((float(f[3]), float(f[6])))
def med(k, i):
    return statistics.median(r[i] for r in rows[k])
print("%-28s %9s %9s %7s | %8s %8s %7s" % ("pipeline", "cpu spec", "cpu uber", "x",
      "fs spec", "fs uber", "x"))
for k in sorted({k.rsplit("+", 1)[0] for k in rows}):
    a, b = k + "+spec", k + "+uber"
    if a in rows and b in rows:
        cs, cu, fs, fu = med(a, 0), med(b, 0), med(a, 1), med(b, 1)
        print("%-28s %9.1f %9.1f %7.2f | %8.1f %8.1f %7.2f" %
              (k, cs, cu, cu / cs, fs, fu, fu / fs if fs else 0))
PY
