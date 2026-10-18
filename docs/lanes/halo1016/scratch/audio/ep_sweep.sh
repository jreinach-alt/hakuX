#!/bin/sh
# Frequency sweep of Halo's own DSP program, bin 0 (FL) -> EP L and GP L,
# with audio1016's dsp_gain_matrix.py on the slot1 export.
#   ep_sweep.sh EXPORTDIR [BIN]
S=/home/justin/hakux-work/wt/halo1016/docs/lanes/halo1016/scratch/audio
T=/home/justin/hakux-work/wt/halo1016/docs/lanes/audio1016/tools
BIN=${2:-0}
for f in 60 100 150 250 400 600 997 1500 2000 3000 4000 6000 8000 12000; do
    printf '%6s Hz ' "$f"
    python3 "$T/dsp_gain_matrix.py" "$S/dsp_harness" "$1" "$S/dsp_work" \
        --bins "$BIN" --freq "$f" | tail -n 1
done
