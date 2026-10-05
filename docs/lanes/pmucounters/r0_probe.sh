#!/bin/bash
# lane.pmucounters (#433) R0: can the hardware counters be read on this
# handheld at all, from which context, and do the control kernels read as
# expected? About 90 s of device time. It launches NO title and touches no
# pref, setting or file outside /data/local/tmp/pmu433 and the debug app's
# files/pmu433 dir.
#
#   DEV=thor|nova bash docs/lanes/pmucounters/r0_probe.sh [outdir]
#
# RUN IT UNDER A HOLD YOU HOLD, ON AN IDLE DEVICE (hold.sh take ... &&
# hold.sh wait-idle ...). The control kernels load a core fully for ~6 s per
# pass; they must not run beside someone's measurement. It does not take or
# release a hold itself, so that whoever already holds the device (lane.local's
# Thor cold slot, a pathfind gap) can run it inside their hold.
#
# It does NOT set security.perf_harden. It records it. If HARDEN0=1 is passed
# (hostops's leave only; a reboot resets it), it sets 0 first and reads back.
#
# Steps, each logged with its exit and output:
#   1. getprop security.perf_harden, /proc/sys/kernel/perf_event_paranoid,
#      uptime, the event_source PMUs (name, type, cpus) and each CPU's MIDR
#      part (/proc/cpuinfo), battery, thermal xo.
#   2. simpleperf list hw / raw (which events the kernel says it can count).
#   3. pmuprobe (the [pmu433] hook built standalone) as shell, pinned to the
#      X3 (cpu7), then the A715 (cpu3) and the A510 (cpu0): open result per
#      PMU, then the eight control kernels, then 3 s of slice lines.
#   4. the same pinned to cpu7 under `run-as` (the debug app's uid and SELinux
#      context; closer to the in-process hook's than shell's).
#   5. simpleperf stat with hardware events on pmuprobe (as shell, cpu7): the
#      same counts by simpleperf's path, for agreement with step 3.
#   6. simpleperf record -e cpu-cycles and -e raw-l1d-cache-refill on
#      pmuprobe (5 s): can hardware events be SAMPLED (R2's attribution)?
set -u
DEV=${DEV:-thor}
case $DEV in nova) S=ee317437 ;; thor) S=bdc158a5 ;; *) echo "DEV nova|thor"; exit 2 ;; esac
PKG=com.jreinach.hakux.debug
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT=${1:-/home/justin/hakux-work/perf/$(date +%F)-pmucounters/r0-$DEV}
mkdir -p "$OUT"
LOG=$OUT/r0.log
T=/data/local/tmp/pmu433
a() { adb -s $S "$@" < /dev/null; }
say() { echo "== $*" | tee -a "$LOG"; }
run() {   # run <label> <adb shell command>
    say "$1: $2"
    a shell "$2" > "$OUT/$1.txt" 2>&1
    local rc=$?
    echo "rc=$rc" >> "$OUT/$1.txt"
    tail -n 60 "$OUT/$1.txt" >> "$LOG"
}

bash "$HERE/build_probe.sh" "$OUT/pmuprobe" >> "$LOG" 2>&1 \
    || { say "build failed"; exit 1; }
a get-state > /dev/null 2>&1 || { say "device $S not reachable"; exit 1; }
if a shell "ps -A -o NAME" | tr -d '\r' | grep -qx "$PKG:xemu"; then
    say "the emulator is running on $DEV: refusing (run on an idle device)"
    exit 1
fi
if [ "${HARDEN0:-0}" = 1 ]; then
    say "HARDEN0=1: setprop security.perf_harden 0"
    a shell setprop security.perf_harden 0
fi

run env 'getprop security.perf_harden; cat /proc/sys/kernel/perf_event_paranoid;
  cat /proc/uptime; getenforce;
  for d in /sys/bus/event_source/devices/*; do
    echo "$d type=$(cat $d/type 2>&1) cpus=$(cat $d/cpus 2>/dev/null) cpumask=$(cat $d/cpumask 2>/dev/null)";
  done;
  grep -E "^processor|^CPU part" /proc/cpuinfo | paste - -;
  dumpsys battery | grep -E "level|temperature";
  for z in /sys/class/thermal/thermal_zone*; do
    case $(cat $z/type) in *xo*|*cpu-1-3*|cpuss*) echo "$(cat $z/type) $(cat $z/temp)";; esac;
  done'
run list_hw 'simpleperf list hw'
run list_raw 'simpleperf list raw'

a shell "rm -rf $T; mkdir -p $T"
a push "$OUT/pmuprobe" $T/pmuprobe > /dev/null && a shell "chmod 755 $T/pmuprobe"
run probe_shell_cpu7 "taskset 80 $T/pmuprobe 3"
run probe_shell_cpu3 "taskset 08 $T/pmuprobe 3"
run probe_shell_cpu0 "taskset 01 $T/pmuprobe 3"
# run-as: copy into the app's own files (an app may not exec shell files on
# every release), then run from there; if that exec is refused, try /data/local/tmp.
run probe_runas_cpu7 "run-as $PKG sh -c 'mkdir -p files/pmu433 && cp $T/pmuprobe files/pmu433/ && chmod 700 files/pmu433/pmuprobe && taskset 80 files/pmu433/pmuprobe 3'"
grep -q '\[pmu433\] open pmu' "$OUT/probe_runas_cpu7.txt" \
    || run probe_runas_tmp_cpu7 "run-as $PKG taskset 80 $T/pmuprobe 3"
run stat_basic_cpu7 "taskset 80 simpleperf stat -e cpu-cycles,instructions $T/pmuprobe 1"
run stat_cpu7 "taskset 80 simpleperf stat -e cpu-cycles,instructions,branch-misses,raw-stall-frontend,raw-stall-backend,raw-l1i-cache-refill,raw-l1d-cache-refill,raw-l2d-cache-refill $T/pmuprobe 1"
run record_cycles "cd $T && taskset 80 simpleperf record -e cpu-cycles -c 100000 -o $T/rec-cyc.data $T/pmuprobe 2 > /dev/null; simpleperf report -i $T/rec-cyc.data --sort symbol 2>&1 | head -25"
run record_l1d "cd $T && taskset 80 simpleperf record -e raw-l1d-cache-refill -c 1000 -o $T/rec-l1d.data $T/pmuprobe 2 > /dev/null; simpleperf report -i $T/rec-l1d.data --sort symbol 2>&1 | head -25"
run cleanup "run-as $PKG rm -rf files/pmu433; rm -rf $T"
say "done: $OUT (read with docs/lanes/pmucounters/pmuread.py --controls $OUT/probe_*.txt)"
