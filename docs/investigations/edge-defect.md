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
  with purpose-built discs (a vertex sweep across n + 9/16 ± 2⁻ᵏ; a 1:1
  textured quad with a per-texel pattern) and neither is worth guessing at.

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
2. **Deterministic texel-tie resolution, gated on measurement.** Before a
   nearest-filtered sample, round the texel-space coordinate to the nearest
   1/256 texel (the subtexel precision Vulkan reports on both lanes), so an
   interpolated value a few ULP either side of an integer lands on it and
   `floor` is decided by the boundary, not by the host's interpolation noise.
   Expected on lavapipe: `Texture_render_target` 11 → about 37 exact, the
   checkerboard rows unchanged (they are already "up" here), no other suite
   moved unless it carries a near-tie within 1/512 texel. The change lives at
   the sampling sites in `hw/xbox/nv2a/pgraph/glsl/psh.c` (2D at `:2002` and
   `:2057`, rect normalisation at `:2395`), keyed on the stage's filter. It
   goes in only if the lavapipe sweep shows no regression and the device
   probes show Adreno does not already match hardware.
3. **No rasteriser change.** The two `Viewport` captures stay red. If the
   NV2A transform precision is ever wanted, it is a disc and a measurement,
   not a constant.
4. **Shadow boundary and lit-gradient bands** stay where they are: #35 and
   #38, precision floor, now counted as such.
