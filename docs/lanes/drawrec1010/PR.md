drawrec1010: census of consecutive-draw state at the NFS Most Wanted race start, then dirty-tracked reuse (#433, 0.5)
State: draft

Lane: drawrec1010       Issue: #433 (umbrella), none filed
Base: master @ 9fd2608f8f
Files: hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/shaders.c, docs/lanes/drawrec1010/**, docs/testing/predictions/drawrec1010-*.json
Prediction: none yet (registered before the A/B arm; census first)
Needs device: yes (Nova)
Needs NDK: no

Step 3 of `docs/lanes/nfs30plan1010/PLAN.md`: cut the PFIFO thread's
per-draw recording cost at the NFS Most Wanted race start by about a third.

1. `HAKUX_DRAWCENSUS=1` (default off, no behaviour change): for every
   consecutive pair of draws, which inputs changed, as a histogram per 60
   frames in logcat. Reader: `docs/lanes/drawrec1010/censusread.py`.
2. The census decides between dirty-tracked reuse (`HAKUX_DRAWREC=1`),
   batching, or stopping with a recommendation for the recorder thread.

Work in progress; see `docs/lanes/drawrec1010/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
