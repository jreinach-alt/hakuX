# lane.linecap13 -- #13's cap/join residual

Brief: give `emit_line()` in `glsl/geom.c` correct cap geometry against the
goldens' `Line_*` captures, without moving the exact-extent cuts already
proven.  Base: master @ `38385b79c1`, merged forward to `415dcc6997`.

## Why attempt 1 did not finish

It did the work and did not publish it.  At the end of attempt 1 the shader
change was committed locally as `7ce57a799b` and **never pushed**, PR #141 was
left in **draft** with `Prediction: pending` in its body, and this file still
showed three unticked boxes that the commit had in fact done.  From outside
that is indistinguishable from a lane that got nowhere: `board.sh:107`,
`fleet.py` and `fold.sh` all skip drafts, so the PR sat.

Attempt 1 also ended waiting on CI, which is not a thing to wait for here --
CI was green on `c208fdfb78` before the session ended.  The one real defect it
left behind is the next section.

## What attempt 2 changed

1. **`geom_dump/build/` was committed** -- two generated `.c` files carved out
   of the tree, three `.o`, and an 82 KB binary.  `make` regenerates all six
   from `glsl/geom.c`, so a stale copy on disk reads exactly like the
   generator's current output.  `psh_differ`, which `geom_dump` is modelled
   on, ignores its `build/` for that reason; `geom_dump` now does too.
   `make clean && make run` rebuilds from nothing and prints all six cases.
2. **`line_cap_phase.py --vs-goldens`** added -- the leg the arm is scored on
   (whole-capture ink mismatch of a capture set against the goldens).  It was
   uncommitted in the worktree at the end of attempt 1.
3. **The predicted device number was wrong, and is now measured.**  See below.

## Where the residual was

`line_extent_phase.py --reconstruct` reproduces on this base, unchanged:

    48 captures, 1967133 golden ink px, 14 pixel-exact in coverage
      derived          495 mismatched px = 0.0252%
      ours           59605 mismatched px = 3.0300%

493 of the 495 are ours-only and sit within `w/2 + 2` of a vertex.  The
residual is concentrated at even integer widths (56 -> 32 px, 58 -> 35,
60 -> 41, 62 -> 45) against odd ones (57 -> 11, 59 -> 14, 61 -> 14, 63 -> 17),
which is the first sign that a *tie* rather than a shape is at stake.

## What the goldens say the cap is

Read off `docs/testing/line_cap_phase.py --anatomy` / `--corners`, and
confirmed pixel by pixel on four corners with `line_cap_map.py`.

The extent band and the perpendicular butt cap are both right.  What is
missing is a third constraint, and it is axis-aligned in the MINOR axis: the
footprint never reaches further, on the minor axis, than the endpoints' own
minor coordinates extended by **w/2** -- the line width, not the widened
extent `E` -- rounded OUTWARD to whole pixel indices:

    minor index i is lit only if   floor(m_min - w/2) <= i <= ceil(m_max + w/2)

with `m_min`/`m_max` the smaller/larger of the two endpoints' minor
coordinates on the same 1/16 grid the extent rule already uses.

It bites only at the two tips of the parallelogram, which is exactly where
the residual was: inside the segment the `E`-band and the perpendicular slab
are both tighter, so the constraint changes nothing there.

### The four corners it was read from (Line_0063.7, w = 63.875, w/2 = 31.9375)

| edge | side | endpoint minor | golden's outermost lit index | `floor`/`ceil` of m -+ w/2 |
|---|---|---:|---:|---:|
| Quad0  | low  | 388.0 | 356 | `floor(356.0625) = 356` |
| Quad3  | low  | 160.0 | 128 | `floor(128.0625) = 128` |
| LLoop4 | low  | 287.0 | 255 | `floor(255.0625) = 255` |
| QStrip3| high | 287.0 | 319 | `ceil(318.9375) = 319` |
| Poly3  | high | 477.0 | 509 | `ceil(508.9375) = 509` |
| LLoop0 | high | 356.0 | 388 | `ceil(387.9375) = 388` |

The low and the high side disagree by exactly one pixel at the same |slope|
and the same width (LLoop0 reaches 32.5 px past its endpoint, LLoop4 stops at
31.5), which is what forces the *outward* rounding rather than a centre
sampled band: a centre-sampled `+-w/2` band scores 497 px, worse than the
412 px it was meant to fix.

## The tie bias decides which offline number is the device's

This is the thing attempt 1 got wrong, and it would have been registered as a
prediction had this attempt not checked it.

The clip is scored offline by rasterising the polygon `emit_line()` emits and
XORing it with the golden ink.  That rasterisation takes a **tie bias**, and
attempt 1 measured at an epsilon bias to isolate the geometry:

    tie = 1e-9      before the cap clip  414 px     after  21 px

21 px is not a number the device can produce.  `vk/draw.c`'s
`geom_line_params()` sets `lineTieBias = 1 / (2^subPixelPrecisionBits *
surface_scale_factor)`; Adreno reports 8 bits, so at scale 1 the device pushes
**1/256**, not an epsilon.  At the bias the device actually pushes:

    tie = 1/256     before the cap clip  935 px     after 544 px
                    captures worse after: none

935 is the number to trust as arm A's predicted value, and it is corroborated
from outside this model: the extent lane measured ~908 px of whole-capture
residual on a real device arm.  A model that lands within 3% of an independent
device measurement of the same quantity is the one to quote.

So the cap clip is predicted to take the whole-capture coverage residual from
~908-935 px to roughly 544 px -- a 42% cut, **not** to near-zero.  The rest is
the tie bias interacting with the rasteriser's own vertex quantisation, which
is a separate question this lane did not open: the bias is not a free
parameter, it is worth 550-580 of the 8,890 fit-set cuts on the extent legs,
and trading those away to win coverage pixels would be a bad trade made
blind.

**The prediction is therefore registered as a BOUND (<= 600 px), not a value,**
and the bound is chosen so that it holds under either modelling of the tie:
21 px and 544 px both clear it, while doing nothing (908 px) does not.  That
is the property that makes it a discriminator rather than a formality.

## The shader draws the rule, checked rather than assumed

`line_cap_phase.py --shader` rasterises `emit_line()`'s own emitted polygon
and compares it against the model pixel for pixel, because a rule derived
offline and a shader that implements something next to it is a failure
nothing else here would catch.  The GLSL and the Python transliteration were
also read side by side this attempt: same `k`, same tie vector, the same two
`cap_clip()` calls on `floor(min(m) - w/2)` / `ceil(max(m) + w/2) + 1`, in the
same order, and the strip's zig-zag index covers the convex hexagon exactly.

`docs/testing/geom_dump` prints the GLSL the generator emits, because neither
CI job compiles it and a geometry shader that fails to compile draws nothing,
silently (audit finding L10).  All six Vulkan cases parse under glslang with
Vulkan/SPIR-V rules; the check trips on a mutant.

## What the next lane should not repeat

- **Do not quote the epsilon-tie score as a device prediction.**  It is a
  clean measurement of the geometry alone and it is off by 25x as a
  prediction of the device.  The two differ by 523 px and the difference is
  entirely the tie bias.
- **Do not chase the remaining 544 px by tuning `lineTieBias`.**  It is
  pinned by the extent legs (1,911 of 41,892 band edges land exactly on a
  pixel centre) and by `subPixelPrecisionBits`, and it is not ours to pick.
  If that residual is worth opening, it is a question about the rasteriser's
  vertex quantisation, not about the cap.
- `geom_dump/build/` is generated.  Do not commit it; `make clean && make run`.

## Status

- [x] rule derived offline, no device
- [x] scored over all 48 captures (935 -> 544 at the device tie bias, none worse)
- [x] implemented in `emit_line()` (`7ce57a799b`)
- [x] geom_dump build output untracked, `--vs-goldens` leg committed
- [x] prediction registered (`docs/testing/predictions/line-cap-clip.json`)
