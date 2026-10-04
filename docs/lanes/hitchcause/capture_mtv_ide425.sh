#!/bin/bash
# lane.hitchcause (#433) capture: one held Nova session, one pathfind hold of
# MTV Celebrity Deathmatch (5454000B) for HOLD_S seconds of play with
# --state any, on the APK built from REF (the [ide425] window line).
#
# A copy of docs/lanes/vcpusleep/capture_simpsons_offcpu.sh with these changes:
#   - the driver is pathfind.py --hold-s with no record (the MTV route is
#     pathknow/paths/5454000B.json on lane/pathfind; the caller copies it into
#     this tree, untracked, before running and removes it after);
#   - the APK is installed here from builds/REF-perflog.apk, because the device
#     may carry another lane's build (accuracy804's request was running);
#   - no off-CPU simpleperf: the record is the perflog and logcat that
#     pathfind keeps under OUT/pf.
#
#   capture_mtv_ide425.sh
#
# Hold: taken and released only with jobs/hold.sh (tag lane.hitchcause). Every
# exit path stops pathfind (SIGINT first, so its own finally releases the
# titles disk), force-stops the app, clears this APK's shader caches, sleeps the
# screen and releases the hold.
set -u
HOLD_S=${HOLD_S:-700}
BUDGET_MIN=${BUDGET_MIN:-25}
TID=5454000B
REF=${REF:-b559c094eb}
DEV=nova S=ee317437 MIN_BATT=${MIN_BATT:-20}
PKG=com.jreinach.hakux.debug
D=/home/justin/hakux-work/dispatch
OUT=/home/justin/hakux-work/perf/2026-10-04-hitchcause/mtv-ide425
APK=$D/builds/$REF-perflog.apk
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../testing" && pwd)"
HOLDSH="$HERE/jobs/hold.sh"
TAG=lane.hitchcause
LEASE=/tmp/hakux-device-lease.$DEV
PF="$HERE/titles/pathfind.py"
ROUTE="$HERE/titles/pathknow/paths/$TID.json"
mkdir -p "$OUT"
a() { timeout "${T:-120}" adb -s $S "$@"; }
say() { echo "CAP $(date -u +%H:%M:%S) $*"; }

# Before the hold: a run that cannot start must not take the device.
[ -f "$APK" ] || { say "no apk $APK"; exit 1; }
[ -f "$PF" ] || { say "no $PF"; exit 2; }
[ -f "$ROUTE" ] || { say "no route $ROUTE (copy it from lane/pathfind)"; exit 2; }
a get-state >/dev/null 2>&1 || { say "adb sees no $S"; exit 2; }

bash "$HOLDSH" wait $DEV $TAG "${HOLD_WAIT_S:-1800}" \
    "lane.hitchcause #433: held $DEV session, pathfind hold of MTV (5454000B) for ${HOLD_S} s of play, --state any (apk $REF, [ide425] window line); capture_mtv_ide425.sh releases on every exit" \
    || { say "could not take hold/$DEV: $(bash "$HOLDSH" who $DEV)"; exit 3; }
say "hold taken"

LEASE_PID="" PF_PID="" USED=0
cleanup() {
    rc=$?
    if [ "$USED" = 1 ]; then
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
USED=1
( while :; do touch "$LEASE"; sleep 20; done ) & LEASE_PID=$!
say "device free; session starts"

lvl=$(a shell dumpsys battery | tr -d '\r' | awk '/level:/{print $2; exit}')
say "battery $lvl"
[ -n "$lvl" ] && [ "$lvl" -ge "$MIN_BATT" ] || { say "battery below $MIN_BATT or unreadable"; exit 4; }

T=300 a install -r "$(wslpath -w "$APK")" 2>&1 | tail -1 | grep -q Success || { say "install failed"; exit 5; }
say "installed $REF"
a shell am force-stop $PKG
a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin"
a exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/prefs.xml"
grep -q 'name="validation_layers" value="true"' "$OUT/prefs.xml" && { say "validation_layers on; refusing"; exit 6; }
# A previous request's --env left in the pref would run this under it (a
# frame dump slows the run): drop the key, write it back, read it back.
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

setsid python3 "$PF" $TID --device $DEV --hold-s "$HOLD_S" --state any \
    --budget-min "$BUDGET_MIN" --out "$OUT/pf" --no-record > "$OUT/pathfind.log" 2>&1 &
PF_PID=$!
say "pathfind pid $PF_PID"
echo "$PF_PID" > "$OUT/pathfind.pid"

# Long wait: pathfind boots, plays to gameplay, holds HOLD_S seconds, exits.
t=0
while kill -0 $PF_PID 2>/dev/null; do
    [ $t -ge $((BUDGET_MIN * 60 + 600)) ] && { say "ABORT: pathfind still running at ${t} s"; exit 7; }
    sleep 10; t=$((t + 10))
done
wait $PF_PID; pf_rc=$?
PF_PID=""
say "pathfind exited rc=$pf_rc"
