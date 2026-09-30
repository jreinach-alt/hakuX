#!/usr/bin/env bash
# Host checks for the #569 P6 ubershader: SPLICE (uberhost) and a glslang
# compile of every generated pair. Run from anywhere; writes under build/.
#
#   run_checks.sh [per-baseline] [glslangValidator]
set -u
H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
N="${1:-200}"
GLSLANG="${2:-/home/justin/hakux-work/turnipfork-glslang/install/bin/glslangValidator}"

make -C "$H" > "$H/build.log" 2>&1 || { tail -20 "$H/build.log"; exit 1; }
rm -rf "$H/build/shaders"
"$H/build/uberhost" --out "$H/build/shaders" --per-baseline "$N" > "$H/build/run.log" 2>&1
rc=$?
tail -1 "$H/build/run.log"
[ "$rc" = 0 ] || echo "uberhost exit $rc"

# glslang: every uber and every spec shader must compile for Vulkan.
bad=0; n=0
for f in "$H"/build/shaders/uber_*.frag "$H"/build/shaders/spec_*.frag; do
    n=$((n + 1))
    if ! "$GLSLANG" -V --target-env vulkan1.1 -S frag -o /dev/null "$f" > "$H/build/glslang.one" 2>&1; then
        bad=$((bad + 1))
        [ "$bad" -le 5 ] && { echo "glslang FAIL: $f"; grep -m5 ERROR "$H/build/glslang.one"; }
    fi
done
echo "glslang: $n compiled, $bad failed"
