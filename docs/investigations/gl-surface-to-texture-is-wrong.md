# Every capture where the GL renderer is still behind Vulkan is the
# surface-to-texture fast path

One diagnostic arm, one line: make
`pgraph_gl_check_surface_to_texture_compatibility()` return false always, so
a texture backed by a live render surface is read from guest memory instead
of sampled directly. Against the head at `0fc3e17f`, 236 captures:

```
BETTER  Blend_surface::R5G6B5_Add_SrcA_1-SrcA     25,086 -> 12,598
BETTER  Blend_surface::R5G6B5_Add_SrcA_DstA       21,283 -> 11,964
BETTER  Surface_pitch::Swizzle                    15,360 -> 12,224
BETTER  Surface_clip::rt_x8y16_w632h464               464 ->      0
BETTER  Surface_clip::rt_x0y0_w512h384                384 ->      0
BETTER  Surface_clip::rt_x320y240_w320h240            240 ->      0
BETTER  Surface_clip::rt_x16y8_w512h384               228 ->      0
BETTER  Surface_clip::rt_x0y0_w0h384                  106 ->      0
BETTER  Surface_clip::rt_x0y0_w512h0                    4 ->      0
```

**9 better, 0 worse.** GL's bit-exact count goes 102 → **108**, which is
Vulkan's exactly, and its differing-pixel total to 4,293,810 against
Vulkan's 4,443,147.

That is every capture on the disc where OpenGL was still behind Vulkan,
without exception. Three suites, three formats, one cause.

## It subsumes #71

#71 was filed as "the fast path is worse than its own fallback **for
A8R8G8B8**", because that was the format #60's fix happened to expose. It is
not format-specific. `Blend_surface`'s two are `R5G6B5`, `Surface_clip`'s six
are an R5G6B5 render target, `Surface_pitch::Swizzle` is a swizzled surface,
and #60's three were `A8R8G8B8`. The same arm moves all of them the same
way.

`Surface_pitch::Swizzle` lands at 12,224 here and landed at 12,224 in #71's
own control arm, which is the two measurements agreeing across a week of
other changes.

## What is measured, and what is not

Measured:

* The GL surface texture for `R5G6B5` really is a 565 render target. Asked
  for `GL_RGB565`, got `GL_RGB565`, `glGetTexLevelParameteriv` reports
  **5/6/5/0**. The driver is not promoting it.
* Yet the final capture holds **156 distinct red, 242 green, 156 blue**
  values, of which 124/178/124 are not valid 5- or 6-bit expansions. Vulkan
  and the golden both hold 33/64/33, essentially all valid.
* So the extra precision is introduced *after* the 565 surface, in the path
  that samples it — which is the path this arm refuses.

Not measured, and not to be guessed at: **which** part of that path. The
candidates visible from the code are the sampler state on a surface texture
(`update_surface_part()` sets `GL_TEXTURE_MIN_FILTER` to `GL_LINEAR` at
creation and never sets `GL_TEXTURE_MAG_FILTER`), the scaling factor, and
the format the sampling shader believes it is reading. Naming one without
an arm behind it is how the last three hypotheses on this issue died.

## The fix is not "turn it off"

Refusing the fast path forces a guest-memory round trip for every
render-to-texture, which is a throughput cost on exactly the workload the
path exists for. A change whose whole mechanism is *declining a path makes
pixels better* is a curve fit with a bill attached, and the orchestration
notes already flag two unpriced performance items coming out of accuracy
work.

What this arm buys is not a patch. It is the statement that the path is
wrong **in general** rather than for one format, which is the difference
between a mechanism and a correlation, and it narrows the search to one
function's worth of code with nine captures to measure any candidate
against.

---

## Root cause found for eight of the nine: a stale filter cache

`pgraph_gl_render_surface_to_texture()`'s fast path sets
`GL_TEXTURE_MIN_FILTER` to `GL_LINEAR` on the destination binding's texture.
It has to — the default is `GL_NEAREST_MIPMAP_LINEAR`, which leaves a
single-level texture incomplete. But it did not update
`texture->min_filter`, and `apply_texture_parameters()` applies the guest's
filter a moment later behind `if (min_filter != binding->min_filter)`. A
fresh binding was safe, since `generate_texture_binding()` seeds the field
to `0xFFFFFFFF`. **A reused binding whose cached filter already equalled
what the guest was asking for skipped that call and kept the forced
`GL_LINEAR`** — so a guest point sample was served a bilinear one, for the
rest of that binding's life.

That is what put non-565 values into a genuine 565 render target:
interpolating between quantised neighbours.

One line, `texture->min_filter = 0xFFFFFFFF;`, landed as `f75a4aad`:

```
Blend_surface::R5G6B5_Add_SrcA_1-SrcA   25,086 -> 12,598
Blend_surface::R5G6B5_Add_SrcA_DstA     21,283 -> 11,964
Surface_clip::rt_x8y16_w632h464            464 ->      0
Surface_clip::rt_x0y0_w512h384             384 ->      0
Surface_clip::rt_x320y240_w320h240         240 ->      0
Surface_clip::rt_x16y8_w512h384            228 ->      0
Surface_clip::rt_x0y0_w0h384               106 ->      0
Surface_clip::rt_x0y0_w512h0                 4 ->      0
```

8 better, 0 worse, GL bit-exact 102 → **108, Vulkan's exactly**, and no
throughput cost — the fast path stays. All four registered values exact.

### What it does not explain

**`Surface_pitch::Swizzle`.** The refuse-the-whole-path arm put it at
12,224; this leaves it in its 14,848–15,360 noise band. So roughly 3,136 px
of that capture is a second defect in the same path, and it was registered
as not predicted.

**#60's last regression.** With the filter cache fixed, #60's format
refresh goes from three captures regressing to **one**:
`Blend_surface::DstAlpha_XA_O1A7RGB8`, +8,192 px, 8,192 pixels moving from
`#000000` (matching the golden) to `#FFFFFF`.

That one is not the filter. Narrowing #60's refresh to the single
`X8R8G8B8_Z8R8G8B8 → A8R8G8B8` pair reproduced it, so it is a surface
rendered while the guest called it a pad format and then sampled as one
where alpha is meaningful: the raster's raw alpha shows through where
hardware reads the pad as zero. On desktop the only readers of a binding's
`shape.color_format` are the two surface-to-texture compatibility tests —
every `android_surface_*` conversion is inside `#ifdef __ANDROID__`,
checked rather than assumed — so the path from the refreshed field to those
8,192 pixels runs through the fast path being taken, not through a
conversion choosing differently.

**That is #59's subject**, pad bits written by the raster rather than
masked, and #59's lane holds `glsl/psh.c` for exactly that fix.


---

## The second residual, localised: swizzled surfaces

The filter-cache fix took eight of the nine captures. The ninth,
`Surface_pitch::Swizzle`, did not follow — the refuse-the-whole-path arm put
it at 12,224 and the filter fix leaves it at 15,360. Three arms behind a
runtime switch, each refusing a narrower slice of the fast path:

| arm | `Surface_pitch::Swizzle` | other captures moved |
|---|---:|---:|
| control | 15,360 | — |
| refuse **swizzled** surfaces | **12,224** | **0 of 235** |
| refuse swizzled **and** pitch-mismatched | 15,808 | 0 of 235 |

Refusing swizzled surfaces recovers the entire remaining GL-only gap, 3,136
px, and moves **nothing else on the disc**. So the second residual is the
surface-to-texture path applied to a *swizzled* surface, and it is confined
to the one capture that exercises it.

**The obvious hypothesis is refuted.** `check_surface_to_texture_compatibility()`
skips the pitch check for swizzled surfaces —
`(!surface->swizzle && surface->pitch != shape->pitch)` — which reads like
the defect in a test named `Surface_pitch`. Refusing exactly that subset
made the capture **worse** than doing nothing, 15,808 against 15,360, so
the mismatched pitch is not what is wrong; whatever the fast path does to a
swizzled surface is wrong across the board and the pitch-matched cases were
carrying the capture rather than breaking it.

What is left standing, and is not yet measured: the fast path is a GPU blit
(`render_surface_to()`), and a swizzled guest surface is held *unswizzled*
in its GL texture — `pgraph_gl_upload_surface_data()` calls
`unswizzle_rect()` on the way in. A blit cannot reapply a swizzle, while the
slow path goes back through guest memory where the layout is handled. That
is a reading, not an arm.

**Not fixed, and deliberately.** Refusing the path for swizzled surfaces is
the same curve fit as refusing it for `A8R8G8B8` was, with the same
throughput bill, and the same objection applies: it does not say why the
path is wrong. What the arms buy is that the remaining GL-only gap is one
named slice of one function, with one hypothesis already eliminated.

Note also that 12,224 is still 1,984 above Vulkan's 10,240 on this capture,
so even the refusal does not close it — the rest is the swizzle
address-mapping defect both renderers share, where whole blocks land in the
wrong place and the two are wrong differently.
