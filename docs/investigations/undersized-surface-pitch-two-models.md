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

## Citations in this document are BY SYMBOL, not by line

`vk/surface.c` moved by about 206 lines between this lane's base and
`master` — every by-line citation in the first draft of this document was
wrong within a day, and one of them (`:858`, offered as "no pitch anywhere")
had come to land inside the deferred CPU swizzle, the one block in the file
that *does* take pitch. That is `3c2f6622c5`'s lesson, "L4's drift, five more
times", committed 67 minutes before this lane registered its prediction and
carrying ten fresh by-line citations into the same file. Functions are named
instead; where a line number appears it is dated and marked as such.

## The one-paragraph derivation

The swizzled (Morton) address computation in `hw/xbox/nv2a/pgraph/swizzle.c`
takes **no pitch**: `generate_swizzle_masks(width, height, depth)` interleaves
the bits of x and y and nothing else, so a destination offset is a function of
`(x, y, log2 width, log2 height, bpp)` alone. Pitch enters one step earlier,
as the row stride of the *linear intermediate* that the CPU download path
builds before swizzling it: the intermediate is written one row at a time at
offset `y * surface->pitch`, and then `swizzle_rect(..., surface->pitch, bpp)`
reads it back at the same stride — `row_pitch` is what `swizzle_box_internal`
adds per source row. When `pitch == width * bpp` those two strides coincide
with hardware's and everything cancels. When `pitch < width * bpp` they do
not: each row's write of `width * bpp` bytes lands at `y * pitch`, so only its
first `pitch` bytes survive (the GL paths overwrite the tail with the next
row; the Vulkan deferred path never copies it, `memcpy_image` copying
`MIN(src_stride, dst_stride)`), and the read then takes `width` pixels from
`y * pitch` — the head of row `y` followed by the head of row `y + 1`. That
yields a closed-form map with no free parameters, which is what makes this a
derivation rather than a fit:

```
Model H  (hardware / "pitch does not enter")
    dest(x, y) = src(x, y)                       for all x, y
    and the surface occupies width * height * bpp bytes, not pitch * height

Model E  (this tree's CPU download path)
    dest(x, y) = src(x, y)                       x <  pitch/bpp
    dest(x, y) = src(x - pitch/bpp, y + 1)       x >= pitch/bpp
```

## WHICH download path. GL has three shapes, not one, and one of them asserts

"The CPU download path" above is three code paths, and an earlier draft of
this document quoted the write from the wrong one:
`dst_row = linear_guest + y * surface->pitch` is
`android_surface_download_depth16_to_guest()` — `#ifdef __ANDROID__`, **depth16
only**, and it cannot run for the A8R8G8B8 colour render target this whole
document is about. The mechanism is right; the citation named a function the
subject surface never reaches. `pgraph_gl_surface_download_to_buffer()`'s
inner `surface_download_to_buffer()` (`gl/surface.c`, the second definition —
the first is the depth16/z24s8 Android block) branches three ways for a
swizzled download, and the difference between them decides whether the arm
measures anything at all:

| path | taken when | at `pitch < width*bpp` |
|---|---|---|
| **A** — Android RGBA8 transfer | `__ANDROID__` **and** `android_surface_uses_rgba8_transfer()`, which is true for `LE_A8R8G8B8` | **Model E.** `android_surface_rgba8_to_guest()` writes `dst_row = dst + y * dst_stride` with `dst_stride = surface->pitch`, then `swizzle_rect(..., surface->pitch, bpp)`. Buffer is `g_malloc(surface->size)`, so in bounds. |
| **B** — generic, unscaled | otherwise, and `surface_scale_factor == 1` | **Model E.** `glo_readpixels(..., scale * surface->pitch, ...)` sets `GL_PACK_ROW_LENGTH = pitch/bpp`, which is *less* than the 128-pixel read width, so GL packs overlapping rows; then the same `swizzle_rect` at `surface->pitch`. |
| **C** — generic, scaled | otherwise, and `surface_scale_factor != 1` | **`assert(surface->pitch >= surface->width * surface->fmt.bytes_per_pixel)` — abort.** The assert is keyed on this lane's own subject. |

Path C is not hypothetical. `surface_download()` calls
`surface_download_to_buffer(d, surface, /*swizzle=*/true, /*flip=*/false,
/*downscale=*/true, ...)` — `downscale` is `true` unconditionally for every
surface→VRAM download — and the only thing that turns it off is
`downscale &= (pg->surface_scale_factor != 1)` at the top of the function.
Nothing in surface creation forbids the undersized condition:
`populate_surface_binding_entry_sized()` asserts the DMA limit and
`pitch % bpp == 0`, never `pitch >= width * bpp`.

**What each arm therefore runs**, which is what the registration has to pin:

* **Vulkan, either platform** — `download_surface_to_buffer()` takes
  `use_compute_to_swizzle` (`surface->swizzle && bpp == 4 &&
  !depth_stencil`, all true here) and memcpys `width*height*bpp` out of the
  compute swizzle with no pitch anywhere. **Model H by construction.**
* **GL on an Android device** — Path A. Model E, and Path C's assert is
  **unreachable**, because the RGBA8 branch `goto cleanup`s before it for any
  colour format `android_surface_uses_rgba8_transfer()` accepts. Scale factor
  does not matter. (`g_config.display.renderer` selects the NV2A backend on
  Android too; only the *window* is forced GLES, at `ui/xemu.c`.)
* **GL on a desktop build** — Path B **at `surface_scale = 1` only**, which is
  the `config_spec.yml` default. At any other scale the arm aborts inside
  `surface_download_to_buffer` on the `Surface_pitch/Swizzle` capture, which
  is neither model and settles nothing. **Both registered refs pin
  `[display] quality.surface_scale = 1` for exactly this reason.** Without
  that pin the prediction's "either outcome settles it" is false: there is a
  third outcome and the registration did not exclude it.

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
(`populate_surface_binding_entry_sized()`, `gl/surface.c:2872` at 2026-09-19)
already oversizes it, so the last row's overlapping
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
rather than be tuned to fit. Run against what is on file — and the three
bullets are **not** the same kind of evidence, which is the correction this
section needed:

* **Hardware, and it holds.** `Surface_pitch` programs the **same** 128x128
  surface twice, at `SET_SURFACE_PITCH_COLOR` 512 and 256, and **the golden
  is identical across that pair** — recorded in the #87 fix's own comment in
  `pgraph_gl_check_surface_to_texture_compatibility()` (`gl/surface.c:1545`,
  dated 2026-09-19), and it is the observation that killed the pitch reading
  there. Silicon ignores pitch at the one-half ratio for a power-of-two
  width. That **confirms** #109's *hardware* rule at the one point the disc
  can reach; it does not refute it.
* **Our capture, and it discriminates nothing.** "Our capture is identical
  across that pair too, 0 px" and "#87's residual was identical on both
  128-wide quads" are both observations about **the Vulkan capture**, and
  Vulkan is the renderer this document proves is **Model H by construction**.
  `nv2a_issues.toml` #87 is explicit: *"at HEAD, with NO bound, the VULKAN
  renderer reproduces that exact digest unaided … so its capture IS the
  race-free image. GL on the same binary and disc gives 15,360 with a
  different digest every run."* The 10,240 is the Vulkan column of
  `gl-vs-vulkan-surf1-2026-09-13.tsv`; GL's is 15,360. On a Model-H path the
  two quads are identical **by construction** — which is exactly what was
  seen. **The absence of the asymmetry is entailed by the path, not evidence
  against the rule.**
* The two models **agree exactly** (0 of 16,384) on the pitch-512 member, by
  construction: at the exact pitch the two strides coincide. So that member
  could never have discriminated either.

**So the falsifier returns neither "refuted" nor "confirmed": it returns
UNMEASURED, and the difference is the instruction the board gets.** Model E
predicts an asymmetry between the pitch-512 and pitch-256 quads *on a path
that uses pitch*. Every clean number on this capture is from the path that
does not. Nothing on file has ever looked. What is true and what is not:

* **True:** #109's hardware rule is right about hardware, at the one ratio
  the golden reaches, and is confirmed rather than refuted by it.
* **True:** #87 is closed on its own subject with no free parameters — one
  uncancelled Morton transform through the surface-to-texture fast path,
  100.0000% over both affected quadrants against a 68.75% identity control,
  inverting the map made the capture byte-identical to the golden, and
  `c807592d02` measured `Surface_pitch/Swizzle` 10,240 -> 0 on device.
* **Unsupported, and the reason is absence of measurement rather than
  contrary measurement:** #109's claim to be *a lead on #87*. Do not close
  that lead on the strength of this document. The GL arm registered here is
  the measurement that has never been taken, and the cross-renderer table
  this document already cites is the opposite of reassuring — GL 15,360
  against Vulkan 10,240 on 2026-09-13, i.e. the two renderers **do** differ
  on this exact capture.

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
  surface.** `download_surface_to_buffer()` (`vk/surface.c`) initialises
  `use_compute_to_swizzle = surface->swizzle && bytes_per_pixel == 4 &&
  !use_compute_to_convert_depth_stencil_format`, true for exactly this
  surface, and that branch `memcpy`s `width * height * bpp` bytes out of the
  compute swizzle with no pitch anywhere. Every clean number on
  `Surface_pitch/Swizzle` is Vulkan. **A Vulkan 0 is consistent with both
  models and discriminates neither.**
* **GL has no compute path**, so `pgraph_gl_surface_download_to_buffer`
  applies Model E to every swizzled download — Path A on an Android device,
  Path B on an unscaled desktop build, and Path C's assert otherwise; see the
  path table above. The only GL numbers on this capture (13,160 / 14,848 /
  15,360) predate `c807592d02` and are race-affected. GL after the fix is
  unmeasured — and the fix is exactly what routes GL out of the fast path and
  into the pitch-using code.
* **Vulkan's *deferred* download also applies Model E**, and
  `download_surface_record_deferred()` sets `dl->use_compute_to_swizzle =
  false` unconditionally, so the same surface gets a different layout
  depending on which of the two routes serves it.
  `pgraph_vk_complete_staged_downloads()` sizes its intermediate
  `g_malloc(dl->pitch * dl->height)` rather than from `surface->size`, so the
  `swizzle_rect(..., dl->pitch, ...)` beside it reads its last row
  `width * bpp` wide from `(height-1) * pitch` and runs `width * bpp - pitch`
  bytes past the allocation — 256 bytes, 64 pixels, for the 128x128 pitch-256
  case. Bounded, read-only, and it lands in the guest surface's last-row
  Morton cells. **Recommend a tracker row.** What is *not* established, and is
  the missing step: that this route is reached for a swizzled
  undersized-pitch surface on the current disc. There is no guard excluding
  swizzled surfaces from `download_surface_record_deferred`, but "not
  excluded" is not "reached".
* **`pitch * height` is used as the surface's extent in seventeen places**
  where Model H says the extent is `width * height * bpp`. An earlier draft
  said "four" and the prediction said "seven"; both were short, and both were
  hand-counted, so this document gives the command instead of a number that
  can drift out of step with the code:

  ```
  git grep -n 'pitch \* .*height' -- hw/xbox/nv2a/pgraph/gl/surface.c \
                                      hw/xbox/nv2a/pgraph/vk/surface.c
  ```

  On `master` at 2026-09-19 that returns fourteen sites in `vk/surface.c` and
  three in `gl/surface.c`, in eight functions:

  | function | file | what the extent is used for |
  |---|---|---|
  | `populate_surface_binding_entry_sized()` | gl | the permissive DMA-limit assert |
  | `surface_download()` | gl | **two** `memory_region_set_client_dirty` calls |
  | `populate_surface_binding_target_sized()` | vk | the permissive DMA-limit assert |
  | `download_surface_record_deferred()` | vk | `surface_vram_written` under-reports — a shelved overlapping surface is not marked `vram_newer` |
  | `pgraph_vk_complete_staged_downloads()` | vk | the `g_malloc` above, plus **two** dirty-range calls |
  | `pgraph_vk_download_surface_complete_deferred()` | vk | **two** dirty-range calls |
  | `download_surface()` | vk | `surface_vram_written` **and two** dirty-range calls — the *synchronous* path, i.e. the same defect as the deferred one, on the route this document elsewhere calls Model H by construction |
  | `pgraph_vk_process_pending_downloads()` | vk | **two** dirty-range calls |
  | `pgraph_vk_download_dirty_surfaces()` | vk | **two** dirty-range calls |

  For an undersized pitch every one of these **under-reports by the missing
  half**: two permissive DMA-limit asserts, two `surface_vram_written` calls
  that leave a shelved overlapping surface unmarked as `vram_newer`, and
  **twelve** `memory_region_set_client_dirty` calls — ten in `vk/surface.c`,
  two in `gl/surface.c` — whose dirty range misses the second half of what
  was written. The prediction's "the four dirty-range calls" was short by
  eight. Anyone fixing this should run the
  grep rather than work from the table: **the table is dated, the grep is
  not.** None of it is reachable by the current disc, which is why it is the
  hardware leg's job.

## The two legs, and what each one needs

**Leg 1 — no silicon required, and it is the one that discriminates.** One
commit, two arms differing only in the renderer, on an **eight-suite** disc:
`Surface pitch, Surface format, Surface clip, Texture perspective, Texture
perspective enable, Null surface, Color Zeta Disable, Texture Framebuffer
Blit`. Model E predicts GL nonzero and Vulkan 0 on `Surface_pitch/Swizzle`
(one `better` in the whole arm); Model H predicts 0 in both (`same`).

**Both refs pin `[display] quality.surface_scale = 1`**, which is the
`config_spec.yml` default, and the registration says so. Unpinned, a desktop
GL arm at any other scale takes Path C and aborts on the assert — a third
outcome that settles neither model and that the first draft of this
registration did not exclude. On an Android device arm the pin is
redundant but harmless: Path A returns before the assert.

It is registered and **not queueable**. `request.sh` has no renderer
selector, the renderer is an `xemu.toml` key, and no `HAKUX_*` variable reads
it. The arms job will therefore skip the registration with "a_ref does not
resolve", which is the right outcome for a prediction nothing can run. The
cheapest unblock is a renderer override the dispatcher can set — an
`xemu.toml` write in `request.sh`, or a `HAKUX_RENDERER` read where the toml
is parsed; whatever sets the renderer should set the scale in the same
place, for the reason above. The desktop route runs both renderers but the
desktop build is unmeetable on this host (`AGENTS.md`, verified 2026-09-14:
no `libcurl4-openssl-dev`).

**Leg 2 — silicon required, and the existing golden already covers less of it
than #109 assumes.** The current disc has exactly one `Surface_pitch`
capture, `Swizzle`, and its golden *already* answers the headline question at
one point: hardware drew the same image at pitch 512 and pitch 256, so
hardware ignores pitch at the one-half ratio for a power-of-two width. What
silicon adds is the part no capture on the disc can reach:

1. **Extent.** Place a second surface at `colour_offset + pitch * height`,
   inside the region this tree treats as free. Model H says the swizzled
   store occupies `width * height * bpp` and clobbers it; a pitch-extent rule
   says it does not. This is the claim behind **every** `pitch * height` site
   the grep above returns, and nothing on the disc tests it.
2. **Ratios that are not one half**, e.g. `pitch = 3/4 * width * bpp`, where
   `pitch % bpp == 0` but `pitch / bpp` is not a power of two. Model E's map
   stays well defined; a hardware rule that quantises pitch would not.
3. **`pitch % bpp != 0`**, which `assert(surface->pitch %
   fmt.bytes_per_pixel == 0)` in `populate_surface_binding_entry_sized()`
   says cannot happen. Whether silicon accepts it is unknown, and the assert
   is a crash path if it does.

**Two asserts are crash paths here, and the second is keyed on this lane's
own subject.** The one above fires on `pitch % bpp != 0`, which no test
programs today. The one in `surface_download_to_buffer()` —
`assert(surface->pitch >= surface->width * surface->fmt.bytes_per_pixel)`,
Path C in the table above — fires on `pitch < width * bpp` **itself**, the
entire subject of this document, on any desktop GL run with
`surface_scale != 1`. Nothing in surface creation forbids the condition, so
this is not a leg-2 unknown at all: it is reachable today, from the arm this
lane registers, and it is why both refs pin the scale.

Each of those needs a new `nxdk_pgraph_tests` variant, so the prediction names
the captures by their intended keys rather than pretending they exist. Per
`roles/lane.md` a prediction whose keys match no golden is refused at queue
time — which is correct, and is why leg 2's keys live in the prediction's
prose and not in its `must_not_move`.

## Provenance of the control list

The must-not-move captures are chosen from the two dated cross-renderer
records on file, not guessed:

* #87's comment of 2026-09-18 enumerates **the eighteen captures where GL and
  Vulkan differ** at `0.4.0-j1-368-g8c938792`. No capture in the eight-suite
  disc appears on that list except `Surface_pitch/Swizzle` itself.
* `docs/testing/gl-vs-vulkan-surf1-2026-09-13.tsv` gives per-capture GL and
  Vulkan counts for all 236 captures of `iso_surf1`. Every registered control
  is equal between the renderers there, and the nonzero ones are preferred:
  a control at 0 and 0 shows only that both arms ran.

Six `Surface_clip/rt_*` captures differed on 2026-09-13 and are excluded even
though the #87 investigation records them as repaired to 0, because using a
stale value as a control is how a baseline gets believed twice.

**Four of the fourteen controls are `(gl 0, vk 0)`, in tension with the rule
just stated, and all four are forced rather than careless.**
`Null_surface` and `Color_Zeta_Disable` have **exactly one capture each** on
this disc, `XemuBug893` and `MaskOff_ZB`, and both are 0/0 — the suite offers
nothing else. `Surface_clip` has 47 captures and **not one nonzero
cross-renderer-equal capture among them**: its only nonzero rows are the six
`rt_*` that *differ* between the renderers and are excluded above. So a
`Surface_clip` control is either 0/0 or stale, and 0/0 was the right side of
that to fall on. The rule stands as written — prefer nonzero — and these four
are the cases where the disc does not offer one.

**`must_not_move` is bit-identical across two different renderers, and that is
the leg most likely to fire first.** `ab_compare.py` treats `must_not_move` as
byte equality, with the byte leg firing on `pixels_moved_attributable`; ten of
the fourteen controls are nonzero-but-score-equal cross-renderer (4,419 …
32,667), and score equality in the 2026-09-13 tsv is **not** evidence of byte
equality. The strictness is deliberate — see the paragraph below — but the
expectation is registered here rather than discovered on the day: **a first
run may come back with a control violation that masks the discrimination, and
the correct response is to re-scope those ten to `must_not_regress` and
re-register, not to explain the violation away.** Which of the two it is
depends on the capture, and that judgement is the next reader's.

One guard is deliberately left strict. `must_not_move` fails if a capture's
score holds while its bytes move, and across two renderers that can happen
innocently — `Color_zeta_overlap/Swap` is the documented case, tied at 165,447
with different bytes. It is not in this disc, and no score-equal /
byte-different pair is documented for any suite that is. So if the guard fires
on a control, that is **a finding and not an excuse**: two renderers drawing
different pixels at the same distance from a surface golden would deserve its
own row.
