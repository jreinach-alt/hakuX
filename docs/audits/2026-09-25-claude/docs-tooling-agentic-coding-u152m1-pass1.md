# Audit pass 1 -- PR #247 (lane.remote, #109): stage a swizzled surface at width * bpp

Auditor: `[job.cloud]`, 2026-09-25. Head audited: `669e6ebd`.
Diff: `hw/xbox/nv2a/pgraph/gl/surface.c` (+45 -14), `nv2a_index.json`
(line-number regeneration), the prediction file, and `docs/lanes/remote/`
notes and script.

**Result: no HIGH, no MEDIUM, no LOW against the diff.** Two observations
about code this PR does not change and says it does not change are recorded
below; they are not findings on this diff. Nothing is left for pass 2 to verify,
so the PR goes straight to `fold-ready`.

## What was checked

1. **Every buffer the new stride writes into is big enough.** The new stride
   `width * bpp` can be larger than `pitch`, so each buffer that used to be
   written at `pitch` stride now takes up to `width * bpp * height` bytes. Each
   one is sized by `surface->size`, and `surface.c:2903` sets
   `size = height * MAX(pitch, width * bpp)` (this is on master already, at
   `:2872`). So:
   - desktop `swizzle_buf = g_malloc(surface->size)` (`:2477`): fits;
   - `pg->scale_buf`, `factor^2 * size` (`:2482`), read at
     `factor * guest_pitch` stride for `factor * height` rows: fits;
   - Android RGBA8 `linear_guest = g_malloc(surface->size)` (`:2446`) and
     depth16 `swizzle_buf = g_malloc(surface->size)` (`:2090`): fit;
   - upload `buf = g_malloc(surface->size)` (`:2688`), which `unswizzle_rect` fills
     at `buf_pitch = width * bpp`: fits;
   - z24s8 `swizzle_buf = g_malloc(output_pitch * output_height)` (`:2272`), with
     `output_pitch` now `output_width * bpp` whenever the surface is swizzled.
     Every row writes `output_width * 4` bytes and z24s8 is 4 bpp, so it fits.
     This closes a heap overflow on master: there a swizzled zeta surface with
     `pitch < width * 4` wrote past a `pitch * height` allocation. The PR body
     says the same.
2. **Linear surfaces are unchanged.** Every new stride is
   `swizzle ? surface_swizzle_linear_pitch(surface) : surface->pitch`, or is
   inside an `if (surface->swizzle)`. On the linear path `guest_pitch ==
   surface->pitch` at each site, so the readback stride, the downscale loop and
   the assert are byte-for-byte the old expressions. In the upload path
   `buf_pitch` stays `surface->pitch` for linear surfaces, and the repack
   condition `buf_pitch != optimal_pitch` is the old condition.
3. **The upload repack goes away for swizzled surfaces**, because `buf_pitch ==
   optimal_pitch`. That is correct: `unswizzle_rect` has already produced a
   tight buffer.
4. **The downscale assert** is now trivially true on the swizzled path and still
   guards linear surfaces. That is intended, and the scale-2 leg shows master
   aborting there (exit 134) while B completes.
5. **No staging site was missed.** A grep over `gl/` for `swizzle_rect` and
   `unswizzle_rect` finds five call sites in `surface.c` (`:2109`, `:2302`,
   `:2454`, `:2515`, `:2689`) and all five are converted. The only other hit is
   `texture.c:1163`, a texture unswizzle at the texture's own pitch, which is
   not a surface staging site.
6. **Consistency of `bpp`.** `swizzle_rect` and `surface_swizzle_linear_pitch`
   both use `surface->fmt.bytes_per_pixel`, so the stride and the swizzle agree
   at every site.
7. **Evidence.** The registered arm passed 75/75 on desktop GL. The one mover is
   the registered one (Swizzle −4,032, q3's Model E component only), and the
   other 72 captures are byte-identical. The legs were posted on #109 before the
   code existed, and the later amendment changes routing only (it adds `title`).
   CI shows build ×2 and check green on `669e6ebd`, and the PR is `MERGEABLE`.
8. **Index diff** is a line-number shift in `gl/surface.c` locs, consistent with
   +29 lines above those sites.

## Observations, not findings on this diff

- **O1: the dirty extent is too short when the pitch is undersized.**
  `surface_download` marks `pitch * height` dirty (`:2557`, `:2560`), but
  `swizzle_rect` writes `width * bpp * height` swizzled bytes into guest VRAM.
  When `pitch < width * bpp`, the tail is written without being marked
  `DIRTY_MEMORY_NV2A_TEX`, so a texture bound over those bytes may keep a stale
  cache entry. Master has the same behaviour, and the PR names the extent sites
  as #109's open silicon question, so they are deliberately out of scope. This
  belongs to #109's next step, not to a remediation here.
- **O2: the Android branches only compile.** The Android RGBA8, depth16 and
  z24s8 branches were syntax-checked but nothing ran them, and no fleet arm can
  run them (the fleet APK uses Vulkan). The z24s8 change is the one with a
  safety effect, and by the size argument in (1) it removes an overflow rather
  than adding one.
