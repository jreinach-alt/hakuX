#!/bin/bash
# lane.doa413c (#413): one held Nova session over DOA Ultimate's scene-load
# stall. Adapted from docs/lanes/slowdown462/capture_profile.sh (hold, lease,
# env-pref and cleanup handling; read that file's comments for why) and
# docs/lanes/gta482/capture_gta.sh (the code-buffer and RAM dump).
#
#   capture_stall.sh
#
# What it takes:
#   - the soak's logcat (soak_title.sh, the survey route: the source run's);
#   - taskio.txt: every emulator thread's read counters and CPU ticks, once a
#     second, launch to exit (taskio.sh, read by taskio.py);
#   - up to two stall records. stallwatch.py waits for a stall on the live
#     logcat (no fifoskew/gfps line for GAP s while the vCPU is pegged), then
#     rec-N.data: simpleperf record -e cpu-clock --call-graph dwarf,8192
#     --duration REC_S -f 1000 over the app, marked 'prof N start/end' in the
#     logcat, and straight after it the TCG code buffer (codebuf-N-<start>.bin.gz)
#     so tbmap.py maps that record's JIT samples to guest pcs;
#   - the guest RAM (ram-<start>.bin.gz) once, after the last record, so the
#     hot pcs can be disassembled.
# APK: dispatch/builds/a593d8eb85.apk (slowdown462's DOA profiles;
# include/exec/translation-block.h is unchanged from it to f82e7e87fe, the
# layout tbmap.py reads).
set -u
DEV=nova S=ee317437 MIN_BATT=${MIN_BATT:-20}
PKG=com.jreinach.hakux.debug
D=/home/justin/hakux-work/dispatch
OUT=${OUT:-/home/justin/hakux-work/perf/2026-09-27-doa413c/s1}
APK_REF=${APK_REF:-a593d8eb85}
APK=$D/builds/$APK_REF.apk
ISO=54430006-Dead_or_Alive_1_Ultimate.xiso.iso
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../testing" && pwd)"
LANE="$HERE/../lanes/doa413c"
HOLDSH="$HERE/jobs/hold.sh"
TAG=lane.doa413c
LEASE=/tmp/hakux-device-lease.$DEV
SOAK_S=${SOAK_S:-330}
GAP=${GAP:-3}
REC_S=${REC_S:-6}
NREC=${NREC:-2}
mkdir -p "$OUT"
a() { timeout "${T:-120}" adb -s $S "$@"; }
say() { echo "CAP $(date -u +%H:%M:%S) $*"; }
running_dev() { grep -lx $DEV "$D"/running/*.owner 2>/dev/null; }
T0=""

[ -f "$APK" ] || { say "no apk $APK"; exit 1; }
w=$(bash "$HOLDSH" who $DEV)
case "$w" in
*" by $TAG -- "*) say "hold already ours" ;;
held:*) say "hold/$DEV held by someone else: $w; not waiting"; exit 3 ;;
*) bash "$HOLDSH" take $DEV $TAG \
    "lane.doa413c #413: held Nova session, DOA Ultimate scene-load stall: <=2 x ${REC_S} s simpleperf + code-buffer/RAM dump, apk $APK_REF, <10 min of device time; waits for the running request first; capture_stall.sh releases on every exit" \
    || { say "could not take hold/$DEV: $(bash "$HOLDSH" who $DEV)"; exit 3; }
   say "hold taken" ;;
esac

LEASE_PID="" SOAK_PID="" IO_PID="" USED=0
cleanup() {
    rc=$?
    if [ "$USED" = 1 ]; then
    [ -n "$SOAK_PID" ] && kill "$SOAK_PID" 2>/dev/null && wait "$SOAK_PID" 2>/dev/null
    if ! grep -q '"perf_restored": true' "$OUT/perf_regimen.json" 2>/dev/null; then
        ( . "$HERE/devices.sh"; read -r _ _ pr fr <<<"$(device_perf_values $S)"
          [ -n "$pr" ] && SERIAL=$S device_perf_set "$pr" "$fr" >/dev/null && say "REST set by cleanup" )
    fi
    a shell am force-stop $PKG >/dev/null 2>&1
    [ -n "$IO_PID" ] && kill "$IO_PID" 2>/dev/null
    a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin files/doa413c-taskio.sh" >/dev/null 2>&1
    a shell "rm -f /data/local/tmp/doa413c-*.data" >/dev/null 2>&1
    rm -f "$D/.shader_cache_apk.$DEV"
    a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
    [ -n "$T0" ] && say "device time $(( $(date +%s) - T0 )) s"
    fi
    [ -n "$LEASE_PID" ] && kill "$LEASE_PID" 2>/dev/null && rm -f "$LEASE"
    bash "$HOLDSH" release $DEV $TAG && say "hold released" || say "hold not ours; left alone"
    say "exit rc=$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

for i in $(seq 1 45); do
    r=$(running_dev) || break
    say "waiting for running request $r"; sleep 20
done
running_dev >/dev/null && { say "$DEV still busy after 15 min"; exit 3; }
USED=1
T0=$(date +%s)
( while :; do touch "$LEASE"; sleep 20; done ) & LEASE_PID=$!
say "device free; session starts"

lvl=$(a shell dumpsys battery | tr -d '\r' | awk '/level:/{print $2; exit}')
say "battery $lvl"
[ -n "$lvl" ] && [ "$lvl" -ge "$MIN_BATT" ] || { say "battery below $MIN_BATT or unreadable"; exit 4; }
say "perf: harden=$(a shell getprop security.perf_harden | tr -d '\r') paranoid=$(a shell cat /proc/sys/kernel/perf_event_paranoid | tr -d '\r') uptime=$(a shell cat /proc/uptime | tr -d '\r' | cut -d' ' -f1)"

ROOTS=$( . "$HERE/devices.sh"; device_env $S >/dev/null; echo "$DEVICE_ISO_ROOTS")
ISOPATH=""
for r in ${ROOTS//:/ }; do
    ISOPATH=$(a shell "ls $r/$ISO" 2>/dev/null | tr -d '\r' | grep -v 'No such' | head -1)
    [ -n "$ISOPATH" ] && break
done
[ -n "$ISOPATH" ] || { say "no $ISO on the $DEV ($ROOTS)"; exit 5; }
say "iso $ISOPATH"

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
a shell "rm -f /data/local/tmp/doa413c-*.data"
cp "$HERE/titles/routes/survey.route" "$OUT/route.txt" || { say "no route survey"; exit 5; }

LOGCAT_SPEC="hakuX-crash:V hakuX-unhandled:W hakuX-perf:I hakuX-phase:I xemu-work:I hakuX-tier1:D hakuX-pages:I hakuX:I hakuX-stderr:E hakuX-vk:I hakuX-route:I hakuX-pace:I hakuX-stall:I hakuX-rpbrk:I hakuX-cpu:I xemu-gpu:I xemu-sfp:I libc:F DEBUG:F *:S" \
HAKUX_DEVICE_LEASE="$OUT/soak.lease" CAPTURE_LOG="$OUT/logcat.txt" ROUTE_FILE="$OUT/route.txt" SERIAL=$S \
PERF_RESULT="$OUT/perf_regimen.json" \
    setsid bash "$HERE/soak_title.sh" "$ISOPATH" $SOAK_S > "$OUT/soak.log" 2>&1 &
SOAK_PID=$!
say "soak pid $SOAK_PID"
# the sampler waits (up to 120 s) for the emulator process to appear; it is
# written into the app's files/ the way the prefs are (stdin through run-as)
a shell "run-as $PKG sh -c 'cat > files/doa413c-taskio.sh'" < "$LANE/taskio.sh"
( T=$((SOAK_S + 200)) a shell "run-as $PKG sh files/doa413c-taskio.sh $PKG:xemu" < /dev/null > "$OUT/taskio.txt" 2>&1 ) & IO_PID=$!

PID=""
dump() {  # <kind: codebuf|ram> <label>
    [ -n "$PID" ] || PID=$(a shell "ps -A -o PID,NAME" | tr -d '\r' | awk -v n="$PKG:xemu" '$2 == n {print $1; exit}')
    [ -n "$PID" ] || { say "no emulator pid; no $1 dump"; return 1; }
    a exec-out "run-as $PKG cat /proc/$PID/maps" > "$OUT/maps-$2.txt"
    python3 - "$OUT/maps-$2.txt" "$1" > "$OUT/regions-$2.txt" <<'PYMAPS'
import sys
out = []
for l in open(sys.argv[1]):
    f = l.split()
    if len(f) < 5:
        continue
    path = f[5] if len(f) > 5 else ''
    if path and not path.startswith('[anon'):
        continue
    lo, hi = (int(x, 16) for x in f[0].split('-'))
    if sys.argv[2] == 'codebuf' and 'x' in f[1] and hi - lo >= 1 << 20:
        out.append(f"{lo:x} {hi:x}")
    elif sys.argv[2] == 'ram' and 'w' in f[1] and 'x' not in f[1] and hi - lo in (64 << 20, 128 << 20):
        out.append(f"{lo:x} {hi:x}")
print("\n".join(out[:2]))
PYMAPS
    say "$1 regions ($2): $(tr '\n' ';' < "$OUT/regions-$2.txt")"
    while read -r lo hi; do
        sk=$(( 0x$lo / 4096 )); ct=$(( (0x$hi - 0x$lo) / 4096 ))
        T=180 a exec-out "run-as $PKG sh -c 'dd if=/proc/$PID/mem bs=4096 skip=$sk count=$ct 2>/dev/null | gzip -1'" > "$OUT/$1-$2-$lo.bin.gz" < /dev/null
        n=$(gzip -dc "$OUT/$1-$2-$lo.bin.gz" 2>/dev/null | wc -c)
        say "dump $1 $2 $lo: $n of $(( ct * 4096 )) bytes"
    done < "$OUT/regions-$2.txt"
}

nrec=0
deadline=$(( $(date +%s) + SOAK_S + 60 ))
while [ $nrec -lt "$NREC" ] && kill -0 $SOAK_PID 2>/dev/null; do
    left=$(( deadline - $(date +%s) ))
    [ $left -gt 20 ] || break
    st=$(python3 "$LANE/stallwatch.py" "$OUT/logcat.txt" $left --gap "$GAP" --after "mark booted" --runlog "$OUT/soak.log") || { say "no stall before the deadline"; break; }
    nrec=$((nrec + 1))
    a shell log -t hakuX-route "'prof $nrec start'" >/dev/null
    say "rec $nrec: $st"
    rec=$(T=60 a shell "simpleperf record --app $PKG -e cpu-clock --call-graph dwarf,8192 --duration $REC_S -f 1000 -o /data/local/tmp/doa413c-$nrec.data" 2>&1)
    a shell log -t hakuX-route "'prof $nrec end'" >/dev/null
    echo "$rec" | grep -v 'symbol table' | tail -4 | sed "s/^/CAP rec-$nrec: /"
    dump codebuf $nrec
    a exec-out screencap -p > "$OUT/shot-$nrec.png" 2>/dev/null
    # the next stall must be a new one: wait for the pusher to come back first
    t=0
    while [ $t -lt 60 ] && kill -0 $SOAK_PID 2>/dev/null; do
        python3 "$LANE/stallwatch.py" "$OUT/logcat.txt" 1 --gap "$GAP" >/dev/null || break
        sleep 2; t=$((t + 2))
    done
done
[ $nrec -gt 0 ] && dump ram last
# let the soak run on to its end (the fight is taskio's control window)
wait $SOAK_PID 2>/dev/null; SOAK_PID=""
for n in $(seq 1 $nrec); do
    ( cd "$OUT" && T=300 a pull /data/local/tmp/doa413c-$n.data ./rec-$n.data 2>&1 | tail -1 )
done
say "records=$nrec done"
[ $nrec -gt 0 ]
