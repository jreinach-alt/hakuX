gtasagpu1011: GTA San Andreas, hard-edged sky polygons and no shadow under CJ (#433, 0.5)
State: draft

Lane: gtasagpu1011      Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 6d8947bb47
Files: docs/lanes/gtasagpu1011/NOTES.md, docs/lanes/gtasagpu1011/PR.md, hw/xbox/nv2a/pgraph/vk/renderer.c
Prediction: none: step 1 is a switch screen read by eye (P per switch in NOTES.md section 1); step 2 is instrumentation
Needs device: yes (Nova)    Needs NDK: yes

Work in progress.

- Step 1 queued: `HAKUX_SURFGPU=0` (`1-1791735439-lane.gtasagpu1011-3545202`) and `HAKUX_GPL=0` (`...-3545543`).
- Step 2: the live frame dump now records each draw's blend, depth, stencil, colour mask, depth target and render-to-texture surfaces (schema 4, 33ceb415ca). A 30-frame dump in sunny gameplay is queued (`1-1791735798-lane.gtasagpu1011-3571105`).

Release note (none): frame-dump instrumentation only; off unless XEMU_FRAME_DUMP is set.
