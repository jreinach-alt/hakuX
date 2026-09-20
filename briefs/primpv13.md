# lane.primpv13 -- #13's provoking-vertex trade in prim_rewrite.c

Issue: #13 (Line and point rasterisation)
Base: master @ 1e184b134f2e81f24a2457eeefac7b2473b8f8a5
Files: hw/xbox/nv2a/pgraph/prim_rewrite.c

## What's already done

geom.c's derived edge-priority order (last-drawn wins, per-primitive
triangulation) landed and is measured: Tri 58.22%->100.00%, nine other
classes unchanged, ALL 85.12%->95.85%. TFan came in at the PREDICTED
70.36%, not 100%, because `rewrite_triangle_fan()` calls `emit_tri_pv()`,
which rotates the provoking vertex to index 0 before the triangle reaches
geom.c. A fan triangle therefore arrives already rotated by one relative
to a list triangle, and `GeomState::primitive_mode` carries the REWRITTEN
mode, so geom.c cannot tell the two apart and cannot compensate. Residue:
TFan short by 29.64% of 9,731 decisive px, QStrip/TFan short by 22.83% of
22,897 -- 32,628 decisive pixels, all attributed and none guessed (the
issue's own #13 comments show this number was predicted before being
measured, on a leg registered as NOT reaching 100%).

## Goal

Undo (or compensate for) `rewrite_triangle_fan()`'s provoking-vertex
rotation for the fan/quad-strip-fan edge-order classes ONLY, without
breaking flat shading, which needs the provoking vertex at index 0 for
geom.c's `provoking_index`. This is a genuine trade, not an oversight --
read #13's tracker entry and its GitHub comments (the "What is left, and
it is 32,628 decisive pixels" section) before touching the file; a prior
hand-trace of this same rotation got the direction backwards and only a
calibration against measured per-class percentages caught it.

## Falsifier

`docs/testing/line_priority.py --order` (and `--rules`) against the
Line_*/Shade_model goldens: TFan and QStrip/TFan must move toward 100%
decisive-pixel agreement without moving Tri, QUADS, QUAD_STRIP, POLYGON,
or the LINES/STRIP/LOOP classes off their current (already-exact) values,
and without regressing any Line_0000.*/Line_0064.* or Shade_model flat
capture already accounted for in the geom.c fold. Register a prediction
naming the expected TFan/QStrip-TFan percentage before running the arm --
a leg that only says "improves" is not a falsifier here, per the issue's
own method note.

## Done when

line_priority.py shows TFan and QStrip/TFan at or converging toward 100%
decisive agreement, ab_compare shows 0 worse against the must-not-move
classes, flat-shading behaviour is unchanged (state so explicitly), and a
registered prediction is written so the arms job can queue device
verification.
