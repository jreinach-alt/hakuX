Lane: blinx372e            Issue: #372
Base: master @ e5db66fa37 (plus a merge of lane/doa413b @ 988e51328e, PR #440, as the brief asks)
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/blinx372e/NOTES.md, docs/lanes/blinx372e/abquad.py, docs/lanes/blinx372e/register_mnm.py, docs/lanes/blinx372e/pr-body.md, docs/testing/predictions/blinx372e-demo-ab.json, docs/testing/predictions/blinx372e-mnm.json
Merged from #440 (not edited here; these drop out of the diff when #440 folds): docs/audits/2026-09-26-doa413b-pass1.md, docs/lanes/doa413b/NOTES.md, docs/lanes/doa413b/ab_read.py, docs/lanes/doa413b/cc_surface.py, docs/lanes/doa413b/register_defoff.py, docs/testing/dispatcher.sh, docs/testing/predictions/doa413b-defoff-mnm.json, docs/testing/predictions/doa413b-lazy-mnm.json
Prediction: docs/testing/predictions/blinx372e-demo-ab.json, docs/testing/predictions/blinx372e-mnm.json (A 988e51328e, B 489394939f)
Needs device: yes    Needs NDK: no

Blinx's attract demo flips one linear D24S8 zeta binding at one address, pitch 2560, between 640x480 and 320x240 twice a frame, and each flip was a synchronous surface download plus a re-upload (blinx372d). This PR removes the small-to-big one: the small binding's image is copied into the top-left corner of the large binding's kept image with `vkCmdCopyImage` (depth and stencil), and the large binding then owes the download, as #396's handoff partner does. Big to small is unchanged.

**The CPU-write gap is closed by a guard, not assumed away.** The copy is right only if the large binding's image still equals an upload of its VRAM outside the corner. So the guard hashes that VRAM when the large binding's own eviction download lands, and hashes it again at the flip. Any writer (the guest's CPU, a blit, a download) changes the hash and sends the flip down the old path. The large binding keeps its watch on the shelf (it was shelved draw-dirty), and `[quad372] cpu_writes=` counts guest stores to it. At the flip the watch is handed over with no unwatched moment: the old watches' removal is queued after the new insert. Also declined: rows wider than the pitch (AA x2 zeta, `3D_primitive` -ls/-ps), which make the download non-invertible.

`[quad372] copies= arms= cpu_writes= vram_changed=` prints every 5 s beside `[evict372]`.

| | value | kind |
|---|---|---|
| A's two waits (blinx372c/d soaks) | Sub 25.6-35.2 ms of Tot 56.6-71.1 ms | measured |
| B's ceiling | about 15-19 fps by gfps (18-23 by Tot), from about 12.5 | bound, not a value |
| added cost | one 320x240 D24S8 image copy and two 1.2 MB hashes per frame (analytic 0.1-0.6 ms) | estimate |

Arms: the demo A/B is queued (`1790483694-blinx372e-3615063` / `1790483698-blinx372e-3616042`, Thor) and judged by `docs/lanes/blinx372e/abquad.py`. The must-not-move arm (Surface_clip, 3D_primitive, Depth_buffer_fixed_function, Color_zeta_overlap, Surface_format, Texture_CPU_Update, Texture_render_update_in_place) goes to the arms job. Results: pending. Details are in docs/lanes/blinx372e/NOTES.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
