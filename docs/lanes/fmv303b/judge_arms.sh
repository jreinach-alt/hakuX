#!/bin/sh
# Run tier1_judge.py on the four queued arms, and show each run's build and tier1 lines.
R=/home/justin/hakux-work/dispatch/results
D=$(dirname "$0")
L1=$R/0-0-y-1790433000-1790433154-fmv303b-2431986/logcat.txt
L2=$R/0-0-y-1790433000-1790433156-fmv303b-2432129/logcat.txt
L3=$R/0-0-y-1790433000-1790433159-fmv303b-2432336/logcat.txt
L4=$R/0-0-y-1790433000-1790433161-fmv303b-2432888/logcat.txt
for f in "$L1" "$L2" "$L3" "$L4"; do
  echo "== $f"
  grep -m3 -E 'hakuX-build|tier1 threshold|HAKUX_TIER1' "$f"
  echo "tint lines: $(grep -c 'tex0 tint' "$f")"
done
python3 "$D/tier1_judge.py" --on "$L1" --on "$L3" --off "$L2" --off "$L4"
