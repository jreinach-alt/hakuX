# lane.tie282c: does the #282 binade rule hold on a second geometry?

Follow-up to `docs/lanes/cloud-282b/`. Desktop only: no device, no build, no `hw/` edit.

## Outcome

**Hit, by the criterion registered in `d0e6d4cd54` before the scorer ran.** On
`Texture_render_target` row 240, cloud-282b's rule predicts **6,108 of 6,108**
observable tie pixels over the 40 `TexFmt_*` goldens. In every capture that
observes it, silicon's up/down transition sits exactly where the rule puts it:
up through column 391, down from 392. The rule has no parameter to tune here.
The strongest rival, a threshold on the edge function's own binade, scores
95.35%, and "always up" (today) scores 75.88%. The direction is keyed on the
**barycentric weights** (l0 = 1/4), not on screen position, not on the edge
functions' magnitudes, and not on the triangle alone.

What this does and does not establish:

- **It holds out the rule's coordinates, not its whole table.** Row 240 has
  l2 = 1/2 exactly, so it exercises one condition only: in T1 at l2 = 1/2, down
  iff l0 <= 1/4. On the checkerboard that is also row 240, where the boundary
  falls at x = 480. The second quad maps pixels to weights differently
  (285.625 px wide, not dyadic, a different area). That is why the column is a
  real prediction, but no new binade cell is tested. The l2 conditions (the
  (1/4, 1/2] band in l2, and "up above 1/2") are still checked only on the
  checkerboard.
- **It is not blind in the strict sense.** `render-to-texture-residual.md`
  recorded that our captures differ from the golden on columns 392-462 before
  this lane derived anything. See the contamination note in the pre-registration
  below. The rule's constants come from the checkerboard, and the column follows
  from the quad's corners with nothing to choose.
- **It corrects `render-to-texture-residual.md`.** That page read the 214
  columns where gold[240] == gold[241] as "the shift is invisible there". They
  are not invisible. On the 15 captures with a v gradient in every column,
  gold[239] != gold[241] on all 285 columns. So those 214 columns are
  *observed going up*, and the row is split, not "wholly shifted". The page
  also calls row 240 "a precision floor, not a defect". It is a deterministic,
  weight-keyed rule that we do not implement.
- **The console run is again not a second sample.** All 40 console captures
  (`2026-09-25-full6743`) are byte-identical to the goldens (0 px differ), so
  silicon is deterministic here and the console adds no independent evidence.

**Recommendation: a code lane, scoped.** Details in "The hunk" below. The
recoverable pixels are synthetic: the checkerboard's 156,844 tie px and this
suite's 2,989 channels on 26 captures. The lane is worth running only after the
suites with game-visible residuals, and only in the scoped form.

## Row 240 by weight binade (`row240.py`, goldens)

l2 = 1/2 on the whole row. In T1, l1 = 1/2 - l0.

| tri | b(l0) | b(l1) | columns | golden down / observable |
|---|---:|---:|---|---:|
| T2 and the edge | - | - | 178-320 | 0 / 3,136 |
| T1 | -2 | -9 .. -3 | 321-391 | **0 / 1,499** (the band: up) |
| T1 | -3 | -2 | 392-427 | **748 / 748** |
| T1 | -4 .. -9 | -2 | 428-462 | **725 / 725** |

On this row the l0 condition and "l1 in [1/4, 1/2)" pick out the same columns,
so the row cannot say which of the two weights the rule is keyed on. The
checkerboard can: there, l1's binade separates nothing.

| rule | agrees / observable |
|---|---:|
| **binade rule (cloud-282b)** | **6,108 / 6,108, 100.00%** |
| edge-function binade (l0 <= 2^14 / 2A = 0.2008, down from 406) | 5,824, 95.35% |
| always up (today's `texelTieBias`) | 4,635, 75.88% |
| screen x >= 481 (the checkerboard's row-240 split, carried over in screen space) | 4,635, 75.88% |
| #314 diag (every T1 v tie down) | 4,609, 75.46% |

Per capture: the 15 full-gradient formats observe all 285 columns, with down
exactly at 392-462. The AY8/Y8/Y16/A8Y8 family observes 58 columns, down at
396-461 and up through 391. Index8 observes 212, down at 393-462. UYVY/YUY2
observe 214, down at 392-462 and up through 389. DXT1 observes 151, all up and
all at or left of 328. The 5- and 6-bit formats observe none, because a 256-level
gradient quantised to 32 levels is flat across one texel. No capture puts a
down column left of 392 or an up column right of 391.

## The hunk, and who holds it

cloud-282b said the rule was "not implementable without the triangle's
barycentrics in the fragment shader". **That premise is half wrong on today's
tree.** `pgraph_glsl_need_geom` (`glsl/geom.c:67`) is true for every
`PRIM_TYPE_TRIANGLES` draw, and geom.c already hands psh.c the three snapped
vertex positions flat (`vtxPos0..2`, `geom.c:236-238`). psh.c already builds
per-fragment barycentrics from them (`psh.c:2604-2615`, the depth path). So the
weights are available without `VK_KHR_fragment_shader_barycentric`.

What is missing is the per-vertex texcoords. The rule needs to know which vertex
the tied coordinate follows.

- `hw/xbox/nv2a/pgraph/glsl/geom.c`: pass texcoord *t* of each vertex flat, next
  to `vtxPos`. Holder: **lane.vkpointsize34** (#34), `origin/board:territory.toml`
  wave 237.
- `hw/xbox/nv2a/pgraph/glsl/psh.c:2019` `texelTieBias` and its three use sites
  (`1103-1107`, `1454`, `3000`): make the v half's sign per fragment. Holder:
  **lane.fog278** (#278), wave 237. (cloud-282b named lane.wbufdepth24. psh.c has
  moved twice since.)

**Scope, which is what makes it a lane and not a fit.** Implement only the
configuration measured. The tied coordinate must equal one vertex's weight times
the span: two vertices share the low value and the odd vertex is the triangle's
third, as in T1's v. Only then is the direction down iff
`l_odd <= 1/2 and not (l0 in (1/4,1/2] and l_odd in (1/4,1/2])`. Every other
configuration keeps today's up. The arm needs a must-not-move control on the
u-tie and VS-draw captures (#314's census says we match those today), plus
`Point_params` and `Bump_env_lum`, which the v bias already moved
(`edge-defect.md`).

## Do not repeat

- **Do not generalise by "the odd vertex's weight is computed a hair low when
  <= 1/2".** It reads well on T1 v, T1 u and T2 v. It predicts **down** for T2's
  u ties (u = l1 there, rising in the odd vertex), and silicon puts 99.80% of all
  u ties up (cloud-282b). The general form, for arbitrary per-vertex
  texcoords, is not determined by any data on disk.
- Do not score row 240 on the 5/6-bit formats: they observe 0 columns.
- Do not re-read `render-to-texture-residual.md`'s "wholly shifted, a quarter
  observable". The row is split at l0 = 1/4 and every column is observable on
  the 15 full-gradient formats.
- Do not use the console run as a second sample for this suite either
  (byte-identical to the goldens).

## For #286 (lane.aasample)

Step 3 supports the rule, so the half-column answer job.cloud gave on #286
stands: texel 2x+1, the odd half-column, which is what we already select.
lane.aasample's PR #332 merged on that basis. Row 240 is a v tie on an FF draw,
so it adds nothing specific about the resolve's u tie on a VS draw. That still
rests on the 92,506 of 92,506 VS u-tie pixels going up.

## Reproduce

```
python3 docs/lanes/tie282c/row240.py /home/justin/goldens/results/Texture_render_target
python3 docs/lanes/tie282c/row240.py /home/justin/hakux-work/hardware/runs/2026-09-25-full6743/console-run/console/Texture_render_target
```

## Pre-registered (committed before `row240.py` was run)

### Geometry, from source

`texture_render_target_tests.cpp:104` draws `DefineBiTri(0, -1.75, 1.75, 1.75, -1.75, 0.1f)`
under `SetXDKDefaultViewportAndFixedFunctionMatrices`. `DefineBiTri` (pbkitplusplus
`vertex_buffer.cpp:216-222`, then the 1<->2 and 4<->5 swaps at 253-260) gives
T1 = (UL, UR, LR) with uv (0,0) (1,0) (1,1) and T2 = (UL, LR, LL) with uv (0,0) (1,1) (0,1).
That is the checkerboard's vertex order, so the weights mean the same thing:
in T1, v = l2 and l0 = (R - x_c) / W_q; in T2, v = 1 - l0.

All four vertices have w = 7.1, so 1/w is constant and the interpolation is affine.
The half-extent is 240 * 1.75 * cot(pi/8) / 7.1 = 142.81 px on both axes. With the
0.53125 offset and a 1/16 snap (truncating or round-to-nearest), the corners are
x 177.6875 .. 463.3125 and y 97.6875 .. 383.3125. That gives W_q = 285.625, and the
centre is at 320.5 / 240.5 whatever the snap does, because the snap stays symmetric
about the centre. Pixel centres are at x + 0.5, so the quad covers columns
178..462 and rows 98..382. Row 240's centre is 240.5, so v = 256 * 1/2 = 128: an
exact tie on the whole row, with **l2 = 1/2 exactly**.

On row 240 the diagonal UL-LR crosses x_c = 320.5. So columns 321..462 are in T1
and 178..319 are in T2. Column 320 sits on the edge.

### What the rule predicts (no free parameter)

cloud-282b's rule: a T1 v tie goes down iff `l2 <= 1/2 and not (l0 in (1/4,1/2] and
l2 in (1/4,1/2])`; T2 goes up. With l2 = 1/2 in T1, that reduces to **down iff
l0 <= 1/4**, i.e. x_c >= R - W_q/4 = 391.906. So:

| columns | triangle | l0 | rule |
|---|---|---|---|
| 178..320 | T2 (and the edge) | - | **up** |
| 321..391 | T1 | (1/4, 1/2) | **up** (the band) |
| 392..462 | T1 | < 1/4 | **down** (71 px) |

The boundary does not depend on the snap. Unsnapped it is 391.94, and snapped either
way it is 391.906 or 391.9375. No pixel centre is within 0.4 px of it.

**Contamination, stated up front.** `docs/investigations/render-to-texture-residual.md`
already records that *our* captures differ from the golden on row 240 at columns
392-462, and I read it before deriving the table above. The derivation uses only
the rule's constants (1/4, 1/2, fitted on the checkerboard) and this quad's
corners. It has nothing to tune. The number 392 is still not a blind prediction,
and the score below has to be read that way. What that page does *not* establish
is the golden's direction on columns 178..391. It read those columns as
"unobservable", which this lane tests.

### Rivals scored on the same pixels

| rival | predicts on row 240 |
|---|---|
| always up (today's `texelTieBias`) | up everywhere |
| #314 diag: every T1 v tie at v <= 128 goes down | down 321..462 |
| screen-space: the checkerboard's row-240 split (down iff x >= 481) | up everywhere (the quad ends at 462) |
| edge-function binade: threshold at the first power of two of E0 = l0 * 2A below 1/4, l0 = 2^14 / 81,581.6 = 0.2008 | down iff x_c >= 406.0, i.e. 406..462 |

The last rival is the discriminating one. On the checkerboard the edge-function
binades (0.213, 0.427) could be ruled out only because they missed 1/4 and 1/2.
Here the quad area is not a power of two times the checkerboard's, so the two
weightings put the boundary 14 columns apart.

### Hit criterion

Score per pixel on row 240, columns 178..462: 285 tie pixels per capture. Columns
0..177 and 463..639 are background, not ties. For each capture, a column is
*down* if gold[240] == gold[239] != gold[241] (all channels), *up* if
gold[240] == gold[241] != gold[239], and *unobservable* otherwise. Pool the
observable columns over the 40 `TexFmt_*` goldens.

- **Hit**: the rule agrees on >= 99% of observable pixels, the golden's up/down
  transition in T1 lies at 392 +/- 1 in every capture that observes it, and the rule
  scores strictly better than every rival above.
- **Falsified**: the rule does no better than "always up" (the majority-class
  baseline), or the transition sits outside 391..393, or it moves between
  captures.
- Anything in between is recorded as partial, with the columns that disagree.

Data: goldens `/home/justin/goldens/results` at `6e159f1` (2026-08-11). Console
(V1.1): `hardware/runs/2026-09-25-full6743/console-run/console` (2026-09-25).
