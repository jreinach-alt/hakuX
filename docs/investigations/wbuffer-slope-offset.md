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

## The anchors are all recoverable EXACTLY, and that changes the blocker (#31, 2026-09-13)

The section above ends with "the rule that selects between the two regimes is
not determined by the goldens available", and the tracker carries that as
*"619,349 structural px remain ... under the 4-pixel anchoring regime the
available goldens cannot select between."*  A blocker is a claim and needs the
same evidence as a fix, so it was measured.  `docs/testing/wbuf_anchor_recover.py`
does it, offline, with no device run.

**The instrument.** The offset is one constant per triangle and the depth
stored is `floor(w + offset)`, so over a triangle's pixels

    offset in [ max(z - w), min(z + 1 - w) ]

is an **exact interval**, typically 0.002 wide on a value of 10^5.  Moving the
anchor one pixel moves the offset by 0.5%-5%, so that interval pins the anchor
to a few thousandths of a pixel.  The earlier work read the offset off the
*fraction* of pixels sitting on the higher of two adjacent integers, which is
biased by up to 0.1 of a unit because `frac(w)` is not uniform over a triangle;
the interval has no such assumption.

Two controls, because a negative from a blind instrument is the trap this
campaign keeps hitting:

  - `floor(w)` from the recovered plane equals hardware's own `ZS0` depth on
    **100.00%** of the pixels of `FloorQuad` (221,970), `RoofQuad` (234,955),
    `WallQuad` (233,760) and `TriH` (26,400), and on 99.45% of `TriV` (144 of
    26,400, six per triangle, all on exact edges).  An oracle that could not
    reproduce the unbiased capture has no business arbitrating the biased one.
  - the same file emulates `wbufSlopeStep` in float32 and reproduces the
    **device's** exact/±1/wrong split for `bdc26fa5c8` *to the pixel* on six of
    the eight nonzero `WBuf24D` rows of `run-2026-09-10-wbuffer-adreno.tsv`:
    `ClipF` 281/16,520/189,489 and 0/0/159,250 and 0/0/112,210, `ClipW`
    227,737/1,703/0 and 167,539/12,941/0 and 124,410/7,110/0.  `TriH` and `TriV`
    match on `wrong` and `TriH` splits 84 px differently between exact and ±1,
    which is one float32 ULP of the offset -- see "what the ±1 floor is" below.

**66 anchors recovered, 64 of them discriminating** (`LargeZ` is excluded and
must be: `w ~ 1.7e7` changing by 1 over the whole surface, so its offset is 136
at *every* anchor.  Counting it as agreement would be as wrong as counting it
as disagreement).

| class | n | measured anchor | shipped 2-snap |
|---|---|---|---|
| `TriH`, all 24 triangles | 24 | row `4*floor(y_top/4)+2` | wrong on 12 |
| Floor, Roof, Wall, `ClipW` x3, `ClipF` t0 | 13 | first covered px, 2-snap | **right** |
| `ClipF` t1, three clip tops | 3 | row `clip_top + 2` | wrong |
| `TriV`, all 24 triangles | 24 | **no integer column at all** | wrong |

So the first correction: **"the goldens cannot select the regime" is false about
the anchors.**  Every anchor in the suite is determined, to a fraction of a
pixel, by data already on disk.  What is underdetermined is narrower and is
stated below.

### `TriV`'s 4-pixel grid is REFUTED, not merely unselected

The section above records `TriV cols = 4*floor(x_left/4)+4`, i.e. column 164 for
the first four triangles.  Column 164 predicts offsets 403,404.8 / 420,816.6 /
439,380.5 / 459,200.5.  Hardware's intervals are
[403,283.1552, 403,283.1566] / [421,475.6559, 421,475.6689] /
[440,927.2732, 440,927.2878] / [461,755.6224, 461,755.6255].  The errors are
**-122, +658, +1,547 and +2,555 units** -- 0.03% to 0.55% -- where this same
model lands *inside* hardware's interval on all 24 `TriH` triangles and on all
eleven clipped ones.  No other integer column is closer: the recovered anchors
are 164.007, 163.963, 163.920, 163.876, drifting **-0.0435 px per triangle**
while the triangles translate by exactly 1 px, and the pattern repeats with
period 4 across all 24 (so it is a function of the anchor's position relative
to the triangle, not of precision degrading down the screen).

A two-parameter fit over absolute anchor and step length does not rescue it
(best A=162.02, s=0.917, residuals up to 28 units where the interval is 0.002
wide).  **`TriV` is a third, unmodelled mechanism, and 105,600 of the 619,349
residual pixels belong to it rather than to the 4-grid class.**  That is the
one number in the tracker's sentence that is wrong: the 4-grid class is
`TriH` 52,800 plus `ClipF` 460,949, and `TriV` is something else.

Consequence for the fix: the **column stays on the 2-grid.**  Setting it to 164
would move no pixel -- `TriV` has `pb == 0` exactly, so its captures cannot see
a row change either -- and would replace a wrong answer with a wrong answer,
which a differing-pixel count cannot distinguish from inertness.

### What IS underdetermined, stated as the measurement that would refute it

Two capture pairs, and they are jointly fatal to every selector expressible in
the suite's own variables.

**PAIR A -- `ClipF-150-032` t0 vs t1.**  One planar quad, so both triangles have
the *same* 1/w plane; the same window clip; the same topmost vertex (`v0`, since
the split is on the v0-v2 diagonal); and the same first covered row, 32 --
hardware's coverage is byte-identical to the geometric prediction on all 206,290
pixels, checked row by row.  Measured anchors: **row 32 and row 34.**  So no
function of (plane, clip rect, first covered pixel, top vertex) can reproduce
the table.  *If one existed, these two anchors would be equal.*  They differ by
exactly 2 rows, recovered to ±0.001 px.

**PAIR B -- `FloorQuad` t1 vs `ClipF-150-032` t1.**  Identical vertices,
identical plane, identical shape and orientation; only `clip_top` differs, 0
against 32.  Measured anchors: **row 0 and row 34**, i.e. `clip_top+0` against
`clip_top+2`.  So the selector cannot be a function of the triangle alone
either.

Together the four cells read

    (shape t0, ct=0)  -> 2-snap     (shape t1, ct=0)  -> 2-snap
    (shape t0, ct=32) -> 2-snap     (shape t1, ct=32) -> 4-grid

which is a single interaction term pinned by exactly one data point.  Any rule
that reproduces it is fitted to that cell, and "one reason per exception is a
curve fit".  Discriminators that die on Pair A or Pair B, each killed by one
row rather than by taste: clip-edge-bounded vs geometry-bounded first pixel
(Pair B); the clip's top edge truncating the primitive (Pair A -- it truncates
t0 too); first covered column (`FloorQuad` t1 and `ClipF` t1 both start at
column 150 and split); triangle area, height, or top-row width (no ordering
separates the two sets).

**The measurement that would refute this**, and it needs new geometry rather
than more fitting: a second data point in the (shape, clip) table.  Either a
single triangle translated in y across the 4-grid phase with the clip held
fixed -- which separates "absolute grid" from "grid relative to the clip" --
or a quad at `clip_top > 0` whose *both* triangles are truncated at the top,
which fills the empty cell directly.  `nxdk_pgraph_tests` can produce both; the
existing suite conflates translation, clipping and apex visibility, which is
what the first pass of this document already said and is now quantified rather
than asserted.

### What the fix does, and why it is the measured half

`psh.c` now snaps the anchor **ROW** to `4*floor(r/4)+2` when the
Sutherland-Hodgman clip did not cut the triangle, and keeps the 2x2-quad snap
otherwise.  The `cut` flag is recorded during the clip rather than re-derived.

This reproduces 37 of the 64 discriminating anchors against the shipped rule's
25, and every one of the 25 the shipped rule already had is kept -- the gate is
false for all of them, because every quad in the suite has its topmost vertex
off-window (`FloorQuad`/`ClipF` at y=-34.3, `WallQuad`/`ClipW` at y=-26.8 and
y=-1248.7, `RoofQuad` at x=-1168.7, `LargeZ` at x=0 against a clip at 150).
Simulated in float32 against the goldens, `TriH` goes 13,116/84/13,200 to
25,854/546/0 per capture and **nothing else moves at all**.

Not done, both deliberate and both recorded above: the column grid (refuted by
`TriV`) and `ClipF` t1's `clip_top+2` (unselectable per Pair A/Pair B).  So
52,800 px of the 619,349 are addressed and 566,549 are explicitly left, of which
460,949 need new geometry and 105,600 need a new mechanism.

**Blast radius, measured not argued.**  288 shaders were emitted through the
shipped `psh.c` and this one over `z_perspective` x `depth_needed` x
`window_clip_count` x exclusive x stipple x zeta format x three renderers.
**216 are byte-identical** -- every shader with `z_perspective` false or
`depth_needed` false, which is every shader in the corpus outside `W buffering`
and `Depth Clamp` -- and the 72 that change do so by exactly one of three
texts, differing only in line numbering between the three renderers: the `bool
cut` declaration, the two assignments to it, and the row snap.  No other
emitted statement differs anywhere.

### What the ±1 floor actually is, and why it is not the anchor

Worth recording because the issue's "structural 0" for Wall and LargeZ hides
it.  With the anchor right, our offset still differs from hardware's by up to
**one unit** -- e.g. `FloorQuad` t1: hardware [113,136.7720, 113,136.7745],
ours 113,137.398.  Hardware's own interval is 0.002 wide, so that gap is real
and is hardware rounding the offset in a fixed-point format, not our anchor
being off (an anchor error is thousands of units).  It accounts for the
941,308 off-by-one pixels the `WBuf*` half of the device sweep carries (294,842
of them on `WBuf24D` ZB0 alone, which the simulation reproduces), and it is a
separate, smaller and better-posed question than the anchor: **what format does silicon round the
slope offset to?**  The 66 exact intervals in this document are the data for
it, and no device run is needed to answer it.

### The off-by-one floor is silicon's PLANE SOLVE, not our anchor (#31, 2026-09-13)

Measured on #31 arm A (`1789312070-wslope-anchor-agent-645937`, ref
`a00910d346`) with `wbuf_anchor_recover.py --ours`, which bounds the offset from
our own capture exactly the way it bounds hardware's from a golden.  This is the
larger half of the residual -- 941,308 off-by-one pixels across the `WBuf*`
captures against 669,293 structural -- and it is a different question from the
anchor.

**Two triangles of one planar quad, same plane and same anchor row, get
different offsets on hardware.**

| triangle | hardware | ours |
|---|---|---|
| `FloorQuad` t0 (v0,v1,v2) | [113137.2866, 113137.2991] | [113137.3964, 113137.4026] |
| `FloorQuad` t1 (v0,v2,v3) | [113136.7720, 113136.7745] | [113137.4180, 113137.4180] |

`FloorQuad` is planar, so the two triangles share the 1/w plane exactly, and
both anchor on row 0.  Our two offsets therefore agree to 0.02.  Hardware's
differ by **0.52**, and each of its intervals is 0.002 wide, so that is not
measurement slack.  In anchor terms 0.52 units is 1.7e-4 of a pixel row -- the
anchors are the same row and the difference is elsewhere.

The reproducibility is not in doubt: `WallQuad` t0 and all three `ClipW` t0
give the byte-identical interval [199541.0145, 199541.0277], and `RoofQuad` t0
and `WallQuad` t1 give the identical [6466.1445, 6466.1467] from two different
quads that happen to share w endpoints and anchor at the same end.

**CANDIDATE, not a finding: the setup engine's plane coefficients are rounded
per triangle.** The two triangles are solved from different vertex triples with
different determinants, so a fixed-point plane solve gives each its own
rounding. The arithmetic is consistent with it: `FloorQuad`'s d(1/w)/dx is
exactly 0 in real arithmetic (v0 and v1 share y and w), the two triangles'
anchor COLUMNS are 179 and 150, and d(offset)/di here is -5.6e7, so a residual
|d(1/w)/dx| of order 1e-9 in hardware's solve moves the offset by order 1 unit
across 29 columns. That is the right size. It is arithmetic consistent with the
measurement, not a measurement of the solve.

What follows either way, and this is the part that is not a candidate:

- **The off-by-one class is per-triangle and is not reachable from the plane**,
  so no anchor rule can remove it.  It is the floor on what #31 can reach, and
  the issue's "structural 0 at both ZS settings" for `WallQuad` and `LargeZ`
  hides it -- `WBuf24D_WallQuad` is 263 differing with 263 off-by-one, and
  `LargeZ` 118,240 with 118,240.
- **The 66 exact intervals in this document are the whole dataset for it**, on
  both sides, and it needs no device run.  The question to ask of them is what
  fixed-point format reproduces all 66 hardware values from the vertex triples,
  which is a fit over 66 constraints rather than a guess.
- The discriminating test is cheap and already in the corpus: a planar quad's
  two triangles must come out EQUAL under any model that reads only the plane,
  and hardware says they are 0.52 apart.
