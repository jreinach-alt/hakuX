# lane.spheremap273 -- #273 SphereMap_RotateX / SphereMap_Arbitrary

Base: master @ 8e683b3a26. Outcome: mechanism found and priced offline; the fix
is one case in `pgraph.c` `kelvin_map_texgen`, which is lane.vshsubneg255's
file. The hunk is below, the path is requested on the PR, and no prediction is
registered because a b_ref has to contain the hunk.

## 1. What the test does (nxdk_pgraph_tests `texgen_matrix_tests.cpp`)

- One quad, `DefineBiTri(-2.75, 1, 2.75, -2.5)`, at world z = 0. Normal
  (0,0,1), texcoord0 = (u,v) with r = 0. XDK default camera at z = -7, so every
  vertex is at the same eye depth.
- `SetTexgenS/T/R(mode)`: **R is set to the same mode as S and T**. Q stays
  disabled (w = 1). The texture matrix is enabled, and `STAGE_2D_PROJECTIVE`
  samples (s/q, t/q).
- Texture: `GenerateSurface` 256x128, red = row*255/128, green = col*255/256,
  blue = 255 - red. So a pixel's red reads t and its green reads s directly.

Why only two of the eleven SphereMap matrices fail: in the column-vector form
the test prints, **RotateX** has t' = R, and **Arbitrary** has q' = R (row 3 is
(0,0,1,0)), with s' and t' also taking 0.515R and 0.49R. These are the only two
matrices where the R texgen output reaches s, t or q. In RotateY, s' = -R, which
is clamped to texel 0 whether R is 0 or 0.9, so the difference never shows.

## 2. Where xemu is wrong (first difference)

`hw/xbox/nv2a/pgraph/pgraph.c` `kelvin_map_texgen`: SPHERE_MAP on channel >= 2
is mapped to DISABLE (#28's anti-abort guard). The vertex shader therefore emits
`oT0.z = texture0.z = 0`. The vsh-ff.c:699 guess in the brief is not the site:
the sphere-map code there is never reached for R.

- RotateX: t' = 0, so every pixel reads texel row 0 (blue). Silicon reads rows
  near 0.9 (orange).
- Arbitrary: q' = 0, so s/q and t/q go to infinity and both clamp (flat yellow).
  Silicon draws a finite gradient.

## 3. Silicon's R, derived from the golden region

Per vertex (eye p = (x, y, -7), u = normalize(p), r = reflect(u, n)):

| corner | S (xemu = golden) | T | u.z | golden R (RotateX red/255) |
|---|---|---|---|---|
| top (y = 1) | 0.4076 / 0.5924 | 0.5336 | 0.9226 | 235/255 = 0.922 |
| bottom (y = -2.5) | 0.4106 / 0.5894 | 0.4187 | 0.8832 | 225/255 = 0.882 |

**R = r.z, the reflection vector's z**: the value REFLECTION_MAP already emits
on R. It is not the sphere formula applied to z: `r.z*invM + 0.5` gives
0.735, not 0.92.

`docs/lanes/spheremap273/price.py` renders all 11 SphereMap matrices over the
whole quad (per-vertex texgen, attributes interpolated before the q divide,
bilinear, clamp) for three candidate R values, and scores each against the
golden (131,495 px per capture, count of pixels off by more than 2):

| matrix | R = 0 (xemu today) | **R = r.z** | R = r.z*invM+0.5 | xemu capture |
|---|---|---|---|---|
| RotateX | 131,495 (max 235) | **0 (max 1)** | 131,495 (max 49) | 131,495 (max 235) |
| Arbitrary | 131,495 (max 43) | **0 (max 1)** | 131,495 (max 25) | 131,495 (max 43) |
| other 9 | 0 | 0 | 0 | 0 |

The model has been checked in both directions. With R = 0 it reproduces xemu's
own capture error exactly (235 and 43 max on every pixel). With R = r.z it
lands within 1 LSB of silicon on every pixel. The sphere-z row fails
everywhere, so the model can reject a wrong R.

Independent support: `ReflectionMap_RotateX` and `ReflectionMap_Arbitrary`
put the same `r.z` datapath (REFLECTION_MAP on R) through the same matrices,
and they are already exact (0 px > 2 at z-tip-067).

Residual ambiguity: with n = (0,0,1), r.z = -u.z = -(n.u) at every vertex, so
this test cannot tell "reflection z" apart from "-u.z" or "-(n.u)". A test
with a tilted normal would. Reflection z is chosen because it is the datapath
the hardware already has for R.

## 4. The hunk (pgraph.c `kelvin_map_texgen`; file held by lane.vshsubneg255)

```c
    case NV097_SET_TEXGEN_S_SPHERE_MAP:
        /* Sphere mapping on R gives the reflection vector's z, the value
         * reflection mapping puts there: Texgen with texture matrix
         * SphereMap_RotateX reads it as t and SphereMap_Arbitrary as q, and
         * both goldens match r.z to 1 LSB over the whole quad (#273). Q has
         * no evidence yet. */
        if (channel == 2) {
            texgen = NV_PGRAPH_CSV1_A_T0_S_REFLECTION_MAP; break;
        }
        if (channel >= 3) {
            NV2A_UNIMPLEMENTED("texgen SPHERE_MAP on channel %u", channel);
            texgen = NV_PGRAPH_CSV1_A_T0_S_DISABLE; break;
        }
        texgen = NV_PGRAPH_CSV1_A_T0_S_SPHERE_MAP; break;
```

The comment above the switch ("What the hardware does with the request is not
known") should be narrowed to Q and to NORMAL/REFLECTION on Q.

This stores 5 (REFLECTION_MAP) in the CSV1 R field, where silicon may store 3.
A guest could read CSV1_A back over PGRAPH MMIO, but no test does, and xemu's
own readers are the shader-state builder (glsl/vsh.c) and `vk/renderer.c:1274`,
which only writes diagnostic JSON. A version that keeps 3 in the register would
need a `j == 2` branch in vsh-ff.c's SPHERE_MAP case. That touches a second
held file (lane.shadetie224b's) for no pixel difference, so it is not
recommended.

## 5. The arm (for whoever holds pgraph.c)

Register after the last rebase, with a_ref = the merge base and b_ref = the
hunk commit:

- **must_move**: `Texgen_with_texture_matrix/SphereMap_RotateX` 131,495 -> 0,
  `Texgen_with_texture_matrix/SphereMap_Arbitrary` 131,495 -> 0 (residual
  allowance: rounding at <= 2 per channel, as in the other nine).
- **must_not_move**: `Texgen_with_texture_matrix/*` (other than those two).
  The hunk is gated on (SPHERE_MAP, channel 2), and only the 11 SphereMap
  captures send that pair.
  - The other 9 SphereMap matrices do not route R into s, t or q (table in
    section 1; the model scores them identically under all three R values).
    A leg there moves only if the patch also changed S or T, for example by
    touching the `channel < 2` path.
  - The Disabled, EyeLinear, ObjectLinear, NormalMap and ReflectionMap
    captures never send SPHERE_MAP. A leg there moves only if the patch
    changed another case of the switch.

  No other golden anywhere has "SphereMap" in its name, and `texgen_tests.cpp`
  keeps TG_SPHERE_MAP commented out. No other suite exercises the path.

Expected: +262,990 px recovered, no other capture moves.

## 6. Do not repeat

- The vsh-ff.c:699 lead: that code only runs for S and T. R never reaches it
  while the pgraph.c mapping turns it into DISABLE.
- Point-sampling the quad is enough to see the mechanism here, but only
  because the quad is at one eye depth and R depends on the vertex row alone.
  The whole-quad price in price.py is the evidence.
