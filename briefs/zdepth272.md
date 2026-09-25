# #272 (+#275): derive silicon's fixed-function depth arithmetic; ours reads 2-5 units off near maximum depth

Lane: zdepth272            Issue: #272 (Depth buffer fixed function, 323,036 px; #275's Swap folds into it)
Base: origin/master @ 8af1bbb18e (rebase to the tip before you register anything).
Files: docs/lanes/zdepth272/**, docs/testing/predictions/zdepth272-*.json
       (LOCATE-FIRST: the transform is vsh-ff.c:~884 z/w feeding psh.c zfloor. vsh-ff.c is
       lane.wparamcode223's (same position tail), psh.c is lane.wbufdepth24's. Name the hunk and the
       function, ask for the path by board-request, do not edit a held file.)
Needs device: yes for the arm (Nova or Thor); the derivation is desktop. Needs NDK: no.

## The defect
Depth buffer fixed function z24 full-range captures (two are 275,358 px; up to all 14 = 323,036) read 2-5
units HIGH across the receding quad near max depth, same signature as #266 (lane.wbufdepth24, PR #268 --
read its NOTES first: if its D24 saturate mechanism already covers these rows, say so and stop early).
lane.zetaswap275 (PR #301, folded) located #275's Swap as this defect: silicon sits ~4 units BELOW the exact
value, ours is exact. That is a rounding-model question, independent of #266's D24 saturate.

## The job
1. From the goldens, region-not-point, derive the depth arithmetic: what precision does silicon carry for
   z/w after the viewport transform, and where does it round (truncate? float32 z then *2^24-1? guard bits)?
   DBFF's grid is the training set; hold out Swap and ZetaIntoColor. Do not fit a two-point offset.
2. Price it offline against every depth capture on disk (scoreboard c866527e03 and the newest sweep).
   Report the per-capture residual and the rows a candidate would MOVE the wrong way.
3. Name the hunk (function, file, lines) and whether it needs vsh-ff.c, psh.c or both.

## The arm (register BEFORE building, after the last rebase)
must_move: the two z24 full-range captures and Color_zeta_overlap/Swap -> exact or a stated residual.
must_not_move: every depth capture exact today, Blend_surface/*, Surface_format/*, W buffering. Failing world:
a fix that lands Swap but shifts the exact 16-bit or W-buffer rows. Check scores1.tsv `status` for
`unreadable` and the run log for PARTIAL COVERAGE.

## Done when
NOTES.md holds the arithmetic, the priced per-capture result and the exact hunk per holder; the arm is
registered; the PR is ready. Analysis plus the hunk is a complete outcome; the board grants files as holders fold.
