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
        /* Measured on real NV2A silicon (#188): two independent read-only
         * sweeps, with a reboot between them, both read 0x01110000 here --
         * 1,024 of 1,024 PMC dwords reproducible. We returned 0.
         *
         * The state it was read in is part of the measurement: the console
         * freshly out of the dashboard, drive quiescent, engines idle, and no
         * write issued in either sweep. Both sweeps were that same state, so
         * 1,024/1,024 bounds REPEATABILITY, not state-independence -- which
         * is the property a hardcoded constant actually needs.
         * nv2a-probe-pmc-findings.md says as much of its own numbers.
         *
         * A bare constant, deliberately -- but NOT because the header and the
         * measurement contradict each other, which an earlier version of this
         * comment claimed and two documents in this tree refute. The header
         * puts _PFIFO at bit 8 and _PGRAPH at bit 12, and the measured word
         * has both of those bits CLEAR. In the same sweep PGRAPH read 0/2048
         * non-zero, so "PGRAPH is not enabled" is what the header PREDICTS
         * for this word, not a refutation of it. (PFIFO read 382/2048
         * non-zero, which settles nothing either way: a disabled engine's
         * registers can still hold reset defaults.) And
         * nv2a-mapping-programme.md:168 already reads bit 16 as PTIMER,
         * cross-checked against PTIMER reading 992/1024 non-zero in that same
         * survey.
         *
         * What is unestablished, and what the envytools cross-reference #188
         * asks for should settle: what bits 20 and 24 gate, and what this
         * register reads on a machine that is actually rendering. Until then
         * no field decomposition here -- which does mean we answer "PFIFO and
         * PGRAPH are down" to any guest that asks, at all times, including
         * mid-frame. The 0 we used to return said exactly the same thing and
         * was further from silicon in the one state anyone has measured.
         *
         * Nor is the write side modelled, for a blunter reason: writing 0 to
         * this register halted the physical console outright -- no ICMP, ARP
         * FAILED, power cycle. Writes stay a silent no-op via pmc_write's
         * `default` until someone establishes what each bit gates.
         */
        r = 0x01110000;
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
    default:
        break;
    }
}

