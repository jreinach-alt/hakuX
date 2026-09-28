/*
 * #507 (lane.ibcache): the inline indirect-branch probe.
 *
 * At every lookup_and_goto_ptr site the x86 front end (gen_eob, DISAS_JUMP:
 * RET, JMP/CALL r/m, a direct jump to another page) emits an inline probe
 * of the per-CPU jump cache before the call to helper_lookup_tb_ptr. A hit
 * branches straight to the TB; only a miss calls the helper. The probe is
 * tb_lookup()'s hit test, in generated code: the same slot, the same key
 * (pc, cs_base, flags, cflags), so the same invalidation (a wiped slot or a
 * CF_INVALID TB fails it).
 *
 * The jump cache's layout and hash live in accel/tcg (tb-jmp-cache.h,
 * tb-hash.h); this is how the front end learns them without including
 * those private headers. hakux_ibc_enabled() checks the hash it describes
 * against tb_jmp_cache_hash_func() before it says yes.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#ifndef ACCEL_TCG_HAKUX_IBC_H
#define ACCEL_TCG_HAKUX_IBC_H

typedef struct HakuxIbcLayout {
    int array_ofs;      /* offsetof(CPUJumpCache, array) */
    int entry_shift;    /* log2(sizeof(CPUJumpCache.array[0])) */
    int tb_ofs;         /* of .tb within an entry */
    int pc_ofs;         /* of .pc within an entry */
    int hash_shift;     /* TARGET_PAGE_BITS - TB_JMP_PAGE_BITS */
    int page_mask;      /* TB_JMP_PAGE_MASK */
    int addr_mask;      /* TB_JMP_ADDR_MASK */
    bool count;         /* HAKUX_IBC=2: count probe hits in hakux_ibc_hits */
} HakuxIbcLayout;

/*
 * HAKUX_IBC: unset or "1" on, "0" off, "2" on with a hit counter. Fills *l
 * and returns true when the probe may be emitted. Read once; logs one
 * "[ibc507]" line.
 */
bool hakux_ibc_enabled(HakuxIbcLayout *l);

/* Probe hits, counted only with HAKUX_IBC=2 (vCPU thread only). */
extern uint64_t hakux_ibc_hits;

#endif /* ACCEL_TCG_HAKUX_IBC_H */
