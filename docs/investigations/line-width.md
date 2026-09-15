# Line width: a third the size it looks, and three separate causes

`Line_width` was ranked the best-shaped unclaimed target on the board —
816k px at 60 of 61 captures `structural`. Measured on this lane it is
1,088,183 px over 61 captures, and it decomposes into three unrelated things,
only part of which is real work.

## The split

| | px | share |
|---|---:|---:|
| colour differs where both agree there is ink | 1,006,513 | **92.5%** |
| coverage differs — one says ink, the other does not | 81,670 | 7.5% |

So the thinness is the small half. I had characterised this suite as "our lines
are systematically too thin", which is true and is 7.5% of it.

Of the colour differences:

| | px | share of colour |
|---|---:|---:|
| \|delta\| = 1 | 740,293 | **73.6%** |
| \|delta\| = 2..4 | 5,481 | 0.5% |
| \|delta\| > 4 | 260,739 | **25.9%** |

**The genuinely structural content is about 342k px** — 260,739 colour plus
81,670 coverage — not 1.09M and not 816k.

That is not a contradiction of the `structural` classification. The residual
classifier's label is all-or-nothing, so a capture that is three-quarters
one-step with a structural tail reads `structural`. Sixty-one such captures
read as a 816k structural block. The tail is real; the block is not.

## Why the one-step share is suspect on this lane specifically

`line_width_tests.cpp` calls `host_.SetBlend(true)`. Every pixel in this suite
is blended, and this lane's blend is exactly what `bump-alpha-blend-rounding.md`
just established is wrong here and right on Adreno — 6.46M px of one-step alpha
that do not exist on real hardware.

**That makes 740,293 px of this suite untrusted rather than wrong.** It is not
a conclusion: it is a hypothesis with a cheap test, and the device lane can
settle it the same way it settled the bump alpha, from a capture set it is
already producing. I am not going to assert the mechanism this time.

## The coverage part, which is three causes not one

Test names encode the raw `NV097_SET_LINE_WIDTH` register **in eighths**:
`Line_0063.7` is 63 + 7/8 = 63.875, not 63.7. (My first pass through this read
them as decimals and fitted nonsense.) With the widths right:

**1. Below width 1 we are too fat.** At 0.625 we have 1,252 px of ink gold does
not, and none the other way. Hardware draws a genuinely sub-pixel line;
`clamp_line_width_to_device_limits()` raises anything under 1.0 to the device
minimum, which is 1.0 here. Vulkan cannot draw a line thinner than
`lineWidthRange[0]`, so this is not reachable by adjusting the width.

**2. Between 1 and about 12 we are one pixel narrow.** The missing pixels are
a clean one-pixel shell on our own ink — at width 12, 1,437 px in 915 blobs of
at most 6 px each. An edge or coverage-rule difference, not a scale error:
`wideLines` is supported here with granularity 1/128, so the width we ask for
is the width we get.

**3. Above that, the corners go unfilled.** At width 57 the same 2,176 missing
px form only **60 blobs**, the largest 193 px. The unfilled tests run with
`NV097_SET_FRONT_POLYGON_MODE_V_LINE`, so the line loop, triangles, quad strip,
triangle fan and polygon all draw as wireframe — corners everywhere. Hardware
fills the wedge between adjacent segments; Vulkan's strict lines rasterise
independent rectangles and leave it empty. The blob count tracks the corner
count, and the gaps thicken with width as a wedge does.

## What it would take

All three coverage causes are the same fix: stop using Vulkan line primitives
and generate the geometry — quads per segment plus joins — which is the only
way to get sub-pixel widths, control the coverage rule, and fill corners.

That is an architectural change of the same size as the shader-side blending
#43 needs, for a quarter of the payoff, against a target whose size is a third
of what the ranking says and three quarters of which may be a host artefact.

**Recommendation: do not take `Line_width` next.** Have the device lane price
the one-step share first. If those 740k px are host, what is left here is
~342k px behind a rewrite of line rasterisation, which is not the best use of
the next change.

**Better candidate, priced on hardware while this was being written.** The
device lane re-ran `Bump_map` on Adreno: 435,201 RGB px differing, **0% of them
within one step**, 0 of 40 captures exact. That defect survives the change of
host entirely — so it is real work, it is already isolated to one suite, and it
does not need a rasteriser rewrite to attack. Note this does not resurrect
`Bump_map`'s 2.0M *alpha* px, which are the lavapipe artefact; the 435,201 are
the RGB residue underneath them.
