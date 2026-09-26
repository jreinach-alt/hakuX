# Audit pass 1: PR #321, lane/wparamcode223 (#223)

Head audited: cdf844872e.  Diff read: `gh pr diff 321` (hw/xbox/nv2a/pgraph/glsl/vsh-ff.c,
hw/xbox/nv2a/pgraph/glsl/geom.c, nv2a_index.json line shifts, the prediction, lane tooling).

**Verdict: no HIGH, no MEDIUM.  Four LOWs.  -> needs-audit-2.**

## What was checked

### (A) vsh-ff.c position tail

- **0 * x = 0 branch.**  `oPos = tPosition * compositeMat` is row-vector times
  matrix, so `oPos[j] = dot(tPosition, cm[j])`.  The loop computes
  `p = tPosition * cm[j]` component-wise and zeroes `p[i]` where either factor
  is 0, which is `oPos[j]` with nv2a's multiply.  The indexing is right.  The
  branch is taken only for a non-finite `tPosition`, so finite inputs keep the
  old `vec * mat`.  If a driver folds `isinf`/`isnan` away, the result is today's
  behaviour, not a new failure.
- **Carry.**  `scrPos` is the old `oPos.xy / w + vpoff`, with the same operations
  in the same order, so `roundScreenCoords(scrPos)`, `vtxPos` and every
  non-carried component are unchanged.  The carried expression
  `2h/S + (2 vpoff/S - 1) w` is algebraically the old
  `((2 (h/w + vpoff) - S) / S) w`.  The select is per component, and both
  operands are clip space over the same (clamped) w.  `h` is the unclamped
  numerator, and w is clamped in both expressions, so they agree when
  `clampAwayZeroInf` moves w.  A NaN `scrPos` fails `lessThan` and is carried.
  It was NaN before and stays NaN or inf, so nothing that was finite regresses.
- `roundScreenCoords` is the identity for |pos| >= 2^19: pos*16 >= 2^23 is
  already an integer in float32.  So the carry threshold and (B)'s bound are
  the same boundary, as the comments say.
- After the tail, nothing reads the old in-place `oPos.xy`.  point_params
  reads `position`, not `oPos`.

### (B) geom.c zero-area rule

- The call site is `PRIM_TYPE_TRIANGLES` under `POLY_MODE_FILL` only
  (geom.c:424-430).  LINE-mode passes never reach `emit_wedge`, so w_gaps'
  golden lines cannot be dropped by this rule.  This confirms the lane's claim.
- The rule runs after the exactly-one-negative check and the finite-q check.
  `pz` is `v_vtxPos` from `calc_triz`, the snapped screen position.
- Exactness: below 2^19, each coordinate has at most 23 significant bits and
  each difference at most 24, so `g1`, `g2` are exact.  `kahan_det` is
  `precise` + `fma`.  When the real determinant is 0,
  `fma(a,b,-cd) = -(err)` exactly, so `garea == 0.0` is exact.  A non-zero grid
  determinant (>= 2^-8) cannot round to 0.  NaN/inf in pz makes `garea` NaN or
  `pmax` not < 2^19, and falls through to the old `return false`.
- Geometry: projected points collinear <=> det[X0 X1 X2] = 0.  So the whole
  triangle lies in a plane through the eye and projects to a line, whatever the
  signs of w.  Emitting nothing matches silicon under the lane's
  snapped-vertex model, and the goldens exercise it (tri1 at the extremes,
  w_gaps).
- The hunks are unchanged since the arm's b_ref: `git diff 8555c013c6 HEAD --
  hw/` touches neither geom.c nor vsh-ff.c, only master merged forward.  The
  arm's PASS (19 better / 0 worse / 568 same) was taken on this code.

## Findings

### L1 (LOW): "every finite carried vertex is bit-identical" is stated generally, measured on two rows
The PR body and prediction state it as a property of (A).  NOTES §3 measures it
with ff_port.py on ff quad and bitri w-0.96e-34 / w-3.08e-33 only.  The carried
expression rounds differently from the old one: a divide-add-subtract-divide-
multiply versus a divide-add-multiply-add.  So a finite game vertex with
|x/w + vpoff| >= 2^19 can get a gl_Position.xy an ulp or so away from today's.
Scenario: a ground plane with a vertex just in front of the eye plane (tiny
positive w, scr ~ 1e7 px).  The edge into the screen pivots by ~2^-23 rad,
which is a displacement far below 1/16 px on screen.  So the blast radius is a
possible single-pixel tie flip at worst, and the 568 unchanged captures
include such geometry in Viewport and Depth_Clamp.  Remedy: word the claim as
"on the W_param rows measured", or state the ulp bound.

### L2 (LOW): prose magnitudes missed on 10 rows, and `expect` is empty
The machine legs are `expect_counts` {better 19, worse 0} and the must-not-move
list, and they hold.  The per-row magnitudes are prose.  The 8 bitri rows
landed at ~3.2k against "under 2,000", and w_gaps at 31.7k against "under
25,000".  The PR body reports this plainly and names the residual as needing a
different rule.  That is honest, but #223 is not finished by this PR.  The
residuals want a follow-up, or #223 left open with them recorded.

### L3 (LOW): carry overflows for |hPos| > FLT_MAX/2
`2.0 * hPos` goes to inf when |hPos| > 1.7e38, and gl_Position.xy becomes inf.
The old path is inf there too: `trunc(scr * 16)` overflows past 2^124.  So this
is not a regression, only an unreached edge of the fix.  `hPos * (2.0 /
surfaceSize)` would move the edge by a factor of S.

### L4 (LOW): lane tooling hardcodes a host path
`docs/lanes/wparamcode223/vshemit/check.py` sets `GLSLC` to
`/home/justin/Android/Sdk/ndk/29.0.14206865/...`, so the documented rerun
fails on any other machine.  This is lane tooling, not shipped code.

## For pass 2

Nothing is HIGH or MEDIUM.  Pass 2 checks whether L1's claim is reworded or
bounded, and whether L2's residuals are recorded on #223.  L3 and L4 may stand.
