# Line_width under OpenGL, measured for the first time

`iso_line` aborted until `5b707602`, so this suite had never been scored under
the GL renderer. Measured on that commit: **61 captures, 1 exact, 4,514,611
differing channels**, of which 4,462,131 is structural and discriminating
(`golden_colours` ~ 2,990 on the large captures, so these captures have real
discriminating power -- see `corpus-residual-triage.md`).

This is a first baseline and a characterisation, not a fix.

## The error is monotonic in width, and there are two clean boundaries

| width | differing channels | painted px (ours) | painted px (golden) | ours/gold |
|---:|---:|---:|---:|---:|
| 0.0 | **0** | 3,104 | 3,104 | **1.000** |
| 1.0 | 5,737 | 6,155 | 6,677 | 0.922 |
| 4.0 | 21,075 | 14,524 | 16,192 | 0.897 |
| 8.0 | 42,095 | 24,105 | 26,827 | 0.899 |
| 16.0 | 76,243 | 38,926 | 42,870 | 0.908 |
| 32.0 | 129,362 | 59,581 | 64,780 | 0.920 |
| 63.0 | 201,403 | 84,938 | 90,802 | 0.935 |
| 63.875 | **202,486** | | | |
| 64.0 | **5,737** | 6,151 | 6,673 | 0.922 |
| 64.875 | 5,737 | | | |
| `FFFFFFFF` | 5,737 | | | |

**Width 0 is byte-exact.** 3,104 painted pixels on both sides, zero differing
channels -- the only exact capture in the suite.

**Everything at width >= 64 collapses**, and collapses on BOTH sides. 64.0
through 64.7 and the `FFFFFFFF` capture all give *exactly* 5,737 differing
channels, and 5,737 is also width 1.0's figure. Ours paints 6,151 against the
golden's 6,673 there -- the same ratio as width 1. So the hardware collapses at
64 too, and this range is very nearly right; it is not where the defect is.

## The defect is the 1.0 to 63.7 range, and we paint too FEW pixels

Ours is smaller than the golden at every width from 1 upward, by 6% to 10%,
and the absolute gap grows with width: 522 px at width 1, 2,722 at 8, 5,199 at
32, 5,864 at 63. The tallest painted column grows the same way -- 120 against
the golden's 125 at width 1, 310 against 348 at width 63.

Our lines are systematically **thinner than the hardware's**.

## The obvious cause is ruled out, from this data alone

`gl/draw.c` clamps to `supported_aliased_line_width_range[1]` /
`supported_smooth_line_width_range[1]`, so a driver whose maximum line width is
below 63.875 would make us draw too thin -- exactly the symptom.

**It is not that.** If we were clamping at some maximum W, every width above W
would paint IDENTICALLY. The painted count rises without a plateau all the way
to 63.0 (6,155 -> 84,938, monotone), so no clamp is binding below 63.875. No probe
was needed to rule this out; the curve already says so.

So the deficit is a rasterisation difference rather than a clamp, and that is
where the next instrument goes.

## Not concluded

Whether the deficit is in the line's WIDTH, its LENGTH, or its end caps. The
tallest-column figures point at width, but "painted pixels" confounds all three
and this document does not pretend to separate them. Nor is it established
whether the 4.46M is one mechanism or several -- 60 of 61 captures classify
structural, which says only that they are not one-step or boundary-shift.

`Line_FFFFFFFF`, `Fill_0000.0` (41,533), `Fill_0001.0` (43,083) and
`Fill_0032.0` (70,357) are in this suite too and are not analysed here.

## Reproduce

    bash /tmp/pgraph-run/runx_gl.sh <bin> /tmp/pgraph-run/iso_line.iso <tag> line

then score `score_<tag>/<tag>` against `/tmp/goldens/results/Line_width`. The
captures used here are `/tmp/pgraph-run/score_lfix/lfix` at `5b707602`.


---

## Correction and refinement, same day

### The capture names are eighths, not tenths

`line_width_tests.cpp` builds its widths as `fixed_t` in **1/8 units**
(`kDefaultWidth = 1 << 3`), and the capture name spells the fraction as eighths.
So `Line_0063.7` is width 63 + 7/8 = **63.875**, not 63.7, and `Line_0064.7` is
64.875. Corrected above. The shape of the finding is unaffected -- the collapse
boundary is still exactly 64.0 -- but the labels were wrong and the per-unit
arithmetic derived from them was wrong with them.

### It is the WIDTH. Not the length, not the position.

The document above left width/length/end-caps unseparated. They separate
cleanly, and it needed no probe either:

**The bounding boxes are identical.** On `Line_0016.0`, ours and the golden both
paint y=[25,479] x=[20,484]. Same extent, same position, same endpoints. So the
deficit is not length, not placement, and not a global scale.

**The runs differ.** Scanning one row, ours gives `[16, 16, 28, 21, 16, 16, 16]`
against the golden's `[16, 17, 28, 29, 34, 18]`. Ours sits at exactly the
requested 16; the golden runs wider. Where the golden's lines widen enough to
touch, they merge -- 6 runs against our 7 -- which is why the painted-pixel gap
grows with width even though each line is only slightly wider.

### And it is NOT a uniform factor, which rules out the easy fix

At width 4 the runs pair up as

    ours   [4, 4, 6, 7, 13, 4, 4]
    golden [4, 4, 8, 9, 13, 4, 6]

Runs 1, 2, 5 and 6 match **exactly**; runs 3, 4 and 7 are narrower in ours. At
width 8: ours `[8, 8, 36, 8, 8]`, golden `[8, 9, 40, 9, 12]` -- again the first
matches exactly and the others do not, by differing amounts.

So some lines are already right and others are too thin. **A global multiplier
on `glLineWidth` would break the lines that currently match**, and is the wrong
shape of fix. The difference tracks something per-line -- angle is the obvious
candidate, since GL specifies line width perpendicular to the line and other
rasterisers widen along the major axis instead, which differ by up to sqrt(2) on
a diagonal.

**That candidate is NOT established here** -- it is named so the next
measurement has something to falsify, not offered as the answer. What is
established is narrower and solid: the deficit is in width, it is per-line
rather than global, and a single scale factor cannot be the fix.


---

## Correction: "per-line, not global" was wrong

The section above concludes that some lines are already correct, that a global
multiplier would break them, and that angle is the likely per-line variable.
**All three are retracted.** Measured per primitive type
(`predictions/2026-09-14-line-width-by-primitive.md`), the ours/golden painted
ratio is uniform across every primitive -- LINE_LOOP 0.891, TRIANGLES 0.852,
QUAD_STRIP 0.888, TRIANGLE_FAN 0.885, POLYGON 0.869, QUADS 0.895 at width 8 --
so the shortfall is global, not per-line.

The runs that appeared to "match exactly" are integer roundings of a uniformly
scaled width. Summed rather than compared item by item: 42/48 at width 4, 68/78
at width 8, 119/141 at width 16. A global widening is the right shape of fix
after all.

The lesson is the general one: **compare the sums, not the items, when the items
are quantised.** Comparing quantised runs individually manufactured a per-line
story out of a global effect.

---

## Measuring a VERTICAL edge changes the picture again

Everything above measures painted-pixel totals over the whole frame, which mixes
every line angle together. Isolating one edge where the geometry is trivial --
the `QUAD_STRIP`'s vertical edges at screen x=160 and x=265, where a line's
horizontal run IS its width, no trigonometry -- gives a much sharper answer.

### The width is EXACT

| requested | ours | golden |
|---:|---:|---:|
| 3, 4, 5, 6, 7, 8 | 3, 4, 5, 6, 7, 8 | identical |
| 9, 10, 11, 12 | 9, 10, 11, 12 | identical |
| 13, 14, 15, 16 | 13, 14, 15, 16 | identical |
| 24, 32, 40, 48 | 24, 32, 40, 48 | identical |

**Zero difference at every integer width from 1 to 48**, on both vertical edges.
The rendered width of a vertical line is exactly the requested width in ours and
in the hardware. So "our lines are systematically thinner" -- the headline of
this document -- is **wrong as a statement about width**. It is true only as a
statement about painted-pixel totals over a frame that is mostly diagonals.

### Two real differences, both precise

**1. Odd widths are offset one pixel.** At x=160: ours starts at 159 where the
golden starts at 160 (w=1), 158/159 (w=3), 157/158 (w=5), and so on through
w=15. Even widths start identically -- 158/158, 156/156, 152/152, 144/144.
Reproduced independently at x=265: 264/265, 263/264, 262/263, 261/262, 260/261,
259/260, 257/258, with every even width matching.

So for an ODD line width we place the line one pixel left of where the hardware
puts it. The width is right; the centring convention is not.

**2. Fractional widths round differently.** Requested 1.125, 1.250 and 1.375 give
2 on the hardware and 1 from us; 1.500 upward gives 2 from both. That is the
hardware taking a ceiling where we round to nearest.

### And this partly reinstates what `d902a5cd` retracted

`d902a5cd` falsified the per-primitive predictions and concluded the deficit was
global, retracting angle as a candidate. The vertical-edge measurement says
otherwise: if vertical lines are width-exact and the whole frame is still ~0.9x,
the deficit must live on the NON-vertical lines. **The angle dependence is back**,
now on a direct measurement rather than a guess.

`d902a5cd`'s per-primitive test could not have seen this: every primitive in the
grid is mostly diagonal edges, so a uniform ratio across primitives is exactly
what an angle-dependent rule produces. That test was not wrong, it was
unable to discriminate -- which is a different failure and worth the distinction.

### What is established now

- Vertical lines: width exact at every integer 1..48, both edges.
- Odd widths: our line is one pixel left of the hardware's. Even widths agree.
- Fractional widths: hardware ceilings, we round to nearest.
- The bulk of the 4.46M is on non-vertical lines and is explained by NONE of the
  above. It has not been measured.

### What is NOT established

The rule for diagonals, which is where the residual actually lives. Also whether
the odd-width offset is fixable in `gl/draw.c` at all -- it may be a GL-versus-
hardware centring convention that only moves by shifting geometry, and
`roundScreenCoords` in `glsl/vsh.c` is rasteriser-wide and needs the owner.
Nothing here licenses touching it.

Rows at w >= 13 on the x=265 edge, and w >= 56 on x=160, are merged runs where
the edge has met a neighbour; they are excluded above rather than read as widths.


---

## Thickness is correct at every angle, so the angle reading is doubtful too

The section above concludes from vertical edges that thickness is exact at 90
degrees and infers, from the frame-wide total still being ~0.9x, that "the angle
dependence is back". Measured directly
(`predictions/2026-09-15-line-width-square-pen.md`): thickness is **1.000 of the
golden's** at 3.3, 10.1, 19.6 and 77.7 degrees, at widths 4 and 8, on every
segment where the instrument's control passes.

So there is no angle dependence in the thickness, and that inference is
withdrawn. It was drawn from a frame-wide aggregate -- the same mistake as
before, one level down.

The surviving candidate is **line joins**, from the contaminated rows: where two
wide segments meet, the golden reads far wider than ours and our own thickness
dips BELOW the requested width, which is what a notch looks like. A candidate,
not a finding -- it rests on readings whose whole point is that they cannot be
trusted, and it needs its own instrument, control and registered prediction.

---

## The residual is COLOUR, not geometry, and I spent eight hypotheses on geometry

Splitting the differing pixels three ways -- painted only by the golden, painted
only by us, and painted by BOTH with different colours:

| | W=8 | W=32 |
|---|---:|---:|
| gold-only (we leave background) | 2,827 | 5,804 |
| our-only | 105 | 605 |
| **both painted, different colour** | **15,219** | **48,304** |

**84% of the residual at W=8 and 88% at W=32 is pixels both renderers paint,
disagreeing about the colour.** The geometry -- who paints where -- accounts for
about one pixel in seven.

Every hypothesis in the ledger above is about geometry: clamp, per-primitive
concentration, global scale, square pen, angle-dependent thickness, joins,
position offset, boundary-shift floor. Eight, all refuted, all aimed at the
minority term. They were motivated by "we paint ~10% fewer pixels", which is
true and is the wrong metric: **painted-pixel COUNT cannot see a colour
difference at all.**

That is the same lesson as `compare the sums, not the items` and `an aggregate
over mixed cases hides the rule`, one level up: the metric chosen at the start
determined which hypotheses were even thinkable.

### What the colour difference looks like

Per channel, ours-low against ours-high is 2,200/2,715, 2,709/2,902,
2,783/2,354 at W=4 -- **roughly symmetric**, so not a scale error. And it
degrades sharply with line width:

| | W=4 | W=8 | W=32 |
|---|---:|---:|---:|
| \|d\| <= 1 | 63.6% | 41.8% | **18.4%** |
| \|d\| <= 4 | 92.9% | 80.5% | 35.2% |
| \|d\| > 16 | 3.0% | 5.7% | **29.7%** |

At W=4 most shared pixels are within one step -- ordinary precision. At W=32
nearly a third differ by more than 16, with max\|d\| around 200: completely
different colours.

### The candidate, named with its falsifier

The test Gouraud-shades: `SetDiffuse(kPalette[i])` per vertex, so colour is
interpolated. GL interpolates a wide line's colour **along** the line only --
every fragment across the width shares the value at that parametric position. If
the hardware also varies colour **across** the width, the disagreement would be
zero at W=1, grow with width, and be symmetric -- which is what the table shows.

**Falsifier:** sample the colour across the line's width at a fixed position
along it. If ours is constant across the width and the golden's varies, the
candidate holds. If both are constant across the width and differ only along it,
the candidate is dead and the difference is in the interpolation ALONG the line
-- which would make it the same defect class as `Image_blit`'s residual, already
established as vertex-colour interpolation and already known not to be
`gl/blit.c`'s.

Not tested here. Registered as the next instrument with the discriminator fixed
in advance.

## MECHANISM FOUND: we interpolate colour ACROSS a wide line's width; the hardware does not

The registered falsifier was: sample colour across the line's width at a fixed
position along it; ours constant and the golden's varying confirms the
cross-width candidate. **The measurement inverts it.**

Clean 77.7-degree segment, three positions along the line, sampling every pixel
across the width:

| W=32, position | distinct colours ours | distinct colours gold |
|---|---:|---:|
| s=0.35 | **8** | 5 |
| s=0.50 | **8** | 5 |
| s=0.65 | **8** | 4 |

and the values at s=0.50, first / middle / last across the width:

    ours  (143,163,255)  (155,151,255)  (255,112,194)
    gold  (155,151,255)  (155,151,255)  (154,152,255)

**The golden is constant across the width** -- R spans 154 to 155 -- and **ours
is not**, spanning R 143 to 255 and G 163 to 112. Our far edge is a completely
different colour from our near edge. At W=8 the same measurement shows ours with
2-3 distinct values against the golden's 3-4, all within a few steps: the effect
is there but small, because a narrow line has little width to go wrong across.

### What that means

The hardware gives a wide line **one colour across its width** -- the
interpolated vertex colour at that parametric position ALONG the line, which is
what a line primitive means. We expand the wide line into geometry and then
interpolate the vertex colours across that geometry, **including across the
width direction**, so one edge of the line drifts toward a different vertex's
colour.

This accounts for every measured property of the residual:

- **84-88% of it is commonly-painted pixels differing in colour**, not geometry.
- It is **roughly symmetric per channel** -- one edge drifts one way, the other
  the other, so neither sign dominates.
- It **grows sharply with width** -- zero cross-width at W=1, and at W=32 nearly
  a third of shared pixels differ by more than 16.
- The **geometry is right**: thickness exact at every angle, verticals exact at
  every integer width. We draw the right shape and fill it wrongly.

Nine hypotheses were tested; eight were geometric and all eight were refuted.
This is the first positive mechanism, and it was reached by abandoning
painted-pixel count as the metric.

### Ownership, stated rather than assumed

Wide-line expansion happens in the geometry stage. `glsl/geom.c` is `[free]` in
`territory.toml` -- **unclaimed, and NOT this lane's** -- and `roundScreenCoords`
in `glsl/vsh.c` is rasteriser-wide and needs the owner. This is a finding and its
evidence, handed over. No code is touched here.

### Not established

That the fix is a flat-shaded varying across the width rather than something
subtler -- the golden's 4 to 5 distinct values are not literally one colour, and
whether that residual variation is dithering, precision, or a real gradient has
not been measured. And this is one segment of one primitive at two widths;
confirming it wants the same measurement on a second angle and a second
primitive before anyone edits a shader on the strength of it.
