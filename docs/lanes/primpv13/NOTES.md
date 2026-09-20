# lane.primpv13 -- #13's provoking-vertex trade in `prim_rewrite.c`

Issue: #13. Base: master @ `1e184b134f`.

## The state this lane inherited

`glsl/geom.c`'s derived edge-priority order landed (PR for the `r=+1`
rotation, fold `ba31c26ee0`) and measured PRE-REGISTERED-PASS on 13 legs:
`Tri` 58.22% -> 100.00%, nine other classes unchanged, `ALL` 85.12% ->
95.85%. `TFan` landed at the predicted **70.36%**, not 100%, and
`QStrip/TFan` at **77.17%**. That residue -- 29.64% of 9,731 plus 22.83%
of 22,897 = **32,628 decisive pixels** -- was attributed to
`rewrite_triangle_fan()` calling `emit_tri_pv()`, which rotates the
provoking vertex to index 0 before the triangle reaches `geom.c`.

## Progress log

(filled in as the lane runs; see the sections below for the findings)
