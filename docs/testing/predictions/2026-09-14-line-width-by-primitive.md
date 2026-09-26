# Prediction: the Line_width deficit is not uniform across primitive types

Registered 2026-09-14 on `c0c506dc`, before measuring.

## Where this stands

`line-width-first-gl-baseline.md` establishes: the deficit is in **width**, not
length or position (bounding boxes byte-identical); it is **per-line, not
global** (at width 4 some runs match exactly and others are narrower); and a
single scale factor therefore cannot be the fix.

That document names **angle** as the obvious candidate. **I am retracting that
candidate before testing it**, because reading the test source shows the
decomposition is something else.

## The test does not draw lines at varying angles

`line_width_tests.cpp`'s `Draw()` renders **seven different primitive types** in
a labelled grid, all at the one `NV097_SET_LINE_WIDTH`:

    PRIMITIVE_POINTS       16 verts   offset x   9..106  y  11..104
    PRIMITIVE_LINE_LOOP    16 verts   offset x 106..205  y   3..107
    PRIMITIVE_TRIANGLES     6 verts   offset x 232..310  y  19..102
    PRIMITIVE_QUAD_STRIP    6 verts   offset x   0..105  y 120..239
    ... plus TFan, Poly, Quad

all offset by `(x, y) = (640*0.25, 480*0.10) = (160, 48)`. The `Line_*` variants
draw these with fill off, so the closed primitives become outlines.

So the runs that match and the runs that do not are **different primitives**,
not different angles of one line. Angle may still vary within a primitive, but
primitive type is the decomposition the test was built to expose and it is
directly measurable from region masks.

## The prediction

**P1. The POINTS region is not governed by line width at all** and should
differ from the golden by an amount that does not track width. `glLineWidth`
cannot affect `PRIMITIVE_POINTS`; point size is a separate piece of state. If
the POINTS region's error DOES scale with the requested line width, something
is applying line width where it must not, and that is a finding in its own
right.

**P2. The deficit is concentrated in the closed primitives drawn as outlines**
(TRIANGLES, QUAD_STRIP, TFan, Poly, Quad) rather than in LINE_LOOP. LINE_LOOP is
native lines, where `glLineWidth` is exactly the right mechanism; the outlines
go through polygon-mode line rasterisation, where the hardware's edge rule and
GL's need not agree.

**P3. Consequently the per-region shares are uneven** -- this is the falsifiable
form. If every region carries the deficit in proportion to its painted area,
P2 is dead and the cause is something global after all, which would also
resurrect a scale-factor fix that `c0c506dc` argued against.

## Discriminators

Per-region, ours vs golden, across several widths: painted pixels, differing
channels, and whether each tracks the requested width.

- POINTS error flat in width -> P1 holds. POINTS error rising with width -> P1
  fails and line width is leaking into point rendering.
- Outline regions carrying disproportionate error -> P2 holds.
- Error share roughly proportional to painted area everywhere -> P3's falsifier,
  and both P1 and P2 are wrong.

## Not assumed

That the fix is in `gl/draw.c`. If the deficit is in polygon-outline
rasterisation, the relevant code may be the geometry stage or the polygon mode
setup, and `roundScreenCoords` in `glsl/vsh.c` is rasteriser-wide and off limits
without the owner. Naming that now so a result cannot later be read as licence.

---

## Outcome: all three falsified, and they take `c0c506dc` with them

Per-region, ours vs golden painted pixels. Ratio = ours/gold.

| primitive | w=1 | w=8 | w=32 |
|---|---:|---:|---:|
| POINTS | 0.947 | 0.837 | 0.808 |
| LINE_LOOP | 0.836 | 0.891 | 0.933 |
| TRIANGLES | 0.839 | 0.852 | 0.851 |
| QUAD_STRIP | 0.870 | 0.888 | 0.916 |
| TRIANGLE_FAN | 0.843 | 0.885 | 0.938 |
| POLYGON | 0.872 | 0.869 | 0.896 |
| QUADS | 0.885 | 0.895 | 0.922 |

**P1 falsified.** The POINTS region's error does NOT stay flat in width -- it
grows from 18 painted pixels at width 1 to 2,278 at width 32. But the golden
grows with it (19 -> 2,820), so `NV097_SET_LINE_WIDTH` genuinely does affect
point rendering on the hardware, and we follow it, just short. The prediction's
"if it scales, something is applying line width where it must not" was the wrong
reading: hardware applies it too.

**P2 falsified.** The deficit is NOT concentrated in the outline primitives.
LINE_LOOP -- native lines, where `glLineWidth` is exactly the right mechanism --
sits in the same band (0.836 / 0.891 / 0.933) as TRIANGLES (0.839 / 0.852 /
0.851) and QUAD_STRIP (0.870 / 0.888 / 0.916). Every primitive type carries the
same proportional shortfall.

**P3's falsifier is met.** The error share is roughly proportional to painted
area everywhere, so the cause is global after all.

## Which means `c0c506dc` is wrong and is corrected here

That commit concluded, from runs that matched exactly at width 4:

> some lines are already right and others are too thin. **A global multiplier on
> `glLineWidth` would break the lines that currently match**, and is the wrong
> shape of fix.

**That reading does not survive.** Sum the same runs instead of comparing them
one by one:

    width 4:  ours 42 / golden 48  = 0.875
    width 8:  ours 68 / golden 78  = 0.872
    width 16: ours 119 / golden 141 = 0.844

The runs that "match exactly" match because a 4-pixel run cannot be 4.6 pixels
wide -- they are integer roundings of a uniformly scaled width, not lines that
are already correct. Whole-image ratios agree: 0.897 to 0.927 across widths 1
to 48.

So a global widening is back as the right shape of fix, and the reason
`c0c506dc` rejected it was an artefact of comparing quantised runs individually
rather than in aggregate. **Compare the sums, not the items, when the items are
quantised.**

## Caveat on the width-32 column

The regions are vertex bounding boxes padded by half the line width, and at
width 32 they overlap: the per-region differing channels sum to 113.6% of the
whole image, so that column double-counts. The width 1 and width 8 columns sum
to 97.6% and 96.6% and are sound. The falsifications rest on those.

## Still not established

The exact form of the widening -- a factor, an offset, or a rounding rule --
and whether it is the same for points as for lines. The whole-image ratio is not
constant (0.897 to 0.927, non-monotone), so a single multiplier is the right
SHAPE but is not yet the right VALUE, and fitting one to these seven numbers
would be fitting to the corpus rather than deriving the rule.
