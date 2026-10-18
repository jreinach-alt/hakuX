#!/usr/bin/env bash
# Run 13 (Turnip) video on the clock from the three anchors: t = 13.2513 + 0.0334128 f.
T=/home/justin/hakux-work/wt/haloring1017/docs/lanes/haloring1017/tools
R=/home/justin/hakux-work/dispatch/results/1-1792184446-x1port1012-1339105
H=/tmp/claude-1000/-home-justin-hakuX/hr
o=$H/m2c
python3 $T/vidmap.py $R/pulled/framedump_1792184534.jsonl $H/m2a/ram.bin $R/video/v00001.mp4 $o every=5 line=13.2513,0.0334128 > $H/m2c.vidmap.log 2>&1
echo VIDMAP_DONE >> $H/m2c.done
python3 $T/bandfit.py $R/pulled/framedump_1792184534.jsonl $H/m2a/ram.bin $o/bandfit.tsv draws=n4,n5 every=5 images=$o/map.tsv > $o/bandfit.log 2>&1
echo "BANDFIT_DONE $?" >> $H/m2c.done
python3 $T/bandsum.py $o/bandfit.tsv > $o/bandsum.out 2>&1
echo ALL_DONE >> $H/m2c.done
