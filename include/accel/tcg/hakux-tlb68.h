/*
 * #68, lane.tcgchurn: TLB-flush and dirty-reset accounting, and the two
 * fix switches. Definitions and the rationale are in accel/tcg/cputlb.c.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#ifndef ACCEL_TCG_HAKUX_TLB68_H
#define ACCEL_TCG_HAKUX_TLB68_H

#ifdef XBOX

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
