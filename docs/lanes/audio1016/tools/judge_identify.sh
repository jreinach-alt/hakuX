#!/bin/sh
# Run mixlog_read.py and level_windows.py over each run's logcat and keep the
# output under OUT_DIR (.tsv: the repo ignores *.txt):
#   <run>.mix.tsv     every apumix row, with today's and the switch's gains
#   <run>.sum.tsv     one row per slot layout, frame-weighted excess (switch v1)
#   <run>.cap.tsv     the same with the unity cap (switch v2)
#   <run>.lvl.tsv     per-5 s level windows from the cumulative meter
#   <run>.meter.tsv   the last cumulative meter lines (clipped count, run total)
#   <run>.dsp.tsv     the apudsp lines (GP/EP cycles, APU thread load), if any
#
#   judge_identify.sh RESULTS_DIR OUT_DIR R1=<id> R2=<id> ...
res=$1
out=$2
shift 2
tools=$(dirname "$0")
mkdir -p "$out"
for kv in "$@"; do
    name=${kv%%=*}
    id=${kv#*=}
    lc="$res/$id/logcat.txt"
    python3 "$tools/mixlog_read.py" "$lc" --min-frames 0 > "$out/$name.mix.tsv"
    python3 "$tools/mixlog_read.py" "$lc" --min-frames 0 --summary > "$out/$name.sum.tsv"
    python3 "$tools/mixlog_read.py" "$lc" --min-frames 0 --summary --cap > "$out/$name.cap.tsv"
    python3 "$tools/level_windows.py" "$lc" > "$out/$name.lvl.tsv"
    grep -h "hakuX-audio.*level [LR]:" "$lc" | tail -2 > "$out/$name.meter.tsv"
    grep -h "hakuX-audio.*apudsp " "$lc" > "$out/$name.dsp.tsv"
    echo "$name $id: $(wc -l < "$out/$name.mix.tsv") mix rows, $(wc -l < "$out/$name.lvl.tsv") level rows, $(wc -l < "$out/$name.dsp.tsv") dsp rows"
done
