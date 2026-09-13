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


### The swizzle reading is refuted too, at zero run cost

The reading left standing above was that the fast path is a GPU blit and a
swizzled guest surface is held *unswizzled* in its GL texture, so the blit
cannot reapply the layout. That predicts a **pure rearrangement**: the fast
path's output and the slow path's should hold the same pixels in different
places.

They do not. Comparing the two arms already on disk — `s2t0` took the fast
path, `s2t1` refused it — over the 13,296 px where they differ:

| | distinct colours | contents |
|---|---:|---|
| fast path | 3 | `#00AA00` ×6,112 · `#FFFFFF` ×4,616 · `#000000` ×2,568 |
| slow path | 4 | `#FFFFFF` ×4,584 · `#000000` ×4,584 · `#00AA00` ×2,080 · `#7722FF` ×2,048 |

**Not the same multiset**, so not a permutation and not a layout error. The
fast path loses `#7722FF` entirely — 2,048 px to zero — and gains 4,032 px of
`#00AA00`, which is the solid colour the test fills each of its four render
targets with before drawing into them.

So the fast path is not mis-arranging content; it is serving the **fill
instead of the drawn result**. That is a staleness or wrong-binding
signature, and it fits the rest of this issue — the path serving something
other than what the guest last rendered — and it fits the run-to-run
instability, where sometimes the content is caught and sometimes it is not.

Which of those it is, this does not say, and it is not guessed at here. What
it does is take the swizzle reading off the board for the cost of reading two
captures that were already on disk: no build, no run, no device. A hypothesis
that predicts a multiset invariant is cheap to kill, and it is worth looking
for that shape before queueing an arm.

Neither arm matches the golden's own multiset — `#FF2222` and `#2222FF`
appear in the golden and in neither of ours — which is the shared
address-mapping defect, unchanged and still separate.


### And it is not the texture cache serving a stale render either

The next candidate after the swizzle reading was the gate in `gl/texture.c`:

```c
if (surf_to_tex && binding->draw_time < surface->draw_time) {
    pgraph_gl_render_surface_to_texture(...);
    binding->draw_time = surface->draw_time;
}
```

If a surface were drawn into without `surface->draw_time` advancing, the
cached texture would be served unchanged and the guest would see the previous
render — which is exactly the observed signature.

Instrumented over a full run: **335 surface-to-texture decisions, every one
`RENDER`, none `REUSE-CACHED`.** 222 on unswizzled surfaces, 112 on the one
swizzled surface (`02e06000`, the only swizzled address on the disc), one
more with `draw_dirty` clear. The cached-texture path is never taken on this
disc, so it cannot be what serves the fill.

So the render *does* run, every time, and still produces the fill rather
than the drawn result. **The loss is inside `pgraph_gl_render_surface_to_texture()`,
not in whether it is called.** That is a narrowing rather than an answer, and
it is where the next probe goes: dump what the surface's own GL texture holds
at the moment of the render, which separates "the render copied the wrong
thing" from "the thing it copied was already wrong".

One more fact from the same run, recorded because it bounds a candidate:
`surface->upload_pending` is **0 at every one of the 335 sites**, so the
`if (surf_to_tex && surface->upload_pending)` refresh in `gl/texture.c` never
fires. Whatever the surface's GL texture holds when the render runs, it was
not refreshed from guest memory there.


### The slow path is never reached, and I nearly reported the opposite

Instrumented at the branch in `pgraph_gl_render_surface_to_texture()` that
chooses between the GPU blit and `render_surface_to_texture_slow()`, over a
full run:

```
412 surface-to-texture calls, every one FAST, none SLOW
  229  03628000 swz=0     46  02e06000 swz=1     40  026a4000 swz=1
   48  026eb000 swz=0     46  02c06000 swz=1      3  others
```

So `render_surface_to_texture_slow()` is dead on this disc, and the swizzled
surfaces go through the blit like everything else.

**I nearly recorded the opposite**, and the near-miss is worth more than the
fact. A probe placed inside the fast path printed 109 lines; summarised with
`sort | uniq -c | sort -rn | head -8` it showed one address only, because
that address's lines were *identical to each other* and repeated while the
others' histograms all differed and sorted below the cut. Counting the same
log by address instead gives five addresses: 40, 34, 33, 1, 1. The conclusion
drawn from the first view -- *the swizzled case does not take the fast path,
so the defect is in the slow path* -- was wrong in both halves.

That is the second instance in one day of reading a **summarised view as if
it were the whole set**; the first turned a flat warning count into a
four-warning improvement. `uniq -c | sort -rn | head` answers "which line
repeats most", and a line that carries a varying field can never repeat. When
the question is "which things appear", cut the varying fields out *before*
counting, or count the key directly.

What is left standing is unchanged and now better bounded: every call takes
the blit, the blit runs every time, and the result is still the fill rather
than the drawn content. The next probe is the one already named -- read back
the source surface's own GL texture for the surface that backs
`Surface_pitch::Swizzle` specifically, which first requires identifying that
surface's address rather than assuming it is one of the swizzled ones seen
here.


## Answered: the thing the blit copied was already wrong

The surfaces backing `Surface_pitch::Swizzle` were identified from the
existing probe log rather than assumed — the test fills each of its four
render targets with `0xFF00AA00`, so the surface whose GL texture is mostly
`#00AA00` is one of them:

```
SRCTEX addr=0270b000 128x128 distinct=3  top: #00AA00 x12288 #000000 x2048 #FFFFFF x2048
SRCTEX addr=0271b000 128x128 distinct=3  top: #00AA00 x12288 #000000 x2048 #FFFFFF x2048
```

128×128 = 16,384 = 12,288 + 2,048 + 2,048, so those two dumps are complete:
their GL textures hold **exactly three colours**. Each took the fast path
exactly once, matching the path census.

That settles the question this section was opened to answer.

* The source GL texture is **not** pure fill — it carries `#000000` and
  `#FFFFFF` drawn over the `#00AA00`, so the blit is not copying a blank.
* But it does **not** contain `#7722FF`, the colour the fast path loses and
  the refused-path arm produces.

The refused arm reads guest memory; the fast arm reads the GL texture. The
colour exists in one and not the other, so **the surface's GL texture is out
of date with guest memory, and the blit faithfully copies a stale source.**
Of the two readings left open — *the render copied the wrong thing* versus
*the thing it copied was already wrong* — it is the second.

That also gives the `upload_pending` bound recorded above its meaning. The
refresh that would reconcile the two is

```c
if (surf_to_tex && surface->upload_pending) {
    pgraph_gl_upload_surface_data(d, surface, false);
}
```

and `upload_pending` is 0 at every one of the 412 sites, so it never fires.
The test writes its inner checkerboard from the CPU
(`GenerateSwizzledRGBACheckerboard` at `kInnerTextureMemory`), and a CPU
write to surface memory is what `surface_access_callback()` exists to notice.

**Not established, and the next thing to measure:** whether that callback
fires for this write at all. If it does and the flag is consumed before the
texture read, the fix is about ordering; if it never fires, the fix is about
coverage. Those need opposite changes, which is why this stops here rather
than guessing between them — the same reason the four earlier hypotheses
were tested rather than adopted.
