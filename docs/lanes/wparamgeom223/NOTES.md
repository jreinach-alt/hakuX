# lane.wparamgeom223 -- #223: a uniform w scale in the geometry shader (blocked)

Brief: scale each filled triangle's three clip-space vertices by one positive
factor so that sqrt(max|w| * min|w|) = 1 (`docs/lanes/wparam223/NOTES.md`
section 5), then prove it on a Thor W_param arm.

**Outcome: blocked, and no device arm was run.** The brief's premise is false,
and the test source and a capture on disk show it offline. The scale is written,
compiled and reverted on this branch (ad620e10f9, reverted by d5e72c865b), so
the net diff against master is NOTES only.

## 1. The premise, and what the test actually draws

The brief, and section 4 of the wparam223 NOTES it came from, gave tri2 in
`prog_w_zero_inf__bitri_w-1.88e-37` as {-2^-58, 2^-64}: small magnitude,
small ratio. On that reading the scale takes it to {-8, 1/8}.

The test (`nxdk_pgraph_tests/src/tests/w_param_tests.cpp:646-706`) draws

    tri1 = {kMinW / m, kMinW, kMinW}      kMinW = 2^-64
    tri2 = {kMaxW * m, kMaxW, kMaxW}      kMaxW = 2^64

So tri2's positive vertices are at **2^64**, not 2^-64. Clamped by
`clampAwayZeroInf()` the same way vsh.c clamps them, with the factor
`tri_w_scale()` would apply (k is the power of two; script in section 4):

| capture | tri1 {neg \| pos} | ratio | k | silicon vs us | tri2 {neg \| pos} | ratio | k | silicon vs us |
|---|---|---|---|---|---|---|---|---|
| w-1.00 | {-2^-64 \| 2^-64} | 1 | +64 | drawn | {-2^64 \| 2^64} | 1 | -64 | drawn |
| w-inf | {-2^-64 \| 2^-64} | 1 | +64 | drawn | {-2^64 \| 2^64} | 1 | -64 | drawn |
| w-0.00 | {-2^64 \| 2^-64} | 2^128 | 0 | **missing** | {-2^-64 \| 2^64} | 2^128 | 0 | **missing** |
| w-3.08e-33 | {-2^44 \| 2^-64} | 2^108 | +10 | drawn | {-2^-44 \| 2^64} | 2^108 | -10 | drawn |
| w-1.50e-36 | {-2^55 \| 2^-64} | 2^119 | +4 | drawn | {-2^-55 \| 2^64} | 2^119 | -4 | drawn |
| w-7.52e-37 | {-2^56 \| 2^-64} | 2^120 | +4 | drawn | {-2^-56 \| 2^64} | 2^120 | -4 | 4,025 px missing |
| w-3.76e-37 | {-2^57 \| 2^-64} | 2^121 | +3 | drawn | {-2^-57 \| 2^64} | 2^121 | -3 | **missing** |
| w-1.88e-37 | {-2^58 \| 2^-64} | 2^122 | +3 | drawn | {-2^-58 \| 2^64} | 2^122 | -3 | **missing** |

- **Every triangle we fail to draw has a |w| ratio of 2^120 or more.** Every
  ratio-1 triangle draws, whether its magnitude is 2^-64 or 2^64. The data
  gives no case of a failure driven by magnitude.
- **A uniform scale cannot change a ratio.** That is the whole point of it,
  because it is what keeps it rendering-invariant.
- On the three must-move rows the scale moves w by 2^-3, 2^-3 and 2^-4, not
  the 2^61 the brief modelled. The only way that could help is a failure
  within three binades of a float limit that the ratio-1 rows at 2^64 and
  2^-64 would also hit, and they draw.
- The rows the scale would move by 2^64 are the ratio-1 ones that already
  match silicon (666 and 670 px, wash). So the change touches every triangle
  in every game, adds risk where we are right, and does nothing where we are
  wrong.

So the brief's "world in which must_move fails" is true, but not for the
reason it guessed (a screen-extent effect). tri2's failure is ratio-driven, and
the section 4 table had hidden that by giving tri2 the wrong positive w.

## 2. Two more corrections to the brief

- **`w-0.00` was not a must-not-move for this model.** On the brief's own
  reading, `w-0.00` tri2 = {-2^-64, 2^-64} is ratio 1 and the scale would
  reach it. The pixel split below says half the capture is tri2. So even on
  the brief's own model that leg would have moved by ~142.7k. On the real w
  both triangles are ratio 2^128, k = 0, and the scale is exactly a no-op there.
  Split of the 271,518 px against PR #235's fix arm
  (`dispatch/results/1790332452-arms-shadeflat224-fix-1762588`, ok status):
  142,693 px in tri2's golden colour (37,209,245), 128,825 in tri1's
  (229,17,53), and 0 of the difference outside the two wedges.
- **Quads DO reach the geometry shader** on Vulkan and on desktop GL.
  `pgraph_prim_rewrite_get_output_mode()` maps QUADS / QUAD_STRIP / POLYGON
  to `PRIM_TYPE_TRIANGLES` under FILL, and `pgraph_glsl_need_geom()` returns
  true for that. So the `ff_..._quad` family is within reach of any
  geometry-shader fix, and the 20 `prog_w_zero_inf__quad` captures at 0 are a
  real invariance check on one.

## 3. What was built, and checked offline

`tri_w_scale()` in `glsl/geom.c` (ad620e10f9) chooses a power of two from the
float exponent bits, not from log2(), so the scale is exact in float32. It
applies to the TRIANGLES fill path and to #235's adjacency path, and it falls
back to 1.0 on zero/subnormal/inf/NaN w or on a component that would leave the
normal range. All 11 `docs/testing/geom_dump` cases compile under the NDK's
`glslc` (vulkan1.0, and opengl for the GL/GLES cases), and the check rejects
a mutant (`intBitsToFloat(127.0 + k)`: "no matching overloaded function").
It is correct as a no-op, and useless as a fix.

The SPIR-V cache (`vk/glsl.c`) is keyed on a hash of the GLSL source, so a
generator change like this one needs no `SHADER_STATE_LAYOUT_VERSION` bump.
That is worth knowing for the next geom.c lane.

## 4. What the next lane should do, and not repeat

- **Do not repeat** the uniform scale, or any per-triangle scale. Every such
  scale is ratio-invariant, and a per-vertex scale is not rendering-invariant.
- **The remaining lever is the one both NOTES named as the second step:**
  clip the triangle in the geometry shader and emit silicon's external wedge
  as ordinary positive-w geometry. For one negative vertex N and positives
  P1, P2, the wedge is bounded by the edge P1-P2 and the two edges' extensions
  through N. Clip it to the guard band in screen space and emit it with w > 0,
  so the host clipper never sees a negative w. That removes the host from the
  decision, which section 4 says is where llvmpipe, Adreno and silicon
  disagree. It needs varyings extrapolated projectively across the wedge, and
  it needs a max_vertices raise checked against vk/instance.c's
  PGRAPH_GEOM_MAX_OUTPUT_VERTICES. Scope is `prog_*bitri` and, through the
  quad rewrite, `ff_*quad` and `prog_*quad` (the latter must stay at 0).
- Arm for that change, from this table: must_move `prog_..._bitri_w-0.00`
  (271,518, both wedges), `_w-1.88e-37` / `_w-3.76e-37` (143.5k, tri2),
  `_w-7.52e-37` (4,768). must_not_move: the 20 `prog_..._quad` at 0 and the
  positive-w `prog_..._bitri_w*` rows at 0. Beware the ratio-1 rows that pass
  today: the new path takes them too, so they are part of the test.
- Script to regenerate the table: section 1's arithmetic is short enough to
  redo from the test source. Clamp to [2^-64, 2^64] by sign, then
  `k = -trunc((emax + emin) / 2)` over the float exponents.

## Files

- `docs/lanes/wparam223/NOTES.md`: section 4's table corrected in place (tri2's
  positive w, ratio column, pixel split). Section 5 carries a withdrawal at
  its top, with the original text kept below it.
