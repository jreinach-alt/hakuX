# lane.wparamclip223 -- #223: emit silicon's external wedge from the geometry shader

Brief: for a filled triangle with exactly one negative-w vertex, build the
external wedge in `glsl/geom.c` and emit it as positive-w geometry, so the host
clipper never cuts at w = 0. Price it offline first, then prove it on a Thor
W_param arm.

**Status: implemented, priced, prediction registered
(`docs/testing/predictions/wparamclip223-wedge.json`, a_ref 0a4e284536 = master,
b_ref 77bc07d5e2). Waiting on the arm.** Section 5 is filled in when the verdict
lands.

## 1. The wedge, and a correction to the brief's wording

A point of the homogeneous triangle with weights a, b, c >= 0 on (N, P1, P2)
and w > 0 projects to `Q + t (Q - N)`, where Q is on the edge P1-P2 and t >= 0.
So the region is across P1-P2 from N, between the rays N->P1 and N->P2
**continued past P1 and P2**. The brief says "extensions ... beyond N", but that
would be the opposite cone. The goldens settle it: in `prog_..._bitri_w-1.00`,
tri1 has N = (480,390), P1 = (480,70) and P2 = (160,390), and it fills
x < 480, y < 390, above the diagonal. That is the continuation past P1 and P2.

The region depends on the screen positions alone. The w magnitudes only change
the varyings. That is why every negative-w bitri golden has the same two
wedges, whatever its ratio.

## 2. Offline pricing (before any C)

`wedge_price.py` regenerates each capture's vertices from
`w_param_tests.cpp:485-740`. It applies the float32 arithmetic of vsh-prog.c
and vsh-ff.c (clampAwayZeroInf, the ff divide and viewport offset,
roundScreenCoords). It then decides per triangle between WEDGE (exactly one
negative w, finite, non-zero screen area) and today's path. Finally it scores
coverage against the golden. The label pixels are excluded, and the clear
colour is 0x251135. `C` is the #235 fix arm
`1790332452-arms-shadeflat224-fix-1762588` (Thor, apk 8e4014f440ba, every
W_param row `ok`).

| capture (prog bitri) | paths | golden ink | C xor G today | model xor G |
|---|---|---:|---:|---:|
| w-0.00 | W,W | 271,518 | 271,518 | **0** |
| w-1.88e-37 | W,W | 271,496 | 143,122 | **0** |
| w-3.76e-37 | W,W | 271,512 | 143,072 | **0** |
| w-7.52e-37 | W,W | 271,634 | 4,025 | **0** |
| w-0.25 / -0.50 / -1.00 / -2.00 / -4.00 / -inf | W,W | ~271-273k | 0 | 0 |
| w-0.96e-34 / -1.50e-36 / -3.08e-33 | W,W | ~271.4k | 0 | 0 |

**The model covers all 13 negative-w prog bitri goldens with 0 coverage
mismatch**, the four must-move rows included. The brief's stop condition does
not fire.

The quads keep today's path. prog and ff quads are split v0-v2 by
`rewrite_quads()`, and v0 and v2 are the two negative vertices, so each half
has two negative w and the new path is never taken. The 20
`prog_..._quad` rows at 0 are therefore a clean control.

For ff bitri, the negative rows with a non-degenerate screen triangle take the
path: w-0.25, -0.50, -1.00, -2.00, -4.00 and -inf. The others keep today's path:

- w-0.00, -1.50e-36, -1.88e-37, -3.76e-37 and -7.52e-37: N lands exactly on
  P1-P2 at (320,240) after the divide and truncation, so the area is 0.
- w-0.96e-34 and -3.08e-33: tri1 is also degenerate. tri2 has a vertex at
  ~8e35 px whose cross product overflows float32.

| ff bitri | C xor G today | model xor G |
|---|---:|---:|
| w-0.25 | 128 | 128 |
| w-0.50 | 262 | 209 |
| w-1.00 / -2.00 / -4.00 | 0 | 0 |
| w-inf | 114,508 | 95,270 |

ff w-inf over-draws in the model too. ff's vertex positions come from
vsh-ff.c's divide, which this lane does not touch, so that residual says
nothing about the wedge. It is recorded, not modelled.

**Colour, and why the must-move rows land near 742 rather than 0.** Counting
off-colour pixels inside each wedge on the extreme-ratio rows:

- The golden's red wedge is solid apart from the 320-px shared diagonal. Silicon
  paints that diagonal in both wedges, additively. The host's tie rule gives it
  to one.
- Our current capture (host path) has about 422 more off-colour px inside tri1,
  which are texel-rounding specks on u + v = 256.
- So the rows that draw today with the same geometry sit at 742-743
  (w-1.50e-36, w-3.08e-33, w-0.96e-34).

The specks depend on how this build rounds that texcoord, so they may move
either way. The registered bound is <= 2,500 for each of the four.

## 3. The change (`glsl/geom.c`, `append_wedge()`)

- **Gate:** exactly one w < 0, and every q_i = xy/w, z/w and the screen area
  finite and non-zero. Anything else returns false **before emitting a
  vertex**, and the triangle is emitted as before.
- **Polygon:** the quadrilateral P1, N + K(P1 - N), N + K(P2 - N), P2. K is
  twice the largest mu = 1 - lambda_N over the surface corners. It is
  Sutherland-Hodgman clipped to NDC +/-1, so it has at most 8 vertices.
  `max_vertices` goes from 3 to 8, against the 18 that `vk/instance.c` already
  checks, so instance.c needs no change. P1 and P2 are copied, never
  recomputed, so the diagonal the two W_param wedges share is one exact edge.
- **Varyings:** weights alpha_i = lambda_i / w_i (all >= 0 in the wedge),
  normalised, with w' = smin / s. A/w' and 1/w' interpolate linearly across
  screen to the triangle's own perspective field. NOPERSPECTIVE takes lambda.
  Flat colours and vtxFogSpecial come from gl_in[0], as emit_vertex() does;
  cylinder wrap is applied per vertex before weighting. w' is held at
  >= 2^-64 of its maximum, because the weights span up to 2^128 here and A/w'
  would overflow.
- **Winding:** the strip winds as the host clipper's polygon does, opposite to
  the screen triangle (the sign of the homogeneous determinant). So a culled
  draw culls what it culled before.
- **Two negative w:** unchanged. The host clipper keeps the w > 0 part, the
  region around the positive vertex. **Three negative w:** unchanged, and
  nothing is drawn. The adjacency path (#235's flat quads) is unchanged.

Checked offline:

- `wedge_port.py` is a float32 port of `emit_wedge()`. On every triangle that
  takes the path it reproduces the analytic wedge exactly (0 px). Every strip
  triangle winds as the host clipper's polygon does. The w' clamp bites only on
  the extreme tri2 rows and ff tri1 (3 and 1-2 vertices).
- `geom_dump` gains four filled-triangle cases (flat; noperspective with
  cylinder wrap; GL; GLES 3.20).
  - All 15 cases compile under the NDK's glslc (29.0.14206865): the Vulkan
    cases for vulkan1.0, and the GL and GLES cases for opengl with
    `-fauto-map-locations`, as #235 did.
  - A mutant (`al / S` for `al / S[k]`) is rejected.
- `nv2a_index.json` was regenerated over the tests tree at 6743b6a and
  pbkitplusplus e91d509. Only line numbers and provenance changed, and `check`
  passes.
- `check_legs.py` checks the prediction against the 451-capture disc. It
  guards 432 captures bit-identical and leaves 19 new-path captures to be
  judged by hand. No new-path row sits inside a `must_not_move` glob, and no
  other row is unguarded.

## 4. The arm (registered before any build)

`docs/testing/predictions/wparamclip223-wedge.json`. #235's 13-suite disc is
used, because its replicate pair moved 0 of 451 captures outside Shade_model.

- **Must move, judged by hand:** prog bitri w-0.00 (271,518), w-1.88e-37
  (143,546), w-3.76e-37 (143,494) and w-7.52e-37 (4,768), each to <= 2,500
  (expected ~742), with coverage mismatch 0 (`wedge_price.py` on the B
  capture).
- **New path, judged by hand:**
  - the other nine negative prog bitri rows, and ff bitri w-0.25, -1.00,
    -2.00 and -4.00: |B - A| <= 1,000 each;
  - ff w-0.50: coverage 262 -> 209;
  - ff w-inf: coverage 114,508 -> 95,270.
- **Must not move, bit-identical:** everything else, 432 captures. The patch
  change that would move them is a geometry shader that fails to compile,
  which draws nothing on Vulkan, or the gate leaking.
- **World in which must-move fails:** silicon's wedge is not this region, for
  example because of a guard band or a coarse raster rule. The captures then
  move but not onto the golden. Report the residual; do not refit.

## 5. Result

Pending. **Waiting (2026-09-25)** on the arms job's `[job.arms]` verdict for
`wparamclip223-wedge.json` (a 0a4e284536, b 77bc07d5e2) on PR #250. When it
lands:

1. Check both arms' `scores1.tsv` status column for `unreadable`, and
   `run1.log` for PARTIAL COVERAGE and UtilAcceptVsock.
2. Judge the 19 new-path rows by hand against section 4's ranges.
3. Run `wedge_price.py --capture-dir <B>/captures1` for coverage.
4. Mark the PR ready.

## For the next lane

- Do not rebuild a uniform or per-triangle w scale (wparamgeom223).
- Do not score desktop captures against these goldens.
- ff w-inf's remaining over-draw is a vertex-position question (vsh-ff.c's
  divide at w = -0 / -inf), not a wedge question.
- `wedge_price.py` and `wedge_port.py` rerun in seconds. Point
  `--capture-dir` at an arm's `captures1` to score coverage on it.
