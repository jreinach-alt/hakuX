# 3D_primitive: the axis that matters is the AA surface, not the smooth flags

Measured on `5b707602`, OpenGL, the 160 captures in
`/tmp/pgraph-run/score_cx_attr`, scored against `/tmp/goldens/results/3D_primitive`.
7,254,492 differing channels; `corpus-residual-triage.md` ranks the suite fourth
by actionable channels at 6,664,407.

Capture names encode three axes -- `<Primitive>-<submission>-<ls>-<ps>` -- and
all three were pivoted before any hypothesis.

## The submission path is irrelevant

| submission | n | differing | share |
|---|---:|---:|---:|
| `default` | 40 | 1,814,762 | 25.0% |
| `inlinearrays` | 40 | 1,814,101 | 25.0% |
| `inlineelements` | 40 | 1,812,834 | 25.0% |
| `inlinebuf` | 40 | 1,812,795 | 25.0% |

Within 2,000 channels of one another across 1.81M. **The vertex submission path
is not the defect**, and the geometry reaching the rasteriser is the same on all
four. That is a clean negative and it is worth having: four of the sixteen
variants per primitive can be treated as replicates from here on.

## `-ls` and `-ps` are NOT a smoothing axis

They look like line-smooth and poly-smooth, and they are
(`NV097_SET_LINE_SMOOTH_ENABLE`, `NV097_SET_POLY_SMOOTH_ENABLE`,
`three_d_primitive_tests.cpp:955-956`). But at `:936` the test does something
else when **either** is set:

```c
if (line_smooth || poly_smooth) {
    const uint32_t kAAFramebufferPitch = host_.GetFramebufferWidth() * 4 * 2;
    ...
    host_.SetSurfaceFormat(..., TestHost::AA_CENTER_CORNER_2);
}
```

It switches the render surface to **`AA_CENTER_CORNER_2` multisampling at double
pitch**, renders into texture memory, and resolves back at `:1024`. So the real
axis is **AA surface on or off**, and the smooth flags ride on top of it.

This was caught by a cross-tabulation that made no sense under the naive
reading: `-ls` moved the **filled** residual by +16.4%, and line smoothing
cannot touch a filled primitive.

## Re-pivoted on the axis the test actually varies

| arm | n | differing | share | abs-sum | mean \|d\| | exact |
|---|---:|---:|---:|---:|---:|---:|
| **no-AA** | 40 | 1,539,200 | 21.2% | 1,618,016 | **1.05** | 4 |
| no-AA / FILLED | 24 | 1,525,516 | | 1,589,760 | 1.04 | 0 |
| no-AA / LINES | 12 | 13,684 | | 28,256 | 2.06 | 0 |
| no-AA / POINTS | 4 | **0** | | 0 | 0.00 | **4** |
| **AA** | 120 | 5,715,292 | **78.8%** | 18,560,487 | **3.25** | 0 |
| AA / FILLED | 72 | 5,463,420 | | 13,853,666 | 2.54 | 0 |
| AA / LINES | 36 | 251,620 | | 4,681,453 | 18.61 | 0 |
| AA / POINTS | 12 | 252 | | 25,368 | **100.67** | 0 |

**78.8% of the suite is the AA-surface arm.** Without it the residual is a
one-step floor: mean \|d\| 1.05 over 1.54M channels, 87.7% of them exactly 1.

### The sharpest datum is Points

**Points are byte-exact in all four non-AA captures and differ at mean \|d\|
100.67 in all twelve AA captures.** A points capture has no lines to smooth and
no polygons to smooth, so nothing in the smooth flags can apply to it. That
isolates the AA surface path on its own, with a byte-exact control sitting
beside it.

It is also small -- 252 channels, 84 per flag combination, identical for `ls`,
`ps` and both -- which makes it the cheapest possible place to look next.

## The one-step floor is real but is NOT one rounding convention

`predictions/2026-09-15-3d-primitive-is-a-rounding-floor.md` asked whether the
`|d| == 1` differences are a signed convention like the tie-rounding already
established in `image-blit-residual-is-not-the-blit.md`. Sign of `golden - ours`
over `|d| == 1`:

| group | golden > ours | ours > golden | split |
|---|---:|---:|---:|
| FILLED (all) | 2,458,375 | 3,669,620 | 40.1% |
| `QuadStrip` | 1,148,560 | 636,604 | **64.3%** |
| `Quads` | 304,567 | 419,772 | 42.0% |
| `TriStrip` | 399,588 | 652,316 | 38.0% |
| `Triangles` | 113,816 | 212,068 | 34.9% |
| `Polygon` | 280,324 | 992,804 | **22.0%** |
| `TriFan` | 211,520 | 756,056 | **21.9%** |

**P1 and P3 are falsified.** `QuadStrip` leans 64% one way and `Polygon` and
`TriFan` lean 78% the other. Opposite directions on the same axis is not one
convention.

It is **not noise either**, and the prediction's own kill condition is what
settles that: it named "inside 55/45" as the symmetric case, and neither the
40.1/59.9 aggregate nor the per-primitive splits are anywhere near it. Something
systematic differs **by primitive type**, which is the shape of a decomposition
difference -- the same filled shape reaching the rasteriser as a different set
of triangles -- rather than a global rounding rule. Untested.

### Control C1 passed, and C2 found something

C1 required the LINES subset to show a different profile, and it does: `|d| == 1`
splits 47.4% (symmetric) while `|d| >= 16` splits **80.9% golden > ours**, and
`Lines` alone is **88.8%**. FILLED's `|d| >= 16` is 40.1%.

**On line primitives, the hardware paints where we do not.** That is the same
character found in `Line_width` -- the golden holding content we do not produce
anywhere nearby -- and here it is concentrated in 77,184 channels rather than
spread over millions.

## Where this leaves the triage ranking

`corpus-residual-triage.md` ranks `3D_primitive` fourth at 6,664,407 actionable
channels. That number is not wrong, but it is **one label over two populations**:
1.54M of one-step differences with no AA surface, and 5.72M with one. Anyone
picking the suite up from the ranking alone would spend their time on the wrong
half. Noted here rather than by editing the ranking, because the ranking's own
caveat already says `golden_colours` is a property of (golden, our output).

## Ownership, stated rather than assumed

`pgraph.h:521` models `AA_CENTER_CORNER_2` by doubling the surface **width
only**. The consumers are `gl/draw.c` (scissor), `gl/surface.c` (surface
sizing), `glsl/vsh.c:643` and `glsl/psh.c:2996-3016`.

`gl/*.c` is `[lane.remote]`. **`glsl/vsh.c`, `glsl/psh.c` and `pgraph.h` are
not** -- `psh.c` is explicitly `[free]`, and `vsh.c` holds `roundScreenCoords`,
which is rasteriser-wide and needs the owner. So the AA lead is **partly** in
this lane and cannot be finished inside it without a grant.

Nothing is edited here.

`docs/testing/suite_residual_pivot.py` reproduces every table above.
