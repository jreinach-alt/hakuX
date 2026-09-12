# `Line width`: what is actually left, and the mistake that hid it

Rewritten 2026-09-12. The first version of this file said the width never
reaches the rasteriser. **That was wrong**, and the way it went wrong is worth
more than the conclusion was.

## The mistake

I measured our output against the goldens using `res_full0907`, a full-corpus
capture set from 2026-09-07, and never checked it against the binary it came
from. `4ed3a55ea6`, "nv2a: rasterise lines at the width SET_LINE_WIDTH asks
for", landed on 2026-09-11 — after those captures were taken. So the constant
coverage column I found, ~6,470 lit pixels for every width from 0.0 to 64.875,
was real and is four days stale. On the current binary the same measurement
tracks silicon.

The same-shaped error is already on the record for goldens
(`docs/testing/nv2a_issues.toml` #27: a test newer than its golden poisons a
suite). This is that error pointed the other way — a capture older than its
fix — and it cost a write-up, an instrumented build and a wrong entry at the
top of the target ranking. **Date the captures against the commit, not just
the goldens against the disc.**

## What the current binary does

Measured on the #19 sweep's own `g0` arm, APK `f9b5a5df2776`, all 61 captures.

| width | golden | ours | ours/golden |
|---:|---:|---:|---:|
| 0.000 | 3,104 | 3,104 | **1.00 exact** |
| 0.125 | 3,564 | 6,471 | 1.82 |
| 0.500 | 4,798 | 6,475 | 1.35 |
| 1.000 | 6,677 | 6,471 | 0.97 |
| 1.125 | 7,296 | 6,451 | 0.88 |
| 1.250 | 7,667 | 8,124 | 1.06 |
| 1.750 | 9,172 | 9,566 | 1.04 |
| 4.000 | 16,192 | 15,491 | 0.96 |
| 16.000 | 42,870 | 41,229 | 0.96 |
| 63.875 | 91,319 | 89,374 | 0.98 |

Three distinct things are left, and they want different work:

**1. Below about 1.25 px the width does not move.** Ours sits at ~6,470 — the
1.0 figure — from 0.125 through 1.125, while silicon rises smoothly from 3,564
to 7,296. Above that our coverage steps in visible jumps (6,471 → 8,124 →
9,566), which is a granularity quantum, not a smooth curve. Both are the
device's doing: `lineWidthRange[0]` need not go below 1.0 and
`lineWidthGranularity` snaps what it does admit. `4ed3a55ea6` says as much and
deliberately left it: silicon draws a rectangle narrower than a pixel as
*dashes*, which no line rasteriser will do.

**2. Width 0.0 is exact**, and that is not luck — the same commit found that a
zero-width line covers no pixel centre and drops the draw entirely, which the
golden confirms by keeping the test's points and losing every line.

**3. A systematic 3-4% shortfall at every width from 1.0 up.** 0.96–0.98 with
a slow drift towards 1.0 as the line gets wider, which is the signature of a
per-line constant: the ends. On a wide line the ends are a smaller fraction of
the total, so the ratio improves. `4ed3a55ea6` names "the ends and joins" as
remaining, and this is the shape of that.

## What is worth doing, in order

1. **The device's limits, which nothing logs.** `lineWidthRange`,
   `lineWidthGranularity`, and whether `wideLines` was enabled. Committed as
   `0a97b8f48e` and still the right measurement — it bounds how much of (1) is
   reachable at all before any geometry work, and the numbers are currently
   guesses. One run of the suite.
2. **The ends**, which is (3), the only part that is ours rather than the
   device's, and it applies at *every* width rather than to a corner of the
   range.
3. **Lines as geometry**, which is the only route to (1) and to the sub-pixel
   dashes. Expensive: `emit_line` in `glsl/geom.c` already computes the
   perpendicular, but `emit_vertex` passes `gl_Position` through untouched and
   the widened quad must carry the original `vtxPos0/1/2` triple so fragment
   interpolation still describes the true line. It also needs a pixel-to-clip
   scale in the geometry stage, which has no uniform block today — so either
   new uniform plumbing across both renderers, or the surface size keyed into
   `GeomState` the way the width would be. Worth doing after (1) says how much
   it buys.

Method note: measuring lit pixels per capture against the requested parameter
is what made all of this legible, both the stale answer and the real one — a
golden diff says "these pixels are wrong", a coverage column says whether the
parameter is arriving and in what steps. `docs/testing/line_coverage.py`. Its
one-line verdict ("constant to within 5%: the parameter is not arriving")
is what should have made me check the date, because a parameter that had never
worked at all would have been noticed by whoever wrote the register handler.
