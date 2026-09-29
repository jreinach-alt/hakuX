#!/usr/bin/env bash
#
#   proof-run.sh <serial> <out dir> <FAN_MODE> <PERF_REGIMEN> <iso path> [seconds]
#
# lane.fanduty507 proof soak: this worktree's soak_title.sh (the dispatcher's
# snapshot does not have FAN_MODE until the fold), run by hand under the
# lane's hold on an idle handheld. Prints the soak's fan lines, then the
# device's fan settings 5 s after it ended.
cd /home/justin/hakux-work/wt/fanduty507 || exit 2
SERIAL="$1"; P="$2"; FM="$3"; REG="$4"; ISO="$5"; SECS="${6:-180}"
mkdir -p "$P"
env SERIAL="$SERIAL" HAKUX_DEVICE_LEASE="$PWD/.proof/lease" CAPTURE_LOG="$P/logcat.txt" \
    PERF_REGIMEN="$REG" FAN_MODE="$FM" \
    timeout $((SECS + 480)) bash docs/testing/soak_title.sh "$ISO" "$SECS" > "$P/run.log" 2>&1
echo "soak rc=$?"
grep -E '^(PERF|FAN|THERMAL|COOLDOWN|held|guest|soak|fan-mode)' "$P/run.log"
sleep 5
timeout 20 adb -s "$SERIAL" shell 'echo "after +5s: performance_mode=$(settings get system performance_mode) fan_mode=$(settings get system fan_mode) fan_speed=$(settings get system fan_speed) duty=$(cat /sys/class/gpio5_pwm2/duty) battery=$(cat /sys/class/power_supply/battery/capacity)"' | tr -d '\r'
