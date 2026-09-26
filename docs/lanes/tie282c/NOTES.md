# lane.tie282c: does the #282 binade rule hold on a second geometry?

Follow-up to `docs/lanes/cloud-282b/`. Desktop only: no device, no build, no `hw/` edit.

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
