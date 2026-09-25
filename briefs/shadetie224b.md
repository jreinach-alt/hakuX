# #224 family B, take two: which stage of the light path rounds, priced against THREE ties

Lane: shadetie224b           Issue: #224 (Shade model)
Base: origin/master 2b04d4d422
Files: hw/xbox/nv2a/pgraph/glsl/vsh-ff.c, docs/testing/predictions/shadetie224b-*.json,
docs/lanes/shadetie224/**
Needs device: yes (Thor arm). Needs NDK: no.

## Read first: docs/lanes/shadetie224/NOTES.md sections 1, 6, 7 (on master, PR #259)

Family B is 884,185 px over 18 Fixed/W_Fixed Flat captures: ours (0,85,59) against
silicon (0,85,60) on normal 3; normal 1 must stay 179. Master rounds oD0 by
truncation (`colorPrecision`, vsh.c:476) after `lt()` on the light registers.
The previous lane's candidate, `lt()` on the whole eye-space normal, fixed all 18
captures exactly and was REFUTED by the arm: Lighting_range/Directional went
792 -> 66,328 (one 256x256 block, blue 224 -> 225), 20 must_not_regress legs
worse. Its vsh-ff.c change is reverted; do not re-run it.

## The job

Price every still-unpriced candidate against all THREE tie points at once, in
`docs/lanes/shadetie224/price.py` (it models diffuse only today; extend it with
vsh-ff.c's specular-params evaluation -- NOTES section 6 lists the inputs):

- Shade_model normal 3 -> 60, normal 1 -> 179, Lighting_range/Directional
  specular blue -> 224 (the three ties);
- the Lighting_control NoSpec rows (a single block of 52 or 58 px each way);
- candidates: `lt()` on N.L only; `lt()` on the diffuse product only (specular
  inputs untouched); the LT's truncating multiply/add (`ltN+trunc`);
  round-to-nearest in place of truncation at one NAMED stage.

A candidate that fits the ties only by construction is a curve fit and is not a
finding. It needs an argument from something other than the three points
(envytools' Celsius model, the silicon goldens under `docs/testing/`).

If none fits all three with an independent argument, STOP without a code change:
write NOTES section 7's nxdk_pgraph_tests capture spec (one flat quad per normal,
z stepped across the 0.3333 tie at 1-ulp spacing +/-8 ulp; a second row for the
Directional specular setup) as the deliverable. That is a fine outcome.

## The arm, if a candidate survives (register BEFORE building, after the last rebase)

- must_move: the 18 Flat captures carrying B, each to 0.
- must_not_move / must_not_regress: Lighting_range/*, Lighting_control/*,
  Specular/*, Specular_back/* -- name them individually, the last verdict has
  the 20 that broke -- plus the six B-free Flat captures at 0, every Smooth
  capture, all Prog_*. `nv2a_index.py blast hw/xbox/nv2a/pgraph/glsl/vsh-ff.c`
  for the rest.
- The world in which it fails: a candidate that moves Directional's blue off 224.

Check `scores1.tsv` status for `unreadable` and `run1.log` for PARTIAL COVERAGE /
UtilAcceptVsock before believing a verdict; an unreadable capture scores as 0.

## Do not

Refit lt(N); chase family C (#38's) or A (folded); touch glsl/geom.c, psh.c,
pgraph.c (other lanes'); trigger CI as a self-check; edit board files.

## Done when

The arm verdict is on your PR with the status column checked, or NOTES hold the
pricing table and the capture spec with no code change. Index regenerated over the
pinned tests tree, preflight passes, PR marked ready with its `Files:` line.
