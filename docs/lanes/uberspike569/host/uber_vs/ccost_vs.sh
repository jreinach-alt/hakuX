#!/usr/bin/env bash
# Addendum design 1, C on the host: Turnip's compile time for a FULL uber
# pipeline (uber vertex prototype + GS + the family fragment ubershader) against
# specialised pipelines, through turnipcost569's harness and host Turnip, every
# cache off. Needs build.sh's SPIR-V and ccost.sh's build/ccost/{spec,uber}_basic.spv.
#
#   ccost_vs.sh [reps]   -> ../build/uber_vs/ccost_vs.tsv
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
TC=/home/justin/hakux-work/wt/turnipcost569/.scratch
OUTD="$TC/out-base-noopt"
B="$H/../build"
U="$B/uber_vs"
C="$B/ccost"
REPS="${1:-3}"
[ -x "$C/vkharness" ] || gcc -O2 -g -Wall -I"$TC/mesa/include" -o "$C/vkharness" \
    "$H/../../../turnipcost569/vkharness.c" -ldl
GS="$OUTD/gs_tri_smooth.spv"
cat > "$U/manifest.txt" <<EOF
spec:prog_skin4+gs+fs_spec $OUTD/vs_prog_skin4_a0_pfx.spv $C/spec_basic.spv $GS
spec:ff_unlit+gs+fs_spec $OUTD/vs_ff_unlit_pfx.spv $C/spec_basic.spv $GS
spec:ff_lit2+gs+fs_spec $OUTD/vs_ff_lit2_pfx.spv $C/spec_basic.spv $GS
uber:vp+gs+fs_spec $U/vs_uber_vp.spv $C/spec_basic.spv $GS
uber:ff+gs+fs_spec $U/vs_uber_ff.spv $C/spec_basic.spv $GS
uber:both+gs+fs_spec $U/vs_uber_both.spv $C/spec_basic.spv $GS
uber:both+gs+fs_uber $U/vs_uber_both.spv $C/uber_basic.spv $GS
uber:both+fs_uber $U/vs_uber_both.spv $C/uber_basic.spv
spec:prog_pass+fs_spec $OUTD/vs_prog_pass.spv $C/spec_basic.spv
EOF
env LD_PRELOAD="$TC/mesa-build/src/freedreno/drm-shim/libfreedreno_noop_drm_shim.so" \
    FD_GPU_ID=740 VK_ENABLE_PIPELINE_CACHE=false MESA_SHADER_CACHE_DISABLE=true \
    "$C/vkharness" "$TC/mesa-build/src/freedreno/vulkan/libvulkan_freedreno.so" \
    "$U/manifest.txt" "$REPS" > "$U/ccost_vs.tsv" 2> "$U/ccost_vs.err"
python3 - "$U/ccost_vs.tsv" <<'PY'
import statistics, sys, collections
rows = collections.defaultdict(list)
for line in open(sys.argv[1]):
    f = line.split()
    if len(f) < 8 or f[0] == "name":
        continue
    rows[f[0]].append([float(x) for x in f[2:8]])
print("%-26s %4s %9s %9s %8s %8s %8s" % ("pipeline", "n", "cpu_ms", "fb_pipe", "vs", "fs", "gs"))
for k, v in rows.items():
    m = lambda i: statistics.median(r[i] for r in v)
    print("%-26s %4d %9.1f %9.1f %8.1f %8.1f %8.1f" % (k, len(v), m(1), m(2), m(3), m(4), m(5)))
PY
