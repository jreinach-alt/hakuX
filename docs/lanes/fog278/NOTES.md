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

## Status

2026-09-26: the hunk and the prediction are pushed (57197f1290). Waiting on the
[job.arms] verdict and CI. Next: merge master, re-run the arm, mark ready.
