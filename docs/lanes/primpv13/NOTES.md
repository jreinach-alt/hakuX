# lane.primpv13 -- #13's provoking-vertex trade in `prim_rewrite.c`

Issue: #13. Base: master @ `1e184b134f`. PR #194.

## The state this lane inherited

`glsl/geom.c`'s derived edge-priority order landed (fold `ba31c26ee0`) and
measured PRE-REGISTERED-PASS on 13 legs: `Tri` 58.22% -> 100.00%, nine other
classes unchanged, `ALL` 85.12% -> 95.85%. `TFan` landed at the predicted
**70.36%**, not 100%, and `QStrip/TFan` at **77.17%**, attributed to
`rewrite_triangle_fan()` calling `emit_tri_pv()`.

## What this lane changed

`pv_placement_observable(mode)` -- `flat_shading || polygon_mode !=
POLY_MODE_LINE` -- now gates the fan's provoking-vertex rotation.

The reasoning, in the order it has to be read:

1. The rotation exists so index 0 is the guest's provoking vertex. Both
   renderers rasterise first-vertex-provoking (`gl/draw.c` sets
   `GL_FIRST_VERTEX_CONVENTION`; nothing in `vk/` enables
   `VK_EXT_provoking_vertex`), and `geom.c:92` spells `provoking_index` as
   the literal `"0"` only when the shade mode is FLAT.
2. `needs_rewrite()` **already encodes exactly this** for
   `PRIM_TYPE_TRIANGLES`: it declines to rewrite at all unless the draw is
   flat AND last-provoking. The strip and the fan must be rewritten whatever
   the state, because that is a topology change, and the provoking placement
   rode along with it. That asymmetry *is* #13's residue.
3. Under `POLY_MODE_LINE` the rotation is worse than useless. `geom.c` splits
   `(A,B,C)` into `emit_line(B,C)`, `emit_line(C,A)`, `emit_line(A,B)`, so
   rotating the triple is a **pure rotation of the edge list**: the multiset
   of *ordered* `(i0,i1)` pairs is unchanged, only the paint order moves.
4. Hence `vtxFogSpecial` -- which `glsl/common.c` qualifies `flat` in EVERY
   shade mode, so it *is* observable under smooth shading -- does not change:
   each `emit_line()` takes it from that edge's own first endpoint, not from
   the triangle's index 0, and no edge's endpoints move.
5. Under `POLY_MODE_FILL` and `POLY_MODE_POINT` step 3 does not hold: there
   the rotation decides the triangle's provoking output vertex outright, and
   with it the flat colour and `vtxFogSpecial`. Those keep it.

So the trade is **narrowed, not abolished**: it survives only for a
flat-shaded wireframe, where the colour must win over the paint order.

## Flat shading is unchanged -- stated explicitly, as the brief asks

`pv_placement_observable()` returns true whenever `flat_shading` is set, in
every polygon mode, so `rewrite_triangle_fan()` behaves exactly as before on
every flat-shaded draw. This is not an argument; it is the first term of the
predicate, and the all-states A/B below measures it.

## Three things worth the next lane's time

### 1. The falsifier the brief named was measuring a renderer two folds old

`line_priority.py`'s `our_edges()` was hand-listed when the tool was written
(`68c5d92a69`) and **never updated by either fold**. Run as-is it scored:

| block | hand-listed `ours` | what the tree actually emits |
|---|---|---|
| Tri | `(0,1) (1,2) (2,0)` | `(1,2) (2,0) (0,1)` |
| QStrip | `(0,1) (1,3) (3,2) (2,0)` | `(2,0) (0,1) (1,3) (3,2)` |
| Poly | `(0,1) (1,2) (2,3) ...` | `(1,2) (0,1) (2,3) ...` |
| Quad | `(0,1) (1,2) (2,3) (3,0)` | `(1,2) (0,1) (2,3) (3,0)` |
| LLoop, TFan | correct | correct (the two rotations cancel for TFan) |

`order_for()` was worse: its index arithmetic (`_perm(3t, 3t+1, 3t+2, ...)`)
was tacitly keyed to the *old* `our_edges` layout, so the `opp_abc` column --
the derived rule itself -- was also being scored against the wrong slots.
Both are now **derived** from `prim_rewrite()` composed with `geom.c`'s three
`emit_line()` calls, and `silicon_tris()` states the tessellation once so a
slot counts as internal exactly when its pair is absent from the emission.
A future edit to either file now shows up as a changed score instead of as a
silently wrong baseline.

**Do not trust a tool's "ours" column without dating it against the tree.**

### 2. "32,628 decisive pixels" is a population, not a residual

#13's comments and this lane's brief both call the residue "32,628 decisive
pixels". That is `9,731 + 22,897` -- the **size of the two classes**. The
pixels actually naming the wrong edge are `2,884` (TFan) + `5,228`
(QStrip/TFan) = **8,112**, which is also exactly the gap between the two rule
columns (`198,731 - 190,619`). Registering 32,628 as the expected movement
would have been wrong by 4x.

### 3. The offline model reproduces the device arm exactly, once the window matches

`line_priority.py --rules` on its defaults does *not* reproduce the arm: it
gives ALL = 203,023 px and Tri = 98.05%. The difference is entirely the width
window -- the arm ran `--min-width 8 --max-width 63.875`, which also excludes
the void `Line_0064.*`. With that window:

| class | n | `ours` (offline) | arm B (device, measured) |
|---|---:|---:|---:|
| Tri | 45,760 | 100.00% | 100.00% |
| QStrip | 35,560 | 100.00% | 100.00% |
| LLoop | 31,548 | 99.53% | 99.53% |
| QStrip/TFan | 22,897 | 77.17% | 77.17% |
| Quad | 22,761 | 100.00% | 100.00% |
| Poly | 15,235 | 100.00% | 100.00% |
| Poly/TFan | 13,853 | 100.00% | 100.00% |
| TFan | 9,731 | 70.36% | 70.36% |
| LLoop/Tri | 1,305 | 100.00% | 100.00% |
| Poly/Tri | 222 | 100.00% | 100.00% |
| LLoop/TFan | 8 | 100.00% | 100.00% |
| **ALL** | **198,880** | **95.85%** | **95.85%** |

Eleven `n`s and twelve percentages, none fitted. That is what makes the
predicted column below a prediction.

## The predicted arm

`ours_patched` is not a second model: `patched_order(block)` comes out
**identical to `order_for(block, "opp_abc")`** for every block -- i.e. the
patch makes our emission the derived rule exactly -- and identical to `ours`
for every block but `TFan`. Machine-checked, not asserted.

| class | before | after | |
|---|---:|---:|---|
| TFan | 70.36% | **100.00%** | leg 1 |
| QStrip/TFan | 77.17% | **100.00%** | leg 2 |
| nine others | -- | unchanged | leg 3 |
| ALL | 95.85% | **99.93%** | advisory |

The 149 px left at 99.93% is `LLoop`'s known 99.53% (about 148 of it); this
patch cannot touch it and does not claim to.

## Scope, measured rather than asserted

Both revisions of `prim_rewrite.c` were compiled side by side (public symbols
renamed, statics kept file-local) and their output diffed over every
`(primitive_mode x polygon_mode x last_provoking x flat_shading x count)`
combination -- 1508 states:

```
DIFF TRIANGLE_FAN   LINE  lastpv=0 flat=0 count= 6  n=12/12
DIFF TRIANGLE_FAN   LINE  lastpv=1 flat=0 count= 6  n=12/12
        old: 2 0 1 3 0 2 4 0 3 5 0 4
        new: 0 1 2 0 2 3 0 3 4 0 4 5
20 of 1508 (mode x polymode x lastpv x flat x count) states differ
```

Every differing state is `TRIANGLE_FAN` + `POLY_MODE_LINE` + smooth, at both
provoking conventions, with an **identical index count**. That dump is also
the direct evidence for the edge-list claim in step 3 above: `2 0 1` yields
edges `(0,1) (1,2) (2,0)` and `0 1 2` yields `(1,2) (2,0) (0,1)` -- the same
ordered pairs, rotated. A prior hand-trace of this same rotation got its
*direction* backwards; this is why it was compiled rather than read.

## What this lane did NOT do, and why

**`rewrite_triangle_strip()` is untouched.** The same reasoning reaches it --
a strip triangle is pre-rotated relative to a list triangle too, and `geom.c`
cannot tell them apart either. The difference is evidence: the odd-`i` case
is a **reflection** `(v1, v0, v2)`, not a rotation, so its composition with
`geom.c`'s edge order is a different derivation, and the `Line width` corpus
that pins these orders to the pixel draws **no `TRIANGLE_STRIP` under
`POLY_MODE_LINE` at all** (the eleven classes are LLoop/Tri/QStrip/TFan/
Poly/Quad and their mixtures -- no TStrip). Changing it would be a guess
scored by nothing. If someone wants it, it needs a disc variant that draws a
wireframe triangle strip first.

**`glsl/geom.c` is untouched** -- another lane's territory. Its comment at
lines ~195-206 now describes a state that no longer exists ("the rest of
TFan is `rewrite_triangle_fan()`'s rotation to undo, and undoing it there
collides with flat shading"). That is now done, and narrowed rather than
collided-with. Routed on the PR rather than edited here.

**The extent rule** is still #13's larger half and is not this lane's.

## Second-order item, disclosed rather than buried

`geom.c`'s `POLY_MODE_LINE` body takes its depth slope from
`calc_triz(0, 1, 2)`, which builds `m` and `b` relative to vertex 0. A fan
triangle's `dz` is therefore now evaluated on the same basis a list
triangle's already was. The plane's gradient is rotation-invariant, so this
can move `dz` only by floating-point rounding, and it feeds `triMZ` (depth),
never coverage. `Line width` disables the depth test, so it cannot show
there at all. Named in the prediction as expected-to-move-direction-
unpredicted rather than claimed inert.

## Prediction

`docs/testing/predictions/line-prim-rewrite-fan-provoking.json`,
a_ref `4955050b31` -> b_ref `40ca2bcb22`, sha256
`d62d2817409eb451dd897d16a0d2ceb3e78d68f168015ded87371e40046470f3`.
Registered before any device run and committed with the refs it names. Legs
1-4 are the class measurements from `line_priority_arms.py`; legs 5 and 6 are
`must_not_move` globs covering 154 of `Shade_model`'s 168 captures -- all but
the 14 `*_TriFan_Smooth_*` that may legitimately move. Leg 5
(`*_TriFan_Flat_*`) is the trade's own guard: it is what fails, loudly, if the
predicate is inverted or the `flat_shading` term is dropped.

`2D_Lines/*` byte-identical is registered as an assertion about my own output
and **not** counted as a falsifier: `PRIMITIVE_LINES` never reaches
`rewrite_triangle_fan()`, so the patch forces it true.
