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

#include "renderer.h"

#ifdef __ANDROID__
#include <android/log.h>
#endif

VkDeviceSize pgraph_vk_update_index_buffer(PGRAPHState *pg, void *data,
                                           VkDeviceSize size)
{
    nv2a_profile_inc_counter(NV2A_PROF_GEOM_BUFFER_UPDATE_2);
    return pgraph_vk_append_to_buffer(pg, BUFFER_INDEX_STAGING, &data, &size, 1,
                                      1);
}

VkDeviceSize pgraph_vk_update_vertex_inline_buffer(PGRAPHState *pg, void **data,
                                                   VkDeviceSize *sizes,
                                                   size_t count)
{
    nv2a_profile_inc_counter(NV2A_PROF_GEOM_BUFFER_UPDATE_3);
    return pgraph_vk_append_to_buffer(pg, BUFFER_VERTEX_INLINE_STAGING, data,
                                      sizes, count, 1);
}

/*
 * #433 (lane gtasagpu1011), HAKUX_VTX_HAZARD=1. Every draw in a command
 * buffer reads its vertices from one staging copy of vertex RAM, when the
 * command buffer runs, not when the draw is recorded. An upload for a later
 * draw that changes bytes an earlier draw in the same command buffer reads
 * replaces that draw's vertices before the GPU reaches it. A guest that
 * reuses one vertex buffer for several draws a frame, waiting only for the
 * GPU to have fetched the previous draw (which pgraph has, on the guest's
 * clock), does that. Upstream finished the command buffer on any re-upload
 * of a page uploaded since the last finish; 41be412ae0 dropped that check
 * when it gave each submit frame its own copy, but the copies only keep
 * command buffers apart, not the draws in one.
 *
 * This finishes before such an upload, as upstream did, but only when bytes
 * an earlier draw reads actually change, not on a shared page: an append to a
 * ring of vertices shares pages with the draws before it, not bytes.
 *
 * Bookkeeping: pgraph_vk_bind_vertex_attributes notes the draw's exact byte
 * ranges in vtxhz_cur; pgraph_vk_vtxhz_commit (end of begin_pre_draw and
 * begin_draw, vk/draw.c) adds them to vtxhz_read for the rotation the draw is
 * recorded in. A rotation empties vtxhz_read. Off, it costs one load per
 * bind, upload and commit.
 *
 * On by default (#433, defaulton1011): unset means on; HAKUX_VTX_HAZARD=0
 * turns it off for an A/B.
 */
static bool vtxhz_env(void)
{
    static int v = -1;
    if (v < 0) {
        const char *e = getenv("HAKUX_VTX_HAZARD");
        v = e ? atoi(e) > 0 : 1;
#ifdef __ANDROID__
        __android_log_print(ANDROID_LOG_INFO, "hakuX",
                            "HAKUX_VTX_HAZARD=%d (finish before an upload "
                            "that rewrites an earlier draw's vertices)%s", v,
                            e ? "" : " (default)");
#endif
    }
    return v;
}

static void vtxhz_note_read(PGRAPHVkState *r, hwaddr lo, hwaddr hi)
{
    if (hi > lo && r->vtxhz_cur_n < ARRAY_SIZE(r->vtxhz_cur)) {
        r->vtxhz_cur[r->vtxhz_cur_n++] =
            (MemorySyncRequirement){ .addr = lo, .size = hi - lo };
    }
}

static void vtxhz_clear(PGRAPHVkState *r)
{
    r->vtxhz_rot = r->frame_rotations;
    r->vtxhz_n = 0;
    r->vtxhz_lo = (hwaddr)-1;
    r->vtxhz_hi = 0;
}

static void vtxhz_sync_rotation(PGRAPHVkState *r)
{
    if (r->vtxhz_rot != r->frame_rotations) {
        vtxhz_clear(r);
    }
}

void pgraph_vk_vtxhz_commit(PGRAPHVkState *r)
{
    if (!r->vtxhz_on || r->vtxhz_cur_rot == r->frame_rotations) {
        return;
    }
    vtxhz_sync_rotation(r);
    r->vtxhz_cur_rot = r->frame_rotations;
    for (size_t i = 0; i < r->vtxhz_cur_n; i++) {
        hwaddr lo = r->vtxhz_cur[i].addr;
        hwaddr hi = lo + r->vtxhz_cur[i].size;
        r->vtxhz_lo = MIN(r->vtxhz_lo, lo);
        r->vtxhz_hi = MAX(r->vtxhz_hi, hi);
        if (r->vtxhz_n > 0) {
            /* Interleaved attributes of one draw, or a draw over the vertices
             * of the one before it: one range. */
            MemorySyncRequirement *p = &r->vtxhz_read[r->vtxhz_n - 1];
            if (lo <= p->addr + p->size && hi >= p->addr) {
                hwaddr nlo = MIN(lo, p->addr);
                p->size = MAX(hi, p->addr + p->size) - nlo;
                p->addr = nlo;
                continue;
            }
        }
        if (r->vtxhz_n == r->vtxhz_cap) {
            r->vtxhz_cap = r->vtxhz_cap ? r->vtxhz_cap * 2 : 256;
            r->vtxhz_read = g_renew(MemorySyncRequirement, r->vtxhz_read,
                                    r->vtxhz_cap);
        }
        r->vtxhz_read[r->vtxhz_n++] =
            (MemorySyncRequirement){ .addr = lo, .size = hi - lo };
    }
}

/* Does copying `data` over the staging copy at `offset` change a byte a draw
 * already recorded in this command buffer reads? */
static bool vtxhz_overwrites(PGRAPHVkState *r, const uint8_t *staged,
                             hwaddr offset, const uint8_t *data,
                             VkDeviceSize size)
{
    vtxhz_sync_rotation(r);
    hwaddr end = offset + size;
    if (r->vtxhz_n == 0 || end <= r->vtxhz_lo || offset >= r->vtxhz_hi) {
        return false;
    }
    for (size_t i = 0; i < r->vtxhz_n; i++) {
        hwaddr lo = MAX(r->vtxhz_read[i].addr, offset);
        hwaddr hi = MIN(r->vtxhz_read[i].addr + r->vtxhz_read[i].size, end);
        if (lo < hi && memcmp(staged + lo, data + (lo - offset), hi - lo)) {
            return true;
        }
    }
    return false;
}

void pgraph_vk_update_vertex_ram_buffer(PGRAPHState *pg, hwaddr offset,
                                        void *data, VkDeviceSize size)
{
    PGRAPHVkState *r = pg->vk_renderer_state;

    pgraph_vk_download_surfaces_in_range_if_dirty(pg, offset, size);

    size_t start_bit = offset / TARGET_PAGE_SIZE;
    size_t end_bit = TARGET_PAGE_ALIGN(offset + size) / TARGET_PAGE_SIZE;
    size_t nbits = end_bit - start_bit;

    /* Per-frame buffer: no finish needed between command buffers, each
     * frame has its own copy. Within one, see HAKUX_VTX_HAZARD above. */
    bool hazard_finished = false;
    if (unlikely(r->vtxhz_on) &&
        /* Not while merged or reordered draws are being recorded: the
         * finish would flush those queues from inside their own flush. */
        r->draw_queue.count == 0 && r->reorder_window.count == 0 &&
        vtxhz_overwrites(r, get_staging_buffer(r, BUFFER_VERTEX_RAM)->mapped,
                         offset, data, size)) {
        pgraph_vk_finish(pg, VK_FINISH_REASON_VERTEX_BUFFER_DIRTY);
        r->vtxhz_finishes++;
        hazard_finished = true;
#ifdef __ANDROID__
        {
            static int64_t logged_us;
            static uint64_t logged_n;
            int64_t now = g_get_monotonic_time();
            if (now - logged_us >= 10 * G_USEC_PER_SEC) {
                __android_log_print(ANDROID_LOG_INFO, "hakuX",
                                    "vtx_hazard: %" PRIu64 " finishes, %"
                                    PRIu64 " since the last line",
                                    r->vtxhz_finishes,
                                    r->vtxhz_finishes - logged_n);
                logged_us = now;
                logged_n = r->vtxhz_finishes;
            }
        }
#endif
        /* Also when the finish did not rotate: what it submitted is no
         * longer this command buffer's to protect. */
        vtxhz_clear(r);
    }

    nv2a_profile_inc_counter(NV2A_PROF_GEOM_BUFFER_UPDATE_1);
    StorageBuffer *vram = get_staging_buffer(r, BUFFER_VERTEX_RAM);
    if (unlikely(nv2a_dbg_framedump_active())) {
        pgraph_vk_fdump_vertex_upload(r, offset, vram->mapped + offset, data,
                                      size, hazard_finished);
    }
    memcpy(vram->mapped + offset, data, size);

    FrameStagingState *fs = &r->frame_staging[r->current_frame];
    if (offset < fs->vertex_ram_flush_min) {
        fs->vertex_ram_flush_min = offset;
    }
    VkDeviceSize end = offset + size;
    if (end > fs->vertex_ram_flush_max) {
        fs->vertex_ram_flush_max = end;
    }
    for (int i = 0; i < NUM_SUBMIT_FRAMES; i++) {
        FrameStagingState *other = &r->frame_staging[i];
        if (other == fs) {
            continue;
        }
        if (offset < other->vertex_ram_stale_min) {
            other->vertex_ram_stale_min = offset;
        }
        if (end > other->vertex_ram_stale_max) {
            other->vertex_ram_stale_max = end;
        }
    }

    bitmap_set(get_uploaded_bitmap(r), start_bit, nbits);
}

static void update_memory_buffer(NV2AState *d, hwaddr addr, hwaddr size)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    assert(r->num_vertex_ram_buffer_syncs <
           ARRAY_SIZE(r->vertex_ram_buffer_syncs));
    r->vertex_ram_buffer_syncs[r->num_vertex_ram_buffer_syncs++] =
        (MemorySyncRequirement){ .addr = addr, .size = size };
}

static const VkFormat float_to_count[] = {
    VK_FORMAT_R32_SFLOAT,
    VK_FORMAT_R32G32_SFLOAT,
    VK_FORMAT_R32G32B32_SFLOAT,
    VK_FORMAT_R32G32B32A32_SFLOAT,
};

static const VkFormat ub_to_count[] = {
    VK_FORMAT_R8_UNORM,
    VK_FORMAT_R8G8_UNORM,
    VK_FORMAT_R8G8B8_UNORM,
    VK_FORMAT_R8G8B8A8_UNORM,
};

static const VkFormat s1_to_count[] = {
    VK_FORMAT_R16_SNORM,
    VK_FORMAT_R16G16_SNORM,
    VK_FORMAT_R16G16B16_SNORM,
    VK_FORMAT_R16G16B16A16_SNORM,
};

static const VkFormat s32k_to_count[] = {
    VK_FORMAT_R16_SSCALED,
    VK_FORMAT_R16G16_SSCALED,
    VK_FORMAT_R16G16B16_SSCALED,
    VK_FORMAT_R16G16B16A16_SSCALED,
};

static char const * const vertex_data_array_format_to_str[] = {
    [NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_UB_D3D] = "UB_D3D",
    [NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_UB_OGL] = "UB_OGL",
    [NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_S1] = "S1",
    [NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_F] = "F",
    [NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_S32K] = "S32K",
    [NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_CMP] = "CMP",
};

/*
 * Which attributes come from arrays and which from their persistent values
 * (uniform_attrs), and which need unpacking (compressed_attrs) or swizzling
 * (swizzle_attrs), is part of the vertex shader: each mask is a different
 * variant. The masks are derived here from the array formats, and nothing
 * else announces a change in them to the shader-state check, which
 * pgraph_vk_bind_pipeline only reaches when shader_state_gen has moved.
 * A draw that enables or disables an attribute and changes nothing else --
 * every Attrib carryover test draws position-only right after a draw with
 * a diffuse and one more attribute from arrays -- kept the previous
 * variant, whose array inputs the new vertex input state no longer
 * provides, and the position it fetched was undefined.
 *
 * Bump the generations the shader gate and the single-draw fast path are
 * keyed on when the masks change, as SET_SURFACE_FORMAT does for the zeta
 * format.
 */
static void attr_masks_changed(PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;
    if (pg->uniform_attrs == r->bound_uniform_attrs &&
        pg->compressed_attrs == r->bound_compressed_attrs &&
        pg->swizzle_attrs == r->bound_swizzle_attrs) {
        return;
    }
    r->bound_uniform_attrs = pg->uniform_attrs;
    r->bound_compressed_attrs = pg->compressed_attrs;
    r->bound_swizzle_attrs = pg->swizzle_attrs;
    pg->shader_state_gen++;
    pg->non_dynamic_reg_gen++;
    pg->any_reg_gen++;
}

void pgraph_vk_bind_vertex_attributes(NV2AState *d, unsigned int min_element,
                                      unsigned int max_element,
                                      bool inline_data,
                                      unsigned int inline_stride,
                                      unsigned int provoking_element)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    unsigned int num_elements = max_element - min_element + 1;

    r->vtxhz_on = vtxhz_env();
    r->vtxhz_cur_n = 0;
    r->vtxhz_cur_rot = UINT64_MAX;

    if (inline_data) {
        r->cached_num_active_bindings = 0;
    } else if (pg->vertex_attr_gen == r->last_vertex_attr_gen &&
               r->cached_num_active_bindings > 0) {
        OPT_STAT_INC(vtx_cache_hits);
        pg->compressed_attrs = r->cached_compressed_attrs;
        pg->uniform_attrs = r->cached_uniform_attrs;
        pg->swizzle_attrs = r->cached_swizzle_attrs;
        r->num_active_vertex_attribute_descriptions = r->cached_num_active_attrs;
        r->num_active_vertex_binding_descriptions = r->cached_num_active_bindings;
        memcpy(r->vertex_attribute_descriptions, r->cached_attr_descs,
               sizeof(r->cached_attr_descs));
        memcpy(r->vertex_binding_descriptions, r->cached_bind_descs,
               sizeof(r->cached_bind_descs));
        memcpy(r->vertex_attribute_to_description_location,
               r->cached_attr_to_desc_loc,
               sizeof(r->cached_attr_to_desc_loc));
        memcpy(r->vertex_attribute_offsets, r->cached_attr_offsets,
               sizeof(r->cached_attr_offsets));
        for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
            if (r->cached_attr_layout[i].stride) {
                hwaddr start = r->cached_attr_layout[i].base_addr +
                               min_element * r->cached_attr_layout[i].stride;
                update_memory_buffer(d, start,
                                     num_elements * r->cached_attr_layout[i].stride);
                if (unlikely(r->vtxhz_on)) {
                    /* The cached layout is this vertex_attr_gen's, so the
                     * attribute's size and count are still these. */
                    VertexAttribute *attr = &pg->vertex_attributes[i];
                    vtxhz_note_read(r, start,
                                    start + (num_elements - 1) *
                                                r->cached_attr_layout[i].stride +
                                            attr->size * attr->count);
                }
            }
        }
        attr_masks_changed(pg);
        return;
    }
    OPT_STAT_INC(vtx_cache_misses);

    if (inline_data) {
        NV2A_VK_DGROUP_BEGIN("%s (num_elements: %d inline stride: %d)",
                             __func__, num_elements, inline_stride);
    } else {
        NV2A_VK_DGROUP_BEGIN("%s (num_elements: %d)", __func__, num_elements);
    }

    pg->compressed_attrs = 0;
    pg->uniform_attrs = 0;
    pg->swizzle_attrs = 0;

    r->num_active_vertex_attribute_descriptions = 0;
    r->num_active_vertex_binding_descriptions = 0;

    for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
        r->cached_attr_layout[i].stride = 0;
        r->cached_attr_layout[i].base_addr = 0;
        VertexAttribute *attr = &pg->vertex_attributes[i];
        NV2A_VK_DGROUP_BEGIN("[attr %02d] format=%s, count=%d, stride=%d", i,
                             vertex_data_array_format_to_str[attr->format],
                             attr->count, attr->stride);
        r->vertex_attribute_to_description_location[i] = -1;
        if (!attr->count) {
            pg->uniform_attrs |= 1 << i;
            NV2A_VK_DPRINTF("inline_value = {%f, %f, %f, %f}",
                            attr->inline_value[0], attr->inline_value[1],
                            attr->inline_value[2], attr->inline_value[3]);
            NV2A_VK_DGROUP_END();
            continue;
        }

        VkFormat vk_format;
        bool needs_conversion = false;
        bool d3d_swizzle = false;

        switch (attr->format) {
        case NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_UB_D3D:
            assert(attr->count == 4);
            d3d_swizzle = true;
            /* fallthru */
        case NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_UB_OGL:
            assert(attr->count <= ARRAY_SIZE(ub_to_count));
            vk_format = ub_to_count[attr->count - 1];
            break;
        case NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_S1:
            assert(attr->count <= ARRAY_SIZE(s1_to_count));
            vk_format = s1_to_count[attr->count - 1];
            break;
        case NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_F:
            assert(attr->count <= ARRAY_SIZE(float_to_count));
            vk_format = float_to_count[attr->count - 1];
            break;
        case NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_S32K:
            assert(attr->count <= ARRAY_SIZE(s32k_to_count));
            vk_format = s32k_to_count[attr->count - 1];
            break;
        case NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE_CMP:
            vk_format =
                VK_FORMAT_R32_SINT; // VK_FORMAT_B10G11R11_UFLOAT_PACK32 ??
            /* 3 signed, normalized components packed in 32-bits. (11,11,10) */
            assert(attr->count == 1);
            needs_conversion = true;
            break;
        default:
            fprintf(stderr, "Unknown vertex type: 0x%x\n", attr->format);
            assert(false);
            break;
        }

        nv2a_profile_inc_counter(NV2A_PROF_ATTR_BIND);
        hwaddr attrib_data_addr;
        size_t stride;

        hwaddr start = 0;
        if (inline_data) {
            attrib_data_addr = attr->inline_array_offset;
            stride = inline_stride;
        } else {
            hwaddr dma_len;
            uint8_t *attr_data = (uint8_t *)nv_dma_map(
                d, attr->dma_select ? pg->dma_vertex_b : pg->dma_vertex_a,
                &dma_len);
            assert(attr->offset < dma_len);
            attrib_data_addr = attr_data + attr->offset - d->vram_ptr;
            stride = attr->stride;
            start = attrib_data_addr + min_element * stride;
            update_memory_buffer(d, start, num_elements * stride);
        }

        uint32_t provoking_element_index = provoking_element - min_element;
        size_t element_size = attr->size * attr->count;
        assert(element_size <= sizeof(attr->inline_value));
        const uint8_t *last_entry;

        if (inline_data) {
            last_entry =
                (uint8_t *)pg->inline_array + attr->inline_array_offset;
        } else {
            last_entry = d->vram_ptr + start;
        }
        if (!stride) {
            // Stride of 0 indicates that only the first element should be
            // used.
            pg->uniform_attrs |= 1 << i;
            pgraph_update_inline_value(attr, last_entry);
            NV2A_VK_DPRINTF("inline_value = {%f, %f, %f, %f}",
                            attr->inline_value[0], attr->inline_value[1],
                            attr->inline_value[2], attr->inline_value[3]);
            NV2A_VK_DGROUP_END();
            continue;
        }

        NV2A_VK_DPRINTF("offset = %08" HWADDR_PRIx, attrib_data_addr);
        if (unlikely(r->vtxhz_on) && !inline_data) {
            /* The bytes it reads, not update_memory_buffer's whole strides:
             * the last element's stride runs into the next vertex. */
            vtxhz_note_read(r, start,
                            start + (num_elements - 1) * stride + element_size);
        }
        last_entry += stride * provoking_element_index;
        pgraph_update_inline_value(attr, last_entry);

        r->vertex_attribute_to_description_location[i] =
            r->num_active_vertex_binding_descriptions;

        r->vertex_binding_descriptions
            [r->num_active_vertex_binding_descriptions++] =
            (VkVertexInputBindingDescription){
                .binding = r->vertex_attribute_to_description_location[i],
                .stride = stride,
                .inputRate = VK_VERTEX_INPUT_RATE_VERTEX,
            };

        r->vertex_attribute_descriptions
            [r->num_active_vertex_attribute_descriptions++] =
            (VkVertexInputAttributeDescription){
                .binding = r->vertex_attribute_to_description_location[i],
                .location = i,
                .format = vk_format,
            };

        r->vertex_attribute_offsets[i] = attrib_data_addr;

        if (!inline_data) {
            r->cached_attr_layout[i].base_addr = attrib_data_addr;
            r->cached_attr_layout[i].stride = stride;
        }

        if (needs_conversion) {
            pg->compressed_attrs |= (1 << i);
        }
        if (d3d_swizzle) {
            pg->swizzle_attrs |= (1 << i);
        }

        NV2A_VK_DGROUP_END();
    }

    if (!inline_data) {
        r->last_vertex_attr_gen = pg->vertex_attr_gen;
        r->cached_num_active_bindings = r->num_active_vertex_binding_descriptions;
        r->cached_num_active_attrs = r->num_active_vertex_attribute_descriptions;
        memcpy(r->cached_attr_descs, r->vertex_attribute_descriptions,
               sizeof(r->cached_attr_descs));
        memcpy(r->cached_bind_descs, r->vertex_binding_descriptions,
               sizeof(r->cached_bind_descs));
        memcpy(r->cached_attr_to_desc_loc,
               r->vertex_attribute_to_description_location,
               sizeof(r->cached_attr_to_desc_loc));
        memcpy(r->cached_attr_offsets, r->vertex_attribute_offsets,
               sizeof(r->cached_attr_offsets));
        r->cached_compressed_attrs = pg->compressed_attrs;
        r->cached_uniform_attrs = pg->uniform_attrs;
        r->cached_swizzle_attrs = pg->swizzle_attrs;
    }
    attr_masks_changed(pg);

    NV2A_VK_DGROUP_END();
}

void pgraph_vk_bind_vertex_attributes_inline(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    r->vtxhz_cur_n = 0;
    r->vtxhz_cur_rot = UINT64_MAX;
    r->cached_num_active_bindings = 0;

    pg->compressed_attrs = 0;
    pg->uniform_attrs = 0;
    pg->swizzle_attrs = 0;

    r->num_active_vertex_attribute_descriptions = 0;
    r->num_active_vertex_binding_descriptions = 0;

    for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
        VertexAttribute *attr = &pg->vertex_attributes[i];
        if (attr->inline_buffer_populated) {
            r->vertex_attribute_to_description_location[i] =
                r->num_active_vertex_binding_descriptions;
            r->vertex_binding_descriptions
                [r->num_active_vertex_binding_descriptions++] =
                (VkVertexInputBindingDescription){
                    .binding =
                        r->vertex_attribute_to_description_location[i],
                    .stride = 4 * sizeof(float),
                    .inputRate = VK_VERTEX_INPUT_RATE_VERTEX,
                };
            r->vertex_attribute_descriptions
                [r->num_active_vertex_attribute_descriptions++] =
                (VkVertexInputAttributeDescription){
                    .binding =
                        r->vertex_attribute_to_description_location[i],
                    .location = i,
                    .format = VK_FORMAT_R32G32B32A32_SFLOAT,
                };
            memcpy(attr->inline_value,
                   attr->inline_buffer + (pg->inline_buffer_length - 1) * 4,
                   sizeof(attr->inline_value));
        } else {
            r->vertex_attribute_to_description_location[i] = -1;
            pg->uniform_attrs |= 1 << i;
        }
    }
    attr_masks_changed(pg);
}
