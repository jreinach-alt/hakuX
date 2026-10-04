#!/usr/bin/env bash
# Addendum design 2 (P5, GPL) on host Turnip: library creation and link times
# against a monolithic create, for specialised and uber pipelines.
#
#   gpl.sh [reps]   -> ../build/gpl/gpl.tsv (+ gpl.err: the device's GPL properties)
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
TC=/home/justin/hakux-work/wt/turnipcost569/.scratch
OUTD="$TC/out-base-noopt"
B="$H/../build"
G="$B/gpl"
U="$B/uber_vs"
C="$B/ccost"
REPS="${1:-3}"
mkdir -p "$G"
gcc -O2 -g -Wall -I"$TC/mesa/include" -o "$G/gplharness" "$H/gplharness.c" -ldl
GS="$OUTD/gs_tri_smooth.spv"
cat > "$G/manifest.txt" <<EOF
spec:prog_pass+fs_spec $OUTD/vs_prog_pass.spv $C/spec_basic.spv
spec:prog_pass+fs_uber $OUTD/vs_prog_pass.spv $C/uber_basic.spv
spec:ff_unlit+gs+fs_spec $OUTD/vs_ff_unlit_pfx.spv $C/spec_basic.spv $GS
spec:ff_unlit+gs+fs_uber $OUTD/vs_ff_unlit_pfx.spv $C/uber_basic.spv $GS
spec:ff_lit2+gs+fs_spec $OUTD/vs_ff_lit2_pfx.spv $C/spec_basic.spv $GS
spec:ff_lit2+gs+fs_uber $OUTD/vs_ff_lit2_pfx.spv $C/uber_basic.spv $GS
spec:prog_skin4+gs+fs_spec $OUTD/vs_prog_skin4_a0_pfx.spv $C/spec_basic.spv $GS
uber:both+gs+fs_uber $U/vs_uber_both.spv $C/uber_basic.spv $GS
EOF
env LD_PRELOAD="$TC/mesa-build/src/freedreno/drm-shim/libfreedreno_noop_drm_shim.so" \
    FD_GPU_ID=740 VK_ENABLE_PIPELINE_CACHE=false MESA_SHADER_CACHE_DISABLE=true \
    "$G/gplharness" "$TC/mesa-build/src/freedreno/vulkan/libvulkan_freedreno.so" \
    "$G/manifest.txt" "$REPS" > "$G/gpl.tsv" 2> "$G/gpl.err"
head -2 "$G/gpl.err"
python3 - "$G/gpl.tsv" <<'PY'
import statistics, sys, collections
rows = collections.defaultdict(list)
hdr = None
for line in open(sys.argv[1]):
    f = line.split()
    if f[0] == "name":
        hdr = f[2:]
        continue
    rows[f[0]].append([float(x) for x in f[2:]])
print("%-26s %3s " % ("pipeline", "n") + " ".join("%8s" % h for h in hdr))
for k, v in rows.items():
    print("%-26s %3d " % (k, len(v)) +
          " ".join("%8.1f" % statistics.median(r[i] for r in v) for i in range(len(hdr))))
PY
