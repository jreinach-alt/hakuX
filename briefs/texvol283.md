# #283: Y16 and R16B16 volume textures differ from silicon

Lane: texvol283            Issue: #283 (pgraph; may share #10's Y16/R16B16 decode classes)
Base: origin/master @ d92ae5d7f3 (rebase to the tip before you register anything).
Files: hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/gl/texture.c,
hw/xbox/nv2a/pgraph/texture.c, docs/testing/predictions/texvol283-*.json, docs/lanes/texvol283/**
Needs device: yes for the arm. Needs NDK: no.

## The defect
Volume texture Y16 (65,369 px, white-content) and R16B16 (42,412 px): 0/2 exact, 6,450
one-step. These figures are the H fallback (scoreboard c866527e03, 2026-09-13, Thor), NOT a
current run: the issue's own expected recoverable is 10,778 px (10% of the 0-107,781 ceiling).

## Step 1 is a measurement, and it can end the lane
1. Re-measure on today's build: run the Volume texture suite on the Thor (or Nova), score
   against the goldens with `scores1.tsv` status read. If both captures are exact or within
   rounding now, say so in NOTES.md and stop -- that is a finished lane.
2. Read #10 (briefs/10.md and the issue) before writing code: BumpMap_Y16 44,748 and R16B16
   101,330 are decode classes it already owns or refuted. If the volume captures fail for the
   same reason, the mechanism belongs there; cite it and do not derive it twice. If they
   differ (a volume-specific layout, a depth-slice stride, a swizzle that is per-slice),
   that is yours.
3. The issue's location, vk/texture.c 16-bit formats, is a guess. Derive from the capture:
   decode one texel of each format by hand and compare with the golden pixel.

## The arm (register BEFORE building, after the last rebase)
- must_move: Volume texture Y16 and R16B16 legs, each stated separately.
- must_not_move: every other Volume texture capture and the suites in
  `nv2a_index.py blast hw/xbox/nv2a/pgraph/vk/texture.c` -- in particular the 16-bit 2D
  formats and BumpMap_Y16 / R16B16 unless #10's mechanism is the same one.
- Failing world: a decode change that fixes the volume capture by shifting a 2D 16-bit format.
- Check `unreadable` status and PARTIAL COVERAGE.

## Done when
Either both captures match silicon, or NOTES.md records that the fresh measurement leaves
no residual / that #10 owns the mechanism (with the citation), the must-not-move legs hold,
and the PR is ready with the arm verdict.
