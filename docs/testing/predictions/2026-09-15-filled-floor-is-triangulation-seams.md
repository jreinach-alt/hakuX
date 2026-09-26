# Prediction: the filled one-step floor lies on triangulation seams

Registered 2026-09-15 on `6b04093e`, before measuring.

## Why this and not the AA arm

`3d-primitive-is-the-aa-surface.md` now carries a correction: normalised per
capture, the AA surface costs 1.19x on filled primitives, not the 78.8% its
share of the suite total suggested. The largest population in `3D_primitive` is
the **filled one-step floor**, present at 63,563-75,880 channels per capture in
**both** arms -- about 7.0M channels, mostly `|d| = 1`.

## The claim under test

That floor is already known **not** to be a single rounding convention: the sign
of `golden - ours` inverts by primitive.

| primitive | golden > ours at \|d\|=1 |
|---|---:|
| `QuadStrip` | **64.3%** |
| `Quads` | 42.0% |
| `TriStrip` | 38.0% |
| `Triangles` | 34.9% |
| `Polygon` | **22.0%** |
| `TriFan` | **21.9%** |

A rule that depends on the primitive *type*, for shapes the test draws at the
same place, is the shape of a **decomposition difference**: the same filled area
reaching the rasteriser as a different set of triangles, so interpolated values
land a step differently along whichever diagonal each decomposition chose.

**If that is what it is, the differing pixels have a spatial signature**: they
lie on thin linear structures -- the seams -- not spread through the filled
interior.

## Predictions

**P1 -- thinness.** On a non-AA filled capture (no AA confound, the cleaner
substrate), the `|d| = 1` pixels are predominantly **thin**: for most differing
pixels, a majority of their four neighbours do **not** differ. Quantified: the
mean count of differing 4-neighbours is **below 2.0**, and the fraction of
differing pixels with 3 or 4 differing neighbours is **below 35%**.

**P2 -- linearity.** Those thin structures are straight and diagonal, matching a
quad or fan decomposition, rather than following the primitive's outline.

**P3 -- primitive dependence.** `Quads` (one diagonal per quad) and `TriFan`
(all seams radiating from one vertex) show visibly different seam layouts, and
their sign bias differs (42.0% vs 21.9%) in the same direction as their seam
geometry differs.

## What kills it

- **P1 failing** -- differing pixels forming solid regions, mean neighbour count
  at or above 2.0 and a large fraction fully surrounded. Then the floor is
  interpolation precision spread over the whole filled area, not a seam, and
  the decomposition story is wrong. That is the outcome I consider most likely
  to be uncomfortable, because a floor spread everywhere is largely not ours to
  fix and would make ~7.0M channels of this suite unactionable.
- P1 holding but P2 failing -- thin but following outlines -- would mean edges,
  not seams, and points at rasterisation rules instead.

## Controls

**C1 -- the background must not differ at all.** Any differing pixel outside the
drawn primitives means the measurement is picking up the test's own label or
clear colour, and the thinness statistic is meaningless.

**C2 -- restrict to `|d| <= 3`.** The floor is the claim; the small tail of
large differences is a different population and must not be allowed to
contaminate a shape statistic.

**C3 -- compare against a shuffled control.** Scatter the same number of
differing pixels at random over the same bounding area and compute the same
neighbour statistic. Thin structure has to beat random placement, not merely
look small.

## Scope

Decomposition of filled primitives into triangles happens before the
rasteriser. If this holds, the fix is unlikely to be in `gl/*.c` -- another
handover. Registering it anyway: whether 7.0M channels are seams or an
unfixable precision floor is worth knowing regardless of who owns the answer.

---

## Outcome: P1 FALSIFIED. The floor is solid area, not seams.

Non-AA filled captures, `|d| <= 3` only, label band excluded:

| capture | differing px | C1 bg-diff | mean differing 4-nbrs | >=3 nbrs | shuffled mean | shuffled >=3 |
|---|---:|---:|---:|---:|---:|---:|
| `Quads` | 25,059 | **0** | **2.56** | **57.1%** | 1.05 | 5.8% |
| `TriFan` | 31,863 | **0** | **3.29** | **81.1%** | 1.70 | 21.0% |
| `QuadStrip` | 68,644 | **0** | **3.22** | **80.1%** | 2.71 | 61.2% |
| `Polygon` | 47,691 | **0** | **3.08** | **77.2%** | 1.89 | 27.3% |
| `Triangles` | 10,171 | **0** | **3.39** | **77.0%** | 0.50 | 0.7% |
| `TriStrip` | 35,124 | **0** | **2.98** | **68.2%** | 1.66 | 19.7% |

P1 asked for a mean below **2.0** and fewer than **35%** with three or four
differing neighbours. **Every primitive fails both bounds**, most of them
badly: means of 3.0-3.4 out of a maximum of 4, and 68-81% of differing pixels
fully or almost fully surrounded by other differing pixels.

Those are **solid regions**. A seam would have produced the opposite -- a mean
*below* the shuffled control, because a one-pixel-wide line has at most two
neighbours on it.

**C1 passed**: zero differing pixels where both sides are background, in every
capture, so the statistic is not picking up the label or the clear colour.

**C3 is informative rather than reassuring.** The real data is more clustered
than random placement of the same count (`Triangles` 3.39 against 0.50), so the
differences are structured -- just structured into **areas**, not lines.

**P2 and P3 not reached.**

## What this means, including the part I do not like

This file named the falsifying outcome in advance as the uncomfortable one, and
that is the one that happened. The decomposition story is wrong: the
one-step floor is spread across the filled interior.

So for `3D_primitive`'s largest population -- about 7.0M channels, present at
63,563-75,880 per capture in both the AA and non-AA arms -- what is now
established is:

- it is **not** one rounding convention (the sign inverts by primitive),
- it is **not** triangulation seams (this measurement),
- it is **not** the AA surface (1.19x per capture on filled),
- it **is** `|d| = 1` over solid areas of every filled primitive.

That is the signature of interpolation or precision differences across the
whole rasterised area, which is the least actionable shape a residual can have
and the hardest to attribute to any one file. **I am not calling it unactionable
on this evidence** -- that is a judgement, and `43fc3f43` already falsified one
floor reading of mine. But three specific mechanisms are now excluded, and
anyone picking this suite up should know they are excluded before spending a
cycle re-deriving them.

The parts of `3D_primitive` that remain concretely actionable are small and
already reported: the **7 dropped points** under AA (`5bd3de52`), and the
**6.13x-per-capture LINES displacement** under AA.
