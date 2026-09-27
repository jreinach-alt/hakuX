#!/system/bin/sh
# lane.gta482 (#482): the HOST's state, read on the device. Read-only.
#
#   sh hoststate.sh <package> [light|full]
#
# Why: slowdown462's open-world record (gta-open.data, 4.8 fps) has every
# hakuX thread on cpu0-2 only, and both fast records (gta.data, s4) have the
# vCPU on cpu7 and the rest on cpu3-6 (cpuof.py). So the slow regime may be a
# host state: a cpuset move (the app no longer top-app), or the big cores
# isolated or capped (thermal). This read tells them apart:
#   online/offline/isolated, core_ctl     cores taken away (thermal, core_ctl)
#   cpuN cur/max                          a frequency cap
#   cpuset/<group> cpus                   what each group may run on
#   the emulator's cpuset, Cpus_allowed   which group hakuX is in
#   per-thread stat + schedstat           the CPU each thread last ran on, and
#                                         its run time and RUN-QUEUE WAIT (ns):
#                                         waiting for a CPU is not blocking
#   thermal zones, cooling devices        how hot, and what is throttled
# full adds the slow reads: process state, power, thermalservice, battery.
PKG=$1
MODE=${2:-light}
echo "== hoststate $MODE t=$(date +%H:%M:%S) up=$(cut -d' ' -f1 /proc/uptime)"
C=/sys/devices/system/cpu
echo "online=$(cat $C/online 2>/dev/null) offline=$(cat $C/offline 2>/dev/null) isolated=$(cat $C/isolated 2>/dev/null)"
for c in 0 1 2 3 4 5 6 7; do
    d=$C/cpu$c
    echo "cpu$c online=$(cat $d/online 2>/dev/null) cur=$(cat $d/cpufreq/scaling_cur_freq 2>/dev/null) max=$(cat $d/cpufreq/scaling_max_freq 2>/dev/null) hwmax=$(cat $d/cpufreq/cpuinfo_max_freq 2>/dev/null) gov=$(cat $d/cpufreq/scaling_governor 2>/dev/null) core_ctl[active=$(cat $d/core_ctl/active_cpus 2>/dev/null) min=$(cat $d/core_ctl/min_cpus 2>/dev/null) max=$(cat $d/core_ctl/max_cpus 2>/dev/null) need=$(cat $d/core_ctl/need_cpus 2>/dev/null)]"
done
for s in top-app foreground background restricted system-background camera-daemon; do
    [ -d /dev/cpuset/$s ] && echo "cpuset/$s cpus=$(cat /dev/cpuset/$s/cpus 2>/dev/null)"
done
PID=$(pidof "$PKG:xemu" 2>/dev/null | cut -d' ' -f1)
[ -n "$PID" ] || PID=$(pidof "$PKG" 2>/dev/null | cut -d' ' -f1)
echo "pid=$PID"
if [ -n "$PID" ]; then
    run-as "$PKG" sh -c "
        echo proc cpuset=\$(cat /proc/$PID/cpuset 2>/dev/null) oom_score_adj=\$(cat /proc/$PID/oom_score_adj 2>/dev/null) \$(grep Cpus_allowed_list /proc/$PID/status 2>/dev/null | tr '\t' ' ')
        for t in /proc/$PID/task/*; do
            echo task \${t##*/} cpuset=\$(cat \$t/cpuset 2>/dev/null) schedstat=\$(cat \$t/schedstat 2>/dev/null | tr ' ' ,) stat=\$(cat \$t/stat 2>/dev/null)
        done
    " 2>/dev/null
fi
for z in /sys/class/thermal/thermal_zone*; do
    echo "tz ${z##*zone} $(cat $z/type 2>/dev/null) $(cat $z/temp 2>/dev/null)"
done 2>/dev/null
for z in /sys/class/thermal/cooling_device*; do
    s=$(cat $z/cur_state 2>/dev/null)
    [ -n "$s" ] && [ "$s" != 0 ] && echo "cool ${z##*device} $(cat $z/type 2>/dev/null) cur=$s max=$(cat $z/max_state 2>/dev/null)"
done 2>/dev/null
if [ "$MODE" = full ]; then
    echo "-- settings performance_mode=$(settings get system performance_mode) fan_mode=$(settings get system fan_mode) low_power=$(settings get global low_power) screen_off_timeout=$(settings get system screen_off_timeout)"
    echo "-- battery"; dumpsys battery | grep -E 'level|temperature|status|AC powered|USB powered'
    echo "-- power"; dumpsys power | grep -E 'mWakefulness=|mLastUserActivityTime|mUserActivitySummary|mLowPowerModeEnabled|mDeviceIdleMode|Display Power: state' | head -12
    echo "-- activity"; dumpsys activity processes "$PKG" 2>/dev/null | grep -E 'curProcState|curSchedGroup|setSchedGroup|curAdj|hasTopUi|\*APP\*|mTopApp|ResumedActivity|topResumed' | head -30
    echo "-- top"; dumpsys activity activities 2>/dev/null | grep -E 'topResumedActivity|ResumedActivity|mFocusedApp' | head -12
    echo "-- thermalservice"; dumpsys thermalservice 2>/dev/null | head -60
    echo "-- core_ctl global_state"; cat $C/cpu0/core_ctl/global_state 2>/dev/null | head -80
    echo "-- walt"; for f in /proc/sys/walt/sched_*cpus* /sys/devices/system/cpu/cpu_capacity; do [ -f $f ] && echo "$f=$(cat $f 2>/dev/null)"; done
fi
echo "== end"
