# Line and polygon smoothing: what the hardware does, and what it would cost

Issue #36. Neighbour: #13 (plain line and point rasterisation), #12 (the
interpolation precision floor).

**Verdict: a measured negative.** The mechanism is now pinned to better than
1/255, and it is not reachable from `vk/draw.c`. Both halves need a file
outside the smoothing owner's set, and one of them needs a device capability
nobody has measured yet.

Data: the 2026-09-12 full-corpus sweep, binary `fb4dfafc6d38`, one disc per
suite, Retroid Pocket Nova (QCS8550 / Adreno 740, Turnip
`26.3.0-T30-1.4.359`). Captures at
`dispatch/results/z-sweep-001-3D_primitive/captures1/` (mtime 2026-09-12
13:37, i.e. the same day as the binary — not stale), against
`goldens/results/3D_primitive/`, 160 of 160 golden-matched.

## 1. #36 is 4.5% of the suite it is filed against, not 100%

The board entry reads `3D_primitive 4/160, 3,866,664 px`, and the issue is
worded as though that number is the smoothing gap. It is not. Splitting the
suite by variant class first — each class is 40 captures, 10 primitives × 4
submission paths — settles it before any per-pixel work:

| class | captures | differing | of which off-by-one | max Δ |
|---|---:|---:|---:|---:|
| plain (both bits clear) | 40 | 883,336 | 821,136 | 207 |
| `-ls` | 40 | 995,032 | 795,964 | 234 |
| `-ps` | 40 | 976,680 | 785,968 | 255 |
| `-ls -ps` | 40 | 1,011,616 | 781,132 | 224 |

883,336 px differ with **both smoothing bits clear**, and turning them on adds
only ~110k each. The four submission paths are identical to each other apart
from the on-screen label, so one path (40 captures) can be measured and scaled
×4; measured that way the classification is:

| population | px | share of 3,866,664 |
|---|---:|---:|
| \|Δ\| ≤ 2 interpolation wash | ~3,670,576 | **94.93%** |
| structural (\|Δ\| > 2), on a golden edge | ~172,812 | 4.47% |
| structural, interior | ~23,188 | 0.60% |

The wash is #12's precision floor. Of the structural interior residual, 88.5%
is `TriFan` + `TriStrip` alone — the triangle-fan/strip split seam, a separate
defect. Edges are measured as a golden local luminance range > 16 over a 3×3
region, never a single-pixel comparison.

Subtracting the part the hardware bits are actually responsible for — the
difference between the hardware's own smoothed and unsmoothed goldens, which
is the ceiling on any fix — gives **43,926 px per submission path, ~175,704 px
of 3,866,664, or 4.5%.**

### A constant that is not an effect

Comparing `golden(-ls)` against `golden(plain)` for a *filled* primitive gives
exactly **150 px** every time; `-ps` against plain for a *line* primitive gives
exactly **168 px** every time; `Points` gives both. The bbox is always
`y[27..40]`, a single 14-row text band: it is the test's on-screen name label
gaining `-ls` / `-ps`. Fitting anything to it would be fitting to a string.
Every number above excludes it, and the per-pixel work crops to `y >= 45`.

The same trap sits on the submission axis: the inline-path captures differ from
the array-path capture by a constant 954 / 702 / 1058 px, identical for
`LineLoop` and `TriStrip`, which is again only the label.

## 2. The mechanism, measured

**Coverage, alpha-blended against the destination.** Fit one scalar coverage
per pixel from whichever channel is furthest from the background, then use it
to predict the other two channels:

| capture | core px fitted | residual on the 2 unfitted channels | null (no smoothing) |
|---|---:|---:|---:|
| `Lines-ls` | 1,250 | **0.28** | 27.88 |
| `LineStrip-ls` | 2,195 | **0.84** | 23.47 |
| `LineLoop-ls` | 2,520 | **0.92** | 22.21 |

A single scalar explains the hardware output to under one part in 255, against
a null of 22–28. So `golden = cov·unsmoothed + (1−cov)·dst` and nothing else.

**Coverage is quantised to eighths.** Snapping the fitted values:

| snap | mean \|err\| | within 0.01 |
|---|---:|---:|
| 1/2 | 0.1263 | 31.2% |
| 1/4 | 0.0434 | 63.3% |
| **1/8** | **0.0040** | **93.4%** |
| 1/16 | 0.0033 | 94.4% |
| 1/32 | 0.0028 | 96.3% |

(`LineLoop-ls`; the other two line primitives agree to the third decimal.)
1/8 is where the error collapses and finer buys nothing — a 3-bit coverage
value. The observed levels are 4/8, 5/8, 6/8, 7/8, 8/8: there is a **floor at
half coverage**, and a smoothed line never fades below it.

**The two bits are disjoint, and each is a no-op on the other class.**

| | footprint plain → smoothed | fringe added | core re-shaded |
|---|---|---:|---:|
| `LINESMOOTH`, `Lines` | 1,258 → 2,452 (+95%) | 1,195 | 1,121 px, mean −50.8 lum |
| `LINESMOOTH`, `LineLoop` | 2,567 → 4,904 (+91%) | 2,342 | 2,124 px, mean −42.8 lum |
| `POLYSMOOTH`, `TriStrip` | 52,463 → 52,902 (+0.8%) | 439 | 1,255 |
| `POLYSMOOTH`, `Polygon` | 62,822 → 63,259 (+0.7%) | 437 | 1,215 |

Line smoothing roughly **doubles** the footprint and moves energy outward into
a ~1px fringe on each side. Polygon smoothing is a thin silhouette effect only
— 98% of the polygon interior sits at coverage exactly 1.0 — which is why it
cannot be what the `TriFan`/`TriStrip` interior seam is.

Our own output moves the wrong way: `ours(-ls)` has a footprint 193–244 px
**smaller** than `ours(plain)`, because the bits change nothing in the
rasteriser and the only thing that does change is the test's surface redirect.

### Retracted: the 2× supersample story

Issue #36 says the `-ls`/`-ps` tests redirect the colour surface at 2× pitch
with `AA_CENTER_CORNER_2` and resolve by texturing a quad, so "hardware's
smoothing in these captures is partly the 2× horizontal supersample being
averaged on resolve". **The goldens falsify this as an explanation of the
output.** A 2-tap horizontal box filter of `golden(plain)` is a *worse* model
of `golden(-ls)` than `golden(plain)` itself:

| capture | vs `golden(plain)` | vs 2-tap box of it |
|---|---:|---:|
| `LineLoop-ls` | mean 0.653, 4,645 px>2 | mean 0.774, 5,114 px>2 |
| `Lines-ls` | mean 0.414, 2,466 px>2 | mean 0.501, 2,700 px>2 |
| `TriStrip-ls` | mean 0.101, 150 px>2 | mean 0.384, 6,459 px>2 |

Whatever the harness does with the AA surface, the resolved golden is not a
horizontal average of the unsmoothed image. The eighths-quantised coverage
model above is, to 0.9/255. Implement that, not a supersample.

## 3. Why it cannot be done in `vk/draw.c`

- **Lines** need `VK_EXT_line_rasterization` with `smoothLines` and
  `VK_LINE_RASTERIZATION_MODE_RECTANGULAR_SMOOTH_EXT`. hakuX never requests
  that extension — it is absent from both lists in `vk/instance.c` — so the
  measured enabled-extension list from the device (8 entries) says nothing
  about availability, and the six
  `VkPhysicalDeviceLineRasterizationFeaturesEXT` booleans are **UNMEASURED**.
  `vk/draw.c` already has an unused `rasterizer_next_struct` hook to hang the
  line state off, so the draw-side change is small; the enablement is not in
  this file.
  - **Do not read the booleans off the driver blob.** Both Turnip `.so`s
    contain `VK_EXT_line_rasterization` and all six feature names — and also
    `VK_NV_ray_tracing` and `VK_HUAWEI_cluster_culling_shader`. That is Mesa's
    generated full-registry string table, not a support list.
  - Even granted the extension, the spec leaves the coverage falloff
    implementation-defined. Enabling it does not guarantee eighths with a 4/8
    floor.
- **Polygons** have no Vulkan analog whatsoever. The only route is MSAA, and
  there is no multisampling anywhere in either backend — every pipeline and
  image is hardwired to `VK_SAMPLE_COUNT_1_BIT`. 8× MSAA would give the right
  quantisation, but it reaches the render pass, the framebuffers and
  `surface.c`.
- `surface_scale_factor` supersampling cannot substitute. The downscale on
  readback is a raw row-stride copy, not a filtered resolve, so the extra
  samples are discarded rather than averaged.
- **Either route must force `SRC_ALPHA`/`ONE_MINUS_SRC_ALPHA` blending on**,
  since coverage unblended is worthless. That is a synthesised blend state
  `NV_PGRAPH_BLEND` does not hold, and it lands directly on top of
  `pgraph_vk_effective_blend_reg()`'s destination-alpha substitution for #48
  (`2f23dd9ce5`), whose A/B is in flight. The two changes must be sequenced,
  not merged.

Unmasking `LINESMOOTHENABLE`/`POLYSMOOTHENABLE` from `init_pipeline_key()` on
its own measures exactly 0 better and 0 worse — nothing consumes the bits. It
is a necessary half of a fix, never a fix.

### What to collect first, cheaply

The pattern at `vk/draw.c:3255` (`clamp_line_width_to_device_limits()` logging
the real `lineWidthRange`) is how the line-width limits got measured. The same
one-capture trick would settle: the full
`vkEnumerateDeviceExtensionProperties` list rather than only the enabled
subset, `VkPhysicalDeviceLineRasterizationFeaturesEXT` via
`vkGetPhysicalDeviceFeatures2`, and
`limits.framebufferColorSampleCounts` / `sampledImageColorSampleCounts`. Until
those exist, any smoothing plan is a guess about the driver.

## 4. The two neighbouring suites are not this issue

**`Antialiasing_tests`, 235,978 px.** 99.8% of it is three captures at
*exactly* 78,496 px each — `CreateSurfaceWithCenter1`,
`CreateSurfaceWithCenterCorner2`, `CreateSurfaceWithSquareOffset4`. Identical
counts because the residual is mode-independent: the pairwise differences
between the three goldens (546 / 624 / 382 px) are reproduced *exactly* by the
pairwise differences between our three captures, so what varies with AA mode we
already get right and what we get wrong does not vary with it. The residual is
a large-area brightness difference (bbox `y[68..415] x[70..574]`, golden median
lum 192 vs ours 133) with 55,478 of 78,496 px in the **interior**, not on
edges. Neither a 2-tap box nor a 2× squash of the golden models it. Not a
smoothing defect. The suite has zero off-by-one pixels, so #12 is not in it
either.

**`2D_Lines`, 3,257 px.** 100% structural, 100% on edges, and the per-capture
count is exactly the line length: 479 px for a 480px vertical line, 627 for
the 640×480 diagonal, 300 for a 300px line, 0 for the zero-length case. **The
line is simply not drawn.** For `2DLine-24-C00FFFFFF-400_0-400_479` the golden
has 479 pixels at lum 255 in column x=400 and we have background (lum 68) in
every column from 395 to 405; our only non-background content is the label at
`y[25..65] x[20..314]`. Rolling our capture horizontally by ±1, ±2, ±3 makes
the score monotonically *worse* (479 → 2,039 → 3,355 → 4,639), so it is not
displaced either.

> Correction to `docs/testing/run-2026-09-12-golden-discrimination.tsv`: it
> classes ten of the thirteen `2D_Lines` captures as `boundary-shift`. They are
> not shifted — the primitive is absent. The rows have `golden_colours = 1`,
> and per the correction at the top of `unfalsifiable-goldens.md` that is a
> proxy only: these goldens are a saturated line on a flat ground, which ranks
> as low-discrimination but in fact pins the geometry exactly, because the only
> question they ask is whether a pixel is on the line. They are good evidence,
> and the class label is what is wrong.

This belongs with #13, not #36, and it is a missing draw rather than a
rasterisation inaccuracy.

## What was ruled out

- Smoothing being the bulk of `3D_primitive` — it is 4.5%; 94.9% is #12's wash.
- The 2× `AA_CENTER_CORNER_2` supersample as the source of the golden's
  smoothing — a 2-tap box is a worse fit than no filter at all.
- `POLYSMOOTH` as the cause of the `TriFan`/`TriStrip` interior residual —
  polygon smoothing is silhouette-only, 98% of the interior at coverage 1.0.
- `LINESMOOTH` mattering to filled primitives, or `POLYSMOOTH` to lines — both
  cross-terms are the label band, to the pixel.
- `Antialiasing_tests` and `2D_Lines` being smoothing at all.
- Reading the driver blob's string table as a capability list.
- Unmasking the pipeline-key bits as a standalone fix — provably 0/0.
