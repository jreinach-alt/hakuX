# #281: NaN vertex attributes (NaNs/NaNq) differ from silicon by 14.6k px each

Lane: nanattr281           Issue: #281 (component pgraph; Attrib float)
Base: origin/master @ d709a8d1fa (rebase to the tip before you register anything).
Files: docs/lanes/nanattr281/**, docs/testing/predictions/nanattr281-*.json
       (LOCATE-FIRST lane: no hw/ file yet. pgraph.c is lane.vshsubneg255's (#255, a neighbour of
       this defect: read PR #288 first), vsh-prog.c is lane.vshr12280's, vsh-ff.c is
       lane.shadetie224b's. Name the function that must change and ask the board for the path.)
Needs device: yes for the arm (Nova or Thor); the analysis half is desktop. Needs NDK: no.

## The defect
Attrib_float `-NaNs_NaNs` (14,646 px) and `-NaNq_NaNq` (14,586 px), both white-content. Console set
K (hardware/runs/2026-09-19-calib): OURS differs from the console by 14,586 px per capture, and the
console differs from the golden by 60 and 0 px. So the console is the reference and the gap is a
real emulator difference. Expected 29,172-29,232 px; game-visible: low.

## Read first; the location is a claim
1. Read the test's source in nxdk_pgraph_tests (Attrib float): which attribute carries a signalling
   vs quiet NaN, in which vertex format, and what geometry is drawn. Say what silicon does with a
   NaN attribute (passes it through, flushes to 0, clamps, or culls the primitive), derived from the
   console capture region, not a point sample.
2. Find where our path first differs: host fetch of the attribute, the vsh input register load, or
   the rasteriser. PR #245 (folded d92ae5d7f3) and PR #288 (draft) changed nearby behaviour
   (a vertex outside Begin/End; subnormal inputs): read both diffs so you do not fight them.
3. NaNs vs NaNq: they share a mechanism or they do not. Say which, with evidence.

## The arm (register BEFORE building, after the last rebase)
- must_move: Attrib_float NaNs/NaNq captures -> exact against the golden, or state the residual.
- must_not_move: every other Attrib float capture exact today, and the Exceptional Float rows
  lane.vshsubneg255 works. Name the patch change that would move each.
- Failing world: a fix that treats all non-finite input alike and breaks the Inf captures that
  pass today; register one Inf leg.
- Check scores1.tsv `status` for `unreadable` and the run log for PARTIAL COVERAGE.

## Done when
The two captures match silicon (or the residual is measured and explained), every must-not-move leg
holds, docs/lanes/nanattr281/NOTES.md names the mechanism, and the PR is ready with the arm
verdict. If the fix lands in a held file, report the function name and stop with the analysis
committed: that is a complete outcome.
