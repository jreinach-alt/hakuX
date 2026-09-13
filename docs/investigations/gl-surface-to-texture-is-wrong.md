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
