# Device side, run as the app (`adb shell run-as <pkg> sh -s <pkg>:xemu` < this file).
# Once a second, for every thread of the emulator process: its read counters
# and CPU ticks. Lines:
#   T <uptime s>
#   <tid> <rchar> <syscr> <read_bytes> | <raw /proc/<pid>/task/<tid>/stat>
# The stat line is raw because a thread name can hold spaces; taskio.py
# splits it on the last ')'. Runs until the process is gone.
name=$1
pid=""
i=0
while [ -z "$pid" ] && [ $i -lt 120 ]; do
    pid=$(ps -A -o PID,NAME | awk -v n="$name" '$2 == n {print $1; exit}')
    [ -z "$pid" ] && sleep 1
    i=$((i + 1))
done
[ -z "$pid" ] && { echo "E no $name"; exit 1; }
echo "P $pid"
while [ -d /proc/$pid ]; do
    echo "T $(cut -d' ' -f1 /proc/uptime)"
    for t in /proc/$pid/task/*; do
        io=$(awk '/^rchar|^syscr|^read_bytes/ {printf "%s ", $2}' $t/io 2>/dev/null)
        echo "${t##*/} $io| $(cat $t/stat 2>/dev/null)"
    done
    sleep 1
done
echo "X gone"
