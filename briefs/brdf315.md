# #315: Texture_BRDF -- PS_TEXTUREMODES_BRDF unimplemented, and silicon's only ink (a 614-px wedge) is not rasterised

Lane: brdf315              Issue: #315 (BRDF_e0_l0, e0_l1, e1_l0: 614 px each, 7/7 runs 09-13..09-25)
Base: origin/master @ fab230935e (rebase to the tip before you register anything).
Files: docs/lanes/brdf315/**, docs/testing/predictions/brdf315-*.json
       (glsl/psh.c:3123-3128 is held by other lanes; the BRDF case is a named hunk for a grant.)
Needs device: yes (the discriminating run); the model is desktop. Needs NDK: no.

## The defect, two stacked
1. PS_TEXTUREMODES_BRDF emits `vec4 t2 = vec4(0.0)` + NV2A_UNIMPLEMENTED; the final combiners read TEX2.
2. Silicon's only ink is a wedge (x 579..639, y 460..479, 1 px at row 460, 61 at row 479), colours
   (194,246,202..222) / (190,246,218..222) = a BRDF-volume lookup. We draw the clear colour (18,18,18,254) there.
   Neither cube of texture_brdf_tests.cpp:181-183 appears on silicon or on ours. Games: low.

## Do in this order
1. The discriminating run first (issue body): any Texture BRDF capture at a ref containing 8e683b3a26 (#223's
   fold). Read pixel (639,479): (18,18,18,254) = still unrasterised, #223 is not the mechanism; (0,0,0,0) =
   rasterised, only defect 1 remains. The 614 count is the same either way -- do not judge by the count. Use an
   on-disk capture at that ref if one exists (date it); queue one otherwise.
2. From the test source and the NV2A BRDF definition, derive what the wedge is: #223's one-negative-w external
   wedge, or a real BRDF-textured triangle? Decode the wedge colours against the BRDF volume the test uploads and
   fit the rule per pixel. Re-derive the issue's premises (wedge geometry, the t2 dependency) from source first.
3. Price the psh.c BRDF case offline against the 3 goldens; name the hunk and its holder.

## Done when
NOTES.md states which defect(s) remain at current master, the fitted BRDF rule with its per-capture priced
result, and the hunk; an arm is registered if code is named (must_not_move: every other Texture / Pixel shader
capture, naming the change that would move each); the PR is ready. Analysis plus a named hunk is a complete
outcome.
