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

/*
 * #433 HAKUX_VTXHZ_BUMP (lane p11vtxbump1022; off by default). With
 * HAKUX_VTX_HAZARD on, an upload that would change bytes an earlier draw in
 * the open command buffer reads goes to a fresh offset past the end of the
 * frame's vertex RAM copy instead of finishing the command buffer. The
 * identity copy keeps the bytes the earlier draws read; draws set up after
 * the upload bind the fresh copy (pgraph_vk_vtxhz_bump_offset, from
 * bind_vertex_buffer and snapshot_vertex_buffers in vk/draw.c).
 *
 * The entries belong to one rotation of one frame and only grow in it. An
 * upload that overlaps one bumps too, so the newest entry holding a byte is
 * the newest copy of that byte, and the identity copy is the newest outside
 * the entries. The first touch after the frame rotates, or once nothing
 * recorded is left to run, copies the entries into the current identity copy,
 * oldest first, and owes the other frames those bytes (vtxhz_bump_resolve).
 * Out of room, the upload takes today's path: the hazard check and finish.
 *
 * Value: 0 or unset, off (today's path); 1, 8 MB a frame; N > 1, N MB (at
 * most 256). Inert with HAKUX_VTX_HAZARD=0: the hazard check decides a bump.
 */
static int vtxhz_bump_env_raw;

static int vtxhz_bump_env(void)
{
    static int mb = -1;
    if (mb < 0) {
        const char *e = getenv("HAKUX_VTXHZ_BUMP");
        vtxhz_bump_env_raw = e ? atoi(e) : 0;
        mb = vtxhz_bump_env_raw <= 0 ? 0 :
             vtxhz_bump_env_raw == 1 ? 8 : MIN(vtxhz_bump_env_raw, 256);
    }
    return mb;
}

static void vtxhz_note_read(PGRAPHVkState *r, hwaddr lo, hwaddr hi)
{
    if (hi > lo && r->vtxhz_cur_n < ARRAY_SIZE(r->vtxhz_cur)) {
        r->vtxhz_cur[r->vtxhz_cur_n++] =
            (MemorySyncRequirement){ .addr = lo, .size = hi - lo };
    }
}

/* Attribute `i` of the draw being set up reads [lo, hi) */
static void vtxhz_note_attr(PGRAPHVkState *r, int i, hwaddr lo, hwaddr hi)
{
    vtxhz_note_read(r, lo, hi);
    r->vtxhz_attr_lo[i] = lo;
    r->vtxhz_attr_hi[i] = hi;
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

/* The always-on count line, at most every 10 s (gtasagpu1011/scrread.py
 * reads its "vtx_hazard: N finishes" prefix). */
static void vtxhz_log(PGRAPHVkState *r)
{
#ifdef __ANDROID__
    static int64_t logged_us;
    static uint64_t logged_n;
    int64_t now = g_get_monotonic_time();
    if (now - logged_us >= 10 * G_USEC_PER_SEC) {
        __android_log_print(ANDROID_LOG_INFO, "hakuX",
                            "vtx_hazard: %" PRIu64 " finishes, %" PRIu64
                            " since the last line; %" PRIu64 " bumps (%"
                            PRIu64 " kB), %" PRIu64 " no room, %" PRIu64
                            " partial; %" PRIu64 " buffer-space finishes",
                            r->vtxhz_finishes, r->vtxhz_finishes - logged_n,
                            r->vtxhz_bumps, r->vtxhz_bump_bytes >> 10,
                            r->vtxhz_bump_full, r->vtxhz_bump_partial,
                            r->vtxhz_buf_finishes);
        logged_us = now;
        logged_n = r->vtxhz_finishes;
    }
#else
    (void)r;
#endif
}

/* HAKUX_VTXHZ_BUMP: size the frames' vertex RAM copies (vk/buffer.c). The
 * bytes each needs past vertex RAM's own, 0 when off. */
VkDeviceSize pgraph_vk_vtxhz_bump_init(PGRAPHVkState *r, VkDeviceSize vram_size)
{
    int mb = vtxhz_bump_env();
    bool on = mb > 0 && vtxhz_env();

    r->vtxhz_bump_base = ROUND_UP(vram_size, TARGET_PAGE_SIZE);
    r->vtxhz_bump_cap = on ? (VkDeviceSize)mb << 20 : 0;
    r->vtxhz_bump_used = r->vtxhz_bump_flushed = 0;
    r->vtxhz_bump_n = 0;
    r->vtxhz_bump_lo = (hwaddr)-1;
    r->vtxhz_bump_hi = 0;
    r->vtxhz_bump_frame = r->current_frame;
    r->vtxhz_bump_rot = r->frame_rotations;
#ifdef __ANDROID__
    __android_log_print(ANDROID_LOG_INFO, "hakuX",
                        "HAKUX_VTXHZ_BUMP=%d (%d MB a frame for an upload "
                        "that would rewrite an earlier draw's vertices, "
                        "instead of a finish)%s", vtxhz_bump_env_raw,
                        on ? mb : 0,
                        on ? "" : mb ? " (inert: HAKUX_VTX_HAZARD=0)" :
                        " (off)");
#endif
    return on ? r->vtxhz_bump_base + r->vtxhz_bump_cap - vram_size : 0;
}

/* The other frames' copies owe [lo, hi). The one place the bump path reads
 * the stale bookkeeping; the upload below keeps its own. */
static void vtxhz_mark_stale(PGRAPHVkState *r, hwaddr lo, hwaddr hi)
{
    for (int i = 0; i < r->ring_alloc; i++) {
        FrameStagingState *other = &r->frame_staging[i];
        if (i == r->current_frame) {
            continue;
        }
        if (lo < other->vertex_ram_stale_min) {
            other->vertex_ram_stale_min = lo;
        }
        if (hi > other->vertex_ram_stale_max) {
            other->vertex_ram_stale_max = hi;
        }
    }
}

/* Copy the entries into the current frame's identity copy, oldest first, and
 * start an empty set for this rotation of this frame. Callers make sure the
 * GPU reads neither the copy's [lo, hi) of any entry nor, if the entries are
 * this frame's, their offsets: the frame has rotated (its fence was waited),
 * or nothing recorded is left to run. */
static void vtxhz_bump_resolve(PGRAPHVkState *r)
{
    FrameStagingState *src = &r->frame_staging[r->vtxhz_bump_frame];
    FrameStagingState *fs = &r->frame_staging[r->current_frame];

    for (size_t i = 0; i < r->vtxhz_bump_n; i++) {
        struct VtxhzBump *b = &r->vtxhz_bump[i];
        memcpy(fs->vertex_ram.mapped + b->lo, src->vertex_ram.mapped + b->off,
               b->hi - b->lo);
        if (b->lo < fs->vertex_ram_flush_min) {
            fs->vertex_ram_flush_min = b->lo;
        }
        if (b->hi > fs->vertex_ram_flush_max) {
            fs->vertex_ram_flush_max = b->hi;
        }
        vtxhz_mark_stale(r, b->lo, b->hi);
    }
    r->vtxhz_bump_n = 0;
    r->vtxhz_bump_lo = (hwaddr)-1;
    r->vtxhz_bump_hi = 0;
    r->vtxhz_bump_used = r->vtxhz_bump_flushed = 0;
    r->vtxhz_bump_frame = r->current_frame;
    r->vtxhz_bump_rot = r->frame_rotations;
}

static inline void vtxhz_bump_sync(PGRAPHVkState *r)
{
    if (r->vtxhz_bump_rot != r->frame_rotations) {
        vtxhz_bump_resolve(r);
    }
}

/* The newest entry holding a byte of [lo, hi), or NULL */
static struct VtxhzBump *vtxhz_bump_find(PGRAPHVkState *r, hwaddr lo,
                                         hwaddr hi)
{
    if (r->vtxhz_bump_n == 0 || hi <= r->vtxhz_bump_lo ||
        lo >= r->vtxhz_bump_hi) {
        return NULL;
    }
    for (size_t i = r->vtxhz_bump_n; i-- > 0;) {
        if (r->vtxhz_bump[i].lo < hi && lo < r->vtxhz_bump[i].hi) {
            return &r->vtxhz_bump[i];
        }
    }
    return NULL;
}

/* Out of room for an upload of [lo, hi) that overlaps entries: the identity
 * copy takes it, so no entry may answer for those bytes any more. A split
 * entry's right part goes in just after it, keeping the order by age. */
static void vtxhz_bump_trim(PGRAPHVkState *r, hwaddr lo, hwaddr hi)
{
    for (size_t i = 0; i < r->vtxhz_bump_n; i++) {
        struct VtxhzBump *b = &r->vtxhz_bump[i];
        if (b->hi <= lo || b->lo >= hi) {
            continue;
        }
        bool left = b->lo < lo, right = b->hi > hi;
        if (left && right) {
            if (r->vtxhz_bump_n == r->vtxhz_bump_alloc) {
                r->vtxhz_bump_alloc *= 2;
                r->vtxhz_bump = g_renew(struct VtxhzBump, r->vtxhz_bump,
                                        r->vtxhz_bump_alloc);
                b = &r->vtxhz_bump[i];
            }
            memmove(b + 2, b + 1,
                    (r->vtxhz_bump_n - i - 1) * sizeof(*b));
            r->vtxhz_bump_n++;
            b[1] = (struct VtxhzBump){ hi, b->hi, b->off + (hi - b->lo) };
            b->hi = lo;
            i++;
        } else if (left) {
            b->hi = lo;
        } else if (right) {
            b->off += hi - b->lo;
            b->lo = hi;
        } else {
            memmove(b, b + 1, (r->vtxhz_bump_n - i - 1) * sizeof(*b));
            r->vtxhz_bump_n--;
            i--;
        }
    }
}

/*
 * HAKUX_VTXHZ_BUMP's part of an upload of `data` to guest [offset, +size):
 *  1  it went to a fresh offset; the identity copy is untouched;
 *  0  it goes to the identity copy, which no recorded draw reads differently;
 * -1  out of room: it goes to the identity copy after today's hazard check.
 */
static int vtxhz_bump_upload(PGRAPHVkState *r, hwaddr offset,
                             const uint8_t *data, VkDeviceSize size)
{
    vtxhz_bump_sync(r);

    bool queues_empty = r->draw_queue.count == 0 &&
                        r->reorder_window.count == 0;
    if (queues_empty && !r->in_command_buffer) {
        /* Nothing recorded is left to run: a finish on this thread rotated,
         * or the render thread's waited the fence. */
        vtxhz_bump_resolve(r);
        vtxhz_clear(r);
        return 0;
    }
    if (size == 0) {
        return 0;
    }

    StorageBuffer *vram = get_staging_buffer(r, BUFFER_VERTEX_RAM);
    hwaddr end = offset + size;
    bool overlap = vtxhz_bump_find(r, offset, end) != NULL;
    /* The same test today's finish takes, below */
    if (!overlap && !(queues_empty &&
                      vtxhz_overwrites(r, vram->mapped, offset, data, size))) {
        return 0;
    }

    /* The copy keeps the address's low 8 bits: attribute alignment, and
     * remap_unaligned_attributes' view of it, stay the guest's. */
    VkDeviceSize at = ROUND_UP(r->vtxhz_bump_base + r->vtxhz_bump_used, 256) +
                      (offset & 255);
    if (at + size > r->vtxhz_bump_base + r->vtxhz_bump_cap) {
        r->vtxhz_bump_full++;
        if (overlap) {
            vtxhz_bump_trim(r, offset, end);
        }
        return -1;
    }

    if (r->vtxhz_bump_n == r->vtxhz_bump_alloc) {
        r->vtxhz_bump_alloc = r->vtxhz_bump_alloc ? r->vtxhz_bump_alloc * 2 : 64;
        r->vtxhz_bump = g_renew(struct VtxhzBump, r->vtxhz_bump,
                                r->vtxhz_bump_alloc);
    }
    if (unlikely(nv2a_dbg_framedump_active())) {
        pgraph_vk_fdump_vertex_upload(r, offset, vram->mapped + offset, data,
                                      size, false);
    }
    memcpy(vram->mapped + at, data, size);
    r->vtxhz_bump[r->vtxhz_bump_n++] =
        (struct VtxhzBump){ .lo = offset, .hi = end, .off = at };
    r->vtxhz_bump_used = at + size - r->vtxhz_bump_base;
    r->vtxhz_bump_lo = MIN(r->vtxhz_bump_lo, offset);
    r->vtxhz_bump_hi = MAX(r->vtxhz_bump_hi, end);
    /* Uploaded, as the identity copy's own write marks it */
    hwaddr first = offset / TARGET_PAGE_SIZE;
    bitmap_set(get_uploaded_bitmap(r), first,
               TARGET_PAGE_ALIGN(end) / TARGET_PAGE_SIZE - first);
    r->vtxhz_bumps++;
    r->vtxhz_bump_bytes += size;
    vtxhz_log(r);
    return 1;
}

/* HAKUX_VTXHZ_BUMP: the offset to bind attribute `attr` at, given its offset
 * in the identity copy. vk/draw.c calls it while there are entries. */
VkDeviceSize pgraph_vk_vtxhz_bump_offset(PGRAPHVkState *r, int attr,
                                         VkDeviceSize ident)
{
    vtxhz_bump_sync(r);
    hwaddr lo = r->vtxhz_attr_lo[attr], hi = r->vtxhz_attr_hi[attr];
    struct VtxhzBump *b = vtxhz_bump_find(r, lo, hi);
    if (!b) {
        return ident;
    }
    if (b->lo <= lo && hi <= b->hi) {
        /* b->off >= vertex RAM's size > b->lo */
        return b->off - b->lo + ident;
    }
    /* Unreachable when the attribute reads inside its sync range: the sync
     * before the bind re-uploaded any range no one entry holds. */
    r->vtxhz_bump_partial++;
    return ident;
}

/* HAKUX_VTXHZ_BUMP: no one copy holds all of [addr, +size)'s newest bytes,
 * so the range must be uploaded again (vk/draw.c, sync_vertex_ram_buffer and
 * has_dirty_vertex_pages). */
bool pgraph_vk_vtxhz_bump_needs_copy(PGRAPHVkState *r, hwaddr addr,
                                     hwaddr size)
{
    vtxhz_bump_sync(r);
    struct VtxhzBump *b = vtxhz_bump_find(r, addr, addr + size);
    return b && !(b->lo <= addr && addr + size <= b->hi);
}

/* HAKUX_VTXHZ_BUMP: flush_memory_buffer's part for the fresh copies (vk/draw.c),
 * recorded with the identity copy's before the submit. The entries' frame, not
 * the current one: a change of the submit frame count resets current_frame
 * while the command buffer that reads them is still open. */
void pgraph_vk_vtxhz_bump_flush(PGRAPHVkState *r, VkCommandBuffer cmd)
{
    if (r->vtxhz_bump_used <= r->vtxhz_bump_flushed) {
        return;
    }
    StorageBuffer *vram = &r->frame_staging[r->vtxhz_bump_frame].vertex_ram;
    VkDeviceSize offset = r->vtxhz_bump_base + r->vtxhz_bump_flushed;
    VkDeviceSize size = r->vtxhz_bump_used - r->vtxhz_bump_flushed;

    VK_CHECK(vmaFlushAllocation(r->allocator, vram->allocation, offset, size));

    VkBufferMemoryBarrier barrier = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask = VK_ACCESS_HOST_WRITE_BIT,
        .dstAccessMask = VK_ACCESS_VERTEX_ATTRIBUTE_READ_BIT,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .buffer = vram->buffer,
        .offset = offset,
        .size = size,
    };
    OPT_STAT_INC(barrier_count);
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_HOST_BIT,
                         VK_PIPELINE_STAGE_VERTEX_INPUT_BIT, 0, 0, NULL, 1,
                         &barrier, 0, NULL);
    r->vtxhz_bump_flushed = r->vtxhz_bump_used;
}

void pgraph_vk_update_vertex_ram_buffer(PGRAPHState *pg, hwaddr offset,
                                        void *data, VkDeviceSize size)
{
    PGRAPHVkState *r = pg->vk_renderer_state;

    /* HAKUX_VTX_EXACT: sync_vertex_ram_buffer downloaded the draw's bytes */
    if (likely(!r->vtx_exact_downloaded)) {
        pgraph_vk_download_surfaces_in_range_if_dirty(pg, offset, size);
    }
    r->vtx_exact_downloaded = false;

    size_t start_bit = offset / TARGET_PAGE_SIZE;
    size_t end_bit = TARGET_PAGE_ALIGN(offset + size) / TARGET_PAGE_SIZE;
    size_t nbits = end_bit - start_bit;

    /* HAKUX_VTXHZ_BUMP: a fresh offset in place of the finish below */
    int bump = -1;
    if (unlikely(r->vtxhz_bump_cap)) {
        bump = vtxhz_bump_upload(r, offset, data, size);
        if (bump > 0) {
            nv2a_profile_inc_counter(NV2A_PROF_GEOM_BUFFER_UPDATE_1);
            return;
        }
    }

    /* Per-frame buffer: no finish needed between command buffers, each
     * frame has its own copy. Within one, see HAKUX_VTX_HAZARD above. */
    bool hazard_finished = false;
    if (bump < 0 && unlikely(r->vtxhz_on) &&
        /* Not while merged or reordered draws are being recorded: the
         * finish would flush those queues from inside their own flush. */
        r->draw_queue.count == 0 && r->reorder_window.count == 0 &&
        vtxhz_overwrites(r, get_staging_buffer(r, BUFFER_VERTEX_RAM)->mapped,
                         offset, data, size)) {
        pgraph_vk_finish(pg, VK_FINISH_REASON_VERTEX_BUFFER_DIRTY);
        r->vtxhz_finishes++;
        hazard_finished = true;
        vtxhz_log(r);
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
    for (int i = 0; i < r->ring_alloc; i++) {
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
                    vtxhz_note_attr(r, i, start,
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
            vtxhz_note_attr(r, i, start,
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
