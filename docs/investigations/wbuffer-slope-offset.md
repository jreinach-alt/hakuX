# W-buffer slope-scaled polygon offset (#31)

Measured on the `W_buffering` goldens (XBOX 1.0), `ZS1` (slope factor 65536)
minus `ZS0`, both with the depth buffer stored as `floor(w)`.

## What the hardware does

The offset is **one constant per triangle**, and it is exactly

    offset = factor × |w(P) − w(P′)|

for two adjacent pixel centres `P`, `P′`, stepping along the axis of the larger
`1/w` gradient. The stored value is `floor(w + offset)`, which is why each
region shows two adjacent integers (6466 on 85 % of the pixels, 6467 on 15 %:
the offset is 6466.15).

Not `factor × max|d(1/w)| × w²` per pixel (what the emulator applied), which
varies 30× across one quad; and not evaluated at a vertex (Roof's second
triangle sits at w = 152.9, no vertex is near that).

| triangle | pair (px centres) | measured | predicted from the pair |
|---|---|---|---|
| Wall (v0,v2,v3) | cols 150,151 row 0 | 6466 | 6465.9 |
| Wall (v0,v1,v2) | cols 636,637 row 0 | 199541 | 199540 |
| Roof (v0,v1,v2) | rows 0,1 | 6466 | 6466.1 |
| Roof (v0,v2,v3) | rows 366,367 | 44201 | 44200.5 |
| Floor (both) | rows 0,1 | 113136/7 | 113137.4 |
| Z-buffer control (Roof, both) | – | 7783 | 16 × dz/dy = 7783.8 |

The Z-mode control has no reference point (dz is constant), and matches.

## Where the pair sits

Two regimes were observed.

**Clipped triangles** (all the quads: vertices at x = −1168 … 1808,
y = −1248 … 1728, window clip x ≥ 150): the pair starts at the **first pixel
the rasteriser covers** — the top-most row of the triangle ∩ clip window, at
the covered column nearest the top vertex's x. Wall's two triangles pick
opposite ends of their shared top row (150 and 636) because their top vertices
are v3 (x = 150) and v0 (x = 637.31). Roof's second triangle starts at row 366
only because of the x ≥ 150 clip (its sliver above that is off-window).

The clipped variants pin the pair down further. `ClipW` moves Wall's
window-clip left edge to 159, 261 and 363: the pair becomes (158,159),
(260,261), (362,363) — the **2-aligned pixel pair containing the first
visible column**, straddling the clip edge. The vertex anchors read the same
way: x = 150.0 gives (150,151), x = 637.31 gives (636,637); rows 0 and 366
give (0,1) and (366,367). `ClipF` moves Floor's top edge to 32, 128 and 224:
the small triangle (its top row starts where the diagonal meets the clip)
gets (32,33) by that rule, but the large one, whose top row starts at the
window corner, gets (34,35), (130,131), (226,227) — the 4-grid rule below.

**Small unclipped triangles** (`TriH`: 10×200 px, tops at y = k + 0.5;
`TriV`: 200×10 px, lefts at x = 160.5 + k): the pair sits on a 4-pixel grid:

    TriH rows: 4·⌊y_top/4⌋ + 2, +3      (k = 0..3 → rows 2,3; k = 4..7 → 6,7)
    TriV cols: 4·⌊x_left/4⌋ + 4, +5     (k = 0..3 → cols 164,165; k = 4..7 → 168,169)

Congruent triangles shifted one pixel therefore cycle through four offsets
(439380, 459200, 480392, 503086), each reproduced to 0.04 % by the pair.
The two regimes are not one rule: Roof's top edge is on y = 0.0 and uses rows
(0,1); the small-triangle rule would put it on (2,3).

## What the emulator does now

`wbufSlopeStep()` in `psh.c` (fragment shader, W mode, only when
`depthFactor != 0`): clip the triangle to window-clip region 0 (Sutherland–
Hodgman), find the first covered row, the covered column nearest the top
vertex, snap both to the 2×2 quad that contains them, and return
`|step| / (i1·i2)` — the exact `w(P) − w(P′)` without
cancellation (`i` is `1/w` on the plane; `step` is the plane's per-pixel
`1/w` increment). This is the clipped-triangle regime; it also gives the
right magnitude for the small-triangle regime (within 12 % on TriH), which the
per-pixel formula did not.

Measured on the Nova (`docs/testing/run-2026-09-10-wbuffer-adreno.tsv`),
suite total wrong pixels 7,199,516 → 1,312,385 (1,774,025 before the quad
snap); Wall both triangles and all three `ClipW` variants exact or ±1, Floor
and LargeZ from all-wrong to exact/±1, Roof's second triangle within the
hardware's own ±1, TriH half right. What remains wrong is the 4-grid regime:
`ClipF` (461 k px) and the small triangles (66 k px).

Offline validation of the first-pixel rule against the goldens before the build
(`ZS1 − ZS0` within `[⌊pred⌋, ⌊pred⌋+1]`):

    WBuf24D WallQuad  233760/233760
    WBuf24D RoofQuad  225289/234955   (second triangle: hardware's own ±1)
    WBuf24D FloorQuad 180729/221970   (second triangle: hardware's own ±1)
    WBuf24D TriH        6600/26400    (only k ≡ 2 mod 4 coincide)
    WBuf24D TriV           0/26400

Open: the small-triangle grid rule, and what selects between the regimes.
Both would need new test geometry (a translated single triangle, apex on and
off the window) — only goldens are available here, so this is recorded, not
modelled.

## Related

`LineStrip` receives no slope offset at all (770 px, offset 0). `LargeZ`
(w ≈ 16.7 M, +1 over the height) gets 136 everywhere — consistent with the
pair model but not discriminating. The fixed-function `_V0_` ZS1 captures are
empty (nothing drawn) on hardware; not investigated.

## The residual is the anchor snap, and it is arithmetic (#31, 2026-09-12)

Read off `docs/testing/run-2026-09-10-wbuffer-adreno.tsv`, i.e. the device
numbers for the code as shipped in `bdc26fa5c8`.  The shipped snap is

    c = 2*floor(c/2);   r = 2*floor(r/2);

and that one pair of lines accounts for every remaining wrong `WBuf*` pixel.
`x_left`/`y_top` below are the small triangles' own geometry; the quads'
anchors are the first covered pixel as derived above.

| capture | ours | hardware | after_wrong |
|---|---|---|---:|
| `TriH` k=0,1 (y_top = k+0.5) | row 0 | row 2 | wrong |
| `TriH` k=2,3 | row 2 | row 2 | **exact** |
| `TriV` k=0,1 (x_left = 160.5+k) | col 160 | col 164 | wrong |
| `TriV` k=2,3 | col 162 | col 164 | wrong |
| `ClipF-150-032` large tri | row 32 | row 34 | wrong |
| `ClipF-150-128` large tri | row 128 | row 130 | wrong |
| `ClipF-150-224` large tri | row 224 | row 226 | wrong |

`TriH` is the check: `2*floor(r/2)` lands on hardware's row 2 for k = 2,3 and
on row 0 for k = 0,1, so two of the four congruent triangles must be exact and
two wrong.  Measured `WBuf24{D,F}_TriH_V1_ZB{0,1}_ZS1_ZB`: 13,200 exact and
13,200 wrong of 26,400, i.e. exactly two triangles each.  `TriV`'s snap never
reaches col 164 for any k, so it must be all wrong; measured 0 of 26,400
exact.  The offline row above ("TriH 6600/26400, only k = 2 mod 4 coincide")
predates the quad snap and no longer describes the shipped code.

Two rows in the residual are *not* the anchor: `WBuf24F_RoofQuad_V1_ZB{0,1}`
(23,380 px each) is Roof's second triangle, which `WBuf24D_RoofQuad` gets to
within hardware's own rounding on the same geometry -- the difference is the
24-bit *float* depth encoding, so it belongs to #52's float-Z defect, not
here.  `ZBuf24D_FloorQuad_V0_ZB{0,1}` (151,316 px each) is Z-mode, scores
identically before and after the W fix, and is likewise #52.

### Why the 4-grid rule is not shippable on its own

Applying the small-triangle rule everywhere -- `r = 4*floor(r/4)+2`,
`c = 4*floor(c/4)+4` -- moves the anchors that currently agree with hardware:

    Wall   col 150 -> 152,  col 636 -> 640
    Roof   row 0   -> 2,    row 366 -> 366  (survives)
    Floor  row 0   -> 2
    ClipW  col 158 -> 160,  260 -> 264,  362 -> 364

So the trade is measured, not guessed: **620,349 px** recoverable (`TriH`
52,800 + `TriV` 105,600 + `ClipF` 461,949) against **4,172,280 px** across the
19 `WBuf*` captures that currently score zero wrong, all of whose anchors move
except Roof's second triangle.  6.7x worse.  The regime selector is load
bearing; a blanket switch is the wrong shape and is not worth shipping.

Discriminators tried against the table above and rejected, each because one
row contradicts it: clip-edge-derived vs geometry-derived anchor (Wall's
second triangle is geometry-derived and 2-grid); primitive area (Roof, Wall
and Floor are large and 2-grid, `ClipF`'s large triangle is large and 4-grid);
`ClipF`'s own two triangles share a clip edge and split across the regimes.
The suite still conflates translation, clipping and apex visibility, so this
stays where the previous section left it: needs new geometry, not more fitting.

### Measured dead in the renderers

Checked while looking for a renderer-side contribution; all four are negative,
and all four are reads of the current tree rather than inference.

- `vk/draw.c` and `gl/draw.c` only *disable* polygon offset
  (`depthBiasEnable = VK_FALSE`, `glDisable(GL_POLYGON_OFFSET_*)`), and no
  `vkCmdSetDepthBias*` is issued anywhere, so the static `VK_FALSE` is live
  rather than shadowed by dynamic state.  Neither renderer holds any part of
  the offset arithmetic; it is all `glsl/psh.c`.
- `NV_PGRAPH_SETUPRASTER`'s `POFFSET{POINT,LINE,FILL}ENABLE` bits are in
  `pgraph_reg_dynamic_mask_table`, so changing only them bumps neither
  `shader_state_gen` nor `non_dynamic_reg_gen`, and the dynamic apply reads
  SETUPRASTER only for cull mode and front face -- yet those bits decide
  whether `depthOffset`/`depthFactor` carry the ZOFFSET registers or zero.
  The super-fast path looks like it would draw with the previous draw's
  offset, but it also fails on `any_reg_gen`, which *every* register write
  bumps, so the stale-uniform window does not exist.
- Dropping `NV_PGRAPH_ZOFFSETBIAS`/`ZOFFSETFACTOR` from the pipeline key under
  `OPT_DYNAMIC_STATES` is safe for the same reason plus one more: they feed
  uniforms only, and `vk/shaders.c` re-hashes the uniform block and sets
  `uniforms_changed` when a value moves.
- `prim_rewrite.c` splits a quad on the v1-v3 diagonal under flat shading
  instead of hardware's v0-v2, which would relocate both triangles' reference
  pixels.  Ruled out by measurement, not by reading: Wall and Floor reproduce
  to the unit on the v0-v2 decomposition, so these tests are not flat shaded.
