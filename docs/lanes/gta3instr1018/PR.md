# GTA III dip frame: race-free render-pass-break counters and timed vertex-copy, shader-bind and fence-wait costs

State: draft

Lane: gta3instr1018            Issue: #1049 #433
Base: master @ 1b3b3db8f4
Files: docs/lanes/gta3instr1018/NOTES.md, docs/lanes/gta3instr1018/PR.md, docs/testing/jobs/selftest.d/99-dipwin-counters.sh, hw/xbox/nv2a/pgraph/vk/dipwin.h, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/surface.c
Prediction: none: no arm (instrumentation compiled into perflog builds only; no pixel claim)
Selftest: 99-dipwin-counters.sh
Needs device: yes    Needs NDK: yes

Release note (none): perflog builds gain a per-60-flip breakdown of render-pass ends and frame costs; release builds are unchanged.

A perflog build now prints one `[dipwin]` line under `hakuX-rpbrk` every 60 flips:

- render passes begun and ended, with every end attributed to what asked for it: finishes by reason, framebuffer
  dirty, render-pass change, occlusion query, clears, non-draw commands (by caller address), and the surface
  binding gate split three ways;
- calls and milliseconds for the vertex-RAM sync and copy, the full-path pipeline bind (shader bind, key build,
  LRU lookup, UBO descriptor writes), the finish split into submit and fence, and the fence phase split into its
  waits, downloads, drains and the stale vertex-span copy;
- running totals of flips, passes and ends, which only grow.

The window is counted in flips and closed in one place (the flip finish on the PFIFO thread), and every counter is
added with a relaxed atomic and taken with an atomic exchange, so each add lands in exactly one window. The old
`hakuX-stall`/`rpbrk` window closed on either thread's finish, so a "60-frame" window was 30 to 60 flips; under
perflog it now closes on the flip finish only. Release builds compile none of this; the one restructured release
line (the pipeline-key compare) behaves as before.

`99-dipwin-counters.sh` builds the counter header against four writer threads and a taking reader (the windows must
sum to every add), and checks that draw.c has one window emitter on the flip path. Mutants that use a plain `+=`,
read and then zero, close the window on the presenting finish, add a second emitter, or increment a counter
directly all fail it.

Measurements: see docs/lanes/gta3instr1018/NOTES.md and FINDINGS.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
