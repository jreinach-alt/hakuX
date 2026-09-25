# #275: Color zeta overlap Swap: 165,447 px from one colour pair, and the console matches the golden

Lane: zetaswap275          Issue: #275 (component pgraph; Color zeta overlap)
Base: origin/master @ d709a8d1fa (rebase to the tip before you register anything).
Files: docs/lanes/zetaswap275/**, docs/testing/predictions/zetaswap275-*.json
       (LOCATE-FIRST lane: no hw/ file yet. Name the one function that has to change, then ask the
       board for that path with a board-request. vk/surface.c is lane.remote's, pgraph.c is
       lane.vshsubneg255's, glsl/psh.c is lane.wbufdepth24's, vk/draw.c is lane.vtxarr262's. If your
       fix lives in one of those, say which function and we sequence it.)
Needs device: yes for the arm (Nova or Thor); the analysis half is desktop. Needs NDK: no.

## The defect
Color_zeta_overlap Swap draws one colour pair across the whole region and is wrong by 165,447 px
(0 exact, status ok). The console (set K, hardware/runs/2026-09-19-calib) MATCHES the golden on
Swap, so this is the emulator. ZetaIntoColor (71,663; nondeterministic on silicon, at most 51,669
recoverable) and ColorIntoZeta_ZB (10,766; inside the console's own nondeterminism) are NOT the
target. #92 closed 2026-09-19 unmodellable offering "SurfaceShape has no address" as Swap's cause
and never measured it; #88 and #91 (colour-wins policy, PR #253, regression-accepted:91 for Swap)
closed 2026-09-25. Read #88, #91, #92 and PR #253's diff first: the trade #91 accepted concerns
this very capture, so what you fix must not undo the accepted policy silently.

## Read first; the location is a claim
Derive from the nxdk_pgraph_tests source for Color zeta overlap Swap: which surface is bound as
colour, which as zeta, at what address, what is drawn, in what order. Say which of the two colours
silicon shows and why, from the console capture (region, not point samples). Do not patch to make
the capture match. "SurfaceShape has no address" is a hypothesis: measure it (does the surface
cache key on address?) before building on it.

## The arm (register BEFORE building, after the last rebase)
- must_move: Color_zeta_overlap/Swap -> exact, or state the residual and why.
- must_not_move: the rest of Color zeta overlap that is exact today, Blend_surface/*,
  Surface_format/*, Depth buffer suites. Name the patch change that would move each leg.
- Failing world: a fix that resolves the overlapping pair as silicon does for Swap but reinstates
  the pre-#91 losses; register the #91 captures as legs.
- Check scores1.tsv `status` for `unreadable` and the run log for PARTIAL COVERAGE.

## Done when
Swap matches silicon (or the residual is measured and explained), every must-not-move leg holds,
docs/lanes/zetaswap275/NOTES.md names the mechanism and what you did not chase, and the PR is ready
with the arm verdict. If the fix cannot avoid a held file, report the function name and stop with
the analysis committed: that is a complete outcome.
