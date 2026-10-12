# fpsbelow1012: the below-bar titles on the Nova at master, and one fix that lifts several (#433, 0.5)

State: in progress

Lane: fpsbelow1012          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 5326de78b2, merged 00fde8afb3
Files: docs/lanes/fpsbelow1012/NOTES.md, docs/lanes/fpsbelow1012/OUTBOX.md, docs/lanes/fpsbelow1012/PR.md, docs/lanes/fpsbelow1012/tools/routecheck.py, docs/lanes/fpsbelow1012/tools/routecheck.tsv, docs/lanes/fpsbelow1012/tools/tilesim.py, docs/lanes/fpsbelow1012/zetad24.patch
Prediction: none yet (registered before the A/B, at docs/testing/predictions/fpsbelow1012-<lever>.json)
Needs device: yes (Nova, sweep tier)    Needs NDK: not yet

Step 1 done: the offline table of the 43 Nova titles is in NOTES.md section 2. Telemetry at master: the two pilot
runs are queued at sweep tier (z-1791787431-fpsbelow1012-2456548, z-1791787432-fpsbelow1012-2456706).

Found offline (NOTES.md section 5): the GMEM-replay class replays because Z24S8 is stored as
D32_SFLOAT_S8_UINT. Turnip keeps that format's stencil as a separate 1-byte plane, which doubles the A740's tile
width alignment to 192, so a 640/720x480 pass with 32-bit colour needs two tiles; two tiles get no HW binning, so
each replays the whole draw stream. As D24_UNORM_S8_UINT the pass fits one tile. Lever L1, `HAKUX_ZETA_D24`
(off by default), is drafted as `zetad24.patch` and waits on a grant for `hw/xbox/nv2a/pgraph/vk/surface.c`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
