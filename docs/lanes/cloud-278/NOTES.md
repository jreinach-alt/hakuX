# lane cloud-278: INF fog coordinate, exp and exp2 (#278)

Analysis only, no device. Base `origin/master` @ 215ed58e95. Instrument:
`inf_fog_rule.py` in this directory; its full output is `inf_fog_rule.out`.

## Result

**Silicon's result is NOT a function of the coordinate alone: it depends on
the fog multiplier (`fogParam.y`).** The INF tests (`TestParams` in
`nxdk_pgraph_tests/src/tests/fog_exceptional_value_tests.cpp`) draw 24 quads
per capture: bias rows {-1, 1, 1.5, 1000} by multiplier columns {Lin, Exp,
Exp2, 1, **0**, -1000}. The coordinate is +INF on every vertex. In the four
exp modes silicon computes `0 * INF = 0` in the m=0 column, then runs the
ordinary formula on `x = bias - 1.5`. Every other cell takes the fixed
special value we already emit.

| mode | m != 0 (20 cells) | m = 0, bias -1 / 1 / 1.5 / 1000 | psh.c today | wrong cells |
|---|---|---|---|---|
| exp       | unfogged (1) | **F F** u u (= 2^(16x): 2^-40, 2^-8, 1, 1) | u everywhere | 2 |
| exp_abs   | fogged (0)   | F F **u** F (= 2^(-16\|x\|))               | F everywhere | 1 |
| exp2      | fogged (0)   | F F **u** F (= 2^(-32x^2))                 | F everywhere | 1 |
| exp2_abs  | fogged (0)   | F F **u** F                                | F everywhere | 1 |
| linear, linear_abs | unfogged | u u u u (**no** 0*INF rule: the formula would give F F ~0.5 u) | u | 0 |
| NaN, all six modes | special | special (0*NaN stays NaN) | special | 0 |

(u = unfogged, F = fogged; bold = the cells psh.c gets wrong.) Both the
issue's phrasing and the brief's guess ("exp(-INF) = 0 vs INF*INF") were
wrong about the mechanism. The special values for exp (1) and for exp_abs,
exp2 and exp2_abs (0) are right in 20 of 24 cells. The only defect is the
m=0 column, where silicon never sees an INF at all.

Linear does not follow the exp modes: at m=0 it still reads as special (1).
So the exceptional-value check on silicon sits in a different place per
path: on the product `m*d` for exp, and on the raw coordinate (or after a
NaN-producing multiply) for linear. I report that as observed and do not
claim a hardware reason for it.

### Scored against the goldens (regions, 24 quads per capture)

Each quad is classed by nine samples inside it: all `#FF0000` means fogged,
all showing diffuse means unfogged.

| set | captures | current model | rule278 |
|---|---|---|---|
| INF exp          | 4  | 22/24 each | **24/24** each |
| INF exp_abs, exp2, exp2_abs | 12 | 23/24 each | **24/24** each |
| INF linear, linear_abs (control) | 8 | 24/24 | 24/24 |
| NaN, all six modes (control) | 24 | 24/24 | 24/24 |

The goldens agree on all four gen modes (planar, abs_planar, fog_x,
spec_alpha), because the test uses a vertex program, which writes oFog
directly.

### Scored against our captures

Two runs, `z-c866527e03-029-Fog_exceptional_value` (09-13, thor) and
`1790359589-xbox-full6743-dry3` (09-25, thor, ref 84a67b9cf8), give identical
numbers. Our captures match the "current" model in 24/24 cells of every
capture, so what the device shows is what psh.c says.

| capture (x4 gen modes) | structural px now | inside rule278's flipped quads | predicted after hunk |
|---|---|---|---|
| INF-FogExc-exp-*      | 9,029 | 8,192 (b-1/m0, b1/m0) | **837**: the shared unfogged-diffuse residual (below) |
| INF-FogExc-exp_abs-*  | 4,096 | 4,096 (b1.5/m0) | **18**: the same residual inside the newly unfogged quad |
| INF-FogExc-exp2-*     | 4,096 | 4,096 | **18** |
| INF-FogExc-exp2_abs-* | 4,096 | 4,096 | **18** |
| **16 captures** | **85,268** (the issue's figure exactly) | **81,920** | **3,564** (81,704 recovered) |

**Why the rule does not reach "exact".** Two residuals remain, neither of
them from this rule:

1. **Unfogged-diffuse residual.** A fully unfogged quad here carries 9-80
   structural px against silicon. INF-linear and NaN-exp both show 860 px on
   every capture, with the per-quad pattern identical to INF-exp's unfogged
   cells. It sits in the diffuse gradient, not in the fog. So INF-exp keeps
   837 px, and the quad that becomes unfogged in exp_abs, exp2 and exp2_abs
   gains 18. This is a separate defect and is not #278's.
2. **The f = 2^-8 cell (bias 1, m 0).** All four modes give exactly 2^-8
   here. Silicon writes 0 (`#FF0000`), and our exp path rounds instead of
   truncating, so it gives 1/255. The Fog param suite shows the same thing
   today: `FogZeroBias-{exp,exp_abs,exp2,exp2_abs}` quad 0 (bias 1.0, m 0)
   is (255,0,0) in the golden and (254,1,1) in all three of our runs. This
   is the known exp-truncation residual described in the psh.c:1860 comment.
   After the hunk the cell is one-step (|d| <= 1): a structural gain for
   exp, but a **one-step loss for exp_abs, exp2 and exp2_abs**, whose cell is
   exact today only because the special value 0 happens to match. That is
   4096 px x 12 captures moving from exact to one-step. It shows in the
   one-step count, not in the structural count, and it is expected. Do not
   read it as a regression of the rule.

## The hunk to grant (not edited here: psh.c is held by other lanes)

Two sites. vsh.c must tell INF from NaN, because 0*NaN stays special.

`hw/xbox/nv2a/pgraph/glsl/vsh.c:944-949`, the fog-coordinate flag:

```c
"  if (isnan(fogDistance)) {\n"
"    fogSpecial = 1.0;\n"          /* NaN: special in every mode */
"    oFog = vec4(0.0);\n"
"  } else if (isinf(fogDistance)) {\n"
"    fogSpecial = 2.0;\n"          /* INF: special unless exp-family and m == 0 */
"    oFog = vec4(0.0);\n"
"  } else {\n"
```

`hw/xbox/nv2a/pgraph/glsl/psh.c:1905-1912` (`append_fog_factor`): for the
exp-family modes only, exempt the INF-with-zero-multiplier case from the
special value. `fogCoord` is already 0 there, because vsh zeroes oFog, so
the formula already evaluates `x = bias - 1.5`:

```c
/* exp, exp_abs, exp2, exp2_abs */
"if ((vtxFogSpecial > 0.5 && !(vtxFogSpecial > 1.5 && fogParam.y == 0.0))"
"    || isnan(fogFactor)) {\n"
"  fogFactor = %s;\n"
"}\n"
/* linear, linear_abs: unchanged, `vtxFogSpecial > 0.5 || isnan(fogFactor)` */
```

`vtxFogSpecial` is `flat` and is only ever compared `> 0.5`
(`geom.c` and `prim_rewrite.c` copy it, and nothing else reads it). So the
value 2.0 changes nothing on any other path. `fogParam.y == 0.0` is also
true for -0.0.

## Prediction legs for the lane that takes the grant

Suite `Fog_exceptional_value`, keys `Fog_exceptional_value/<test>`.

- **Movers (structural):** `INF-FogExc-exp-{planar,abs_planar,fog_x,spec_alpha}`
  9,029 -> 837 each. `INF-FogExc-{exp_abs,exp2,exp2_abs}-*` 4,096 -> 18 each.
  Total 85,268 -> 3,564.
- **Expected one-step rise:** the 12 exp_abs/exp2/exp2_abs INF captures, in
  the bias-1/m0 quad (reason 2 above).
- **Must not move, each with the patch mistake that would move it:**
  - `NaN-FogExc-exp-*`: moves if the hunk treats NaN like INF (0*NaN = 0):
    its m0 bias -1/1 cells would turn fogged.
  - `INF-FogExc-linear-*` and `INF-FogExc-linear_abs-*`: move if the
    exemption is applied to linear: its m0 bias -1/1 cells would turn fogged.
  - `NaN-FogExc-{exp_abs,exp2,exp2_abs}-*` (exact today): move under the
    same NaN mistake, with bias 1.5 turning unfogged.
  - `FogExc-*` and `RCP-FogExc-*`: every draw has m != 0 (the test's own
    D3D parameters), so they are inert unless the m test is wrong,
    e.g. `abs(fogParam.y) < eps`.
- The whole of `Fog_param` must be unchanged: its coordinates are finite.

No prediction is registered from here. This lane may not edit psh.c, so no
`b_ref` exists to name.

## What the next lane should not repeat

- Do not look for an exp(-INF) vs INF arithmetic difference. The 20 cells
  with m != 0 already match. The defect is only the m=0 column.
- `docs/investigations/fog-inf-coord-is-coverage.md` is about a different
  suite (`Fog_inf_coord`, the AFF-* captures) and does not bear on this.
- The 860/837 px unfogged residual is not fog. Do not attribute it to #278.
