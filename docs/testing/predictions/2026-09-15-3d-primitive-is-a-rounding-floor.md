# Prediction: 3D_primitive's bulk is a signed rounding convention, or it is noise

Registered 2026-09-15 on `fb60b5fc`, before measuring the sign.

## What is already measured

160 captures in `/tmp/pgraph-run/score_cx_attr`, 7,254,492 differing channels.
Capture names encode three axes and all three were pivoted before any hypothesis:

**Submission path is irrelevant.** `default`, `inlinearrays`, `inlineelements`
and `inlinebuf` come out at 25.0% each, within 2,000 channels of one another
across 1.81M. The vertex submission path is not the defect, and the geometry
reaching the rasteriser is the same on all four.

**Primitive class splits it, and the two halves have opposite character:**

| group | differing | \|d\| <= 3 | \|d\| >= 16 |
|---|---:|---:|---:|
| FILLED (Quad/Tri/Polygon) | 6,988,936 | **96.8%** | 2.1% |
| LINES (Lines/Strip/Loop) | 265,304 | 42.5% | **29.1%** |
| POINTS | 252 | 0.0% | 85.7% |

**87.7% of the filled residual is exactly \|d\| = 1.** Points are byte-exact in
all four non-smoothed captures.

So the 6,664,407 channels that `corpus-residual-triage.md` calls actionable for
this suite are, overwhelmingly, single-step differences on filled primitives.

## The claim under test

A million channels off by exactly one is either a **convention** or **noise**,
and the sign distribution tells them apart. `image-blit-residual-is-not-the-blit.md`
already established one such convention on this hardware -- **it rounds ties
up** -- so the shape is not hypothetical.

**P1.** The `|d| == 1` differences on filled primitives are systematically
signed: one direction holds at least 70% of them. That is a rounding convention,
it is nameable, and it is worth someone's time.

**P2.** If P1 holds, the direction is `golden > ours`, matching the tie-rounding
already established in `Image_blit`.

**P3.** The sign is consistent across the six filled primitive types. A split
that depends on primitive would mean it is not one convention.

## What kills it

A roughly symmetric split -- anywhere near 50/50, say inside 55/45 -- means
these are precision noise, not a convention. **Then the triage ranking I
published is wrong about this suite**, `3D_primitive`'s 6.66M is not actionable
in any useful sense, and `corpus-residual-triage.md` needs a correction saying
so.

## Control

**C1.** The LINES subset must show a *different* profile from FILLED on this
same measurement. They already differ by an order of magnitude in
`|d| >= 16` share, so if the sign test returns identical numbers for both, the
test is measuring something frame-wide rather than the defect.

**C2.** Report the sign split for `|d| >= 16` separately. A convention should
live in the small differences; if the large ones share the same strong bias,
this is not a rounding story.

## Why this matters beyond the suite

I published `corpus-residual-triage.md`'s ranking. If a suite it ranks fourth is
mostly a one-step floor, the ranking sends the next lane to the wrong place, and
I would rather correct my own table than have someone spend a day on it. I have
already falsified one floor reading of my own (`43fc3f43`, `Line_width`), so
this is not a reading I get to assume -- but unlike that one, **the magnitudes
here are measured rather than inferred**, and only the interpretation is open.

---

## Outcome: P1 and P3 FALSIFIED, P2 not reached, and the framing was superseded

**P1 falsified.** The `|d| == 1` differences on filled primitives split
2,458,375 / 3,669,620 -- **40.1% golden > ours**. The prediction asked for one
direction at 70% or better. It is a real bias but not that.

**P3 falsified, and decisively.** The sign is not consistent across primitives:

| primitive | golden > ours |
|---|---:|
| `QuadStrip` | **64.3%** |
| `Quads` | 42.0% |
| `TriStrip` | 38.0% |
| `Triangles` | 34.9% |
| `Polygon` | **22.0%** |
| `TriFan` | **21.9%** |

`QuadStrip` leans 64% one way while `Polygon` and `TriFan` lean 78% the other.
Opposite directions on the same axis is not one convention.

**P2 not reached**, since it was conditional on P1.

**But the kill condition was not met either.** This file named "inside 55/45" as
the symmetric case that would make the residual noise and my published triage
ranking wrong about this suite. Neither the 40.1/59.9 aggregate nor the
per-primitive splits are near that. **So it is not a convention and it is not
noise**, and the ranking is not corrected on this evidence.

Writing the kill condition as a number rather than "roughly symmetric" is what
made that a decision instead of a judgement call. Worth keeping.

**C1 passed.** LINES shows a different profile: `|d| == 1` splits 47.4%
(symmetric) while `|d| >= 16` splits **80.9% golden > ours**, `Lines` alone
**88.8%**, against FILLED's 40.1%. The test discriminates.

**C2 found something.** On line primitives the large differences are almost all
one-directional: **the hardware paints where we do not.** 77,184 channels, the
same character as `Line_width`'s residual and far more concentrated.

## The framing was wrong, and a cross-tab caught it

This file treated the suite as one population and asked whether it was a floor.
It is two populations. `-ls` and `-ps` are not merely smoothing flags:
`three_d_primitive_tests.cpp:936` switches the render surface to
**`AA_CENTER_CORNER_2` at double pitch** when either is set.

**78.8% of the suite is that AA arm.** The one-step floor this file is named
after is the *other* 21.2%.

The tell was a cross-tabulation with no hypothesis attached to it: `-ls` moved
the **filled** residual by +16.4%, and line smoothing cannot touch a filled
primitive. Pivoting on an axis I had no theory about is what exposed the axis
that mattered.

Full result in `investigations/3d-primitive-is-the-aa-surface.md`.
