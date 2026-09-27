#!/bin/bash
# lane.slowdown462 (#462): one held Nova session per title, one 30 s simpleperf
# capture of gameplay, the survey route verbatim (the route the title's perflog
# soak ran). Generalised from docs/lanes/aufire412b/capture_p1p2.sh.
#
#   capture_profile.sh <short> <iso file name> [delay after `mark play`, s]
#
# APK: dispatch/builds/a593d8eb85.apk (not perflog). It is code-identical to
# e5db66fa37, the ref of every soak this lane queued (`git diff --stat
# a593d8eb85 e5db66fa37 -- ':!docs'` is empty), so the profile and the soak ran
# one emulator.
#
# Capture: `simpleperf record --app <pkg> -e cpu-clock --call-graph dwarf,8192
# --duration 30 -f 1000`, starting <delay> s (default 60) after the route's
# `mark play`. `prof start`/`prof end` go to logcat (hakuX-route) so the
# window can be cut from the session logcat, which carries the same tags as a
# dispatcher soak.
#
# Hold: taken and released only with jobs/hold.sh (tag lane.slowdown462); a
# request already running on the Nova finishes first. The per-device lease is
# kept fresh while this script lives (the Stop hook reads only the lease).
# Every exit path force-stops the app, clears this APK's shader caches, drops
# the dispatcher's shader-cache and env markers for the Nova (so its next run
# reinstalls and re-applies prefs), sleeps the screen and releases the hold.
set -u
SHORT=$1 ISO=$2 DELAY=${3:-60}
S=ee317437 DEV=nova
PKG=com.jreinach.hakux.debug
D=/home/justin/hakux-work/dispatch
OUT=/home/justin/hakux-work/perf/2026-09-26-slowdown462/$SHORT
APK=$D/builds/a593d8eb85.apk
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../testing" && pwd)"
HOLDSH="$HERE/jobs/hold.sh"
TAG=lane.slowdown462
LEASE=/tmp/hakux-device-lease.$DEV
SOAK_S=${SOAK_S:-330}
mkdir -p "$OUT"
a() { timeout "${T:-120}" adb -s $S "$@"; }
say() { echo "CAP $(date -u +%H:%M:%S) $*"; }
running_nova() { grep -lx $DEV "$D"/running/*.owner 2>/dev/null; }

[ -f "$APK" ] || { say "no apk $APK"; exit 1; }
# The grant (#462, 21:10 PDT): the session runs only between runs. A poll
# for an empty running/ never sees the gap: on 2026-09-26 04:31:38-04:32:41Z a
# 2 s poll missed it, the dispatcher claiming the next request in the same
# second the last one ended (aufire412b saw the same). So the hold is taken
# while a request may still be running: it stops the NEXT claim, the running
# request finishes untouched (nothing below touches the device until running/
# is empty of the Nova), and the session then has the gap.
bash "$HOLDSH" wait $DEV $TAG "${HOLD_WAIT_S:-3600}" \
    "lane.slowdown462 #462: held Nova session, 1 x 30 s simpleperf of $SHORT (apk a593d8eb85), <10 min of device time; waits for the running request first; capture_profile.sh releases on every exit" \
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
    rm -f "$D/.shader_cache_apk.$DEV" "$D/.env_pref.$DEV"
    a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
    fi
    [ -n "$LEASE_PID" ] && kill "$LEASE_PID" 2>/dev/null && rm -f "$LEASE"
    bash "$HOLDSH" release $DEV $TAG && say "hold released" || say "hold not ours; left alone"
    say "exit rc=$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

for i in $(seq 1 45); do
    r=$(running_nova) || break
    say "waiting for running request $r"; sleep 20
done
running_nova >/dev/null && { say "nova still busy after 15 min"; exit 3; }
USED=1
# the lease is the dispatcher's while its request runs; ours only from here
( while :; do touch "$LEASE"; sleep 20; done ) & LEASE_PID=$!
say "device free; session starts"

lvl=$(a shell dumpsys battery | tr -d '\r' | awk '/level:/{print $2; exit}')
say "battery $lvl"
[ -n "$lvl" ] && [ "$lvl" -ge "${MIN_BATT:-20}" ] || { say "battery below ${MIN_BATT:-20} or unreadable"; exit 4; }

ISOPATH=$(a shell "ls /storage/*/Games/XBox/$ISO" 2>/dev/null | tr -d '\r' | head -1)
[ -n "$ISOPATH" ] || { say "no $ISO on the Nova"; exit 5; }
say "iso $ISOPATH"

T=300 a install -r "$(wslpath -w "$APK")" 2>&1 | tail -1 | grep -q Success || { say "install failed"; exit 5; }
a shell am force-stop $PKG
a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin"
a exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/prefs.xml"
grep -q 'name="validation_layers" value="true"' "$OUT/prefs.xml" && { say "validation_layers on; refusing"; exit 6; }
# A previous request's --env left in the pref would run this profile under it.
grep -Eq '<string name="env_vars">[^<]+' "$OUT/prefs.xml" && { say "env_vars pref not empty; refusing: $(grep 'name="env_vars"' "$OUT/prefs.xml")"; exit 6; }
a shell "rm -f /data/local/tmp/$SHORT.data"
cp "$HERE/titles/routes/survey.route" "$OUT/route.txt"

LOGCAT_SPEC="hakuX-crash:V hakuX-unhandled:W hakuX-perf:I hakuX-phase:I xemu-work:I hakuX-tier1:D hakuX-pages:I hakuX:I hakuX-stderr:E hakuX-vk:I hakuX-route:I hakuX-pace:I hakuX-stall:I hakuX-rpbrk:I hakuX-cpu:I xemu-gpu:I xemu-sfp:I libc:F DEBUG:F *:S" \
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
if wait_for "ROUTE .* mark play" 1 400; then
    sleep "$DELAY"
    a shell log -t hakuX-route "'prof start'" >/dev/null
    say "prof start"
    for attempt in 1 2; do
        rec=$(T=90 a shell "simpleperf record --app $PKG -e cpu-clock --call-graph dwarf,8192 --duration 30 -f 1000 -o /data/local/tmp/$SHORT.data" 2>&1)
        echo "$rec" | tail -3 | sed "s/^/CAP rec: /"
        echo "$rec" | grep -q "Recorded for" && { a shell log -t hakuX-route "'prof end'" >/dev/null; ok=1; break; }
        sleep 2
    done
else
    say "mark play never came"
fi
sleep 5
kill $SOAK_PID 2>/dev/null; wait $SOAK_PID 2>/dev/null; SOAK_PID=""
# adb is adb.exe: an absolute /home path does not resolve, a cwd-relative one does
[ $ok = 1 ] && ( cd "$OUT" && T=300 a pull /data/local/tmp/$SHORT.data ./$SHORT.data 2>&1 | tail -1 )
[ -f "$OUT/$SHORT.data" ] || ok=0
say "profile=$ok done"
[ $ok = 1 ]
