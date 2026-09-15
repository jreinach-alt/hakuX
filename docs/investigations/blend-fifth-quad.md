# `Blend tests`: the arithmetic is right, and the residual is one quad

Measured 2026-09-12 on the recovered 1,568-test oracle, APK `64c01cc70067`.

## Why this was invisible

Our sweeps run 105 `#spot_` captures. The suite once had **1,568** individual
`<sfactor>_<eqn>_<dfactor>` tests, each drawing five quads full-screen, and the
goldens for all of them are still in the repository — they were captured on
silicon in February 2025 and the tests were retired upstream when `#spot_`
grids replaced them. The 2025-03-14 release still generates them:
**1,568 captures in 934 seconds, matching the golden count exactly.**

`#spot_` draws four swatches per cell. These draw five quads. That fifth quad
is the entire finding, and no amount of work on the modern subset could have
found it.

## The result, and one claim of mine to disregard

Over the 1,120 tests using the five **unsigned** equations, what is solid is
the *location*:

| | |
|---|---:|
| captures differing on exactly 16,384 px | **847** |
| captures differing on 8,192 px | 246 |
| the differing region, measured | **256 rows × 64 cols, one quad** |
| captures wrong anywhere else in the frame | **0** |

So the residual is confined to the fifth quad and the rest of the frame —
including the other four quads, across all five equations and all fifteen
source and fifteen destination factors — matches hardware. **The blend
arithmetic is right.** That part is established by the pixel counts and the
bounding boxes, and it stands.

**The mechanism is not established, and my first answer was wrong.** I reported
that the fifth quad renders the first quad's result, on the strength of
single-pixel samples at row 240 agreeing on 1,119 of 1,120 captures. Comparing
the whole 256×64 *region* against our own first quad instead: **identical on 0
of 224**. The quads are not flat — the same file read one row apart gives
different colours — so a row of point samples was never measuring "the quad's
colour", and the agreement it produced was an artefact of the sampling.

What the region actually contains, on `1_MAX_1` (`MAX` ignores both factors, so
the expected result is `max(source, destination)` per channel):

| | colours present in the differing region |
|---|---|
| silicon | (0,0,221) (0,221,0) (44,44,192) (44,192,44) (48,48,196) (48,196,48) |
| ours | (0,0,192) (0,192,0) (44,44,192) (44,192,44) (4,4,196) (4,196,4) |

Where silicon has 221 we have 192, and where it has 48 we have 4 — and in both
cases the value we produce is the *lower* of the pair, with the two flat
background colours shared. That is the shape of the source contributing
nothing: the fifth draw's source either never arrives or is being taken as the
destination. **That is a hypothesis, not a finding** — it fits one test's
colour inventory and has not been checked across the suite, and the last two
hypotheses I offered for this region did not survive contact with a better
measurement.## Where to look

The suite draws its quads in sequence with a colour change between them. On the
evidence, four of those changes take effect and the fifth does not — so the
candidates are a draw whose vertex colour is fetched before the change lands, a
state hash that does not include whatever the fifth draw alters, or a deferred
draw replayed with stale constants. The draw-queue path is a specific suspect:
it reorders and replays draws, and a colour that changes between two draws in
the same window is exactly what it must not miss.

The one violation out of 1,120 is worth finding too — a rule that holds 1,119
times and fails once usually means the exception is the informative case.

## What it changes for the corpus

`Blend tests` carries the largest non-precision population in the corpus and
was ranked as the strongest single item on the board. On this oracle, the
unsigned half of it is **one draw-state bug**, not a blend-unit investigation —
and the blend unit is exonerated by 4,480 matching quads rather than by
argument.
