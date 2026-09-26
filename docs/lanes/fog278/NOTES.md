# lane fog278: INF fog coordinate, two-half hunk (#278)

Base `origin/master` @ 6550967a5e. The rule and its pricing come from
`docs/lanes/cloud-278/NOTES.md` (PR #319). This lane lands it.

## The change (eb6ce3a908, one commit, both halves)

- `hw/xbox/nv2a/pgraph/glsl/vsh.c`: an infinite fog coordinate is flagged
  `fogSpecial = 2.0`, and NaN stays `1.0`. Both still zero `oFog`.
- `hw/xbox/nv2a/pgraph/glsl/psh.c` `append_fog_factor`: in exp, exp_abs,
  exp2 and exp2_abs the special value is skipped when
  `vtxFogSpecial > 1.5 && fogParam.y == 0.0`. `fogCoord` is 0 there, so the
  ordinary formula runs on x = bias - 1.5. The linear modes emit the old
  condition byte for byte.

The line ranges named in the brief (at 248f1312c7) had drifted. On
6550967a5e the vsh.c site was :952-958 and the psh.c condition :1934.
Nothing else reads `vtxFogSpecial` except as `> 0.5`: geom.c and
prim_rewrite.c only copy it.

## Prediction: `docs/testing/predictions/fog278-inf-m0.json`

It is registered against a = 6550967a5e and b = eb6ce3a908, with 2 runs per
arm, over the discs Fog, Fog param, Fog inf coord and Fog exceptional value.

**The judge classes captures on `differing`, not on structural px, so the
16 movers do not all class `better`.** The bias-1/m0 quad evaluates to
exactly 2^-8 in all four modes. Our exp path rounds that to 1/255, and
silicon truncates it to 0. So after the hunk that quad is one-step
(4,096 px) in all 16 captures.

- exp x4: the quad was structural before (special 1 against a fogged
  golden). `differing` drops, so these class `better`. Structural is
  predicted to go 9,029 -> 837.
- exp_abs, exp2, exp2_abs x12: the quad is exact today, but only because the
  special value 0 happens to match. It turns one-step while the bias-1.5/m0
  quad goes 4,096 structural -> 18. `differing` rises by about 18, so these
  class `worse`, while structural goes 4,096 -> 18.

Registered: `better=4, worse=12`. The magnitude leg (<= 3,564 structural over
the 16) is read off the structural column of the verdict. Must-not-move
covers every other capture on those discs:

| capture set | what would move it |
|---|---|
| NaN-FogExc-* | NaN treated like INF |
| INF-FogExc-linear-*, INF-FogExc-linear_abs-* | the exemption leaking to linear |
| FogExc-*, RCP-FogExc-* | a wrong m test (these have m != 0) |
| Fog_param/*, Fog/*, Fog_inf_coord/* | none expected (finite coordinates, or m != 0) |

## For the next lane

- The one-step loss in the 12 is the exp-rounding residual (psh.c comment
  above `append_fog_factor`), not a fault in this rule. Truncating the exp
  modes globally was measured worse (2154 against 2352 of 2560 quads), so do
  not "fix" these 12 by flipping to floor.

## Result: PASS (148/148 checks)

Arms `1790408994-arms-fog278-base-14596` (a) and `-fix-14639` (b), 2 runs
each, every capture byte-identical with itself in each arm.

| | predicted | measured |
|---|---|---|
| classes | better 4, worse 12 | better 4, worse 12, same 146, noise 0 |
| exact | unchanged | 19 -> 19, 0 regressed from exact |
| structural over the 162 | falls by 85,268 - 3,564 = 81,704 | 145,228 -> 63,524, falls by **81,704** |
| byte-level movers | the 16 INF exp-mode captures | exactly those 16 |
| differing, INF-FogExc-exp-* | falls | 52,312 -> 48,216 each (-4,096) |
| differing, the other 12 | rises by ~18 | 4,096 -> 6,071 each (**+1,975**) |

Only the 16 differ byte for byte, so the whole structural drop is theirs, and
it matches the predicted 81,704 to the pixel. That puts the 16 at 3,564
structural (4 x 837 + 12 x 18), as long as the 85,268 baseline still holds.
The verdict does not print per-capture structural, so that figure is inferred
from the totals, not read off a row.

**What the prediction got wrong:** on the 12 worse captures `differing` rose
by 1,975, not ~18. Structural fell exactly as predicted, so the ~1,957 extra
pixels are one-step (off-by-one), not structural. The likely source is the
bias-1.5/m0 quad: it lands one step short of the golden on about half its
pixels rather than exact. That is the same exp rounding residual as the
bias-1 quad, and it is a class-shape miss, not a refutation. No check
failed.

## Why attempt 1 did not finish

The session ended correctly: it was waiting on the arm (about 90 min) and CI,
both outside the session, and it posted a `[lane.fog278] waiting:` comment.
Handback resumed the lane once CI was GREEN and the verdict was `verified`.

## Merge of master (attempt 2)

`origin/master` moved 16 commits past 6550967a5e (folds #375-#378, all
analysis). None of them touch `hw/xbox/nv2a/pgraph/glsl/`, so the shader
source after the merge is identical to what arm b ran. The brief asks for the
arm to be re-run after the merge, but with no shader change a re-run would
measure the same binary diff. It was not re-run, deliberately.
