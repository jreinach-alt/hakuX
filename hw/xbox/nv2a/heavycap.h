/*
 * hakuX heavycap1022 (#433): the per-guest-frame record of what the emulated
 * CPU spent each frame on, and the hooks that feed it.
 *
 * On in perflog builds (NV2A_PERF_LOG=1); elsewhere when HAKUX_HEAVYCAP=1.
 * Off, every hook is one relaxed load and a not-taken branch. The record, the
 * trigger, the hakuX-heavy blocks and the 2 s summary live in
 * hw/xbox/nv2a/pgraph/profile.c; the rules in hw/xbox/nv2a/heavyrule.h.
 *
 * Every counter here is a never-reset total, read at the guest flip and
 * differenced against the previous flip's read. Each has one writer thread
 * (or is written under the BQL), so a relaxed load-add-store is enough; the
 * reader is the PFIFO thread at the flip.
 *
 * Copyright (c) 2026 hakuX contributors
 * SPDX-License-Identifier: GPL-2.0-or-later
 */

#ifndef HW_XBOX_NV2A_HEAVYCAP_H
#define HW_XBOX_NV2A_HEAVYCAP_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

extern int hakux_hc_on;                 /* profile.c */

static inline bool hakux_heavycap_on(void)
{
    return __builtin_expect(__atomic_load_n(&hakux_hc_on, __ATOMIC_RELAXED)
                            != 0, 0);
}

/* A total with one writer (a thread, or the BQL) read from another thread. */
#define HC_ADD(p, v) __atomic_store_n((p), __atomic_load_n((p), \
                                      __ATOMIC_RELAXED) + (v), __ATOMIC_RELAXED)

/* Main thread, from qemu_init_cpu_loop(), before any vCPU or PFIFO thread. */
void hakux_heavycap_init(void);

/* Draws (BEGIN_END begins) since the last flip: PFIFO thread, pgraph.c. */
extern uint32_t hakux_hc_draws;

/* Guest idle (the kernel's sti;nop;nop;cli loop, cpu-exec.c rrw_sti/rrw_wake),
 * booked by the interrupt class that ended each stretch; total includes the
 * stretch still open. */
enum {
    HAKUX_HC_I_VBL,         /* NV2A with PCRTC (VBLANK) pending */
    HAKUX_HC_I_NV2A,        /* NV2A, other units */
    HAKUX_HC_I_PIT,         /* vector 0x30 */
    HAKUX_HC_I_IDE,         /* vector 0x3e, IRQ14 */
    HAKUX_HC_I_OTHER,
    HAKUX_HC_NI,
};
typedef struct HakuxHcIdle {
    uint64_t total_ns;
    uint64_t cls_ns[HAKUX_HC_NI];
    uint64_t cls_n[HAKUX_HC_NI];
} HakuxHcIdle;
bool hakux_rrw_idle_totals(HakuxHcIdle *o);          /* cpu-exec.c */

/* Translation and flushes (accel/tcg/cputlb.c, the [tcg787] counters). */
typedef struct HakuxHcTcg {
    uint64_t gen_n, gen_ns;     /* tb_gen_code */
    uint64_t cg_ns;             /* ... of which codegen */
    uint64_t flush_ns;          /* TLB flushes (full + page) */
    uint64_t tf_ns;             /* tlb_fill_align, TLB miss fills: timed
                                 * only while the perflog switch is on */
    uint64_t tb_flushes;        /* tb_ctx.tb_flush_count (whole-cache) */
} HakuxHcTcg;
void hakux_tcg_totals(HakuxHcTcg *o);

/* IDE/ATAPI (hw/ide/core.c, atapi.c), all written under the BQL. */
typedef struct HakuxHcIde {
    uint64_t vcpu_ns;       /* submit + drain + sync read, on the vCPU */
    uint64_t other_ns;      /* the same on any other thread */
    uint64_t sync_ns;       /* atapi cd_read_sector_sync, any thread */
    uint64_t dev_ns;        /* command to IRQ, the guest-visible latency */
    uint64_t bytes;
    uint64_t cmds, irqs;
} HakuxHcIde;
void hakux_ide_totals(HakuxHcIde *o);
void hakux_hc_ide_sync(int64_t t0, uint64_t bytes);   /* atapi.c */

/* VBLANK raise and PCRTC acknowledge, both under the BQL (nv2a.c, pcrtc.c).
 * @was_pending: VBLANK was still pending when raised again (a miss);
 * @deferred: the timer raised it late. Times are QEMU_CLOCK_REALTIME ns. */
void hakux_hc_vblank_raise(bool was_pending, bool deferred, int64_t now);
void hakux_hc_vblank_ack(int64_t now);

/* The automatic save (HAKUX_HEAVYSAVE=1). hxs.c registers @post, which must
 * only wake a thread and return; that thread calls hakux_heavycap_saved()
 * when the save is done. Names are relative to the states dir. */
void hakux_heavycap_set_saver(bool (*post)(void));
void hakux_heavycap_saved(const char *name, int ok, int64_t pause_ms,
                          int64_t total_ms);

#ifdef __cplusplus
}
#endif

#endif /* HW_XBOX_NV2A_HEAVYCAP_H */
