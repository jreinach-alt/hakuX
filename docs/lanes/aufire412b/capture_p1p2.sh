#!/bin/bash
# lane.aufire412b: the held Nova session granted 2026-09-26 17:49 PDT (brief
# addendum). Agent Under Fire on the survey route, APK 1b557ff6a4 (the folded
# #416 hunk, not perflog), two 30 s vCPU-side simpleperf captures:
#   p1  pause menu over the scene: starts 5 s after the 11th `press START`
#       of the route's 14 menu rounds (the soaks' 220-285 s window);
#   p2  mission play: starts 40 s after `mark play` (the soaks' 299-483 s).
# The route is the survey route verbatim (shots included), from
# dispatch/results/0-0-y-1790433159-titleplay-p1-aufire/request.json, so the
# scene and its timing match the soaks the profile is read against.
#
# Hold: taken only if hold/nova is absent and no running/*.owner names nova;
# released only if it still holds our tag. Every exit path force-stops the
# app, clears the shader caches this APK wrote (the dispatcher reinstalls its
# own APK per request, and an empty cache is only a cold one), sleeps the
# screen with KEYCODE_SLEEP, and releases the hold.
set -u
S=ee317437
PKG=com.jreinach.hakux.debug
D=/home/justin/hakux-work/dispatch
OUT=/home/justin/hakux-work/perf/2026-09-26-aufire412b
APK=$D/builds/1b557ff6a4.apk
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../testing" && pwd)"
TAG="aufire412b:$$:$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOLD=$D/hold/nova
SOAK_S=480
mkdir -p "$OUT"
a() { timeout "${T:-120}" adb -s $S "$@"; }
say() { echo "CAP $(date -u +%H:%M:%S) $*"; }

running_nova() { grep -lx nova "$D"/running/*.owner 2>/dev/null; }

[ -f "$APK" ] || { say "no apk $APK"; exit 1; }
[ -e "$HOLD" ] && { say "hold/nova exists: $(cat "$HOLD")"; exit 3; }
r=$(running_nova) && { say "running on nova: $r"; exit 3; }
lvl=$(a shell dumpsys battery | tr -d '\r' | awk '/level:/{print $2; exit}')
say "battery $lvl"
[ -n "$lvl" ] && [ "$lvl" -ge 30 ] || { say "battery below 30 or unreadable"; exit 4; }

( set -o noclobber; echo "$TAG" > "$HOLD" ) 2>/dev/null || { say "lost the race for hold/nova"; exit 3; }
echo "lane.aufire412b #412: held Nova session, 2 x 30 s simpleperf of AUF (apk 1b557ff6a4), <=15 min, granted by hostops 2026-09-26 17:49 PDT; tag $TAG" > "$HOLD.why"
say "hold taken: $TAG"

SOAK_PID=""
cleanup() {
    rc=$?
    [ -n "$SOAK_PID" ] && kill "$SOAK_PID" 2>/dev/null && wait "$SOAK_PID" 2>/dev/null
    a shell am force-stop $PKG >/dev/null 2>&1
    a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin" >/dev/null 2>&1
    a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
    if [ "$(cat "$HOLD" 2>/dev/null)" = "$TAG" ]; then
        rm -f "$HOLD" "$HOLD.why"; say "hold released"
    else
        say "hold no longer ours; left alone"
    fi
    say "exit rc=$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# A request that was claimed between our check and our hold finishes first.
for i in $(seq 1 30); do
    r=$(running_nova) || break
    say "waiting for running request $r"; sleep 20
done
running_nova >/dev/null && { say "nova still busy after 10 min"; exit 3; }

T=300 a install -r "$APK" 2>&1 | tail -1 | grep -q Success || { say "install failed"; exit 5; }
a shell am force-stop $PKG
a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin"
a exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/prefs.xml"
grep -q 'name="validation_layers" value="true"' "$OUT/prefs.xml" && { say "validation_layers on; refusing"; exit 6; }
a shell "rm -f /data/local/tmp/p1.data /data/local/tmp/p2.data"

python3 - "$D/results/0-0-y-1790433159-titleplay-p1-aufire/request.json" > "$OUT/route.txt" <<'EOF'
import json, sys
print(json.load(open(sys.argv[1]))["route"])
EOF

LOGCAT_SPEC="hakuX-crash:V hakuX-unhandled:W hakuX-perf:I hakuX-phase:I xemu-work:I hakuX:I hakuX-stderr:E hakuX-vk:I hakuX-route:I hakuX-pace:I hakuX-stall:I hakuX-cpu:I xemu-gpu:I libc:F DEBUG:F *:S" \
HAKUX_DEVICE_LEASE="$OUT/soak.lease" CAPTURE_LOG="$OUT/logcat.txt" ROUTE_FILE="$OUT/route.txt" SERIAL=$S \
    setsid bash "$HERE/soak_title.sh" "/storage/E6C6-D7AA/Games/XBox/4541000D-007_Agent_Under_Fire.xiso.iso" $SOAK_S \
    > "$OUT/soak.log" 2>&1 &
SOAK_PID=$!
say "soak pid $SOAK_PID"

record() {  # <name>
    local rec
    for attempt in 1 2; do
        rec=$(T=90 a shell "simpleperf record --app $PKG -e cpu-clock --call-graph dwarf,8192 --duration 30 -f 1000 -o /data/local/tmp/$1.data" 2>&1)
        echo "$rec" | tail -3 | sed "s/^/CAP $1: /"
        echo "$rec" | grep -q "Recorded for" && { a shell log -t hakuX-route "'$1 end'" >/dev/null; return 0; }
        sleep 2
    done
    return 1
}

wait_for() {  # <grep pattern> <nth> <timeout s>
    local t=0
    while [ $t -lt "$3" ]; do
        [ "$(grep -c -- "$1" "$OUT/soak.log")" -ge "$2" ] && return 0
        kill -0 $SOAK_PID 2>/dev/null || return 1
        sleep 1; t=$((t + 1))
    done
    return 1
}

p1=0 p2=0
if wait_for "ROUTE .* press START" 11 400; then
    sleep 5
    a shell log -t hakuX-route "'p1 start'" >/dev/null
    say "p1 start"; record p1 && p1=1
else
    say "p1: 11th menu round never came"
fi
if wait_for "ROUTE .* mark play" 1 300; then
    sleep 40
    a shell log -t hakuX-route "'p2 start'" >/dev/null
    say "p2 start"; record p2 && p2=1
else
    say "p2: mark play never came"
fi
kill $SOAK_PID 2>/dev/null; wait $SOAK_PID 2>/dev/null; SOAK_PID=""
[ $p1 = 1 ] && T=300 a pull /data/local/tmp/p1.data "$OUT/p1.data" 2>&1 | tail -1
[ $p2 = 1 ] && T=300 a pull /data/local/tmp/p2.data "$OUT/p2.data" 2>&1 | tail -1
say "p1=$p1 p2=$p2 done"
