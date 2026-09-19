# lane.linecap13 -- #13's cap/join residual

Brief: give `emit_line()` in `glsl/geom.c` correct cap geometry against the
goldens' `Line_*` captures, without moving the exact-extent cuts already
proven.  Base: master @ `38385b79c1`.

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

## Status

- [x] rule derived offline, no device
- [ ] scored over all 48 captures
- [ ] implemented in `emit_line()`
- [ ] prediction registered
