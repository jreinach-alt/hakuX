#!/bin/bash
# lane.gpuclock (#433): The Simpsons: Hit & Run on the Nova, ONE held pathfind
# session, the GPU floor switched between performance_mode 0 (401 MHz), 1
# (550 MHz) and 2 (615 MHz) in BLOCK_S blocks during free roam, order
# 0 2 1 / 1 0 2 / 2 1 0 (each mode once in each third of the session). Every
# switch is read back and written to logcat (`hakuX-route: gpuclock pm=<n>
# fan=<n> floor=<mhz>`), so gpuclock.py --blocks splits the [gpuclk433]
# windows by condition. Host-run (lane.local): a lane cannot touch the device.
#
# A copy of docs/lanes/vcpusleep/capture_simpsons_offcpu.sh with these
# changes, nothing else:
#   - No simpleperf. After the gate opens, the switch loop runs; that is the
#     whole measurement. The APK is this lane's instrument build (APK_REF,
#     default 521ea8a93e: master d32c35d3ce + the [gpuclk433] line).
#   - performance_mode is written with `settings put system`, the OEM menu's
#     own setting (devices.sh), and read back with kgsl min_clock_mhz. fan_mode
#     is put back to 4 (SMART, the default) after every switch, because the
#     SystemUI tile rewrites it when performance_mode changes; read back too.
#     A read-back that differs is logged `gpuclock MISMATCH` and the block is
#     void in the reader.
#   - On every exit: performance_mode 0 and fan_mode 4 (the device default and
#     REST), read back, before the hold is released.
#   - The hold tag is lane.gpuclock.
#
#   PATHFIND_TREE=/path/to/pathfind/checkout capture_simpsons_gpuclock.sh simpclk1
#
# Read: docs/lanes/gpuclock/gpuclock.py --blocks $OUT/pf (the pathfind result
# dir: logcat.txt, run.log-less; the reader takes the hold's mark gameplay
# from logcat). decompose.py (docs/lanes/near30) on $OUT/pf for the vCPU split.
set -u
SHORT=$1
BLOCK_S=${BLOCK_S:-60}
ORDER=${ORDER:-"0 2 1 1 0 2 2 1 0"}
GATE_S=${GATE_S:-90}
DELAY=${DELAY:-20}
HOLD_S=${HOLD_S:-720}    # pathfind's hold: DELAY + 9 x 60 s blocks + margin
TID=56550015
DEV=nova S=ee317437 MIN_BATT=${MIN_BATT:-20}
PKG=com.jreinach.hakux.debug
D=/home/justin/hakux-work/dispatch
OUT=/home/justin/hakux-work/perf/2026-10-05-gpuclock/$SHORT
APK_REF=${APK_REF:-521ea8a93e}
APK=$D/builds/$APK_REF.apk
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../testing" && pwd)"
HOLDSH="$HERE/jobs/hold.sh"
TAG=lane.gpuclock
LEASE=/tmp/hakux-device-lease.$DEV
PATHFIND_TREE=${PATHFIND_TREE:-/home/justin/hakux-work/wt/pathfind}
PF="$PATHFIND_TREE/docs/testing/titles/pathfind.py"
mkdir -p "$OUT"
[ -f "$PF" ] || { echo "CAP no $PF (set PATHFIND_TREE to a lane/pathfind checkout)"; exit 2; }
[ -f "$PATHFIND_TREE/docs/testing/titles/pathknow/paths/$TID.json" ] \
    || { echo "CAP $PATHFIND_TREE has no recorded Simpsons path (pathknow/paths/$TID.json)"; exit 2; }
a() { timeout "${T:-120}" adb -s $S "$@"; }
say() { echo "CAP $(date -u +%H:%M:%S) $*"; }
running_dev() { grep -lx $DEV "$D"/running/*.owner 2>/dev/null; }
PFLOG="$OUT/pf/logcat.txt"

[ -f "$APK" ] || { say "no apk $APK"; exit 1; }
bash "$HOLDSH" wait $DEV $TAG "${HOLD_WAIT_S:-3600}" \
    "lane.gpuclock #433: held $DEV session, pathfind hold of Simpsons, GPU floor switched 401/550/615 MHz in ${BLOCK_S} s blocks (apk $APK_REF), ~17 min of device time; capture_simpsons_gpuclock.sh releases on every exit" \
    || { say "could not take hold/$DEV: $(bash "$HOLDSH" who $DEV)"; exit 3; }
say "hold taken"

# perf <mode>: performance_mode <mode>, fan_mode 4, read back; echoes "pm fan floor"
perf() {
    a shell "settings put system performance_mode $1" >/dev/null 2>&1
    sleep 1
    a shell "settings put system fan_mode 4" >/dev/null 2>&1
    sleep 1
    a shell 'echo "$(settings get system performance_mode) $(settings get system fan_mode) $(cat /sys/class/kgsl/kgsl-3d0/min_clock_mhz)"' 2>/dev/null | tr -d '\r' | tail -1
}

LEASE_PID="" PF_PID="" USED=0
cleanup() {
    rc=$?
    if [ "$USED" = 1 ]; then
        got=$(perf 0)
        say "restored performance_mode/fan_mode/floor: $got"
        a shell log -t hakuX-route "'gpuclock end $got'" >/dev/null 2>&1
        if [ -n "$PF_PID" ] && kill -0 "$PF_PID" 2>/dev/null; then
            kill -INT "$PF_PID" 2>/dev/null
            for _ in $(seq 60); do kill -0 "$PF_PID" 2>/dev/null || break; sleep 1; done
            kill "$PF_PID" 2>/dev/null
        fi
        a shell am force-stop $PKG >/dev/null 2>&1
        a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin" >/dev/null 2>&1
        rm -f "$D/.shader_cache_apk.$DEV"
        a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
    fi
    [ -n "$LEASE_PID" ] && kill "$LEASE_PID" 2>/dev/null && rm -f "$LEASE"
    bash "$HOLDSH" release $DEV $TAG && say "hold released" || say "hold not ours; left alone"
    say "exit rc=$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

bash "$HOLDSH" wait-idle $DEV "${IDLE_WAIT_S:-1800}" || { say "$DEV still busy (wait-idle)"; exit 3; }
running_dev >/dev/null && { say "$DEV still busy after wait-idle"; exit 3; }
USED=1
( while :; do touch "$LEASE"; sleep 20; done ) & LEASE_PID=$!
say "device free; session starts"

lvl=$(a shell dumpsys battery | tr -d '\r' | awk '/level:/{print $2; exit}')
st=$(a shell dumpsys battery | tr -d '\r' | awk '/status:/{print $2; exit}')
say "battery $lvl status $st (2 charging, 3 discharging)"
[ -n "$lvl" ] && [ "$lvl" -ge "$MIN_BATT" ] || { say "battery below $MIN_BATT or unreadable"; exit 4; }

T=300 a install -r "$(wslpath -w "$APK")" 2>&1 | tail -1 | grep -q Success || { say "install failed"; exit 5; }
a shell am force-stop $PKG
a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin"
a exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/prefs.xml"
grep -q 'name="validation_layers" value="true"' "$OUT/prefs.xml" && { say "validation_layers on; refusing"; exit 6; }
if grep -Eq '<string name="env_vars">[^<]+' "$OUT/prefs.xml"; then
    say "clearing a previous request's env_vars: $(grep 'name="env_vars"' "$OUT/prefs.xml" | sed 's/^ *//')"
    python3 - "$OUT/prefs.xml" "$OUT/prefs.noenv.xml" <<'PYENV' || { say "could not edit prefs; refusing"; exit 6; }
import re, sys
s = open(sys.argv[1]).read()
if "</map>" not in s:
    sys.exit("prefs file has no </map>")
open(sys.argv[2], "w").write(re.sub(r'\n?[ \t]*<string name="env_vars">.*?</string>', "", s, flags=re.S))
PYENV
    a shell "run-as $PKG sh -c 'cat > shared_prefs/x1box_prefs.xml'" < "$OUT/prefs.noenv.xml"
    a exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/prefs.xml"
    grep -Eq '<string name="env_vars">[^<]+' "$OUT/prefs.xml" && { say "env_vars still set after the clear; refusing"; exit 6; }
    grep -q '</map>' "$OUT/prefs.xml" || { say "prefs read back truncated; refusing"; exit 6; }
    rm -f "$D/.env_pref.$DEV"
    say "env_vars cleared (read back)"
fi
# The session starts at the device default; the first block sets its own mode.
say "start modes: $(perf 0)"

setsid python3 "$PF" $TID --device $DEV --hold-s "$HOLD_S" --budget-min "${BUDGET_MIN:-15}" \
    --out "$OUT/pf" --no-record > "$OUT/pathfind.log" 2>&1 &
PF_PID=$!
say "pathfind pid $PF_PID"

t=0
until grep -q 'hakuX-route.*mark gameplay' "$PFLOG" 2>/dev/null; do
    kill -0 $PF_PID 2>/dev/null || { say "ABORT: pathfind ended before a gameplay claim: $(tail -2 "$OUT/pathfind.log" | tr '\n' ' ')"; exit 7; }
    [ $t -ge "${CLAIM_S:-1200}" ] && { say "ABORT: no gameplay claim in ${CLAIM_S:-1200} s"; exit 7; }
    sleep 2; t=$((t + 2))
done
say "mark gameplay after ${t} s"
sleep "$DELAY"

last_state() { grep -o 'hakuX-route[^:]*: state=[a-z_]*' "$PFLOG" | tail -1 | sed 's/.*state=//'; }
t=0
while :; do
    st=$(last_state)
    case $st in play|still) break ;; esac
    kill -0 $PF_PID 2>/dev/null || { say "ABORT: pathfind ended (state ${st:-?}) before the blocks"; exit 7; }
    [ $t -ge "$GATE_S" ] && { say "ABORT: not in play ${GATE_S} s after mark+${DELAY}: state ${st:-?}"; exit 7; }
    sleep 1; t=$((t + 1))
done
say "gate open: state=$st"

for pm in $ORDER; do
    kill -0 $PF_PID 2>/dev/null || { say "pathfind ended during the blocks"; break; }
    got=$(perf $pm)
    set -- $got
    case $pm in 0) want_floor=401 ;; 1) want_floor=550 ;; 2) want_floor=615 ;; *) want_floor=? ;; esac
    if [ "${1:-}" = "$pm" ] && [ "${2:-}" = 4 ] && [ "${3:-}" = "$want_floor" ]; then
        a shell log -t hakuX-route "'gpuclock pm=$1 fan=$2 floor=$3'" >/dev/null
        say "block pm=$pm read back [$got]"
    else
        a shell log -t hakuX-route "'gpuclock MISMATCH want=$pm got=$got'" >/dev/null
        say "block pm=$pm MISMATCH read back [$got]"
    fi
    sleep "$BLOCK_S"
done
a shell log -t hakuX-route "'gpuclock blocks done'" >/dev/null
say "blocks done; state=$(last_state)"
for _ in $(seq "${PF_WAIT_S:-600}"); do kill -0 $PF_PID 2>/dev/null || break; sleep 1; done
say "done"
