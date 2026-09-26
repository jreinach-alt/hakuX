#!/usr/bin/env bash
#
#   held_session.sh <label> <outdir>
#
# One HELD session on one handheld, under 30 minutes:
#   1. idle probe: step performance_mode and fan_mode through their values
#      with no title running and read what moves (GPU floor, fan PWM duty and
#      tach, CPU clocks, temperatures);
#   2. the pilot: Blinx hands-off, arms REST, MAX, REST through this branch's
#      soak_title.sh (PERF_REGIMEN=rest|max), with a sampler reading the same
#      nodes every 10 s under that fixed load.
# REST is restored by a trap on every exit. The caller owns the hold file;
# this refuses to start without it, below 50% battery, or while the
# dispatcher still has a request running on the device.
set -u
LABEL="$1"; OUT="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
TESTING="$(cd "$HERE/../../testing" && pwd)"
D="${DISPATCH_DIR:-$HOME/hakux-work/dispatch}"
. "$TESTING/devices.sh"
case "$LABEL" in thor) S=bdc158a5 ;; nova) S=ee317437 ;; *) echo "label?"; exit 2 ;; esac
device_env "$S" >/dev/null
read -r PMAX FMAX PREST FREST <<<"$(device_perf_values "$S")"
ISO="$DEVICE_ISO_ROOT/${PILOT_TITLE:-4D530013-Blinx_The_Time_Sweeper.xiso.iso}"
ARM_S="${ARM_S:-250}"
# The dispatcher's spec, so an arm logs what a queued soak would.
LOGCAT_SPEC="${LOGCAT_SPEC:-$(sed -n 's/^LOGCAT_SPEC="\${LOGCAT_SPEC_OVERRIDE:-\(.*\)}"$/\1/p' "$TESTING/dispatcher.sh")}"
mkdir -p "$OUT"
T0=$(date +%s)
log() { echo "[$(date +%H:%M:%S) +$(( $(date +%s) - T0 ))s] $*"; }
a() { timeout 30 adb -s "$S" "$@"; }

[ -f "$D/hold/$LABEL" ] || { log "REFUSED: no hold file $D/hold/$LABEL"; exit 2; }
for f in "$D"/running/*.owner; do
    [ -f "$f" ] && [ "$(cat "$f")" = "$LABEL" ] && { log "REFUSED: $f still runs on $LABEL"; exit 2; }
done
batt() { a shell dumpsys battery | tr -d '\r' | sed -n 's/^ *level: //p'; }
b=$(batt); log "battery $b%"
[ "${b:-0}" -ge 50 ] || { log "REFUSED: battery $b% < 50%"; exit 2; }

rest() {
    local got; got=$(device_perf_set "$PREST" "$FREST")
    log "REST restored: read back [$got] (want [$PREST $FREST])"
}
trap 'a shell am force-stop "$PKG" >/dev/null 2>&1; rest; a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1' EXIT
trap 'exit 143' TERM; trap 'exit 130' INT

N='/sys/class/kgsl/kgsl-3d0'
C='/sys/devices/system/cpu/cpufreq'
F='/sys/class/gpio5_pwm2'
snap() {   # one line of every readout
    a shell "echo \"t=\$(date +%s) set=\$(settings get system performance_mode)/\$(settings get system fan_mode) gpu_min_mhz=\$(cat $N/min_clock_mhz) gpu_min_pl=\$(cat $N/min_pwrlevel) gpuclk=\$(cat $N/gpuclk) busy=\$(cat $N/gpu_busy_percentage 2>/dev/null|tr -d ' %') c0=\$(cat $C/policy0/scaling_cur_freq) c3=\$(cat $C/policy3/scaling_cur_freq) c7=\$(cat $C/policy7/scaling_cur_freq) fan_duty=\$(cat $F/duty) fan_state=\$(cat $F/state) fan_rpm=\$(cat $F/speed) gpuss0=\$(cat /sys/class/thermal/thermal_zone63/temp 2>/dev/null) batt_t=\$(cat /sys/class/power_supply/battery/temp 2>/dev/null)\"" 2>&1 | tr -d '\r' | tail -1
}

{
log "device $LABEL $S, REST=$PREST/$FREST MAX=$PMAX/$FMAX, iso $ISO"
a shell dumpsys package "$PKG" | tr -d '\r' | grep -E "versionName|lastUpdateTime" | head -2
echo "env_pref: $(tr '\n' ' ' < "$D/.env_pref.$LABEL" 2>/dev/null)"
a shell am force-stop "$PKG" >/dev/null 2>&1
a shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1

# 1. Idle probe. 8 s settle per step: the fan ramps, the GPU floor is a write.
# SKIP_IDLE=1 for a follow-up session that only runs arms.
if [ "${SKIP_IDLE:-0}" = 1 ]; then log "== idle probe skipped"; exit 0; fi
log "== idle probe"
step() { log "set perf=$1 fan=$2 -> [$(device_perf_set "$1" "$2")]"; sleep "${SETTLE_S:-8}"; log "  $(snap)"; }
log "  baseline $(snap)"
step "$PREST" "$FREST"
for p in 1 2; do step "$p" "$FREST"; done
step "$PREST" "$FREST"
for f in 0 1 2 3 5; do step "$PREST" "$f"; done
step "$PREST" "$FREST"
step "$PMAX" "$FMAX"
step "$PREST" "$FREST"
} 2>&1 | tee "$OUT/idle.log"

# 2. The pilot arms.
sampler() {   # <file>: every 10 s until killed
    while :; do snap >> "$1"; sleep 10; done
}
arm_n=0
for arm in ${ARMS:-rest max rest}; do
    arm_n=$((arm_n+1))
    el=$(( $(date +%s) - T0 ))
    # 30 min hold: an arm is ~5 min with boot and teardown.
    if [ "$el" -gt $(( ${HOLD_BUDGET_S:-1680} - ARM_S - 60 )) ]; then
        log "SKIP arm $arm_n ($arm): ${el}s elapsed, no room in the hold" | tee -a "$OUT/session.log"; break
    fi
    b=$(batt)
    if [ "${b:-0}" -lt 32 ]; then log "STOP: battery $b%" | tee -a "$OUT/session.log"; break; fi
    ad="$OUT/arm$arm_n-$arm"; mkdir -p "$ad"
    log "== arm $arm_n $arm (battery $b%)" | tee -a "$OUT/session.log"
    sampler "$ad/samples.txt" & SP=$!
    SERIAL="$S" CAPTURE_LOG="$ad/logcat.txt" PERF_REGIMEN="$arm" \
        HAKUX_DEVICE_LEASE="$OUT/lease" LOGCAT_SPEC="${LOGCAT_SPEC:-}" \
        bash "$TESTING/soak_title.sh" "$ISO" "$ARM_S" > "$ad/run.log" 2>&1
    rc=$?
    kill "$SP" 2>/dev/null; wait "$SP" 2>/dev/null
    log "   arm $arm_n $arm rc=$rc $(grep '^PERF:' "$ad/run.log" | tr '\n' ' ')" | tee -a "$OUT/session.log"
    sleep 5
done
log "session done, $(( $(date +%s) - T0 ))s, battery $(batt)%" | tee -a "$OUT/session.log"
