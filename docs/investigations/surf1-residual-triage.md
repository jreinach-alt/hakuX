# What the surf1 disc's residual is actually made of

Measured on `9d020102`, OpenGL, 236 captures, `QEMU_EXIT=0`, scored against
`/tmp/goldens/results` and classified with `docs/testing/classify_residuals.py`.

Ranking these suites by channel count puts `Blend_surface` first and
`Texture_perspective` third. **Both placements are misleading, and the most
tractable-looking signature on the disc is a documented non-target.** This is
the triage, using the corpus's own criteria rather than size.

## 21.3% of the residual cannot discriminate between wrong models

`classify_residuals.py` records `golden_colours` -- how many distinct colours the
*golden* holds over the pixels where we differ -- and says in its own header
that when it is one, "every wrong model scores identically ... its channel count
must never drive a ranking -- the number is the size of a region, not the size
of a defect."

| suite | differing | flat-golden | share | captures with no discriminating power |
|---|---:|---:|---:|---|
| `Blend_surface` | 3,660,115 | 1,474,560 | **40.3%** | 6 of 32 |
| `Color_zeta_overlap` | 330,305 | 330,305 | **100%** | 3 of 9 |
| `Texture_render_target` | 102,998 | 639 | 0.6% | 3 of 40 |
| `Texture_perspective_enable` | 50,160 | 2 | 0.0% | 1 of 2 |
| **TOTAL (disc)** | **8,461,969** | **1,805,506** | **21.3%** | |

`Color_zeta_overlap` is the extreme: **every one of its 330,305 differing
channels** sits where the golden is flat. The suite can say pass or fail and
nothing else.

`Blend_surface` is the consequential one. Its four largest captures --
`1-DstAlpha_X_ORGB8`, `DstAlpha_X_ORGB8` (344,064 each) and the two
`X_O1RGB5` (294,912 each) -- all have `golden_colours = 1`. Its first-place
ranking is 40% an artefact of region size.

## The most tractable-looking signature is the precision floor

`Texture_render_target` classifies as **28 boundary-shift, 11 exact, 1
structural**. Twenty-eight captures sharing one signature looks like a
single-cause defect worth chasing. It is not. `classify_residuals.py` defines
boundary-shift as an isolated one-pixel band equal to the golden's neighbour
across it, and says these "are the same shape whatever produced them, and they
are the precision floor of interpolation, not a rule to derive
(docs/investigations/edge-defect.md)".

So the cleanest-looking target on the disc is explicitly a non-target, and
fitting to it is the failure mode that document exists to prevent.

## #72 is converged, and that is what disqualifies Texture_perspective

`Texture_perspective` has 0 of 8 exact, 1,427,840 channels, and enormous
discriminating power -- 46,845 to 59,431 distinct golden colours on its four
`tex_diff_pers_*` captures. By every criterion above it is the best target on
the disc. It is still not this lane's.

`gl-never-emits-noperspective.md` recorded Vulkan's counts for those captures
before #72 landed. Measuring GL now, after `2c25f719`:

| capture | GL now (px) | Vulkan, as recorded | |
|---|---:|---:|---|
| `tex_diff_pers_n_quad` | 184,281 | 184,281 | equal |
| `tex_diff_pers_y_quad` | 181,998 | 181,998 | equal |
| `tex_diff_pers_n_bitri` | 177,149 | 177,149 | equal |
| `tex_diff_pers_y_bitri` | 184,210 | 184,210 | equal |

**Equal to the pixel on all four.** That is worth stating twice over:

1. **#72's fix is verified converged, not merely landed.** The suite that split
   perfectly on the `noperspective` bit no longer splits at all. GL and Vulkan
   agree exactly where they used to differ by 22,826 and 15,652 pixels.
2. **The 1,427,840 channels that remain are renderer-independent.** They are
   present identically on both renderers, so they are upstream of the renderer
   split and no change in `gl/*.c` or `glsl/common.c` can reach them.

(The doc's figures are pixels; `classify_residuals.py` and this lane's scorer
count channels, which is why the two sets of numbers differ by roughly 2x. The
comparison above is pixel to pixel.)

## What that leaves

On this disc, for this lane, after removing what cannot discriminate, what is
the documented precision floor, and what is renderer-independent, the honest
remaining set is much smaller than 8.4M channels suggests -- and the two suites
a size ranking would pick first are the two that survive it worst.

Not proposing a target here. The point of this document is that three plausible
ones do not survive their own evidence, and that is worth writing down before
someone spends a day on `Blend_surface` because it is top of a list.
