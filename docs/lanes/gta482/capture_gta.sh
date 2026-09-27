#!/bin/bash
# lane.gta482 (#482): one held Thor session in GTA: San Andreas's open world.
# Adapted from docs/lanes/slowdown462/capture_profile.sh (same hold, lease,
# env-pref and cleanup handling; read that file's comments for why).
#
#   capture_gta.sh [delay after `mark gameplay`, s, default 60]
#
# What it takes, in order, starting <delay> s after the gta-sa route's
# `mark gameplay` (slowdown462's soak with frames: the open world starts
# ~43 s after the mark):
#   1. screencap shot1.png
#   2. rec-on.data:  simpleperf record -e cpu-clock --call-graph dwarf,8192
#      --duration 25 -f 1000 (on-CPU)
#   3. screencap shot2.png
#   4. rec-off.data: the same plus --trace-offcpu (where threads block); one
#      retry, skipped if the session is past its deadline
#   5. screencap shot3.png
#   6. maps.txt and every executable anonymous/memfd mapping of the emulator
#      process of >= 1 MiB, read from /proc/<pid>/mem under run-as and gzipped
#      on the device (codebuf-<start>.bin.gz). That is the TCG code buffer:
#      each TranslationBlock header sits just before its host code, so
#      tbmap.py maps a JIT sample's host address to the guest pc of its TB.
#      No code change and no -perfmap (Android has no /tmp, and the launcher
#      passes no extra argv).
# APK: dispatch/builds/a593d8eb85.apk, the build slowdown462 profiled GTA with
# (alley: gta.data, open world: gta-open.data). include/exec/translation-block.h
# is unchanged from a593d8eb85 to c91697f116.
#
# Device grant (hostops, 2026-09-27): Thor only, GTA only, under 10 min per
# session. DEADLINE_S (default 500) is counted from the moment the Thor is
# free; steps 4 and 6 are skipped rather than run past it.
set -u
DELAY=${1:-60}
DEV=thor S=bdc158a5 MIN_BATT=${MIN_BATT:-30}
PKG=com.jreinach.hakux.debug
D=/home/justin/hakux-work/dispatch
OUT=${OUT:-/home/justin/hakux-work/perf/2026-09-27-gta482/s1}
APK=$D/builds/a593d8eb85.apk
ISO=54540082-Grand_Theft_Auto_San_Andreas.xiso.iso
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../testing" && pwd)"
HOLDSH="$HERE/jobs/hold.sh"
TAG=lane.gta482
LEASE=/tmp/hakux-device-lease.$DEV
SOAK_S=${SOAK_S:-450}
DEADLINE_S=${DEADLINE_S:-500}
mkdir -p "$OUT"
a() { timeout "${T:-120}" adb -s $S "$@"; }
say() { echo "CAP $(date -u +%H:%M:%S) $*"; }
running_dev() { grep -lx $DEV "$D"/running/*.owner 2>/dev/null; }
T0=""
left() { echo $(( DEADLINE_S - ($(date +%s) - T0) )); }

[ -f "$APK" ] || { say "no apk $APK"; exit 1; }
# The hold stops the dispatcher's NEXT claim; a request already running on the
# Thor finishes untouched (nothing below touches the device until running/ is
# empty of it). hold.sh's own header documents this as the way to get a gap.
# A hold this lane already took (to wait out a running request across tool
# calls) is used as it is; anyone else's is a refusal.
w=$(bash "$HOLDSH" who $DEV)
case "$w" in
*" by $TAG -- "*) say "hold already ours" ;;
held:*) say "hold/$DEV held by someone else: $w; not waiting"; exit 3 ;;
*) bash "$HOLDSH" take $DEV $TAG \
    "lane.gta482 #482: held Thor session (hostops grant 09-27), GTA SA open world: 2 x 25 s simpleperf + code-buffer dump, apk a593d8eb85, <10 min of device time; waits for the running request first; capture_gta.sh releases on every exit" \
    || { say "could not take hold/$DEV: $(bash "$HOLDSH" who $DEV)"; exit 3; }
   say "hold taken" ;;
esac

LEASE_PID="" SOAK_PID="" USED=0
cleanup() {
    rc=$?
    if [ "$USED" = 1 ]; then
    [ -n "$SOAK_PID" ] && kill "$SOAK_PID" 2>/dev/null && wait "$SOAK_PID" 2>/dev/null
    if ! grep -q '"perf_restored": true' "$OUT/perf_regimen.json" 2>/dev/null; then
        ( . "$HERE/devices.sh"; read -r _ _ pr fr <<<"$(device_perf_values $S)"
          [ -n "$pr" ] && SERIAL=$S device_perf_set "$pr" "$fr" >/dev/null && say "REST set by cleanup" )
    fi
    a shell am force-stop $PKG >/dev/null 2>&1
    a shell "run-as $PKG rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin" >/dev/null 2>&1
    a shell "rm -f /data/local/tmp/gta482-on.data /data/local/tmp/gta482-off.data" >/dev/null 2>&1
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
a shell "rm -f /data/local/tmp/gta482-on.data /data/local/tmp/gta482-off.data"
# The display must be on. soak_title.sh sends KEYCODE_WAKEUP and checks
# nothing; in session 1 (18:37Z) the Thor stayed dark, every frame was black
# and the game stopped flipping. Wake, dismiss the keyguard, read it back.
a shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
a shell wm dismiss-keyguard >/dev/null 2>&1
sleep 2
wk=$(a shell dumpsys power | tr -d '\r' | grep -o 'mWakefulness=[A-Za-z]*' | head -1)
a exec-out screencap -p > "$OUT/shot0.png" 2>/dev/null
s0=$(stat -c %s "$OUT/shot0.png" 2>/dev/null || echo 0)
say "display: $wk, screencap $s0 bytes"
[ "$wk" = mWakefulness=Awake ] && [ "$s0" -gt 12000 ] || { say "the display is not on; refusing"; exit 7; }
cp "$HERE/titles/routes/gta-sa.route" "$OUT/route.txt" || { say "no route gta-sa"; exit 5; }

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
shot() { a exec-out screencap -p > "$OUT/$1.png" 2>/dev/null; say "shot $1 $(stat -c %s "$OUT/$1.png" 2>/dev/null)"; }
record() {  # <name> <extra flags>
    local rec
    rec=$(T=90 a shell "simpleperf record --app $PKG -e cpu-clock $2 --call-graph dwarf,8192 --duration 25 -f 1000 -o /data/local/tmp/gta482-$1.data" 2>&1)
    echo "$rec" | grep -v 'symbol table' | tail -8 | sed "s/^/CAP rec-$1: /"
    echo "$rec" | grep -q "Recorded for"
}

ok_on=0 ok_off=0 ok_dump=0
if wait_for "ROUTE .* mark gameplay" 1 420 && wait_for "ROUTE .* shot gameplay" 1 20; then
    sleep 2
    g=$(ls -t "$OUT"/route-frames/*-gameplay.png 2>/dev/null | head -1)
    gs=$(stat -c %s "$g" 2>/dev/null || echo 0)
    say "gameplay frame $g $gs bytes"
    # session 1: every frame 10,899 B (all black), and the game stopped flipping
    [ "$gs" -gt 100000 ] || { say "the gameplay frame is black: not the open world; stopping"; exit 8; }
    sleep "$DELAY"
    a shell log -t hakuX-route "'prof start'" >/dev/null
    say "prof start (left $(left) s)"
    shot shot1
    record on "" && ok_on=1
    a shell log -t hakuX-route "'prof on end'" >/dev/null
    shot shot2
    if [ "$(left)" -gt 150 ]; then
        for attempt in 1 2; do
            record off "--trace-offcpu" && { ok_off=1; break; }
            say "off-CPU record attempt $attempt failed"; sleep 2
            [ "$(left)" -gt 130 ] || break
        done
        a shell log -t hakuX-route "'prof off end'" >/dev/null
        shot shot3
    else
        say "skipping the off-CPU record: $(left) s left"
    fi
    if [ "$(left)" -gt 70 ]; then
        PID=$(a shell "pidof $PKG:xemu" | tr -d '\r' | awk '{print $1}')
        say "xemu pid $PID"
        if [ -n "$PID" ]; then
            a exec-out "run-as $PKG cat /proc/$PID/maps" > "$OUT/maps.txt"
            # executable, private or memfd, not file-backed, >= 1 MiB
            # code: executable anon/memfd >= 1 MiB (the TCG buffer); ram: a
            # writable non-executable anon/memfd mapping of exactly 64 or 128
            # MiB (the guest's RAM), dumped after the code if time allows
            python3 - "$OUT/maps.txt" > "$OUT/regions.txt" <<'PYMAPS'
import sys
code, ram = [], []
for l in open(sys.argv[1]):
    f = l.split()
    if len(f) < 5:
        continue
    path = f[5] if len(f) > 5 else ''
    # the TCG buffer and the guest RAM are unnamed; /memfd:jit-cache and
    # /memfd:jit-zygote-cache are ART's (session 1 dumped one of those)
    if path and not path.startswith('[anon'):
        continue
    lo, hi = (int(x, 16) for x in f[0].split('-'))
    if 'x' in f[1] and hi - lo >= 1 << 20:
        code.append(f"codebuf {lo:x} {hi:x} {path}")
    elif 'w' in f[1] and 'x' not in f[1] and hi - lo in (64 << 20, 128 << 20):
        ram.append(f"ram {lo:x} {hi:x} {path}")
print("\n".join(code + ram[:2]))
PYMAPS
            say "regions: $(tr '\n' ';' < "$OUT/regions.txt")"
            while read -r kind lo hi _; do
                [ "$kind" = ram ] && [ "$(left)" -lt 45 ] && { say "skipping $kind $lo: $(left) s left"; continue; }
                sk=$(( 0x$lo / 4096 )); ct=$(( (0x$hi - 0x$lo) / 4096 ))
                # < /dev/null: adb reads stdin, and in session 1 it ate the
                # rest of regions.txt, so only the first region was dumped
                T=180 a exec-out "run-as $PKG sh -c 'dd if=/proc/$PID/mem bs=4096 skip=$sk count=$ct 2>/dev/null | gzip -1'" > "$OUT/$kind-$lo.bin.gz" < /dev/null
                n=$(gzip -dc "$OUT/$kind-$lo.bin.gz" 2>/dev/null | wc -c)
                say "dump $kind $lo: $n of $(( ct * 4096 )) bytes (left $(left) s)"
                [ "$kind" = codebuf ] && [ "$n" = $(( ct * 4096 )) ] && ok_dump=1
            done < "$OUT/regions.txt"
        fi
    else
        say "skipping the code-buffer dump: $(left) s left"
    fi
else
    say "anchor mark gameplay never came"
fi
kill $SOAK_PID 2>/dev/null; wait $SOAK_PID 2>/dev/null; SOAK_PID=""
for n in on off; do
    ( cd "$OUT" && T=300 a pull /data/local/tmp/gta482-$n.data ./rec-$n.data 2>&1 | tail -1 )
done
[ -f "$OUT/rec-on.data" ] || ok_on=0
[ -f "$OUT/rec-off.data" ] || ok_off=0
say "on=$ok_on off=$ok_off dump=$ok_dump done"
[ $ok_on = 1 ]
