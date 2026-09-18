/*
 * Geforce NV2A PGRAPH Vulkan Renderer
 *
 * Copyright (c) 2024 Matt Borgerson
 *
 * Based on GL implementation:
 *
 * Copyright (c) 2012 espes
 * Copyright (c) 2015 Jannik Vogel
 * Copyright (c) 2018-2024 Matt Borgerson
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#include "hw/xbox/nv2a/nv2a_int.h"
#include "hw/xbox/nv2a/debug.h"
#include "renderer.h"

#if defined(__aarch64__)
#include <arm_neon.h>

/*
 * Exact round-to-nearest division by NV_BETA's 0x7f80 scale.
 *
 * BLEND_AND forms V = src*beta + dst*(0x7f80 - beta) and silicon returns
 * V / 0x7f80 rounded to nearest, not truncated. 0x7f80 is 255 << 7, and
 * floor(floor(x / 128) / 255) == floor(x / 32640), so shift the 128 out
 * first -- the remainder W is then below 2^16, where W / 255 is exact as
 * (W * 0x8081) >> 23.
 *
 * This replaces a >> 15 that stood in for the divide. 32768 is 0.4% larger
 * than 32640, so that form can only ever land low: checked over all 2^24
 * (src, dst, beta) triples it is short by exactly one on 8,388,608 of them
 * and high on none, which is the sign signature this suite shows.
 */
static inline uint16x4_t blend_and_div(uint32x4_t prod_s, uint32x4_t prod_d)
{
    uint32x4_t v = vaddq_u32(vaddq_u32(prod_s, prod_d), vdupq_n_u32(0x3FC0));
    uint32x4_t w = vshrq_n_u32(v, 7);
    return vmovn_u32(vshrq_n_u32(vmulq_u32(w, vdupq_n_u32(0x8081)), 23));
}
#endif

static void perform_blit(int operation, uint8_t *source, uint8_t *dest,
                         size_t width, size_t height, size_t width_bytes,
                         size_t source_pitch, size_t dest_pitch,
                         unsigned int bytes_per_pixel, BetaState *beta)
{
    if (operation == NV09F_SET_OPERATION_SRCCOPY) {
        for (unsigned int y = 0; y < height; y++) {
            memmove(dest, source, width_bytes);
            source += source_pitch;
            dest += dest_pitch;
        }
    } else if (operation == NV09F_SET_OPERATION_BLEND_AND) {
        /*
         * This branch hard-codes 32bpp: it walks `width` PIXELS and indexes
         * s[x * 4 + ch], and its NEON body loads and stores 16 bytes per four
         * pixels. The caller admits NV062_SET_COLOR_FORMAT_LE_Y8 (1 byte) and
         * ..._LE_R5G6B5 (2), so a narrow-format blend walked twice the
         * intended extent per row -- four times on Y8 -- spilling into the
         * next row and, on the last row, past dest_offset + dest_size.
         * SRCCOPY above is format-correct because it memmoves width_bytes;
         * only this branch converts pixels to bytes, and it did so with a
         * constant. bytes_per_pixel was already threaded into
         * perform_blit_tiled() and simply never reached here.
         *
         * The overrun is BOUNDED, and the bound is worth stating because it
         * is the difference between this and a host-memory escape. row_pixels
         * is clamped to MIN(source_pitch, dest_pitch) / bytes_per_pixel in
         * pgraph_vk_image_blit(), so the walk is at most 4 pitches where one was
         * intended: 3 extra pitches at Y8, 1 at R5G6B5, 0 at 32bpp. Nothing
         * downstream CATCHES it -- nv_dma_map()'s end-of-object assert is
         * commented out (nv2a.c:96), pgraph_vk_image_blit() checks only
         * dest_offset < dest_dma_len rather than dest_offset + extent, and the
         * surplus falls outside both the range given to
         * pgraph_vk_download_surfaces_in_range_if_dirty() and the later
         * invalidate -- but not catching it is not the same as it being
         * open-ended. Corruption beyond the blit rect, not a host-memory
         * escape, which is the limit the finding's own author stated.
         *
         * Those two facts sit a few lines apart and disagree: the clamp
         * divides by bytes_per_pixel and this loop indexes by a constant 4.
         * THE CLAMP IS AUTHORITATIVE -- `width` here is a count of
         * destination-format pixels, and the indexing is the side that is
         * wrong. Refusing rather than rescaling is what keeps it that way; a
         * fix that instead treated `width` as 32bpp pixels would have made the
         * indexing authoritative and left max_row_pixels computing the wrong
         * clamp.
         *
         * Refusing rather than guessing, which is what pgraph_vk_solid_line()
         * below already does for the identical question, and what gl/blit.c
         * does after b9d845d316. A correct 16bpp blend must unpack 5/6/5,
         * blend and repack, and the rounding rule for that repack is not
         * established by anything measured here -- the 2^24 exhaustive behind
         * this blend's divide covers 8-bit channels only. Inventing one would
         * put an unmeasured rule into this path.
         *
         * Soft guard, not an assert: a guest can select a narrow surface
         * format and issue a blend blit, so this is reachable guest state
         * rather than an internal invariant -- the same reasoning
         * pgraph_vk_solid_line() records for its own narrow-format return.
         *
         * THE DECIDING GUARD IS IN pgraph_vk_image_blit(), before any surface
         * bookkeeping is committed; this one is the defensive backstop, so no
         * future caller can reach the 32bpp indexing by another route. Both
         * exist on purpose. It is silent because the entry guard has already
         * warned on every path that can currently get here, and a second warn
         * for one event would misreport it as two.
         *
         * All 20 ImgBlt_BLENDAND_* captures in the suite are XRGB or ZRGB,
         * both 32bpp, so no arm on this fleet can reach either guard with a
         * narrow format; the entry warn is how it becomes visible if a title
         * does. stderr is pumped onto logcat under tag hakuX-stderr
         * (android/app/src/main/cpp/xemu_android.cpp), so a plain fprintf is
         * visible on the platform that ships. Audit HIGH, issue #84,
         * pre-existing on both renderers.
         *
         * ONE EXCEPTION to `width` counting destination-format pixels, and it
         * is the one place in this file where the byte count and the pixel
         * count are not two views of the same number: perform_blit_tiled()
         * passes `chunk / bytes_per_pixel` as width and `chunk` as
         * width_bytes, so an unaligned dest_offset (pgraph.c:2024 masks with
         * 0x07FFFFFF and does not align) can truncate the division and leave
         * the two disagreeing. width can only SHRINK there, so it is a wrong
         * picture and never an overrun, and it needs a valid GPU tile plus a
         * blit that overruns it. Pre-existing; audit LOW L2, issue #84.
         */
        if (bytes_per_pixel != 4) {
            return;
        }

        uint32_t max_beta_mult = 0x7f80;
        uint32_t beta_mult = beta->beta >> 16;
        /*
         * beta_mult <= max_beta_mult is enforced in a DIFFERENT MODULE and
         * nothing here named the dependency. NV012_SET_BETA stores
         * `parameter & 0x7f800000` (pgraph/pgraph.c:1951); those are the only
         * two write sites for beta->beta, and BetaState appears in no vmstate
         * description, so neither a guest nor a savestate can exceed it. That
         * makes it an internal invariant rather than guest input, which is
         * what assert() is for -- and nothing in this function's control flow
         * implies it, so the assert can actually fire if the mask changes.
         *
         * It is load-bearing twice:
         *
         *   - inv_beta_mult below would underflow. The NEON path narrows it to
         *     uint16 while the scalar path uses it unmasked, so the two would
         *     not merely be wrong, they would be wrong DIFFERENTLY -- and the
         *     scalar result could then exceed 255 and truncate in the uint8_t
         *     store.
         *   - it bounds the dividend. Today, with a plain division, that only
         *     keeps the result inside the uint8_t store and the headroom is
         *     large -- the sum cannot exceed 8,339,520 against 2^32, about
         *     515x. The narrow margin belongs to the RECIPROCAL form the held
         *     0x7f80 fix introduces (issue #38), where the operand must stay
         *     below 2^16: largest reachable 65,152 against a first
         *     disagreement at 66,299, 1.76% of headroom, and the first failure
         *     a silently wrong pixel rather than a trap. So the tight bound is
         *     a property of that trick and not of the problem; gl/blit.c
         *     divides plainly and has no such precondition at all.
         *
         * pgraph.c's own comment there -- "only 8 fractional bits are actually
         * implemented in hardware" -- signposts the world where someone widens
         * the mask if a capture says otherwise. One step past it,
         * beta_mult = 0x8000, gives inv_beta_mult = 0xFFFFFF80, which the NEON
         * path narrows to 65,408 and which drives the divide's operand to
         * 195,712 -- past both thresholds. Audit MEDIUM M1, issue #84.
         */
        assert(beta_mult <= max_beta_mult);
        uint32_t inv_beta_mult = max_beta_mult - beta_mult;

        for (unsigned int y = 0; y < height; y++) {
            uint8_t *s = source;
            uint8_t *d = dest;
            unsigned int x = 0;

#if defined(__aarch64__)
            /* NEON: process 4 pixels (16 bytes) at a time.
             * Use 16-bit intermediate to avoid overflow:
             * max value = 255 * 0x7f80 = 0x7f_7f80 fits in u32,
             * but we use vmull for u8×u16 → u32 lane-wise. */
            uint16x8_t v_beta = vdupq_n_u16((uint16_t)beta_mult);
            uint16x8_t v_inv  = vdupq_n_u16((uint16_t)inv_beta_mult);
            for (; x + 4 <= width; x += 4) {
                uint8x16_t src_px = vld1q_u8(s + x * 4);
                uint8x16_t dst_px = vld1q_u8(d + x * 4);

                /* Low 8 pixels (first 2 RGBA pixels) */
                uint16x8_t s_lo = vmovl_u8(vget_low_u8(src_px));
                uint16x8_t d_lo = vmovl_u8(vget_low_u8(dst_px));
                uint32x4_t prod_s_lo0 = vmull_u16(vget_low_u16(s_lo), vget_low_u16(v_beta));
                uint32x4_t prod_d_lo0 = vmull_u16(vget_low_u16(d_lo), vget_low_u16(v_inv));
                uint16x4_t res_lo0 = blend_and_div(prod_s_lo0, prod_d_lo0);

                uint32x4_t prod_s_lo1 = vmull_u16(vget_high_u16(s_lo), vget_high_u16(v_beta));
                uint32x4_t prod_d_lo1 = vmull_u16(vget_high_u16(d_lo), vget_high_u16(v_inv));
                uint16x4_t res_lo1 = blend_and_div(prod_s_lo1, prod_d_lo1);

                uint8x8_t out_lo = vmovn_u16(vcombine_u16(res_lo0, res_lo1));

                /* High 8 pixels (next 2 RGBA pixels) */
                uint16x8_t s_hi = vmovl_u8(vget_high_u8(src_px));
                uint16x8_t d_hi = vmovl_u8(vget_high_u8(dst_px));
                uint32x4_t prod_s_hi0 = vmull_u16(vget_low_u16(s_hi), vget_low_u16(v_beta));
                uint32x4_t prod_d_hi0 = vmull_u16(vget_low_u16(d_hi), vget_low_u16(v_inv));
                uint16x4_t res_hi0 = blend_and_div(prod_s_hi0, prod_d_hi0);

                uint32x4_t prod_s_hi1 = vmull_u16(vget_high_u16(s_hi), vget_high_u16(v_beta));
                uint32x4_t prod_d_hi1 = vmull_u16(vget_high_u16(d_hi), vget_high_u16(v_inv));
                uint16x4_t res_hi1 = blend_and_div(prod_s_hi1, prod_d_hi1);

                uint8x8_t out_hi = vmovn_u16(vcombine_u16(res_hi0, res_hi1));

                /* Preserve alpha from destination (blend only RGB) */
                uint8x16_t result = vcombine_u8(out_lo, out_hi);
                /* Restore original alpha bytes at positions 3,7,11,15 */
                result = vbslq_u8(
                    (uint8x16_t){0,0,0,0xFF, 0,0,0,0xFF, 0,0,0,0xFF, 0,0,0,0xFF},
                    dst_px, result);
                vst1q_u8(d + x * 4, result);
            }
#endif
            /* Scalar fallback for remaining pixels. Rounds to nearest for the
             * same reason the NEON path above does -- truncating here is low
             * by one on 8,164,890 of the 2^24 (src, dst, beta) triples and
             * high on none. This is the whole path on non-aarch64. */
            for (; x < width; x++) {
                for (unsigned int ch = 0; ch < 3; ch++) {
                    uint32_t a = s[x * 4 + ch] * beta_mult;
                    uint32_t b = d[x * 4 + ch] * inv_beta_mult;
                    d[x * 4 + ch] =
                        (a + b + max_beta_mult / 2) / max_beta_mult;
                }
            }
            source += source_pitch;
            dest += dest_pitch;
        }
    } else {
        fprintf(stderr, "Unknown blit operation: 0x%x\n", operation);
        assert(false && "Unknown blit operation");
    }
}

static void patch_alpha(uint8_t *dest, size_t width_pixels, size_t height,
                        size_t dest_pitch, uint8_t alpha_val)
{
    for (unsigned int y = 0; y < height; y++) {
        uint8_t *d = dest;
        unsigned int x = 0;
#if defined(__aarch64__)
        uint8x16_t v_alpha = vdupq_n_u8(alpha_val);
        for (; x + 4 <= width_pixels; x += 4) {
            uint8x16_t px = vld1q_u8(d + x * 4);
            /* Set alpha bytes at positions 3,7,11,15 */
            px = vbslq_u8(
                (uint8x16_t){0,0,0,0xFF, 0,0,0,0xFF, 0,0,0,0xFF, 0,0,0,0xFF},
                v_alpha, px);
            vst1q_u8(d + x * 4, px);
        }
#endif
        for (; x < width_pixels; x++) {
            d[x * 4 + 3] = alpha_val;
        }
        dest += dest_pitch;
    }
}

/*
 * A GPU tile does not only bound a blit, it changes where the bytes land.
 *
 * Hardware remaps addresses inside a tiled region so that a rectangle of the
 * surface is contiguous in memory. Because every consumer -- scanout, texture
 * fetch, the CPU aperture -- goes through the same remap, the shuffle is
 * normally invisible, and treating tiled memory as linear (which is what we do
 * everywhere else) gives the right answer. It stops being invisible the moment
 * data is written through a tile and read back after that tile has been
 * reassigned, which is exactly what Image blit's BlitBeyondWidth does.
 *
 * The layout below was solved out of that test's golden and reproduces it
 * bit-exactly; docs/investigations/gpu-tile-blit-swizzle.md has the derivation
 * and says which parts are measured and which are not.
 *
 *   - the unit of the layout is 256 bytes x 16 rows = 4096 bytes;
 *   - a band is 16 rows, holding pitch/256 units left to right;
 *   - the unit column is XORed with 1 and with the band parity, so vertically
 *     adjacent units land in opposite halves of a unit pair;
 *   - inside a unit: four 4-row groups, each holding four 64-byte columns,
 *     each holding its four rows in order;
 *   - inside a 64-byte row fragment the four 16-byte chunks are rotated by an
 *     amount fixed by which 4-row group it is: 0, 2, 3, 1.
 */
typedef struct BlitGpuTile {
    bool valid;
    hwaddr base;
    hwaddr limit;
    unsigned int pitch;
} BlitGpuTile;

static BlitGpuTile find_blit_gpu_tile(NV2AState *d, hwaddr addr,
                                      unsigned int fallback_pitch)
{
    BlitGpuTile tile = { false, 0, 0, 0 };
    const uint32_t *regs = d->pfb.regs;

    for (int i = 0; i < NV_NUM_GPU_TILES; ++i) {
        uint32_t base_and_flags = regs[NV_PFB_TILE_BASE_ADDRESS_AND_FLAGS(i)];
        if (!(base_and_flags & NV_PFB_TILE_FLAGS_VALID)) {
            continue;
        }

        hwaddr base = base_and_flags & NV_PFB_TILE_BASE_ADDRESS;
        hwaddr limit = regs[NV_PFB_TILE_LIMIT(i)];
        if (addr < base || addr > limit) {
            continue;
        }

        /*
         * The layout is defined in 256-byte columns, so a pitch that is not a
         * multiple of 256 has no meaning in it. Prefer the tile's own pitch and
         * fall back to the blit's, rather than shuffling bytes by a rule that
         * cannot be justified.
         */
        unsigned int pitch = regs[NV_PFB_TILE_PITCH(i)];
        if (pitch == 0 || (pitch % 256) != 0) {
            pitch = fallback_pitch;
        }
        if (pitch == 0 || (pitch % 256) != 0) {
            continue;
        }

        tile.valid = true;
        tile.base = base;
        tile.limit = limit;
        tile.pitch = pitch;
        break;
    }

    return tile;
}

static hwaddr gpu_tile_swizzle(hwaddr offset, unsigned int pitch)
{
    static const unsigned int kChunkRotate[4] = { 0, 2, 3, 1 };

    unsigned int units_per_band = pitch / 256;
    unsigned int row = offset / pitch;
    unsigned int col = offset % pitch;

    unsigned int band = row / 16;
    unsigned int unit = (col / 256) ^ 1u ^ (band & 1u);
    unsigned int group = (row % 16) / 4;
    unsigned int column = (col % 256) / 64;
    unsigned int line = row % 4;
    unsigned int chunk = ((col % 64) / 16 + 4 - kChunkRotate[group]) % 4;

    return ((hwaddr)(band * units_per_band + unit)) * 4096 + group * 1024 +
           column * 256 + line * 64 + chunk * 16 + (col % 16);
}

/*
 * The swizzle is the identity within a 16-byte chunk, so a run is copied in
 * pieces that stop at every 16-byte boundary. Each piece still goes through
 * perform_blit(), so SRCCOPY and BLEND_AND stay defined in one place.
 */
static void perform_blit_tiled(int operation, uint8_t *source,
                               uint8_t *tile_base, hwaddr dest_offset,
                               const BlitGpuTile *tile, size_t width_bytes,
                               size_t height, size_t source_pitch,
                               size_t dest_pitch, unsigned int bytes_per_pixel,
                               BetaState *beta)
{
    for (size_t y = 0; y < height; y++) {
        hwaddr row_offset = dest_offset + y * dest_pitch;
        size_t done = 0;

        while (done < width_bytes) {
            hwaddr offset = row_offset + done;
            size_t chunk = 16 - (size_t)(offset % 16);
            if (chunk > width_bytes - done) {
                chunk = width_bytes - done;
            }

            perform_blit(operation, source + done,
                         tile_base + gpu_tile_swizzle(offset, tile->pitch),
                         chunk / bytes_per_pixel, 1, chunk, source_pitch,
                         dest_pitch, bytes_per_pixel, beta);
            done += chunk;
        }

        source += source_pitch;
    }
}

static void patch_alpha_tiled(uint8_t *tile_base, hwaddr dest_offset,
                              const BlitGpuTile *tile, size_t width_pixels,
                              size_t height, size_t dest_pitch,
                              uint8_t alpha_val)
{
    size_t width_bytes = width_pixels * 4;

    for (size_t y = 0; y < height; y++) {
        hwaddr row_offset = dest_offset + y * dest_pitch;
        size_t done = 0;

        while (done < width_bytes) {
            hwaddr offset = row_offset + done;
            size_t chunk = 16 - (size_t)(offset % 16);
            if (chunk > width_bytes - done) {
                chunk = width_bytes - done;
            }

            patch_alpha(tile_base + gpu_tile_swizzle(offset, tile->pitch),
                        chunk / 4, 1, 0, alpha_val);
            done += chunk;
        }
    }
}

void pgraph_vk_image_blit(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;
    ContextSurfaces2DState *context_surfaces = &pg->context_surfaces_2d;
    ImageBlitState *image_blit = &pg->image_blit;
    BetaState *beta = &pg->beta;

    {
        extern bool xemu_get_frame_skip(void);
        if (r->frame_skip_active && xemu_get_frame_skip()) {
            return;
        }
    }

    pgraph_vk_surface_update(d, false, true, true);

    /* Log blit into diagnostic capture */
    if (nv2a_dbg_diag_frame_active()) {
        nv2a_diag_log_blit(d, pg);
    }

    assert(context_surfaces->object_instance == image_blit->context_surfaces);

    unsigned int bytes_per_pixel;
    switch (context_surfaces->color_format) {
    case NV062_SET_COLOR_FORMAT_LE_Y8:
        bytes_per_pixel = 1;
        break;
    case NV062_SET_COLOR_FORMAT_LE_R5G6B5:
        bytes_per_pixel = 2;
        break;
    case NV062_SET_COLOR_FORMAT_LE_A8R8G8B8:
    case NV062_SET_COLOR_FORMAT_LE_X8R8G8B8:
    case NV062_SET_COLOR_FORMAT_LE_X8R8G8B8_Z8R8G8B8:
    case NV062_SET_COLOR_FORMAT_LE_Y32:
        bytes_per_pixel = 4;
        break;
    default:
        fprintf(stderr, "Unknown blit surface format: 0x%x\n",
                context_surfaces->color_format);
        assert(false);
        break;
    }

    /*
     * BLEND_AND is implemented for 32bpp destinations only -- see the long
     * comment in perform_blit(). REFUSE HERE, AT THE ENTRY, and not only in
     * the leaf, because by the time perform_blit() runs this function has
     * already committed the destination surface's bookkeeping to a write that
     * is about to not happen: the surf_dest block below clears
     * download_pending and draw_dirty on a full-surface blit -- discarding
     * whatever the GPU rendered and had not yet written back -- sets
     * upload_pending, so the VkImage reloads from VRAM nobody wrote, and the
     * three memory_region_set_client_dirty() calls at the end then advertise
     * the change to the VGA client, the texture cache and the surface tracker.
     * Refusing in the leaf alone turns "this blit did nothing" into "this blit
     * reset the destination to stale VRAM and told three subsystems it had
     * written". Audit MEDIUM M1 over this fix, issue #84.
     *
     * This is also where pgraph_vk_solid_line() puts its identical guard: at
     * the top of the entry function, above its own soft guards and before any
     * state is touched. Copying its warn-once shape into a leaf three frames
     * down copied the idiom and not the placement, which was the whole point.
     *
     * The leaf keeps its guard as a defensive return, so no future caller can
     * reach the 32bpp indexing by another route.
     */
    if (image_blit->operation == NV09F_SET_OPERATION_BLEND_AND &&
        bytes_per_pixel != 4) {
        static bool warned;
        if (!warned) {
            warned = true;
            fprintf(stderr,
                    "nv2a: BLEND_AND blit at %u bytes/pixel is not "
                    "implemented; skipping the blit rather than overrunning "
                    "the destination\n",
                    bytes_per_pixel);
        }
        return;
    }

    hwaddr source_dma_len;
    uint8_t *source = (uint8_t *)nv_dma_map(
        d, context_surfaces->dma_image_source, &source_dma_len);
    assert(context_surfaces->source_offset < source_dma_len);
    source += context_surfaces->source_offset;
    hwaddr source_addr = source - d->vram_ptr;

    hwaddr dest_dma_len;
    uint8_t *dest = (uint8_t *)nv_dma_map(d, context_surfaces->dma_image_dest,
                                          &dest_dma_len);
    assert(context_surfaces->dest_offset < dest_dma_len);
    dest += context_surfaces->dest_offset;
    hwaddr dest_addr = dest - d->vram_ptr;

    SurfaceBinding *surf_src = pgraph_vk_surface_get(d, source_addr);
    if (surf_src) {
        OPT_STAT_INC(dif_blit);
        pgraph_vk_surface_download_if_dirty(d, surf_src);
    }

    hwaddr source_offset = image_blit->in_y * context_surfaces->source_pitch +
                           image_blit->in_x * bytes_per_pixel;
    hwaddr dest_offset = image_blit->out_y * context_surfaces->dest_pitch +
                         image_blit->out_x * bytes_per_pixel;

    size_t max_row_pixels =
        MIN(context_surfaces->source_pitch, context_surfaces->dest_pitch) /
        bytes_per_pixel;
    size_t row_pixels = MIN(max_row_pixels, image_blit->width);

    hwaddr dest_size = (image_blit->height - 1) * context_surfaces->dest_pitch +
                       image_blit->width * bytes_per_pixel;
    hwaddr source_size =
        (image_blit->height - 1) * context_surfaces->source_pitch +
        image_blit->width * bytes_per_pixel;

    /*
     * Bring VRAM up to date under both ranges before the copy touches it.
     * The surface lookups above and below match on the exact base address,
     * so a blit into the middle of a surface -- which is precisely what the
     * Image blit Overlap_* tests do, one pixel just inside a corner -- found
     * nothing, wrote its pixel into VRAM, and then had it overwritten when
     * the surface it landed inside was downloaded. Hardware sees one VRAM;
     * this is what makes ours behave like it (issue #7).
     */
    pgraph_vk_download_surfaces_in_range_if_dirty(
        pg, source_addr + source_offset, source_size);
    pgraph_vk_download_surfaces_in_range_if_dirty(
        pg, dest_addr + dest_offset, dest_size);

    uint8_t *source_row = source + source_offset;
    uint8_t *dest_row = dest + dest_offset;
    size_t row_bytes = row_pixels * bytes_per_pixel;

    size_t adjusted_height = image_blit->height;
    size_t leftover_bytes = 0;

    hwaddr clipped_dest_size =
        nv_clip_gpu_tile_blit(d, dest_addr + dest_offset, dest_size);

    /*
     * Only a blit the tile actually clipped is written through the tile's
     * address map.
     *
     * That is a restriction, not a mechanism. Hardware remaps every write into
     * a tiled region whether or not it also clips one, but the remap is
     * invisible while the tile is valid -- scanout, texture fetch and the CPU
     * aperture all go through it, so it cancels -- and we model tiling nowhere
     * else. Swizzling a write whose reader is one of our linear paths
     * therefore corrupts it, which is what Texture_Framebuffer_Blit's
     * FBToZetaAsTex measured: it blits the framebuffer over the zeta buffer,
     * which pbkit does register as a valid tile (unlike the colour tile, whose
     * VALID flag it leaves clear), and then samples zeta as a texture.
     * Swizzling that write while the fetch stayed linear took it from 14,383
     * to 34,382 differing pixels.
     *
     * A blit that overruns its tile is the one configuration hardware evidence
     * covers, and the only one in the corpus where the guest drops the tile
     * and reads the bytes back afterwards -- which is when the remap stops
     * cancelling. Restricting to it keeps BlitBeyondWidth bit-exact and leaves
     * every other blit, FBToZetaAsTex included, on the linear path.
     *
     * The mechanism-level fix is neither here nor in the texture path: keep
     * storing tiled memory linearly, and permute it when a tile is created or
     * torn down, which is where the remap actually becomes observable. That
     * belongs with the tile registers in pfb.c. The derivation, this
     * measurement and that design are in
     * docs/investigations/gpu-tile-blit-swizzle.md.
     */
    BlitGpuTile dest_tile = { false, 0, 0, 0 };

    if (clipped_dest_size < dest_size) {
        adjusted_height = clipped_dest_size / context_surfaces->dest_pitch;
        size_t consumed_bytes = adjusted_height * context_surfaces->dest_pitch;

        leftover_bytes = clipped_dest_size - consumed_bytes;

        dest_tile = find_blit_gpu_tile(d, dest_addr + dest_offset,
                                       context_surfaces->dest_pitch);
    }

    hwaddr dest_tile_offset =
        dest_tile.valid ? dest_addr + dest_offset - dest_tile.base : 0;
    uint8_t *dest_tile_base = d->vram_ptr + dest_tile.base;

    SurfaceBinding *surf_dest = pgraph_vk_surface_get(d, dest_addr);
    if (surf_dest) {
        if (adjusted_height < surf_dest->height ||
            row_pixels < surf_dest->width) {
            OPT_STAT_INC(dif_blit);
            pgraph_vk_surface_download_if_dirty(d, surf_dest);
        } else {
            // The blit will completely replace the surface so any pending
            // download should be discarded.
            surf_dest->download_pending = false;
            surf_dest->draw_dirty = false;
        }
        surf_dest->upload_pending = true;
        pg->draw_time++;
    }

    NV2A_DPRINTF("  blit 0x%tx -> 0x%tx (Size: %llu, Clipped Height: %zu)\n",
                 source_addr, dest_addr, dest_size, adjusted_height);

    if (adjusted_height > 0) {
        if (dest_tile.valid) {
            perform_blit_tiled(image_blit->operation, source_row,
                               dest_tile_base, dest_tile_offset, &dest_tile,
                               row_bytes, adjusted_height,
                               context_surfaces->source_pitch,
                               context_surfaces->dest_pitch, bytes_per_pixel,
                               beta);
        } else {
            perform_blit(image_blit->operation, source_row, dest_row,
                         row_pixels, adjusted_height, row_bytes,
                         context_surfaces->source_pitch,
                         context_surfaces->dest_pitch, bytes_per_pixel, beta);
        }
    }

    if (leftover_bytes > 0) {
        uint8_t *src =
            source_row + adjusted_height * context_surfaces->source_pitch;
        uint8_t *dest =
            dest_row + adjusted_height * context_surfaces->dest_pitch;

        if (dest_tile.valid) {
            perform_blit_tiled(image_blit->operation, src, dest_tile_base,
                               dest_tile_offset +
                                   adjusted_height *
                                       context_surfaces->dest_pitch,
                               &dest_tile, leftover_bytes, 1,
                               context_surfaces->source_pitch,
                               context_surfaces->dest_pitch, bytes_per_pixel,
                               beta);
        } else {
            perform_blit(image_blit->operation, src, dest,
                         leftover_bytes / bytes_per_pixel, 1, leftover_bytes,
                         context_surfaces->source_pitch,
                         context_surfaces->dest_pitch, bytes_per_pixel, beta);
        }
    }

    bool needs_alpha_patching;
    uint8_t alpha_override;
    switch (context_surfaces->color_format) {
    case NV062_SET_COLOR_FORMAT_LE_X8R8G8B8:
        needs_alpha_patching = true;
        alpha_override = 0xff;
        break;
    case NV062_SET_COLOR_FORMAT_LE_X8R8G8B8_Z8R8G8B8:
        needs_alpha_patching = true;
        alpha_override = 0;
        break;
    default:
        needs_alpha_patching = false;
        alpha_override = 0;
    }

    if (needs_alpha_patching) {
        if (adjusted_height > 0) {
            if (dest_tile.valid) {
                patch_alpha_tiled(dest_tile_base, dest_tile_offset, &dest_tile,
                                  row_pixels, adjusted_height,
                                  context_surfaces->dest_pitch,
                                  alpha_override);
            } else {
                patch_alpha(dest_row, row_pixels, adjusted_height,
                            context_surfaces->dest_pitch, alpha_override);
            }
        }

        if (leftover_bytes > 0) {
            uint8_t *dest =
                dest_row + adjusted_height * context_surfaces->dest_pitch;
            if (dest_tile.valid) {
                patch_alpha_tiled(dest_tile_base,
                                  dest_tile_offset +
                                      adjusted_height *
                                          context_surfaces->dest_pitch,
                                  &dest_tile, leftover_bytes / 4, 1,
                                  context_surfaces->dest_pitch,
                                  alpha_override);
            } else {
                patch_alpha(dest, leftover_bytes / 4, 1, 0, alpha_override);
            }
        }
    }

    dest_addr += dest_offset;

    if (dest_tile.valid) {
        /*
         * The written bytes are scattered across the bands the blit touched,
         * so the linear range is the wrong thing to invalidate. Mark whole
         * bands: conservative, and a band is only pitch * 16 bytes.
         */
        hwaddr band_bytes = (hwaddr)dest_tile.pitch * 16;
        hwaddr first_row = dest_tile_offset / dest_tile.pitch;
        hwaddr last_row =
            first_row + (adjusted_height + (leftover_bytes > 0 ? 1 : 0));
        hwaddr lo = dest_tile.base + (first_row / 16) * band_bytes;
        hwaddr hi = dest_tile.base + ((last_row / 16) + 1) * band_bytes;

        if (hi > dest_tile.limit + 1) {
            hi = dest_tile.limit + 1;
        }
        if (hi > lo) {
            dest_addr = lo;
            clipped_dest_size = hi - lo;
        }
    }

    memory_region_set_client_dirty(d->vram, dest_addr, clipped_dest_size,
                                   DIRTY_MEMORY_VGA);
    memory_region_set_client_dirty(d->vram, dest_addr, clipped_dest_size,
                                   DIRTY_MEMORY_NV2A_TEX);
    /*
     * Also mark NV2A surface dirty so that update_surface_part() detects
     * the blit write and sets upload_pending on any surface bound at this
     * address. Without this, the surface's VkImage retains stale GPU-
     * rendered content while VRAM has fresh blit data.
     */
    memory_region_set_client_dirty(d->vram, dest_addr, clipped_dest_size,
                                   DIRTY_MEMORY_NV2A);
}

/*
 * Rasterise a solid line (class 0x5C) into the 2D destination surface.
 *
 * This stays on the LINEAR path and never consults the GPU tile map, and that
 * is a decision with evidence behind it rather than an omission. The blit
 * above swizzles only a copy that *overruns* its tile, because a remap is
 * invisible while the tile is valid -- scanout, texture fetch and the CPU
 * aperture all go through it, so it cancels -- and we model tiling nowhere
 * else. Swizzling a write whose reader is one of our linear paths corrupts it,
 * which is what Texture_Framebuffer_Blit's FBToZetaAsTex measured when it went
 * from 14,383 to 34,382 differing pixels. A solid line's reader is the linear
 * surface download, and pbkit leaves the colour tile's VALID flag clear
 * anyway, so there is no configuration here where the remap stops cancelling.
 *
 * So gpu_tile_swizzle() was neither copied nor called: the line needs it in no
 * case the corpus contains. That it sits in this file is why the question
 * could be answered rather than guessed at.
 *
 * The surface bookkeeping is the part that cannot live in shared code, and is
 * the reason this is a renderer op at all. The direct upload_pending write
 * below has no renderer-agnostic equivalent: marking DIRTY_MEMORY_NV2A looks
 * like one, and both renderers do read that bit, but their scans
 * test-and-clear it *before* the guard that consumes it, and with
 * upload == false on a live binding the bit is cleared and discarded -- and
 * upload == false is what every surface_update call in shared code passes. A
 * dirty-bit-only route can therefore lose the write with no symptom.
 */
void pgraph_vk_solid_line(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;
    ContextSurfaces2DState *context_surfaces = &pg->context_surfaces_2d;
    SolidLineState *solid_line = &pg->solid_line;

    {
        extern bool xemu_get_frame_skip(void);
        if (r->frame_skip_active && xemu_get_frame_skip()) {
            return;
        }
    }

    if (solid_line->operation != NV09F_SET_OPERATION_SRCCOPY) {
        static bool warned;
        if (!warned) {
            warned = true;
            fprintf(stderr,
                    "nv2a: solid line operation 0x%x is not implemented; "
                    "only SRCCOPY is\n",
                    solid_line->operation);
        }
        return;
    }

    /*
     * The destination depth comes from the surfaces object, not from the
     * line's COLOR_FORMAT -- that field decodes the source colour. Every
     * corpus case is A8R8G8B8, and what a 5-5-5 colour becomes in a 1- or
     * 2-byte destination is unmeasured, so the narrow cases say so rather
     * than inventing an answer.
     */
    unsigned int bytes_per_pixel;
    switch (context_surfaces->color_format) {
    case NV062_SET_COLOR_FORMAT_LE_Y8:
        bytes_per_pixel = 1;
        break;
    case NV062_SET_COLOR_FORMAT_LE_R5G6B5:
        bytes_per_pixel = 2;
        break;
    case NV062_SET_COLOR_FORMAT_LE_A8R8G8B8:
    case NV062_SET_COLOR_FORMAT_LE_X8R8G8B8:
    case NV062_SET_COLOR_FORMAT_LE_X8R8G8B8_Z8R8G8B8:
    case NV062_SET_COLOR_FORMAT_LE_Y32:
        bytes_per_pixel = 4;
        break;
    default:
        bytes_per_pixel = 0;
        break;
    }

    if (bytes_per_pixel != 4) {
        static bool warned;
        if (!warned) {
            warned = true;
            fprintf(stderr,
                    "nv2a: solid line into a %u-byte destination (surface "
                    "format 0x%x) is not implemented\n",
                    bytes_per_pixel, context_surfaces->color_format);
        }
        return;
    }

    /*
     * Soft guards, not asserts. Unlike a blit, a solid line can be triggered
     * without any surfaces object ever having been bound -- the class carries
     * its own SURFACE method -- so an unset destination is a reachable guest
     * state rather than an internal invariant.
     */
    if (!context_surfaces->dest_pitch || !context_surfaces->dma_image_dest) {
        return;
    }

    pgraph_vk_surface_update(d, false, true, true);

    hwaddr dest_dma_len;
    uint8_t *dest = (uint8_t *)nv_dma_map(d, context_surfaces->dma_image_dest,
                                          &dest_dma_len);
    if (context_surfaces->dest_offset >= dest_dma_len) {
        return;
    }
    dest += context_surfaces->dest_offset;
    hwaddr dest_addr = dest - d->vram_ptr;

    hwaddr dest_avail = dest_dma_len - context_surfaces->dest_offset;
    unsigned int max_x = context_surfaces->dest_pitch / bytes_per_pixel;
    unsigned int max_y = dest_avail / context_surfaces->dest_pitch;
    if (!max_x || !max_y) {
        return;
    }

    /* The row span the line can touch, for the sync and the dirty mark. */
    unsigned int y_lo = MIN(solid_line->start_y, solid_line->end_y);
    unsigned int y_hi = MAX(solid_line->start_y, solid_line->end_y);
    if (y_lo >= max_y) {
        return;
    }
    if (y_hi >= max_y) {
        y_hi = max_y - 1;
    }

    hwaddr touched_offset = (hwaddr)y_lo * context_surfaces->dest_pitch;
    hwaddr touched_size =
        (hwaddr)(y_hi - y_lo + 1) * context_surfaces->dest_pitch;

    /*
     * Bring any surface overlapping the touched rows down into VRAM first.
     * The lookup below matches on an exact base address, so a line drawn into
     * the middle of a surface would otherwise write VRAM and then have it
     * overwritten when that surface was downloaded -- the same hazard the
     * blit hit in issue #7.
     */
    pgraph_vk_download_surfaces_in_range_if_dirty(
        pg, dest_addr + touched_offset, touched_size);

    SurfaceBinding *surf_dest = pgraph_vk_surface_get(d, dest_addr);
    if (surf_dest) {
        /*
         * Always download first. A line never covers a whole surface, so the
         * blit's "the copy replaces everything, discard the download"
         * shortcut has no analogue here -- taking it would throw away the
         * background the line is drawn over.
         */
        pgraph_vk_surface_download_if_dirty(d, surf_dest);
        surf_dest->upload_pending = true;
        pg->draw_time++;
    }

    pgraph_solid_line_rasterize(pg, dest, context_surfaces->dest_pitch, max_x,
                                max_y);

    memory_region_set_client_dirty(d->vram, dest_addr + touched_offset,
                                   touched_size, DIRTY_MEMORY_VGA);
    memory_region_set_client_dirty(d->vram, dest_addr + touched_offset,
                                   touched_size, DIRTY_MEMORY_NV2A_TEX);
    memory_region_set_client_dirty(d->vram, dest_addr + touched_offset,
                                   touched_size, DIRTY_MEMORY_NV2A);
}
