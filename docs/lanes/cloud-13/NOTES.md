# cloud-13 -- #13's line-mode families outside Line_width: one rule or several

Brief: from the goldens and our captures on disk, decide whether ONE rule
(extent, cap/join phase or edge order for the wireframe path) explains the
three families the 2026-09-25 inventory added to #13 -- Front_face
`FrontFace_LM_*` (12 captures, 36,796 px), Shade_model `ProgLM_*` (24,
11,178), 3D_primitive plain lines (12, 9,712) -- fitting on Front_face and
predicting the other two with the rule held out.  Analysis only, no edit under
`hw/`.  Base: master @ `24208f15cb`.

## Answer

**No single rule. The falsifier fires, and #13 splits.**  The rule fitted on
Front_face predicts Shade_model's strokes (except a few chains that the
instrument merges) but not 3D_primitive's: 5 of 17 3D_primitive strokes fall
within tolerance, and every one of its 17 strokes is off in the same
direction.  Beyond that, stroke geometry is a minor part of the residual in
all three families.  Every structural pixel is attributed below to one of
four causes, and only one of them (the tie strokes) appears in all three
families.  It is not a rasteriser rule: the same tie breaks the other way
on 988 of 988 Line_width tie cuts.

| cause | Front_face | Shade_model | 3D_primitive | total | a stroke rule? |
|---|---:|---:|---:|---:|---|
| **A. culling not applied to line-mode triangles** | **31,152** | 0 | 0 | 31,152 | no: whole primitives |
| B. tie strokes (a whole stroke 1 px over) | 5,424 | 2,856 | 6,320 | 14,600 | no: see B |
| C. flat colour in a line-mode quad/polygon | 0 | 7,324 | 40 | 7,364 | no: colour |
| D. extent / phase | 220 | 988 | 2,644 | 3,852 | D1 no, D2 yes |
| structural (max channel delta > 8) | 36,796 | 11,168 | 9,004 | 56,968 | |

Front_face reproduces the inventory's 36,796 to the pixel.  Shade_model
(11,168 against 11,178) and 3D_primitive (9,004 against 9,712) are measured on
the capture sets named under "Captures".  The inventory read a different run
of each, so those two differ by 10 and 708 px.  `lm_attrib.py` produces the
table.

## What the families are

- **Front_face `FrontFace_LM_*`** (`front_face_tests.cpp`) uses the
  passthrough vertex shader and `TRIANGLES` under `POLYGON_MODE_LINE` with cull
  enabled.  It draws a CCW quad (left), a CW quad (right), and two
  **zero-area** triangles, each with three vertices on one x (133 and 507).  The
  left quad's vertices carry w = INFINITY, 0.98 and 0.  Width 1.
- **Shade_model `ProgLM_*`** (`shade_model_tests.cpp`) uses a perspective
  vertex program, all six triangle and quad primitive types, and line mode, in
  flat and smooth variants.  The suite default leaves cull enabled (cull back,
  front CW, `test_suite.cpp:275-277`), and silicon draws every one of these
  primitives.
- **3D_primitive `Lines*`, `LineStrip*`, `LineLoop*`**, without `-ls`/`-ps`
  (`three_d_primitive_tests.cpp`), are **line primitives, not line-mode
  polygons**.  They use the fixed-function transform, depth test, alpha test
  and blend, and draw with `NV097_SET_SMOOTHING_CONTROL = 0xFFFF0000`.  Width
  1: every suite sets `NV097_SET_LINE_WIDTH 8` (`test_suite.cpp:173`).

## A. Culling: 31,152 px, 84.7% of Front_face, the largest single item

`vk/draw.c:4533` clears `NV_PGRAPH_SETUPRASTER_CULLENABLE` for every draw
whose geometry stage widens lines, on the premise "Silicon does not cull
lines".  That is right for line **primitives**.  But `widen_lines` is also
true for `TRIANGLES` under `POLY_MODE_LINE` (`glsl/geom.c:406-409`), and
silicon culls a line-mode triangle by the source triangle's face.  Read off
each golden (`ff_cull_table.py`):

| golden | left quad (CCW) | right quad (CW) | zero-area tri @133 | @507 | ours |
|---|---|---|---|---|---|
| `CW/0x00/0x63_CF_B` | culled | drawn | culled | culled | all drawn |
| `CW/0x00/0x63_CF_F` | drawn | culled | drawn | drawn | all drawn |
| `CCW_CF_B` | drawn | culled | drawn | drawn | all drawn |
| `CCW_CF_F` | culled | drawn | culled | culled | all drawn |
| every `CF_FaB` | culled | culled | culled | culled | all drawn |

So on silicon:

1. Face culling applies to line-mode triangles exactly as to filled ones.
2. `0x00` and `0x63` are ignored and CW is kept, which is what the test
   expects.  Front-face handling itself is right in fill mode: the `FM_`
   captures are not in this residual.
3. **A zero-area triangle takes the same face as the CCW-wound quad**: it is
   culled with it and drawn with it in all 12 goldens.

We draw all four primitives in all 12 captures.  All 31,152 px of the class
are ours-only.

Colour is **0 px** in Front_face.  Once culling is fixed, Front_face's
residual is B (5,424) plus D (220).

### The named hunk (for the lane that takes the grant; glsl/geom.c is held by lane.wparamcode223, PR #321)

- **`hw/xbox/nv2a/pgraph/glsl/geom.h`, `GeomState`**: add the cull state,
  `bool cull_enable; uint8_t cull_face; bool front_ccw;`.
- **`hw/xbox/nv2a/pgraph/glsl/geom.c`, `pgraph_glsl_set_geom_state()`**: fill
  those fields from `NV_PGRAPH_SETUPRASTER` (`CULLENABLE`, `CULLCTRL`,
  `FRONTFACE`), and **only when `polygon_front_mode == POLY_MODE_LINE`**.
  Zero them otherwise, so no fill-mode or line-primitive shader key changes.
- **`hw/xbox/nv2a/pgraph/glsl/geom.c`, `pgraph_glsl_gen_geom()`, the
  `PRIM_TYPE_TRIANGLES` / `POLY_MODE_LINE` body (currently lines 496-499)**:
  before the three `emit_line()` calls, compute the signed area of the
  *source* triangle from the three truncated screen positions the widening
  already uses (`v_vtxPos`, not `gl_Position`: the widened footprint's own
  winding is decided by the perpendicular offset and means nothing), classify
  the face, and `return` without emitting when the face is culled.  An area
  of exactly 0 classifies as the face a CCW triangle gets (point 3 above).
- **`hw/xbox/nv2a/pgraph/vk/draw.c`**: **keep** clearing Vulkan's cull for
  widened draws (lines 4533-4546 and 5597-5599).  The hunk moves culling
  into the shader; it does not re-enable it on the widened footprint.  Update
  the comment, which states the premise this refutes.

**Calibrate the sign on one golden, then predict the rest.**  Which sign of
the area is "CW" depends on whether our screen y runs down, which this
analysis did not establish.  Calibrate on `FrontFace_LM_CW_CF_B` alone (left
quad and both zero-area triangles must go).  The other 11 captures are then
predictions, and the must_not_move set below checks the sign independently.

**What it cannot reach**: `QUADS`, `QUAD_STRIP` and `POLYGON` under line mode
reach `geom.c` already rewritten to `PRIM_TYPE_LINES`
(`prim_rewrite.c:254-268`), so their face is gone by then.  Culling them needs
the source polygon's winding carried through the rewrite, which is a separate
design.  No capture in the corpus draws a back-facing line-mode quad or
polygon with cull enabled (Shade_model's are all front-facing: silicon draws
every one, 0 px of class A), so nothing scores that case today.

**Strip parity** is the risk.  In `TRIANGLE_STRIP`, `prim_rewrite.c`
reflects odd triangles (see `docs/lanes/primpv13/NOTES.md`).  If the
reflection does not restore a consistent winding, the area test culls every
other strip triangle.  `Shade_model/ProgLM_TriStrip_*` is the guard for it:
silicon draws every strip triangle there with cull enabled.

### must_move / must_not_move for the arm that lands the hunk

These are bounds from this attribution, not values.  The model assumes the
fix removes exactly class A and nothing else.

- **must_move** (all 12 `Front_face/FrontFace_LM_*`):
  - The 4 `CF_FaB` captures go from 3,911 structural px to **≤ 20** each.
    With no culling nothing gets there, so this is the leg that shows the
    hunk executed.
  - The 4 captures now at 3,030 and the 4 now at 2,258 go to **≤ 720** each:
    B's 678 plus D's 18-20, which the hunk does not touch.
- **must_not_move** (byte-identical expected):
  - `Shade_model/ProgLM_*` (24): cull enabled, every triangle front-facing on
    silicon.  A wrong sign culls whole triangles, and wrong strip parity culls
    half of `ProgLM_TriStrip_*`.
  - The `Line_width` captures that draw `Tri`/`TFan` blocks: same argument
    and the same default cull state.
  - `3D_primitive/Lines*`, `LineStrip*`, `LineLoop*`: line primitives, which
    the hunk must not reach.
  - `Front_face/FrontFace_FM_*`: fill mode, which is not widened.

## B. Tie strokes: 14,600 px, in all three families, and not a rasteriser rule

Per stroke (`lm_strokes.py`), **every slanted stroke in all three families has
shift fraction f = 0**.  A constant sub-pixel offset between our line centre
and silicon's would move a fraction |d| of the cuts of *every* slanted stroke,
so that is refuted.  The shifted cuts sit on a handful of **whole strokes**
(f = 1) that are axis-aligned or nearly so, with ours one pixel toward the
higher index:

| family | stroke | silicon | ours |
|---|---|---|---|
| Front_face | quad's horizontal edges, integer y = 44 and 430 (passthrough) | rows 43, 429 | 44, 430 |
| 3D_primitive | bottom line, kBottom at kZBack | row 324 | 325 |
| 3D_primitive | the near-horizontal LineStrip/LineLoop segment (t = 0.017) | f = 0.80 | |
| Shade_model | world x = 0 vertical (TriFan, QuadStrip), screen x = 320 | column 319 | 320 |

Other strokes on the same axes are exact, including Front_face's verticals at
integer x = 138 and 310 (the same vertices as the shifted horizontals),
3D_primitive's top line and ProgLM's kLeft/kRight/-0.4 verticals.  So the
shifted strokes are the ones whose minor coordinate lands exactly on a pixel
boundary, i.e. ties.

It is not a tie rule.  `lw_tie_axis.py` reruns `line_extent_phase.py`'s own
cuts: Line_width, which uses **the same passthrough shader** with w = 1,
breaks **47 of 47 y-axis ties and 941 of 941 x-axis ties low-open**, as we do,
and 0 of 988 high-open.  Front_face breaks its y ties the other way and its x
ties the same way, on the same vertices.  No rule on the screen position can
do both.  What differs is what produced the coordinate:
- Front_face's quad carries w = INF/0/0.98;
- ProgLM's x = 320 comes out of a perspective vertex program;
- 3D_primitive's bottom line comes out of the fixed-function transform.

That is the class `glsl/vsh.c:547-561` already records for #49: "coverage is
decided by the last bit of the transform", where silicon resolves two
coordinates on the same grid line in opposite directions.  Nothing is proposed
for B here.  The measurement that would separate "silicon's transform lands
below the grid line" from anything else is a console variant (lane.xbox):
Line_width's passthrough geometry at integer y with w = 2 instead of 1, and
with w = INFINITY on one endpoint.  A change in the tie direction between the
two names w as the input.

## C. Flat colour in a line-mode quad/polygon: 7,324 px, Shade_model only

Only `ProgLM_{Quad,QuadStrip,Poly}_Flat_*` carry it (982-1,388 px each).  The
smooth variants and every flat Tri/TriStrip/TriFan have **0** colour px.  On
silicon the whole wireframe quad is one colour (`flat_edge_colour.py`: all
four edges of the left quad carry vertex 3's colour), and **FIRST and LAST
give the same golden**.  We colour each edge from its own first endpoint,
because these primitives reach `geom.c` as independent LINES (see A) and
`emit_line()` takes the flat colour per edge.  This is prim_rewrite's
flat-wireframe corner, which PR #194 left as "narrowed, not abolished".  It is
a colour question in `prim_rewrite.c`, not a stroke rule.  Which vertex
silicon picks is read here on one quad only (vertex 3 of 0-3).  The second
quad's colours pass through the program's lighting, and the probe did not
separate them.  Settle it on all three primitives before writing a rule.

## D. Extent / phase: 3,852 px

The rule under test is Line_width's `E = w * (1 + t/2)` at w = 1, scored **per
stroke on the goldens alone** (`lm_extent.py`: the mean run length on a stroke
must equal E within 2 sigma of the mean over its cuts).  It is fitted on
nothing new, since the constants come from Line_width.

| set | strokes within tolerance | ink on the scored cuts, observed vs E predicts |
|---|---:|---:|
| positive control, `Line_width/Line_0001.0` | 26 / 30 | 1,944 vs 1,804 |
| **Front_face** (the fit family) | **4 / 4** | 714 vs 709 |
| **Shade_model** (held out) | 23 / 35 | 10,330 vs 9,555 |
| **3D_primitive plain** (held out) | **5 / 17** | **2,208 vs 2,426: every stroke's mean is exactly 1.000** |

- **D1, Shade_model: consistent with the rule.**  Its 12 misses go both ways
  (obs > exp on long chains that join two edges at a shared vertex, obs < exp
  on two), which is the instrument's chaining, not an extent.  Our own runs
  agree: 532 cuts longer and 780 shorter than silicon (`lm_runlen.py`),
  two-sided, so this is phase.  Front_face: 32 of 12,600 cuts differ in
  length.
- **D2, 3D_primitive: refutes the rule.**  Silicon lights **exactly one
  pixel per major step** on all 17 slanted strokes, 2,208 cuts and 0 of
  length 2, including an exact 45-degree line that Line_width's w = 1 golden
  draws two pixels thick.  Our runs are one-sidedly longer: 3,676 cuts longer,
  16 shorter.  So at the same register width, silicon draws these thinner
  than E = 1 + t/2.  Candidates, none established: `SMOOTHING_CONTROL =
  0xFFFF0000` during the draw (only 3D_primitive, Swath_width and Smoothing
  set it), the fixed-function transform, and depth/alpha/blend.  The
  measurement that separates them is a console variant of Line_0001.0 with
  `SMOOTHING_CONTROL 0xFFFF0000` pushed.

## Falsifier verdict, as the brief asked

The rule fitted on Front_face (culling aside, Front_face's strokes are the
Line_width rule: 4/4 extent strokes, 10,184 of 10,200 row cuts exact) predicts
Shade_model's stroke geometry and **fails on 3D_primitive**.  So it is two
causes, not one, and #13 splits.  Honestly it is more than two: the four
causes above are separate mechanisms in separate files, and the largest one
(A) is not a rasterisation rule at all.

Suggested split, for the board (this lane edits no tracker file):
1. **A (31,152 px)**: line-mode triangle culling, the geom.c hunk above.
   Offline-derived, with must_move/must_not_move ready.
2. **C (7,364 px)**: flat colour of line-mode quads/polygons in
   `prim_rewrite.c`.  The provoking vertex needs reading on all three
   primitives first.
3. **D2 (~2,600 px)**: 3D_primitive's thin-line extent.  Needs a console
   variant.
4. **B (14,600 px)**: tie strokes.  Belongs with #49's viewport-9/16 class,
   not with a line rule.

## Captures

- Front_face and Shade_model:
  `dispatch/results/1790373302-arms-wparamcode223-fix-991557/captures1`
  (ref `8555c013c6`, 2026-09-25 14:29 PDT).
- 3D_primitive:
  `dispatch/results/0-0-d-1790381162-arms-tcgchurn-fix-1743435/captures1`
  (ref `1ce8693eb1`, 16:02 PDT).

Between those refs and base `24208f15cb`, `geom.c` changed only in the
fill-mode one-negative-w wedge, and `vsh.c`/`vk/draw.c` only in NaN colour
and vertex-surface overlap.  The line path, culling and `prim_rewrite.c` are
unchanged, so the attribution describes current master.

## Tools (all in this directory, goldens and captures only, no device)

| tool | what it answers |
|---|---|
| `lm_survey.py CAP` | differing / structural px per capture |
| `lm_attrib.py --cap ...` | the A/B/C/D attribution table |
| `lm_cuts.py --cap ...` | colour vs placement px, per-axis cut outcomes |
| `lm_strokes.py --cap ... --family F` | per-stroke shift fraction f (B) |
| `lm_extent.py --family F` / `--suite-glob Line_width 'Line_0001.0'` | held-out extent test on goldens (D) |
| `lm_runlen.py --cap ...` | (golden, ours) run-length pairs, one-sided vs two-sided |
| `lw_tie_axis.py` | Line_width tie cuts by axis, low- vs high-open |
| `ff_cull_table.py CAP` | which primitives silicon draws per Front_face golden (A) |
| `flat_edge_colour.py CAP` | flat edge colours, golden vs ours (C) |
| `lm_view.py`, `lm_probe.py` | pictures and pixel columns |

`lm_cuts.thin_runs` is pure Python, so a whole-family run takes minutes.

## Do not repeat

- Do not fit a sub-pixel offset or a tie direction to B.  Line_width pins
  both tie directions the other way on 988 cuts with the same shader, so a
  fit would trade them away.
- Do not read the 3D_primitive bottom line as a colour defect.  It is drawn
  one row lower (325 vs 324) over a gradient, and the colour column is 40 px.
- Do not score `-ls`/`-ps` 3D_primitive variants with these families.  They
  render into a 2x-wide AA surface and blit it, which is a different path.
