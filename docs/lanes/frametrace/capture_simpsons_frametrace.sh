#!/bin/bash
# lane.frametrace (#433): The Simpsons: Hit & Run on the Nova, ONE held
# pathfind session with HAKUX_FRAMETRACE=1, free roam. Host-run (lane.local):
# a lane cannot touch the device.
#
# A copy of docs/lanes/gpuclock/capture_simpsons_gpuclock.sh (origin/
# lane/gpuclock) with these changes:
#   - No performance_mode switching: the device default throughout.
#   - env_vars is SET to HAKUX_FRAMETRACE=1 (read back) instead of cleared,
#     and CLEARED again on every exit (read back), so the device is left in
#     the shipped state.
#   - A second logcat follows the session with hakuX-lane on the list
#     (pathfind's LOGCAT_SPEC does not carry it, and the [hakuX-ft1] summary
#     and [hakuX-ft] hitch blocks are logged there). Out: $OUT/ft-logcat.txt.
#   - At the end the frame CSV is pulled from the app's external files dir
#     (frametrace_*.csv) into $OUT/.
#   - The hold tag is lane.frametrace. HOLD_S defaults to 300 (180 s of
#     confirmed play is the brief's first read, plus DELAY and margin).
#
#   PATHFIND_TREE=/path/to/pathfind/checkout capture_simpsons_frametrace.sh simpft1
#
# Read: python3 docs/lanes/frametrace/ftread.py --pf $OUT
set -u
SHORT=$1
GATE_S=${GATE_S:-90}
DELAY=${DELAY:-20}
HOLD_S=${HOLD_S:-300}
TID=56550015
DEV=nova S=ee317437 MIN_BATT=${MIN_BATT:-20}
PKG=com.jreinach.hakux.debug
D=/home/justin/hakux-work/dispatch
OUT=/home/justin/hakux-work/perf/2026-10-05-frametrace/$SHORT
APK_REF=${APK_REF:-0bb89cd1f5}
APK=$D/builds/$APK_REF.apk
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../testing" && pwd)"
HOLDSH="$HERE/jobs/hold.sh"
TAG=lane.frametrace
LEASE=/tmp/hakux-device-lease.$DEV
PATHFIND_TREE=${PATHFIND_TREE:-/home/justin/hakux-work/wt/pathfind}
PF="$PATHFIND_TREE/docs/testing/titles/pathfind.py"
FTSPEC="hakuX-lane:I hakuX-route:I hakuX-pace:I hakuX-perf:I hakuX:W libc:F DEBUG:F *:S"
mkdir -p "$OUT"
[ -f "$PF" ] || { echo "CAP no $PF (set PATHFIND_TREE to a lane/pathfind checkout)"; exit 2; }
[ -f "$PATHFIND_TREE/docs/testing/titles/pathknow/paths/$TID.json" ] \
    || { echo "CAP $PATHFIND_TREE has no recorded Simpsons path (pathknow/paths/$TID.json)"; exit 2; }
a() { timeout "${T:-120}" adb -s $S "$@"; }
say() { echo "CAP $(date -u +%H:%M:%S) $*"; }
running_dev() { grep -lx $DEV "$D"/running/*.owner 2>/dev/null; }
PFLOG="$OUT/pf/logcat.txt"

[ -f "$APK" ] || { say "no apk $APK (queue any request at $APK_REF to build it)"; exit 1; }
bash "$HOLDSH" wait $DEV $TAG "${HOLD_WAIT_S:-3600}" \
    "lane.frametrace #433: held $DEV session, pathfind hold of Simpsons free roam with HAKUX_FRAMETRACE=1 (apk $APK_REF), ~10 min of device time; capture_simpsons_frametrace.sh releases on every exit" \
    || { say "could not take hold/$DEV: $(bash "$HOLDSH" who $DEV)"; exit 3; }
say "hold taken"

# setenv <value or empty>: write env_vars (dispatcher.sh apply_env_pref's
# shape), read back; echoes what the read-back holds.
setenv() {
    a shell am force-stop $PKG >/dev/null 2>&1
    a exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/prefs.xml"
    python3 - "$OUT/prefs.xml" "$OUT/prefs.new.xml" "$1" <<'PYENV' || return 1
import re, sys
s = open(sys.argv[1]).read()
if "</map>" not in s:
    sys.exit("prefs file has no </map>")
s = re.sub(r'\n?[ \t]*<string name="env_vars">.*?</string>', "", s, flags=re.S)
if sys.argv[3]:
    s = s.replace("</map>", '    <string name="env_vars">%s</string>\n</map>' % sys.argv[3])
open(sys.argv[2], "w").write(s)
PYENV
    a shell "run-as $PKG sh -c 'cat > shared_prefs/x1box_prefs.xml'" < "$OUT/prefs.new.xml"
    a exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/prefs.back.xml"
    grep -q '</map>' "$OUT/prefs.back.xml" || { echo "TRUNCATED"; return 1; }
    python3 -c 'import re,sys; m=re.search(r"<string name=\"env_vars\">(.*?)</string>", open(sys.argv[1]).read(), re.S); print(m.group(1) if m else "")' "$OUT/prefs.back.xml"
}

LEASE_PID="" PF_PID="" LC_PID="" USED=0
cleanup() {
    rc=$?
    if [ "$USED" = 1 ]; then
        if [ -n "$PF_PID" ] && kill -0 "$PF_PID" 2>/dev/null; then
            kill -INT "$PF_PID" 2>/dev/null
            for _ in $(seq 60); do kill -0 "$PF_PID" 2>/dev/null || break; sleep 1; done
            kill "$PF_PID" 2>/dev/null
        fi
        a shell am force-stop $PKG >/dev/null 2>&1
        [ -n "$LC_PID" ] && kill "$LC_PID" 2>/dev/null
        for f in $(a shell "ls /sdcard/Android/data/$PKG/files/" 2>/dev/null | tr -d '\r' | grep '^frametrace_.*\.csv$'); do
            a pull "/sdcard/Android/data/$PKG/files/$f" "$OUT/$f" >/dev/null 2>&1 \
                && say "pulled $f" && a shell rm -f "/sdcard/Android/data/$PKG/files/$f" >/dev/null 2>&1
        done
        got=$(setenv "")
        say "env_vars cleared, read back [$got]"
        rm -f "$D/.env_pref.$DEV"
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
a exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/prefs.orig.xml"
grep -q 'name="validation_layers" value="true"' "$OUT/prefs.orig.xml" && { say "validation_layers on; refusing"; exit 6; }
got=$(setenv "HAKUX_FRAMETRACE=1") || { say "could not write env_vars; refusing"; exit 6; }
[ "$got" = "HAKUX_FRAMETRACE=1" ] || { say "env_vars read back [$got], not HAKUX_FRAMETRACE=1; refusing"; exit 6; }
say "env_vars set, read back [$got]"
a shell "rm -f /sdcard/Android/data/$PKG/files/frametrace_*.csv" >/dev/null 2>&1

adb -s $S logcat -v time -T 1 $FTSPEC > "$OUT/ft-logcat.txt" 2>/dev/null & LC_PID=$!

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
    kill -0 $PF_PID 2>/dev/null || { say "ABORT: pathfind ended (state ${st:-?}) before play"; exit 7; }
    [ $t -ge "$GATE_S" ] && { say "ABORT: not in play ${GATE_S} s after mark+${DELAY}: state ${st:-?}"; exit 7; }
    sleep 1; t=$((t + 1))
done
say "gate open: state=$st"
a shell log -t hakuX-route "'frametrace window start'" >/dev/null
for _ in $(seq "${PF_WAIT_S:-900}"); do kill -0 $PF_PID 2>/dev/null || break; sleep 1; done
a shell log -t hakuX-route "'frametrace window end'" >/dev/null 2>&1
say "done; state=$(last_state)"
