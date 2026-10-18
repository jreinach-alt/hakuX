# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, ok/bad/check. Not executable, no shebang, no exit.
#
# Each submit frame keeps its own copy of vertex RAM. An upload lands in the
# current frame's copy and marks its pages stale in every other frame; rotating
# a frame in copies its stale pages from the outgoing frame (vk/vtxstale.h,
# #1049). Before, the marks were one byte span per frame, and scattered uploads
# made every rotation copy tens of MB. Before that, the range went to the next
# frame only, and the third frame of the ring read zeros (#39). This pins:
#
#   1. Correctness: every frame, when rotated in, equals the newest data byte
#      for byte. Unaligned writes, a write spanning two pages, a write at the
#      end of the buffer, empty writes, a frame never made current, and a frame
#      left out of the ring for a while, then 3000 scattered random rotations.
#   2. Cost: each rotation copies exactly the page-rounded union of what was
#      uploaded while that frame was not current: no page missed, none extra.
#      The flush range is that union's lowest to highest byte.
#
# The harness runs the marking loop from vk/vertex.c and the rotation copy from
# vk/draw.c as they stand in the tree (cut out by their anchors) against the
# real vk/vtxstale.h; a missing anchor fails the check rather than testing
# nothing.

echo "== vk/vtxstale.h: per-frame stale vertex-RAM pages"
VS="$T/vtxstale"
mkdir -p "$VS"
VS_HDR="$REPO/hw/xbox/nv2a/pgraph/vk/vtxstale.h"
VS_VTX="$REPO/hw/xbox/nv2a/pgraph/vk/vertex.c"
VS_DRAW="$REPO/hw/xbox/nv2a/pgraph/vk/draw.c"

cat > "$VS/extract.py" <<'PY'
import re, sys
vtx, draw, out = sys.argv[1:4]
L = open(vtx).read().split("\n")
a = [i for i, l in enumerate(L) if "QEMU_BUILD_BUG_ON(TARGET_PAGE_SIZE != VTXSTALE_PAGE_SIZE);" in l]
b = [i for i, l in enumerate(L) if "bitmap_set(get_uploaded_bitmap(r), start_bit, nbits);" in l]
if len(a) != 1 or len(b) != 1 or b[0] <= a[0]:
    sys.exit("vertex.c: the marking loop's anchors were not found once each, in order")
open(out + "/mark.inc", "w").write("\n".join(L[a[0]:b[0]]) + "\n")
D = open(draw).read().split("\n")
s = [i for i, l in enumerate(D) if re.fullmatch(r"\s*if \(!next_fs->vertex_ram_initialized\) \{", l)]
if len(s) != 1:
    sys.exit("draw.c: the rotation copy's anchor was found %d times" % len(s))
depth, i = 0, s[0]
while True:
    depth += D[i].count("{") - D[i].count("}")
    if depth == 0:
        break
    i += 1
    if i >= len(D):
        sys.exit("draw.c: the rotation copy never closes")
open(out + "/rotate.inc", "w").write("\n".join(D[s[0]:i + 1]) + "\n")
PY

cat > "$VS/vtxstale_test.c" <<'C'
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* qemu/bitmap.h's four, bit by bit */
#define BPL (sizeof(unsigned long) * 8)
static int test_bit_(const unsigned long *m, unsigned long i)
{
    return (m[i / BPL] >> (i % BPL)) & 1;
}
static void bitmap_set(unsigned long *m, long start, long nr)
{
    for (long i = start; i < start + nr; i++) {
        m[i / BPL] |= 1UL << (i % BPL);
    }
}
static void bitmap_clear(unsigned long *m, long start, long nr)
{
    for (long i = start; i < start + nr; i++) {
        m[i / BPL] &= ~(1UL << (i % BPL));
    }
}
static unsigned long find_next_bit(const unsigned long *m, unsigned long size,
                                   unsigned long off)
{
    for (; off < size; off++) {
        if (test_bit_(m, off)) {
            return off;
        }
    }
    return size;
}
static unsigned long find_next_zero_bit(const unsigned long *m,
                                        unsigned long size, unsigned long off)
{
    for (; off < size; off++) {
        if (!test_bit_(m, off)) {
            return off;
        }
    }
    return size;
}

/* Every copy the header and the rotation make, counted */
static uint64_t copied;
static void *counted_memcpy(void *d, const void *s, size_t n)
{
    copied += n;
    return (memcpy)(d, s, n);
}
#undef memcpy
#define memcpy(d, s, n) counted_memcpy(d, s, n)

#include <vtxstale.h>

#define NUM_SUBMIT_FRAMES 3
#define TARGET_PAGE_SIZE 4096
#define VK_WHOLE_SIZE (~0ULL)
#define QEMU_BUILD_BUG_ON(x) _Static_assert(!(x), #x)
typedef uint64_t VkDeviceSize;
typedef uint64_t hwaddr;
typedef struct {
    uint8_t *mapped;
    size_t buffer_size;
} StorageBuffer;
typedef struct {
    StorageBuffer vertex_ram;
    VkDeviceSize vertex_ram_flush_min;
    VkDeviceSize vertex_ram_flush_max;
    unsigned long *vertex_ram_stale;
    bool vertex_ram_initialized;
} FrameStagingState;
typedef struct {
    FrameStagingState frame_staging[NUM_SUBMIT_FRAMES];
    int current_frame;
    size_t bitmap_size;
} Renderer;

/* 101 pages: runs cross an unsigned long, and the last word is partial */
#define PAGES 101
#define BUF ((size_t)PAGES * TARGET_PAGE_SIZE)

static Renderer rs, *r = &rs;
static uint8_t truth[BUF];
static bool expect[NUM_SUBMIT_FRAMES][PAGES];
static size_t span_lo[NUM_SUBMIT_FRAMES], span_hi[NUM_SUBMIT_FRAMES];
static int nactive = NUM_SUBMIT_FRAMES;
static uint8_t stamp;
static uint64_t rotations, page_bytes, span_bytes, missed, count_bad,
    flush_bad, rand_page, rand_span;
static uint32_t lcg = 1049;

static uint32_t rnd(uint32_t n)
{
    lcg = lcg * 1103515245u + 12345u;
    return (lcg >> 8) % n;
}

/* vk/vertex.c, pgraph_vk_update_vertex_ram_buffer(): the other frames' marks */
static void mark_others(hwaddr offset, VkDeviceSize size)
{
    FrameStagingState *fs = &r->frame_staging[r->current_frame];
#include "mark.inc"
}

static void upload(size_t offset, size_t size)
{
    /* every byte written changes, so a missed page always differs */
    stamp++;
    for (size_t i = 0; i < size; i++) {
        uint8_t v = (uint8_t)(stamp + i * 7);
        truth[offset + i] = v == truth[offset + i] ? v + 1 : v;
    }
    memcpy(r->frame_staging[r->current_frame].vertex_ram.mapped + offset,
           truth + offset, size);
    mark_others(offset, size);
    if (size == 0) {
        return;
    }
    for (int s = 0; s < NUM_SUBMIT_FRAMES; s++) {
        if (s == r->current_frame) {
            continue;
        }
        for (size_t p = offset / TARGET_PAGE_SIZE;
             p <= (offset + size - 1) / TARGET_PAGE_SIZE; p++) {
            expect[s][p] = true;
        }
        if (offset < span_lo[s]) {
            span_lo[s] = offset;
        }
        if (offset + size > span_hi[s]) {
            span_hi[s] = offset + size;
        }
    }
}

static void rotate(void)
{
    int next_frame = (r->current_frame + 1) % nactive;
    FrameStagingState *cur_fs = &r->frame_staging[r->current_frame];
    FrameStagingState *next_fs = &r->frame_staging[next_frame];
    bool was_init = next_fs->vertex_ram_initialized;
    size_t want = 0, first = PAGES, last = 0;
    for (size_t p = 0; p < PAGES; p++) {
        if (expect[next_frame][p]) {
            want += TARGET_PAGE_SIZE;
            first = first < p ? first : p;
            last = p;
        }
    }
    if (!was_init) {
        want = BUF;
    }
    size_t span = span_hi[next_frame] > span_lo[next_frame] ?
        span_hi[next_frame] - span_lo[next_frame] : 0;

    copied = 0;
    next_fs->vertex_ram_flush_min = VK_WHOLE_SIZE;
    next_fs->vertex_ram_flush_max = 0;
    /* vk/draw.c, pgraph_vk_finish(): the rotation copy */
#include "rotate.inc"
    r->current_frame = next_frame;
    rotations++;

    if (copied != want) {
        if (count_bad++ < 3) {
            printf("rotation %llu into frame %d: copied %llu, the uploads "
                   "since it was current cover %zu\n",
                   (unsigned long long)rotations, next_frame,
                   (unsigned long long)copied, want);
        }
    }
    if (was_init && want &&
        (next_fs->vertex_ram_flush_min != first * TARGET_PAGE_SIZE ||
         next_fs->vertex_ram_flush_max != (last + 1) * TARGET_PAGE_SIZE)) {
        flush_bad++;
    }
    if (memcmp(next_fs->vertex_ram.mapped, truth, BUF)) {
        if (missed++ < 3) {
            size_t i = 0;
            while (next_fs->vertex_ram.mapped[i] == truth[i]) {
                i++;
            }
            printf("rotation %llu into frame %d: page %zu is stale\n",
                   (unsigned long long)rotations, next_frame,
                   i / TARGET_PAGE_SIZE);
        }
    }
    if (was_init) {
        page_bytes += copied;
        span_bytes += span;
    }
    memset(expect[next_frame], 0, sizeof(expect[next_frame]));
    span_lo[next_frame] = SIZE_MAX;
    span_hi[next_frame] = 0;
}

int main(void)
{
    r->bitmap_size = PAGES;
    for (int s = 0; s < NUM_SUBMIT_FRAMES; s++) {
        FrameStagingState *fs = &r->frame_staging[s];
        fs->vertex_ram.mapped = calloc(1, BUF);
        fs->vertex_ram.buffer_size = BUF;
        fs->vertex_ram_stale = calloc((PAGES + BPL - 1) / BPL,
                                      sizeof(unsigned long));
        span_lo[s] = SIZE_MAX;
    }
    /* renderer.c: all of VRAM into frame 0, which is then initialized */
    upload(0, BUF);
    r->frame_staging[0].vertex_ram_initialized = true;

    /* Frame 2 is not made current until the ring widens */
    nactive = 2;
    upload(5, 10);                          /* inside one page */
    rotate();
    upload(3 * TARGET_PAGE_SIZE - 3, 10);   /* across pages 2 and 3 */
    rotate();
    upload(BUF - 5, 5);                     /* the last bytes of the buffer */
    rotate();
    nactive = 3;
    rotate();                               /* 1 -> 2, first time current */
    rotate();
    upload(7 * TARGET_PAGE_SIZE, TARGET_PAGE_SIZE); /* exactly one page */
    rotate();
    upload(10 * TARGET_PAGE_SIZE + 9, 0);   /* empty */
    rotate();
    upload(0, 1);
    upload(BUF - 1, 1);                     /* far apart: two pages, not all */
    rotate();
    rotate();
    rotate();
    upload(20 * TARGET_PAGE_SIZE + 100, 2 * TARGET_PAGE_SIZE); /* three pages */
    upload(64 * TARGET_PAGE_SIZE - 1, 2);   /* across the long boundary */
    rotate();
    rotate();
    rotate();
    rotate();                               /* nothing new: copies nothing */

    /* Scattered uploads; frame 2 drops out of the ring and comes back */
    uint64_t p0 = page_bytes, s0 = span_bytes;
    for (int i = 0; i < 3000; i++) {
        if (i % 500 == 250) {
            nactive = nactive == 3 ? 2 : 3;
        }
        int n = rnd(12);
        for (int k = 0; k < n; k++) {
            uint32_t kind = rnd(100);
            size_t size = kind < 70 ? 1 + rnd(256) :
                          kind < 95 ? 1 + rnd(TARGET_PAGE_SIZE) :
                                      1 + rnd(3 * TARGET_PAGE_SIZE);
            size_t off;
            if (kind % 10 == 0) {
                off = BUF - size;
            } else if (kind % 10 == 1) {
                off = (1 + rnd(PAGES - 1)) * TARGET_PAGE_SIZE - 1 - rnd(8);
            } else {
                off = rnd(BUF);
            }
            if (off + size > BUF) {
                size = BUF - off;
            }
            upload(off, size);
        }
        rotate();
    }
    rand_page = page_bytes - p0;
    rand_span = span_bytes - s0;

    printf("rotations=%llu missed=%llu count=%llu flush=%llu "
           "page_bytes=%llu span_bytes=%llu random_page=%llu "
           "random_span=%llu\n",
           (unsigned long long)rotations, (unsigned long long)missed,
           (unsigned long long)count_bad, (unsigned long long)flush_bad,
           (unsigned long long)page_bytes, (unsigned long long)span_bytes,
           (unsigned long long)rand_page, (unsigned long long)rand_span);
    return rotations > 3000 && !missed && !count_bad && !flush_bad &&
           rand_page * 2 < rand_span ? 0 : 1;
}
C

# Variants: the tree as it stands, and mutants of each of the three sources
vs_variant() {   # <name> <header> <vertex.c> <draw.c>
    mkdir -p "$VS/$1"
    cp "$2" "$VS/$1/vtxstale.h"
    python3 "$VS/extract.py" "$3" "$4" "$VS/$1" > "$VS/extract-$1.log" 2>&1 &&
        cc -O1 -std=gnu11 -U_FORTIFY_SOURCE -I"$VS/$1" "$VS/vtxstale_test.c" \
            -o "$VS/test-$1" > "$VS/cc-$1.log" 2>&1
}
vs_run() { "$VS/test-$1" > "$VS/run-$1.log" 2>&1; }

vs_variant real "$VS_HDR" "$VS_VTX" "$VS_DRAW"
check "vtxstale_test builds from vk/vtxstale.h, vertex.c's marks and draw.c's rotation copy" \
    test -x "$VS/test-real"
check "every frame current byte for byte when rotated in, copying exactly the stale pages" vs_run real
if [ -s "$VS/run-real.log" ]; then echo "       $(tail -n 1 "$VS/run-real.log" | head -c 300)"; fi

# ------------------------------------------------------------ falsifications
# A mutant is caught only if it built, ran to its summary line, and failed on
# the field it is meant to break: one that does not compile, or fails some
# other way, must not read as caught.
vs_caught() {   # <name> <field>
    [ -x "$VS/test-$1" ] || return 1
    ! vs_run "$1" || return 1
    python3 -c 'import re,sys; m=re.search(r"\b%s=(\d+)" % sys.argv[2], open(sys.argv[1]).read()); sys.exit(0 if m and int(m[1]) > 0 else 1)' \
        "$VS/run-$1.log" "$2"
}
vs_differs() { bash -c '! cmp -s "$1" "$2"' _ "$1" "$2"; }

# 1. The last page counted from the size, not from the end: a write that
#    crosses a page boundary loses its second page.
sed 's/size_t last = (offset + size - 1) >> VTXSTALE_PAGE_SHIFT;/size_t last = first + ((size - 1) >> VTXSTALE_PAGE_SHIFT);/' \
    "$VS_HDR" > "$VS/hdr-round.h"
vs_variant round "$VS/hdr-round.h" "$VS_VTX" "$VS_DRAW"
check "falsification ran: the size-rounded header differs" vs_differs "$VS_HDR" "$VS/hdr-round.h"
check "FALSIFIED: the last page taken from the size misses a page" vs_caught round missed

# 2. The copy loop stops short of the last page.
sed 's/while (b < nbits) {/while (b + 1 < nbits) {/' "$VS_HDR" > "$VS/hdr-tail.h"
vs_variant tail "$VS/hdr-tail.h" "$VS_VTX" "$VS_DRAW"
check "falsification ran: the short-loop header differs" vs_differs "$VS_HDR" "$VS/hdr-tail.h"
check "FALSIFIED: a copy that never reaches the last page misses it" vs_caught tail missed

# 3. Copied pages left marked: correct bytes, copied again every rotation.
sed '/bitmap_clear(stale, b, e - b);/d' "$VS_HDR" > "$VS/hdr-noclear.h"
vs_variant noclear "$VS/hdr-noclear.h" "$VS_VTX" "$VS_DRAW"
check "falsification ran: the no-clear header differs" vs_differs "$VS_HDR" "$VS/hdr-noclear.h"
check "FALSIFIED: pages never cleared are copied again" vs_caught noclear count

# 4. The span rule this replaced: first to last marked page in one copy.
python3 - "$VS_HDR" "$VS/hdr-span.h" <<'PY'
import sys
src = open(sys.argv[1]).read()
i = src.index("static inline size_t vtxstale_copy(")
j = src.rindex("#endif")
span = '''static inline size_t vtxstale_copy(uint8_t *dst, const uint8_t *src,
                                   size_t buf_size, unsigned long *stale,
                                   size_t nbits, size_t *lo, size_t *hi)
{
    size_t first = find_next_bit(stale, nbits, 0), last = first;
    if (first >= nbits) {
        return 0;
    }
    for (size_t b = first; b < nbits; b = find_next_bit(stale, nbits, b + 1)) {
        last = b;
    }
    size_t off = first << VTXSTALE_PAGE_SHIFT;
    size_t end = (last + 1) << VTXSTALE_PAGE_SHIFT;
    if (end > buf_size) {
        end = buf_size;
    }
    memcpy(dst + off, src + off, end - off);
    bitmap_clear(stale, 0, nbits);
    *lo = off;
    *hi = end;
    return end - off;
}

'''
open(sys.argv[2], "w").write(src[:i] + span + src[j:])
PY
vs_variant span "$VS/hdr-span.h" "$VS_VTX" "$VS_DRAW"
check "falsification ran: the span header differs" vs_differs "$VS_HDR" "$VS/hdr-span.h"
check "FALSIFIED: one first-to-last span copies more than the stale pages" vs_caught span count

# 5. #39 again: an upload marks only the next frame, so the third reads stale.
sed 's/if (other == fs) {/if (other != \&r->frame_staging[(r->current_frame + 1) % NUM_SUBMIT_FRAMES]) {/' \
    "$VS_VTX" > "$VS/vertex-next.c"
vs_variant next "$VS_HDR" "$VS/vertex-next.c" "$VS_DRAW"
check "falsification ran: the next-frame-only vertex.c differs" vs_differs "$VS_VTX" "$VS/vertex-next.c"
check "FALSIFIED: marking only the next frame leaves the third stale" vs_caught next missed

# 6. A frame's first whole copy keeps the marks it gathered before it.
sed '/bitmap_clear(next_fs->vertex_ram_stale, 0,/{N;d}' "$VS_DRAW" > "$VS/draw-initclear.c"
vs_variant initclear "$VS_HDR" "$VS_VTX" "$VS/draw-initclear.c"
check "falsification ran: the draw.c without the first-copy clear differs" vs_differs "$VS_DRAW" "$VS/draw-initclear.c"
check "FALSIFIED: marks kept across the first whole copy are copied again" vs_caught initclear count
