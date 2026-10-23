/*
 * hakuX heavycap1022 (#433): when a guest frame is slow or heavy, and when a
 * heavy stretch lasts long enough to save a state of it.
 *
 * Pure functions of their arguments and a small state struct: no clock, no
 * lock, no allocation. hw/xbox/nv2a/pgraph/profile.c calls them at the guest
 * flip (PFIFO thread); android/app/src/main/cpp/savestate/hxs.c takes the
 * slot constants; docs/testing/jobs/selftest.d/99-heavycap-rules.sh builds
 * them on the host and checks every bound below, then rebuilds them from
 * copies of this file with one rule put back to its weaker form and requires
 * the case for that rule to fail. Its mutants replace text here: an edit to a
 * rule's line fails that selftest until the mutant is updated with it.
 *
 * Copyright (c) 2026 hakuX contributors
 * SPDX-License-Identifier: GPL-2.0-or-later
 */

#ifndef HW_XBOX_NV2A_HEAVYRULE_H
#define HW_XBOX_NV2A_HEAVYRULE_H

#include <stdbool.h>
#include <stdint.h>

/* ---- the trigger: one frame ------------------------------------------- */

#define HC_FRAME_SLOW_NS 50000000LL     /* guest flip to flip over 50 ms */
#define HC_GPU_SLOW_NS 33000000LL       /* host main pass over 33 ms */
#define HC_DRAWS_DEFAULT 1000u          /* draws in the flip, over */
#define HC_PRE 30                       /* records before the firing one */
#define HC_POST 30                      /* ... and after it */

#define HC_TRIG_SLOW 1u
#define HC_TRIG_DRAWS 2u
#define HC_TRIG_GPU 4u

#define HC_OVER(v, bar) ((v) > (bar))   /* over, not at */

/* Which of the three bars this frame is over: 0 for none. */
static inline unsigned hc_trigger(int64_t frame_ns, uint32_t draws,
                                  int64_t gpu_ns, uint32_t draws_bar)
{
    unsigned t = 0;

    if (HC_OVER(frame_ns, HC_FRAME_SLOW_NS)) {
        t |= HC_TRIG_SLOW;
    }
    if (HC_OVER(draws, draws_bar)) {
        t |= HC_TRIG_DRAWS;
    }
    if (HC_OVER(gpu_ns, HC_GPU_SLOW_NS)) {
        t |= HC_TRIG_GPU;
    }
    return t;
}

/* ---- the block: rate limit -------------------------------------------- */

/*
 * One block is 1 + HC_PRE + 1 + HC_POST lines. A block is admitted when none
 * is still collecting its HC_POST records and the last one was admitted at
 * least HC_BLOCK_GAP_NS ago; a refused fire is counted and the count goes out
 * on the next admitted block's header (sup=) and on every summary line. So a
 * heavy stretch of any length prints at most one block per 10 s.
 */
#define HC_BLOCK_GAP_NS 10000000000LL

typedef struct HcBlockRule {
    bool have;              /* a block was admitted */
    int64_t last;           /* when */
    uint32_t suppressed;    /* fires refused since */
} HcBlockRule;

static inline bool hc_block_admit(HcBlockRule *r, int64_t now,
                                  bool in_progress, uint32_t *suppressed_before)
{
    if (in_progress) {
        r->suppressed++;
        return false;
    }
    if (r->have && now - r->last < HC_BLOCK_GAP_NS) {
        r->suppressed++;
        return false;
    }
    *suppressed_before = r->suppressed;
    r->suppressed = 0;
    r->last = now;
    r->have = true;
    return true;
}

/* ---- the save: a sustained stretch ------------------------------------ */

/*
 * Fires on 1 s of consecutive flips over the draws bar (the run starts at the
 * start of its first heavy frame, and any flip at or under the bar ends it),
 * or on HC_SLOW_N frames over 50 ms whose ends fall within 2 s. At most one
 * save per HC_SAVE_GAP_NS; a firing inside the gap is refused and counted.
 * Firing clears both conditions, so the next save needs a new stretch.
 */
#define HC_SUST_DRAWS_NS 1000000000LL
#define HC_SLOW_N 3
#define HC_SLOW_WIN_NS 2000000000LL
#define HC_SAVE_GAP_NS 60000000000LL

#define HC_SAVE_DRAWS 1u
#define HC_SAVE_SLOW 2u

typedef struct HcSaveRule {
    bool in_run;            /* flips over the draws bar, consecutive */
    int64_t run_t0;
    int64_t slow_t[HC_SLOW_N];  /* ends of the last slow frames, a ring */
    uint32_t slow_n;
    bool have_save;
    int64_t last_save;
    uint32_t refused;       /* firings inside the gap */
} HcSaveRule;

/* @now: the flip that ends this frame; @frame_ns: its length. Returns the
 * HC_SAVE_* reasons that fired (0: no save). */
static inline unsigned hc_save_check(HcSaveRule *r, int64_t now,
                                     int64_t frame_ns, uint32_t draws,
                                     uint32_t draws_bar)
{
    unsigned why = 0;

    if (HC_OVER(draws, draws_bar)) {
        if (!r->in_run) {
            r->in_run = true;
            r->run_t0 = now - (frame_ns > 0 ? frame_ns : 0);
        }
        if (now - r->run_t0 >= HC_SUST_DRAWS_NS) {
            why |= HC_SAVE_DRAWS;
        }
    } else {
        r->in_run = false;
    }
    if (HC_OVER(frame_ns, HC_FRAME_SLOW_NS)) {
        r->slow_t[r->slow_n % HC_SLOW_N] = now;
        r->slow_n++;
        if (r->slow_n >= HC_SLOW_N &&
            now - r->slow_t[r->slow_n % HC_SLOW_N] <= HC_SLOW_WIN_NS) {
            why |= HC_SAVE_SLOW;
        }
    }
    if (!why) {
        return 0;
    }
    if (r->have_save && now - r->last_save < HC_SAVE_GAP_NS) {
        r->refused++;
        return 0;
    }
    r->have_save = true;
    r->last_save = now;
    r->in_run = false;
    r->slow_n = 0;
    return why;
}

/* ---- where a heavy state goes ----------------------------------------- */

/*
 * HC_KEEP files, heavy0.hxs .. heavy3.hxs, as hxs.c slots HC_SLOT_BASE ..
 * HC_SLOT_BASE + HC_KEEP - 1: past HXS_SLOT_COUNT (slots 0-9, auto, undo),
 * so no owner state and no UI row is ever written, listed or auto-loaded.
 * hxs.c asserts the base at build time; the selftest checks it from hxs.h.
 */
#define HC_KEEP 4
#define HC_SLOT_BASE 12

/* The ring position for the next heavy state: the first empty one, else the
 * one saved longest ago. */
static inline int hc_pick_slot(const bool present[HC_KEEP],
                               const int64_t saved_at[HC_KEEP])
{
    int pick = 0;

    for (int k = 0; k < HC_KEEP; k++) {
        if (!present[k]) {
            return k;
        }
    }
    for (int k = 1; k < HC_KEEP; k++) {
        if (saved_at[k] < saved_at[pick]) {
            pick = k;
        }
    }
    return pick;
}

static inline int hc_slot_of(int k)
{
    return HC_SLOT_BASE + k;
}

#endif /* HW_XBOX_NV2A_HEAVYRULE_H */
