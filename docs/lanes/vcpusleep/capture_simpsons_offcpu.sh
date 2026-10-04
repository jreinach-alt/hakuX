#!/bin/bash
# lane.vcpusleep (#507) R1: one held Nova session, one 60 s OFF-CPU simpleperf
# capture of The Simpsons: Hit & Run in free roam. It names what the vCPU
# sleeps on (vcpu60: 9.4 ms of a 26.7 ms frame).
#
# A copy of docs/lanes/vcpuwait433/capture_offcpu.sh (the capture that named
# Tron's pfifo.lock read) with these changes, nothing else:
#   - The driver is pathfind.py --hold-s, not a route file. Simpsons has no
#     route. Its 10-04 data was a pathfind hold, and the recorded path
#     (pathknow/paths/56550015.json) is on lane/pathfind, so PATHFIND_TREE
#     points at a checkout that has it.
#   - The anchor is the hold's own `mark gameplay` (pathfind writes it when it
#     claims play). The record starts DELAY (60) s after it, for REC_S (60) s.
#   - The gate FAILS CLOSED on pathfind's play judgement. Pathfind logs
#     `state=<s> t=<n>` to hakuX-route at every change. The record starts only
#     while the newest state line is play or still (free roam, moving or
#     parked), waiting up to GATE_S for it. The record is VOID afterwards if a
#     state line other than play/still lands between `prof start` and
#     `prof end`. In every case the record window's kept frames are read by eye
#     before any verdict (NOTES).
#   - No slow-window gate. Simpsons runs at 37 fps median in free roam, and the
#     brief asks for the free-roam sleep as it is, not its slowest window.
#   - The APK is APK_REF (default 3ff55c9ac2: master's emulator code at
#     425ffe1ad1; no emulator file has changed since that build). It is a plain
#     build, not perflog.
#   - The hold tag is lane.vcpusleep.
#
#   PATHFIND_TREE=/path/to/pathfind/checkout capture_simpsons_offcpu.sh simp1
#
# Read: docs/lanes/vcpuwait433/waitsite.py $OUT/simp1.data (auto-picks the
# vCPU), then --detail "pfifo.lock in USER" or the top site's name for the
# holders (the per-tid pass). docs/lanes/vcpuwait433/decompose.py on
# $OUT/pf/logcat.txt gives v_blk for the same window.
#
# Hold: taken and released only with jobs/hold.sh (tag lane.vcpusleep). A
# request already running on the Nova finishes first. Every exit path stops
# pathfind (SIGINT first, so its own finally releases the titles disk),
# force-stops the app, clears this APK's shader caches, drops the
# dispatcher's shader-cache marker, sleeps the screen and releases the hold.
set -u
SHORT=$1
DELAY=${DELAY:-60}
REC_S=${REC_S:-60}
GATE_S=${GATE_S:-90}
HOLD_S=${HOLD_S:-240}    # seconds of play pathfind holds: DELAY + REC_S + margin for model looks off play
OFFCPU=${OFFCPU:-1}
TID=56550015
DEV=nova S=ee317437 MIN_BATT=${MIN_BATT:-20}
PKG=com.jreinach.hakux.debug
D=/home/justin/hakux-work/dispatch
OUT=/home/justin/hakux-work/perf/2026-10-04-vcpusleep/$SHORT
APK_REF=${APK_REF:-3ff55c9ac2}
APK=$D/builds/$APK_REF.apk
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../testing" && pwd)"
HOLDSH="$HERE/jobs/hold.sh"
TAG=lane.vcpusleep
LEASE=/tmp/hakux-device-lease.$DEV
PATHFIND_TREE=${PATHFIND_TREE:-/home/justin/hakux-work/wt/pathfind}
PF="$PATHFIND_TREE/docs/testing/titles/pathfind.py"
mkdir -p "$OUT"
# Before the hold: a script that cannot drive the title must not take the device.
[ -f "$PF" ] || { echo "CAP no $PF (set PATHFIND_TREE to a lane/pathfind checkout)"; exit 2; }
[ -f "$PATHFIND_TREE/docs/testing/titles/pathknow/paths/$TID.json" ] \
    || { echo "CAP $PATHFIND_TREE has no recorded Simpsons path (pathknow/paths/$TID.json)"; exit 2; }
a() { timeout "${T:-120}" adb -s $S "$@"; }
say() { echo "CAP $(date -u +%H:%M:%S) $*"; }
running_dev() { grep -lx $DEV "$D"/running/*.owner 2>/dev/null; }
PFLOG="$OUT/pf/logcat.txt"

[ -f "$APK" ] || { say "no apk $APK"; exit 1; }
bash "$HOLDSH" wait $DEV $TAG "${HOLD_WAIT_S:-3600}" \
    "lane.vcpusleep #507: held $DEV session, pathfind hold of Simpsons + 1 x ${REC_S} s off-CPU simpleperf (apk $APK_REF), ~15 min of device time; waits for the running request first; capture_simpsons_offcpu.sh releases on every exit" \
    || { say "could not take hold/$DEV: $(bash "$HOLDSH" who $DEV)"; exit 3; }
say "hold taken"

LEASE_PID="" PF_PID="" USED=0
cleanup() {
    rc=$?
    if [ "$USED" = 1 ]; then
        if [ -n "$PF_PID" ] && kill -0 "$PF_PID" 2>/dev/null; then
            # SIGINT: pathfind's finally releases the titles disk and stops the app
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
say "battery $lvl"
[ -n "$lvl" ] && [ "$lvl" -ge "$MIN_BATT" ] || { say "battery below $MIN_BATT or unreadable"; exit 4; }
say "perf: harden=$(a shell getprop security.perf_harden | tr -d '\r') paranoid=$(a shell cat /proc/sys/kernel/perf_event_paranoid | tr -d '\r') uptime=$(a shell cat /proc/uptime | tr -d '\r' | cut -d' ' -f1)"

T=300 a install -r "$(wslpath -w "$APK")" 2>&1 | tail -1 | grep -q Success || { say "install failed"; exit 5; }
a shell am force-stop $PKG
a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin"
a exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/prefs.xml"
grep -q 'name="validation_layers" value="true"' "$OUT/prefs.xml" && { say "validation_layers on; refusing"; exit 6; }
# A previous request's --env left in the pref would run this capture under it
# (capture_offcpu.sh's clear, unchanged: drop the key, write, read back).
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
a shell "rm -f /data/local/tmp/$SHORT.data"

# pathfind boots the title, replays the recorded path to free roam, claims
# play, writes `mark gameplay` and holds HOLD_S seconds of play
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

# newest pathfind state line: play or still (free roam) opens the gate
last_state() { grep -o 'hakuX-route[^:]*: state=[a-z_]*' "$PFLOG" | tail -1 | sed 's/.*state=//'; }
t=0
while :; do
    st=$(last_state)
    case $st in play|still) break ;; esac
    kill -0 $PF_PID 2>/dev/null || { say "ABORT: pathfind ended (state ${st:-?}) before the record"; exit 7; }
    [ $t -ge "$GATE_S" ] && { say "ABORT: not in play ${GATE_S} s after mark+${DELAY}: state ${st:-?}"; exit 7; }
    sleep 1; t=$((t + 1))
done
say "gate open: state=$st"

ok=0
a shell log -t hakuX-route "'prof start'" >/dev/null
for attempt in 1 2 3 4; do
    off=""; [ "$OFFCPU" = 1 ] && [ $attempt -le 3 ] && off="--trace-offcpu"
    rec=$(T=$((REC_S + 60)) a shell "simpleperf record --app $PKG -e cpu-clock $off --call-graph dwarf,8192 --duration $REC_S -f 1000 -o /data/local/tmp/$SHORT.data" 2>&1)
    say "record attempt $attempt ${off:-(on-CPU only)}"
    echo "$rec" | grep -v 'symbol table' | tail -8 | sed "s/^/CAP rec: /"
    echo "$rec" | grep -q "Recorded for" && { a shell log -t hakuX-route "'prof end'" >/dev/null; ok=1; break; }
    sleep 15
done

# VOID check: any state other than play/still between prof start and prof end
if [ $ok = 1 ]; then
    sleep 2
    bad=$(awk '/hakuX-route.*prof start/{on=1} on && /hakuX-route.*state=/{ if ($0 !~ /state=(play|still) /) print } /hakuX-route.*prof end/{on=0}' "$PFLOG")
    if [ -n "$bad" ]; then
        say "VOID: pathfind left play during the record: $(echo "$bad" | head -3 | tr '\n' ' ')"
        echo "$bad" > "$OUT/VOID"
    fi
fi

# adb is adb.exe: an absolute /home path does not resolve, a cwd-relative one does
[ $ok = 1 ] && ( cd "$OUT" && T=300 a pull /data/local/tmp/$SHORT.data ./$SHORT.data 2>&1 | tail -1 )
[ -f "$OUT/$SHORT.data" ] || ok=0
# pathfind finishes its hold on its own; it stops the app and releases the disk
for _ in $(seq "${PF_WAIT_S:-600}"); do kill -0 $PF_PID 2>/dev/null || break; sleep 1; done
say "profile=$ok void=$([ -f "$OUT/VOID" ] && echo yes || echo no) done"
[ $ok = 1 ]
