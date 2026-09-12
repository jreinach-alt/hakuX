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
#endif

static void perform_blit(int operation, uint8_t *source, uint8_t *dest,
                         size_t width, size_t height, size_t width_bytes,
                         size_t source_pitch, size_t dest_pitch,
                         BetaState *beta)
{
    if (operation == NV09F_SET_OPERATION_SRCCOPY) {
        for (unsigned int y = 0; y < height; y++) {
            memmove(dest, source, width_bytes);
            source += source_pitch;
            dest += dest_pitch;
        }
    } else if (operation == NV09F_SET_OPERATION_BLEND_AND) {
        uint32_t max_beta_mult = 0x7f80;
        uint32_t beta_mult = beta->beta >> 16;
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
            /* Reciprocal approximation: 1/0x7f80 ≈ 0x0101/0x7f80
             * Use shift: 0x7f80 = 32640, close to 32768 = 1<<15.
             * We can use (a + b + (1<<14)) >> 15 as a close approximation
             * since max_beta_mult ≈ 2^15. Error is < 1 LSB for typical values.
             * Exact: val / 0x7f80. Approx: (val + 0x3FC0) >> 15. */
            for (; x + 4 <= width; x += 4) {
                uint8x16_t src_px = vld1q_u8(s + x * 4);
                uint8x16_t dst_px = vld1q_u8(d + x * 4);

                /* Low 8 pixels (first 2 RGBA pixels) */
                uint16x8_t s_lo = vmovl_u8(vget_low_u8(src_px));
                uint16x8_t d_lo = vmovl_u8(vget_low_u8(dst_px));
                uint32x4_t prod_s_lo0 = vmull_u16(vget_low_u16(s_lo), vget_low_u16(v_beta));
                uint32x4_t prod_d_lo0 = vmull_u16(vget_low_u16(d_lo), vget_low_u16(v_inv));
                uint32x4_t sum_lo0 = vaddq_u32(prod_s_lo0, prod_d_lo0);
                sum_lo0 = vaddq_u32(sum_lo0, vdupq_n_u32(0x3FC0));
                uint16x4_t res_lo0 = vshrn_n_u32(sum_lo0, 15);

                uint32x4_t prod_s_lo1 = vmull_u16(vget_high_u16(s_lo), vget_high_u16(v_beta));
                uint32x4_t prod_d_lo1 = vmull_u16(vget_high_u16(d_lo), vget_high_u16(v_inv));
                uint32x4_t sum_lo1 = vaddq_u32(prod_s_lo1, prod_d_lo1);
                sum_lo1 = vaddq_u32(sum_lo1, vdupq_n_u32(0x3FC0));
                uint16x4_t res_lo1 = vshrn_n_u32(sum_lo1, 15);

                uint8x8_t out_lo = vmovn_u16(vcombine_u16(res_lo0, res_lo1));

                /* High 8 pixels (next 2 RGBA pixels) */
                uint16x8_t s_hi = vmovl_u8(vget_high_u8(src_px));
                uint16x8_t d_hi = vmovl_u8(vget_high_u8(dst_px));
                uint32x4_t prod_s_hi0 = vmull_u16(vget_low_u16(s_hi), vget_low_u16(v_beta));
                uint32x4_t prod_d_hi0 = vmull_u16(vget_low_u16(d_hi), vget_low_u16(v_inv));
                uint32x4_t sum_hi0 = vaddq_u32(prod_s_hi0, prod_d_hi0);
                sum_hi0 = vaddq_u32(sum_hi0, vdupq_n_u32(0x3FC0));
                uint16x4_t res_hi0 = vshrn_n_u32(sum_hi0, 15);

                uint32x4_t prod_s_hi1 = vmull_u16(vget_high_u16(s_hi), vget_high_u16(v_beta));
                uint32x4_t prod_d_hi1 = vmull_u16(vget_high_u16(d_hi), vget_high_u16(v_inv));
                uint32x4_t sum_hi1 = vaddq_u32(prod_s_hi1, prod_d_hi1);
                sum_hi1 = vaddq_u32(sum_hi1, vdupq_n_u32(0x3FC0));
                uint16x4_t res_hi1 = vshrn_n_u32(sum_hi1, 15);

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
            /* Scalar fallback for remaining pixels */
            for (; x < width; x++) {
                for (unsigned int ch = 0; ch < 3; ch++) {
                    uint32_t a = s[x * 4 + ch] * beta_mult;
                    uint32_t b = d[x * 4 + ch] * inv_beta_mult;
                    d[x * 4 + ch] = (a + b) / max_beta_mult;
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
                         dest_pitch, beta);
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

    if (clipped_dest_size < dest_size) {
        adjusted_height = clipped_dest_size / context_surfaces->dest_pitch;
        size_t consumed_bytes = adjusted_height * context_surfaces->dest_pitch;

        leftover_bytes = clipped_dest_size - consumed_bytes;
    }

    /*
     * If the destination sits inside an active tile, the same bytes go to the
     * same offsets, but those offsets are shuffled by the tile. Only a tile
     * with the VALID flag set counts -- pbkit registers the framebuffer's tile
     * with that flag clear, which is why nothing else in the Image blit suite
     * takes this path.
     */
    BlitGpuTile dest_tile = find_blit_gpu_tile(d, dest_addr + dest_offset,
                                               context_surfaces->dest_pitch);
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
                         context_surfaces->dest_pitch, beta);
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
                         context_surfaces->dest_pitch, beta);
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
