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

