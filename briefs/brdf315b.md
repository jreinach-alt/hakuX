# #315: why did the fitted BRDF rule (605/610 px exact offline) not survive rendering -- 614 -> 614 x3

Lane: brdf315b          Issue: #315 (Texture_BRDF, 3 captures x 614 px, the wedge at x 579..639, y 460..479)
Base: origin/master @ 6550967a5e (rebase to the tip before you register anything).
Files: docs/lanes/brdf315b/**, docs/testing/predictions/brdf315b-*.json
       glsl/psh.c is held by lane.fog278 (lent to lane.y16bump10): do NOT edit it. A hunk goes in a patch under
       docs/lanes/brdf315b/, and its file is `board-request`ed after those PRs fold.
Needs device: yes, one Texture BRDF capture per hypothesis (request.sh, Thor or Nova; date it). Needs NDK: no.

## What is known (read these first; re-derive, do not trust the summaries)
- lane.brdf315 (PR #326, docs/lanes/brdf315/): the wedge is ordinary geometry (both cubes off screen, only draw 0 clips into
  the corner; #223 is NOT the mechanism); BRDF rule fitted offline: get_sampler_type BRDF case, dots_needed 0,
  texture(texSamp2, vec3(t0.r, t1.r, fract(t1.g - t0.g))), 605/610 px exact.
- lane.pshqueue (PR #347, docs/lanes/pshqueue/NOTES.md): landing that hunk was arm-REFUTED: Texture_BRDF 614 -> 614 on all
  three captures, pixels moved but not toward the golden; hunk reverted. The arm's must_move legs and the measured
  figures are in NOTES and the [job.arms] verdict on PR #347 (pshqueue-315-brdf.json).
So the offline fit matched the golden's wedge colours but the rendered hunk did not. The gap is between the fit and the
shader: which input did the fit assume that the emitted shader does not deliver?

## The job, in order
1. From the arm's captures, diff our wedge against the golden per pixel (region, not point samples): which pixels moved,
   to what colours, and are they the fitted rule's colours at the WRONG pixels (a coverage/raster problem) or the wrong
   colours at the right pixels (a lookup/coordinate problem)? Read `status` for `unreadable` before trusting a count.
2. Test each assumption in the fit against what psh.c actually emits for this test: which stages feed t0/t1 (the
   dots_needed 0 and the r/g channel choice), the volume texture's wrap and filter state, and whether texSamp2 is
   bound as a 3D sampler at all under the BRDF mode. Name the one that breaks with a measured value.
3. Report on #315: the corrected rule (or "the fit is a coincidence") with the per-pixel evidence and, if a hunk is
   warranted, its patch and a registered prediction (a_ref = tip, b_ref = fix commit; must_not_move every other
   Texture and Pixel shader capture, naming the change that would move each). Do not tune a hunk to the number.

## Falsifier
Failing world: the wedge pixels change colour but land on the golden's colours only at the pixels the offline fit already
agreed on, while the other 9 stay wrong -- then the rule is right and coverage is the defect. The opposite world (the
same pixels, different colours) is the lookup. Say which one you measured.

## Done when
#315 carries the per-pixel diff of the arm's capture, the named broken assumption, and one next step (a patch with its
file, or "no mechanism, bound is X"). Analysis is a complete outcome. Do not edit the board files.
