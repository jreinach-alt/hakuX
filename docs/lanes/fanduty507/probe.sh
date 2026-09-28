#!/usr/bin/env bash
# lane.fanduty507 held probe (#507): does duty 50000 hold for 5 minutes under
# fan_mode 6 with NO re-write, and what does the node hold after fan_mode goes
# back to REST (4)? Run only under `jobs/hold.sh take <dev> lane.fanduty507`
# with nothing of the dispatcher's running on the device.
#   probe.sh <serial> [seconds=300] [every=15]
set -u
S="${1:?serial}"; SECS="${2:-300}"; EVERY="${3:-15}"
N=/sys/class/gpio5_pwm2
a() { timeout 20 adb -s "$S" shell "$@" | tr -d '\r'; }
rd() { a "echo \"mode=\$(settings get system fan_mode) duty=\$(cat $N/duty) period=\$(cat $N/period) speed=\$(cat $N/speed 2>/dev/null) bat=\$(cat /sys/class/power_supply/battery/capacity) xo=\$(for z in /sys/class/thermal/thermal_zone*; do [ \"\$(cat \$z/type)\" = xo-therm ] && cat \$z/temp; done)\""; }
echo "before  $(date -u +%T) $(rd)"
a "settings put system fan_mode 6; sleep 1; echo 50000 > $N/duty"
t0=$(date +%s)
echo "set     $(date -u +%T) +0s $(rd)"
while :; do
    sleep "$EVERY"; t=$(( $(date +%s) - t0 ))
    echo "hold    $(date -u +%T) +${t}s $(rd)"
    [ "$t" -ge "$SECS" ] && break
done
a "settings put system fan_mode 4"
for w in 1 3 10 30; do
    sleep "$w"
    echo "rest    $(date -u +%T) +${w}s-step $(rd)"
done
