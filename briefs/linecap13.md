# lane.linecap13 -- #13's cap/join residual

Issue: #13 (Line rasterisation, [accuracy])
Base: master @ 38385b79c141d863560f4f97482d02b514c8dd79
Files: hw/xbox/nv2a/pgraph/glsl/geom.c

## What's already done

The Vulkan line-width extent phase already landed and is exact
(47.8178% -> 99.5838%+ vs silicon on widths >= 6, 99.6563% over all widths;
docs/testing/predictions/line-extent-phase-exact.json PASSED pre-registered).
What is left is narrower: ~908px residual (495 in the latest whole-capture
scoring), ours-only, 98.8% within w/2+2 px of a vertex -- cap/join geometry,
not the extent rule. `emit_line()` in glsl/geom.c generates the
perpendicular-rectangle body only; grep finds no cap or join geometry there
today.

## Goal

Give `emit_line()` correct cap and/or join geometry against the goldens'
Line_* captures, without moving the exact-extent cuts already proven.

## Falsifier

`docs/testing/line_extent_phase.py --vs-goldens` over the Line_* captures:
the cap/join residual class must shrink toward 0 without regressing any
must_not_move capture, and `ab_compare` must show 0 worse on Line_* and
Blend_tests. Read nv2a_issues.toml's #13 entry before trusting any exact-match
leg -- it records one earlier control that was mis-transcribed (11 captures
that a correct w=1.0 fix must legitimately move).

## Done when

`line_extent_phase.py --vs-goldens` shows the cap/join residual gone or
sharply reduced, `ab_compare` shows 0 worse on Line_* and Blend_tests, and a
registered prediction is written (not just measured locally) so the arms job
can queue and verify it on device.

## Out of scope

The GL renderer (gl/shaders.c, gl/draw.c) is lane.remote's territory --
do not touch it even for parity; this issue's Vulkan half stands alone per
its own tracker note ("AGENTS.md does not oblige both renderers to gain a
feature in the same commit").
