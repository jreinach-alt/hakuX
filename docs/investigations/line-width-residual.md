# `Line width`: what is actually left, and the mistake that hid it

Rewritten 2026-09-12. The first version of this file said the width never
reaches the rasteriser. **That was wrong**, and the way it went wrong is worth
more than the conclusion was.

## The mistake

I measured our output against the goldens using `res_full0907`, a full-corpus
capture set from 2026-09-07, and never checked it against the binary it came
from. `4ed3a55ea6`, "nv2a: rasterise lines at the width SET_LINE_WIDTH asks
for", landed on 2026-09-11 — after those captures were taken. So the constant
coverage column I found, ~6,470 lit pixels for every width from 0.0 to 64.875,
was real and is four days stale. On the current binary the same measurement
tracks silicon.

The same-shaped error is already on the record for goldens
(`docs/testing/nv2a_issues.toml` #27: a test newer than its golden poisons a
suite). This is that error pointed the other way — a capture older than its
fix — and it cost a write-up, an instrumented build and a wrong entry at the
top of the target ranking. **Date the captures against the commit, not just
the goldens against the disc.**

## What the current binary does

Measured on the #19 sweep's own `g0` arm, APK `f9b5a5df2776`, all 61 captures.

| width | golden | ours | ours/golden |
|---:|---:|---:|---:|
| 0.000 | 3,104 | 3,104 | **1.00 exact** |
| 0.125 | 3,564 | 6,471 | 1.82 |
| 0.500 | 4,798 | 6,475 | 1.35 |
| 1.000 | 6,677 | 6,471 | 0.97 |
| 1.125 | 7,296 | 6,451 | 0.88 |
| 1.250 | 7,667 | 8,124 | 1.06 |
| 1.750 | 9,172 | 9,566 | 1.04 |
| 4.000 | 16,192 | 15,491 | 0.96 |
| 16.000 | 42,870 | 41,229 | 0.96 |
| 63.875 | 91,319 | 89,374 | 0.98 |

Three distinct things are left, and they want different work:

**1. Below about 1.25 px the width does not move.** Ours sits at ~6,470 — the
1.0 figure — from 0.125 through 1.125, while silicon rises smoothly from 3,564
to 7,296. Above that our coverage steps in visible jumps (6,471 → 8,124 →
9,566), which is a granularity quantum, not a smooth curve. Both are the
device's doing: `lineWidthRange[0]` need not go below 1.0 and
`lineWidthGranularity` snaps what it does admit. `4ed3a55ea6` says as much and
deliberately left it: silicon draws a rectangle narrower than a pixel as
*dashes*, which no line rasteriser will do.

**2. Width 0.0 is exact**, and that is not luck — the same commit found that a
zero-width line covers no pixel centre and drops the draw entirely, which the
golden confirms by keeping the test's points and losing every line.

**3. A systematic 3-4% shortfall at every width from 1.0 up.** 0.96–0.98 with
a slow drift towards 1.0 as the line gets wider, which is the signature of a
per-line constant: the ends. On a wide line the ends are a smaller fraction of
the total, so the ratio improves. `4ed3a55ea6` names "the ends and joins" as
remaining, and this is the shape of that.

## The device's limits, measured

`0a97b8f48e` logged them and one run of the suite settled it. Adreno 740 under
Turnip (Mesa 26.3.0):

    lineWidthRange [1.000, 127.500]   lineWidthGranularity 0.5   wideLines=1

Which produces exactly this, over the 52 distinct widths the suite asks for:

| register | asked | delivered |
|---|---|---|
| 0 – 9 | 0.000 – 1.125 px | **1.000** |
| 10 – 13 | 1.250 – 1.625 px | **1.500** |
| 14 – 15 | 1.750 – 1.875 px | **2.000** |
| 24 and up | 3.000 px and up | **exact** |

So the register is honoured exactly from 3 px up — every whole-pixel width
lands on the device's half-pixel grid — and the device only interferes below
2 px, where the 1.0 minimum and the 0.5 granularity between them flatten
sixteen of the suite's sixty-one tests.

**That splits the work cleanly, which is the point of having measured it:**

* **16 tests** (widths 0.000 – 1.875) are unreachable without generating line
  geometry ourselves. That is the architectural change, and it buys sixteen
  tests.
* **45 tests** (3 px and up) already receive the exact width they ask for, so
  every pixel they still get wrong is **ours** — the ends and caps, and the
  colour along the line. No rewrite required to work on them.

The desktop lane measures granularity 1/128 on lavapipe, so the sixteen
affected tests land much closer there. Line-width accuracy is therefore
host-dependent today, and generating the geometry would remove that dependence
as well as fixing the sixteen.

## What is worth doing, in order

1. ~~The device's limits~~ — done, above.
2. **The ends**, which is (3), the only part that is ours rather than the
   device's, and it applies at *every* width rather than to a corner of the
   range.
3. **Lines as geometry**, which is the only route to (1) and to the sub-pixel
   dashes. Expensive: `emit_line` in `glsl/geom.c` already computes the
   perpendicular, but `emit_vertex` passes `gl_Position` through untouched and
   the widened quad must carry the original `vtxPos0/1/2` triple so fragment
   interpolation still describes the true line. It also needs a pixel-to-clip
   scale in the geometry stage, which has no uniform block today — so either
   new uniform plumbing across both renderers, or the surface size keyed into
   `GeomState` the way the width would be. Worth doing after (1) says how much
   it buys.

Method note: measuring lit pixels per capture against the requested parameter
is what made all of this legible, both the stale answer and the real one — a
golden diff says "these pixels are wrong", a coverage column says whether the
parameter is arriving and in what steps. `docs/testing/line_coverage.py`. Its
one-line verdict ("constant to within 5%: the parameter is not arriving")
is what should have made me check the date, because a parameter that had never
worked at all would have been noticed by whoever wrote the register handler.

---

# Rewritten again 2026-09-12 evening: the width is right, and the residual is not the width

The sections above ask "is the width arriving" and answer yes above 3 px. That
is still true. This section asks the next question — *what shape* is silicon
laying down, and what is actually left — and the answer moves this issue off
line width entirely.

Measured on the scoreboard sweep column `z-sweep-044-Line_width`, APK
`fb4dfafc6d38`, ref `ce9c4eecf8`, Retroid Pocket Nova. Tool:
`docs/testing/line_footprint.py`.

## Not blocked on a capability, unlike #36

#36 closed as blocked because lines need `VK_EXT_line_rasterization` and its
six feature booleans are unmeasured. **That does not apply here.** The device
log from `0a97b8f48e` says:

    lineWidthRange [1.000, 127.500]   lineWidthGranularity 0.5   wideLines=1

63.875 is less than half the limit. Nothing wide is clamped. `63.875` snaps to
`64.0` and every other width the suite asks for at 3 px and up is delivered
exactly. **The clamp hypothesis for the six widest captures is dead**, and it is
dead by measurement rather than by argument: a clamp predicts a residual that
stops changing above the limit, and the residual instead rises monotonically
through 63.875 while the *rendered width in pixels* tracks the register exactly.

## What silicon draws for a wide line

Fitted on the QUADS primitive at the bottom left, the only one with a region of
its own — nothing else in the test reaches y > 366.

| model | golden, err as % of its ink (w = 4 … 63) |
|---|---|
| perpendicular rectangle, butt ends | **1.7 – 5.9%**, and every pixel of it *missing* |
| + bevel join | 6.6 – 15.5% |
| + round join | 7.0 – 21.2% |
| + miter join | 7.4 – 24.4% |
| square caps | 7.6 – 26.8% |

So silicon draws a **perpendicular butt-capped rectangle of exactly the
requested width**: no square caps, no round, bevel or miter join. Adding any
join model makes the fit strictly worse, and none of them removes a single one
of the missing pixels — whatever silicon covers beyond the rectangle union is
not the outer wedge at a join.

The same fit against **our own** output lands at **0.03 – 0.20%**. Our wide
line is that rectangle, to within a handful of pixels in a hundred thousand.

## The one exact rule difference: where the line's centre goes

The quad strip's left edge is vertical at screen x = 160, and row 230 crosses
it far from either end, so the coverage rule can be read off directly. A line
of width W centred at `cx` lights the columns whose centre is in
`[cx - W/2, cx + W/2)`:

| | cx = 160.0, the vertex | cx = 160.5, the pixel centre |
|---|---:|---:|
| golden matches | 11/18 | **18/18** |
| ours matches | **18/18** | 11/18 |

over the eighteen widths from 3.0 to 48.0 where the register is honoured.
Both light exactly W columns. **Silicon puts the line's centre on the pixel
centre nearest the line; we put it on the vertex.** They coincide at even
widths and sit one pixel apart at odd ones, which is the ~1,000 extra
structural channels every odd-width capture carries over its even neighbours
(56 → 44,486, 57 → 45,697, 58 → 45,532, 59 → 46,451 …).

**This is line-specific, and that matters.** The scope warning on #13 says the
fix runs through `roundScreenCoords` in `glsl/vsh.c` and is therefore
rasteriser-wide. It is not: `Fill_0000.0` in this same suite is **coverage
exact — 0 golden-only pixels and 0 ours-only**, and the filled quad strip's left
boundary starts at column 160 in both. The shared vertex path is already right.
Only the line rasteriser disagrees, and it disagrees by snapping, not by an
offset — a line at x = 160.3 snaps to 160.5 (+0.2) and one at 160.7 snaps to
160.5 (−0.2), so no constant translate reproduces it. It needs the line turned
into geometry we place ourselves.

## What the residual actually is

All 57 `Line_*` captures, RGBA, structural = any channel more than one step out:

    structural channels 1,000,125  over  342,679 structural pixels
      golden-only ink (we under-cover)    63,983   18.7%
      ours-only ink   (we over-cover)     17,062    5.0%
      colour on ink both agree about     261,634   76.3%

and of that colour class, by magnitude:

| max channel delta | px | share of the colour class |
|---|---:|---:|
| 2 – 8 | 5,753 | 2.2% |
| 9 – 32 | 40,028 | 15.3% |
| 33 – 96 | 138,027 | 52.8% |
| > 96 | 77,826 | 29.7% |

**82.5% of the colour class is larger than a third of the range.** The test's
palette is built from 0x33 and 0xFF, so a 204-step delta is one palette entry
swapped for another: at those pixels both renderers put ink down and disagree
about *which of several overlapping wide edges is on top*. The suite draws
seven wireframe primitives in a 320×360 box; at width 63 every edge overlaps
several others, and a single row through the quad strip shows it plainly —
golden holds the vertical edge's colour across x = 131…179 while ours switches
at x = 155 to the bottom-left edge's gradient, a segment that is present in
both renders and merely buried in one of them.

So the ranking is:

* **76.3%** of the structural residual is edge priority in the overlaps, not
  line width.
* **18.7%** is coverage we lack, which is the centre snap above plus the
  sub-pixel widths (0.125 – 1.125, where the device's own 1.0 minimum flattens
  eight captures and silicon draws dashes).
* **5.0%** is coverage we add.

The 342,679 figure independently reproduces the ~342k in `line-width.md`,
reached there by a different split on a different capture set.

## Where the priority difference comes from, and what is unresolved

Two different mechanisms produce the wireframe edges, and both clusters show
the residual:

* `QUAD_STRIP`, `QUADS` and `POLYGON` in `POLY_MODE_LINE` are rewritten to
  explicit `PRIM_TYPE_LINES` by `pgraph/prim_rewrite.c`, so **we** choose the
  emission order. `rewrite_quad_strip_line` emits v0-v1, v1-v3, v3-v2, v2-v0,
  which makes v2-v0 last and therefore the winner. Silicon shows v0-v1 winning
  at the one pixel checked by hand, which is consistent with hardware walking
  the two triangles' edges rather than the quad's boundary — but that is one
  data point and a triangle-edge order does not fall out of it uniquely.
* `TRIANGLES`, `TRIANGLE_STRIP` and `TRIANGLE_FAN` keep `VK_POLYGON_MODE_LINE`
  (`vk/draw.c` line 1593), so **Turnip** chooses the order and we cannot.
* `LINE_LOOP` has an unambiguous order that we already match, and still carries
  9,696 structural channels at width 63 — so ordering cannot be the whole
  story even for the clusters where we control it.

That last point is the one that is not settled. A full painter model of the
line loop (16 wide butt quads, colour lerped along each) reproduces neither
capture well enough to arbitrate, so the loop's residual has some other cause
and is the capture that should be attacked first: **`Line_0016.0`, the
`LineLoop` cluster** — moderate width, no polygon-mode question, no rewrite
choice, 2,259 structural channels.

## Recommendation

Do not treat `Line_width` as a line-width defect; the width is correct and the
footprint is correct. Three quarters of it is which wide edge wins an overlap,
which is a primitive-decomposition question and partly the driver's to answer,
not ours. The remaining quarter needs generated line geometry, for the centre
snap and the sub-pixel dashes both — the change `line-width.md` already priced
and declined.

> Superseded on 2026-09-13 for the centre, which turns out to be a constant and
> to need no geometry at all. The sub-pixel dashes still do. See below.

---

# 2026-09-13: it is not a snap, and it costs one line

Everything above about the *width* and the *footprint* stands. The section on
the centre does not, and the way it went wrong is the same shape as the stale
capture set at the top of this file: **a model was fitted where it could not be
falsified, and then relied on.**

## The mistake

The centre was read off one segment: the quad strip's left edge, vertical at
screen x = 160.0. Golden lights the columns of a line centred at 160.5 there
and we light those of one centred at 160.0, 18/18 widths each. That is solid.

The conclusion drawn from it — *silicon snaps the line's centre to the nearest
pixel centre* — is not, because **160.0 is an integer**. A snap to the nearest
pixel centre and a constant shift of +0.5 along x both land on 160.5 there.
The two models are indistinguishable on that segment at every width, and the
segment was the only evidence. The write-up went further and said no constant
translate could reproduce it, illustrating with 160.3 → 160.5 and 160.7 →
160.5 — numbers that appear nowhere in the test. **The illustration was of the
model, not of a measurement**, and it carried the load of a measurement: it is
what put "needs generated line geometry" on the recommendation.

## Two segments that do falsify it

**A vertical edge on a half-integer x.** The triangle fan's hub-to-v4 edge runs
from screen (318.5, 253) to (318.5, 176.5). A half-integer is *already a pixel
centre*, so a snap leaves it exactly where it is while a constant +0.5 moves it
to 319.0 — and the parity of the disagreeing widths flips with it, even widths
differing instead of odd. Only the run's left boundary is usable (other fan
edges merge into it from the right) and only up to width 9 (past that the run
grows back into the hub), which is enough:

| width | golden lo | ours lo | cx=318.5 | cx=319.0 | |
|---:|---:|---:|---:|---:|---|
| 3 | 317 | 317 | 317 | 317 | |
| 4 | 317 | 316 | 316 | 317 | discriminating |
| 5 | 316 | 316 | 316 | 316 | |
| 6 | 316 | 315 | 315 | 316 | discriminating |
| 7 | 315 | 315 | 315 | 315 | |
| 8 | 315 | 314 | 314 | 315 | discriminating |
| 9 | 314 | 314 | 314 | 314 | |

Golden fits a centre in **(318.500, 319.000]**, 7/7. Ours fits **(318.000,
318.500]**, 7/7. Silicon moved a line that was already on a pixel centre.
**It is a translate, and the snap is dead.**

**A near-horizontal edge.** The polygon's closing edge runs from screen
(477, 278.5) to (378, 280); column 399 crosses it at y = 279.674, far from
either end. Over sixteen widths golden and our own output light **exactly the
same rows, 16/16**, both fitting a centre in (279.500, 280.000]. A +0.5 in y
would move every odd width by a row. A snap to the nearest pixel centre would
move width 4 by one — the snapped centre 279.5 lights rows 277–280 where the
goldens light 278–281. The goldens do neither.

So the rule is **+0.5 in x, nothing in y**, and both halves are measured rather
than assumed by symmetry. `docs/testing/line_footprint.py --edge` now reports
all three segments and fits the centre as an *interval intersected over
widths*, because a single width pins the centre only to within a whole pixel
— which is the resolution at which the original mistake becomes invisible.

## Why the asymmetry is not suspicious

It reads oddly until you notice that `Fill_0000.0` cannot see it either. A
filled quad whose boundary sits on an integer x lights the same columns whether
its edge is at 160.0 or 160.5: the fill rule takes pixel centres in `[left,
right)`, and both boundaries move from lying *between* centres to lying *on*
one of them without changing which centres are enclosed. So a half-pixel
convention difference in x is invisible to every axis-aligned fill in the
corpus, and the coverage-exact `Fill_0000.0` is evidence about the fill rule,
not about the vertex path's x convention. Which of "the line rasteriser biases
x" and "the whole pipeline is half a pixel out in x and only lines can tell"
is true is **not decided by this suite**, and the fix is written for the
former: gated on the pipeline rasterising lines, so nothing else can move.

## The fix

`VkViewport.x = 0.5 * surface_scale_factor` on pipelines that rasterise lines,
in `pgraph_vk_line_centre_bias_x()` in `vk/draw.c`. Not the vertex position:
the vertex path is shared with fills, `glsl/vsh.c` would move every draw, and
the viewport is *dynamic* state, which matters because
`VK_EXT_extended_dynamic_state3` makes the static rasteriser state dead on
Turnip. The bias reads `geom.polygon_front_mode` and `geom.primitive_mode` —
the same two fields the pipeline's `polygonMode` and topology come from — so it
is a pure function of the pipeline key, needs no key of its own, and cannot go
stale: any draw crossing into or out of line rasterisation necessarily changes
the pipeline, and both places that program a viewport re-issue it on a bind.

The GL renderer cannot carry it. `glViewport` takes integers.

## What this does not touch

The 76.3% edge-priority class sits **on top of** this one and will not move
with it — the classes overlap and cannot be subtracted. Nor do the sixteen
sub-2px widths, which the device's own `lineWidthRange[0] = 1.0` and
`lineWidthGranularity = 0.5` decide, and which still need generated geometry
for silicon's dashes. And `LINE_LOOP` still carries 9,696 structural channels
at width 63 with an order we already match, so `Line_0016.0`'s `LineLoop`
cluster remains the clean probe for whatever is left after both.

---

# The arm, and the result: the fix works and is wrong

Measured the same day. Arm A `ea879bd647`, arm B `c85391e29d`, 221 captures
over `Line width` and `3D primitive`, Retroid Pocket Nova, APKs `cade6d3c9b13`
and `4a7a0f4f7c6d`. Prediction `docs/testing/predictions/line-centre-half-pixel-x.json`,
registered and bound at queue time.

    differing   4,580,105 -> 4,974,132   (+394,027)
    structural  1,009,484 -> 1,391,382   (+381,898)

| band | n | delta | better / worse |
|---|---:|---:|---|
| `Line_width` odd widths ≥ 3 | 25 | **+214,451** | 0 / 25 |
| `Line_width` even widths ≥ 3 | 16 | **+146,727** | 0 / 16 |
| `Line_width` widths < 2 | 15 | +26,576 | 0 / 15 |
| `3D primitive` line primitives | 48 | +2,572 | 28 / 12 |
| `3D primitive` fill primitives | 112 | **0** | 0 / 0 |

**Nothing improved.** Not one band, and not the odd widths the change was
aimed at.

## And every falsifier passed

This is the part worth keeping. All three registered fitted-centre checks land
exactly:

* quad strip's left edge: ours moves from `(159.500, 160.000]` to
  `(160.000, 160.500]`, matching the golden **18/18**;
* the fan's half-integer edge: ours moves from `(318.000, 318.500]` to
  `(318.500, 319.000]`, **7/7**;
* the near-horizontal edge: unchanged, **16/16**.

The seven odd widths each moved one column right onto the golden's run and the
eleven even ones held, as registered. The bias reached the rasteriser, at the
right magnitude, on the right axis, on exactly the pipelines intended.

**So the arm did not fail to deliver a change; it refuted a model.** That
distinction is the whole value of having written the falsifier as a fitted
centre rather than a pixel total. A pixel total would have said "worse" and
left it ambiguous whether the code was inert, mis-scoped, or wrong-headed.
The centre fit says: delivered exactly, and wrong anyway.

## What is actually true, then

**The +0.5 in x is real on a steep edge and is not a global translate.** Three
independent vertical edges say golden = ours + 0.5 in x; the near-horizontal
edge says golden = ours in y; and moving everything by +0.5 in x makes the
whole suite worse, because most of the ink is on edges that are neither.

That combination has a name. A rule that biases the **minor** axis by half a
pixel, with the sign depending on which axis is major, looks like +0.5 in x on
a y-major edge and like nothing on an x-major one — and it is precisely the
asymmetry in the GL wide-line rule, where an even-width column runs from
−(w/2 − 1) to +w/2 on one major axis and the mirror of that on the other.
Vulkan exposes it as `VK_LINE_RASTERIZATION_MODE_BRESENHAM_EXT`. **No viewport
offset can express it**, because a viewport does not know which axis is major.

Two further measurements bear on that, and they do not agree with each other,
so neither is a conclusion:

* **Width 1 says we are already right.** In `3D primitive`, whose lines are all
  at the default 1.0, our ink matches the golden at IoU 0.958 while shifting it
  a column drops that to 0.605. `Line_0001.0` is 1,899 differing of ~6,500 ink,
  most of it off-by-one. Yet on the quad strip's vertical edge at width 1.0 the
  golden lights column 160 and we light 159. Both are true if width 1 differs
  only at an exact tie, which is what a Bresenham-style nearest-pixel rule
  gives and a +0.5 translate does not.
* **Diagonals say the golden is *wider*, not foreshortened.** On the isolated
  QUADS edge from local (58.5, 425.4) to (12.75, 407.5) — x-major, cos θ =
  0.9313 — the golden's column height runs 10, 14, 19, 29 for widths 8, 12, 16,
  24 where ours runs 9, 13, 17, 26 and a perpendicular rectangle predicts 8.6,
  12.9, 17.2, 25.8. Bresenham predicts exactly 8, 12, 16, 24, so it predicts the
  wrong direction. The quad is only 60 × 85, so at those widths its four edges
  overlap and the measurement may not be of one edge; it is recorded as an
  open question, not as a refutation.

## What not to do next

Not another viewport constant, in either axis or any sign: the axis-dependence
is the whole problem and the viewport cannot see it. Whoever picks this up
should settle the Bresenham question first, and it is settleable cheaply —
`VK_EXT_line_rasterization`'s `bresenhamLines` boolean is one device-log line
on the Nova, and one arm with `lineRasterizationMode` set says the rest. If
Turnip does not offer it, the answer is generated line geometry, which is the
same conclusion this file reached before, reached now for a reason that has
been tested.

## The guard list, including the one that was wrong

114 of 116 registered must-not-move checks held: all 112 fill-mode captures in
`3D primitive` at exactly zero delta, and `Line_0000.0` still pixel-exact. The
gate — bias only a pipeline whose rewritten primitive is `LINES`, or whose
primitive is `TRIANGLES` under `POLY_MODE_LINE` — leaked nothing.

Two failed, and both were the guard's fault rather than the code's:
`Fill_0001.0` and `Fill_0032.0`. `Fill` in this suite only means
`NV097_SET_FRONT_POLYGON_MODE` is `FILL`; `LineWidthTests::Draw()` issues
`PRIMITIVE_LINE_LOOP` unconditionally, and the polygon mode does not reach a
line primitive. Those captures contain real lines and had no business on the
list. `Fill_0000.0`, where width 0 drops the loop, is the one that held — and
is the only one of the three that was ever a fill-only capture.

Writing the list is still what caught the serious bug. `Line_0000.0` was on it
because at width 0 the lines are dropped and the test's sixteen points are the
whole draw; checking the gate against that entry is what revealed that the
first draft biased points as well, since the test sets the fill mode before
drawing them. That build never reached the device.

---

# 2026-09-13: Bresenham is measured, and it is wrong

The section above ends by saying the Bresenham question is settleable cheaply
and should be settled first. It has been. Arms `0499184e2d` and `8f84f5a8ab`,
APKs `553cfffc73d3` and `e6ee765a328f`, 307 captures over `Line width`,
`3D primitive`, `Point size`, `Point params` and `Texture format`. Prediction
`docs/testing/predictions/line-bresenham.json`, registered and content-hashed
at queue time.

The capability is real. From the device, on both handhelds:

    line raster: ext=1 rect=1 bresenham=1 smooth=0
                 stipple(rect=0 bres=0 smooth=0)
                 width[1.000,127.500] gran=0.500 wide=1 strictLines=1

so `VK_EXT_line_rasterization` was added, `bresenhamLines` enabled, and
`VkPipelineRasterizationLineStateCreateInfoEXT` with
`lineRasterizationMode = VK_LINE_RASTERIZATION_MODE_BRESENHAM_EXT` chained onto
the rasterisation state of line-drawing pipelines only.

## The result

    differing   4,755,368 -> 5,548,838   (+793,470)
    structural  1,000,125 -> 3,671,805

| band | n | delta | better / worse |
|---|---:|---:|---|
| `Line_width` `Line_*` w >= 3 | 41 | **+783,991** | 0 / 41 |
| `Line_width` `Line_*` w < 2 | 15 | +3,963 | 6 / 9 |
| `Line_width` `Fill_*` | 3 | +6,145 | 0 / 2 |
| `3D primitive` line primitives | 48 | −1,024 | 12 / 12 |
| `3D primitive` fill primitives | 112 | **0** | 0 / 0 |
| `Point_size` | 21 | **0** | 0 / 0 |
| `Point_params` | 25 | **0** | 0 / 0 |
| `Texture_format` | 40 | **0** | 0 / 0 |

Monotonic in width: `Line_0016.0` +14,124, `Line_0032.0` +24,257,
`Line_0048.0` +31,786, `Line_0063.7` +38,095.

## It was not a plumbing failure, and this time that is measured rather than argued

118 of 118 must-not-move entries held at **exactly zero delta** — every one of
the 112 fill-mode `3D primitive` captures, all 21 `Point_size`, all 25
`Point_params`, all 40 `Texture_format`, `Line_0000.0` still pixel-exact at 0,
and `Fill_0000.0` byte-identical. The validation layer logged nothing. The
device log said `-> bresenham ENABLED`.

Two things that cost the last two arms are worth recording as *fixed*:

* The gate requires a **triangle** topology before `polygonMode LINE` counts.
  The viewport arm's first draft read `POLY_MODE_LINE || primitive_mode ==
  LINES`, which catches the sixteen POINTS the test draws under a LINE fill
  mode; `Line_0000.0` is the capture that says so and it held here.
* `Fill_0001.0` and `Fill_0032.0` were **left off** the list this time, because
  `LineWidthTests::Draw()` issues `PRIMITIVE_LINE_LOOP` unconditionally and
  those captures contain real lines. They moved, as expected (+121 and +6,024),
  and cost no false alarm.

## What it actually measured

**The fitted centre did not move at all.** All three probe edges read
identically on both arms:

| segment | golden | arm A | arm B |
|---|---|---|---|
| quad strip, x = 160.0 | (160.000, 160.500] 18/18 | (159.500, 160.000] | **(159.500, 160.000]** |
| fan, x = 318.5 | (318.500, 319.000] 7/7 | (318.000, 318.500] | **(318.000, 318.500]** |
| polygon, col 399 | (279.500, 280.000] 16/16 | same, 16/16 | **same, 16/16** |

Which is obvious in hindsight and was not obvious in advance: Bresenham
replicates fragments along the **minor axis**, and for an axis-aligned line the
minor axis is exactly where the rectangle already put them. The half pixel the
goldens want on a steep edge is not what this mode changes. **Leg 1 of the
prediction failed outright**, and leg 2 held vacuously.

**What it changed was diagonals, and it changed them the wrong way.** Column
height of the isolated QUADS edge — local (58.5, 425.4) to (12.75, 407.5),
x-major, cos θ = 0.9312 — median over columns 186..205:

| width | golden | arm A | arm B | perp rect, w/cos θ | Bresenham, w |
|---:|---:|---:|---:|---:|---:|
| 8 | 10 | 9 | **8** | 8.6 | 8 |
| 12 | 14 | 13 | **12** | 12.9 | 12 |
| 16 | 19 | 17 | **16** | 17.2 | 16 |
| 24 | 28 | 26 | **24** | 25.8 | 24 |

and the butt-rectangle fit on that primitive degrades from **0.03–0.20%** of
its ink to **2.24–4.96%**, the error now almost entirely pixels the rectangle
has and we lack. So Bresenham *is* applied, and confirmed at the **mechanism**
rather than by a total: the column height is exactly ⌈w⌉, which the Bresenham
rule predicts to the pixel and nothing else does.

## This resolves the recorded disagreement, against Bresenham

The section above left two measurements open and disagreeing. **The QUADS half
wins.** Silicon is *wider* than a perpendicular rectangle on a diagonal;
Bresenham is *narrower*; the perpendicular rectangle we already draw sits
between them and is the closest of the three.

The width-1 half is not an instrument here and should stop being quoted as one.
The 48 line-primitive captures in `3D primitive` moved **−1,024 in total, 12
better and 12 worse** — at width 1 the two modes barely differ, so IoU 0.958
neither confirms nor refutes anything about the mode.

And the golden heights were confirmed independently before either arm ran:
10 / 14 / 19 / 28–29, reproducing the figures recorded from the earlier pass
from a fresh measurement of the goldens. The w = 24 column is the noisy one
(27, 28 and 29 all appear across the twenty columns), which is the edge-overlap
caveat the earlier pass attached to it, honoured.

## The mode knob is exhausted

`VK_EXT_line_rasterization` offers three modes and this device settles all
three:

* `smoothLines = 0` — **#36 stays closed**, on a capability line rather than an
  argument.
* `stippledBresenhamLines = 0` — **#33 gains nothing** from Bresenham here.
* `RECTANGULAR` is what we already draw.
* `BRESENHAM` is measured wrong, by 794k pixels and 0 of 41 captures.

There is no fourth value. Nobody should spend another arm on
`lineRasterizationMode`.

## The next hypothesis, phrased as one

Silicon lights roughly **one pixel more on each minor-axis boundary of a
diagonal** wide line than a centre-in-rectangle rule does, and nothing extra on
an axis-aligned one. The evidence is three edges at three angles:

| edge | cos θ | golden's extent |
|---|---:|---|
| quad strip, vertical | 0 (y-major) | exactly w columns, 18/18 |
| polygon closing, near horizontal | 0.99989 | exactly w rows, 16/16 |
| QUADS, 21.4° | 0.9312 | w/cos θ + 1 to + 2 |

That is the shape of a **coverage** rule — any pixel the rectangle touches —
rather than a centre rule. It is invisible on every axis-aligned edge in the
corpus, which is why the footprint fit reads 0.03–0.20% on the interior while
18.7% of the residual is golden-only ink at the boundary. It also cannot be
expressed as a rasterisation mode, so it needs the generated line geometry this
file has now priced and declined three times — reached the third time for a
reason that has been tested rather than argued.

Do not attack it before the 76.3% it sits underneath. See below.

## What is still the ranking, unchanged by this arm

Arm A reproduces the residual split **to the digit** on a different binary from
the one that first measured it:

    structural channels 1,000,125  over  342,679 structural pixels
      golden-only ink (we under-cover)    63,983   18.7%
      ours-only ink   (we over-cover)     17,062    5.0%
      colour on ink both agree about     261,634   76.3%

so the "date the captures against the commit" lesson at the top of this file is
satisfied here by accident as well as by design: the figures are stable, and
every number above is a B − A delta on a fresh pair regardless.

**76.3% of what is left is edge priority** — both renderers ink the pixel and
disagree about which of several overlapping wide edges is on top — and it is a
primitive-decomposition question, partly the driver's to answer. That is the
next thing, and it is a different issue's shape from anything this arm touched.

---

# 2026-09-13: both remaining rules, read off the goldens with no device

The two things this file left open are the two things this section settles, and
neither needed a build, a device or an arm. `Line width` disables the depth
test and blends opaque palette entries, so at a pixel covered by several wide
edges the golden's colour **names the edge silicon drew last**. That turns the
76.3% edge-priority class from a device question into a pixel-reading exercise,
and the same scene supplies a proper cos θ sweep for the extent hypothesis.

Tool: `docs/testing/line_priority.py` (`--order`, `--rules`, `--extent`,
`--reconstruct`). Predictions registered and content-hashed before the
held-out numbers were computed:
`docs/testing/predictions/line-edge-priority-order.json` and
`line-edge-priority-reconstruct.json`.

## Two conventions had to be measured first, and one of them was a trap

**`SET_DIFFUSE` takes the suite's `kPalette` words as ABGR, not ARGB.** All
sixteen POINTS read back with R and B exchanged — palette index 0 renders as
entry 2, 1 as 1, 2 as 0, 3 as 4, 4 as 3, and 5, 6, 7 fixed, which is exactly
`swap(R,B)` applied to that palette. Read the words as ARGB and every colour
names the wrong edge; the quad at the bottom left comes out with vertex 0 blue
and vertex 2 red, and the resulting "priority rule" is unintelligible rather
than obviously wrong. This is the kind of thing that costs an afternoon and
looks like a hardware mystery.

**A pixel's colour on a wide edge is `lerp(c_a, c_b, t)` with `t` the
projection of the pixel centre onto the segment.** 97.7% of solo-covered
pixels are within 4/255 of that at w = 16, so the colour model is not the
uncertainty in anything below.

And one structural question had to be answered before any ordering could be:
**the tessellation's internal edges are not drawn.** At width 1 the quad at the
bottom left has no diagonal, the polygon has no fan spokes, and the quad strip
*does* draw the shared rail between its two quads. The triangle fan draws every
hub spoke. That is the same decomposition `prim_rewrite.c` already produces, so
the disagreement was never about *which* edges exist. `Edge flag`'s two
captures are byte-identical in these regions, so `SET_EDGE_FLAG` changes
nothing on this hardware and adds no information.

## The priority rule

**Last-drawn wins**, and silicon's submission order for a polygon rasterised in
`POLY_MODE_LINE` is one sentence:

> Triangulate exactly as the fill path does, drop the tessellation's internal
> edges, and for each triangle `(a, b, c)` emit **the edge opposite a, then the
> edge opposite b, then the edge opposite c** — that is `(b,c)`, then `(c,a)`,
> then `(a,b)`.

Line primitives (`LINES`, `LINE_STRIP`, `LINE_LOOP`) are submission order,
which we already match. The rule is only about the polygon-mode-LINE path.

One sentence, four different per-primitive orders, because the tessellations
differ — and all four are what the goldens show:

| primitive | tessellation | silicon's order |
|---|---|---|
| `TRIANGLES` / `STRIP` / `FAN` | — | `(b,c)`, `(c,a)`, `(a,b)` per triangle |
| `QUADS` | v0-v2 diagonal | `(v1,v2)`, `(v0,v1)`, `(v2,v3)`, `(v3,v0)` |
| `QUAD_STRIP` | v1-v2 diagonal | `(v2,v0)`, `(v0,v1)`, `(v1,v3)`, `(v3,v2)` per quad |
| `POLYGON` | fan from v0 | `(v1,v2)`, `(v0,v1)`, `(v2,v3)`, …, `(vn-1,v0)` |

That the same sentence yields a rotation for the quad strip, a swap of the
first two edges for `QUADS` and `POLYGON`, and something like a reversal for a
bare triangle is the reason to believe it is a mechanism rather than four
fitted permutations. Nothing was tuned per primitive.

### The decisive pixels, and what each rival predicts instead

A *decisive* pixel is deep inside two or more rectangles under both candidate
x-conventions, inside no third even marginally, with candidate colours pairwise
at least 48/255 apart and the golden within 10/255 of exactly one of them. Its
answer is therefore decided by the priority rule and by nothing else — not by
the half-pixel centre question this file has already been wrong about twice,
and not by the boundary. 203,023 such pixels over the 45 captures at w ≥ 8.

**A cycle would have killed every ordering rule outright** and forced a
geometric one. There is none: all 61 reliable relations are acyclic, in all six
primitives, and the winner of a pair never depends on which pixel of the
overlap you read (minority share under 2.1% on the pairs that decide anything).

**The within-triangle order is pinned to one of six permutations, twice,
independently.** Triangle `(v3,v4,v5)` gives the complete order `(v4,v5)` <
`(v5,v3)` < `(v3,v4)` at minorities 1.64%, 0.00% and 1.05% — a total order on
three edges, so it excludes the other five permutations on its own. Triangle
`(v0,v1,v2)` gives the same permutation, `(v1,v2)` < `(v2,v0)` < `(v0,v1)`, at
4.96%, 0.00% and 7.63% — its weakest relation sits just inside the reliability
cut, so it is corroboration rather than a second clean pin.

**The quad strip is what separates the two surviving schemes.** "Opposite a, b,
c" and "opposite a, c, b" agree on `QUADS`, `POLYGON`, `TRIANGLE_FAN` and the
line loop, and they disagree here: 100.00% against 79.46%.

**Our current order is refuted, not merely beaten.** It predicts `(v1,v2)`
beats `(v0,v1)` in a triangle, `(v1,v2)` beats `(v0,v1)` in `QUADS`, and
`(v2,v0)` beats `(v0,v1)` in the quad strip. The goldens say the opposite in
all three, on thousands of pixels each.

**Geometric rules are excluded a priori as well as by score.** The decisive
pixels are *fully inside* every candidate rectangle, so "the edge with the
greater coverage at that pixel" has no quantity to compare — coverage is 1 for
all of them, and that rival cannot be stated on this population at all. Every
geometric rule sits between 41% and 48%, which is roughly chance for two to
four candidates.

The rival scores are in the table further down, once the nine void captures
this corpus contains have been identified and removed; the short version is
that the derived rule is correct on **every one** of 225,558 decisive pixels
and the nearest rival on 93.75%.

## The extent rule, and the coverage hypothesis is dead

The hypothesis this file registered — a **coverage** rule on a diagonal's
minor-axis boundary — rested on three edges at three angles with the 21° one
contaminated by its neighbours. Swept properly it dies, and something
parameter-free replaces it.

A *clean* sample is a scanline cut across one edge's rectangle where no other
edge's rectangle comes within 4 px, the cut is at least w from either butt cap,
and the golden's lit run is bounded by background. 9,611 of them, 33 edges,
cos θ from 0.7119 to 1.0000, widths 6 to 48.

> **minor-axis extent = w · (1 + tan θ / 2) = w · (max + min ⁄ 2) / max**
> with max, min the larger and smaller of |dx|, |dy|.

which is the perpendicular rectangle with its half-width scaled by
`(max + min/2) / hypot(max, min)`: **silicon computes the segment length with
the classic alpha-max-plus-beta-min approximation, β = ½**, and that
over-estimates it by up to 6.07% at 45°. "Silicon is wider than a perpendicular
rectangle" is exactly that, at every angle.

| model | in {floor, ceil} over 9,611 | on the 92 samples where it and the rectangle differ by ≥ 2px |
|---|---:|---:|
| **w(1 + tan θ/2)** | **100.00%** | **100.00%** |
| w/cos θ — perpendicular rectangle | 76.94% | 0.00% |
| w/cos θ + tan θ + 1 — coverage | 51.25% | 56.52% |
| w/cos²θ | 73.02% | — |
| w(1 + tan θ) | 55.17% | — |
| w — Bresenham | 40.60% | 0.00% |

**Coverage is refuted where it is cheapest to check, not on a curve fit.** At
cos θ = 1.0000 exactly — the quad strip's two vertical rails, 1,447 samples
over fifteen widths with *zero variance* — the extent is exactly w. Any "the
rectangle touches the pixel square" rule gives w+1 for at least one parity.

And it reproduces the column heights this file has quoted three times:
golden 10 / 14 / 19 / 28–29 at widths 8 / 12 / 16 / 24 on the isolated QUADS
diagonal, predicted 9.57 / 14.35 / 19.13 / 28.70, where the perpendicular
rectangle predicts 8.6 / 12.9 / 17.2 / 25.8 — which is our own 9 / 13 / 17 / 26.

## The nine captures that are not measurements, and how they were found

`Line_0064.0` – `Line_0064.7` and `Line_FFFFFFFF` have goldens whose **ink mask
is byte-identical to `Line_0001.0`'s** — 3,609 lit pixels, zero pixels of
difference in placement. The width register holds nine bits of eighths, 64.0 is
512 and does not fit, and `4ed3a55e` already recorded that a value which does
not fit leaves the width alone, so hardware drew all nine at the 1.0 the suite
restores between tests. Every model in this file draws them at 64.

They are therefore **void captures, not measurements**, and the criterion that
excludes them is a property of the goldens — an ink mask identical to a
different capture's — established before any score, applying to exactly the set
whose register value overflows nine bits, and stated once rather than once per
capture. That distinction matters here because this project has twice been
burned by an exclusion reason chosen after seeing a result.

They were still included in the first pass, and the correction is the whole
difference between "the best rule" and "the rule":

| decisive-pixel score, derived order | with the nine void captures | without |
|---|---:|---:|
| perpendicular-rectangle footprint | 98.73% of 203,023 | 99.93% of 198,880 |
| derived-extent footprint | 98.97% of 229,648 | **100.00% of 225,558** |

Read down the second column and the two findings confirm each other exactly:
dropping the void captures leaves **149** wrong pixels out of 198,880, and
supplying the candidate footprints from the derived *extent* rule removes all
149. **The priority rule becomes exact only when the extent rule builds the
candidates**, which is what leg 3 was trying to ask and asked with the wrong
threshold on the wrong corpus.

**100.00%.** Not 225,557 of 225,558 — every decisive pixel, and 100.00% in each
of the eleven candidate-set classes separately (`Tri` 52,411, `QStrip` 40,139,
`LLoop` 35,571, `Quad` 26,549, `QStrip/TFan` 24,009, `Poly` 19,355,
`Poly/TFan` 13,764, `TFan` 11,636, `LLoop/Tri` 1,724, `Poly/Tri` 272,
`LLoop/TFan` 128). The nearest rival is 93.75%, our own order 78.51%, and every
geometric rule between 41% and 48%.

That is the shape #59's replication rule has: not a rule that scores better,
but **the only rule consistent with the whole decisive set**.

| rule, widths 8–63.875, derived-extent footprint | correct of 225,558 |
|---|---:|
| **opposite a, b, c (derived)** | **100.00%** |
| opposite a, c, b | 93.75% |
| `(c,a)`, `(b,c)`, `(a,b)` | 81.49% |
| `(a,b)`, `(b,c)`, `(c,a)` | 79.17% |
| **ours today** | **78.51%** |
| `(c,a)`, `(a,b)`, `(b,c)` | 64.31% |
| `(a,b)`, `(c,a)`, `(b,c)` | 60.66% |
| nearest vertex | 47.42% |
| farthest centre | 46.45% |
| longest edge | 45.13% |
| nearest centre | 43.44% |
| shortest edge | 41.07% |
| first-submitted wins | 30.92% |

It also **retro-diagnoses leg 3 completely**. That leg predicted the
derived-extent footprint would lift the score to ≥ 99.3% and lift it on every
block; it reached 98.97% and fell on one block, and it FAILED as registered.
The residual it was aiming at was not a second mechanism and not the footprint
— it was nine captures that are not measurements. The leg still failed, the
registration still stands as written, and the reason is recorded rather than
the threshold moved.

And the 149 are **all in the line loop** — `LLoop` reads 99.53% of 31,548 with
the perpendicular footprint and 100.00% with the derived one, while every other
class is already 100.00% under both. So `LINE_LOOP`'s residual, which this file
recorded twice as "some other cause" and as its least certain point, **is the
extent rule**. That is exactly what should have been expected of a primitive
whose order we already match: its wide edges are in the right sequence and the
wrong shape.

## The selection-free score, which is the measurement a fit could fail

`--rules` reads 0.1% of the ink, and it chooses that 0.1% partly by asking
whether the golden matches any candidate at all. A rule right about those and
wrong about the rest would look perfect. `--reconstruct` removes every
selection: it renders the whole scene with a painter's algorithm under each of
the eight order schemes crossed with both extent rules and scores **every
interior ink pixel** — no colour-separation threshold, no multi-coverage
requirement, no "the golden must match something". Excluded only: the text
overlay, a 4 px neighbourhood of the sixteen POINTS (not modelled), and a
1.5 px shell inside each footprint boundary, because the half-pixel convention
and the floor/ceil phase are deliberately not part of either rule.

48 captures, widths 3 – 63.875, **1,741,370 scored pixels**:

| order | extent | within 16/255 | within 4/255 |
|---|---|---:|---:|
| **opposite a,b,c** | **hypot-approx** | **99.31%** | **99.24%** |
| opposite a,c,b | hypot-approx | 96.02% | 95.77% |
| opposite a,b,c | perpendicular | 95.26% | 95.15% |
| `(c,a)(b,c)(a,b)` | hypot-approx | 93.62% | 93.16% |
| opposite a,c,b | perpendicular | 92.22% | 91.93% |
| `(c,a)(b,c)(a,b)` | perpendicular | 89.92% | 89.41% |
| `(a,b)(b,c)(c,a)` | hypot-approx | 89.38% | 88.62% |
| **ours** | hypot-approx | 88.93% | 88.14% |
| `(a,b)(b,c)(c,a)` | perpendicular | 85.85% | 85.06% |
| `(c,a)(a,b)(b,c)` | hypot-approx | 85.57% | 84.61% |
| **ours** | **perpendicular** | **85.43%** | **84.61%** |
| `(a,b)(c,a)(b,c)` | hypot-approx | 83.65% | 82.51% |
| `(c,a)(a,b)(b,c)` | perpendicular | 82.37% | 81.37% |
| `(a,b)(c,a)(b,c)` | perpendicular | 80.49% | 79.32% |
| first-submitted | hypot-approx | 58.86% | 56.96% |
| first-submitted | perpendicular | 57.96% | 56.01% |

**The extent rule beats the perpendicular rectangle for all eight order
schemes**, which is eight separate comparisons at fixed order and is what makes
the extent finding independent of the priority finding rather than entangled
with it. And the two together are 13.9 points above what this emulator's order
and footprint give.

## The held-out result, including the leg that was void and the two that failed

Fit on w ≥ 8 (order) and w ≥ 6 (extent). `Line_0003.0` – `Line_0007.0` were
skipped by the collector's `--min-width` cut and no number from them appears in
the derivation.

**Leg 1 — held-out priority: VOID.** Those five captures yield **nine**
decisive pixels between them, against the 200 the registration named as the
validity floor *before* the count was known. At widths 3–7 the wide edges
barely overlap and the 3 px margin removes what core is left; all eight order
schemes score 100% on nine pixels, which is not evidence. **The low end of
`Line width` cannot test an edge-priority rule at all** — a held-out priority
measurement needs a capture this suite does not contain.

**Leg 2 — held-out extent: PASS, and non-discriminating exactly as
registered.** 100.0% in-band over 4,445 clean samples, 39 edges, widths 3–5 —
and the perpendicular rectangle manages 98.16% there, because at those widths
the two differ by well under a pixel. The registration said in advance this leg
could only catch a blunder. It caught none.

**Leg 3 — the two rules explaining each other: FAIL**, cause found and recorded
above: nine void captures, not a second mechanism.

**Leg 5a — held-out reconstruction: PASS.** `opposite a,b,c` + hypot-approx is
top-ranked on the five captures at widths 3–7 and scores 99.28% within 16/255
of 35,725 pixels. As the registration warned, the spread is small — it ties
`opposite a,c,b` at 99.28% and leads it only on the tighter 4/255 band (99.07%
against 98.91%) — so **it discriminates against our order (98.11%) and not
between the two opposite-vertex schemes**.

**Leg 5b — whole-corpus reconstruction: three of four clauses PASS, and clause
(2) FAILS as registered.** Registered as `--min-width 3`, which includes the
eight `Line_0064.*` captures; those score ~1.5% for *every* combination and
make up 27.8% of the scored population, so the registered form reads 72.07%
against a 95% floor. Top-ranked ✓, gap over ours+perp 10.2 points ✓,
hypot-beats-perp on all eight schemes ✓. On the 48 real captures it is 99.31%.
The flaw is in my registration, not in the rule, and the leg is reported as
failed rather than re-scoped.

## What is still not explained, and it is no longer LINE_LOOP

The decisive pixels are exhausted — 225,558 of 225,558 — so what remains is
outside that population: pixels where the candidate colours are too close
together to decide anything, or where the golden matches no candidate. The
selection-free score puts it at **0.69% of interior ink** (99.31% within
16/255), and it does not thin out with depth: requiring the pixel to be 3 px
inside the **winning** edge's own footprint leaves 0.42–0.50%, flat across
w = 16, 48 and 63. So it is neither a boundary effect nor a phase effect.

At w = 48, 357 such pixels. At most 21 of them name a different covering edge
(11 `LLoop#10` over `LLoop#11`, 10 `Tri#2` over `Tri#3`) — and those are not
decisive pixels, so they do not contradict the 100%. The rest match **no**
covering edge's colour at all: median best-candidate error 44/255, p90 148.

Square caps were the obvious candidate, because a handful of them sit exactly
where a `w/2` extension past a vertex would put that vertex's colour. Applied
everywhere it is catastrophic, which settles it:

| cap | interior ink within 16/255, w = 48 |
|---|---:|
| butt (derived) | **99.36%** |
| extended w/4 | 77.73% |
| square (w/2) | 64.29% |

That also **re-confirms the butt-cap finding on a metric that can see colour**,
not only coverage. The original cap-and-join fit was coverage-only on the
isolated QUADS primitive, where adding a join adds ink the golden lacks; this
one scores the colour at pixels that are already inked either way, which is a
different question and gives the same answer.

## A free corroboration: the fill path's tessellation diagonals

The derived order depends on *which* diagonal the fill path uses, and the
goldens therefore test it — from line-mode colour, which has nothing to do with
the fill measurements the comments in `prim_rewrite.c` rest on.

* `QUADS` on the **v0-v2** diagonal predicts `(v1,v2)`, `(v0,v1)`, `(v2,v3)`,
  `(v3,v0)`, which satisfies all five observed relations. On a v1-v3 diagonal
  the same rule predicts `(v3,v0)` first, and `(v3,v0)` beats `(v0,v1)` on
  5,780 pixels with a 0.00% minority. Excluded.
* `QUAD_STRIP` on the **v1-v2** diagonal predicts `(v2,v0)`, `(v0,v1)`,
  `(v1,v3)`, `(v3,v2)`, satisfying all four. On a v0-v3 diagonal it predicts
  `(v1,v3)` before `(v0,v1)`, and `(v1,v3)` beats `(v0,v1)` on 12,102 pixels.
  Excluded.

Both comments in `prim_rewrite.c` — "matches hardware quad tessellation" and
"matches hardware quad strip tessellation" — are now independently confirmed.

## Which blocks decide what, so nobody re-derives it from the wrong one

| block | pins the within-triangle order? | separates the derived rule from its nearest rival? | separates it from ours? |
|---|---|---|---|
| `Tri` (2 triangles) | **yes, uniquely** | yes, 100.00% vs 88.83% | yes, 57.63% |
| `QStrip` (2 quads) | no | **yes — the only block that does**, 100.00% vs 79.46% | yes, 75.74% |
| `Quad` | no | no (both 100.00%) | yes, 71.31% |
| `TFan` | no | no (both 100.00%) | yes, 73.20% |
| `Poly` | no | no (both 100.00%) | **no — ours also satisfies all four relations** |
| `LLoop` | n/a | no | no — submission order, already matched, and the one block whose score depends on the extent rule (99.53% -> 100.00%) |

Triangle 1 `(v3,v4,v5)` gives the complete order `(v4,v5)` < `(v5,v3)` <
`(v3,v4)` at minorities 1.64%, 0.00% and 1.05%; triangle 0 `(v0,v1,v2)` gives
`(v1,v2)` < `(v2,v0)` < `(v0,v1)` at 4.96%, 0.00% and 7.63% — the same
permutation, with its weakest relation just inside the reliability cut, so it
is corroboration rather than a second clean pin.

`Poly` deciding nothing is worth noticing: it is the one primitive where our
current order already satisfies every observed relation, so a change there is
motivated by the rule and not by a measurement of its own.

## The implied change, priced and not written

This lane claims no code. `prim_rewrite.c` is unclaimed by any stream; the
three small edits below are what the rule implies, and they want one arm.

**1. `rewrite_quads_line` — two lines swapped.**

```c
-        emit_line(r, v0, v1);
         emit_line(r, v1, v2);
+        emit_line(r, v0, v1);
         emit_line(r, v2, v3);
         emit_line(r, v3, v0);
```

**2. `rewrite_quad_strip_line` — rotated by one.**

```c
+        emit_line(r, v2, v0);
         emit_line(r, v0, v1);
         emit_line(r, v1, v3);
         emit_line(r, v3, v2);
-        emit_line(r, v2, v0);
```

**3. `rewrite_polygon_line` — the fan order.** Not simply "swap the first two":
for `count == 3` the order is `(v1,v2)`, `(v2,v0)`, `(v0,v1)`, which the loop
form gets right and a hand-unrolled swap does not.

```c
    /* Silicon fans the polygon from v0 and emits each triangle's edges
     * opposite a, then b, then c, dropping the internal spokes.  Derived
     * from the goldens; see docs/investigations/line-width-residual.md. */
    if (count == 2) {
        emit_line(r, idx_at(idx, 0, base), idx_at(idx, 1, base));
        return;
    }
    for (unsigned int t = 1; t + 1 < count; t++) {
        emit_line(r, idx_at(idx, t, base), idx_at(idx, t + 1, base));
        if (t == count - 2) {
            emit_line(r, idx_at(idx, count - 1, base), idx_at(idx, 0, base));
        }
        if (t == 1) {
            emit_line(r, idx_at(idx, 0, base), idx_at(idx, 1, base));
        }
    }
```

`max_output_indices` already budgets `input_count * 2` for a line-mode polygon,
which is what the fan form emits, so no allocation changes. Note the emission
count is unchanged in all three cases, so `mb_emitted`-style counters cannot
distinguish the arms — diff the captures.

**4. `TRIANGLES` / `TRIANGLE_STRIP` / `TRIANGLE_FAN` are not ours to order at
all today**, and that is a much larger change. They keep
`VK_POLYGON_MODE_LINE` (`vk/draw.c:1593`), so *Turnip* picks their edge order.
Matching silicon means rewriting them to explicit `LINES`:
`pgraph_prim_rewrite_get_output_mode`, `needs_rewrite`, `max_output_indices`
and three new `rewrite_*_line` functions, plus the GL path. Two warnings for
whoever does it:

* The `ours` column for `Tri` and `TFan` in every table above is **not a
  measurement of our renderer**. It is the score of the hypothesis "Turnip
  emits `(a,b)`, `(b,c)`, `(c,a)`", which is plausible and unverified. What the
  goldens establish is silicon's order, not our current one.
* `TRIANGLE_STRIP` is **inferred, not measured**. `Line width` draws no
  triangle strip, and a strip's `(a,b,c)` labelling alternates with winding, so
  which edge is "opposite a" alternates too. That case needs a capture this
  suite does not contain.

**5. The extent rule cannot be expressed in Vulkan at all.** It still needs the
generated line geometry this file has priced and declined three times — but it
now has a formula rather than a hypothesis: the perpendicular half-width is
`(w/2) * (max + min/2) / hypot(max, min)`. `emit_line` in `glsl/geom.c` already
computes the perpendicular; what it needs is that scale factor and a
pixel-to-clip scale in the geometry stage.

## What is deliberately not concluded

* **No pixel total is predicted for any of this.** The priority class and the
  extent class *overlap* — an overlap pixel can be wrong because the wrong edge
  won *and* because that edge's rectangle is the wrong size — so they cannot be
  added or subtracted, and 76.3% of the residual is not 76.3% of the achievable
  improvement.
* **The cap shape beyond "butt" is not claimed.** The minor-axis extent of a
  perpendicular rectangle of scaled width and of a minor-axis-extruded band of
  the same height are the same set for an infinite line; they differ only at
  the ends, and every extent sample is at least w from either cap.
* **The floor/ceil phase is not claimed.** `w(1 + tan θ/2)` is in-band on 100%
  of samples but only 82.6% are within 0.5 of it, and which side silicon takes
  at a given sub-pixel offset is the half-pixel question this file has already
  been wrong about twice.
* **Nothing about the sixteen sub-2px widths**, which `lineWidthRange[0] = 1.0`
  and `lineWidthGranularity = 0.5` decide on this device.
