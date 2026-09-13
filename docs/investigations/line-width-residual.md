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
