/*
 * QEMU Geforce NV2A implementation
 *
 * Copyright (c) 2012 espes
 * Copyright (c) 2015 Jannik Vogel
 * Copyright (c) 2018-2021 Matt Borgerson
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

#include "nv2a_int.h"
#ifdef __ANDROID__
#include "hw/core/cpu.h"
#include "target/i386/cpu.h"
#endif

/* PMC - card master control */
uint64_t pmc_read(void *opaque, hwaddr addr, unsigned int size)
{
    NV2AState *d = (NV2AState *)opaque;

    uint64_t r = 0;
    switch (addr) {
    case NV_PMC_BOOT_0:
        /* chipset and stepping:
         * NV2A, A03, Rev 0 */

        r = 0x02A000A3;
        break;
    case NV_PMC_INTR_0:
        /* Shows which functional units have pending IRQ */
        r = d->pmc.pending_interrupts;
#ifdef __ANDROID__
        {
            static int pmc_intr_log = 0;
            if (r && pmc_intr_log < 100) {
                extern int __android_log_print(int, const char*, const char*, ...);
                __android_log_print(3, "hakuX-nop",
                    "PMC_INTR_0 read: val=0x%x (pgraph=%d pfifo=%d pcrtc=%d)",
                    (uint32_t)r,
                    !!(r & NV_PMC_INTR_0_PGRAPH),
                    !!(r & NV_PMC_INTR_0_PFIFO),
                    !!(r & NV_PMC_INTR_0_PCRTC));
                pmc_intr_log++;
            }
        }
#endif
        break;
    case NV_PMC_INTR_EN_0:
        /* Selects which functional units can cause IRQs */
        r = d->pmc.enabled_interrupts;
        break;
    case NV_PMC_ENABLE:
        /* Stored state (#188). pmc_reset() gives the idle value silicon reads,
         * pmc_write() stores what the guest writes over the implemented bits,
         * and nothing else reads or acts on it. The measurement, and every
         * choice this model makes, is recorded at pmc_write(). */
        r = d->pmc.enable;
        break;
    case 0x160:
    case 0x204 ... 0x2FC:
        /* Measured on real NV2A silicon (#190), by the same read-only survey
         * that produced NV_PMC_ENABLE above: 0x160, and every dword from
         * 0x204 to 0x2FC inclusive (63 of them, contiguous), read
         * 0x00000001. Two independent sweeps with a reboot between them,
         * 1,024/1,024 PMC dwords reproducible, no write issued in either.
         * We returned 0. The same survey reports 957 of PMC's 1,024 dwords
         * reading 0, so 67 are non-zero: these 64, plus BOOT_0 and
         * NV_PMC_ENABLE, plus exactly one more the findings do not name.
         * (0x004/BOOT_1 is the obvious candidate and #189's, but no read
         * value for it is recorded anywhere in this tree, so that is
         * arithmetic and not a measurement.)
         *
         * No name for either of these, deliberately: nv2a_regs.h declares
         * nothing at 0x160 or anywhere in 0x204-0x2FC, and a macro invented
         * here would assert a meaning the measurement does not carry. The
         * raw offsets are what was read.
         *
         * WHAT THIS IS NOT. Whether 0x204-0x2FC is 63 live registers that
         * happen to hold 1, or one register aliased across the range, or a
         * fixed unimplemented-read pattern, is UNTESTED and unmodelled here.
         * The three are indistinguishable from reads alone -- telling them
         * apart needs a write into the range, and the range begins four
         * bytes after the register whose write halted the physical console
         * (#188). So nothing is claimed about the write side and pmc_write
         * keeps dropping these offsets through its `default`, exactly as
         * before this change. If the aliasing reading is ever the right one,
         * this table is still right about what a read returns.
         *
         * Aligned dwords only, which is narrower than the case range looks.
         * The probe read dword-aligned offsets and nothing else, and a read
         * at 0x205 of a register holding 0x00000001 would return 0 under
         * every one of the three readings above. Unaligned offsets therefore
         * keep the 0 they return today rather than inheriting a value from a
         * neighbour nobody measured. An aligned sub-dword read does get 1,
         * which is the correct low byte/word of the measured value. */
        if ((addr & 3) == 0) {
            r = 0x00000001;
        }
        break;
    default:
        break;
    }

#ifdef __ANDROID__
    {
        static int pmc_poll_log = 0;
        CPUState *cpu = first_cpu;
        if (cpu && pmc_poll_log < 200) {
            CPUX86State *env = &X86_CPU(cpu)->env;
            uint32_t eip = (uint32_t)env->eip;
            if (eip >= 0x80015000 && eip <= 0x80016000) {
                extern int __android_log_print(int, const char*, const char*, ...);
                __android_log_print(3, "hakuX-mmio",
                    "PMC read: eip=0x%x reg=0x%x val=0x%x",
                    eip, (uint32_t)addr, (uint32_t)r);
                pmc_poll_log++;
            }
        }
    }
#endif
    nv2a_reg_log_read(NV_PMC, addr, size, r);
    return r;
}

void pmc_write(void *opaque, hwaddr addr, uint64_t val, unsigned int size)
{
    NV2AState *d = (NV2AState *)opaque;

    nv2a_reg_log_write(NV_PMC, addr, size, val);

    switch (addr) {
    case NV_PMC_INTR_0:
        /* the bits of the interrupts to clear are wrtten */
        d->pmc.pending_interrupts &= ~val;
        nv2a_update_irq(d);
        break;
    case NV_PMC_INTR_EN_0:
        d->pmc.enabled_interrupts = val;
        nv2a_update_irq(d);
        break;
    case NV_PMC_ENABLE:
        /* Storage over the ten implemented bits, and NOTHING ELSE (#188).
         *
         * What was measured on real NV2A silicon (#188, #203;
         * docs/testing/nv2a-probe-pmc-findings.md, "NV_PMC_ENABLE (0x200)"):
         *  - idle, no write issued: 0x01110000 (bits 16, 20, 24). Two sweeps,
         *    reboot between, 1,024/1,024 dwords reproducible. pmc_reset().
         *  - after pbkit's pb_init() writes 0xFFFFFFFF, which every graphics
         *    title does: 0x13111113. So bits 0, 1, 4, 8, 12, 16, 20, 24, 25
         *    and 28 are implemented and every other bit ignores a 1. That
         *    read is n = 1 with no artifact in this tree (the findings' own
         *    "Provenance" section says so), and it is the whole basis of the
         *    mask below.
         * pb_kill() writes back the value pb_init() saved, and the only other
         * writes in pbkit clear and re-set bit 12. Storage makes all three
         * round-trip, which a constant read never did: it told a guest
         * "0x01110000" mid-frame, right after that guest wrote all-ones.
         *
         * GATE NOTHING. Which engine any bit gates is UNMEASURED. envytools
         * names 12 PGRAPH and 28 PVIDEO for NV4:G80, but an all-ones write
         * sets every implemented bit whatever it controls, so the read-back
         * separates no hypothesis, and 0, 1, 20 and 25 are named by nothing.
         * So a write here resets no engine, halts nothing on 0 (silicon did
         * halt when 0 was written -- NV_PMC_ENABLE_ALL_DISABLE -- and that is
         * deliberately not modelled either), and no other block consults
         * d->pmc.enable. Wiring bit 12 to PGRAPH or bit 28 to PVIDEO here
         * would model an assignment no measurement supports; the experiment
         * that would is a selective one-bit write from a known baseline, on
         * the register that has halted the console once. PVIDEO is #110's.
         *
         * THE ONE CHOICE THE DATA DOES NOT SETTLE: bits 16, 20 and 24 read 1
         * before any write, so "settable" and "hardwired to 1" predict the
         * same value for every read anyone has taken. After a write that
         * CLEARS one of them, this model reads back 0 -- storage, the same as
         * the seven bits observed to go 0 -> 1. Chosen because it is the
         * smaller claim (one mask, no second hardwired set) and because every
         * write pbkit issues reads back identically under both. Falsifier: on
         * silicon, write 0x13101113 (bit 20 alone cleared; unnamed, and not
         * the PTIMER/PCRTC candidates 16 and 24) and read it back. 0x13111113
         * means bit 20 is hardwired: OR it into the read here, repeat for 16
         * and 24, and change the selftest line that asserts storage.
         *
         * Width: like INTR_EN_0 above, a write replaces the whole word
         * whatever `size` is. Nothing measured says what a sub-dword write
         * does to this register, and no guest code seen issues one. */
        d->pmc.enable = val & 0x13111113;
        break;
    default:
        break;
    }
}

/* The idle value, measured with no write issued (#188): bits 16, 20, 24.
 * What a guest reads before it writes anything; see pmc_write(). */
void pmc_reset(NV2AState *d)
{
    d->pmc.enable = 0x01110000;
}

