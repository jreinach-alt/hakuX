#!/usr/bin/env bash
# lane.fanduty507 proof soak: 3 min, FAN_DUTY=50000, from this worktree's
# soak_title.sh, under the lane's hold on the Nova.
cd /home/justin/hakux-work/wt/fanduty507 || exit 2
P=$PWD/.proof/r1
mkdir -p "$P"
env SERIAL=ee317437 HAKUX_DEVICE_LEASE="$PWD/.proof/lease" CAPTURE_LOG="$P/logcat.txt" \
    PERF_REGIMEN=rest FAN_DUTY=50000 \
    timeout 480 bash docs/testing/soak_title.sh \
    /storage/E6C6-D7AA/Games/XBox/4D530013-Blinx_The_Time_Sweeper.xiso.iso 180 > "$P/run.log" 2>&1
echo "soak rc=$?"
grep -E '^(PERF|FAN|THERMAL|COOLDOWN|held|guest|soak|fan-duty)' "$P/run.log"
sleep 5
timeout 20 adb -s ee317437 shell 'echo "after +5s: fan_mode=$(settings get system fan_mode) performance_mode=$(settings get system performance_mode) duty=$(cat /sys/class/gpio5_pwm2/duty) battery=$(cat /sys/class/power_supply/battery/capacity)"' | tr -d '\r'
