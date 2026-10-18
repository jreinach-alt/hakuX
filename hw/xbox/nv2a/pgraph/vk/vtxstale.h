/*
 * Geforce NV2A PGRAPH Vulkan Renderer: stale vertex-RAM pages per frame (#1049)
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

/*
 * Each submit frame keeps its own copy of vertex RAM. An upload lands in the
 * current frame's copy and marks its pages stale in every other frame's
 * bitmap; rotating a frame in copies its stale pages from the outgoing frame,
 * which always holds the newest data, and clears them (issue #39 is why the
 * marks are kept on the receiving frame).
 *
 * These were one lowest-to-highest byte span per frame. Uploads are
 * scattered across VRAM, so the span covered tens of MB around a few hundred
 * KB of writes and every rotation copied all of it.
 *
 * Standalone (no qemu headers) so the selftest can build it on its own: the
 * includer provides bitmap_set, bitmap_clear, find_next_bit and
 * find_next_zero_bit (qemu/bitmap.h).
 */

#ifndef HW_XBOX_NV2A_PGRAPH_VK_VTXSTALE_H
#define HW_XBOX_NV2A_PGRAPH_VK_VTXSTALE_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* One bit per page, as the frames' uploaded bitmaps are kept */
#define VTXSTALE_PAGE_SHIFT 12
#define VTXSTALE_PAGE_SIZE ((size_t)1 << VTXSTALE_PAGE_SHIFT)

/* Mark every page that bytes [offset, offset + size) touch */
static inline void vtxstale_mark(unsigned long *stale, size_t offset,
                                 size_t size)
{
    if (size == 0) {
        return;
    }
    size_t first = offset >> VTXSTALE_PAGE_SHIFT;
    size_t last = (offset + size - 1) >> VTXSTALE_PAGE_SHIFT;
    bitmap_set(stale, first, last - first + 1);
}

/*
 * Copy every marked page from src to dst and clear its mark. nbits is the
 * bitmap's length; a run past buf_size is cut there. Returns the bytes
 * copied, and in *lo and *hi the lowest and one past the highest byte copied
 * (unchanged when nothing was).
 */
static inline size_t vtxstale_copy(uint8_t *dst, const uint8_t *src,
                                   size_t buf_size, unsigned long *stale,
                                   size_t nbits, size_t *lo, size_t *hi)
{
    size_t copied = 0;
    size_t b = find_next_bit(stale, nbits, 0);
    while (b < nbits) {
        size_t e = find_next_zero_bit(stale, nbits, b);
        size_t off = b << VTXSTALE_PAGE_SHIFT;
        size_t end = e << VTXSTALE_PAGE_SHIFT;
        if (end > buf_size) {
            end = buf_size;
        }
        if (off < end) {
            memcpy(dst + off, src + off, end - off);
            if (copied == 0) {
                *lo = off;
            }
            *hi = end;
            copied += end - off;
        }
        bitmap_clear(stale, b, e - b);
        if (e >= nbits) {
            break;
        }
        b = find_next_bit(stale, nbits, e);
    }
    return copied;
}

#endif
