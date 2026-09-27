#!/usr/bin/env bash
# Read-only: cooling device types/states, fan-ish thermal zones, the OEM apps.
for s in ${SERIALS:-bdc158a5 ee317437}; do
    echo "== $s"
    timeout 40 adb -s "$s" shell '
for c in /sys/class/thermal/cooling_device*; do echo "$(basename $c) $(cat $c/type) $(cat $c/cur_state)/$(cat $c/max_state)"; done | grep -viE "^cooling_device[0-9]+ (thermal-cpufreq|cpu-isolate|cpu-pause)"
echo "-- zones"; for z in /sys/class/thermal/thermal_zone*; do echo "$(basename $z) $(cat $z/type) $(cat $z/temp)"; done | grep -iE "fan|skin|sys-therm|battery|gpuss-0|cpu-1-0-0 " | head
echo "-- pkgs"; pm list packages | grep -iE "odin|ayn|retroid|\.rp\.|gameassist|settings"
echo "-- fan dirs"; ls -d /sys/devices/platform/*fan* /sys/devices/platform/soc/*fan* /sys/bus/platform/devices/*fan* /sys/class/pwm/* 2>&1 | head
' 2>&1 | tr -d '\r'
done
