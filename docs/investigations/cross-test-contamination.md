# Tests that render a previous test's image

**Status:** confirmed on device, 2026-09-08. Root cause not yet located.

## Summary

38% of failing pgraph tests are not rendering the right thing *wrong* — they
are rendering *something else entirely*, namely the output of a test that ran
before them. This was invisible for as long as results were scored only against
each test's own golden, because both faults present identically as "N pixels
differ".

Of 3,132 tests in the baseline sweep, 864 fail. Of those 864, **328 reproduce a
different test's golden more closely than their own**, and in **263** of those
cases the impersonated test is *itself* correct.

This means a substantial part of the issue tracker is measuring one bug, not
twelve. Several filed defects — DXT decode (#6), overlapping `Image_blit` (#7),
`Window_clip` (#11) — are wholly or partly this.

## How it was found

`docs/testing/crossmatch.py`. For every failing test it asks whether some other
golden *in the same suite* fits our output better than the test's own golden
does. That question is cheap and it should be asked of every sweep.

```sh
python3 docs/testing/crossmatch.py results_final --goldens goldens/results
```

## What is proven

Reproduced on device, same build, same session, two purpose-built discs:

| disc | tests enabled | `DXT1_plasma` vs own golden | vs `DXT1_plasma_alpha` |
|---|---|---|---|
| `iso-pair` | `DXT1_plasma_alpha`, `DXT1_plasma` | **14.86** | 0.79 |
| `iso-solo` | `DXT1_plasma` only | **0.36** ✓ | 15.35 |

Mean absolute per-subpixel error. The two runs wrote different bytes for that
test. **One sibling test running first is sufficient to corrupt it**, and the
test is correct when it runs alone.

The fault is specifically in *texture* data, not in the frame:

| region of the failing frame | vs own golden | vs sibling's golden |
|---|---|---|
| the textured quad | 69.65 | **1.65** |
| background and the on-screen text naming the test | **0.00** | 0.56 |

The frame furniture — including the text that spells out which test this is —
matches its own golden *pixel-exactly*. The renderer knew which test it was
drawing and drew everything correctly except the texture it sampled. That rules
out a stale framebuffer readback, an off-by-one frame, and mislabelled output.

## The shape of it

The impersonated test is almost always a sibling differing by **one state bit**,
and the sibling that "wins" is the one that runs first:

| suite | test | renders instead |
|---|---|---|
| `W_param` | `ff_w_zero__quad` | `ff_w_zero__quad_tex_persp` |
| `Texture_perspective` | `tex_tex_pers_n_quad` | `tex_tex_pers_y_quad` |
| `Window_clip` | `rI_x0y0_w0h0-…` (inclusive) | `rE_x0y0_w0h0-…` (exclusive) |
| `Fog_gen` | `FogGen_VS-exp2-radial` | `FogGen_VS-exp2-planar` |
| `Texture_shadow_comparator` | `3F16f_…` | `2F16f_…` |
| `Texture_DXT` | `DXT1_plasma` | `DXT1_plasma_alpha` |

That is the signature of a cache whose key does not distinguish the two states,
so whichever variant is compiled or uploaded first is reused for the second.

Distribution across suites (328 total):

```
44 Texture_cubemap     26 Window_clip     17 Fog_gen         14 Image_blit
34 Line_width          20 W_buffering     16 Texture_shadow  12 Attrib_carryover
30 Depth_buffer        18 Fog_param       15 Blend_tests     11 Depth_buffer_ff
                                          15 Texture_signed  … 14 more suites
```

## Candidate mechanisms

Not yet distinguished. The DXT case is texture data, but `Window_clip` and
`Fog_gen` differ by raster/shader state and cannot be explained by the texture
cache — there may be more than one cache at fault, sharing a pattern.

For the texture path specifically, `hw/xbox/nv2a/pgraph/vk/texture.c` gates the
content comparison behind the VRAM dirty flag:

```c
uint64_t content_hash = 0;
if (!surface_to_texture && possibly_dirty) {
    content_hash = fast_hash(texture_data, texture_length);
}
...
bool vram_changed = possibly_dirty && content_hash != snode->hash;
```

so when `possibly_dirty` is false the texture is never re-hashed and never
re-uploaded. Two things can clear it wrongly:

1. **Per-frame caching of the dirty result** (added post-fork in `21f7d7c3e5`,
   2026-03-01):

   ```c
   bool vram_confirmed_clean =
       snode->dirty_check_frame == pg->frame_time && !snode->dirty_check_result;
   if (vram_confirmed_clean) { possibly_dirty = false; }
   ```

   `pg->frame_time` advances only on `NV097_FLIP_INCREMENT_WRITE`, so any
   texture re-uploaded to the same address within one flip interval is never
   re-read.

2. **`check_texture_dirty` uses `memory_region_test_and_clear_dirty`**, which
   *consumes* the dirty bit over a page-aligned range. The first caller to ask
   clears it for everyone, so a second texture sharing those pages sees clean.

## Why this matters more than its issue count

The 328 are concentrated in exactly the suites whose issues read as broad
rendering failures, which has made several defects look far larger and more
fundamental than they are. `DXT1_plasma` is not a broken DXT decoder; it is a
correct decoder handed the wrong bytes. Until this is fixed, any measurement
that runs more than one test per suite understates accuracy by an unknown
margin, and per-test results are order-dependent — which is
[#15](https://github.com/jreinach-alt/hakuX/issues/15), very likely the same
bug seen from the other side.

## Next

1. Determine whether the non-texture suites (`Window_clip`, `Fog_gen`) share
   one mechanism or need separate work — run the same pair/solo isolation on
   `Window_clip` `rI_`/`rE_`.
2. For the texture path, test hypothesis 1 by removing the per-frame dirty
   cache and re-running the pair disc. It is a small, revertible change and the
   pair disc gives a two-minute answer.
3. Re-run the full sweep afterwards. The headline accuracy number
   (1,110/2,702) is a floor, not a measurement, while this is outstanding.
