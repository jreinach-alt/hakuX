# The "one-pixel edge defect", decomposed

Written 2026-09-11 on the lavapipe lane (`build/qemu-system-i386`, Vulkan on
llvmpipe, LLVM 20.1.2). Goldens are the nxdk_pgraph_tests hardware captures.

A one-pixel band of difference showed up in `Viewport` (#11), the centre
column of `Texture_render_target` (#4), rows 75/150/225 of the lighting-family
suites (#9), and the shadow suite's comparison boundary (#35). It was being
counted as one rasterisation defect. It is not one thing, and none of it is
the rasteriser's sample point or snap grid. This document records what each
band is, how much of each suite it accounts for, and what to do about it.

## Summary

| band | mechanism | class | share |
|---|---|---|---|
| lighting-family rows 30..450 | interpolated texcoord on an exact texel boundary of a stretched checkerboard; hardware breaks the tie down below texel 128, up from 144; lavapipe breaks it up | precision floor | 3–34 % of those suites |
| `Texture_render_target` column 320 | the same tie at u = 128, the exact centre of a screen-centred quad; hardware up, lavapipe down | precision floor, but fixable on lavapipe | 26 of 29 failing captures become exact |
| lit-gradient rows and columns (`Material_alpha`, `Lighting_normals`, `Specular` interior) | a colour quantisation step landing one pixel over | precision floor (#38) | 5–6 % |
| shadow comparison boundary | the depth-compare tie, one row over | precision floor after `97ac9161` | 20 of 28 failing captures |
| `Viewport` at offsets exactly +9/16 and −7/16 | fixed-function transform landing a few ULP either side of a 1/16 snap boundary that coincides with the sample | unmodelled hardware | 2 captures, 1,000 px |

The rasteriser is exonerated by the same suite that raised the alarm: ten of
the twelve `Viewport` offsets, including the XDK default 0.53125 and the
±1.0 cases, are pixel-identical to hardware in every row and column measured.

## VERIFIED

### The rasteriser: sample at +0.5, truncate to 1/16

- Screen coordinates are snapped by `roundScreenCoords`,
  `hw/xbox/nv2a/pgraph/glsl/vsh.c:265`, `trunc(pos * 16.0) / 16.0`, applied
  after the viewport offset in `vsh-ff.c:678` and `vsh-prog.c:757`.
- The Vulkan viewport carries no half-pixel offset (`vk/draw.c:3188`,
  `vk/draw.c:4198`), so pixels are sampled at (x + 0.5, y + 0.5).
- `Viewport` (`nxdk_pgraph_tests/src/tests/viewport_tests.cpp:13`) draws eight
  100 px quads at integer positions, four with a programmable shader that
  carries its own D3D-style viewport, four with the fixed-function pipeline,
  then sweeps `SetViewportOffset`. Measured against gold along rows 190/290
  and columns 170/270/370/470 of every capture
  (`docs/testing/probe_viewport_extents.py`):
  - offsets 0, +0.53125, −0.53125, +1.0, −1.0, with scale 0 or 2: ours equals
    gold in every run of every row and column checked. The programmable quads
    never move; the fixed-function quads move by the offset.
  - +0.53125 renders identically to 0 on both. A vertex at n + 17/32 covering
    pixel n on the left and not pixel n + 100 on the right is only consistent
    with a snap to 1/16 by truncation (17/32 → 8/16) and a sample at +0.5
    with the left edge inclusive. Round-half-up (→ 9/16) would leave pixel n
    uncovered, and any sample point other than +0.5 breaks one of the two edges.
  - only +0.5625 and −0.4375, both exactly n + 9/16 after the offset, differ,
    and only in the fixed-function quads.

### The two failing offsets are per-vertex, not per-edge

At +0.5625 the fixed-function quads have their vertices at 120, 220, 320,
420, 520 in x (plus 9/16) and 140, 240, 340 in y. Gold, row 190:
`P[120..219] b[220] F[221..319] P[320..419] F[420..519]`; row 290:
`b[120] F[121..220] P[221..319] F[320..419] P[420..519]`. Reading each edge
against a sample at +0.5:

| vertex x | required position of the hardware vertex | seen in |
|---|---|---|
| 120, 220 | at or above n + 9/16 (pixel n uncovered on the left, pixel n covered on the right) | both quads sharing the vertex |
| 320, 420, 520 | below n + 9/16, so the snap lands on n + 8/16 (pixel n covered on the left, uncovered on the right) | both quads sharing the vertex |
| 140, 240, 340 (y) | below | all |

Every vertex that appears in two quads needs the same sign in both, so this is
a property of the transformed vertex, not of the edge or the fill rule. Ours
lands at-or-above for every x and below for every y (the same table for our
capture). The −0.4375 capture gives the same sign pattern at 119, 219, 319,
419, 519.

### The vertices really are within rounding distance of the boundary

The test builds each quad corner by unprojecting a screen point through the
inverse composite matrix and letting the fixed-function pipeline project it
back (`viewport_tests.cpp:84`, `UnprojectPoint` in
`xbox_math3d/src/xbox_math_util.cpp:30`). Replicating that arithmetic in
strict fp32 (`docs/testing/viewport_ff_roundtrip.py`) puts the round-tripped
vertices 150–1,400 fp32 ULP away from n + 9/16, i.e. 0.002–0.010 px, because
`UnprojectPoint` extrapolates between a near-plane and a far-plane point that
are 0.4 % apart. That model predicts x = 120 and 220 land *below*, which
neither hardware nor lavapipe shows, so the Xbox build must evaluate that
chain with more precision than one fp32 rounding per operation (the P3
toolchain keeps x87 intermediates). The consistent picture is that the true
vertices sit within a few ULP of n + 9/16 and the sign is decided by the GPU's
own transform arithmetic: hardware's fixed-function transform lands slightly
low at x ≥ 320 and in y, ours does not. Nothing published characterises the
NV2A vertex ALU at that level; `nv2a_vsh_cpu` implements `RCP` as `1.0f / in`
(`src/nv2a_vsh_cpu.c:173`).

### The lighting-family rows are texel ties on the background

- `DrawCheckerboardUnproject` (`pbkitplusplus/src/nv2astate.cpp:1512`) draws
  a 256×256 nearest-filtered checkerboard (`texture_stage.h:252`, filter word
  `0x1012000`) on a quad unprojected to the framebuffer corners, so cell edges
  land at y = cell × 1.875 and x = cell × 2.5.
- The XDK viewport offset 0.53125 (`nv2astate.cpp:933`) snaps the quad to
  0.5..640.5 × 0.5..480.5, so the sample at y + 0.5 sees v = y / 1.875: an
  exact integer texel boundary at every row that is a multiple of 7.5 cells.
- Cell sizes: `material_color_source_tests.cpp:508` 20, `specular_tests.cpp:395`
  14 and `:601` 20, `lighting_control_tests.cpp:385`,
  `lighting_accumulation_tests.cpp:184`, `lighting_range_tests.cpp:152` 24,
  `lighting_spotlight_tests.cpp:256` 16 (its own texture, same quad).
- Measured first row of each new cell, `Material_color_source::Emissive_me0`,
  columns 560/600/630 (`docs/testing/probe_checker_ties.py`):

| cell edge (rows) | 37.5 | 75 | 112.5 | 150 | 187.5 | 225 | 262.5 | 300 | 337.5 | 375 | 412.5 | 450 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| texel v | 20 | 40 | 60 | 80 | 100 | 120 | 140 | 160 | 180 | 200 | 220 | 240 |
| hardware | 38 | **76** | 113 | **151** | 188 | **226** | 263 | 300 | 338 | 375 | 413 | 450 |
| lavapipe | 38 | 75 | 113 | 150 | 188 | 225 | 263 | 300 | 338 | 375 | 413 | 450 |

  Hardware resolves the v-ties down below texel 128 and up above; the 16-cell
  spotlight board puts a tie exactly at v = 128 (row 240) and hardware goes
  down there, the 24-cell boards put one at v = 144 (row 270) and it goes up.
  The x-ties (u = 20k at columns 50k, four rows checked) resolve up on both.
  The same rows, and only those rows, differ in every capture of every suite
  above (`Specular` 105/210, `Lighting_control` 45..225,
  `Lighting_spotlight` 30..240), so the rule is a property of this quad's
  interpolation on hardware, not of the cell size.

### `Texture_render_target` column 320 is the same tie

The framebuffer quad is `DefineBiTri(0, -1.75, 1.75, 1.75, -1.75, 0.1f)`
(`texture_render_target_tests.cpp:112`), symmetric about the screen centre.
After the 0.53125 offset and the 1/16 snap its edges are 177.6875 and
463.3125, whose midpoint is exactly 320.5, so u = 128.0 at pixel 320. On all
285 rows of `TexFmt_A8B8G8R8` ours equals gold[x − 1]: hardware breaks the
tie up (texel 128), lavapipe breaks it down (texel 127). Lavapipe's tie
resolution is not consistently "up" either; it is fp32 interpolation noise.

### How much of each suite this is

`docs/testing/classify_residuals.py` now carries a `boundary-shift` class: a
differing pixel that lies in an isolated one-pixel band (the rows or columns
on either side agree with gold) and equals gold's neighbour across the band.
That catches a texel tie, a colour-quantisation step, a depth-compare tie or
a snapped vertex equally, because they all look the same: a boundary one
pixel over. Measured on this lane's captures, in pixels (the classifier
itself reports channels, like its existing columns, so its shares run higher):

| suite | failing / captures | diff px | boundary-shift px | share | exact once excluded |
|---|---|---|---|---|---|
| `Lighting_accumulation` | 10 / 10 | 163,552 | 55,610 | 34.0 % | 3 |
| `Lighting_spotlight` | 24 / 24 | 595,468 | 164,078 | 27.6 % | 0 |
| `Lighting_range` | 3 / 3 | 10,373 | 2,459 | 23.7 % | 0 |
| `Lighting_control` | 32 / 32 | 265,890 | 56,632 | 21.3 % | 0 |
| `Specular` | 22 / 22 | 444,147 | 45,959 | 10.3 % | 2 |
| `Specular_back` | 17 / 17 | 307,257 | 31,806 | 10.4 % | 2 |
| `Material_alpha` | 18 / 24 | 1,028,160 | 63,680 | 6.2 % | 0 |
| `Lighting_normals` | 16 / 28 | 138,572 | 7,928 | 5.7 % | 0 |
| `Material_color_source` | 28 / 28 | 400,930 | 22,640 | 5.6 % | 4 |
| `Volume_texture` | 18 / 20 | 376,226 | 19,566 | 5.2 % | 2 |
| `Texture_shadow_comparator` | 28 / 288 | 8,776 | 420 | 4.8 % | 20 |
| `Texture_render_target` | 29 / 40 | 210,751 | 7,180 | 3.4 % | 26 |
| `Texture_format` | 22 / 40 | 1,682,460 | 25,024 | 1.5 % | 0 |
| `Viewport` | 2 / 12 | 1,000 | 800 | 80.0 % | 1 |
| `Blend_tests` | 104 / 105 | 5,834,187 | 552 | 0.0 % | 0 |

The earlier figure of 230,034 of 446,954 px for `Specular` was a
rows-with-many-diffs criterion that swept in lit gradient rows; it is
withdrawn. The remainder in #9 is real lighting arithmetic, not an edge.

### Confirmation from `Vertex_shader_rounding_tests`

The corpus already carries the disc this question would otherwise need:
a passthrough vertex shader (no transform arithmetic) draws quads offset by
biases 0, 0.001, 0.4999, 0.5, 0.5624, 0.5625, 0.5626, 0.999 and 1.0
(`vertex_shader_rounding_tests.cpp:26`, its own comment: "Boundaries at
1/16") on the framebuffer, on a smaller and a larger render target, as eight
adjacent quads, and as the same eight quads projected through the D3D-style
viewport; plus two top-left fill-rule sweeps in 1/16 steps and two
render-target viewport tests. It had never been run on this lane. Config:
`docs/testing/configs/vertex_shader_rounding.json`. Result: **47 of 51
exact**.

| family | tests | exact | note |
|---|---|---|---|
| `Geometry` (passthrough, framebuffer) | 9 | 9 | green starts at 200/120 up to bias 0.5624 and at 201/121 from 0.5625, on both sides |
| `GeometrySubscreen`, `GeometrySuperscreen` | 18 | 18 | render targets smaller and larger than the framebuffer |
| `AdjacentGeometry` | 9 | 9 | |
| `ProjAdjacentGeometry` | 9 | 8 | 0.5625 fails: 498 px on row 240 and columns 320/420, boundary-shift; 0.5624 and 0.5626 exact |
| `TopLeftRaster`, `TopLeftRaster_Fixed` | 2 | 2 | fill rule, 1/16 sweeps, programmable and fixed-function |
| `RenderTarget` | 1 | 1 | viewport offset 320.53125 on a render target |
| `Compositing` | 3 | 0 | one-step-hi; a blend accumulated over four passes, #14's class, not geometry |

The snap, the sample point and the fill rule are exact on the suite written
to probe them, on the framebuffer and on render targets at both scales. The
one geometry failure is again the transformed vertex at exactly 9/16, with
the biases one ten-thousandth either side exact on both hosts: the boundary
value is the only one whose side is decided by the last ULP of the transform.

## INFERRED

- The hardware v-tie rule (down below texel 128, up from 144, on this quad)
  is the attribute interpolator, not the sampler: u-ties on the same quad
  all go up, so the sampler alone cannot explain the asymmetry, and the
  transition between 128 and 144 is the same in three cell sizes because it
  is one quad. A gradient-rounding error with the plane reference near the
  screen centre would produce it; nothing here proves that.
- The hardware fixed-function transform landing low at x ≥ 320 and in y is
  consistent with a reciprocal or multiply that rounds toward zero on the
  order of 2⁻¹⁷, which is the magnitude the CPU replication needs. Not
  established.
- Games place integer-aligned 2D geometry at the XDK offset, n + 17/32, which
  is 1/32 away from the nearest snap boundary on either side. The 9/16 cases
  are the test probing the boundary itself; they do not represent gameplay.

## UNRESOLVED

- How Adreno breaks these ties. lavapipe and hardware differ at the RT centre
  column and at six checkerboard rows; the device lane has been asked
  (PR #45) for the same two probes. If Adreno breaks them a third way, the
  deterministic rule below is worth building for portability alone.
- The exact NV2A interpolator and vertex-ALU rounding. Both are measurable
  with purpose-built tests (a vertex sweep across n + 9/16 finer than the
  corpus's ±0.0001; a 1:1 textured quad with a per-texel pattern), which
  means hardware time through the nxdk_pgraph_tests golden pipeline, and
  neither is worth guessing at.

## The texel-tie bias: built, swept, measured

Plan item 2 below, implemented and measured on lavapipe against a matched
baseline: the same tree with only the one-line shader change reverted, the
same eight discs, 1,008 captures.  The change biases the texture coordinate
up by a constant in normalized space, sized to cover fp32 interpolation noise
(2^-18 of the texture, about fifteen times the error on an interpolated
coordinate, 0.001 texels on a 256 texture) and far below any subtexel
position a guest can express.  A coordinate that is mathematically on a
boundary then lands on it instead of a few ULP either side; one that is
genuinely below stays below.  In `psh.c`'s `PS_TEXTUREMODES_PROJECT2D` 2D
path, carried through `textureProj` by scaling the bias by w:

```c
mstring_append(preflight,
               "const vec2 texelTieBias = vec2(1.0 / 262144.0, 0.0);\n");
...
mstring_append_fmt(vars,
    "vec4 t%d = textureProj(texSamp%d,\n"
    "    vec3(%s(pT%d.xy) + texelTieBias * pT%d.w, pT%d.w));\n",
    i, i, tex_remap, i, i, i);
```

### Result

| | diff px | captures better | captures worse | exact |
|---|---|---|---|---|
| baseline | 14,038,276 | | | 502 / 1,008 |
| bias in u only | 14,029,849 (**−8,427**) | 33 | **0** | 502 |
| bias in u and v | 14,017,984 (**−20,292**) | 33 | 104 | 502 |

Where it moves, u only:

| suite | base px | after px | delta | captures |
|---|---|---|---|---|
| `Texture_render_target` | 210,751 | 205,021 | −5,730 | 24, each −285 |
| `Point_params` | 28,798 | 26,581 | −2,217 | 3 |
| `Swath_width` | 347,910 | 347,430 | −480 | 6, each −80 |

Everything else is bit-identical: `Texture_format`, `Texture_DXT`,
`Volume_texture`, `Blend_tests`, all eleven lighting and material suites,
`Texture_shadow_comparator`, `Window_clip`, `Viewport`, `Stencil`,
`Line_width`, `Point_size`, `2D_Lines`, `Smoothing_control`, `Stipple_tests`
and `Vertex_shader_rounding_tests`.  975 of 1,008 captures unchanged to the
byte.

### Why u only

Biasing v as well buys 12,027 px more, almost all of it text glyphs in three
`Point_params` captures, and costs 162 px spread over 104 captures: exactly
the checkerboard cell **corners**, where a u-tie and a v-tie coincide, three
pixels per capture.  At a corner hardware picks (u up, v down); ours already
picked that, and biasing v up moves it to the diagonal texel, which on a
checkerboard is the other colour.

That asymmetry is hardware's, not a fitting choice.  Hardware's u-ties
resolve up in both quads measured (the render target's centre column, the
checkerboard's column edges).  Its v-ties do not resolve consistently: down
at texels 40, 80 and 120, up at 160, 200 and 240 on the same quad, and down
at texel 128 on the render target where the *u*-tie at the same value on the
same quad goes up.  A DDA rasteriser accumulating u along the scanline and v
between scanlines would behave this way.  So u has a rule that every
measurement so far agrees with and v demonstrably does not, and biasing v is
guessing.  Two quads is thin evidence for the u rule and the doc should say
so; what the bias actually guarantees is that our own outcome stops being
decided by host float noise.

### What it does not do

No capture changes state.  The exact count is 502 before and after, because
every capture the bias improves has a second, unrelated residual: the 24
render-target captures still carry 12 to 71 px on **row 240**, which is the
v-tie at the same texel 128, left alone by design.

It also cannot reach the shadow comparator.  That path samples through
`psh_append_shadowmap`, a different emission site, and the tie there is
between the interpolated depth *reference* and an integral threshold, not
between a texture coordinate and a texel boundary.  A bias in u and v does
nothing to a comparison in z.

### The device answer, and why u-only shipped

The Adreno lane ran both probes on a Retroid Pocket Nova, Adreno 740,
Turnip T30.  First row of each new checkerboard cell, `Material_color_source`:

| row | 37.5 | 75 | 112.5 | 150 | 187.5 | 225 | 262.5 | 300 | 337.5 | 375 | 412.5 | 450 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hardware | 38 | **76** | 113 | **151** | 188 | **226** | 263 | 300 | 338 | 375 | 413 | 450 |
| lavapipe | 38 | 75 | 113 | 150 | 188 | 225 | 263 | 300 | 338 | 375 | 413 | 450 |
| Adreno | 38 | 75 | 113 | 150 | 188 | **226** | 263 | 300 | 338 | **376** | 413 | **451** |

Three hosts, three answers, in both directions: Adreno sides with lavapipe at
rows 75 and 150, with hardware at 225, and goes a row past both at 375 and
450.  Turnip 26.3.0, Turnip 26.1.0 and the Qualcomm proprietary driver produce
byte-identical edge rows, so this is our arithmetic meeting a different FP
unit, not driver variance.  On the render target's centre column Adreno
matches lavapipe (its column 320 equals gold's column 319), so that boundary
is host-independent between the two lanes and the bias moves both onto
hardware's answer at once.

That settles u.  It does not settle v: the bias would have to *change* the
checkerboard rows to make the lanes agree there, and on lavapipe it does not
move a single one of the twelve (they are already resolved up).  Whether it
moves Adreno's three outliers onto the same list is a device measurement
nobody has taken.  Until it is taken, biasing v costs 162 px on this lane for
a predicted benefit on another, so v stays zero and the experiment is the
device lane's to run.

### One measurement bought something else

`Stencil::Stencil_REPLACE` came out 40,000 px wrong in the first swept run and
0 px in the matched baseline, which read as a large regression from a change
that cannot reach it: the test samples no texture, it draws three untextured
quads through a passthrough shader.  Six runs of the clipping disc settled it
as run-to-run nondeterminism, twice failing, on builds differing only by that
one constant and with the same binary giving both outcomes.  The whole 200x200
centre region comes out green where the golden is red, which is the third draw
passing where it should fail because the middle stencil-only draw never landed.

That is #39, closed on 2026-09-10 with a real root cause and fix in `2dd2321`
whose verification was two runs of this disc.  At roughly one failure in three,
two runs pass by chance four times in nine.  Reopened with the evidence.

The bound this puts on everything here is worth stating: a capture that fails
one run in three means a single-run sweep carries noise, and a change measured
by one run before and one after can show a difference it did not cause.  The
A/B above survives that only because 975 of its 1,008 captures are identical
to the byte and the 33 that move do so by the same amount on every capture of
a kind.

### The constant cannot be raised much, and the ceiling is the content's

The device lane reported that its choice at column 320 is not contiguous down
the quad: correct on 103 rows and wrong on 182, alternating in 23 runs and
flipping on adjacent rows near the bottom.  That is a quantity drifting across
the tie as the scanline advances, so the worst-case excursion could exceed the
bias, and the obvious remedy is a larger constant.  It is not available.

Measured by sweeping the constant on this lane, against the same baseline:

| bias | texels on a 256 texture | Texture_render_target | Texture_format etc. | lighting |
|---|---|---|---|---|
| 1/262144 (shipped) | 0.00098 | **−5,730 px, 0 worse** | unchanged | unchanged |
| 1/65536 | 0.0039 | +1,417 px, 14 worse | unchanged | unchanged |
| 1/16384 | 0.0156 | +19,419 px, 32 worse | +57,419 px, 34 worse | unchanged |
| 1/4096 | 0.0625 | +91,723 px, 33 worse | +146,423 px, 36 worse | unchanged |

The first failure names the limit.  At 1/65536 seven captures that were exact
break, all of them at **column 455**, not at 320.  Working the quad's geometry
exactly (`177.6875 .. 463.3125`, 285.625 px carrying 256 texels):

| column | u | distance to the nearest texel edge |
|---|---|---|
| 320 | 128.000000 | **0** — a true tie |
| 455 | 248.997812 | 0.002188 texels **below** texel 249 |

So column 455 is not a tie: it is genuinely below its edge, hardware agrees
that it is below, and we get it right without help.  A bias of 0.0039 texels
carries it over and we get it wrong.  The shipped 0.00098 texels is 45% of
that gap.

**This bounds the method, not just the constant.**  A uniform bias cannot
distinguish "exactly on the boundary" from "0.002 texels below the boundary",
and neither can the round-to-nearest-boundary formulation, because both act on
everything within epsilon of an edge and the discrimination threshold is the
same quantity.  The ceiling is set by the closest genuine near-boundary
coordinate the content contains, which in this suite is 0.002188 texels.
There is therefore about 2.2x of headroom and no more.

The consequence for the open v-axis and device work: if the residue after the
bias needs a constant larger than roughly twice the shipped one, raising it is
not the answer and the approach has to change -- to something that knows a
coordinate's intended value rather than guessing from its proximity to an
edge.

## What not to do

`roundScreenCoords` is measured on both sides (`vsh.c:243`): 1/32 and 1/8
grids and round-half-up are all worse, and ten of twelve `Viewport` offsets
already match. Do not move the sample point: every checkerboard row and
column above is consistent only with +0.5, and a shifted sample would move
the ten exact offsets. Do not bias texture coordinates by a constant: that
trades the top-half rows for the bottom-half rows and fixes nothing.

## Plan

1. **Classify, do not chase.** Land the `boundary-shift` class so every sweep
   reports it beside the real residual (this commit). Dispositions: #11's
   remaining two captures `unmodelled-hardware`; the tie rows in #9 and the
   centre column in #4 are named in the issues so the work there targets the
   rest.
2. **Deterministic texel-tie resolution in u.** Built, swept, and landed once
   the device probes came back: Adreno resolves these ties a third way and in
   both directions, so the pixels were host-unstable, and it agrees with
   lavapipe on the render target's centre column, so the bias moves both lanes
   onto hardware's answer there. Strictly non-regressive across 1,008
   captures, −8,427 px, no test changes state. The prediction written here
   before the run, "`Texture_render_target` 11 → about 37 exact", was wrong:
   the u tie is only half of each of those captures' residual.
3. **The v axis stays open**, as a device measurement rather than a code
   change: does the same bias in v move Adreno's three outlying checkerboard
   rows onto lavapipe's list? On this lane it moves none of the twelve, so the
   question cannot be answered here.
4. **No rasteriser change.** The two `Viewport` captures and
   `ProjAdjacentGeometry_0.5625` stay red. If the NV2A transform precision is
   ever wanted, it is a hardware measurement (a finer sweep than the
   ±0.0001 the corpus already has, run through the upstream golden
   pipeline), not a constant.
5. **Shadow boundary and lit-gradient bands** stay where they are: #35 and
   #38, precision floor, now counted as such.
