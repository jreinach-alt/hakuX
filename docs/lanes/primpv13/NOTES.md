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

1. The rotation exists so index 0 is the guest's provoking vertex. Vulkan
   rasterises first-vertex-provoking (nothing in `vk/` enables
   `VK_EXT_provoking_vertex`) and so does the *desktop* GL renderer —
   **but not the Android one** (corrected after audit pass 1, LOW 1; this
   line said "both renderers"): `gl/draw.c:535`'s
   `glProvokingVertex(GL_FIRST_VERTEX_CONVENTION)` is inside
   `#ifndef __ANDROID__`, so an Android GL build keeps GLES 3.x's *last*
   -vertex default. It does not reach the conclusion — step 3 leaves every
   edge's ordered `(i0,i1)` pair intact, so whichever endpoint the
   rasteriser takes a `flat` varying from is the same endpoint on both
   arms — and every device arm here is Vulkan. `geom.c:92` spells
   `provoking_index` as the literal `"0"` only when the shade mode is FLAT.
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

## Four things worth the next lane's time

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
pixels". That is `9,731 + 22,897` -- the **size of the two classes** under the
perpendicular model. The pixels actually naming the wrong edge are `2,884` +
`5,228` = **8,112** there, and `3,119` + `5,801` = **8,920** under the
footprint we draw. Registering 32,628 as the expected movement would have
been 3-4x out either way.

### 3. The judged instrument's DEFAULT footprint is stale, and it changes the numbers

Caught after the first registration and before any device run, which is the
only time it is fixable. `line_priority_arms.py` builds its decisive set from
a model of **our own** footprint — the question is which edge *our* capture's
colour names, so an edge our render covers but the model excludes reads as
`unm` rather than as agreement. Its default is the perpendicular rectangle,
justified in its docstring as "the footprint our renderer actually draws …
[the wider rule is] what we do not yet implement".

**That expired on 2026-09-13.** `80c23dcabe` landed the derived extent in
`geom.c`'s `widen_lines` path the same day the docstring was written, and
`7ce57a799b`/`e0c0a9974b` refined its cap on 2026-09-19. On Vulkan — every
device arm — we draw the wider width now, so `--extent-rule` is the accurate
model and the default is the stale one.

It is not a rounding difference:

| | perpendicular (default) | derived extent (`--extent-rule`) |
|---|---:|---:|
| decisive px, w 8–63.875 | 198,880 | **225,558** |
| `opp_abc`, the derived rule | 99.93%, 98–100% per class | **100.00%, and 100.00% in each of eleven classes** |
| TFan | 9,731 px @ 70.36% | 11,636 px @ **73.20%** |
| QStrip/TFan | 22,897 px @ 77.17% | 24,009 px @ **75.84%** |
| LLoop | 99.53% | **100.00%** |

> **Both totals in this table moved by +12 / +10 in the audit remediation
> below (LOW 2)**, to 225,570 and 198,890. Nothing else in it changed. The
> cause is `LLoop`'s corrected segment direction crossing `decisive()`'s
> threshold on a dozen pixels at ~1e-13; see the remediation section for the
> measurement.

225,558 is the figure `prim_rewrite.c`'s own file comment carries from #13's
original derivation, phrasing and all ("100.00% of 225,558 decisive pixels, in
each of eleven candidate classes separately") — the same instrument, the same
window and, to within this lane's own +12 (LOW 2, below), the same answer. So
the *first* #13 fold used the extent model and the *geom.c* fold used the
perpendicular default — the two folds were judged on different instruments,
and only one of them still describes the renderer.

The docstring is fixed to say so and to tell a new arm to pass `--extent-rule`.
**The default is deliberately left alone**, so the already-judged geom.c arm
stays judgeable on its own footprint — though it no longer reproduces to the
pixel: LOW 2 moved the perpendicular total to **198,890** from the 198,880
that arm was judged against, with every percentage unchanged. The prediction
was re-registered against the extent model with the perpendicular values kept
alongside each leg, so it is judgeable either way.

### 4. The offline model reproduces the device arm exactly, once the window matches

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

> **One row of this table has since moved, and the reason matters.** After the
> audit remediation below (LOW 2), the offline model gives LLoop/Tri **1,315**
> and ALL **198,890** where this table records 1,305 and 198,880. That is not
> the model drifting away from the device: `n` is the size of the *decisive
> set*, which `decisive()` computes from the goldens and the footprint model
> alone — it is device-independent, and the "arm B (device, measured)" column
> above is that same offline computation applied to the arm's captures. The
> 1,305 is a frozen printout from the tool as it stood on 2026-09-20 before
> the LLoop direction was corrected; re-run `line_priority_arms.py` against
> the *same* landed arm today and both columns read 1,315. Every percentage,
> which is the device-dependent half, is unchanged.

## The predicted arm

`ours_patched` is not a second model: `patched_order(block)` comes out
**identical to `order_for(block, "opp_abc")`** for every block -- i.e. the
patch makes our emission the derived rule exactly -- and identical to `ours`
for every block but `TFan`. Machine-checked, not asserted.

Under `--extent-rule`, the footprint we actually draw (the judged column):

| class | n | before | after | |
|---|---:|---:|---:|---|
| TFan | 11,636 | 73.20% | **100.00%** | leg 1 |
| QStrip/TFan | 24,009 | 75.84% | **100.00%** | leg 2 |
| nine others | 189,925 | 100.00% | 100.00% | leg 3 |
| **ALL** | **225,570** | **96.05%** | **100.00%** | advisory |

> **Two `n`s in this table moved with the two beside it**, and unlike those
> two this one is edited in place rather than annotated-and-frozen, because it
> mirrors the *registered* prediction and has to agree with it digit for
> digit. It recorded `nine others` 189,913 and `ALL` 225,558 before the audit
> remediation below (LOW 2); the +12 is entirely `LLoop/Tri`, 1,724 -> 1,736,
> in a class reading 100.00% before and after. Leg 3's nine per-class `n`s
> still sum to the `nine others` cell (189,925), and `189,925 + 11,636 +
> 24,009 = 225,570`. No percentage moved and no leg's verdict moved.

Under the perpendicular default (registered alongside, so the prediction is
judgeable either way): TFan 9,731 px 70.36% -> 100.00%, QStrip/TFan 22,897 px
77.17% -> 100.00%, ALL 198,890 px 95.85% -> 99.93% (198,880 before LOW 2; the
+10 is `LLoop/Tri` again, 1,305 -> 1,315), the 149 px left being `LLoop`'s
known 99.53%.

Pixels that actually change their answer: 3,119 (TFan) + 5,801 (QStrip/TFan)
= **8,920** under the extent model, 2,884 + 5,228 = 8,112 under the
perpendicular one. Both are the `moved` floors in leg 4.

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

**`glsl/geom.c` — SUPERSEDED, see the remediation section below.** This
paragraph originally said the file was untouched because it was "another
lane's territory", and **that was wrong**: `origin/board:territory.toml`
line 618 has it in `[free]`, released by `[retired.linecap13]` at
`2026-09-20T14:57:11Z`, five hours before this lane opened. What was true
is narrower — `[lane.primpv13].files` names only `prim_rewrite.c`, and a
lane may not widen its own row — which is a disclosure to the board, not
another lane's claim. The stale comment is now corrected in `geom.c`
itself; see below.

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
`49cca16cc011b94a66d4ee81ac5a38f0c683ab3f2527ae559937734fc184500c`.
Registered before any device run and committed with the refs it names.
Re-registered **twice**, both times before any device run: once to correct
the footprint model described in finding 3, and once in the audit-pass-1
remediation below. The superseded values are restated inside the file
alongside each leg, so each change is auditable rather than quiet.
The judged command is
`line_priority_arms.py --a <A> --b <B> --extent-rule --min-width 8 --max-width 63.875`. Legs
1-4 are the class measurements from `line_priority_arms.py`; legs 5 and 6 are
`must_not_move` globs covering 154 of `Shade_model`'s 168 captures -- all but
the 14 `*_TriFan_Smooth_*` that may legitimately move. Leg 5
(`*_TriFan_Flat_*`) is the trade's own guard: it is what fails, loudly, if the
predicate is inverted or the `flat_shading` term is dropped.

`2D_Lines/*` byte-identical is registered as an assertion about my own output
and **not** counted as a falsifier: `PRIMITIVE_LINES` never reaches
`rewrite_triangle_fan()`, so the patch forces it true.

## Remediation of audit pass 1 (2026-09-20, `job.cloud`)

`docs/audits/2026-09-20-primpv13-pass1.md`: 0 HIGH, 3 MEDIUM, 3 LOW. All six
are addressed below. None asked for a different predicate and none disputed a
number; `pv_placement_observable()` is unchanged.

### MEDIUM 1 — a fourth reader of index 0, and it does move

The comment that is the whole safety argument asked "does anything downstream
actually READ index 0 of a rewritten triangle?" and enumerated
`provoking_index`, `vtxFogSpecial` and `calc_triz`. It missed **`cylWrap`**,
which is a literal `[0]`, not a `provoking_index`:

```
geom.c:310   vtxT%d = cylWrap(v_vtxT%d[0], v_vtxT%d[index], bvec4(...));   // emit_vertex
geom.c:313   vtxT%d = mix(cylWrap(v_vtxT%d[0], v_vtxT%d[i0], ...),          // emit_vertex_fs
geom.c:314                cylWrap(v_vtxT%d[0], v_vtxT%d[i1], ...), t);
```

Emitted whenever `state->cylinder_wrap[i]` is non-zero (a texture unit in WRAP
address mode, `NV_PGRAPH_TEXADDRESS0_WRAP_U/V/P/Q`), in **both** the GL and the
widened Vulkan paths, and **independently of the shade mode**.

**Which way it moves.** `emit_tri_pv(hub, v1, v2, pv)` put the rim vertex at
index 0 — `v2` under last-provoking, `v1` under first — and that vertex varies
from fan triangle to fan triangle. The patch leaves `(hub, v1, v2)`, so the
cylinder-wrap reference is now the **fan hub**, one reference for the whole
fan. A rim vertex more than half a turn from the hub but less than half a turn
from its old neighbour-reference (or the reverse) now takes a whole turn it did
not take, moving its U or V by 1.0.

**Tolerated, not measured, and now said so in three places** (the
`prim_rewrite.c` comment, the prediction, here). The hub is arguably the better
reference — it is what a `TRIANGLES` draw of the same geometry already gets —
but this arm does not establish that, because **nothing in the registered disc
draws it**: `Shade_model`'s line-mode prefix is `kUntexturedLM` and
`Line width` is untextured, so a textured wireframe fan with WRAP addressing
appears nowhere and every leg is silent on it. A clean verdict is not evidence
about it either way. If a title regresses on textured wireframe geometry after
this folds, start here.

The other two index-0 readers were re-checked and do not move: `calc_triz` (a
plane's gradient is rotation-invariant; feeds `triMZ`, not coverage), and the
widened path's flat block at `geom.c:534-543`, which pins
`vtxD0/vtxD1/vtxB0/vtxB1` to a literal `[0]` but is reached only under FLAT
shading — a second reason the `flat_shading` term is load-bearing.

### MEDIUM 2 — `geom.c:197-206` corrected where it is read, not routed

Two errors, both fixed. The territory claim ("another lane's territory") was
false — `origin/board:territory.toml:618` has `glsl/geom.c` in `[free]` since
`2026-09-20T14:57:11Z`. And routing a correction in a PR body is not routing:
the body leaves the reader's view the moment it merges, which is exactly how
`line_priority.py`'s `ours` table went stale through two folds (finding 1
above).

So the six stale lines are corrected **in `geom.c` itself**, marked
`SUPERSEDED` in place rather than replaced, so a reader meets the old claim and
its correction together. `glsl/geom.c` is added to the PR's `Files:` line and
disclosed to the board in a PR comment; it is comment-only, so the generated
GLSL, and therefore both arms' binaries, are unchanged.

### MEDIUM 3 — the arm's `PASS` line covers the scoping legs and nothing else

`expect`, `expect_counts` and `must_not_regress` are all empty, so the
machine-judged content is the nine `must_not_move` globs — 167 capture checks,
every one of them a **scoping** leg. Legs 1–4 and 7, the claim the arm exists to
test, live only in the prose string, and `ab_compare.judge()` never reads it.
`ab_compare.py` guards post-hoc, tampered and unbound predictions; it has no
guard for an empty `expect`, so `VERDICT: PASS -- all 167 registered checks
hold` will print whether TFan lands at 100.00%, at 73.20% (patch never reached
the binary) or at 47.57% (composition undone rather than completed).

They stay prose — a class aggregate over many captures has no golden key for
`expect` to name, and `must_not_regress` on the one capture pair that could
carry it (`Shade_model/ProgLM_TriFan_Smooth_{First,Last}`) is drawn at the
default line width, where paint order shows on a handful of corner pixels at
most, so it could fail for reasons this lane did not model. What changed is the
**disclosure**: the prediction now says, in its own text, that the automated
verdict covers the scoping legs only; that legs 1–4 and 7 are judged by hand;
**who** does it (whoever reads the `[job.arms]` verdict — the lane if resumed,
else pass 2 or the board, *before* `fold-ready`); **what** they run (the judged
command); and **where the answer goes** (a `[lane.primpv13] arm judged:` PR
comment carrying the eleven class rows, and the same table appended here).

### LOW 1 — the Android GL build is not first-provoking

`gl/draw.c:535`'s `glProvokingVertex(GL_FIRST_VERTEX_CONVENTION)` is inside
`#ifndef __ANDROID__ /* glProvokingVertex not available in GLES 3.x */`, so an
Android GL build keeps GLES 3.x's last-vertex default. The conclusion survives
(step 3 leaves every edge's ordered pair intact; every device arm is Vulkan),
but the sentence was load-bearing prose repeated in four places. Corrected in
all four: `prim_rewrite.c`, the prediction, these notes (step 1 above) and the
PR body.

### LOW 2 — the last hard-coded convention in the derived model, and it was wrong

`line_priority.py`'s `prim_rewrite()` derived everything from the C except
`LLoop`, which returned `(i, i+1)` unconditionally — and that is what
`rewrite_line_loop()` emits under **first**-provoking, while the suite it models
is `PROVOKING_VERTEX_LAST`. The C calls `emit_line_pv(v0, v1, pv = v1)`, and
`emit_line_pv` emits `(b, a)` when the provoking vertex is not already first, so
the real pairs are `(v1, v0)` with a closing `(v_first, v_last)`. It is now
derived from a `last_provoking` parameter threaded through `our_edges()`.

**The audit called this inert for the score; it is not quite, and the
difference is worth recording.** It *is* inert in geometry — measured, not
assumed: over every `LLoop` segment, both namings, seven widths × both footprint
rules, `field()`'s coverage mask disagrees on **zero** pixels. But `t` and the
colour lerp are taken from whichever endpoint is named first, so the two namings
differ by ~1e-13 in colour, and a few pixels sitting exactly on `decisive()`'s
`SEP` / `TOL*3` thresholds cross them. Whole effect:

| | before | after |
|---|---:|---:|
| `--extent-rule` total decisive | 225,558 | 225,570 |
| `--extent-rule` LLoop/Tri | 1,724 | 1,736 |
| perpendicular total decisive | 198,880 | 198,890 |
| perpendicular LLoop/Tri | 1,305 | 1,315 |

One class, which reads 100.00% for every rule before and after. **Every figure
legs 1, 2 and 4 rest on is unchanged** — TFan 11,636 at 73.20%, QStrip/TFan
24,009 at 75.84%, `ALL` 96.05%, and the residue `225,570 − 216,650` is the same
8,920. The prediction was re-registered (still before any device run) so that
what the judged command prints matches what is registered.

The lesson for the next lane, since it is the second time on this file: a
number that "cannot be wrong today" is exactly the kind that goes stale quietly.
`field()`'s dependence on which endpoint is named first is a real, if
1e-13-sized, property of the instrument — it is not order-invariant by
construction, only by arithmetic.

### LOW 3 — "a guess scored by nothing" overstated the strip's evidence gap

`Shade_model/ProgLM_TriStrip_*` — four captures, Flat/Smooth × First/Last — *is*
`TRIANGLE_STRIP` under `POLY_MODE_LINE`, in this arm's own disc, and is
registered under `must_not_move`. It is weak evidence (default line width, so
overlap is confined to corners) but it is not nothing. The comment now reads
"not decisively scored by the `Line width` corpus, and only weakly by
`Shade_model/ProgLM_TriStrip_*` at width 1", so the next lane can price the
strip rather than read a blocker as settled. The reflection-vs-rotation half of
the argument stands unchanged.

## Audit pass 2 remediation (2026-09-21)

`docs/audits/2026-09-20-primpv13-pass2.md`: all six pass-1 scenarios closed,
**1 new MEDIUM and 1 new LOW**, both consequences of the pass-1 remediation
itself. Both are addressed here. The predicate is still unchanged, no
percentage moved, and no leg's verdict moved.

### NEW MEDIUM 1 — the `+12 / +10` correction reached four of six places

The LOW-2 fix changed what `line_priority.py` prints (`225,558 -> 225,570`
under `--extent-rule`, `198,880 -> 198,890` under the default) and the
propagation stopped short of three shipped statements of those same numbers —
one of them inside the prediction that was re-registered to fix exactly this.
The failure the audit named is concrete: the hand-judge appointed by MEDIUM 3
reads the tool's docstring and this file's leg table, runs the tool, gets
`189,925` and `225,570`, and a twelve-pixel discrepancy **in the size of the
group leg 3 declares unchanged** is the shape of the thing leg 3 forbids.

| where | said | now says |
|---|---|---|
| `line_priority_arms.py:34-49` | `198,880` / `225,558` | `198,890` / `225,570`, plus why both moved and that #13's geom.c arm re-runs at 198,890 |
| this file, the predicted-arm table | `189,913` / `225,558` / `198,880` | `189,925` / `225,570` / `198,890`, edited in place with a note, because it mirrors the registered prediction |
| this file, the docstring section | "geom.c arm (198,880 px) stays reproducible" | stays *judgeable on its own footprint*; it no longer reproduces to the pixel |
| prediction, calibration 1 | "exactly the figure … same answer" | the same answer **to within 12 px**, named as this lane's own LOW-2 correction |
| prediction, calibration 2 | reproduces the landed arm's table | …and where two `n`s are +10 against that arm's record, and why |
| `prim_rewrite.c:424` | "correct on 100.00% of 225,558 decisive pixels" | same, with a parenthetical that the instrument prints 225,570 today |

`geom.c:184` carries the same `225,558` and is **deliberately left alone**: it
attributes the figure to #13's derivation doc, which is where it came from,
and calibration 1 now names both files and the difference. Editing it would
have shifted every `geom.c` line number in this branch's prose by three —
which is the other half of this pass (NEW LOW 1) reappearing in the fix for
the first half.

**Done before the arm fires.** No `[job.arms]` comment exists on #194, so
nothing has been measured against any revision of the prediction; the
re-registration is a correction, not a post-hoc edit. `must_not_move`,
`expect`, `expect_counts`, `must_not_regress`, `disc`, `a_ref` and `b_ref` are
byte-identical to the previous registration — only `registered_utc` and the
prose moved, checked field by field rather than asserted.

`225,570` and the nine per-class `n`s were **re-derived here**, not taken from
the audit: `line_priority.py --rules --extent-rule --min-width 8 --max-width
63.875` on this tip gives TFan 11,636, QStrip/TFan 24,009 and nine others
summing to 189,925, total 225,570, `ours` 216,650 (96.05%), residue 8,920.

### NEW LOW 1 — five `geom.c` citations were +16 stale by their own hunk

The `SUPERSEDED` block added at `geom.c:196-221` in `f2433a8909` pushed every
line below it down by 16, and the hand-written citations added in the same
commit were not moved with it. `be2cc09ec7` regenerated `nv2a_index.json` for
precisely that shift, so the machine-read index was re-derived and the prose
beside it was not — which is this repo's oldest shape, one file deriving what
the one next to it hard-codes.

| citation in | said | now |
|---|---|---|
| `prim_rewrite.c:130` | `geom.c:422` | `geom.c:438` (and `:420`, where `fog_special_index` is chosen) |
| `prim_rewrite.c:131` | `geom.c:535` | `geom.c:551` |
| `prim_rewrite.c:144`, prediction | `geom.c:293-298` | `geom.c:310` and `geom.c:313-314` |
| prediction, this file | `geom.c:517-527` | `geom.c:534-543` (the `else` arm itself, not a mechanical +16) |
| this file, the cylWrap block | `geom.c:293`, `:296` | `geom.c:310`, `:313`, `:314` |

Each was checked against `geom.c` on this tip rather than shifted by 16.
`geom.c:92` (`provoking_index`) and `geom.c:197-206` (the superseded claim) sit
above the insert and are unchanged.

`prim_rewrite.c` grew five lines at `:424`, so `nv2a_index.json` is
regenerated: one site moves, `prim_rewrite.c:609 -> :614`, against an
unchanged `tests_commit 91a0de45ca` — the same tests tree the committed index
was built from, checked before the build rather than after.

**Not done, and said rather than left quiet:** the hand-judged half of this
arm (legs 1-4 and 7) is still not run, because no `[job.arms]` verdict exists
yet. That is MEDIUM 3's standing item, not a new one, and the prediction names
who owes it and where the answer goes.

---

## Attempt 2 (2026-09-20): why attempt 1 did not finish, and what this one did

### Why attempt 1 did not finish

Not because a measurement failed and not because anything in the patch was
wrong. The work was complete and pushed at `bb11b82199`, audited over three
passes (pass 1, pass 2, pass 2b), and every finding closed. What it did not
do before it stopped was **bring the trunk in**.

The fold job then refused #194 every tick, for a reason that belongs to no
commit on this branch: the PR's check rollup was FAILURE, and every failing
check on `bb11b82199` had *started before `master`'s current head existed*
(the latest, `check`, started 2026-09-21T03:06:37Z). GitHub does not re-run a
PR's checks when its base moves, so that verdict described a tree that no
longer existed and would have been refused forever. Re-running it would not
have helped either -- the workflows check out this PR's own head, not
`refs/pull/194/merge`, so the branch's own copy of whatever broke on the trunk
is the copy that runs.

A second, smaller thing: **this worktree was 9 commits behind its own remote
branch.** The three audit passes and their two remediation commits were
pushed from other sessions, so `HEAD` here was still `fd73e841b0` while
`origin/lane/primpv13` was `bb11b82199`. Reading only the local `git log`
would have shown a lane that had never been audited. Fast-forwarded first,
before anything else, and `rev-list --left-right --count` is what showed it.

### What attempt 2 did

`git fetch origin master` + `git merge origin/master` -- **merge, never
rebase**, because a rebase rewrites every sha and un-ancestors the registered
prediction's `a_ref`/`b_ref`. 31 commits came in, **no conflicts**, and the
merge touched nothing this lane owns: `git diff --stat bb11b82199..HEAD` over
`docs/testing/jobs/`, `docs/testing/nv2a_index.json`,
`docs/testing/predictions/` and `hw/` is empty. Nothing under `jobs/` moved,
so `jobs/selftest.sh` was not required.

Checked after the merge rather than assumed:

- `a_ref 4955050b31` and `b_ref 40ca2bcb22` are both still ancestors of
  `HEAD`. Merging is what keeps that true; this is the check that would have
  failed had anyone rebased.
- `sha256(docs/testing/predictions/line-prim-rewrite-fan-provoking.json)` is
  `63979910e31cc6b62ea8ed64f9435ae104949c829c1837e9f33b18b8bf104c6e`, which is
  what #194's body already carries. (The `f101bda3a8...` in the "Prediction"
  section further up this file is the *first* registration's digest, superseded
  by the footprint-model correction in `15c2fb9ae5`; the PR body is the current
  one.)
- `preflight.sh` passes on the merged head, tracker gate included -- `nv2a
  index ok`, `territory ok`, `coverage ok`, `board files ok`, exit 0.
- `git diff --stat origin/master...HEAD` is exactly the 12 paths on the PR's
  `Files:` line.

Merged head: `688fe5b8df`, pushed. **No work was re-opened, re-measured or
extended** -- the handback was explicit that only the base had moved, and this
attempt did not touch `prim_rewrite.c`, `geom.c`, the instruments or the
prediction.

### What is left, and it is not a measurement

The `needs-rebase` -> `fold-ready` label flip, once CI is green on
`688fe5b8df`. That head is a fresh build of an already-audited tree against a
trunk it merges cleanly with, so there is nothing to debug in advance of it;
if it goes red, the finding will be about `master`'s 31 new commits meeting
this branch, not about the trade.

The device arm is still unrun -- no `[job.arms]` comment exists on #194. That
remains MEDIUM 3's standing item from audit pass 2, unchanged by this attempt:
legs 1-4 and 7 are registered and judgeable, and nobody has measured them yet.
