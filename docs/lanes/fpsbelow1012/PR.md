# fpsbelow1012: the below-bar titles on the Nova at master, and one fix that lifts several (#433, 0.5)

State: in progress

Lane: fpsbelow1012          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 5326de78b2, merged 00fde8afb3
Files: docs/lanes/fpsbelow1012/NOTES.md, docs/lanes/fpsbelow1012/OUTBOX.md, docs/lanes/fpsbelow1012/PR.md, docs/lanes/fpsbelow1012/tools/routecheck.py, docs/lanes/fpsbelow1012/tools/routecheck.tsv, docs/lanes/fpsbelow1012/tools/tilesim.py, docs/lanes/fpsbelow1012/tools/zread.py, docs/lanes/fpsbelow1012/zetad24.patch, docs/testing/nv2a_index.json, hw/xbox/nv2a/pgraph/vk/surface.c
Prediction: none yet (registered before the A/B, at docs/testing/predictions/fpsbelow1012-<lever>.json)
Needs device: yes (Nova, sweep tier)    Needs NDK: yes

Step 1 done: the offline table of the 43 Nova titles is in NOTES.md section 2. Telemetry at master: the three pilot
runs are queued at sweep tier (DOA3 z-1791787896-fpsbelow1012-2551124, NG Black z-1791787896-fpsbelow1012-2551219,
Midnight Club 3 z-1791787897-fpsbelow1012-2551411), ref 00fde8afb3.

Found offline (NOTES.md section 5): the GMEM-replay class replays because Z24S8 is stored as
D32_SFLOAT_S8_UINT. Turnip keeps that format's stencil as a separate 1-byte plane, which doubles the A740's tile
width alignment to 192, so a 640/720x480 pass with 32-bit colour needs two tiles; two tiles get no HW binning, so
each replays the whole draw stream. As D24_UNORM_S8_UINT the pass fits one tile. Lever L1, `HAKUX_ZETA_D24`
(off by default), is committed at ede7c891c5 (surface.c granted by lane.local, origin/board 9dbc5b2242). Runs on disk
put more titles in the class than gpunonrender named: NBA Live 06/07, Buffy, LOTR, MechAssault 2 and ToeJam also
read as two-tile passes (NOTES.md 5a). The depth-exactness cost of D24 is bounded in NOTES.md section 7; an exact
pgraph pair is planned.

Release note (none): HAKUX_ZETA_D24, an opt-in switch, off by default; nothing changes without it.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
