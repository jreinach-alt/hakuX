# fpsbelow1012: the below-bar titles on the Nova at master, and one fix that lifts several (#433, 0.5)

State: in progress

Lane: fpsbelow1012          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 5326de78b2, merged 00fde8afb3, then a13a2f52db
Files: docs/lanes/fpsbelow1012/NOTES.md, docs/lanes/fpsbelow1012/OUTBOX.md, docs/lanes/fpsbelow1012/PR.md, docs/lanes/fpsbelow1012/drafts/vtxexact.diff, docs/lanes/fpsbelow1012/tools/routecheck.py, docs/lanes/fpsbelow1012/tools/routecheck.tsv, docs/lanes/fpsbelow1012/tools/tilesim.py, docs/lanes/fpsbelow1012/tools/vtxrange.out, docs/lanes/fpsbelow1012/tools/vtxrange.py, docs/lanes/fpsbelow1012/tools/zread.py, docs/testing/nv2a_index.json, docs/testing/predictions/fpsbelow1012-zetad24-pixels.json, docs/testing/predictions/fpsbelow1012-zetad24.json, hw/xbox/nv2a/pgraph/vk/surface.c
Prediction: docs/testing/predictions/fpsbelow1012-zetad24.json @ ec352c20a21e07b144e4b1cc6bfaa895d0792fd745c215135a0a3a739c6dce7e (title A/B); docs/testing/predictions/fpsbelow1012-zetad24-pixels.json @ c543e6ac7e76b4bc73d102c1140b9f59b7816cce469b47086a950e0ad1e9caee (depth cost)
Needs device: yes (Nova, sweep tier)    Needs NDK: yes

Step 1 done: the offline table of the 43 Nova titles is in NOTES.md section 2. The telemetry pilot at master
(00fde8afb3) is read (NOTES.md section 8). NG Black is still a two-tile pass (in/out 0.52-0.54, 19-29 ms of GPU per
command buffer) at fps_ok 0.913. Midnight Club 3 went from 0.006 to 0.815; it is the `range` surface-download class,
with 14 downloads per flip and 11.9 ms/frame. The DOA3 pilot was void before input.

Found offline (NOTES.md section 5): the GMEM-replay class replays because Z24S8 is stored as
D32_SFLOAT_S8_UINT. Turnip keeps that format's stencil as a separate 1-byte plane, which doubles the A740's tile
width alignment to 192, so a 640/720x480 pass with 32-bit colour needs two tiles; two tiles get no HW binning, so
each replays the whole draw stream. As D24_UNORM_S8_UINT the pass fits one tile. Lever L1, `HAKUX_ZETA_D24`
(off by default), is committed at ede7c891c5 (surface.c granted by lane.local, origin/board 9dbc5b2242). Runs on disk
put more titles in the class than gpunonrender named: NBA Live 06/07, Buffy, LOTR, MechAssault 2 and ToeJam also
read as two-tile passes (NOTES.md 5a). The depth-exactness cost of D24 is bounded in NOTES.md section 7; an exact
pgraph pair is registered (`fpsbelow1012-zetad24-pixels.json`) and not yet run.

The title A/B (`fpsbelow1012-zetad24.json`, ref be0239bac8, one binary, env-only B), first title judged
(NOTES.md 9a): NG Black passes every leg.

| arm | zfmt | gfps median | G median | in/out | outer span per cb | fps_ok (whole run) |
|---|---|---|---|---|---|---|
| A (no switch) | 0x82 | 40 | 25.6 ms | 0.53 | 21.54 ms | 0.847 |
| B (`HAKUX_ZETA_D24=1`) | 0x81 | 59 | 16.9 ms | 0.99 | 12.34 ms | 0.960 |

DOA3 A and Buffy A are queued at sweep tier; their B arms are queued only once A reads in the class.

Second lever, L4a (NOTES.md section 10): Midnight Club 3's `range` downloads (927 per 60 frames at master, each
with a finish) are not the texture scan (`scdl` 0). They come from the vertex-RAM sync or a blit. Forza and
Nightfire show the same class in runs on disk. `sync_vertex_ram_buffer` tests GPU staleness on page-rounded,
merged ranges, where `has_dirty_vertex_pages` tests the exact ones, and 6 of MC3's 9 bound surfaces start
mid-page. A `HAKUX_RANGELOG` instrument (surface.c, perf builds, off by default) names each range download's
caller and whether the draw's exact bytes reach the surface. MC3's and Forza's instrument runs are queued. The
fix it would point to (`drafts/vtxexact.diff`, `HAKUX_VTX_EXACT`) is drafted, not applied; it needs draw.c,
vertex.c and renderer.h, which are not granted.

Release note (none): HAKUX_ZETA_D24 and HAKUX_RANGELOG, opt-in switches, off by default; nothing changes without them.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
