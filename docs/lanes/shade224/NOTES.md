# lane.shade224 -- #224: Shade model residual, classified

**Offline-only result.** No patch, no arm. The fix for the largest non-wash
family needs hw/ files outside this lane's Files, so a board request asks for
them (section 5). Section 4 gives the arm that fix needs.

## 0. Baseline, and why it is master's

- Data: `dispatch/results/1789968297-arms-primpv13-fix-2094234` (Thor, ref
  40ca2bcb22, apk 7b846e188dff), goldens `~/goldens/results/Shade_model`.
  It re-derives #224's post-#194 total to the pixel: **3,757,098**. The base
  arm `...-base-2094212` gives 3,757,101, the issue's pre-#194 figure.
- No Shade_model score on disk is newer than #194's fold (2026-09-25T08:04Z).
  The newest is this arm, from 09-21. So I dated the **code**, not the file:
  `git diff 40ca2bcb22 a6bb4a13d4 -- hw/` touches `prim_rewrite.c` and
  `glsl/geom.c` in comments only. The one `gl/draw.c` hunk (#164's
  pad-bit clear colour) is inside `#ifndef __ANDROID__`, and `pmc.c`
  does not render. For this suite on the Thor, the fix arm's binary is
  master's, so no fresh arm was needed.

## 1. Classification: no coverage anywhere, and three families

`shade_split.py` groups the output of lane.wparam223's `split()`
(`docs/lanes/wparam223/wparam_split.py`, PR #228). It imports that function
rather than copying it, so PR #228 must be folded (or the file present)
before it will run. The categories are **wash** (max-channel |d| 1..2),
**coverage** (|d|>2 and exactly one side is the clear colour) and **value**
(|d|>2 and both sides drew).

| path x shade | n | diff | wash | cov | value |
|---|---:|---:|---:|---:|---:|
| W_Fixed Smooth | 12 | 1,135,813 | 1,135,813 | 0 | 0 |
| Prog Smooth | 12 | 735,800 | 735,692 | 0 | 108 |
| W_Fixed Flat | 12 | 619,430 | 619,430 | 0 | 0 |
| Fixed Smooth | 12 | 504,356 | 504,356 | 0 | 0 |
| W_FixedTex Flat | 12 | 282,356 | 0 | 0 | 282,356 |
| Fixed Flat | 12 | 264,755 | 264,755 | 0 | 0 |
| ProgTex Flat | 12 | 96,900 | 0 | 0 | 96,900 |
| FixedTex Flat | 12 | 95,552 | 0 | 0 | 95,552 |
| ProgLM Smooth / Flat | 24 | 20,804 | 9,630 | 0 | 11,174 |
| every *Tex Smooth, Prog Flat | 48 | 1,332 | 0 | 0 | 1,332 |
| **total** | 168 | **3,757,098** | **3,269,676** | **0** | **487,422** |

**Coverage is zero on all 168 captures.** Every differing pixel is inside a
primitive both sides drew, so the edges are not the problem. The residual
falls into three families. PR #228's classifier files two of them together as
"wash", but they have different mechanisms:

| family | captures | px | kind |
|---|---|---:|---|
| A. flat-quad diagonal | *Tex x Quad/QuadStrip x Flat (12) | **474,214** | value, interior |
| B. FF lighting tie | Fixed/W_Fixed x Flat (18 of 24) | **884,185** | 1 LSB, one colour |
| C. interpolator wash | every Smooth untextured | **2,385,491** | +-1..2 gradient |
| (rest) | ProgLM line mode, stragglers | 13,208 | value |

### A. Flat quads are split on a different diagonal from silicon (474,214 px)

In Flat mode, `rewrite_quads()` (prim_rewrite.c:398-403) splits each quad on
v1-v3, and `rewrite_quad_strip()` (473-478) splits each strip quad on v0-v3,
so that provoking vertex v3 lands at index 0 of both triangles. Smooth mode
uses v0-v2 and v1-v2, "matches hardware quad tessellation". Texture
coordinates interpolate per triangle, so on a non-parallelogram quad the
diagonal changes the texture mapping inside the quad.

The goldens show that silicon does not change diagonal with the shade mode.
**Silicon's `FixedTex_QuadStrip_Flat_First` texture pattern is identical to
its `_Smooth_First` one.** Ours matches silicon in Smooth (6 px) and not in
Flat (43,456 px). Every differing pixel is one of the two checker colours
swapped: (112,0,0) and (192,192,32), ±(80,192,32), and nothing else.
It is confined to exactly the rewritten primitives:

| capture (First = Last) | Flat | Smooth sibling |
|---|---:|---:|
| W_FixedTex_QuadStrip | 98,922 | 14 |
| W_FixedTex_Quad | 42,185 | 24 |
| FixedTex_QuadStrip | 43,456 | 6 |
| ProgTex_QuadStrip | 43,453 | 115 |
| ProgTex_Quad | 4,778 | 29 |
| FixedTex_Quad | 4,313 | 104 |
| *Tex Tri / TriStrip / TriFan / Poly Flat | 0-44 | - |

The untextured flat quads don't show it: a flat colour is the same on either
diagonal. That is why the sweep (`sweep-raster.md:371`) recorded this as "a
depth-slope difference" and #31 ruled it out for W-buffering. Nobody had
priced it on textured geometry until now.

**The colour constraint still holds.** Silicon takes the quad's flat colour
from v3 regardless of FLAT_SHADE_OP. Our `Fixed_Quad*_Flat` and
`Prog_Quad*_Flat` match silicon's colour: 10 and 12 px on Prog, and only the
family-B tie on Fixed, with First and Last equal. So the fix cannot just
drop the flat branch. The v0-v2 triangle (v0,v1,v2) does not contain v3, and
it still has to be coloured by v3.

### B. One fixed-function lighting tie (884,185 px, one colour pair)

Every differing pixel in all 24 Fixed/W_Fixed Flat captures is ours
(0,85,59) against silicon's (0,85,60): **one colour pair, 884,185 of
884,185 px.** The six captures at 0 are Poly, and Tri_Flat_Last on both
paths, which are the ones where vertex 3 does not provoke. The test lights
with infinite light direction (0,0,1), diffuse (0,1,0.7) and material 1.
Normal 3 is (-0.66667, 0.66667, 0.3333333), so B = 0.7f x 0.3333333f x 255
= **59.49999**. That is a rounding tie, and silicon writes 60.

I checked this against every other flat colour in the goldens. Round-to-nearest
of z x 255 and 0.7z x 255 reproduces every one: 147/103, 208/146, 186/130,
119/84, 204/143, 74/52, 231/161, 255/179. Normal 1's B = 178.49999 is the
other tie, and silicon rounds it up to 179 **as we do**. So silicon sits a few
ulp above us on this path, and on one of two ties that is enough to cross.
**The data is two points, and I did not fit a rule to them.** Normalisation
is off in this test (`vsh-ff.c:474` gates it), so the tie is set by float
rounding through `invModelViewMat0` and the light setup. It is a genuine
value defect, but the size of a precision floor: 1 LSB on one primitive.

### C. The interpolator wash (2,385,491 px)

This is every Smooth untextured capture. It has both signs in every path, with
a per-channel tilt: FF B is -1:774k against +1:151k, Prog G is -1:395k against
+1:78k, and Prog B is +1:256k against -1:78k. PR #228 found the same thing in
W_param. It is the #12/#58 interpolator population (tracker disposition
`precision-floor`).

## 2. Is #224 a duplicate of #223? No

The brief asked whether `W_Fixed_*_Smooth` are the same captures as #223's
wash. **They are not the same captures.** #223 is the `W param` suite and these
are `Shade model` captures. They are the same **population**: `W_Fixed_*_Smooth`
is 1,135,813 px, all family C, which is what PR #228 calls wash. But family C
is only 63% of #224. The other two families are not in #223 at all:

- Family A (474,214 px) is a primitive-assembly defect with a named line of
  code. It has nothing to do with w: `FixedTex_Quad_Flat`, which has no W_,
  shows it too.
- Family B (884,185 px) is in `W_Fixed_*_Flat` and `Fixed_*_Flat`. PR #228's
  "W_Fixed_* are 100% wash" is **true of its classifier, but it mixes this
  family in**. 619,430 of `W_Fixed`'s 1,755,243 px are this flat
  lighting tie, not interpolation.

So I have **not** closed #224 as a duplicate. Family C should be worked with
#223's wash (and #12/#58), not twice. Families A and B belong to #224.

## 3. The leads, and what each one is

| lead | verdict | evidence |
|---|---|---|
| provoking vertex (#194) | refuted by #224 itself | 3 px moved; First = Last on every quad |
| coverage / edges | **refuted** | cov = 0 on 168 of 168 captures |
| W / interpolation shared with #223 | partial: family C only | section 2 |
| flat-quad diagonal | **named mechanism**, 474,214 px | section 1A |
| FF lighting tie | named, not fitted, 884,185 px | section 1B |

## 4. The arm the family-A fix needs (not registered: no patch yet)

**The patch.** Keep silicon's diagonal in Flat mode and source the flat
varyings from v3 without putting v3 into the triangle. Under
`GL_TRIANGLES_ADJACENCY` / `VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST_WITH_ADJACENCY`,
each triangle is six indices: `(a, v3, b, v3, c, v3)`. The geometry shader
draws gl_in[0,2,4] and reads vtxD0/D1/B0/B1 (and vtxFogSpecial) from
gl_in[1]. That needs three changes:

- `prim_rewrite.c` `rewrite_quads()` / `rewrite_quad_strip()` flat branch:
  emit on v0-v2 / v1-v2 with the adjacency slots. Also update
  `max_output_indices` and the rewritten mode.
- `glsl/geom.c`: a `layout(triangles_adjacency) in` path, where the
  provoking index is 1 and positions come from 0/2/4.
- The GL and VK draw calls: the primitive for that mode.

Only flat, filled quads reach this path. Line mode uses the
`rewrite_*_line` paths and is untouched.

A cheaper design is **wrong**. Dropping the flat branch alone would fix
texture and break colour: (v0,v1,v2) would take v0's colour. That would move
`Fixed_Quad_Flat` from 54,720 px to about the whole first triangle of each
quad in a different colour. The must_not_move leg below catches exactly that.

**must_move.** These are the 12 captures above. They should fall to at most
their Smooth sibling + 200:

- W_FixedTex_QuadStrip_Flat_{First,Last}: 98,922 -> <= 214
- W_FixedTex_Quad_Flat_{First,Last}: 42,185 -> <= 224
- FixedTex_QuadStrip_Flat_{First,Last}: 43,456 -> <= 206
- ProgTex_QuadStrip_Flat_{First,Last}: 43,453 -> <= 315
- ProgTex_Quad_Flat_{First,Last}: 4,778 -> <= 229
- FixedTex_Quad_Flat_{First,Last}: 4,313 -> <= 304

Suite total -474,214 +- 3,000.

**The world in which must_move fails:** silicon's Flat texture mapping is not
its Smooth one for a reason other than the diagonal. One example: silicon
interpolates texcoords over the whole quad bilinearly, and the Smooth
diagonal matches only because these quads are near-parallelograms. Then the
Flat captures would move toward the Smooth sibling but stop short of it.

**must_not_move.** These pin the colour source, which the patch rewires:

- Fixed_Quad_Flat_{F,L} stay at 54,720 +- 300
- Fixed_QuadStrip_Flat_{F,L} stay at 53,494 +- 300
- W_Fixed_Quad_Flat stay at 122,079 / 122,149 +- 600
- W_Fixed_QuadStrip_Flat stay at 125,652 +- 600
- Prog_Quad_Flat and Prog_QuadStrip_Flat stay at 10 / 12, <= 200

These pass or hold today with only family B in them. **They fail in the world
where the adjacency slot delivers the wrong vertex** (v0 or v2 instead of v3):
the counts jump by tens of thousands in a second colour. The patch does not
force them true, because it changes the very line that picks the colour. The
tolerance allows only for the diagonal pixels, where the two triangles'
shared edge now falls on a different line.

Also must_not_move: every Smooth capture (the patch is gated on flat), all
Tri/TriStrip/TriFan/Poly Flat captures (not quads), and ProgLM_* (line
mode), each within +- 50.

## 5. Board request

Written to `dispatch/board-requests/shade224.md`. It asks for
`hw/xbox/nv2a/pgraph/prim_rewrite.c` (rewrite_quads / rewrite_quad_strip
flat branches and max_output_indices), `hw/xbox/nv2a/pgraph/glsl/geom.c`
(triangles_adjacency input), and the GL and VK draw-mode mapping for the new
mode. It also asks for a new #224 tracker row: family A named, family C
routed to #223/#12.

## 6. Do not repeat

- Re-deriving the baseline: the fix arm is master's binary for this suite
  (section 0).
- Looking for coverage: there is none.
- Chasing W for the largest captures: `W_Fixed_QuadStrip_Smooth` is family C,
  and `W_Fixed_*_Flat` is family B. Neither is a w mechanism.
- Fitting family B from its two ties. It needs either the GPU's exact lit
  value (a shader debug dump of oD0 for normal 3) or a new capture with more
  tie normals.

## Files

- `shade_split.py`: the per-axis classification above (imports PR #228's
  `split()`).
- `probe.py`: signed per-channel histogram, colour pairs and bbox per
  capture.
