# lane flatlm13 -- #13 class C: one flat colour per line-mode quad/polygon

Issue #13, class C of PR #370's attribution (`docs/lanes/cloud-13/NOTES.md`
section C): 7,324 colour px, only in `Shade_model/ProgLM_{Quad,QuadStrip,Poly}_Flat_*`.
There are **six** such goldens (3 primitives x FIRST/LAST), not twelve as the brief
says.

## The rule, per primitive, from the goldens

`edge_colour.py` projects `shade_model_tests.cpp`'s vertices (camera z = -7,
fov pi/4, 640x480) and reads the modal colour on the middle 70% of every
boundary edge.  Every edge reads 100% one colour.

| primitive | vertices | colour on EVERY edge (FIRST and LAST alike) | ours today |
|---|---|---|---|
| QUADS | 2 quads, v0-3 and v4-7 | v3 on quad 0, v7 on quad 1: the quad's 4th vertex | each edge's first emitted endpoint |
| QUAD_STRIP | 6 vertices, quads (0,1,2,3), (2,3,4,5) | v3 on quad 0, v5 on quad 1: v(2k+3); the shared edge v2-v3 takes v5 (the later quad paints over it) | same |
| POLYGON | 5 vertices | v0 | same |

So silicon's flat vertex for these is fixed by the primitive and **ignores
FLAT_SHADE_OP**, which is the same vertex the FILL paths already colour from
(v3 for quads, #224; the fan hub v0 for the polygon).

**Read the captures R/B-swapped.**  The PNG channels are kTestDiffuse with red and
blue exchanged: v0 FF0000 reads as 0000FF (= v2's value), v4 FF33CC as CC33FF
(= v9).  cloud-13's `flat_edge_colour.py` names by the unswapped table, and its
"left quad = v3" is right only because v3 (CCCCCC) is swap-invariant.  Under the
unswapped table the right quad reads "v6" and the strip "v8", neither of which is
in the quad.  Both tools here name with the swap.

## Why prim_rewrite.c can fix only part of it

glsl/geom.c gives an emitted LINE its flat varyings from `gl_in[0]` (the
`provoking_index` literal "0" under flat).  A LINES pair has two slots, so an edge
that does not TOUCH the colour vertex (quad edges v0-v1 and v1-v2, polygon edges
v1-v2, v2-v3 and v3-v4) cannot carry it through an index rewrite.  Routing the quad
through TRIANGLES under POLY_MODE_LINE would give every edge `gl_in[0]`, but it
also draws the diagonal, so that route was not taken.

**The hunk (777d929850):** under flat shading, each edge that touches the colour
vertex is emitted FROM it (`emit_edge_flat()`): quads (v2,v3) -> (v3,v2), strip
(v1,v3) -> (v3,v1), polygon closing edge (v_n-1,v0) -> (v0,v_n-1).  Paint order is
unchanged.  Smooth output is byte-identical: `rewrite_edges.sh` builds the real
prim_rewrite.c and prints the emitted pairs, and the diff against master's is
exactly the flat rows.

**Remainder, for the lane that holds geom.c:** a line input with a third slot, e.g. a
LINES_ADJACENCY layout (p, a, b, p) whose flat varyings read slot 0 and whose
line is slots 1-2, as PRIM_TYPE_TRIANGLES_ADJACENCY does for the filled quad
(#224).  That touches vsh_regs.h (enum), glsl/geom.c (layout + body),
vk/draw.c (topology, verts_per_prim), gl/shaders.c and the shader-state cache
version.  prim_rewrite.c would then emit (p, a, b, p) for every edge.

## Offline price (captures1 of 1790373302-arms-wparamcode223-fix-991557, ref 8555c013c6)

`price.py CAPDIR` recolours each edge of the capture in place (in these draws
every edge is uniquely coloured by its first endpoint, located by segment
proximity because the strip reuses v2 and v3) and counts colour px (ink in both,
colour differs) against the golden:

| capture | now | orient (this hunk) | whole (needs geom.c) |
|---|---|---|---|
| Quad_Flat_First / Last | 1,388 | 974 | 0 |
| QuadStrip_Flat_First / Last | 1,275 | 761 | 3 |
| Poly_Flat_First / Last | 994 | 540 | 0 |
| **total (6)** | **7,314** | **4,550** | **6** |

`whole` reaching 0 to 3 px shows the model reproduces silicon: one colour per
quad or polygon, v3/v(2k+3)/v0, is the complete class-C rule.  The hunk takes 38%
of class C.  It assumes reversing an edge's direction does not change its coverage;
the arm tests that.

## Reach

Every suite but Shade_model resets SMOOTH in setup (test_suite.cpp:177), and the
hunk is gated on flat_shading and POLY_MODE_LINE QUADS/QUAD_STRIP/POLYGON.  So
the six captures above are the only ones on the registered disc it can move.
`docs/testing/line_priority.py` models the SMOOTH Line_width path and stays
current.

## Arm

`docs/testing/predictions/flatlm13-orient.json`, a 02374a6847 (master) vs b
970c382ed1 (the hunk merged onto it).  Disc: Shade model, Front face, Line width,
3D primitive, Edge flag.

| leg | judged by | what would move it |
|---|---|---|
| the six ProgLM_{Quad,QuadStrip,Poly}_Flat_* move better | ab_compare `expect_counts` better=6, worse=0 | `emit_edge_flat()` in the three rewrite_*_line() |
| each of them equals `orient`(A) pixel for pixel | `price.py --verify A/captures1 B/captures1`, run by this lane (its A==B control FAILs) | coverage changing when an edge is reversed |
| every other Shade_model capture (162, globs checked to leave exactly the six free), Front_face, Line_width, 3D_primitive, Edge_flag bit-identical | `must_not_move` | the flat gate failing; a fill-path change (none) |

Verdict: pending.  Session 1 (2026-09-26) stopped WAITING on the arms job's
`[job.arms]` comment on PR #401 for this prediction; on resume run
`price.py --verify` on its two result dirs, cite both, and mark the PR ready if
the legs hold.

## Do not repeat

- Do not name vertices from these PNGs without the R/B swap (above).
- Do not route a line-mode quad through TRIANGLES to get `gl_in[0]` for every
  edge: geom.c then draws the diagonal.
- The `differing` column for these six captures differs between the 09-25 arms
  (1007 / 1670 / 1408) and the 09-26 Thor release run at aeb4a096b6
  (1028 / 1470 / 1407), so do not carry an absolute value across refs; predict
  B from A.
