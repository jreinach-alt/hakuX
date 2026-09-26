# vol283r -- #283 residual: the Y16 / R16B16 low-byte +-1 is #282's v-tie rule

Base: master @ 6550967a5e. Desktop-only analysis; no hw/ file edited.

Inputs, all on disk and dated:

- Arm result dirs `1790367468-arms-texvol283-{base-1190693,fix-1190715}`: Nova,
  fix apk acad684607ae @ a5b4141064, 09-25. Replicates are pixel-identical.
- Goldens `/home/justin/goldens/results/Volume_texture` (abaire 6e159f1, 08-11).
  cloud-283 found console set K == golden (0 px) on every Volume texture
  capture.
- Test source: `fold-pins/nxdk_pgraph_tests/src/tests/volume_texture_tests.cpp`,
  plus `fold-pins/pbkitplusplus` (`DefineBiTri`, XDK matrices).

Read after `docs/lanes/cloud-283/NOTES.md` (PR #338), which this refines, and
`docs/lanes/cloud-282b/NOTES.md`, whose rule it tests on held-out data.

## Answer

**Reading (2), in its filter-tie form, and specifically #282's v-tie rule.**
Readings (1) and (3) are refuted, as cloud-283 found: the `round(t*65535)`
recovery is exact on all 65,536 values, and the error is not a function of
the texel value. What is new here:

1. **Every differing pixel in all 20 Volume texture captures is an exact v tie.**
   That is 34,727 px on the fix arm, Y16 and R16B16 included, with 0 off-tie
   and 0 outside a quad. With the vertices snapped to 1/16 by truncation, the
   bottom four quads are exactly 80 px tall for 256 texels, so every 5th pixel
   row's centre lands exactly on a texel-row boundary. The top three quads are
   1281/16 px tall and have no exact tie. They carry **0** differing px in every
   format.
2. **cloud-282b's binade rule predicts silicon's direction on 6,496 of 6,496**
   decidable Volume texture Y16 tie pixels. That rule was read off one quad
   (w = 8, corners (0,0)-(640,480)), and it is scored here on a different
   geometry it never saw (w = 7, four 135 x 80 quads). A
   pixel-exact model built on it reproduces the **golden Y16 frame with 0 of
   75,840 quad px differing**, and the **golden R16B16 frame with 0 RGB px**.
   texvol283's approximate model fit 83%.
3. **Our own tie direction is noise, and every one of our "down" picks is wrong.**
   Ours goes up on 5,961 tie px and down on 535. On all 535, silicon goes
   up: 0 px have both going down. The 3D sample path has no `texelTieBias`,
   while the 2D path has one.

So the Y16 +1 / -1 split is not a rounding sign. It is two populations:

| Y16 differing px | count | cause | fixed by |
|---|---:|---|---|
| B = +1 (ours up, silicon down) | 2,070 | silicon's binade rule sends T1 v ties down | hunk B only |
| B = -1 (ours down, silicon up) | 534 | our interpolated v lands a hair below an exact tie | hunk A |
| B = +255 at x 122, y 343 | 1 | same as -1, across the `(x+y)&255` wrap | hunk A |

## Method (reproducible without scripts)

- **Geometry.** D3D LookAtLH, eye (0,0,-7), fov pi/4, 640x480, viewport offset
  0.53125, world z = 0, so w = 7. The screen corners come out in float32 and
  are then **truncated** to 1/16. In pixels (X0, X1, Y0, Y1):
  - top row: y 765/8 .. 2811/16 (h = 1281/16), with x 743/8..3649/16,
    1891/8..5945/16 and 6077/16..515;
  - q3: x 1891/8..5945/16, y 2943/16..4223/16 (h = 80);
  - q4, q5, q6: y 1089/4..1409/4 (h = 80), x as the top row.

  Round-to-nearest snapping puts q3's ties at rows 186, 191, ... The
  differences are at 185, 190, ..., so the snap truncates, as cloud-282b
  found for its helper.
- **Vertex roles.** After `DefineBiTri`'s swap the triangles are
  T1 = (UL, UR, LR), where v = l2, and T2 = (UL, LR, LL), where v = 1 - l0.
  These are the same roles as cloud-282b's T1 / T2, so `binade_rule` applies
  unchanged.
- **Texels.** texvol283's `texsim.py` rebuilds memory (RGBA8888 bytes,
  swizzled at 4 Bpp) and reads it at 2 Bpp for Y16. Y16 slices per quad are
  0,0,1,1,2,2,3; p = 1.0 clamps to slice 3. Opaque Y16 pixels show
  (G, B) = (hi, lo), so each tie pixel's direction is read directly: it equals
  row T-1's value (down) or row T's (up). 2,176 of the 8,672 tie px have equal
  values in both rows and cannot be decided.

## Per-format reach of each hunk (fix arm vs golden, RGBA differing px)

D = tie px where Y16 shows ours down and silicon up (hunk A fixes these).
U = ours up and silicon down (only the rule fixes these). "undec" = tie
px Y16 cannot decide.

| capture | differing | in D (A fixes) | in U | undec |
|---|---:|---:|---:|---:|
| Y16 | 2,605 | 535 | 2,070 | 0 |
| R16B16 | 1,638 | 275 | 947 | 416 |
| A8R8G8B8 / A8B8G8R8 / B8G8R8A8 / R8G8B8A8 (each) | 2,734 | 470 | 1,599 | 665 |
| X8R8G8B8 | 2,529 | 330 | 1,550 | 649 |
| A8 | 3,463 | 535 | 2,054 | 874 |
| DXT1, SZ_Index8 (each) | 3,496 | 535 | 2,070 | 891 |
| AY8, Y8 (each) | 2,084 | 371 | 1,533 | 180 |
| A8Y8, G8B8, R8B8 (each) | 710 | 146 | 564 | 0 |
| A4R4G4B4 | 222 | 40 | 131 | 51 |
| A1R5G5B5, R6G5B5 (each) | 22 | 4 | 13 | 5 |
| R5G6B5, X1R5G5B5 | 0 | 0 | 0 | 0 |
| **total** | **34,727** | **5,853** | **22,072** | **6,802** |

No format differs at a tie pixel where Y16 shows ours == silicon (0 px in
every row). There is one defect, and it is format-independent.

## Hunk A -- implementable now: `texelTieBias` on the 3D path

`hw/xbox/nv2a/pgraph/glsl/psh.c:3038-3045`, `case PS_TEXTUREMODES_PROJECT3D`,
non-shadow branch. psh.c is held by lane.fog278 (lent to lane.y16bump10), so
this is named here, not applied:

```c
            } else {
                apply_border_adjustment(ps, vars, i, "pT%d");
-               mstring_append_fmt(vars, "vec4 t%d = textureProj(texSamp%d, %s(pT%d.xyzw));\n",
-                                  i, i, tex_remap, i);
+               if (ps->state->dim_tex[i] == 3) {
+                   /* texelTieBias on u and v, as PROJECT2D (see its
+                    * definition); r is left alone.  Scaled by w so that
+                    * textureProj's divide leaves exactly the bias. */
+                   mstring_append_fmt(vars,
+                       "vec4 t%d = textureProj(texSamp%d,\n"
+                       "    vec4(pT%d.xy + texelTieBias * pT%d.w, pT%d.zw));\n",
+                       i, i, i, i, i);
+               } else {
+                   mstring_append_fmt(vars, "vec4 t%d = textureProj(texSamp%d, %s(pT%d.xyzw));\n",
+                                      i, i, tex_remap, i);
+               }
            }
```

`tex_remap` is dropped only on the 3D branch: it is the rect-texture
normaliser, and volumes are swizzled, so it is `""` there.

**Model prediction (exact rationals, per pixel):**

- Y16 goes 2,605 -> **2,070**: fixes 535, breaks 0.
- R16B16 goes from 1,110 to **746** RGB px: fixes 364, breaks 0. The scorer
  counts alpha, so it should drop by at least the 275 D px.
- Off-tie safety: the bias is 2^-10 texel. The smallest off-tie distance below
  a boundary on any quad and axis is 0.00185 texel (q0/q4 u), a margin of
  8.7e-4 texel over the bias. fp32 interpolation error at 256 texels is about
  1e-5.

**Reach.** The shader text changes only for PROJECT3D on a 3D texture. On the
disc that is Volume texture (all 20 captures) and Texture border's
`3D_BorderTex_SZ_*` (9 captures, PassthroughVertexShader, where cloud-282b
measured silicon's ties up on 92,506 of 92,506 VS-draw px). Texture BRDF is
DOT/BRDF and Texture 3D as 2D is PROJECT2D. The other suites generate
byte-identical shaders.

**Legs, ready for briefs/pshqueue.md** (suites: Volume texture, Texture border,
Texture format, Bump map, Bump env lum, Texture render target, Texture BRDF):

- `must_move` (better): `Volume_texture/Y16` (2,605 -> 2,070 +-0),
  `Volume_texture/R16B16` (down by >= 275),
  `Volume_texture/A8R8G8B8` (down by >= 470), `Volume_texture/X8R8G8B8`
  (down by >= 330), `Volume_texture/A8Y8` (down by >= 146).
- `must_not_move`: `Volume_texture/R5G6B5`, `Volume_texture/X1R5G5B5` (0),
  the nine `Texture_border/3D_BorderTex_SZ_{1x1,2x2,4x4,4x8,8x2,8x8,16x1,16x16,32x32}`
  (0 today, host-turnipctl 9395b70d7cf1), and every capture of the other
  five suites.
- **Refuting world:** any Volume texture capture gets worse, or any
  `3D_BorderTex` leaves 0. Either means our 3D ties are not "a hair below"
  as modelled. (A second refuting world, "Y16 moves by more than 535": the
  bias reached an off-tie pixel.)
- Expected suite total: about -5,853 px, or more where the undecided px are
  also D.

## Hunk B -- the rule itself: not implementable in psh.c alone

The +1 class (22,072 px suite-wide, 2,070 on Y16) needs silicon's binade rule:

    T1 v tie goes down  iff  l2 <= 1/2  and not (l0 in (1/4,1/2] and l2 in (1/4,1/2])
    everything else goes up

It needs the triangle's barycentric weights per fragment, and which vertex
carries which weight. PR #376 (lane.tie282c) points out that psh.c already
receives `vtxPos0..2` from geom.c, and that only the per-vertex texcoords are
missing. That is #282's hunk (`glsl/geom.c` + `psh.c:2018-2019`,
`texelTieBias`'s v half, made conditional), not #283's.

**What changes for #282:** cloud-282b declined a code lane because the rule
was "a fit to two triangles". #376 then scored it on
`Texture_render_target` row 240 (6,108 / 6,108), but only in the l2 = 1/2 cell
the checkerboard already had. Volume texture is a **different geometry
across the whole cell table**: four quads at different screen positions,
w = 7, 3.2 texels/px, with T1 ties in l2 binades 2^-6, 2^-4, 2^-3, 2^-2 and
2^-1 and every l0 binade from 2^-9 to 2^-1, plus 32 px at l0 in [2^-12, 2^-11). That
last cell is below the checkerboard's range (l0 >= 1/640), so it is new;
most of the others are cells the checkerboard also had, reached here at
different weights and positions. The rule predicts all 6,496 / 6,496
decidable px, band included (412 up at l0, l2 both in [1/4, 1/2)), and it
reproduces two whole golden frames pixel-exact. One condition remains
open: the rule's general form for a triangle whose vertices are not UL/UR/LR
with v = (0, 0, 1). All three geometries share those roles.

## Reading (2)'s falsifier

"Refuted if a candidate rule moves any pixel that is exact today":

- **Rule (hunk B):** on Volume texture Y16 / R16B16 it moves 0 exact px (the
  model breaks 0). It was not checked on the 184 other captures offline. It
  applies only to FF T1 v ties, and cloud-282b scored it at 99.88 / 99.80 /
  99.96% on the checkerboard suites' 1.19M tie px.
- **Bias (hunk A):** on the decided Y16 set it breaks 0 (0 px where ours and
  silicon both go down). It cannot move any pixel outside the PROJECT3D + 3D
  path. The 6,802 undecided px are covered only by the R16B16 model
  (breaks 0) and by the arm.

## For the board

- Record #283 as **reading (2): texel-tie direction, #282's rule**, not a
  precision floor and not a 16-bit defect. The 16-bit part closed with
  PR #289.
- Queue hunk A (named above) for pshqueue once psh.c is free. It is small
  and one-armed, and its legs are listed above.
- The +1 class, 22,072 px over the suite, belongs to #282, with the
  held-out result above as its new evidence.

## Not chased

- The 8888 / A8 / DXT1 / palettised decodes: their upload goes through
  different converters (my RGBA8888 decode scores 75,526 px off on A8R8G8B8).
  Their move counts above come from Y16's per-pixel direction map instead.
- The general-triangle form of the binade rule, and the arithmetic behind it.
- Checking the rule on the 184 non-Volume captures. `Texture_render_target`
  row 240 is #376's.

## Do not repeat

- Do not model the Volume texture geometry from quad boxes (texvol283's
  `fitall.py`, 83%). Use the truncated-1/16 corners above; they are pixel-exact.
- Do not read the +1 / -1 split as a rounding sign. It is two causes, and
  the -1 is ours alone.
- Do not bias r (the slice coordinate). Every residual pixel is a v tie
  inside one slice.
- Do not look for this residual in the top-row quads. They have no exact
  ties and are 0 px in every format.
