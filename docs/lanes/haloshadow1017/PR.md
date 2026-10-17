# haloshadow1017: character shadows draw as dark squares under the feet (Halo CE and other titles)

State: draft

Lane: haloshadow1017            Issue: #1038
Base: master @ 8d260f39fc
Files: docs/lanes/haloshadow1017/NOTES.md, docs/lanes/haloshadow1017/PR.md, docs/lanes/haloshadow1017/tools/chain.py, docs/lanes/haloshadow1017/tools/deskbuild.sh, docs/lanes/haloshadow1017/tools/deskrun.py, docs/lanes/haloshadow1017/tools/hxsram.py, docs/lanes/haloshadow1017/tools/sqcrop.py, docs/lanes/haloshadow1017/tools/texids.py, hw/xbox/nv2a/pgraph/vk/renderer.c
Prediction: none: analysis-only (so far)
Needs device: yes    Needs NDK: no

A deep dive into the dark square drawn under each soldier's feet in Halo: Combat Evolved.

The step-0 search for approaches already tried is done and committed. Details are in
`docs/lanes/haloshadow1017/NOTES.md`.

What is established so far:

- **The projection's neutral texel is black.** The combiner computes
  S = (1-t1)·v0.a·t0·(1-c0), and the blend is dst·(1-S).
- **Both 128x128 render targets hold correct content on the host.** The save-state guest RAM shows a
  white silhouette on 0x0000, and a blurred silhouette on 0x0000. So the clear lands and the blur
  works.
- **The fault lies between the correct target and the value stage 0 of the projection samples.**
  Stage 0 returns non-zero rgb across the whole [0,1] footprint.
- **The defect survives all three surface-to-texture regimes**: the direct bind (August), the CPU
  decode (0.5.1) and the GPU cvt (0.5.2). So its cause is in what those regimes share.
- **A white texel at stage 0 reproduces the footprint exactly.** The renderer's dummy texture
  samples (1,1,1,1). The leading hypothesis is that the descriptor names the dummy or another
  view while the binding is correct.

Frame dump schema 10 (`hw/xbox/nv2a/pgraph/vk/renderer.c`, diagnostics only, armed by
`XEMU_FRAME_DUMP`):

- the `rttmaxNN` token reads back render targets larger than 64x64 (Halo's are 128x128);
- each stage records which view its descriptor names ("bv", "pv", "tv");
- each draw records "ptd";
- 16-bit colour surfaces are read back.

Release note (none): frame-dump instrumentation only; nothing changes unless a dump is armed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
