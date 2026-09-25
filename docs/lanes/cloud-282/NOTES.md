# cloud-282: the nearest-sample tie-break rule (#282)

Desktop analysis over captures and goldens already on disk. No device run and no
build. Tool: `docs/lanes/cloud-282/tie_rule.py`.

## Outcome in two sentences

Silicon has no *sampler* tie rule to derive. On the checkerboard class (a), the
direction of a tie is set by **which triangle of the quad the pixel is in, on
which axis, and whether the draw is fixed-function**. A texel-index/fraction rule
cannot express that. It is interpolator arithmetic, and the rule that describes
it predicts **95.2% of the disputed tie pixels** (44.8% for what we draw today).
The bump class (b) is not a tie class at all: its edge shift changes sign with
the bump map's texture format on identical geometry.

**psh.c hunk:** `hw/xbox/nv2a/pgraph/glsl/psh.c:1955-1994` (`texelTieBias`, the
v half). **Recommend no grant.** The measured rule needs the triangle's identity
inside the quad, which the sampler cannot see, and a hack keyed on
`gl_PrimitiveID` parity would fit one helper's geometry and nothing else (see
"Do not repeat").

## The geometry, from source

`DrawCheckerboardUnproject` (pbkitplusplus `nv2astate.cpp:1518`) draws one
`PRIMITIVE_QUADS` over the whole 640x480 framebuffer with texcoords 0..1 on a
256x256 swizzled checkerboard. The four screen points are unprojected on the CPU
and re-transformed by the FF pipeline under the XDK viewport (offset 0.53125).
Our `roundScreenCoords` (vsh.c:562, truncate to 1/16) puts the vertices on the
same grid silicon uses, so **u = 0.4·x and v = (256/480)·y exactly**:

- every column x = 5k is an exact u tie (u = 2k);
- every row y = 15k is an exact v tie (v = 8k).

A tie only shows where it is also a checker cell edge (cell 8, 14, 20 or 24
texels per suite). The quad is two triangles split on (0,0)-(640,480):
**T1 = v0 v1 v2 (upper right, x >= 4y/3)** and **T2 = v0 v2 v3 (lower left)**.

## Method (regions, not points)

For each tie line in each capture, take the pixels whose two neighbours are two
*different checker tones of that suite* (so nothing is drawn over the edge
there), and read which neighbour the tie pixel copies: lower texel (D) or upper
texel (U). Read this separately in the golden and in our capture. A rule is
scored on every such pixel of every capture. Tones come from each suite's
`kCheckerboard*` constants (table in `tie_rule.py`).

Captures: `1790361615-arms-shadetie224b-base` (nova, apk 851650a27937, 09-25; all
lighting/specular/material suites), `1790347539-xbox-region200-dryrun` (thor,
a7b9d28e6b84; Combiner, and Lighting_control only where the first run lacks it)
and `z-sweep-079-Texture_border_color` (09-13). 157 captures with a checkerboard
and a golden. `Attrib_float` (z-sweep-005) yields no scorable pixel under its
tones and is excluded, not counted.

```
R=/home/justin/hakux-work/dispatch/results
python3 docs/lanes/cloud-282/tie_rule.py --score $R/1790361615-arms-shadetie224b-base-3530164 \
    $R/1790347539-xbox-region200-dryrun-3236568 $R/z-sweep-079-Texture_border_color
python3 docs/lanes/cloud-282/tie_rule.py --map   <same dirs>      # sign map below
python3 docs/lanes/cloud-282/tie_rule.py --tsv out.tsv <same dirs>  # per line, per capture
```

## What we render today

`texelTieBias` pushes every tie up on both axes, and the captures show it: on
the u axis and on every v tie from texel 136 up, the golden and our capture
agree on every scored pixel. **All** disagreement is on v ties at v <= 128.

## What silicon does: the sign map

Goldens pooled over the FF draws, one line per tie row (from `--map`):

```
v=  8 row  15  U0-19   D20-639
v= 24 row  45  U0-59   D60-639
v= 40 row  75  U0-99   D100-639
v= 56 row 105  U0-139  D140-639
v= 72 row 135  U0-179  D180-319 U320-479 D480-639     (isolated 1-3 px flips omitted)
v=104 row 195  ...     D264-319 U320-479 D480-639
v=120 row 225  U0-299  D300-319 U320-479 D480-639
v=128 row 240  U0-480  D481-639
v=136 row 255  U0-639  (and every row below it)
```

- The U/D boundary on rows 15-105 is **exactly the quad's split diagonal**,
  x = 4y/3: 20, 60, 100, 140 on rows 15, 45, 75, 105.
- In T2, every v tie goes up. In T1, v ties go down, except for a band at
  x 320-479 on rows 135-240 and for everything from row 255 on.
- **It is deterministic.** Over the FF draws only 93 of 19,717 tie pixels get
  votes both ways across tests. Silicon puts the same pixel on the same side
  in every test.

### Three facts that rule out a sampler rule

1. **Axis.** In the region where silicon rounds v ties down (T1, y <= 240), it
   rounds **u ties up on 208,535 of 208,758 pixels (99.9%)**. The same fragment
   resolves its two coordinates in opposite directions. A tie rule is a function
   of one coordinate's fraction and texel index, so it cannot do this.
2. **Triangle.** At one v texel (for example v = 40, row 75), the direction
   flips at x = 100 across the diagonal. Texel index and fraction are identical
   on both sides.
3. **Transform path.** Every test that binds a vertex program before drawing the
   checkerboard (`Lighting_control VS_*`, 16 tests, and the `*VS*` tests in
   Specular / Specular_back) has **0** down ties: 31,480 + 597 + 597 px in T1 at
   v <= 128, all up, as we render them. Caveat: those tests also draw the
   checkerboard through a different projection (the program's own), so this
   controls for "a VS draw" and not for identical vertices.

#9's "down below 128, up from 144" is a projection of fact 2. In this helper,
v <= 128 is the same set as y <= 240, and the T1 part of those rows is what goes
down. Texel index and screen row are collinear in every capture of class (a), so
**no capture on disk can separate a texel-index rule from a screen-position
rule**.

## Scores (tie pixels, every capture, regions)

`diag+FF` = down iff FF draw, v axis, v <= 128 and x >= 4y/3; otherwise up.

| suite | tie px | v<=128 px | current (up) v<=128 | #9 index v<=128 | **diag+FF v<=128** | diag+FF all ties | gain vs current |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lighting_spotlight | 237,998 | 71,350 | 33.7% | 66.3% | **100.0%** | 100.0% | 47,276 |
| Lighting_accumulation | 65,532 | 18,760 | 34.4% | 65.6% | **100.0%** | 100.0% | 12,310 |
| Material_color_source | 142,452 | 26,864 | 18.3% | 81.7% | **98.6%** | 99.7% | 21,552 |
| Lighting_control | 316,032 | 86,160 | 68.3% | 31.7% | **94.9%** | 98.6% | 22,984 |
| Specular | 171,174 | 24,919 | 43.2% | 56.8% | **91.0%** | 98.2% | 11,911 |
| Specular_back | 126,237 | 19,625 | 45.1% | 54.9% | **89.9%** | 98.1% | 8,793 |
| Texture_border_color | 22,959 | 6,920 | 33.9% | 66.1% | **90.1%** | 97.0% | 3,889 |
| Combiner | 91,346 | 26,504 | 37.8% | 62.2% | **87.4%** | 96.4% | 13,144 |
| Lighting_range | 15,925 | 3,579 | 34.2% | 65.8% | **84.4%** | 96.5% | 1,797 |
| **all (157 captures)** | **1,189,655** | **284,681** | **44.8%** | 55.2% | **95.2%** | **98.8%** | **143,656** |

Lighting_accumulation's gain, 12,310, equals the issue's figure for that suite
exactly. The issue's 179,074 counts every differing pixel on a tie row. This
table counts only the pixels where the edge is visible with nothing drawn over
it, so 143,656 is the part of that total a rule can be checked against.

**Controls (captures or pixels that are exact today, and must stay exact):**

| control | px | diag+FF keeps |
|---|---:|---:|
| u ties, all captures | 599,841 | 99.8% (up); the 1,172 golden "down" pixels are matched by our captures too (census: 0 u pixels where golden and ours differ) |
| v ties v >= 136 | 305,133 | 99.99% (42 golden-down px, all isolated) |
| VS-drawn checkerboards, T1 v <= 128 | 32,674 | 100% (FF gate) |
| same rule without the FF gate | | Lighting_control drops to 58.4% (fails) |

**Residual: 13,534 of 284,681 v <= 128 tie pixels (4.8%).** It is almost all the
x 320-479 band on rows 135-240 inside T1, plus row 30's short alternation
(D/U every 2-4 px from x 40 to 80). No plane can produce a band like that,
because an affine error term changes sign at most once along a row. So this is
the interpolator's own arithmetic (attribute setup and evaluation precision),
not something a sampler or tie rule can express.

## (b) the bump suites: a measured negative for a tie rule

`Bump_map` draws through a `PassthroughVertexShader`, and its "boundary" is
where the *bump-displaced* TEX1 coordinate crosses a cell. With
`docs/testing/bump_edge_shift.py` (z-sweep-010, ce9c4eecf8), the mean signed
edge displacement **changes sign with the bump map's format on identical
geometry**: +0.076 px on the 8888 formats, -0.061 on R5G6B5, -0.036 on 1555,
-0.068 on 4444, -2.779 on Y16. A tie rule sees the same coordinate in every one
of those, so it cannot move these pixels. They belong to #10's bump-value
arithmetic, and the diag+FF rule predicts "up" (today's answer) for every one
of them. **(b)'s 155,871 px are not recoverable by any tie-break change.**

## Do not repeat

- **Do not change `texelTieBias.y` to a negative or index-keyed value.** Fact 1:
  a signed v bias moves every T2 tie (up today, right) to down (wrong), and an
  index threshold is #9's rule, which scores 31.7% on Lighting_control, *below*
  today's 68.3%.
- **Do not key a bias on `gl_PrimitiveID` parity** to reproduce T1/T2. It would
  hit the score above on this one helper, but the down sign in T1 is a property
  of how this quad's planes were set up, and nothing on disk shows it holds for
  any other quad. That is a curve fit to a test pattern, applied to every FF
  quad in every game.
- **Do not reopen (b) as a tie class.** See the format table above.

## What would move this forward (not this lane)

A desktop model of NV2A attribute-plane setup and evaluation (per-triangle
reference vertex, gradient format, evaluation grid) that reproduces **the sign
map above, including the x 320-479 band on rows 135-240 and the all-up cut at
row 255**. That band is the discriminating region: any setup model that makes
T1 negative with an affine error will also make the band negative, and the band
is positive. A model that passes it can then be tested out of sample on another
FF quad with exact v ties, before anything touches psh.c or vsh-ff.c.
