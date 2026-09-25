# lane brdf315 -- #315 Texture_BRDF

Base: origin/master @ fab230935e (contains #223's fold 8e683b3a26).
Goldens: `~/goldens` @ 6e159f1 (2026-08-11); test source
`~/nxdk_pgraph_tests` @ 6743b6a, `texture_brdf_tests.cpp` last touched 33e7c6b
(2026-09-01). All three goldens have the same 614-px wedge: same mask, same
colours, byte for byte.

Tools in this directory (desktop, numpy + PIL):
- `brdf_geom.py` replicates the test's transform on the CPU and prints each
  cube vertex's w and screen position.
- `brdf_fit.py` rasterises the draw over the golden's wedge, samples the two
  generated cube maps, and scores candidate BRDF rules per pixel. It prints
  the price.
- `brdf315-psh.diff` is the hunk (see section 4). It applies cleanly to
  fab230935e.

## 1. Which defects remain at current master: one (defect 1)

The issue stacks two defects. **Defect 2 ("we do not rasterise the wedge")
is refuted from source.** At current master only defect 1 remains:
`PS_TEXTUREMODES_BRDF` produces t2 = 0.

- **The wedge is ordinary geometry, and no w is negative.** The draw runs in
  FIXED-function mode. `PerspectiveVertexShader` has no program code: its
  `Activate()` loads nothing, and `TestSuite::SetupTest` had already set
  `SetVertexShaderProgram(nullptr)`. So the position is
  `v * (LookAtLH(eye) * model) * P_xdk`. That is row-vector order, so the
  model's rotate/translate is applied AFTER the view, about the world origin,
  not about the cube's centre. `brdf_geom.py`:

  | draw | w of the 8 vertices | where it lands |
  |---|---|---|
  | 0, (-1.5, 0, 2) | 3.79 .. 7.21, **all positive** | almost wholly off the bottom-right; edge v4 (510.5, 501.2) -> v7 (704.4, 440.0) crosses row 479 at x ~580 and column 639 at y ~460.4 |
  | 1, (1.5, 0, 2) | seven negative, v3 = +0.21 | nothing on screen |

  The wedge is draw 0's **front face** (0,4,7,3), just below that edge.
  Rasterising the model over the golden's wedge covers **610 of 614 px, with
  0 extra**; the other 4 are edge-rule ties. This explains why "neither cube
  appears": each cube does draw, off screen. **#223's one-negative-w wedge is
  not the mechanism.** The triangle has no negative w, and draw 1, the only
  one that does, puts nothing on screen in the golden either.
- **Why ours reads the clear colour.** The suite's default state is
  blending on, `SRC_ALPHA / ONE_MINUS_SRC_ALPHA` (`test_suite.cpp:186`, and
  the `SetBlend()` defaults in pbkitplusplus `nv2astate.h`). The final
  combiner takes colour and alpha from TEX2. With t2 = 0 the source alpha is
  0, so a rasterised pixel blends to exactly the destination:
  (18,18,18,254), alpha 0*0 + 254*1. **Rasterised and unrasterised read the
  same.**
- **So the discriminating run the issue proposed cannot discriminate.**
  "(0,0,0,0) = rasterised" would need blending off. At (639,479) both
  outcomes read (18,18,18,254). The only discriminator is an arm that makes
  t2 non-zero (section 5): a wedge that appears proves it was rasterised.
- **Also, today's t2 = 0 does not come from the `vec4(0.0)` stub.**
  `stage_consistent(ps, vars, i, 2, 3, 2, ...)` requires stages 0 and 1 to
  define dot products. They are CUBE_MAP, so the stage is emitted as NONE
  ("feeding stage produces no dot product") before the stub is reached. And
  `get_sampler_type()` has no BRDF case, so `texSamp2` is never declared.
  Both have to change.
- The read at a ref containing 8e683b3a26 was queued as
  `1790373098-brdf315-964945` (Texture BRDF at fab230935e). Nothing on disk
  was at such a ref: the newest capture, `1790359589-xbox-full6743-dry2`,
  is at 84a67b9cf8, which does not contain it, and the `0-a-now-8e683b3a26`
  sweep stopped at suite 024 of ~071. The expected reading is (18,18,18,254)
  whatever the mechanism; the result is recorded in section 6.

## 2. The BRDF rule, fitted per pixel

The volume the test uploads (`GenerateBRDFFunc`) is 64^3 A8R8G8B8 with texel
(x, y, z) = (R, G, B) = (x, y, z) * 255/63 and A = 255. So each golden colour
decodes straight to a texel index: R 190/194/198 -> x 47/48/49, G 246 -> y 61,
B 202..226 -> z 50..56.

Stages 0 and 1 are R16B16 cube maps (`GenerateSphericalCoordMap`). Each
texel holds its direction's (theta/pi, phi/2pi) as 16-bit fields: phi in the
low half, theta in the high. Texture coordinates: tex0 = the cube vertex
position (eye), tex1 = (0.1, 0.05, +-1) (light, -1 on the front-face
vertices). Stage filters are BOX_LOD0, i.e. nearest (`TestSuite` calls
`SetFilter(0)`).

The rule was scored on the 610 modelled pixels, with nearest cube texels:

| volume axis | best candidate | exact | within 1 texel | every other candidate |
|---|---|---|---|---|
| s (x, R) | theta_eye | 99.8% | 100% | 0% |
| t (y, G) | theta_light | 100% | 100% | 0% |
| r (z, B) | **phi_light - phi_eye**, mod 1 | 99.3% | 100% | 0% (phi_e - phi_l, phi_e + phi_l, each phi alone) |

**(s, t, r) = (theta_eye, theta_light, phi_light - phi_eye mod 1).** The
difference is negative here (about -0.18), so it wraps to 0.82. The test sets
REPEAT on P for that reason. Hardware wrapping it as a 16-bit field
difference, or through the P address mode, cannot be told apart from this
capture. The hunk uses `fract()`, which does not depend on the address mode.

The e1/l1 "blank" variants cannot differ: the test's `memset` blanks
`kTexturePitch * kTextureHeight` bytes, which is **one face** (+X), and the
wedge samples neither eye nor light from +X. So three identical goldens are
what the rule predicts, not a sign that the lookup ignores its inputs.

## 3. Price (offline, per capture)

`brdf_fit.py`, whole-texel (all three channels) agreement over the 610
modelled pixels:

| inputs to the rule | whole-texel exact |
|---|---|
| nearest cube texels, /65536 or /65535 normalisation | **605 / 610** |
| unquantised directions (what a filtered sample tends to) | 187 / 610 |

The 5 misses are each one texel off on one axis, at a texel boundary: CPU
sample-position detail, not a different rule. The large gap between the two
rows says the price depends on the stages 0/1 sampling nearest, which is what
the test sets and what xemu maps BOX_LOD0 to (`GL_NEAREST`).

**Per capture, `BRDF_e0_l0`, `BRDF_e0_l1`, `BRDF_e1_l0`: 614 -> about 9**
(5 boundary texels + the 4 edge-rule pixels, if our rasteriser resolves those
ties differently from silicon). All three captures move by the same amount,
because the goldens are identical.

## 4. The hunk and its holder

`hw/xbox/nv2a/pgraph/glsl/psh.c`, **held by lane.wbufdepth24 (#266)** on
`origin/board` territory. The change is `brdf315-psh.diff`, two parts:

1. `get_sampler_type()`: a `PS_TEXTUREMODES_BRDF` case that returns
   `sampler3D` for a 3D, non-cube, non-shadow texture, and marks the stage
   unusable otherwise. Today it falls through to `default: return NULL`.
2. The `PS_TEXTUREMODES_BRDF` stage (currently psh.c:3123-3128):
   `stage_consistent(..., 2, 3, 0, ...)`, since the feeding stages are
   ordinary reads and define no dot product. Then
   `t<i> = texture(texSamp<i>, vec3(t<i-2>.r, t<i-1>.r, fract(t<i-1>.g - t<i-2>.g)))`.
   With SZ_R16B16's {G,R,R,G} view, `.r` is the high field (theta) and `.g`
   the low (phi).

Not covered: a feeding stage in any other format. Its `.r`/`.g` are not the
16-bit halves, and no capture exercises that. Binding needs no change: the GL
and Vulkan texture binding is not keyed on the stage mode. The GLSL has not
been compiled here; the holder's build is its first compile.

## 5. The arm, ready to register (not registered)

**Not registered**, and `Prediction: none`: its b_ref needs `psh.c`, which
this lane may not commit. Whoever holds psh.c applies `brdf315-psh.diff`,
merges master, and registers after the last rebase:

- **must_move**: `Texture_BRDF/BRDF_e0_l0`, `Texture_BRDF/BRDF_e0_l1`,
  `Texture_BRDF/BRDF_e1_l0`, each 614 -> <= 30 differing. The falsifier is a
  value, not a count: pixel (639,479) must read (198,246,222,255) (texel
  48,61,55, the golden's own) instead of (18,18,18,254).
- **must_not_move**: every other `Texture_*` capture (cubemap, 3D_as_2D,
  signed_component, border, format, ...) and every `Pixel_shader/*` and
  `Combiner/*` capture. The change that would move them: both halves of the
  hunk are reached only when `tex_modes[i] == PS_TEXTUREMODES_BRDF`, and the
  only test that sets BRDF is `texture_brdf_tests.cpp:131` (the
  `pixel_shader_tests.h:41` BRDF test is commented out). One of them moves
  only if the edit changes text emitted for another mode, for example by
  putting the new `get_sampler_type` case where another case falls into it,
  or if a stale shader-key cache serves a program from the other build.

## 6. Discriminating read at fab230935e

Pending: `1790373098-brdf315-964945`.

## What the next lane should not repeat

- Do not judge "rasterised or not" from a blended pixel. This suite blends
  SRC_ALPHA over the clear colour, so t2 = 0 is invisible whether or not the
  triangle was drawn.
- Do not model this test with the programmable `PerspectiveVertexShader`. It
  carries no code. The draw is fixed-function with `view * model`, which is
  why both cubes land off screen.
- Do not read "the three goldens are identical" as "the lookup ignores
  stages 0/1". The blanking memset covers one cube face.
- Do not price the rule with filtered (continuous) theta/phi: 187 vs 605.
