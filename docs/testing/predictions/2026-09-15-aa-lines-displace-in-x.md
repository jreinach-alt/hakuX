# Prediction: the AA line displacement is horizontal, because the AA surface doubles width only

Registered 2026-09-15 on `98767a5d`, before measuring.

## What is already established

`3D_primitive`'s AA arm costs **6.13x the non-AA rate per capture on LINES**
(6,989 against 1,140) -- much the largest AA-specific effect in the suite, now
that "78.8% of the suite" has been corrected to a capture count and the filled
floor shown to be present in both arms.

It is **displacement, not loss**: ours-only and gold-only pixel counts are
balanced in every AA line capture (146/153, 240/223, 297/279). Something moves;
nothing is rejected.

These are width-1 lines (`kDefaultWidth` is 8 eighths = 1.0), so the
axis-offset wide-line rule from `line-width-first-gl-baseline.md` does not
apply.

## The claim under test

`pgraph.h:521` models `AA_CENTER_CORNER_2` by **doubling the surface width and
nothing else**:

```c
case NV097_SET_SURFACE_FORMAT_ANTI_ALIASING_CENTER_CORNER_2:
    if (width) { *width *= 2; }
    break;
```

If the displacement comes from that doubling -- a coordinate scaled, rounded or
resolved differently in the widened axis -- then **it must be horizontal**.
Nothing in that path touches y.

## Predictions

**P1 -- axis.** Taking each gold-only pixel and the nearest ours-only pixel, the
displacement vectors are predominantly **horizontal**: `|dx| >= 1` with `dy = 0`
for a clear majority, and the mean `|dx|` at least twice the mean `|dy|`.

**P2 -- magnitude.** The modal `|dx|` is small and consistent -- one or two
pixels -- rather than spread. A wide spread would mean the lines are being drawn
differently, not moved.

**P3 -- the non-AA control differs.** The same statistic on the non-AA line
captures (1,140 channels per capture, a sixth the rate) is either much smaller
or not x-biased. If non-AA lines show the *same* horizontal displacement, it is
not the AA path and P1 holding would be a coincidence of a defect present
everywhere.

## What kills it

- **Vertical or isotropic displacement.** The width doubling cannot produce it,
  and the mechanism is something else -- most likely the `SZF_Z16` depth format
  or the render-to-texture composite, the other two legs of the three-way
  confound this arm carries.
- A displacement that is not consistent at all -- nearest-neighbour vectors
  scattered over many magnitudes -- would mean "displacement" was the wrong
  reading of the balanced counts, and the lines differ in shape rather than
  position.

## Controls

**C1 -- balance must hold in the measured set.** The ours-only and gold-only
counts must stay within ~20% of each other in the captures analysed. Nearest-
neighbour matching between unbalanced sets manufactures vectors.

**C2 -- exclude the label band.** The top 40 rows carry the test name, which
differs per capture.

**C3 -- report unmatched pixels.** Any gold-only pixel with no ours-only pixel
within a few px is not displacement; the fraction of those is the honest measure
of how much of the residual this explains.

## Scope

If P1 holds, the suspect is the width doubling in `pgraph.h:521` (**not this
lane's**) or how `gl/surface.c` (**mine**) sizes and resolves the doubled
surface. Which of the two is a further measurement, not something this
prediction settles.

---

## Outcome: P1 FALSIFIED — and C3 withdraws the framing this was built on

Gold-only pixels matched to the nearest ours-only pixel within 5 px, label band
excluded:

| capture | ours-only | gold-only | C1 imbalance | horizontal | vertical | mean \|dx\| | mean \|dy\| | **unmatched** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `Lines-ls` | 146 | 153 | 4.6% | 40.0% | 0.0% | 2.80 | 1.60 | **96.7%** |
| `LineStrip-ls` | 240 | 223 | 7.1% | 1.7% | **67.8%** | 0.90 | 2.19 | **73.5%** |
| `LineLoop-ls` | 297 | 279 | 6.1% | 1.7% | **58.6%** | 1.58 | 1.91 | **58.4%** |
| `Lines` | 3 | 3 | 0.0% | 0.0% | 0.0% | 3.00 | 3.00 | 66.7% |
| `LineStrip` | 1 | 4 | 75.0% | 0.0% | 50.0% | 1.50 | 2.00 | 50.0% |
| `LineLoop` | 1 | 4 | 75.0% | 0.0% | 50.0% | 1.50 | 2.00 | 50.0% |

**P1 is falsified.** Where a match exists at all the displacement is
predominantly **vertical** (67.8%, 58.6%), not horizontal. `Lines-ls`'s 40%
horizontal is two pixels out of the five that matched, which is nothing. The
width-doubling story predicted the one axis the data does not show.

**C1 held** on the three AA captures (4.6-7.1% imbalance) and **failed** on the
non-AA ones, which have one to four pixels each -- far too few to support P3,
so the non-AA control is simply absent rather than negative.

### C3 is the real result, and it costs me a published claim

**58.4% to 96.7% of gold-only pixels have no ours-only pixel within five
pixels.** They are not paired. They are in different places.

`3d-primitive-is-the-aa-surface.md` and PR comment 5678812384 say of the AA line
captures: *"every line capture in the AA arm is balanced (146/153, 240/223,
297/279), which is displacement."* **That inference is withdrawn.** Balanced
totals mean neither side systematically paints more than the other. They do
**not** mean the pixels moved -- that is a spatial claim, and it needed a
spatial measurement, which is the one just run.

What the balance does still license, and all it licenses: the AA line residual
is **not** a one-sided rejection like the seven dropped points. Beyond that,
whether the lines are shifted, differently shaped, or differently
anti-aliased is **unmeasured**.

### The rule this earns

**An aggregate cannot license a spatial claim.** Balanced counts, a sign split,
a magnitude histogram -- none of them say where anything is. Three of my own
readings have now failed at exactly this joint: the boundary-shift floor
(`43fc3f43`), the triangulation seams
(`2026-09-15-filled-floor-is-triangulation-seams.md`), and this. In two of the
three the spatial measurement was cheap and I reached for the aggregate first.

## What is actually left of this lead

The AA line residual is 6.13x the non-AA rate per capture and remains the
largest AA-specific effect in the suite. But it is now **uncharacterised**: not
loss, not shown to be displacement, and carrying the three-way confound (AA mode
+ `SZF_Z16` + render-to-texture) that this arm has had all along.

A next instrument would have to work on the lines themselves -- sampling across
and along a known segment, as `line_width_axis_offset.py` does -- rather than on
difference-map statistics. Registering that as the shape of the next attempt,
not starting it here.
