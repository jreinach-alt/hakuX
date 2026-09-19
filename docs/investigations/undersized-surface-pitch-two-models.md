# Undersized surface pitch: two layout models, and why one of them is not #87

Issue [#109](https://github.com/jreinach-alt/hakuX/issues/109), written off
device on 2026-09-18 at `master` `4129a349e6`. Registered prediction:
[`../testing/predictions/undersized-pitch-swizzle-layout.json`](../testing/predictions/undersized-pitch-swizzle-layout.json).
No measurement — there is no silicon, and the arm that needs no silicon is
not dispatchable with today's `request.sh`. Nothing under `hw/xbox/nv2a/` was
touched.

#109 asks: the NV2A tolerates a surface pitch smaller than the width implies,
and our swizzled render-target layout does not reproduce what the hardware
draws in that case. It files this as a lead on #87. This is the derivation of
both models' pixel predictions, and the offline result of #109's own
falsifier.

## The one-paragraph derivation

The swizzled (Morton) address computation in `hw/xbox/nv2a/pgraph/swizzle.c`
takes **no pitch**: `generate_swizzle_masks(width, height, depth)` interleaves
the bits of x and y and nothing else, so a destination offset is a function of
`(x, y, log2 width, log2 height, bpp)` alone. Pitch enters one step earlier,
as the row stride of the *linear intermediate* that the CPU download path
builds before swizzling it — `dst_row = linear_guest + y * surface->pitch`
followed by `swizzle_rect(..., surface->pitch, bpp)`, where `row_pitch` is the
stride at which `swizzle_box_internal` reads its source rows. When `pitch ==
width * bpp` those two strides coincide with hardware's and everything
cancels. When `pitch < width * bpp` they do not: each row's write of
`width * bpp` bytes lands at `y * pitch`, so only its first `pitch` bytes
survive (the GL path overwrites the tail with the next row; the Vulkan
deferred path never copies it, `memcpy_image` copying `MIN(src_stride,
dst_stride)`), and the read then takes `width` pixels from `y * pitch` — the
head of row `y` followed by the head of row `y + 1`. That yields a closed-form
map with no free parameters, which is what makes this a derivation rather than
a fit:

```
Model H  (hardware / "pitch does not enter")
    dest(x, y) = src(x, y)                       for all x, y
    and the surface occupies width * height * bpp bytes, not pitch * height

Model E  (this tree's CPU download path)
    dest(x, y) = src(x, y)                       x <  pitch/bpp
    dest(x, y) = src(x - pitch/bpp, y + 1)       x >= pitch/bpp
```

## The numbers, and the generator that produced them

Divergence is counted over destination pixels as *source coordinates*, so it
is content-independent — it does not depend on what the test draws.

| surface | pitch | exact pitch | Model E != Model H | out-of-bounds reads |
|---|---:|---:|---:|---:|
| 128x128 A8R8G8B8, GL | 512 | 512 | **0** of 16,384 | 0 |
| 128x128 A8R8G8B8, GL | 256 | 512 | **8,128** of 16,384 (49.6%) | 0 |
| 128x128 A8R8G8B8, VK deferred | 256 | 512 | 8,192 of 16,384 (50.0%) | **64 px / 256 B** |
| 64x64 A8R8G8B8, GL | 256 | 256 | **0** of 4,096 | 0 |
| 64x64 A8R8G8B8, GL | 128 | 256 | 2,016 of 4,096 (49.2%) | 0 |
| 64x64 A8R8G8B8, VK deferred | 128 | 256 | 2,048 of 4,096 (50.0%) | 32 px / 128 B |

Diverging columns are always exactly `[pitch/bpp .. width-1]` — the right half
of the surface for the one-half ratio. And Model E has a signature that needs
**no golden at all**, only the capture: `dest(x + pitch/bpp, y) == dest(x,
y + 1)` holds at **8,128 of 8,128** positions for the 128x128 pitch-256 case
(2,016 of 2,016 for 64x64 pitch-128). Under Model H it holds only where the
drawn content happens to satisfy it.

The GL/Vulkan split in the table is only the allocation and the last row.
GL sizes its intermediate from `surface->size`, and
`entry->size = height * MAX(surface->pitch, width * fmt.bytes_per_pixel)`
(`gl/surface.c:2872`) already oversizes it, so the last row's overlapping
write and the read that follows stay in bounds, and that row survives intact
in both halves — hence 8,128 rather than 8,192. **There is no heap overflow on
the GL path.** I derived one before reading line 2872 and it is wrong; it is
recorded here so nobody re-derives it as a finding.

Reproduce, with no dependencies:

```python
def masks(width, height):                 # generate_swizzle_masks, 2-D
    mx = my = 0; bit = mask_bit = 1
    while True:
        done = True
        if bit < width:  mx |= mask_bit; mask_bit <<= 1; done = False
        if bit < height: my |= mask_bit; mask_bit <<= 1; done = False
        bit <<= 1
        if done: return mx, my

def model_e(width, height, bpp, pitch, alloc, overlap):
    """{(x,y): source pixel, or 'OOB'} for the pitch-as-stride round trip."""
    kept = pitch // bpp                   # pixels of each row that survive
    live = {}                             # byte offset -> source pixel
    for y in range(height):
        span = width if (overlap and y == height - 1) else kept
        for x in range(span):
            live[y * pitch + x * bpp] = (x, y)
    out = {}
    for y in range(height):
        for x in range(width):
            off = y * pitch + x * bpp
            out[(x, y)] = 'OOB' if off + bpp > alloc else live.get(off)
    return out

# GL:  alloc = height * max(pitch, width*bpp),  overlap=True
# VK deferred: alloc = pitch * height,          overlap=False
e = model_e(128, 128, 4, 256, 128 * max(256, 128 * 4), True)
print(sum(1 for k, v in e.items() if v != k), 'of', len(e), 'diverge')
```

`masks()` is unused by `model_e` and is kept because it is the check that
matters for Model H: the destination offsets it produces are a function of
width and height only, which is the whole claim that pitch does not enter the
swizzled store.

## #109's own falsifier, run offline: the hypothesis is not #87

#109's falsifier says the undersized-pitch rule earns the "lead on #87" label
only if the two models **diverge on #87's known-wrong quads and agree on the
quads #87 already gets right**, and that if they diverge everywhere or agree
everywhere the hypothesis explains nothing beyond #87 and should say so
rather than be tuned to fit. Run against what is on file:

* `Surface_pitch` programs the **same** 128x128 surface twice, at
  `SET_SURFACE_PITCH_COLOR` 512 and 256, and **both the golden and our
  capture are identical across that pair, 0 px** — recorded in the #87 fix's
  own comment at `hw/xbox/nv2a/pgraph/gl/surface.c:1545`, and it is the
  observation that killed the pitch reading there.
* The two models **agree exactly** (0 of 16,384) on the pitch-512 member, by
  construction: at the exact pitch the two strides coincide.
* #87's residual was **identical on both 128-wide quads** — "the two outer
  128-column results are wrong in the same way", with the same colour
  multisets and the same run-length signature.

So the undersized-pitch rule predicts an **asymmetry between the pitch-512 and
pitch-256 quads**, and the measurement says there is none. It agrees with the
Morton map on one of the two known-wrong quads and diverges on the other,
which is neither of the outcomes the falsifier allows. **The hypothesis
explains nothing about #87.** #87 is separately closed on its subject with no
free parameters: the residual was one uncancelled Morton transform through the
surface-to-texture fast path, 100.0000% over both affected quadrants against a
68.75% identity control, and inverting the map made the capture byte-identical
to the golden; `c807592d02` added the layout-kind check to both renderers'
compatibility gates and the device measured `Surface_pitch/Swizzle`
10,240 -> 0.

The magnitudes do not line up either, and should not be made to. 8,128 is a
count over one render target's 16,384 destination pixels; #87's 10,240 is a
count over the 640x480 framebuffer into which four textured quads were drawn.
They are not the same quantity and no ratio between them means anything.

## What is nevertheless live, and where

Model E is **not refuted** — it is **untested**, and #109's "state in this
tree: absent" is right about the *rule* and wrong about the *consequences*,
which are present in four places. The distinction matters because the code
that would exhibit Model E was not reached by any measurement on file:

* **Vulkan's synchronous download never uses pitch for a swizzled 4-bpp
  surface.** `use_compute_to_swizzle = surface->swizzle &&
  surface->fmt.bytes_per_pixel == 4 && !depth_stencil` (`vk/surface.c:858`),
  and that branch `memcpy`s `width * height * bpp` bytes out of the compute
  swizzle with no pitch anywhere. Every clean number on
  `Surface_pitch/Swizzle` is Vulkan. **A Vulkan 0 is consistent with both
  models and discriminates neither.**
* **GL has no compute path**, so `pgraph_gl_surface_download_to_buffer`
  applies Model E to every swizzled download. The only GL numbers on this
  capture (13,160 / 14,848 / 15,360) predate `c807592d02` and are
  race-affected. GL after the fix is unmeasured — and the fix is exactly what
  routes GL out of the fast path and into the pitch-using code.
* **Vulkan's *deferred* download also applies Model E**, and sets
  `dl->use_compute_to_swizzle = false` unconditionally (`vk/surface.c:587`),
  so the same surface gets a different layout depending on which of the two
  routes serves it. Its intermediate is sized `dl->pitch * dl->height`
  (`vk/surface.c:650`) rather than from `surface->size`, so `swizzle_rect`'s
  last-row read of `width * bpp` bytes from `(height-1) * pitch` runs
  `width * bpp - pitch` bytes past the allocation — 256 bytes, 64 pixels, for
  the 128x128 pitch-256 case. Bounded, read-only, and it lands in the guest
  surface's last-row Morton cells. **Recommend a tracker row.** What is *not*
  established, and is the missing step: that this route is reached for a
  swizzled undersized-pitch surface on the current disc. There is no guard
  excluding swizzled surfaces from `download_surface_record_deferred`, but
  "not excluded" is not "reached".
* **`pitch * height` is used as the surface's extent in at least four places**
  where Model H says the extent is `width * height * bpp`:
  `assert(surface->offset + surface->pitch * height <= dma.limit + 1)`
  (`gl/surface.c:2850`, `vk/surface.c:3109`), `surface_vram_written(...,
  surface->pitch * surface->height, ...)` (`vk/surface.c:593`) and the four
  `memory_region_set_client_dirty(..., s->pitch * s->height, ...)` calls
  (`vk/surface.c:664-669`, `:741-746`). For an undersized pitch every one of these
  **under-reports by the missing half**: a permissive DMA-limit assert, a
  shelved overlapping surface not marked `vram_newer`, and a dirty range that
  misses the second half of what was written. None of this is reachable by
  the current disc, which is why it is the hardware leg's job.

## The two legs, and what each one needs

**Leg 1 — no silicon required, and it is the one that discriminates.** One
commit, two arms differing only in the renderer, on a seven-suite disc:
`Surface pitch, Surface format, Surface clip, Texture perspective, Texture
perspective enable, Null surface, Color Zeta Disable, Texture Framebuffer
Blit`. Model E predicts GL nonzero and Vulkan 0 on `Surface_pitch/Swizzle`
(one `better` in the whole arm); Model H predicts 0 in both (`same`).

It is registered and **not queueable**. `request.sh` has no renderer
selector, the renderer is an `xemu.toml` key, and no `HAKUX_*` variable reads
it. The arms job will therefore skip the registration with "a_ref does not
resolve", which is the right outcome for a prediction nothing can run. The
cheapest unblock is a renderer override the dispatcher can set — an
`xemu.toml` write in `request.sh`, or a `HAKUX_RENDERER` read where the toml
is parsed. The desktop route runs both renderers but the desktop build is
unmeetable on this host (`AGENTS.md`, verified 2026-09-14: no
`libcurl4-openssl-dev`).

**Leg 2 — silicon required, and the existing golden already covers less of it
than #109 assumes.** The current disc has exactly one `Surface_pitch`
capture, `Swizzle`, and its golden *already* answers the headline question at
one point: hardware drew the same image at pitch 512 and pitch 256, so
hardware ignores pitch at the one-half ratio for a power-of-two width. What
silicon adds is the part no capture on the disc can reach:

1. **Extent.** Place a second surface at `colour_offset + pitch * height`,
   inside the region this tree treats as free. Model H says the swizzled
   store occupies `width * height * bpp` and clobbers it; a pitch-extent rule
   says it does not. This is the claim behind all four `pitch * height` sites
   above, and nothing on the disc tests it.
2. **Ratios that are not one half**, e.g. `pitch = 3/4 * width * bpp`, where
   `pitch % bpp == 0` but `pitch / bpp` is not a power of two. Model E's map
   stays well defined; a hardware rule that quantises pitch would not.
3. **`pitch % bpp != 0`**, which `assert(surface->pitch %
   fmt.bytes_per_pixel == 0)` (`gl/surface.c:2851`) says cannot happen.
   Whether silicon accepts it is unknown, and the assert is a crash path if
   it does.

Each of those needs a new `nxdk_pgraph_tests` variant, so the prediction names
the captures by their intended keys rather than pretending they exist. Per
`roles/lane.md` a prediction whose keys match no golden is refused at queue
time — which is correct, and is why leg 2's keys live in the prediction's
prose and not in its `must_not_move`.

## Provenance of the control list

The must-not-move captures are chosen from the two dated cross-renderer
records on file, not guessed:

* #87's comment of 2026-09-18 enumerates **the eighteen captures where GL and
  Vulkan differ** at `0.4.0-j1-368-g8c938792`. No capture in the seven-suite
  disc appears on that list except `Surface_pitch/Swizzle` itself.
* `docs/testing/gl-vs-vulkan-surf1-2026-09-13.tsv` gives per-capture GL and
  Vulkan counts for all 236 captures of `iso_surf1`. Every registered control
  is equal between the renderers there, and the nonzero ones are preferred:
  a control at 0 and 0 shows only that both arms ran.

Six `Surface_clip/rt_*` captures differed on 2026-09-13 and are excluded even
though the #87 investigation records them as repaired to 0, because using a
stale value as a control is how a baseline gets believed twice.

One guard is deliberately left strict. `must_not_move` fails if a capture's
score holds while its bytes move, and across two renderers that can happen
innocently — `Color_zeta_overlap/Swap` is the documented case, tied at 165,447
with different bytes. It is not in this disc, and no score-equal /
byte-different pair is documented for any suite that is. So if the guard fires
on a control, that is **a finding and not an excuse**: two renderers drawing
different pixels at the same distance from a surface golden would deserve its
own row.
