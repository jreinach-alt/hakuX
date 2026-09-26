# lane.tiecode282 -- implement the weight-binade texel-tie rule (#282, #283)

Issues: #282 (tie shift, 334,945 px ceiling), #283 (Volume texture residual). Base: master 7a2036020d.
Files: hw/xbox/nv2a/pgraph/glsl/psh.c, hw/xbox/nv2a/pgraph/glsl/geom.c, docs/testing/predictions/tiecode282-*.json, docs/lanes/tiecode282/**.

## Why now
Silicon has no sampler tie rule; nearest-sample ties break by interpolator arithmetic, keyed on the
barycentric weights (l0, l1, l2) binades. The rule (docs/lanes/cloud-282/tie_rule.py, `binades.py` in
docs/lanes/cloud-282b/) now predicts silicon on THREE geometries: the checkerboard (PR #314), Texture_render_target
row 240 (PR #376, 6,108/6,108 vs always-up 4,635) and Volume texture (PR #378, 6,496/6,496 vs 4,426). Nobody has
implemented it. Today's `texelTieBias` (psh.c ~2021, constant 1/262144 = always up) is the "always up" rival.

## Read first
docs/lanes/tie282c/NOTES.md ("The hunk" section), docs/lanes/vol283r/NOTES.md, docs/lanes/cloud-282/NOTES.md.
The weights reach the fragment shader via `vtxPos0..2`; per-vertex texcoords must reach it flat (geom.c).
Row 240 exercises only l2 = 1/2; the checkerboard exercises the l2 band conditions; the vertex-role
generalisation (other than T1 = UL,UR,LR) is OPEN -- implement what the three geometries support, say what they do not.

## Goal
Replace the always-up bias with the rule, scoped to the cases the evidence covers. Recoverable: checkerboard
156,844 tie px, Texture_render_target 2,989 channels/26 captures, Volume texture 22,072 px (the "down" class).

## Falsifier (register the prediction BEFORE building, after your last rebase)
Legs, each with its own golden: Texture_render_target TexFmt_* row 240 moves toward the golden; checkerboard suites
(Lighting/Bump/Combiner list in #282) improve; Volume texture Y16/R16B16 residual (4,243 px) does not worsen.
must_not_move: every Texture/Pixel shader/Combiner/Volume texture capture the rule does not name, and Texture_BRDF.
A leg that moves the wrong way refutes the scoping, not the rule -- report it and narrow the hunk.

## Coordination
psh.c was released at ready by lane.fog278 (PR #373, needs-audit-1) and is touched by PR #367 (y16bump10, fold-ready).
Before marking your PR ready, merge master (or those branches if unfolded) and re-run your arm. Do NOT touch
`stage_consumed_raw()` or the BRDF stage: docs/lanes/brdf315b/brdf315b-psh.diff (#315) lands there next and takes psh.c after you release it.

## Done when
PR out of draft, CI green, arm verdict posted, files released at ready (say so in the PR body); NOTES section 4 holds
the legs. If the arm refutes, ship the analysis and the negative, no code.
