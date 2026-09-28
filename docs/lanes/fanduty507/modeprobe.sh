#!/usr/bin/env bash
#
#   modeprobe.sh <serial> <settle_s> <reads> <every_s> <name=mode[:speed]>...
#
# The idle PWM duty of each fan option a handheld's UI offers (#507). For
# each option: `settings put system fan_mode <mode>` (and, for Customize,
# `fan_speed <speed>` first, as the Quick Settings slider writes it), wait
# <settle_s>, then <reads> reads of the modes, the fan node (duty, period,
# speed) and xo-therm, <every_s> apart. The fan node is only READ. The prior
# fan_mode and fan_speed are put back on every exit (EXIT trap), and read
# back.
#
# Run under `jobs/hold.sh take <dev> lane.<name>` on an idle handheld, with
# no request running on it.
set -u
SERIAL="$1"; SETTLE="$2"; READS="$3"; EVERY="$4"; shift 4
a() { timeout 20 adb -s "$SERIAL" "$@"; }
PRIOR=$(a shell settings get system fan_mode | tr -d '\r')
PRIOR_SPEED=$(a shell settings get system fan_speed | tr -d '\r')
restore() {
    if [ "$PRIOR_SPEED" = null ]; then
        a shell settings delete system fan_speed >/dev/null 2>&1
    else
        a shell settings put system fan_speed "$PRIOR_SPEED" >/dev/null 2>&1
    fi
    a shell settings put system fan_mode "$PRIOR" >/dev/null 2>&1
    sleep 5
    echo "restored: $(read_once) (prior fan_mode $PRIOR fan_speed $PRIOR_SPEED)"
}
read_once() {
    a shell 'echo "perf=$(settings get system performance_mode) fan_mode=$(settings get system fan_mode) fan_speed=$(settings get system fan_speed) duty=$(cat /sys/class/gpio5_pwm2/duty) period=$(cat /sys/class/gpio5_pwm2/period) speed=$(cat /sys/class/gpio5_pwm2/speed 2>/dev/null) battery=$(cat /sys/class/power_supply/battery/capacity)"; for z in /sys/class/thermal/thermal_zone*; do [ "$(cat $z/type)" = xo-therm ] && echo "xo=$(cat $z/temp)"; done' \
        | tr -d '\r' | paste -sd' ' -
}
trap restore EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
echo "device $SERIAL, prior fan_mode $PRIOR fan_speed $PRIOR_SPEED, $(date -u +%FT%TZ)"
echo "before: $(read_once)"
for opt in "$@"; do
    name="${opt%%=*}"; rest="${opt#*=}"; mode="${rest%%:*}"
    if [ "$rest" != "$mode" ]; then
        a shell settings put system fan_speed "${rest#*:}" >/dev/null 2>&1
    fi
    a shell settings put system fan_mode "$mode" >/dev/null 2>&1
    sleep "$SETTLE"
    for i in $(seq "$READS"); do
        echo "$name ($rest) +$((SETTLE + (i - 1) * EVERY))s: $(read_once)"
        [ "$i" -lt "$READS" ] && sleep "$EVERY"
    done
done
