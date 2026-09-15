# Prediction: `Attrib_carryover`'s residual is `3D_primitive`'s filled ±1 floor, not a carryover defect

Registered 2026-09-15, BEFORE the measurements below. Nothing here is edited
after the fact; corrections go in the results doc.

## What is already measured (and is why this prediction exists)

Baseline over all 96 captures against `/tmp/goldens/results/Attrib_carryover`:

- **2,923,650 differing channels**, mean |d| 1.16.
- **|d| is capped at 2.** 83.77% at exactly 1, 16.23% at exactly 2, **nothing above**.
- `T` (triangles) 2,896,815 / 48 captures = 60,350 per capture; `L` (lines)
  26,835 / 48 = 559. Triangles carry 99.1%.
- **Eleven of the twelve attributes produce BYTE-IDENTICAL difference maps**
  (`np.array_equal` true, zero differing pixels between the maps). Only `d`
  (diffuse) differs.
- The colour axis in the capture names is **perfectly confounded** with the draw
  mode -- `kTestConfigs` in `attribute_carryover_tests.cpp` assigns one colour
  per mode, so `col` carries no independent information. Not an axis.

## The control that has already run, and what it settles

For each attribute, how much does the image move relative to the `w` capture --
**on our side and on hardware's side separately**:

| | ours-vs-ours(w) | GOLD-vs-GOLD(w) |
|---|---:|---:|
| T/da `t0` | 65,154 | 65,154 |
| T/da `bd` | 34,410 | 34,410 |
| T/ie `n` | 92,208 | 92,208 |
| L/da `fc` | 3,720 | 3,720 |

**46 of 48 comparisons are identical to the pixel**; only `d` differs, and by
under 0.3%. The test *does* discriminate -- the counts are large and differ per
attribute -- so this is not a blind instrument.

**Therefore attribute carryover is REPRODUCED, not ignored.** Our renderer
responds to all twelve attributes exactly as the hardware does. The in-lane
lead I opened this suite on -- `gl/vertex.c:110/205/207/224` and
`gl/draw.c:642-656`, the inline-value binding sites -- **is dead**. That code is
correct. This is my own rule firing: **an identical aggregate can mean
reproduced, not ignored** -- and here the manipulation-response is identical
too, which is the stronger version.

## Hypothesis

**H:** what is left -- |d| in {1,2} over triangle interiors, independent of
which attribute is exercised -- is the **same mechanism** as `3D_primitive`'s
filled ±1 floor (~7.0M channels, 63,563-75,880 per capture in both arms), i.e. a
colour interpolation/quantisation difference over solid rasterised interiors.

This is worth testing because the two suites reach the rasteriser by **different
vertex paths**: `Attrib_carryover` runs a real nv2a vertex program
(`attribute_carryover_tests.vshinc`), `3D_primitive` does not. If the same floor
appears under both, the floor is **not** in the vertex path.

## Predictions, with numeric kill conditions

- **P1 -- SOLID, not thin.** Differing pixels sit in areas, not on seams or
  edges: mean differing-4-neighbours **>= 2.5** (max 4) and **>= 55%** of
  differing pixels with **>= 3** differing neighbours.
  **KILL:** mean < 2.0 or fewer than 35% at >= 3 -> this is edge/seam-shaped and
  is a different population from the `3D_primitive` floor.

- **P2 -- same magnitude signature.** `3D_primitive`'s FILLED arm is likewise
  concentrated at tiny |d|: **>= 95%** of its filled-arm channels at |d| <= 2.
  **KILL:** more than 5% of the filled arm at |d| >= 3 -> the two are not one
  population on this evidence and the cross-suite claim drops.

- **P3 -- gradient-linked.** The floor tracks colour *interpolation*, not flat
  fill: the mean local colour gradient at differing in-primitive pixels exceeds
  that at non-differing in-primitive pixels by **>= 1.5x**.
  **KILL:** ratio inside **0.8-1.25** -> the floor is not gradient-linked and I
  have no mechanism.

- **C1 (control).** **Zero** differing pixels where both sides are background.
  If this fails the label/background is contaminating and every number above is
  suspect.

- **C2 (control).** Shuffled-position control for P1: the shuffled mean
  4-neighbour count must sit **materially below** the observed mean. If shuffled
  ~= observed, P1's "solid" reading is unearned -- the map is simply dense.

## The uncomfortable outcome, named in advance

**P1 and P2 hold but P3 fails.** That leaves a floor confirmed across two suites
and ~10M channels, reproduced under two different vertex paths, and **still
without a mechanism** -- and the in-lane lead already dead. If that is what
comes back I report `Attrib_carryover` as characterised-and-not-actionable and
stop, rather than reaching for a fourth framing. Three framings of the
`3D_primitive` floor have already failed; a fourth guess is not evidence.

The other uncomfortable outcome: **P2 fails**, which would mean I have been
treating two unrelated small-|d| populations as one because "±1 floor" is a
label that fits almost anything. That is exactly the error the aggregate rule
warns about, one level up.
