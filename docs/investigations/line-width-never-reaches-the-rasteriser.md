# `Line width`: the requested width never reaches the rasteriser

Measured 2026-09-11, entirely from captures already on disk. No device time.

`Line width` is 60 of 61 captures classified `structural` on the reclassified
corpus, 815,888 non-precision channels — the best-shaped unclaimed target on
the board. It turns out to be one cause, and the evidence is unusually clean.

## What the captures say

Lit pixels per capture, ours against the golden, across the suite's whole
width series. `NV097_SET_LINE_WIDTH` is nine bits of eighths of a pixel, so
the series runs 0.0 to 63.875 and then past the end of the register.

| width | golden | ours |
|---:|---:|---:|
| 0.000 | 3,104 | 6,491 |
| 0.500 | 4,798 | 6,475 |
| 1.000 | 6,677 | 6,471 |
| 2.000 (0001.7 ≈) | 9,517 | 6,435 |
| 4.000 | 16,192 | 6,475 |
| 8.000 | 26,827 | 6,489 |
| 16.000 | 42,870 | 6,463 |
| 32.000 | 64,780 | 6,469 |
| 63.875 | 91,319 | 6,435 |
| 64.000 | 6,673 | 6,467 |

**Our coverage is constant to within ±1% across the entire range** — 6,435 to
6,491 over 58 captures, while the golden's grows by a factor of thirty. We
draw every line one pixel wide whatever the guest asked for, and the only
width we get close to is 1.0.

Three further things fall out of the same table:

* **The hardware honours sub-pixel widths.** At width 0.0 the golden is 3,104,
  about half the 1.0 figure — a thinner line, not an absent one. Whatever we
  do instead cannot be reached by clamping up to 1.0.
* **Out-of-range writes are confirmed to be ignored**, not masked or clamped:
  from 64.0 up the golden returns to the 1.0 coverage the suite restores
  between tests, which is what `pgraph.c`'s handler already implements and
  this is the measurement that backs it.
* **Even at width 1.0 we are 3% light** (6,471 against 6,677). That is a
  separate and much smaller question about the coverage rule at the ends of a
  segment, and it should not be confused with this one.

## Why

`hw/xbox/nv2a/pgraph/vk/draw.c`. The width is requested through Vulkan's wide
lines:

* `pgraph_vk_line_width()` converts the register to pixels correctly,
  `(line_width / 8.0) * surface_scale_factor`.
* `clamp_line_width_to_device_limits()` then snaps it to
  `lineWidthGranularity` and clamps it into `lineWidthRange`.
* `snode->has_dynamic_line_width` additionally requires
  `enabled_physical_device_features.wideLines`, and where it is false the
  pipeline's static `.lineWidth = 1.0f` stands.

Both routes end at 1.0 on this device, and the captures cannot tell them
apart because 1.0 is the answer either way. That distinction is the one datum
this analysis is missing, and it is one log line:
`lineWidthRange`, `lineWidthGranularity`, and whether `wideLines` was actually
enabled. It matters only for how much of the fix is needed, not for whether.

## What the fix has to be

Vulkan cannot express what this register asks for. `lineWidthGranularity`
quantises, `lineWidthRange` bounds, and neither is required to admit a width
below 1.0 at all — so sub-pixel widths, the 1/8 steps, and anything past the
device's maximum are all unreachable through `vkCmdSetLineWidth` on any
conformant driver. A driver-dependent path also makes the accuracy numbers
driver-dependent, which the driver survey went to some trouble to rule out.

So the width has to be applied by us: expand each line segment into a quad of
the requested width. The pipeline already puts a geometry stage in front of
every `LINES`, `LINE_LOOP` and `LINE_STRIP` draw — that generator is where the
expansion belongs, and it covers `POLY_MODE_LINE` wireframe fill (the suite's
three `Fill_*` captures) by the same route. The device's own line rasteriser
then only ever sees the 1.0 it can do, and the accuracy stops depending on
which driver is installed.

Two details the goldens already pin down, and which a quad expansion must
reproduce rather than approximate: the sub-pixel behaviour at width 0.0 (half
the coverage of 1.0, so the expansion cannot simply floor to one pixel), and
the 3% shortfall at width 1.0, which says our end-of-segment coverage is
already slightly wrong before any of this.

## Order of work

1. Log the three device limits, so the diagnosis names one mechanism instead
   of two. Free — it rides the next build.
2. Expand lines to quads in the geometry stage, width from the register.
3. Re-run the suite. The prediction is testable and specific: coverage should
   track the golden's column across all 58 in-range widths, and the 3%
   shortfall at 1.0 should survive as the only remaining error.

Method note: measuring lit pixels per capture rather than diffing against the
golden is what made this legible. A diff says "wrong here"; a coverage total
against the requested width says "the parameter is not arriving", and the
constant column is the whole finding. `docs/testing/line_coverage.py`.
