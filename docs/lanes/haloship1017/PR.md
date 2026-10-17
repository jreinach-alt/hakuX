# Halo CE: the ship's rear lights show through the hull after the cut to the front (opening cinematic)

State: draft

Lane: haloship1017            Issue: #1039
Base: master @ 8d260f39fc
Files: docs/lanes/haloship1017/, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/reports.c, ui/xemu-input.c
Prediction: none: instrument only so far (no arm)
Needs device: yes    Needs NDK: no

Release note (none): instrumentation only, off unless set: frame dump schema 10 (visibility tests), HAKUX_ZREP, HAKUX_PAD_FILE.

Step 0 done: `docs/lanes/haloship1017/NOTES.md` carries the Already-tried table and the hypothesis table. The
owner's sighting was on 2636e89f4a, which has no REPORT_EARLY, so a stale early answer is not the origin. The
per-report instrument is in; next: reproduce on the desktop, every frame across the cut.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
