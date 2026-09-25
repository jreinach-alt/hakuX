# #224 family B: the 1-LSB fixed-function lighting tie (884,185 px)

Lane: shadetie224            Issue: #224 (Shade model)
Base: origin/master 0a4e284536
Files: hw/xbox/nv2a/pgraph/glsl/vsh-ff.c, docs/testing/predictions/shadetie224-*.json,
docs/lanes/shadetie224/**
Needs device: yes (Thor Shade model arm). Needs NDK: no.

## Read first: docs/lanes/shade224/NOTES.md section 1B (on master, PR #232)

Every differing pixel in the 24 Fixed/W_Fixed Flat captures is one colour pair:
ours (0,85,59) against silicon's (0,85,60) -- 884,185 of 884,185 px. The six
captures at 0 are Poly and Tri_Flat_Last, where vertex 3 does not provoke.
Lighting: infinite light dir (0,0,1), diffuse (0,1,0.7), material 1, so
B = 0.7f x 0.3333333f x 255 = 59.49999 for normal 3 (-0.66667, 0.66667,
0.3333333). A rounding tie; silicon writes 60. Normal 1's B = 178.49999 is the
OTHER tie and silicon rounds it up to 179 **as we do**. Normalisation is off
(`vsh-ff.c:474`), so the tie is set by float rounding through
`invModelViewMat0` and the light setup. Round-to-nearest reproduces all 8 other
flat colours (147/103, 208/146, 186/130, 119/84, 204/143, 74/52, 231/161,
255/179).

## The job

Find a float pipeline in vsh-ff.c's lighting path that lands on silicon's side
of BOTH ties, and derive it from something other than the two ties.

1. Enumerate the operations between the normal and oD0 (matrix product, dot,
   scale by diffuse, clamp, x255, round) and the ways silicon's fixed-function
   unit could differ: fused multiply-add vs separate, operand order, reciprocal
   instead of divide, a few ulp of headroom on the normalisation constants.
2. Price each candidate offline against every lit flat colour in the goldens
   (the 8 easy ones must stay put, normal 1 must stay 179, normal 3 must go to
   60). A candidate that fits only the two tie points is a curve fit: the
   previous lane declined for exactly that reason. Prefer a candidate with an
   independent argument (the nv2a's documented arithmetic, nxdk_vsh_tests
   silicon goldens on master under `docs/testing/`, #233/#242's evaluator).
3. If none has an independent argument, the finding is that family B needs a
   silicon capture with more tie normals -- write the nxdk_pgraph_tests case
   spec into NOTES and stop without a code change. That is a fine outcome.

## The arm (register BEFORE building, and after the last rebase)

- **must_move:** the 18 Fixed/W_Fixed x Flat captures that carry B, each to 0
  (or to the residual your pricing predicts, per capture).
- **must_not_move:** the six B-free captures at 0; every Smooth capture
  (family C, #38's) and all Prog_* captures unchanged; `nv2a_index.py blast
  hw/xbox/nv2a/pgraph/glsl/vsh-ff.c` for the other suites a lighting change
  reaches (Lighting, Fog, Texgen, Material) -- name each and bound it.
- **The world in which must_move fails:** the tie is not a float-order effect
  but a different light path (e.g. per-vertex lit value stored at reduced
  precision before interpolation). Then the pixel moves to 59 or 61, not 60.

**Before trusting the verdict:** check `scores1.tsv` status for `unreadable`
and `run1.log` for "PARTIAL COVERAGE"/UtilAcceptVsock; an unreadable capture
scores as 0.

## Do not

- Fit a rule to two ties and call it a mechanism.
- Chase family C (Smooth wash, #38) or family A (folded, #235).
- Touch glsl/geom.c, psh.c or pgraph.c (other lanes').
- Trigger CI as a self-check.

## Done when

- Either the arm verdict is on your PR with the status column checked, or NOTES
  record the offline pricing and a capture spec for the missing ties.
- `nv2a_index.json` regenerated over the pinned tests tree; preflight passes;
  PR marked ready with its `Files:` line.
