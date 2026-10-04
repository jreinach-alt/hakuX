#!/usr/bin/env bash
# Read-only: the nodes and properties a performance/fan mode could move.
# SERIALS="bdc158a5" bash probe_nodes.sh
for s in ${SERIALS:-bdc158a5 ee317437}; do
    echo "== $s"
    timeout 40 adb -s "$s" shell '
echo "-- props"; getprop | grep -iE "perf|fan|thermal|gear|odin|ayn|retroid|cool" | head -40
echo "-- cpufreq"; for p in /sys/devices/system/cpu/cpufreq/policy*; do echo "$p cur=$(cat $p/scaling_cur_freq) min=$(cat $p/scaling_min_freq) max=$(cat $p/scaling_max_freq) gov=$(cat $p/scaling_governor)"; done
echo "-- kgsl"; for f in min_pwrlevel max_pwrlevel default_pwrlevel thermal_pwrlevel gpuclk max_gpuclk min_clock_mhz max_clock_mhz devfreq/governor devfreq/min_freq devfreq/max_freq devfreq/cur_freq; do echo "$f=$(cat /sys/class/kgsl/kgsl-3d0/$f 2>&1)"; done
echo "-- fan-ish nodes"; ls -d /sys/class/hwmon/* /sys/devices/platform/*fan* /sys/class/thermal/cooling_device* 2>/dev/null | head -60
for h in /sys/class/hwmon/*; do echo "$h name=$(cat $h/name 2>/dev/null) $(ls $h | tr "\n" " ")"; done
for c in /sys/class/thermal/cooling_device*; do t=$(cat $c/type 2>/dev/null); case "$t" in *fan*|*Fan*|*FAN*|*pwm*) echo "$c type=$t cur=$(cat $c/cur_state) max=$(cat $c/max_state)";; esac; done
' 2>&1 | tr -d '\r'
done
