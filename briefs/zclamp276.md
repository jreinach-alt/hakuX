# #276: ZMinMaxControl -- we draw geometry silicon culls under NEARFAR ZCLAMP / ZCULL

Lane: zclamp276            Issue: #276 (ZMinMaxControl; 129,337 + 14,336 px, 0/12 exact)
Base: origin/master @ 8af1bbb18e (rebase to the tip before you register anything).
Files: docs/lanes/zclamp276/**, docs/testing/predictions/zclamp276-*.json
       (LOCATE-FIRST: the issue's guess is vk/draw.c:2294 depthClampEnable; vk/draw.c is lane.vtxarr262's,
       glsl/psh.c is lane.wbufdepth24's. Name the function, ask for the path by board-request.)
Needs device: yes for the arm; the analysis is desktop. Needs NDK: no.

## The defect
`*_NEARFAR_ZCLAMP*` (8 captures, 129,337 px) and `*_WBuf_NEARFAR_ZCULL*` (4, 14,336 px): 0/12 exact,
69,420 one-step, status ok. We draw geometry silicon culls. #19's run-alone check (09-12) classed them real
emulator defects ("missing-state"); nobody followed up. The 8 ZCLAMP captures share one wrong outcome.
Games: medium (depth-clamp state is common in shipped titles).

## Read first; the location is a claim
1. The issue's location is a GUESS. Derive from the nxdk_pgraph_tests source for ZMinMaxControl: which
   NV097_SET_ZMIN_MAX_CONTROL bits (CULL_NEAR_FAR_EN, ZCLAMP_EN, CULL_IGNORE_W) each test sets, and what is
   drawn at which depth. Then read how pgraph.c / vk/draw.c / glsl handle each bit.
2. Score the geometry silicon culls vs keeps by REGION against the golden, per capture; say which of
   near-cull, far-cull and clamp each capture exercises. Name what the emulator ignores or inverts.
3. Price the candidate rule offline against all 12 captures; note which would still differ and why (the
   12 include the ZCULL/W-buffer four, which may be a different bit).

## The arm (register after the last rebase; bind it to the function you name)
must_move: the 8 ZCLAMP captures -> exact or a stated residual; the 4 ZCULL captures likewise or explained.
must_not_move: Depth buffer suites, W buffering, Clear, every capture whose ZMIN_MAX_CONTROL is default.
Name the change that would move each. Check scores1.tsv `status` for `unreadable` and PARTIAL COVERAGE.

## Done when
NOTES.md names the mechanism, the priced per-capture result and the exact hunk with its holder; the arm is
registered; the PR is ready. Analysis plus the hunk is a complete outcome; the board grants files as holders fold.
