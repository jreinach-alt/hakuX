/*
 * Translation Block Maintenance
 *
 *  Copyright (c) 2003 Fabrice Bellard
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#include "qemu/osdep.h"
#ifdef __ANDROID__
#include <android/log.h>
#endif
#include "qemu/interval-tree.h"
#include "qemu/qtree.h"
#include "exec/cputlb.h"
#include "exec/log.h"
#include "exec/page-protection.h"
#include "exec/mmap-lock.h"
#include "exec/tb-flush.h"
#include "exec/target_page.h"
#include "accel/tcg/cpu-ops.h"
#include "tb-internal.h"
#include "system/tcg.h"
#include "tcg/tcg.h"
#include "tb-hash.h"
#include "tb-context.h"
#include "tb-internal.h"
#include "internal-common.h"
#include "tb-cache-hints.h"
#ifdef CONFIG_USER_ONLY
#include "user/page-protection.h"
#define runstate_is_running()  true
#else
#include "system/runstate.h"
#endif
#include "trace.h"

#ifdef XBOX
/*
 * Sizing counters for the whole-page invalidation this fork does instead of
 * upstream's range-precise one. Defined here rather than beside their uses
 * because tb_page_add() needs one and it comes first in the file. The comment
 * that explains what they mean sits with tb_overlaps_written_range() below.
 */
uint64_t hakux_inval_events;          /* range invalidations that found a TB */
uint64_t hakux_inval_tbs_overlap;     /* ... of those TBs, bytes were written */
uint64_t hakux_inval_tbs_spared;      /* ... of those TBs, none were */
uint64_t hakux_inval_emptied;         /* events that emptied the page */
uint64_t hakux_inval_would_survive;   /* events that would NOT have, with the
                                       * range test restored */
/*
 * `em` AND `ws` ALSO CHANGED POPULATION AT #73's FIX, which the note on
 * hakux_inval_already below says of `ai` and did not say of these two. Audit
 * pass 1 M1.
 *
 * Pre-fix an already-invalid TB was never unlinked, so it held p->first_tb
 * non-NULL and `em` could not fire on any event that had visited one. The fix
 * unlinks it, so such events now empty the page and now count. `em` is
 * therefore larger post-fix for a reason that has nothing to do with what the
 * guest wrote, and `ws` -- which is gated on `em` -- moves with it.
 *
 * The six Crimson Skies soaks of 2026-09-13 are PRE-fix on all three
 * counters. Do not difference them against a post-fix run. The `ws` figures
 * from runs between 2af6def68a and the comparison fix at the bottom of
 * tb_invalidate_phys_page_range__locked() are wrong in a third way again, and
 * are over-reports.
 */
uint64_t hakux_tlb_protect_calls;     /* arming walks: the 10.6% symbol */
/*
 * TBs visited by the invalidation loop that already carried CF_INVALID.
 *
 * This exists to explain a row that otherwise cannot happen. Whole-page
 * invalidation discards every block on the page, so `emptied` should equal
 * `events` exactly -- that is registered as a leg precisely because a
 * systematic misreading of this file would show up as plausible numbers
 * everywhere else.
 *
 * But it has one benign failure mode, found by reading
 * do_tb_phys_invalidate() rather than by being surprised on a device:
 * `if (!qht_remove(&tb_ctx.htable, tb, h)) { return; }` fires **before**
 * tb_remove(), so a TB that was already invalidated stays on the page list
 * and the page does not empty. The fork's tier-1 soft invalidation sets
 * CF_INVALID without unlinking (see c174c8bde8), so such TBs exist.
 *
 * Counting them turns "em < ev, probably that" into "em < ev, and exactly
 * this many visits were already-invalid TBs, which accounts for it". An
 * impossible row that can be explained is worth much less than one that
 * cannot, and the whole point of the leg is to notice the difference.
 *
 * WHAT THIS COUNTS CHANGED with the #73 fix in do_tb_phys_invalidate, and a
 * reader comparing against the six Crimson Skies soaks of 2026-09-13 must
 * know it. Those runs measured ai/visits at 0.85-0.93: the qht_remove missed
 * on the tier-1 population, so every such TB was counted here once per store
 * to its page, for the life of the translation buffer. It is now removed on
 * its FIRST visit. tb_phys_invalidate() has ONE LIVE CALLER and one gated-off
 * one, and the difference matters because this sentence is the premise of the
 * row in hakux_inval_impossible below: translate-all.c:879
 * (tb_check_watchpoint) is live and passes page_addr == -1, and
 * translate-all.c:1131 is inside tb_gen_superblock(), dead while
 * XBOX_SUPERBLOCK_ENABLED == 0, and also passes -1. Audit pass 1 L6 -- "both
 * callers" was literally true and counted a dead caller as evidence. So
 * rm_from_page_list is false only for a TB with no page list entry to begin
 * with, which leaves tier-1 promotion as the only producer of a CF_INVALID TB
 * on a page list. Each is therefore
 * counted here exactly once and then discarded.
 *
 * THE FALSIFIER THAT WAS REGISTERED HERE DID NOT WORK, and it is replaced
 * rather than reworded. Audit pass 1 M4. It read: "ai should fall from ~0.9
 * of visits to the tier-1 promotion rate. If it does not, the #73 model is
 * wrong." Two things were wrong with it, and each alone is fatal:
 *
 *   - ai counts promoted TBs an invalidation VISITS. That is bounded ABOVE by
 *     the promotion count and has no reason to equal it -- a promoted block
 *     on a page the guest never writes is never visited and never counted.
 *     The prediction named a bound as a value.
 *   - there is no promotion count on the hakuX-pages line to compare against
 *     anyway. g_tier1_promotions_total is emitted only by a qemu_printf in
 *     tier1_maybe_reset_budget() and by hakuX-tier1 DEBUG lines that every
 *     dispatcher logcat spec drops. So ANY fall reads as confirmation: 0.30
 *     and 0.001 would both have been read as the model holding, and so would
 *     a fall caused by something else entirely -- a change in page-write mix,
 *     or fewer promotions because the 64-slot request table saturated.
 *
 * The replacement is an identity rather than a rate, it is checked PER VISIT
 * instead of read off a window, and it needs nothing on the log line that is
 * not already there: every visited block must be discarded, dead ones
 * included. It is counted by hakux_inval_impossible below -- see the "WHAT
 * MAKES IT FIRE" paragraph there, which names the pre-fix value it would have
 * carried. `ai` keeps its job of SIZING the population and loses its job of
 * proving anything.
 */
uint64_t hakux_inval_already;
/*
 * THE EVENT: a VISIT. Every TB the whole-page invalidation loop walks over.
 *
 * This counter was called `hakux_tb_invalidated` until 2026-09-13 and was
 * reported on the always-on hakuX-pages line as "blocks tossed". It is the
 * numerator of the retracted 2.8:1 retranslation waste ratio, and of the
 * "9,500 blocks discarded per 120 frames" that went with it. A visit is not a
 * discard: tb_phys_invalidate__locked -> do_tb_phys_invalidate early-returns
 * when qht_remove fails, and that return is BEFORE tb_remove, so an
 * already-invalid TB is counted, left on the page list, and counted again on
 * every later store to that page. The count therefore grows with how clogged
 * the list is, not with how much work was thrown away.
 *
 * It is renamed rather than moved, because visits/discards is itself the
 * measure of that clog and worth reading. hakux_tb_discarded below is the
 * discard count, and the split between the two is hakux_inval_already.
 */
uint64_t hakux_tb_visited;
/*
 * THE EVENT: a DISCARD. TBs really unlinked, past the early return.
 *
 * Incremented inside do_tb_phys_invalidate after qht_remove has succeeded and
 * before tb_remove, so it is reached exactly once per block that is really
 * taken out of the hash table and off the page list.
 *
 * Note the population is wider than hakux_tb_visited's: this counts EVERY
 * caller of do_tb_phys_invalidate, while visits are counted only in the
 * whole-page loop below. In a softmmu build the other live caller is
 * tb_check_watchpoint(); tb_gen_superblock() is inert while
 * XBOX_SUPERBLOCK_ENABLED is 0. So `discarded - (visited - already)` is the
 * traffic from outside the loop, and is expected to be ~0 rather than exactly
 * 0. The exact identity is the per-visit one asserted by
 * hakux_inval_impossible.
 */
uint64_t hakux_tb_discarded;
/*
 * Did THIS call to do_tb_phys_invalidate() get past the early return?
 *
 * The counter above cannot answer that question. It is a global, and the
 * whole-page loop used to infer "my TB was discarded" by reading it either
 * side of the call -- which is only sound if this thread is the only writer.
 * Audit pass 1 M3: it is not, and "the Xbox has one vCPU" is a different
 * claim from "there is one writer". assert_memory_lock() is empty in softmmu,
 * the page locks are per page while the counter is global, and
 * do_tb_phys_invalidate() is reachable today from a non-vCPU thread through
 * system/physmem.c invalidate_and_set_dirty() -> tb_invalidate_phys_range()
 * on whatever thread performs a device or DMA write -- IDE/DVD here.
 * tb_invalidate_phys_range_fast()'s own comment says it runs with the iothread
 * mutex not held.
 *
 * That race broke the impossible row in the direction that READS AS HEALTHY:
 * a DMA discard on page Q, landing between the two reads, made the delta
 * nonzero and hid a genuine violation on page P. This flag is __thread and is
 * written only by this thread's own call, so the row no longer depends on any
 * cross-thread quantity.
 *
 * STILL NOT FIXED, and stated rather than left implied: hakux_tb_visited,
 * hakux_inval_already and hakux_tb_discarded themselves are non-atomic
 * globals written from both threads, so their absolute values and every ratio
 * built from them are approximate by however much DMA-side invalidation
 * traffic there is. Making them qatomic_inc__nocheck is the fix; it is not
 * done here because it changes what every historical figure means, and the
 * impossible row -- the one thing that had to be exact -- no longer needs it.
 */
static __thread bool hakux_tb_discarded_here;
/*
 * THE IMPOSSIBLE ROW. Must read zero, and is built to, deliberately.
 *
 * #69 exists because an impossible row appeared by accident -- 0.38 guest
 * instructions per generated block -- and was the only thing that made two
 * silently-wrong counters findable. A probe whose every row is plausible has
 * no check in it, so this one carries a row that cannot happen if the model
 * behind the counters above is right.
 *
 * The model, RESTATED for the #73 fix -- read this before comparing a run
 * against anything measured before 2026-09-14.
 *
 * The old model was `live <=> discarded`, exactly, per visit. Its second half
 * relied on a bug: an already-invalid TB was not findable under the hash
 * do_tb_phys_invalidate computed, because that hash included CF_INVALID while
 * the insertion hash could not. Masking the bit off is #73's fix, and it
 * makes the reverse implication FALSE ON PURPOSE: a tier-1-promoted TB is
 * already invalid AND is now really discarded, which is the entire point.
 *
 * What survives, and is what this counts: a LIVE TB must always be discarded.
 * A live TB sits in tb_ctx.htable under the hash tb_link_page() inserted it
 * with, do_tb_phys_invalidate now computes that same hash, so qht_remove must
 * find it. There is no world in which a live block on a page list is not in
 * the table.
 *
 * It is not a tautology of the patch. It fires if a live TB is absent from
 * the htable, if tb_link_page()'s hash inputs ever diverge from
 * do_tb_phys_invalidate's again, or if anything clears CF_INVALID without
 * re-inserting. A nonzero value means the visit accounting is wrong and NO
 * ratio derived from these counters may be quoted.
 *
 * AND THE HALF THAT WAS DROPPED COMES BACK, in the direction that is true
 * after the fix instead of the one that was true before it. Audit pass 1 M4
 * moved #73's proof onto a rate comparison that could not be made; this is
 * the same claim as an identity that can. The old model said a dead TB is
 * never discarded. The new one says a dead TB visited by this loop is ALWAYS
 * discarded -- because it sits in tb_ctx.htable under a hash without
 * CF_INVALID while carrying it, and masking the bit off is precisely what
 * makes do_tb_phys_invalidate() find it. So the row is now simply: a block
 * this loop walked over and committed to discarding was not discarded.
 *
 * WHAT MAKES IT FIRE. Not a tautology of the patch, and not a condition the
 * patch forces: it is the #73 defect itself, counted. Pre-fix this row would
 * have read 85-93% OF VISITS -- that is exactly what the six Crimson Skies
 * soaks of 2026-09-13 measured as ai/visits, every one of which was a visit
 * whose qht_remove missed. Revert the mask at the hash below and xx goes from
 * 0 to roughly nine tenths of visits on the next soak. It also fires if
 * tb_link_page()'s hash inputs diverge from do_tb_phys_invalidate()'s again,
 * if anything clears CF_INVALID without re-inserting, or if a future caller
 * reaches do_tb_phys_invalidate() with rm_from_page_list false for a TB that
 * IS on a page list -- which would strand a block in exactly the #73 shape.
 * Both of tb_phys_invalidate()'s callers pass -1 today, so nothing does.
 *
 * It survives the range test's restoration (937848c9e7, #68) unchanged,
 * because the check sits where the loop is already committed to discarding:
 * with the test restored a spared block never reaches here, and a dead block
 * still does, that commit's `!tb_live` clause being deliberate about it.
 *
 * The second-writer caveat that used to sit here named the wrong axis -- see
 * hakux_tb_discarded_here above. It said a second vCPU, and the Xbox has one;
 * the real second writer is the DMA/device thread, which exists today. The
 * row no longer infers the discard from a global delta, so that race can
 * neither manufacture nor hide a violation here. It still perturbs the
 * MAGNITUDE of visits/already/discarded; nothing on the log line declares
 * that, and no ratio built from them is exact.
 */
uint64_t hakux_inval_impossible;
/*
 * THE CROSS-COUNTER IDENTITIES, and WHICH ONE HOLDS DEPENDS ON THE PREDICATE.
 *
 * Written down because leaving it implicit voided a device arm. #68's arm ran
 * six soaks on 2026-09-14 and docs/testing/perf/tcg_pages.py declared arm B
 * VOID in 21 of 21 windows on `sp + ov == di`, reported as "two counts of the
 * same live population that must agree exactly". They are not two counts of
 * the same population once the range test is restored, and the held commit's
 * own message says so. The counters were coherent; the identity the tool
 * checked was a pre-#68 one that nothing had dated. See
 * docs/investigations/issue68-arm-void.md.
 *
 * There are three, and only the first is invariant across the predicate:
 *
 * (1) THE POPULATION IDENTITY, and it holds on BOTH sides of #68:
 *
 *         visited == ov + sp + ai
 *
 *     Every block the loop walks is counted once in `visited`, and exactly
 *     once more as either already-invalid (`ai`) or live -- and a live block
 *     is split by the overlap test into `ov` (bytes written) and `sp`
 *     (not written, accumulated as tbs_live - tbs_overlap). The split is made
 *     BEFORE the discard predicate is applied, deliberately, so the predicate
 *     cannot select its own population. This is the identity to check first.
 *
 *     It is exact in arithmetic and NOT exact on the log line: `visited` is
 *     printed on the first hakuX-pages line and ov/sp/ai on the second, two
 *     __android_log_print calls with the guest CPU thread running in between,
 *     so a visit in flight lands on one side only. Measured slip on the six
 *     soaks: 0 in most windows, +/-42 in the two boot windows of one run,
 *     cancelling to 0 over the run. A slip that does not cancel, or one at
 *     steady state, is not a boundary effect.
 *
 * (2) THE DISCARD IDENTITY, PRE-#68 -- whole-page invalidation:
 *
 *         di == ov + sp    (equivalently: every live visited block dies)
 *
 *     Holds because the loop discards unconditionally and, before #73's fix,
 *     an already-invalid block took do_tb_phys_invalidate()'s early return
 *     and so was NOT counted in `di`. Both terms are on one log line, so this
 *     one is exact. Measured: 22 of 22 windows on all three arm-A soaks at
 *     117203fe9b.
 *
 * (3) THE DISCARD IDENTITY, POST-#68 -- the range test restored (937848c9e7):
 *
 *         di == ov + ai
 *
 *     A live block whose bytes the write missed is now SPARED, so `sp` leaves
 *     the discard side entirely -- that is the whole change. What is discarded
 *     is the live-and-hit population (`ov`) plus the already-invalid one
 *     (`ai`), which #73's mask makes findable and #68's `!tb_live` clause
 *     discards whatever the write touched. Also exact, both terms on one line.
 *     Measured: 22 of 22 windows on all three arm-B soaks at 937848c9e7,
 *     exactly, with no slack term needed.
 *
 *     The tier >= 2 / superblock clause of that predicate would add a third
 *     term. It is not modelled here for the same reason it is not modelled at
 *     the `ws` site below: XBOX_SUPERBLOCK_ENABLED is 0 and tb_gen_superblock()
 *     is the only producer, so it is a term nothing can currently reach. It
 *     must be added on the day that flag is flipped, and this identity is the
 *     thing that will break if it is not.
 *
 * WHY BOTH (2) AND (3) MATTER RATHER THAN JUST THE CURRENT ONE. An instrument
 * that hard-codes either is wrong on one side of the fold, and the two arms of
 * #68's A/B sit on opposite sides. The check that is honest across a fold is
 * to test both and report WHICH MODEL THE RUN MATCHED -- a run matching
 * neither is the void condition, and two arms matching different models are
 * comparable on `visited`, `ov`, `sp`, `ai`, `em`, `pr` and `cg`, which are
 * counted identically on both, and NOT comparable on anything derived from
 * `di` alone. tcg_pages.py does that as of this commit.
 *
 * `di` REMAINS THE ONE WITH A WIDER POPULATION, on both sides: it counts every
 * caller of do_tb_phys_invalidate() and the whole-page loop is only one of
 * them, so (2) and (3) carry tb_check_watchpoint()'s traffic as an error term.
 * It measured zero on all six soaks. It is not guaranteed zero, and a nonzero
 * residual on these two identities should be checked against that before it is
 * called a defect.
 */
#endif

/* List iterators for lists of tagged pointers in TranslationBlock. */
#define TB_FOR_EACH_TAGGED(head, tb, n, field)                          \
    for (n = (head) & 1, tb = (TranslationBlock *)((head) & ~1);        \
         tb; tb = (TranslationBlock *)tb->field[n], n = (uintptr_t)tb & 1, \
             tb = (TranslationBlock *)((uintptr_t)tb & ~1))

#define TB_FOR_EACH_JMP(head_tb, tb, n)                                 \
    TB_FOR_EACH_TAGGED((head_tb)->jmp_list_head, tb, n, jmp_list_next)

static bool tb_cmp(const void *ap, const void *bp)
{
    const TranslationBlock *a = ap;
    const TranslationBlock *b = bp;

    return ((tb_cflags(a) & CF_PCREL || a->pc == b->pc) &&
            a->cs_base == b->cs_base &&
            a->flags == b->flags &&
            (tb_cflags(a) & ~CF_INVALID) == (tb_cflags(b) & ~CF_INVALID) &&
            tb_page_addr0(a) == tb_page_addr0(b) &&
            tb_page_addr1(a) == tb_page_addr1(b));
}

static bool inv_tb_cmp(const void *ap, const void *bp)
{
    const TranslationBlock *a = ap, *b = bp;
    return tb_cmp(ap, bp) && a->ihash == b->ihash;
}

void tb_htable_init(void)
{
    unsigned int mode = QHT_MODE_AUTO_RESIZE;

    qht_init(&tb_ctx.htable, tb_cmp, CODE_GEN_HTABLE_SIZE, mode);
    qht_init(&tb_ctx.inv_htable, inv_tb_cmp, CODE_GEN_HTABLE_SIZE, mode);
}

typedef struct PageDesc PageDesc;

#ifdef CONFIG_USER_ONLY

/*
 * In user-mode page locks aren't used; mmap_lock is enough.
 */
#define assert_page_locked(pd) tcg_debug_assert(have_mmap_lock())

static inline void tb_lock_pages(const TranslationBlock *tb) { }

/*
 * For user-only, since we are protecting all of memory with a single lock,
 * and because the two pages of a TranslationBlock are always contiguous,
 * use a single data structure to record all TranslationBlocks.
 */
static IntervalTreeRoot tb_root;

static void tb_remove_all(void)
{
    /*
     * Only called from tb_flush__exclusive_or_serial, where we have already
     * asserted that we're in an exclusive state.
     */
    memset(&tb_root, 0, sizeof(tb_root));
}

/* Call with mmap_lock held. */
static void tb_record(TranslationBlock *tb)
{
    vaddr addr;
    int flags;

    assert_memory_lock();
    tb->itree.last = tb->itree.start + tb->size - 1;

    /* translator_loop() must have made all TB pages non-writable */
    addr = tb_page_addr0(tb);
    flags = page_get_flags(addr);
    assert(!(flags & PAGE_WRITE));

    addr = tb_page_addr1(tb);
    if (addr != -1) {
        flags = page_get_flags(addr);
        assert(!(flags & PAGE_WRITE));
    }

    interval_tree_insert(&tb->itree, &tb_root);
}

/* Call with mmap_lock held. */
static void tb_remove(TranslationBlock *tb)
{
    assert_memory_lock();
    interval_tree_remove(&tb->itree, &tb_root);
}

/* TODO: For now, still shared with translate-all.c for system mode. */
#define PAGE_FOR_EACH_TB(start, last, pagedesc, T, N)   \
    for (T = foreach_tb_first(start, last),             \
         N = foreach_tb_next(T, start, last);           \
         T != NULL;                                     \
         T = N, N = foreach_tb_next(N, start, last))

typedef TranslationBlock *PageForEachNext;

static PageForEachNext foreach_tb_first(tb_page_addr_t start,
                                        tb_page_addr_t last)
{
    IntervalTreeNode *n = interval_tree_iter_first(&tb_root, start, last);
    return n ? container_of(n, TranslationBlock, itree) : NULL;
}

static PageForEachNext foreach_tb_next(PageForEachNext tb,
                                       tb_page_addr_t start,
                                       tb_page_addr_t last)
{
    IntervalTreeNode *n;

    if (tb) {
        n = interval_tree_iter_next(&tb->itree, start, last);
        if (n) {
            return container_of(n, TranslationBlock, itree);
        }
    }
    return NULL;
}

#else
/*
 * In system mode we want L1_MAP to be based on ram offsets.
 */
#define L1_MAP_ADDR_SPACE_BITS  HOST_LONG_BITS

/* Size of the L2 (and L3, etc) page tables.  */
#define V_L2_BITS 10
#define V_L2_SIZE (1 << V_L2_BITS)

/*
 * L1 Mapping properties
 */
static int v_l1_size;
static int v_l1_shift;
static int v_l2_levels;

/*
 * The bottom level has pointers to PageDesc, and is indexed by
 * anything from 4 to (V_L2_BITS + 3) bits, depending on target page size.
 */
#define V_L1_MIN_BITS 4
#define V_L1_MAX_BITS (V_L2_BITS + 3)
#define V_L1_MAX_SIZE (1 << V_L1_MAX_BITS)

static void *l1_map[V_L1_MAX_SIZE];

struct PageDesc {
    QemuSpin lock;
    /* list of TBs intersecting this ram page */
    uintptr_t first_tb;
#if HAKUX_SMALL_BLOCK_INSNS
    /*
     * How many times this page has been emptied of translated code, saturating
     * at the latch threshold, and the latch itself. Upstream's PageDesc has no
     * counters at all; these are the fork's. Written only under @lock, from
     * the invalidation path that already holds it.
     */
    uint16_t empties;
    bool small_blocks;
#endif
};

void page_table_config_init(void)
{
    uint32_t v_l1_bits;

    assert(TARGET_PAGE_BITS);
    /* The bits remaining after N lower levels of page tables.  */
    v_l1_bits = (L1_MAP_ADDR_SPACE_BITS - TARGET_PAGE_BITS) % V_L2_BITS;
    if (v_l1_bits < V_L1_MIN_BITS) {
        v_l1_bits += V_L2_BITS;
    }

    v_l1_size = 1 << v_l1_bits;
    v_l1_shift = L1_MAP_ADDR_SPACE_BITS - TARGET_PAGE_BITS - v_l1_bits;
    v_l2_levels = v_l1_shift / V_L2_BITS - 1;

    assert(v_l1_bits <= V_L1_MAX_BITS);
    assert(v_l1_shift % V_L2_BITS == 0);
    assert(v_l2_levels >= 0);
}

static PageDesc *page_find_alloc(tb_page_addr_t index, bool alloc)
{
    PageDesc *pd;
    void **lp;

    /* Level 1.  Always allocated.  */
    lp = l1_map + ((index >> v_l1_shift) & (v_l1_size - 1));

    /* Level 2..N-1.  */
    for (int i = v_l2_levels; i > 0; i--) {
        void **p = qatomic_rcu_read(lp);

        if (p == NULL) {
            void *existing;

            if (!alloc) {
                return NULL;
            }
            p = g_new0(void *, V_L2_SIZE);
            existing = qatomic_cmpxchg(lp, NULL, p);
            if (unlikely(existing)) {
                g_free(p);
                p = existing;
            }
        }

        lp = p + ((index >> (i * V_L2_BITS)) & (V_L2_SIZE - 1));
    }

    pd = qatomic_rcu_read(lp);
    if (pd == NULL) {
        void *existing;

        if (!alloc) {
            return NULL;
        }

        pd = g_new0(PageDesc, V_L2_SIZE);
        for (int i = 0; i < V_L2_SIZE; i++) {
            qemu_spin_init(&pd[i].lock);
        }

        existing = qatomic_cmpxchg(lp, NULL, pd);
        if (unlikely(existing)) {
            for (int i = 0; i < V_L2_SIZE; i++) {
                qemu_spin_destroy(&pd[i].lock);
            }
            g_free(pd);
            pd = existing;
        }
    }

    return pd + (index & (V_L2_SIZE - 1));
}

static inline PageDesc *page_find(tb_page_addr_t index)
{
    return page_find_alloc(index, false);
}

/**
 * struct page_entry - page descriptor entry
 * @pd:     pointer to the &struct PageDesc of the page this entry represents
 * @index:  page index of the page
 * @locked: whether the page is locked
 *
 * This struct helps us keep track of the locked state of a page, without
 * bloating &struct PageDesc.
 *
 * A page lock protects accesses to all fields of &struct PageDesc.
 *
 * See also: &struct page_collection.
 */
struct page_entry {
    PageDesc *pd;
    tb_page_addr_t index;
    bool locked;
};

/**
 * struct page_collection - tracks a set of pages (i.e. &struct page_entry's)
 * @tree:   Binary search tree (BST) of the pages, with key == page index
 * @max:    Pointer to the page in @tree with the highest page index
 *
 * To avoid deadlock we lock pages in ascending order of page index.
 * When operating on a set of pages, we need to keep track of them so that
 * we can lock them in order and also unlock them later. For this we collect
 * pages (i.e. &struct page_entry's) in a binary search @tree. Given that the
 * @tree implementation we use does not provide an O(1) operation to obtain the
 * highest-ranked element, we use @max to keep track of the inserted page
 * with the highest index. This is valuable because if a page is not in
 * the tree and its index is higher than @max's, then we can lock it
 * without breaking the locking order rule.
 *
 * Note on naming: 'struct page_set' would be shorter, but we already have a few
 * page_set_*() helpers, so page_collection is used instead to avoid confusion.
 *
 * See also: page_collection_lock().
 */
struct page_collection {
    QTree *tree;
    struct page_entry *max;
};

typedef int PageForEachNext;
#define PAGE_FOR_EACH_TB(start, last, pagedesc, tb, n) \
    TB_FOR_EACH_TAGGED((pagedesc)->first_tb, tb, n, page_next)

#ifdef CONFIG_DEBUG_TCG

static __thread GHashTable *ht_pages_locked_debug;

static void ht_pages_locked_debug_init(void)
{
    if (ht_pages_locked_debug) {
        return;
    }
    ht_pages_locked_debug = g_hash_table_new(NULL, NULL);
}

static bool page_is_locked(const PageDesc *pd)
{
    PageDesc *found;

    ht_pages_locked_debug_init();
    found = g_hash_table_lookup(ht_pages_locked_debug, pd);
    return !!found;
}

static void page_lock__debug(PageDesc *pd)
{
    ht_pages_locked_debug_init();
    g_assert(!page_is_locked(pd));
    g_hash_table_insert(ht_pages_locked_debug, pd, pd);
}

static void page_unlock__debug(const PageDesc *pd)
{
    bool removed;

    ht_pages_locked_debug_init();
    g_assert(page_is_locked(pd));
    removed = g_hash_table_remove(ht_pages_locked_debug, pd);
    g_assert(removed);
}

static void do_assert_page_locked(const PageDesc *pd,
                                  const char *file, int line)
{
    if (unlikely(!page_is_locked(pd))) {
        error_report("assert_page_lock: PageDesc %p not locked @ %s:%d",
                     pd, file, line);
        abort();
    }
}
#define assert_page_locked(pd) do_assert_page_locked(pd, __FILE__, __LINE__)

void assert_no_pages_locked(void)
{
    ht_pages_locked_debug_init();
    g_assert(g_hash_table_size(ht_pages_locked_debug) == 0);
}

#else /* !CONFIG_DEBUG_TCG */

static inline void page_lock__debug(const PageDesc *pd) { }
static inline void page_unlock__debug(const PageDesc *pd) { }
static inline void assert_page_locked(const PageDesc *pd) { }

#endif /* CONFIG_DEBUG_TCG */

static void page_lock(PageDesc *pd)
{
    page_lock__debug(pd);
    qemu_spin_lock(&pd->lock);
}

/* Like qemu_spin_trylock, returns false on success */
static bool page_trylock(PageDesc *pd)
{
    bool busy = qemu_spin_trylock(&pd->lock);
    if (!busy) {
        page_lock__debug(pd);
    }
    return busy;
}

static void page_unlock(PageDesc *pd)
{
    qemu_spin_unlock(&pd->lock);
    page_unlock__debug(pd);
}

void tb_lock_page0(tb_page_addr_t paddr)
{
    page_lock(page_find_alloc(paddr >> TARGET_PAGE_BITS, true));
}

/*
 * Defined in translate-all.c, which owns both sites that arm jmp_trans.
 * Declared here rather than in a header to match how this fork already
 * shares its accel/tcg globals (see the extern block in profile.c).
 */
extern __thread bool hakux_jmp_trans_armed;

void tb_lock_page1(tb_page_addr_t paddr0, tb_page_addr_t paddr1)
{
    tb_page_addr_t pindex0 = paddr0 >> TARGET_PAGE_BITS;
    tb_page_addr_t pindex1 = paddr1 >> TARGET_PAGE_BITS;
    PageDesc *pd0, *pd1;

    /*
     * AUDIT H1'S GUARD. This function's out-of-order branch below ends in
     * siglongjmp(tcg_ctx->jmp_trans, -3), so calling it without a live frame
     * that armed jmp_trans is undefined behaviour -- a jump into a returned
     * stack frame with two page spinlocks held. That was the state of
     * translate-all.c's recycle path and of tb_gen_superblock() from
     * 255d110496 until 2026-09-14.
     *
     * WHAT MAKES THIS FIRE, stated because a guard whose condition its own
     * patch forces true is not a guard. It is NOT implied by anything below:
     * nothing in this file sets the flag, it is cleared at the top of both
     * tb_gen_code() and tb_gen_superblock(), and it is true only between a
     * sigsetjmp and the return of the frame that armed it. So it fires on the
     * FIRST call from any caller outside such a frame, whatever the page
     * order and whether or not another thread holds the lock -- which is the
     * point, because the contention race itself is not reproducible on this
     * fleet. Concretely: put the tb_lock_page1() call back in the recycle
     * path (translate-all.c) and this aborts on the first recycled two-page
     * block, i.e. within seconds of boot. It would also fire if a future
     * caller reached translator_loop()'s tb_lock_page1() through a path that
     * does not run inside setjmp_gen_code() or tb_gen_superblock().
     *
     * It does NOT check that the armed frame is the RIGHT one. Nesting would
     * defeat it, and nothing nests today: translate_code() is called from
     * exactly three sites, all in translate-all.c, all inside these two
     * frames.
     */
    assert(hakux_jmp_trans_armed);

    if (pindex0 == pindex1) {
        /* Identical pages, and the first page is already locked. */
        return;
    }

    pd1 = page_find_alloc(pindex1, true);
    if (pindex0 < pindex1) {
        /* Correct locking order, we may block. */
        page_lock(pd1);
        return;
    }

    /* Incorrect locking order, we cannot block lest we deadlock. */
    if (!page_trylock(pd1)) {
        return;
    }

    /*
     * Drop the lock on page0 and get both page locks in the right order.
     * Restart translation via longjmp.
     */
    pd0 = page_find_alloc(pindex0, false);
    page_unlock(pd0);
    page_lock(pd1);
    page_lock(pd0);
    siglongjmp(tcg_ctx->jmp_trans, -3);
}

void tb_unlock_page1(tb_page_addr_t paddr0, tb_page_addr_t paddr1)
{
    tb_page_addr_t pindex0 = paddr0 >> TARGET_PAGE_BITS;
    tb_page_addr_t pindex1 = paddr1 >> TARGET_PAGE_BITS;

    if (pindex0 != pindex1) {
        page_unlock(page_find_alloc(pindex1, false));
    }
}

static void tb_lock_pages(TranslationBlock *tb)
{
    tb_page_addr_t paddr0 = tb_page_addr0(tb);
    tb_page_addr_t paddr1 = tb_page_addr1(tb);
    tb_page_addr_t pindex0 = paddr0 >> TARGET_PAGE_BITS;
    tb_page_addr_t pindex1 = paddr1 >> TARGET_PAGE_BITS;

    if (unlikely(paddr0 == -1)) {
        return;
    }
    if (unlikely(paddr1 != -1) && pindex0 != pindex1) {
        if (pindex0 < pindex1) {
            page_lock(page_find_alloc(pindex0, true));
            page_lock(page_find_alloc(pindex1, true));
            return;
        }
        page_lock(page_find_alloc(pindex1, true));
    }
    page_lock(page_find_alloc(pindex0, true));
}

void tb_unlock_pages(TranslationBlock *tb)
{
    tb_page_addr_t paddr0 = tb_page_addr0(tb);
    tb_page_addr_t paddr1 = tb_page_addr1(tb);
    tb_page_addr_t pindex0 = paddr0 >> TARGET_PAGE_BITS;
    tb_page_addr_t pindex1 = paddr1 >> TARGET_PAGE_BITS;

    if (unlikely(paddr0 == -1)) {
        return;
    }
    if (unlikely(paddr1 != -1) && pindex0 != pindex1) {
        page_unlock(page_find_alloc(pindex1, false));
    }
    page_unlock(page_find_alloc(pindex0, false));
}

static inline struct page_entry *
page_entry_new(PageDesc *pd, tb_page_addr_t index)
{
    struct page_entry *pe = g_malloc(sizeof(*pe));

    pe->index = index;
    pe->pd = pd;
    pe->locked = false;
    return pe;
}

static void page_entry_destroy(gpointer p)
{
    struct page_entry *pe = p;

    g_assert(pe->locked);
    page_unlock(pe->pd);
    g_free(pe);
}

/* returns false on success */
static bool page_entry_trylock(struct page_entry *pe)
{
    bool busy = page_trylock(pe->pd);
    if (!busy) {
        g_assert(!pe->locked);
        pe->locked = true;
    }
    return busy;
}

static void do_page_entry_lock(struct page_entry *pe)
{
    page_lock(pe->pd);
    g_assert(!pe->locked);
    pe->locked = true;
}

static gboolean page_entry_lock(gpointer key, gpointer value, gpointer data)
{
    struct page_entry *pe = value;

    do_page_entry_lock(pe);
    return FALSE;
}

static gboolean page_entry_unlock(gpointer key, gpointer value, gpointer data)
{
    struct page_entry *pe = value;

    if (pe->locked) {
        pe->locked = false;
        page_unlock(pe->pd);
    }
    return FALSE;
}

/*
 * Trylock a page, and if successful, add the page to a collection.
 * Returns true ("busy") if the page could not be locked; false otherwise.
 */
static bool page_trylock_add(struct page_collection *set, tb_page_addr_t addr)
{
    tb_page_addr_t index = addr >> TARGET_PAGE_BITS;
    struct page_entry *pe;
    PageDesc *pd;

    pe = q_tree_lookup(set->tree, &index);
    if (pe) {
        return false;
    }

    pd = page_find(index);
    if (pd == NULL) {
        return false;
    }

    pe = page_entry_new(pd, index);
    q_tree_insert(set->tree, &pe->index, pe);

    /*
     * If this is either (1) the first insertion or (2) a page whose index
     * is higher than any other so far, just lock the page and move on.
     */
    if (set->max == NULL || pe->index > set->max->index) {
        set->max = pe;
        do_page_entry_lock(pe);
        return false;
    }
    /*
     * Try to acquire out-of-order lock; if busy, return busy so that we acquire
     * locks in order.
     */
    return page_entry_trylock(pe);
}

static gint tb_page_addr_cmp(gconstpointer ap, gconstpointer bp, gpointer udata)
{
    tb_page_addr_t a = *(const tb_page_addr_t *)ap;
    tb_page_addr_t b = *(const tb_page_addr_t *)bp;

    if (a == b) {
        return 0;
    } else if (a < b) {
        return -1;
    }
    return 1;
}

/*
 * Lock a range of pages ([@start,@last]) as well as the pages of all
 * intersecting TBs.
 * Locking order: acquire locks in ascending order of page index.
 */
static struct page_collection *page_collection_lock(tb_page_addr_t start,
                                                    tb_page_addr_t last)
{
    struct page_collection *set = g_malloc(sizeof(*set));
    tb_page_addr_t index;
    PageDesc *pd;

    start >>= TARGET_PAGE_BITS;
    last >>= TARGET_PAGE_BITS;
    g_assert(start <= last);

    set->tree = q_tree_new_full(tb_page_addr_cmp, NULL, NULL,
                                page_entry_destroy);
    set->max = NULL;
    assert_no_pages_locked();

 retry:
    q_tree_foreach(set->tree, page_entry_lock, NULL);

    for (index = start; index <= last; index++) {
        TranslationBlock *tb;
        PageForEachNext n;

        pd = page_find(index);
        if (pd == NULL) {
            continue;
        }
        if (page_trylock_add(set, index << TARGET_PAGE_BITS)) {
            q_tree_foreach(set->tree, page_entry_unlock, NULL);
            goto retry;
        }
        assert_page_locked(pd);
        PAGE_FOR_EACH_TB(unused, unused, pd, tb, n) {
            if (page_trylock_add(set, tb_page_addr0(tb)) ||
                (tb_page_addr1(tb) != -1 &&
                 page_trylock_add(set, tb_page_addr1(tb)))) {
                /* drop all locks, and reacquire in order */
                q_tree_foreach(set->tree, page_entry_unlock, NULL);
                goto retry;
            }
        }
    }
    return set;
}

static void page_collection_unlock(struct page_collection *set)
{
    /* entries are unlocked and freed via page_entry_destroy */
    q_tree_destroy(set->tree);
    g_free(set);
}

/* Set to NULL all the 'first_tb' fields in all PageDescs. */
static void tb_remove_all_1(int level, void **lp)
{
    int i;

    if (*lp == NULL) {
        return;
    }
    if (level == 0) {
        PageDesc *pd = *lp;

        for (i = 0; i < V_L2_SIZE; ++i) {
            page_lock(&pd[i]);
            pd[i].first_tb = (uintptr_t)NULL;
            page_unlock(&pd[i]);
        }
    } else {
        void **pp = *lp;

        for (i = 0; i < V_L2_SIZE; ++i) {
            tb_remove_all_1(level - 1, pp + i);
        }
    }
}

static void tb_remove_all(void)
{
    int i, l1_sz = v_l1_size;

    for (i = 0; i < l1_sz; i++) {
        tb_remove_all_1(v_l2_levels, l1_map + i);
    }
}

/*
 * Add the tb in the target page and protect it if necessary.
 * Called with @p->lock held.
 */
static void tb_page_add(PageDesc *p, TranslationBlock *tb, unsigned int n)
{
    bool page_already_protected;

    assert_page_locked(p);

    tb->page_next[n] = p->first_tb;
    page_already_protected = p->first_tb != 0;
    p->first_tb = (uintptr_t)tb | n;

    /*
     * If some code is already present, then the pages are already
     * protected. So we handle the case where only the first TB is
     * allocated in a physical page.
     */
    if (!page_already_protected) {
        /*
         * Arming walks every TLB entry on every CPU (tlb_reset_dirty, 10.6%
         * self of the bounding thread). It happens only here, on a page going
         * empty -> non-empty, so this counter is the call count of that walk
         * and the thing any change in this area has to move.
         */
#ifdef XBOX
        hakux_tlb_protect_calls++;
#endif
        tlb_protect_code(tb->page_addr[n] & TARGET_PAGE_MASK);
    }
}

static void tb_record(TranslationBlock *tb)
{
    tb_page_addr_t paddr0 = tb_page_addr0(tb);
    tb_page_addr_t paddr1 = tb_page_addr1(tb);
    tb_page_addr_t pindex0 = paddr0 >> TARGET_PAGE_BITS;
    tb_page_addr_t pindex1 = paddr1 >> TARGET_PAGE_BITS;

    assert(paddr0 != -1);
    if (unlikely(paddr1 != -1) && pindex0 != pindex1) {
        tb_page_add(page_find_alloc(pindex1, false), tb, 1);
    }
    tb_page_add(page_find_alloc(pindex0, false), tb, 0);
}

static void tb_page_remove(PageDesc *pd, TranslationBlock *tb)
{
    TranslationBlock *tb1;
    uintptr_t *pprev;
    PageForEachNext n1;

    assert_page_locked(pd);
    pprev = &pd->first_tb;
    PAGE_FOR_EACH_TB(unused, unused, pd, tb1, n1) {
        if (tb1 == tb) {
            *pprev = tb1->page_next[n1];
            return;
        }
        pprev = &tb1->page_next[n1];
    }
    g_assert_not_reached();
}

static void tb_remove(TranslationBlock *tb)
{
    tb_page_addr_t paddr0 = tb_page_addr0(tb);
    tb_page_addr_t paddr1 = tb_page_addr1(tb);
    tb_page_addr_t pindex0 = paddr0 >> TARGET_PAGE_BITS;
    tb_page_addr_t pindex1 = paddr1 >> TARGET_PAGE_BITS;

    assert(paddr0 != -1);
    if (unlikely(paddr1 != -1) && pindex0 != pindex1) {
        tb_page_remove(page_find_alloc(pindex1, false), tb);
    }
    tb_page_remove(page_find_alloc(pindex0, false), tb);
}
#endif /* CONFIG_USER_ONLY */

/*
 * Flush all the translation blocks.
 * Must be called from a context in which no cpus are running,
 * e.g. start_exclusive() or vm_stop().
 */
void tb_flush__exclusive_or_serial(void)
{
    CPUState *cpu;

    trace_tb_flush();
    assert(tcg_enabled());
    /* Note that cpu_in_serial_context checks cpu_in_exclusive_context. */
    assert(!runstate_is_running() ||
           (current_cpu && cpu_in_serial_context(current_cpu)));

    CPU_FOREACH(cpu) {
        tcg_flush_jmp_cache(cpu);
    }

    qht_reset_size(&tb_ctx.htable, CODE_GEN_HTABLE_SIZE);
    qht_reset_size(&tb_ctx.inv_htable, CODE_GEN_HTABLE_SIZE);
    tb_remove_all();

    tcg_region_reset_all();
    /* XXX: flush processor icache at this point if cache flush is expensive */
    qatomic_inc(&tb_ctx.tb_flush_count);

#ifdef __ANDROID__
    __android_log_print(ANDROID_LOG_WARN, "hakuX-tb",
                        "TB FLUSH #%u -- all translations destroyed",
                        qatomic_read(&tb_ctx.tb_flush_count));
#endif

#ifdef XBOX
    /* Clear stale tier-1 promotion requests — the TBs they reference
     * no longer exist after flush. */
    extern void tier1_clear_all_requests(void);
    tier1_clear_all_requests();
#endif

    /*
     * Prepare rewarm after flush.  On desktop, this translates blocks
     * inline.  On Android, this only sorts hints and marks incremental
     * rewarm pending — actual translation happens in cpu_exec_loop()
     * a few blocks per iteration to avoid blocking the CPU thread.
     */
    if (current_cpu) {
        tb_cache_rewarm_after_flush(current_cpu);
    }

    qemu_plugin_flush_cb();
}

static void do_tb_flush(CPUState *cpu, run_on_cpu_data tb_flush_count)
{
    /* If it is already been done on request of another CPU, just retry. */
    if (tb_ctx.tb_flush_count == tb_flush_count.host_int) {
        tb_flush__exclusive_or_serial();
    }
}

void queue_tb_flush(CPUState *cs)
{
    if (tcg_enabled()) {
        unsigned tb_flush_count = qatomic_read(&tb_ctx.tb_flush_count);
        async_safe_run_on_cpu(cs, do_tb_flush,
                              RUN_ON_CPU_HOST_INT(tb_flush_count));
    }
}

/* remove @orig from its @n_orig-th jump list */
static inline void tb_remove_from_jmp_list(TranslationBlock *orig, int n_orig)
{
    uintptr_t ptr, ptr_locked;
    TranslationBlock *dest;
    TranslationBlock *tb;
    uintptr_t *pprev;
    int n;

    /* mark the LSB of jmp_dest[] so that no further jumps can be inserted */
    ptr = qatomic_or_fetch(&orig->jmp_dest[n_orig], 1);
    dest = (TranslationBlock *)(ptr & ~1);
    if (dest == NULL) {
        return;
    }

    qemu_spin_lock(&dest->jmp_lock);
    /*
     * While acquiring the lock, the jump might have been removed if the
     * destination TB was invalidated; check again.
     */
    ptr_locked = qatomic_read(&orig->jmp_dest[n_orig]);
    if (ptr_locked != ptr) {
        qemu_spin_unlock(&dest->jmp_lock);
        /*
         * The only possibility is that the jump was unlinked via
         * tb_jump_unlink(dest). Seeing here another destination would be a bug,
         * because we set the LSB above.
         */
        g_assert(ptr_locked == 1 && dest->cflags & CF_INVALID);
        return;
    }
    /*
     * We first acquired the lock, and since the destination pointer matches,
     * we know for sure that @orig is in the jmp list.
     */
    if (dest == orig) {
        /*
         * In the case of a TB that links to itself, removing the entry
         * from the list means that it won't be present later during
         * tb_jmp_unlink -- unlink now.
         */
        tb_reset_jump(orig, n_orig);
    }
    pprev = &dest->jmp_list_head;
    TB_FOR_EACH_JMP(dest, tb, n) {
        if (tb == orig && n == n_orig) {
            *pprev = tb->jmp_list_next[n];
            /* no need to set orig->jmp_dest[n]; setting the LSB was enough */
            qemu_spin_unlock(&dest->jmp_lock);
            return;
        }
        pprev = &tb->jmp_list_next[n];
    }
    g_assert_not_reached();
}

/*
 * Reset the jump entry 'n' of a TB so that it is not chained to another TB.
 */
void tb_reset_jump(TranslationBlock *tb, int n)
{
    uintptr_t addr = (uintptr_t)(tb->tc.ptr + tb->jmp_reset_offset[n]);
    tb_set_jmp_target(tb, n, addr);
}

/* remove any jumps to the TB */
static inline void tb_jmp_unlink(TranslationBlock *dest)
{
    TranslationBlock *tb;
    int n;

    qemu_spin_lock(&dest->jmp_lock);

    TB_FOR_EACH_JMP(dest, tb, n) {
        tb_reset_jump(tb, n);
        qatomic_and(&tb->jmp_dest[n], (uintptr_t)NULL | 1);
        /* No need to clear the list entry; setting the dest ptr is enough */
    }
    dest->jmp_list_head = (uintptr_t)NULL;

    qemu_spin_unlock(&dest->jmp_lock);
}

static void tb_jmp_cache_inval_tb(TranslationBlock *tb)
{
    CPUState *cpu;

    if (tb_cflags(tb) & CF_PCREL) {
        /* A TB may be at any virtual address */
        CPU_FOREACH(cpu) {
            tcg_flush_jmp_cache(cpu);
        }
    } else {
        uint32_t h = tb_jmp_cache_hash_func(tb->pc);

        CPU_FOREACH(cpu) {
            CPUJumpCache *jc = cpu->tb_jmp_cache;

            if (qatomic_read(&jc->array[h].tb) == tb) {
                qatomic_set(&jc->array[h].tb, NULL);
            }
        }
    }
}

/*
 * In user-mode, call with mmap_lock held.
 * In !user-mode, if @rm_from_page_list is set, call with the TB's pages'
 * locks held.
 */
static void do_tb_phys_invalidate(TranslationBlock *tb, bool rm_from_page_list)
{
    uint32_t h;
    tb_page_addr_t phys_pc;
    uint32_t orig_cflags = tb_cflags(tb);
    void *existing = NULL;

    assert_memory_lock();

#ifdef XBOX
    /* Cleared on entry, set past the early return. See its declaration. */
    hakux_tb_discarded_here = false;
#endif

    /* make sure no further incoming jumps will be chained to this TB */
    qemu_spin_lock(&tb->jmp_lock);
    qatomic_set(&tb->cflags, tb->cflags | CF_INVALID);
    qemu_spin_unlock(&tb->jmp_lock);

    /* remove the TB from the hash list */
    phys_pc = tb_page_addr0(tb);
    /*
     * CF_INVALID is masked off because it can never have been an input to the
     * hash this TB was INSERTED under, and qht_remove must be given the
     * insertion hash or it looks in the wrong bucket. tb_link_page() is the
     * only insertion site: it asserts !(tb->cflags & CF_INVALID) and then
     * hashes tb->cflags verbatim. qht_remove__locked() states the same
     * requirement from the other side --
     * `qht_debug_assert(b->hashes[i] == hash)`.
     *
     * Upstream gets this for free: orig_cflags is read three lines above,
     * BEFORE the bit is set, so it carries CF_INVALID only for a TB some
     * earlier call already removed -- and there missing is the correct
     * outcome, which the mask preserves, because the TB is no longer in
     * tb_ctx.htable at all and qht_remove (pointer identity) still returns
     * false.
     *
     * This fork breaks that premise. Tier-1 promotion sets CF_INVALID *in
     * place* -- see tb_request_tier1_promotion() in cpu-exec.c: no
     * qht_remove, no tb_remove, deliberately, so the block keeps running
     * until the CPU exits it. Such a TB is in tb_ctx.htable under a hash
     * without the bit while carrying the bit. Without the mask the qht_remove
     * below missed, the early return fired BEFORE tb_remove(), and the TB was
     * stranded for the life of the translation buffer: still in the htable,
     * still on the page list, revisited by every later store to that page.
     * tb_lookup_cmp() masks CF_INVALID off before comparing, so a stranded TB
     * is still found and executed -- with its PRE-WRITE translation once the
     * guest has rewritten those bytes, since the store that should have
     * discarded it is exactly the one that took the early return. Issue #73.
     */
    h = tb_hash_func(phys_pc, (orig_cflags & CF_PCREL ? 0 : tb->pc),
                     tb->flags, tb->cs_base, orig_cflags & ~CF_INVALID);
    if (!qht_remove(&tb_ctx.htable, tb, h)) {
        return;
    }

    qht_insert(&tb_ctx.inv_htable, tb, h, &existing);
    g_assert(existing == NULL);

#ifdef XBOX
    /* Past the early return above, so this block really is being discarded. */
    hakux_tb_discarded++;
    hakux_tb_discarded_here = true;
#endif

    /* remove the TB from the page list */
    if (rm_from_page_list) {
        tb_remove(tb);
    }

    /* remove the TB from the hash list */
    tb_jmp_cache_inval_tb(tb);

    /* suppress this TB from the two jump lists */
    tb_remove_from_jmp_list(tb, 0);
    tb_remove_from_jmp_list(tb, 1);

    /* suppress any remaining jumps to this TB */
    tb_jmp_unlink(tb);

    qatomic_set(&tb_ctx.tb_phys_invalidate_count,
                tb_ctx.tb_phys_invalidate_count + 1);

#ifdef XBOX
    /*
     * Free superblock metadata if this was a merged superblock.
     *
     * DEAD while XBOX_SUPERBLOCK_ENABLED == 0 (cpu-exec.c): tb->superblock is
     * set only by tb_gen_superblock(), whose only caller returns before
     * reaching it, and every other site sets the field NULL. Audit pass 1 L1
     * records the reachability here so the next reader does not re-derive it.
     * RE-AUDIT THIS LIFETIME on the day that flag is flipped, not now: it
     * frees metadata belonging to a TB the fork's tier-1 design deliberately
     * keeps executing after invalidation. The log line below is
     * ANDROID_LOG_INFO under tag "superblock", which no dispatcher logcat
     * spec lists, so it would record nothing even if it did fire.
     */
    if (tb->superblock) {
#ifdef __ANDROID__
        __android_log_print(ANDROID_LOG_INFO, "superblock",
                            "invalidated at 0x%" PRIx64 " (B was 0x%" PRIx64 ")",
                            (uint64_t)tb->pc,
                            (uint64_t)tb->superblock->pc_b);
#endif
        g_free(tb->superblock);
        tb->superblock = NULL;
    }
#endif
}

static void tb_phys_invalidate__locked(TranslationBlock *tb)
{
    qemu_thread_jit_write();
    do_tb_phys_invalidate(tb, true);
    qemu_thread_jit_execute();
}

/*
 * Invalidate one TB.
 * Called with mmap_lock held in user-mode.
 */
void tb_phys_invalidate(TranslationBlock *tb, tb_page_addr_t page_addr)
{
    if (page_addr == -1 && tb_page_addr0(tb) != -1) {
        tb_lock_pages(tb);
        do_tb_phys_invalidate(tb, true);
        tb_unlock_pages(tb);
    } else {
        do_tb_phys_invalidate(tb, false);
    }
}

/*
 * Add a new TB and link it to the physical page tables.
 * Called with mmap_lock held for user-mode emulation.
 *
 * Returns a pointer @tb, or a pointer to an existing TB that matches @tb.
 * Note that in !user-mode, another thread might have already added a TB
 * for the same block of guest code that @tb corresponds to. In that case,
 * the caller should discard the original @tb, and use instead the returned TB.
 */
TranslationBlock *tb_link_page(TranslationBlock *tb)
{
    void *existing_tb = NULL;
    uint32_t h;

    assert_memory_lock();
    tcg_debug_assert(!(tb->cflags & CF_INVALID));

    tb_record(tb);

    /* add in the hash table */
    h = tb_hash_func(tb_page_addr0(tb), (tb->cflags & CF_PCREL ? 0 : tb->pc),
                     tb->flags, tb->cs_base, tb->cflags);
    qht_insert(&tb_ctx.htable, tb, h, &existing_tb);

    /* remove TB from the page(s) if we couldn't insert it */
    if (unlikely(existing_tb)) {
        tb_remove(tb);
        tb_unlock_pages(tb);
        return existing_tb;
    }

    tb_unlock_pages(tb);
    return tb;
}

#ifdef CONFIG_USER_ONLY
/*
 * Invalidate all TBs which intersect with the target address range.
 * Called with mmap_lock held for user-mode emulation.
 * NOTE: this function must not be called while a TB is running.
 */
void tb_invalidate_phys_range(CPUState *cpu, tb_page_addr_t start,
                              tb_page_addr_t last)
{
    TranslationBlock *tb;
    PageForEachNext n;

    assert_memory_lock();

    PAGE_FOR_EACH_TB(start, last, unused, tb, n) {
        tb_phys_invalidate__locked(tb);
    }
}

/*
 * Invalidate all TBs which intersect with the target address page @addr.
 * Called with mmap_lock held for user-mode emulation
 * NOTE: this function must not be called while a TB is running.
 */
static void tb_invalidate_phys_page(tb_page_addr_t addr)
{
    tb_page_addr_t start, last;

    start = addr & TARGET_PAGE_MASK;
    last = addr | ~TARGET_PAGE_MASK;
    tb_invalidate_phys_range(NULL, start, last);
}

/*
 * Called with mmap_lock held. If pc is not 0 then it indicates the
 * host PC of the faulting store instruction that caused this invalidate.
 * Returns true if the caller needs to abort execution of the current TB.
 */
bool tb_invalidate_phys_page_unwind(CPUState *cpu, tb_page_addr_t addr,
                                    uintptr_t pc)
{
    TranslationBlock *current_tb;
    bool current_tb_modified;
    TranslationBlock *tb;
    PageForEachNext n;
    tb_page_addr_t last;

    /*
     * Without precise smc semantics, or when outside of a TB,
     * we can skip to invalidate.
     */
    if (!pc || !cpu || !cpu->cc->tcg_ops->precise_smc) {
        tb_invalidate_phys_page(addr);
        return false;
    }

    assert_memory_lock();
    current_tb = tcg_tb_lookup(pc);

    last = addr | ~TARGET_PAGE_MASK;
    addr &= TARGET_PAGE_MASK;
    current_tb_modified = false;

    PAGE_FOR_EACH_TB(addr, last, unused, tb, n) {
        if (current_tb == tb &&
            (tb_cflags(current_tb) & CF_COUNT_MASK) != 1) {
            /*
             * If we are modifying the current TB, we must stop its
             * execution. We could be more precise by checking that
             * the modification is after the current PC, but it would
             * require a specialized function to partially restore
             * the CPU state.
             */
            current_tb_modified = true;
            cpu_restore_state_from_tb(cpu, current_tb, pc);
        }
        tb_phys_invalidate__locked(tb);
    }

    if (current_tb_modified) {
        /* Force execution of one insn next time.  */
        cpu->cflags_next_tb = 1 | CF_NOIRQ | curr_cflags(cpu);
        return true;
    }
    return false;
}
#else
#ifdef XBOX
/*
 * Would upstream's range test have spared this TB?
 *
 * This fork does not ask. xemu commit 703566ce33 ("tcg: Invalidate all TBs on
 * target page", 2021-10-04) wrapped the range test in `#ifndef XBOX` with no
 * recorded reason, so a guest store to a page holding translated code discards
 * *every* block on that page rather than the blocks whose bytes were written.
 * PAGE_FOR_EACH_TB in the softmmu build ignores its @start/@last arguments
 * (see the macro at the top of the !CONFIG_USER_ONLY section), so that test
 * was the only thing making the invalidation range-precise.
 *
 * That matters to the performance stream because
 * docs/investigations/performance-next-three.md section 2 scopes "smaller
 * translation blocks on thrashing pages" on the stated premise that "the
 * invalidation is already range-precise". It is not, here -- and the whole
 * mechanism by which smaller blocks would help depends on it: a smaller block
 * is only worth less work when a store can miss it. Under whole-page
 * invalidation every block on the page dies whatever its size.
 *
 * So before changing either thing, count what the range test would have done.
 * This computes it and throws the answer away; the invalidation below is
 * unchanged. The arithmetic is upstream's, kept identical on purpose so the
 * count means "what restoring the test would spare" and not "what some other
 * predicate would spare".
 */
static bool tb_overlaps_written_range(const TranslationBlock *tb, int n,
                                      tb_page_addr_t start,
                                      tb_page_addr_t last)
{
    tb_page_addr_t tb_start, tb_last;

    /* NOTE: this is subtle as a TB may span two physical pages */
    tb_start = tb_page_addr0(tb);
    tb_last = tb_start + tb->size - 1;
    if (n == 0) {
        tb_last = MIN(tb_last, tb_start | ~TARGET_PAGE_MASK);
    } else {
        tb_start = tb_page_addr1(tb);
        tb_last = tb_start + (tb_last & ~TARGET_PAGE_MASK);
    }
    return !(tb_last < start || tb_start > last);
}

/*
 * Where whole-page invalidation actually costs something, which is not the
 * discarded code itself.
 *
 * tb_page_add() arms code-write detection only on the empty -> non-empty
 * transition of a page, and tb_invalidate_phys_page_range__locked() disarms it
 * when the page empties. Arming is tlb_protect_code(), which is
 * physical_memory_test_and_clear_dirty() -> tlb_reset_dirty_range_all() ->
 * tlb_reset_dirty(), a walk of every TLB entry on every CPU -- and
 * tlb_reset_dirty is 10.6% self of the thread that bounds the frame, the
 * largest single symbol on it, reached from code generation at 99.7%
 * attribution. See docs/investigations/frame-pacing-and-parallelism.md.
 *
 * A store that empties a page therefore buys a full TLB walk on the next
 * generation there. A store that leaves one block behind buys none. That is
 * the quantity these counters exist to size, and it is the one the range test
 * changes: `emptied` is what happens now, `would_survive` is what would
 * happen with the test restored.
 */
#endif
/*
 * @p must be non-NULL.
 * Call with all @pages locked.
 * (@cpu, @retaddr) may be (NULL, 0) outside of a cpu context,
 * in which case precise_smc need not be detected.
 */
static void
tb_invalidate_phys_page_range__locked(CPUState *cpu,
                                      struct page_collection *pages,
                                      PageDesc *p, tb_page_addr_t start,
                                      tb_page_addr_t last,
                                      uintptr_t retaddr)
{
    TranslationBlock *tb;
    PageForEachNext n;
    bool current_tb_modified = false;
    TranslationBlock *current_tb = NULL;
#ifdef XBOX
    unsigned tbs_seen = 0, tbs_live = 0, tbs_overlap = 0;
#endif

    /* Range may not cross a page. */
    tcg_debug_assert(((start ^ last) & TARGET_PAGE_MASK) == 0);

    if (retaddr && cpu && cpu->cc->tcg_ops->precise_smc) {
        current_tb = tcg_tb_lookup(retaddr);
    }

    /*
     * We remove all the TBs in the range [start, last].
     * XXX: see if in some cases it could be faster to invalidate all the code
     */
    PAGE_FOR_EACH_TB(start, last, p, tb, n) {
#ifndef XBOX
        tb_page_addr_t tb_start, tb_last;

        /* NOTE: this is subtle as a TB may span two physical pages */
        tb_start = tb_page_addr0(tb);
        tb_last = tb_start + tb->size - 1;
        if (n == 0) {
            tb_last = MIN(tb_last, tb_start | ~TARGET_PAGE_MASK);
        } else {
            tb_start = tb_page_addr1(tb);
            tb_last = tb_start + (tb_last & ~TARGET_PAGE_MASK);
        }
        if (!(tb_last < start || tb_start > last)) {
#else
        {
            /*
             * Counted, not acted on: the invalidation below is unchanged.
             *
             * The overlap question is asked only of blocks that are still
             * live. A TB that already carries CF_INVALID is one
             * do_tb_phys_invalidate refused to unlink (its qht_remove fails,
             * and the early return fires before tb_remove), so it sits on the
             * page list and every later store walks over it again. Such a
             * block has no reason to overlap the current write, so counting it
             * would report "a range test would have spared this" for a block
             * that is already dead -- which is how the first run produced
             * sp_share = 1.000 in every window. That figure was measured over
             * the wrong population, and the premise check is worthless unless
             * this split is made here.
             */
            tbs_seen++;
            if (tb_cflags(tb) & CF_INVALID) {
                hakux_inval_already++;
            } else {
                tbs_live++;
                tbs_overlap += tb_overlaps_written_range(tb, n, start, last);
            }
#endif
            if (unlikely(current_tb == tb) &&
                (tb_cflags(current_tb) & CF_COUNT_MASK) != 1) {
                /*
                 * If we are modifying the current TB, we must stop
                 * its execution. We could be more precise by checking
                 * that the modification is after the current PC, but it
                 * would require a specialized function to partially
                 * restore the CPU state.
                 */
                current_tb_modified = true;
                cpu_restore_state_from_tb(cpu, current_tb, retaddr);
            }
#ifdef XBOX
            /*
             * VISITS here, DISCARDS in do_tb_phys_invalidate, and the
             * identity between them checked per visit. See the three comment
             * blocks at the top of this file; the short version is that the
             * early return on qht_remove sits before tb_remove, so counting
             * here counts re-visits of blocks this loop already refused to
             * unlink.
             */
            hakux_tb_visited++;
            tb_phys_invalidate__locked(tb);
            if (!hakux_tb_discarded_here) {
                /* Cannot happen; see hakux_inval_impossible. */
                hakux_inval_impossible++;
            }
#else
            tb_phys_invalidate__locked(tb);
#endif
        }
    }

#ifdef XBOX
    if (tbs_seen) {
        hakux_inval_events++;
        hakux_inval_tbs_overlap += tbs_overlap;
        hakux_inval_tbs_spared += tbs_live - tbs_overlap;
        /*
         * p->first_tb is read after the loop, so `emptied` is what this build
         * actually did. `would_survive` is the counterfactual: with the range
         * test restored, at least one block had no written byte in it, so the
         * page would still hold code and would not be disarmed -- and the next
         * generation there would skip the arming TLB walk. The two are the
         * before and after of restoring the test, measured on the same run.
         */
        if (!p->first_tb) {
            hakux_inval_emptied++;
            /*
             * AUDIT M1. This compared tbs_overlap against tbs_SEEN, and
             * tbs_overlap is accumulated for LIVE blocks only, deliberately,
             * for the reason given in the loop above. Every already-invalid
             * block therefore added 1 to the left-hand side's denominator and
             * 0 to its numerator, and `ws` fired on pages where the range
             * test would have spared nothing.
             *
             * It was correct BY ACCIDENT before #73's fix (2af6def68a) and
             * stopped being correct with it. Pre-fix, an already-invalid TB
             * took do_tb_phys_invalidate()'s early return before tb_remove(),
             * so it stayed on the page list, so `!p->first_tb` could not hold
             * for any event that had visited one: `em` implied
             * tbs_seen == tbs_live and the two tests were the same test. The
             * fix really unlinks those blocks, which removes exactly that
             * implication. The bias is one-directional -- ws OVER-reports --
             * and ws is the counter #68 is argued from, so any ws figure from
             * a run between 2af6def68a and this commit is measured over the
             * wrong population and must not be compared with one from either
             * side of it.
             *
             * tbs_live is the right denominator rather than a dead-inclusive
             * overlap count, and that is a statement about what restoring the
             * range test actually does, not a simplification: 937848c9e7
             * discards an already-invalid block whatever the write touched
             * (its `!tb_live` clause), so a dead block does NOT keep the page
             * alive under the restored test and must not be counted as a
             * survivor here. A survivor is a block that is live AND whose
             * bytes the write missed, which is tbs_live - tbs_overlap -- the
             * quantity already accumulated into `sp` on the line above.
             *
             * Not modelled, because it cannot happen in this build: 937848c9e7
             * also discards tier >= 2 / superblock TBs unconditionally, so
             * those would not be survivors either. XBOX_SUPERBLOCK_ENABLED is
             * 0 and tb_gen_superblock() is the only producer, so adding the
             * term here would be a guard nothing can reach. Add it with that
             * flag, not before.
             */
            if (tbs_overlap < tbs_live) {
                hakux_inval_would_survive++;
            }
#if HAKUX_SMALL_BLOCK_INSNS
            /*
             * Count and latch here rather than on the guest store: this is the
             * event that costs, because an emptied page is disarmed and the
             * next generation on it pays the arming TLB walk. Monotonic, so
             * the mark is one-way by construction as well as by the flag.
             */
            if (!p->small_blocks && ++p->empties >= HAKUX_THRASH_LATCH) {
                p->small_blocks = true;
            }
#endif
        }
    }
#endif

    /* if no code remaining, no need to continue to use slow writes */
    if (!p->first_tb) {
        tlb_unprotect_code(start);
    }

    if (unlikely(current_tb_modified)) {
        page_collection_unlock(pages);
        /* Force execution of one insn next time.  */
        cpu->cflags_next_tb = 1 | CF_NOIRQ | curr_cflags(cpu);
        cpu_loop_exit_noexc(cpu);
    }
}

#if HAKUX_SMALL_BLOCK_INSNS
bool tb_page_wants_small_blocks(tb_page_addr_t phys_pc)
{
    /*
     * page_find() is file-local and takes no lock; the flag is a single byte
     * that only ever goes false -> true and is never cleared, so a torn or
     * stale read can only mean "generate this one block at the old extent",
     * which is what would have happened anyway. It is not part of the TB hash
     * key, so disagreeing readers cannot make a lookup miss -- that is the
     * whole reason the extent lives in max_insns and not in cflags.
     */
    PageDesc *pd = page_find(phys_pc >> TARGET_PAGE_BITS);

    return pd && qatomic_read(&pd->small_blocks);
}
#endif

/*
 * Invalidate all TBs which intersect with the target physical address range
 * [start;last]. NOTE: start and end may refer to *different* physical pages.
 * 'is_cpu_write_access' should be true if called from a real cpu write
 * access: the virtual CPU will exit the current TB if code is modified inside
 * this TB.
 */
void tb_invalidate_phys_range(CPUState *cpu, tb_page_addr_t start,
                              tb_page_addr_t last)
{
    struct page_collection *pages;
    tb_page_addr_t index, index_last;

    pages = page_collection_lock(start, last);

    index_last = last >> TARGET_PAGE_BITS;
    for (index = start >> TARGET_PAGE_BITS; index <= index_last; index++) {
        PageDesc *pd = page_find(index);
        tb_page_addr_t page_start, page_last;

        if (pd == NULL) {
            continue;
        }
        assert_page_locked(pd);
        page_start = index << TARGET_PAGE_BITS;
        page_last = page_start | ~TARGET_PAGE_MASK;
        page_last = MIN(page_last, last);
        tb_invalidate_phys_page_range__locked(cpu, pages, pd,
                                              page_start, page_last, 0);
    }
    page_collection_unlock(pages);
}

/*
 * len must be <= 8 and start must be a multiple of len.
 * Called via softmmu_template.h when code areas are written to with
 * iothread mutex not held.
 */
void tb_invalidate_phys_range_fast(CPUState *cpu, ram_addr_t start,
                                   unsigned len, uintptr_t ra)
{
    PageDesc *p = page_find(start >> TARGET_PAGE_BITS);

    if (p) {
        ram_addr_t last = start + len - 1;
        struct page_collection *pages = page_collection_lock(start, last);

        tb_invalidate_phys_page_range__locked(cpu, pages, p,
                                              start, last, ra);
        page_collection_unlock(pages);
    }
}

#endif /* CONFIG_USER_ONLY */
