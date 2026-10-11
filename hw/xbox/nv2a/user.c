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

/* USER - PFIFO MMIO and DMA submission area
 *
 * The read takes no lock (#433). Each register it returns is one word with
 * one writer on the other side: DMA_PUT and REF are written only by the guest
 * (user_write), DMA_GET only by the guest and the pusher, which stores it with
 * release after the methods it covers have run (pfifo_run_pusher). The read
 * acquires, so a guest that sees GET past a word also sees everything the
 * pusher did before advancing it -- the ordering the lock gave.
 *
 * What the lock cost: the PFIFO thread holds pfifo.lock across
 * pgraph_process_pending_reports(), whose STALLED finish waits for the render
 * thread to submit the open command buffer (wait_frame_submitted). That runs
 * exactly when DMA_GET == DMA_PUT, so a guest polling GET waited out the GPU
 * batch to read a value that was already final. In Tron 2.0's slow window
 * that was 65% of the vCPU's sleep (docs/lanes/vcpuwait433/NOTES.md).
 *
 * The DMA_PUT store takes the lock, and so waits out whatever the PFIFO thread
 * is doing under it: at NFS Most Wanted's race start with the report wait gone
 * that was 7.3 ms per heavy frame (docs/lanes/reportasync1010/PR.md). With
 * HAKUX_POSTED_PUT=1 (off by default) a store that finds the lock busy is
 * posted instead, as the hardware's is; the posted-put block in pfifo.c says
 * how the PFIFO thread is still always woken. */
uint64_t user_read(void *opaque, hwaddr addr, unsigned int size)
{
    NV2AState *d = (NV2AState *)opaque;

    unsigned int channel_id = addr >> 16;
    assert(channel_id < NV2A_NUM_CHANNELS);

    uint32_t channel_modes = qatomic_read(&d->pfifo.regs[NV_PFIFO_MODE]);

    uint64_t r = 0;
    if (channel_modes & (1 << channel_id)) {
        /* DMA Mode */

        unsigned int cur_channel_id =
            GET_MASK(qatomic_read(&d->pfifo.regs[NV_PFIFO_CACHE1_PUSH1]),
                     NV_PFIFO_CACHE1_PUSH1_CHID);

        if (channel_id == cur_channel_id) {
            switch (addr & 0xFFFF) {
            case NV_USER_DMA_PUT:
                r = qatomic_load_acquire(&d->pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT]);
                break;
            case NV_USER_DMA_GET:
                r = qatomic_load_acquire(&d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET]);
                break;
            case NV_USER_REF:
                r = qatomic_load_acquire(&d->pfifo.regs[NV_PFIFO_CACHE1_REF]);
                break;
            default:
                break;
            }
        } else {
            /* ramfc */
            assert(false);
        }
    } else {
        /* PIO Mode */
        assert(false);
    }

    nv2a_reg_log_read(NV_USER, addr, size, r);
    return r;
}

void user_write(void *opaque, hwaddr addr, uint64_t val, unsigned int size)
{
    NV2AState *d = (NV2AState *)opaque;

    nv2a_reg_log_write(NV_USER, addr, size, val);

    unsigned int channel_id = addr >> 16;
    assert(channel_id < NV2A_NUM_CHANNELS);

    if ((addr & 0xFFFF) == NV_USER_DMA_PUT &&
        pfifo_dma_put_may_post(d, channel_id)) {
        /* HAKUX_POSTED_PUT=1: with the lock free, the locked store below,
         * unchanged; with it busy, the posted store. */
        if (qemu_mutex_trylock(&d->pfifo.lock) != 0) {
            pfifo_post_dma_put(d, val);
            g_nv2a_stats.cpu_working.kick_count++;
            return;
        }
    } else {
        int64_t lock_t0 = qemu_clock_get_ns(QEMU_CLOCK_REALTIME);
        qemu_mutex_lock(&d->pfifo.lock);
        g_nv2a_stats.cpu_working.lock_wait_ns +=
            qemu_clock_get_ns(QEMU_CLOCK_REALTIME) - lock_t0;
    }

    uint32_t channel_modes = d->pfifo.regs[NV_PFIFO_MODE];
    if (channel_modes & (1 << channel_id)) {
        /* DMA Mode */
        unsigned int cur_channel_id =
            GET_MASK(d->pfifo.regs[NV_PFIFO_CACHE1_PUSH1],
                     NV_PFIFO_CACHE1_PUSH1_CHID);

        if (channel_id == cur_channel_id) {
            switch (addr & 0xFFFF) {
            case NV_USER_DMA_PUT:
                qatomic_store_release(&d->pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT], val);
                g_nv2a_stats.cpu_working.kick_count++;
                break;
            case NV_USER_DMA_GET:
                qatomic_store_release(&d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET], val);
                break;
            case NV_USER_REF:
                qatomic_store_release(&d->pfifo.regs[NV_PFIFO_CACHE1_REF], val);
                break;
            default:
                assert(false);
                break;
            }

            pfifo_kick(d);

        } else {
            /* ramfc */
            assert(false);
        }
    } else {
        /* PIO Mode */
        assert(false);
    }

    qemu_mutex_unlock(&d->pfifo.lock);

}
