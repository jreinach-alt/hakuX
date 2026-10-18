#!/usr/bin/env bash
# Three anchors on run 13's video: video time T against dump frames F0-75..F0+75 (nominal t = 14.4 + f/30).
T=/home/justin/hakux-work/wt/haloring1017/docs/lanes/haloring1017/tools
R=/home/justin/hakux-work/dispatch/results/1-1792184446-x1port1012-1339105
H=/tmp/claude-1000/-home-justin-hakuX/hr
for spec in 17.4:90 24.4:300 31.4:510; do
  t=${spec%:*}; f0=${spec#*:}
  lo=$((f0 - 75)); [ $lo -lt 0 ] && lo=0
  hi=$((f0 + 75)); [ $hi -gt 599 ] && hi=599
  o=$H/anc$f0
  python3 $T/vidmap.py $R/pulled/framedump_1792184534.jsonl $H/m2a/ram.bin $R/video/v00001.mp4 $o every=1 line=$t,0 frames=$lo:$hi > $o.vidmap.log 2>&1
  ( python3 $T/bandfit.py $R/pulled/framedump_1792184534.jsonl $H/m2a/ram.bin $o/bandfit.tsv draws=n5 every=1 px=8000 pad5=0.0 images=$o/map.tsv > $o/bandfit.log 2>&1; echo "ANCHOR_DONE $f0" >> $H/anchors.done ) &
done
wait
echo ALL_DONE >> $H/anchors.done
