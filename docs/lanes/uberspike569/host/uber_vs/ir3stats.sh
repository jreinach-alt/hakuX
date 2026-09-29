#!/usr/bin/env bash
# ir3's own per-shader statistics (instruction count, registers, loops) for the
# manifest ccost_vs.sh wrote, one rep: IR3_SHADER_DEBUG=disasm prints a stats
# line per compiled variant on stderr. -> ../build/uber_vs/ir3stats.txt
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
TC=/home/justin/hakux-work/wt/turnipcost569/.scratch
U="$H/../build/uber_vs"
C="$H/../build/ccost"
env LD_PRELOAD="$TC/mesa-build/src/freedreno/drm-shim/libfreedreno_noop_drm_shim.so" \
    FD_GPU_ID=740 VK_ENABLE_PIPELINE_CACHE=false MESA_SHADER_CACHE_DISABLE=true \
    IR3_SHADER_DEBUG=disasm \
    "$C/vkharness" "$TC/mesa-build/src/freedreno/vulkan/libvulkan_freedreno.so" \
    "$U/manifest.txt" 1 > "$U/ir3stats.tsv" 2> "$U/ir3stats.err"
python3 - "$U/ir3stats.err" "$U/ir3stats.tsv" > "$U/ir3stats.txt" <<'PY'
import re, sys
err = open(sys.argv[1], errors="replace").read().splitlines()
names = [l.split()[0] for l in open(sys.argv[2]) if l.strip() and not l.startswith("name")]
stats = [l for l in err if re.search(r"\binstrs\b|\bfull\b.*\bhalf\b|max_sun|loops", l)]
print("pipelines in order:", names)
for l in stats:
    print(l.strip()[:300])
PY
wc -l "$U/ir3stats.txt"
