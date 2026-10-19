/*
 * Geforce NV2A PGRAPH Vulkan Renderer: per-flip window counters (#1049)
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
 * The counters behind draw.c's [dipwin] line. Perflog builds only: draw.c
 * includes this under NV2A_PERF_LOG, so a release build carries none of it.
 *
 * Any thread adds; one reader takes. A writer adds with a relaxed atomic and
 * the reader takes each counter with an atomic exchange against zero, so every
 * add lands in exactly one window and none is lost or counted twice. The
 * g_opt_stats window this replaces for the dip numbers did neither: plain
 * increments from the PFIFO and render threads, and a memset from whichever
 * of the two reached the 60th finish.
 *
 * Standalone (no qemu headers) so the selftest can build it on its own.
 */

#ifndef HW_XBOX_NV2A_PGRAPH_VK_DIPWIN_H
#define HW_XBOX_NV2A_PGRAPH_VK_DIPWIN_H

#include <stdbool.h>
#include <stdint.h>

static inline void dipwin_add(uint64_t *c, uint64_t n)
{
    __atomic_fetch_add(c, n, __ATOMIC_RELAXED);
}

/* The window's value, and zero left behind in the same step */
static inline uint64_t dipwin_take(uint64_t *c)
{
    return __atomic_exchange_n(c, 0, __ATOMIC_RELAXED);
}

/*
 * Counts by caller address. A slot's address is claimed once by
 * compare-and-swap and never cleared, so a slot means the same caller in
 * every window; only its count is windowed. The last slot (address 0) takes
 * every caller that finds the others full.
 */
#define DIPWIN_PC_SLOTS 24

typedef struct DipwinPc {
    uintptr_t pc[DIPWIN_PC_SLOTS];
    uint64_t n[DIPWIN_PC_SLOTS];
} DipwinPc;

static inline void dipwin_pc_note(DipwinPc *t, uintptr_t pc)
{
    for (int i = 0; i < DIPWIN_PC_SLOTS - 1; i++) {
        uintptr_t cur = __atomic_load_n(&t->pc[i], __ATOMIC_RELAXED);
        if (cur == 0) {
            uintptr_t expect = 0;
            if (__atomic_compare_exchange_n(&t->pc[i], &expect, pc, false,
                                            __ATOMIC_RELAXED,
                                            __ATOMIC_RELAXED)) {
                cur = pc;
            } else {
                cur = expect;
            }
        }
        if (cur == pc) {
            dipwin_add(&t->n[i], 1);
            return;
        }
    }
    dipwin_add(&t->n[DIPWIN_PC_SLOTS - 1], 1);
}

/* Slot i's address (0 for the overflow slot) and its window count */
static inline uint64_t dipwin_pc_take(DipwinPc *t, int i, uintptr_t *pc)
{
    *pc = i < DIPWIN_PC_SLOTS - 1 ?
        __atomic_load_n(&t->pc[i], __ATOMIC_RELAXED) : 0;
    return dipwin_take(&t->n[i]);
}

#endif
