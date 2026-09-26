# flatlm13 -- #13 class C: one flat colour for a line-mode quad/polygon (prim_rewrite.c)

Lane: flatlm13
Issue: #13 (Line and point rasterisation; class C of PR #370's attribution, 7,324 structural px, Shade_model only)
Base: origin/master at a5b5b628f2 or later (merge the tip before you register any prediction).
Files: hw/xbox/nv2a/pgraph/prim_rewrite.c, docs/testing/predictions/flatlm13-*.json, docs/lanes/flatlm13/**
       (glsl/geom.c is lane.tiecode282's and vk/draw.c is lane.remote's: do not edit them. Ask on your PR for any other file.)
Needs device: yes for the arm (Thor or Nova, via arms.sh / request.sh). Desktop-buildable.

## Why (evidence)
PR #370 (lane cloud-13, merged 2026-09-26 06:52 UTC) attributed every structural pixel of the line-mode
families: docs/lanes/cloud-13/NOTES.md, section "C. Flat colour in a line-mode quad/polygon". Only
`Shade_model/ProgLM_{Quad,QuadStrip,Poly}_Flat_*` carry it (982-1,388 px each); smooth variants and every flat
Tri/TriStrip/TriFan have 0 colour px. Silicon draws the whole wireframe quad in ONE colour (flat_edge_colour.py:
all four edges of the left quad carry vertex 3's colour) and FIRST and LAST give the same golden. We colour each
edge from its own first endpoint, because QUADS/QUAD_STRIP/POLYGON under line mode reach geom.c already rewritten
to independent LINES (prim_rewrite.c:254-268) and emit_line() takes the flat colour per edge. The NOTES warn:
which vertex silicon picks is read on ONE quad only -- settle it on all three primitives from the goldens first.

## Build
1. Read the NOTES section C and docs/lanes/primpv13/NOTES.md (PR #194, "narrowed, not abolished").
2. From the goldens (Shade_model ProgLM_*_Flat_* for Quad, QuadStrip, Poly, both FIRST and LAST provoking), establish
   which source vertex's colour silicon uses for each primitive -- a table, per primitive, before any code.
3. In prim_rewrite.c, when rewriting a line-mode QUADS/QUAD_STRIP/POLYGON to LINES under flat shading, make every
   emitted edge carry that vertex (e.g. by ordering each edge's vertices or duplicating the provoking vertex).

## Proof
A registered arm (docs/testing/predictions/flatlm13-*.json, registered AFTER your last merge of master):
must_move: the 12 ProgLM_{Quad,QuadStrip,Poly}_Flat_* captures lose their colour px (bound from the NOTES table);
must_not_move: ProgLM_*_Smooth_*, every ProgLM Tri/TriStrip/TriFan, Front_face, Line_width, 3D_primitive lines.
Name for each leg the source change that would move it.

## Done when
The hunk is in a READY PR with the arm verdict cited and docs/lanes/flatlm13/NOTES.md naming the rule and the
per-primitive table; or the hunk is left out with the measurement that refuted it. The tracker row is the board's.

## Do not
Edit board files (territory.toml, nv2a_issues.toml). Tune to a must_move that lands on another figure: report it.
Wait on a background task at the end of a turn: your session exits and it dies with it -- poll to completion or stop with a result.
