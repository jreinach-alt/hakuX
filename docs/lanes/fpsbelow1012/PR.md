# fpsbelow1012: the below-bar titles on the Nova at master, and one fix that lifts several (#433, 0.5)

State: in progress

Lane: fpsbelow1012          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 5326de78b2, merged 00fde8afb3
Files: docs/lanes/fpsbelow1012/NOTES.md, docs/lanes/fpsbelow1012/OUTBOX.md, docs/lanes/fpsbelow1012/PR.md, docs/lanes/fpsbelow1012/tools/routecheck.py, docs/lanes/fpsbelow1012/tools/routecheck.tsv, docs/lanes/fpsbelow1012/tools/tilesim.py, docs/lanes/fpsbelow1012/tools/zread.py, docs/testing/nv2a_index.json, docs/testing/predictions/fpsbelow1012-zetad24-pixels.json, docs/testing/predictions/fpsbelow1012-zetad24.json, hw/xbox/nv2a/pgraph/vk/surface.c
Prediction: docs/testing/predictions/fpsbelow1012-zetad24.json @ ec352c20a21e07b144e4b1cc6bfaa895d0792fd745c215135a0a3a739c6dce7e (title A/B); docs/testing/predictions/fpsbelow1012-zetad24-pixels.json @ c543e6ac7e76b4bc73d102c1140b9f59b7816cce469b47086a950e0ad1e9caee (depth cost)
Needs device: yes (Nova, sweep tier)    Needs NDK: yes

Step 1 done: the offline table of the 43 Nova titles is in NOTES.md section 2. The telemetry pilot at master
(00fde8afb3) is read (NOTES.md section 8). NG Black is still a two-tile pass (in/out 0.52-0.54, 19-29 ms of GPU per
command buffer) at fps_ok 0.913. Midnight Club 3 went from 0.006 to 0.815; it is the `range` surface-download class,
with 14 downloads per flip and 11.9 ms/frame. The DOA3 pilot was void before input. The title A/B for
`HAKUX_ZETA_D24` is registered (NOTES.md section 9) and its first four arms are queued at sweep tier: NG Black B and
A, DOA3 A, Buffy A.

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
