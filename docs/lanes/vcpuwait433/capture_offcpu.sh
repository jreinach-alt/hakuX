#!/bin/bash
# lane.vcpuwait433 (#433): one held Nova session, one 60 s OFF-CPU simpleperf
# capture of Tron 2.0's slow in-engine window. A copy of
# docs/lanes/slowdown462/capture_profile.sh (the trace that found DOA's
# pgraph_read lock, #474) with these changes, nothing else:
#   - the route is docs/lanes/vcpuwait433/tron-newgame.route (lane.near30's
#     Tron New Game route, byte-identical), not titles/routes/survey.route;
#   - the anchor is `mark gameplay` and the record starts DELAY (default 10) s
#     after it: on 4 of the 5 New Game soaks lane.near30 decomposed, the first
#     two minutes after that mark are the slowest of the run (16-25 of 30 rows
#     below 28.5 fps, vCPU asleep 8.4-11.3 ms per frame);
#   - `--trace-offcpu` is on by default (OFFCPU=1) and the record is REC_S
#     (default 60) s; SOAK_S defaults to 420 (the mark lands ~229 s after
#     launch);
#   - APK 16f09aa346 (not perflog): the ref of 5 of lane.near30's 7 plain
#     Tron runs, so the profile and the decomposed soaks ran one emulator;
#   - PERF_REGIMEN=default (the decomposed soaks' regimen);
#   - the hold tag is lane.vcpuwait433, and the hold is `take` then
#     `wait-idle` (hold.sh's own recipe).
#
#   DEV=nova capture_offcpu.sh <short> "Tron 2.0 - Killer App (USA, Europe).iso"
#
# Read the result with docs/lanes/slowdown462/offcpu.py <short>.data <vCPU tid>
# (switch records, not simpleperf report's weighting).
#
# Hold: taken and released only with jobs/hold.sh (tag lane.vcpuwait433); a
# request already running on the Nova finishes first. The per-device lease is
# kept fresh while this script lives (the Stop hook reads only the lease).
# Every exit path force-stops the app, clears this APK's shader caches, drops
# the dispatcher's shader-cache marker (so its next run reinstalls), sleeps the
# screen and releases the hold. The env marker is dropped only after this
# script has cleared a leftover env pref and read the clear back.
set -u
SHORT=$1 ISO=$2 DELAY=${3:-10}
REC_S=${REC_S:-60}
OFFCPU=${OFFCPU:-1}
export PERF_REGIMEN=${PERF_REGIMEN:-default}
ROUTE_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tron-newgame.route"
# DEV: nova (the five titles) or thor (GTA SA only: hostops grant, 09-27 08:20 PDT)
DEV=${DEV:-nova}
case $DEV in nova) S=ee317437 MIN_BATT=${MIN_BATT:-20} ;; thor) S=bdc158a5 MIN_BATT=${MIN_BATT:-30} ;; *) echo "DEV nova|thor"; exit 2 ;; esac
PKG=com.jreinach.hakux.debug
D=/home/justin/hakux-work/dispatch
OUT=/home/justin/hakux-work/perf/2026-10-02-vcpuwait433/$SHORT
APK_REF=${APK_REF:-16f09aa346}
APK=$D/builds/$APK_REF.apk
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../testing" && pwd)"
HOLDSH="$HERE/jobs/hold.sh"
TAG=lane.vcpuwait433
LEASE=/tmp/hakux-device-lease.$DEV
SOAK_S=${SOAK_S:-510}   # 420 + the slow gate's 90 s cap
mkdir -p "$OUT"
a() { timeout "${T:-120}" adb -s $S "$@"; }
say() { echo "CAP $(date -u +%H:%M:%S) $*"; }
running_dev() { grep -lx $DEV "$D"/running/*.owner 2>/dev/null; }

[ -f "$APK" ] || { say "no apk $APK"; exit 1; }
# The grant (#462, 21:10 PDT): the session runs only between runs. A poll
# for an empty running/ never sees the gap: on 2026-09-26 04:31:38-04:32:41Z a
# 2 s poll missed it, the dispatcher claiming the next request in the same
# second the last one ended (aufire412b saw the same). So the hold is taken
# while a request may still be running: it stops the NEXT claim, the running
# request finishes untouched (nothing below touches the device until running/
# is empty of the Nova), and the session then has the gap.
bash "$HOLDSH" wait $DEV $TAG "${HOLD_WAIT_S:-3600}" \
    "lane.vcpuwait433 #433: held $DEV session, 1 x ${REC_S} s off-CPU simpleperf of $SHORT (apk $APK_REF), ~10 min of device time; waits for the running request first; capture_offcpu.sh releases on every exit" \
    || { say "could not take hold/$DEV: $(bash "$HOLDSH" who $DEV)"; exit 3; }
say "hold taken"

LEASE_PID="" SOAK_PID="" USED=0
cleanup() {
    rc=$?
    if [ "$USED" = 1 ]; then
    [ -n "$SOAK_PID" ] && kill "$SOAK_PID" 2>/dev/null && wait "$SOAK_PID" 2>/dev/null
    # soak_title.sh restores REST on its own exit; if it never ran or did not, do it here
    if ! grep -q '"perf_restored": true' "$OUT/perf_regimen.json" 2>/dev/null; then
        ( . "$HERE/devices.sh"; read -r _ _ pr fr <<<"$(device_perf_values $S)"
          [ -n "$pr" ] && SERIAL=$S device_perf_set "$pr" "$fr" >/dev/null && say "REST set by cleanup" )
    fi
    a shell am force-stop $PKG >/dev/null 2>&1
    a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin" >/dev/null 2>&1
    # Not .env_pref.$DEV: that marker is how the dispatcher knows to clear a
    # previous request's env, and it goes only after a read-back clear above.
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
# the lease is the dispatcher's while its request runs; ours only from here
( while :; do touch "$LEASE"; sleep 20; done ) & LEASE_PID=$!
say "device free; session starts"

lvl=$(a shell dumpsys battery | tr -d '\r' | awk '/level:/{print $2; exit}')
say "battery $lvl"
[ -n "$lvl" ] && [ "$lvl" -ge "$MIN_BATT" ] || { say "battery below $MIN_BATT or unreadable"; exit 4; }
# --trace-offcpu needs the sched_switch tracepoint; these say whether it can open
say "perf: harden=$(a shell getprop security.perf_harden | tr -d '\r') paranoid=$(a shell cat /proc/sys/kernel/perf_event_paranoid | tr -d '\r') uptime=$(a shell cat /proc/uptime | tr -d '\r' | cut -d' ' -f1)"

ROOTS=$( . "$HERE/devices.sh"; device_env $S >/dev/null; echo "$DEVICE_ISO_ROOTS")
ISOPATH=""
for r in ${ROOTS//:/ }; do
    # quoted: Tron's file name has spaces and parentheses
    ISOPATH=$(a shell "ls '$r/$ISO'" 2>/dev/null | tr -d '\r' | grep -v 'No such' | head -1)
    [ -n "$ISOPATH" ] && break
done
[ -n "$ISOPATH" ] || { say "no $ISO on the $DEV ($ROOTS)"; exit 5; }
say "iso $ISOPATH"

T=300 a install -r "$(wslpath -w "$APK")" 2>&1 | tail -1 | grep -q Success || { say "install failed"; exit 5; }
a shell am force-stop $PKG
a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin"
a exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/prefs.xml"
grep -q 'name="validation_layers" value="true"' "$OUT/prefs.xml" && { say "validation_layers on; refusing"; exit 6; }
# A previous request's --env left in the pref would run this profile under it.
# Clear it the dispatcher's way (apply_env_pref: drop the key, write, read
# back) and only then drop its marker. On 09-27 09:08 this script refused
# here, and its cleanup dropped the marker with the env still set: the next
# Thor request (titleroutes Azurik) ran under HAKUX_TCG424_RANGE=1.
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
cp "$ROUTE_SRC" "$OUT/route.txt" || { say "no route $ROUTE_SRC"; exit 5; }

# the dispatcher's spec (dispatcher.sh), so decompose.py reads this logcat as it
# reads a soak's: [idlehalt]/[rr425w]/[tlb68] are hakuX W, [rwait526] hakuX-lane
LOGCAT_SPEC="hakuX-crash:V hakuX-unhandled:W hakuX-audio:I hakuX-audiocap:I hakuX-build:I hakuX-perf:I hakuX-phase:I xemu-work:I hakuX-lane:I hakuX-tier1:D hakuX-pages:I hakuX:I hakuX-rw:I hakuX-stderr:E hakuX-vk:I hakuX-route:I hakuX-pace:I hakuX-stall:I hakuX-rpbrk:I hakuX-cpu:I xemu-gpu:I xemu-sfp:I xemu-surf:I libc:F DEBUG:F *:S" \
HAKUX_DEVICE_LEASE="$OUT/soak.lease" CAPTURE_LOG="$OUT/logcat.txt" ROUTE_FILE="$OUT/route.txt" SERIAL=$S \
PERF_RESULT="$OUT/perf_regimen.json" \
    setsid bash "$HERE/soak_title.sh" "$ISOPATH" $SOAK_S > "$OUT/soak.log" 2>&1 &
SOAK_PID=$!
say "soak pid $SOAK_PID"

wait_for() {  # <grep pattern> <nth> <timeout s>
    local t=0
    while [ $t -lt "$3" ]; do
        [ "$(grep -c -- "$1" "$OUT/soak.log")" -ge "$2" ] && return 0
        kill -0 $SOAK_PID 2>/dev/null || return 1
        sleep 1; t=$((t + 1))
    done
    return 1
}

ok=0
# ANCHOR / ANCHOR_N: start at the Nth route line matching ANCHOR instead of
# `mark play` (DOA fights during the menu rounds: the 8th `press START`).
if wait_for "ROUTE .* ${ANCHOR:-mark gameplay}" "${ANCHOR_N:-1}" 400; then
    sleep "$DELAY"
    # Slow-window gate: record once a hakuX-pace second shows the guest below
    # SLOW_FPS (frames per 1 s line), or after GATE_S. tron1 recorded a menu at
    # 60 fps because nothing looked; the log line says which way it started.
    t=0; fps=""
    while [ $t -lt "${GATE_S:-90}" ]; do
        fps=$(grep 'hakuX-pace' "$OUT/logcat.txt" | tail -2 | sed -n 's/.* f=\([0-9]*\) .*/\1/p' | awk 'NR==1{a=$1} NR==2{print $1-a}')
        [ -n "$fps" ] && [ "$fps" -lt "${SLOW_FPS:-40}" ] && break
        sleep 1; t=$((t + 1))
    done
    say "slow gate: last pace second ${fps:-?} fps after ${t} s (bar ${SLOW_FPS:-40}, cap ${GATE_S:-90} s)"
    a shell log -t hakuX-route "'prof start'" >/dev/null
    say "prof start"
    # The off-CPU half IS this capture: an on-CPU fallback cannot name a wait.
    # `--trace-offcpu` can fail at once and open minutes later on one boot
    # (slowdown462, Blinx 00:23), so attempts 1-3 keep it, 15 s apart, all
    # inside the ~2 min slow window; only attempt 4 drops it (a record of
    # some kind, marked on-CPU only in the log).
    for attempt in 1 2 3 4; do
        off=""; [ "$OFFCPU" = 1 ] && [ $attempt -le 3 ] && off="--trace-offcpu"
        rec=$(T=$((REC_S + 60)) a shell "simpleperf record --app $PKG -e cpu-clock $off --call-graph dwarf,8192 --duration $REC_S -f 1000 -o /data/local/tmp/$SHORT.data" 2>&1)
        say "record attempt $attempt ${off:-(on-CPU only)}"
        # all of it: on 09-27 attempt 1 failed with an error the last 3 lines cut
        echo "$rec" | grep -v 'symbol table' | tail -8 | sed "s/^/CAP rec: /"
        echo "$rec" | grep -q "Recorded for" && { a shell log -t hakuX-route "'prof end'" >/dev/null; ok=1; break; }
        sleep 15
    done
else
    say "anchor ${ANCHOR:-mark gameplay} x${ANCHOR_N:-1} never came"
fi
sleep 5
kill $SOAK_PID 2>/dev/null; wait $SOAK_PID 2>/dev/null; SOAK_PID=""
# adb is adb.exe: an absolute /home path does not resolve, a cwd-relative one does
[ $ok = 1 ] && ( cd "$OUT" && T=300 a pull /data/local/tmp/$SHORT.data ./$SHORT.data 2>&1 | tail -1 )
[ -f "$OUT/$SHORT.data" ] || ok=0
say "profile=$ok done"
[ $ok = 1 ]
