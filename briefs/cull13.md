# cull13 -- #13 class A: cull line-mode triangles by source face (glsl/geom.c)

Lane: cull13
Issue: #13 (class A of PR #370's attribution: 31,152 structural px, 84.7% of Front_face's line-mode residual)
Base: origin/master at or after the fold of PR #379 (glsl/geom.c changed there; merge the tip before registering).
Files: hw/xbox/nv2a/pgraph/glsl/geom.c, hw/xbox/nv2a/pgraph/glsl/geom.h, hw/xbox/nv2a/pgraph/vk/renderer.c,
       docs/testing/predictions/cull13-*.json, docs/lanes/cull13/**
       (vk/draw.c is lane.remote's and prim_rewrite.c is lane.flatlm13's: do not edit them; ask on your PR if you need them.
        renderer.c is ONLY for bumping SHADER_STATE_LAYOUT_VERSION if your GeomState change does not change its size.)
Needs device: yes for the arm (Thor or Nova).

## Why (evidence)
docs/lanes/cloud-13/NOTES.md (PR #370, merged 2026-09-26), section A: `vk/draw.c` (~:4533) clears CULLENABLE for every
widened draw on "silicon does not cull lines", but TRIANGLES under POLY_MODE_LINE are widened too, and every Front_face
golden shows silicon culling them by source face. A zero-area triangle takes the CCW face. The NOTES name the hunk:
GeomState gains the cull state (filled only under POLY_MODE_LINE, in pgraph_glsl_set_geom_state); pgraph_glsl_gen_geom()'s
line-mode triangle body returns before emit_line() when the source triangle, from v_vtxPos, is culled; vk/draw.c keeps
cull off on the footprint. Read the NOTES' "What it cannot reach" (QUADS/QUAD_STRIP/POLYGON arrive already rewritten to
LINES) and "Strip parity" (prim_rewrite.c reflects odd TRIANGLE_STRIP triangles) paragraphs before writing code.
GeomState is hashed into the shader key (shaders.c:39/66): a new field changes the key; follow renderer.c's
SHADER_STATE_LAYOUT_VERSION comment (bump only if the size does not change; if another PR bumps it too, renumber).

## Proof
The NOTES' "must_move / must_not_move for the arm that lands the hunk" is the prediction (bounds, not values):
must_move: the 4 Front_face CF_FaB captures 3,911 -> <= 20 px each (the leg that shows the hunk executed); the 4 at 3,030
and 4 at 2,258 -> <= 720 each. must_not_move (byte-identical): Shade_model/ProgLM_* (incl. ProgLM_TriStrip_* parity),
Line_width Tri/TFan, FrontFace_FM_*, 3D_primitive lines. Register docs/testing/predictions/cull13-*.json after your last merge.

## Done when
The hunk is in a READY PR with the arm verdict cited and docs/lanes/cull13/NOTES.md; or the hunk is left out with the
measurement that refuted it. The PR touches hw/, so it goes to audit.

## Do not
Edit board files. Tune to a must_move that lands on another figure. Wait on a background task at the end of a turn: your session exits and the task dies with it.
