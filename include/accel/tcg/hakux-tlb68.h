/*
 * #68, lane.tcgchurn: TLB-flush and dirty-reset accounting, and the two
 * fix switches. Definitions and the rationale are in accel/tcg/cputlb.c.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#ifndef ACCEL_TCG_HAKUX_TLB68_H
#define ACCEL_TCG_HAKUX_TLB68_H

#ifdef XBOX

/*
 * #311 fix candidates, one build define each. At most one may be on, so a
 * binary can only ever carry one of them and an arm names its hunk by sha.
 *
 *   HAKUX_TCG311_KEEP_ARMED  (hunk a) a page whose last block is discarded
 *       stays armed for code-write detection, so re-adding a block there does
 *       not pay tlb_reset_dirty's whole-TLB walk. See tb-maint.c.
 *   HAKUX_TCG311_TLB_BOUND   (hunk b) the dynamic TLB counts a same-page
 *       refill once, not twice, and never grows past 1 << HAKUX_TLB_MAX_BITS
 *       entries per MMU index, so the walk has a ceiling. See cputlb.c.
 */
#ifndef HAKUX_TCG311_KEEP_ARMED
#define HAKUX_TCG311_KEEP_ARMED 0
#endif
#ifndef HAKUX_TCG311_TLB_BOUND
#define HAKUX_TCG311_TLB_BOUND 0
#endif
#if HAKUX_TCG311_KEEP_ARMED && HAKUX_TCG311_TLB_BOUND
#error "#311: one fix hunk per binary; turn one of the two off"
#endif

/*
 * Hunk (a)'s fallback: writes an emptied, still-armed page may take through
 * the notdirty slow path before it is disarmed after all, as upstream would
 * have done at once. Bounds what a title that turns a code page into a hot
 * data buffer can pay.
 */
#define HAKUX_TCG311_ARMED_IDLE_WRITES 512

/* Hunk (b)'s ceiling: 2^13 entries per MMU index (upstream i386: 2^20). */
#define HAKUX_TLB_MAX_BITS 13

extern uint64_t hakux_tlb68_ka;     /* pages kept armed on emptying */
extern uint64_t hakux_tlb68_kafb;   /* ... disarmed later by the fallback */

/* Why a full TLB flush was asked for. Set by the caller, consumed once. */
enum {
    HAKUX_TLB68_OTHER,
    HAKUX_TLB68_CR3_NEW,    /* MOV CR3 with a different value */
    HAKUX_TLB68_CR3_SAME,   /* MOV CR3 reloading the value it already held */
    HAKUX_TLB68_CR0,
    HAKUX_TLB68_CR4,
    HAKUX_TLB68_A20,
    HAKUX_TLB68_NCAUSE
};

extern int hakux_tlb68_cause;
extern uint64_t hakux_tlb68_jci;
extern uint64_t hakux_tlb68_jcx;
extern uint64_t hakux_tlb68_jc;
extern uint64_t hakux_tlb68_jc_ns;

/* HAKUX_TCG68_JC: skip the whole-jump-cache wipe on a CF_PCREL discard. */
bool hakux_tlb68_jc_on(void);

/* The periodic [tlb68] line; vCPU thread only. */
void hakux_tlb68_tick(CPUState *cpu);

#define HAKUX_TLB68_SET_CAUSE(c) (hakux_tlb68_cause = (c))
#else
#define HAKUX_TLB68_SET_CAUSE(c) do { } while (0)
#endif

#endif
