# `Blend tests`: the arithmetic is right, the fifth quad is the first one again

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

## The result

Over the 1,120 tests using the five **unsigned** equations:

| | |
|---|---:|
| quads 1–4 matching silicon at their centres | **4,480 / 4,480** |
| our quad 5 equal to our own quad 1 | **1,119 / 1,120** |
| captures wrong in any *other* way | **0** |

**The blend arithmetic is correct.** Every one of the first four quads, in every
one of the 1,120 tests, across all five equations and all fifteen source and
fifteen destination factors, matches hardware. There is no factor-mapping
error, no equation error and no rounding error to find here.

**The fifth quad renders the first quad's result.** Not a different wrong
colour — the first quad's, exactly, 1,119 times out of 1,120. Where the test
happens to want the same colour in both positions the capture comes out exact,
which is the whole of the 255 "passing" captures; the other 865 differ on
precisely the fifth quad's 64×256 pixels and nowhere else.

Three examples, at the fifth quad's centre:

| test | silicon | ours | our quad 1 |
|---|---|---|---|
| `1_MAX_1` | (48, 48, 196) | (196, 48, 48) | (196, 48, 48) |
| `srcRGB_ADD_1-srcRGB` | (47, 47, 161) | (176, 48, 48) | (176, 48, 48) |
| `1_MIN_dstRGB` | (26, 26, 36) | (48, 4, 4) | (48, 4, 4) |

## What it is not

It is **not** a blend defect, and that is the point. `MIN` and `MAX` do not
consult the blend factors at all and behave identically, so the mechanism is
upstream of blending: the fifth draw is issued with the first draw's source
colour. Something about the state the fifth quad sets is not reaching us, or is
reaching us as the first quad's.

It is also **not** the signed-equation problem. The 448 `SADD`/`SREVSUB` tests
fail on five or six quads each rather than one, which is #43 and has its rule
already derived. Splitting them out is what left the unsigned result this
clean.

## Where to look

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
