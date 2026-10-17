#!/bin/sh
# Per-window timeline and frametrace account of the census arms (A off, B HAKUX_S2T_CVT=1).
# Read only: cineread.py's legs belong to the cinesplit prediction and are not judged here.
R=/home/justin/hakux-work/dispatch/results
W=/home/justin/hakux-work/wt/halo1016
python3 "$W/docs/lanes/halo1016/cineread.py" \
    "$R/0-0-x-1792222165-halo1016-1341449" "$R/0-0-x-1792222171-halo1016-1341994" \
    > "$W/docs/lanes/halo1016/scratch/census-frametrace.md" 2>&1
echo "cineread exit $?"
exit 0
