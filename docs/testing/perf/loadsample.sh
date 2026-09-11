#!/bin/bash
# Sample GPU and per-thread CPU load while the emulator runs. Everything here
# is read from the kernel, so it costs the emulator nothing: the Adreno driver
# publishes its own busy counters under /sys/class/kgsl, and per-thread CPU
# comes from /proc/<pid>/task/*/stat. That pair says whether the bottleneck is
# the GPU, one saturated emulator thread, or neither.
#
# The comm field in /proc/.../stat is parenthesised and may itself contain
# spaces, so the fields after it cannot be addressed positionally from the
# start of the line. Split on the last ')' instead.
#   loadsample.sh <duration_s> <interval_s> <out_file>
set -u
S=${SERIAL:-ee317437}; PKG=${PKG:-com.jreinach.hakux.debug}
DUR="${1:-40}"; IVAL="${2:-2}"; OUT="${3:?out file}"

PID=$(adb -s $S shell "pidof $PKG:xemu" | tr -d '\r' | awk '{print $1}')
[ -z "$PID" ] && { echo "no xemu process" >&2; exit 1; }
echo "sampling pid $PID for ${DUR}s" >&2

# One device-side shell runs the whole loop; an adb round trip per sample would
# cost more than the thing being measured.
adb -s $S shell "
PID=$PID
for i in \$(seq 1 $((DUR / IVAL))); do
  echo \"--- \$(date +%s%3N)\"
  echo \"gpubusy \$(cat /sys/class/kgsl/kgsl-3d0/gpubusy 2>/dev/null)\"
  echo \"gpu_pct \$(cat /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage 2>/dev/null | tr -d ' %')\"
  echo \"gpu_clk \$(cat /sys/class/kgsl/kgsl-3d0/gpuclk 2>/dev/null)\"
  echo \"gpu_temp \$(cat /sys/class/kgsl/kgsl-3d0/temp 2>/dev/null)\"
  for c in 0 4 7; do
    printf 'cpufreq%s %s\n' \$c \$(cat /sys/devices/system/cpu/cpu\$c/cpufreq/scaling_cur_freq 2>/dev/null || echo 0)
  done
  for t in /proc/\$PID/task/*; do
    [ -r \$t/stat ] || continue
    awk '{
      p = index(\$0, \"(\"); q = 0
      for (i = length(\$0); i > 0; i--) if (substr(\$0, i, 1) == \")\") { q = i; break }
      comm = substr(\$0, p + 1, q - p - 1)
      gsub(/ /, \"_\", comm)
      n = split(substr(\$0, q + 2), a, \" \")
      # after comm: state ppid pgrp sid tty tpgid flags minflt cminflt
      # majflt cmajflt utime stime  -> utime a[12], stime a[13]
      printf \"thread %s %s %s %s\n\", \$1, comm, a[12], a[13]
    }' \$t/stat
  done
  sleep $IVAL
done
" > "$OUT" 2>/dev/null
echo "wrote $OUT" >&2
