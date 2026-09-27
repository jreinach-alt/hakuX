#!/usr/bin/env bash
# Read-only: every fan node the OEM settings APKs name, plus the GPU floor
# and the two settings, in one line per node. SERIALS="bdc158a5" probe_fan.sh
for s in ${SERIALS:-bdc158a5 ee317437}; do
    echo "== $s $(date +%H:%M:%S)"
    timeout 30 adb -s "$s" shell '
echo "settings performance_mode=$(settings get system performance_mode) fan_mode=$(settings get system fan_mode)"
for f in /sys/devices/platform/odm/odm:mid_custom/fan /sys/devices/platform/odm/odm:mid_custom/fan_pwm \
         /sys/devices/virtual/fan_info/fan_info_data/duty /sys/devices/virtual/fan_info/fan_info_data/state \
         /sys/devices/virtual/fan_info/fan_info_data/speed \
         /sys/class/gpio5_pwm2/duty /sys/class/gpio5_pwm2/state /sys/class/gpio5_pwm2/speed \
         /sys/class/kgsl/kgsl-3d0/min_clock_mhz /sys/class/kgsl/kgsl-3d0/min_pwrlevel /sys/class/kgsl/kgsl-3d0/gpuclk \
         /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq /sys/devices/system/cpu/cpufreq/policy7/scaling_cur_freq \
         /sys/devices/system/cpu/cpufreq/policy7/scaling_max_freq; do
    echo "$f=$(cat $f 2>&1 | head -1)"
done
ls /sys/devices/platform/odm/odm:mid_custom/ /sys/devices/virtual/fan_info/fan_info_data/ 2>&1 | tr "\n" " "; echo
getprop | grep -iE "fan|perf.*mode|performance"
echo "battery $(dumpsys battery | grep level)"
' 2>&1 | tr -d '\r'
done
