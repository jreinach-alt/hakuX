# lane.ring53impl -- #53: implement the six-entry ring of stale FF lighting inputs under a vertex program

Issue: #53. Base: origin/master @ 98990d3c7c. Continues lane.ring53 (PR #391, merged): read its docs/lanes/ring53/NOTES.md first.
Files: hw/xbox/nv2a/pgraph/pgraph.h, hw/xbox/nv2a/pgraph/pgraph.c, hw/xbox/nv2a/pgraph/glsl/vsh.h,
       hw/xbox/nv2a/pgraph/glsl/vsh.c, hw/xbox/nv2a/pgraph/glsl/vsh-ff.c,
       docs/lanes/ring53impl/**, docs/testing/predictions/ring53impl-*.json.
       vsh-ff.c was released at ready by lane.zrtz272 (PR #364, folded); vsh-prog.c is free and needs no hunk.
       vk/draw.c is lane.remote's: do not touch it; if the design needs it, name the hunk and board-request it.
Needs device: yes for the arm (desktop for the design and pricing). Needs NDK: no.

## What changed since lane.ring53 stopped
The console run it asked for landed: PR #394 (lane/xbox-ringw, CI green, fold-ready; until it folds read
`git show origin/lane/xbox-ringw:docs/testing/xbox-ringw-2026-09-26.md` and docs/lanes/xbox/ringw_score.py). Measured
weights, step-4 mod 6, every leg held and all 15 cases readable:
- a draw of 1 quad advances the window start by 4 (M0); NOP 0x100, LIGHT_CONTROL (same value), empty BEGIN_END: +0
- COMBINER_COLOR_ICW (same value), SPECULAR_ENABLE (same or toggled), SET_TRANSFORM_CONSTANT vec4: +1 each
- one pb_fill: -1 (5 mod 6). Between tests, with no fill and no label, the first draw after priming starts at 5; each fill before it is -1.
- back face: face state and per-vertex back attributes +0; MATERIAL_ALPHA_BACK plus six SPECULAR_PARAMS_BACK +1 as a group
  (candidate for Specular_back's +1 -- confirm against your model, do not assume).
The weight is per METHOD SEEN BY PGRAPH, not per dword: find what pb_fill and each of these look like at the method
hook in pgraph.c before writing weights, and say how you know the mapping.

## The job
1. Implement NOTES s2's hunks exactly as sized there: ff_lit_ring[6][6][4] + ring_pos in pgraph.h; ringInput/ringPhase
   uniforms in vsh.h; fill and upload in vsh.c beside #41's hook; the per-method weight advance in pgraph.c; the consumer
   in vsh-ff.c (pgraph_glsl_append_vsh_prog_lighting). Keep the mux on the READING quad's LIGHT_CONTROL (NOTES s2 / Do not repeat).
2. Weights: use the table above, one row per method. The phase must come from the weights, never a fitted constant.
3. Price offline before the arm, held out: fit nothing on the Specular / Specular_back ControlFlags_VS captures you score.
   ring53_price.py and cf_corners.py in docs/lanes/ring53/ are the readers; extend, do not rewrite.

## Falsifier and arm
Mover: Specular and Specular_back ControlFlags_VS (102,240 px on ControlFlags_VS, 162,258 px in #53) toward their one-step floor.
Must-not-move: every FF-lighting capture (no vertex program), Lighting range/accumulation, #41's RADIAL-fog captures unless
priced in the same commit. Name which change would move each. If the table fails on a held-out row, say which method's weight is wrong
and stop -- a guessed constant is a fit. Check `status` for `unreadable` and PARTIAL COVERAGE on every row before believing a number.

## Done when
NOTES.md holds the mapping (method -> weight, with how each was recognised), the priced held-out result and the hunks; the code
is landed; the prediction is registered after the last rebase; before marking ready merge master and re-run the arm; PR is ready.
