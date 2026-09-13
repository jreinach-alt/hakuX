/*
 * QEMU Geforce NV2A implementation
 *
 * Copyright (c) 2012 espes
 * Copyright (c) 2015 Jannik Vogel
 * Copyright (c) 2018-2025 Matt Borgerson
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
#include <android/log.h>
#include "hw/core/cpu.h"
#include "target/i386/cpu.h"
#endif

#ifndef XEMU_OPT_THREAD_AFFINITY
#define XEMU_OPT_THREAD_AFFINITY 0
#endif

#ifndef XEMU_OPT_PFIFO_LOCK_BATCH
#define XEMU_OPT_PFIFO_LOCK_BATCH 1
#endif

#ifndef XEMU_OPT_LOCKLESS_FAST_DISPATCH
#define XEMU_OPT_LOCKLESS_FAST_DISPATCH XEMU_OPT_PFIFO_LOCK_BATCH
#endif

#ifndef XEMU_OPT_FIFO_SPIN
#define XEMU_OPT_FIFO_SPIN 1
#endif


#if XEMU_OPT_FIFO_SPIN
#define FIFO_SPIN_ACTIVE_NS 100000 /* 100µs active spin window */
#endif

/*
 * The skew bound: hold the guest at its own submission point until PGRAPH has
 * consumed what it published.
 *
 * On. It was added off, in its own commit, so the instrument above could
 * measure the unbounded baseline first and so the A/B that prices it differs
 * by exactly one constant -- this one. `HAKUX_FIFO_SKEW_BOUND=0` turns it off
 * at runtime for a local bisect.
 */
#ifndef XEMU_OPT_FIFO_SKEW_BOUND
#define XEMU_OPT_FIFO_SKEW_BOUND 1
#endif

/* Poll DMA_GET without sleeping for this long first. The pusher spins for
 * FIFO_SPIN_ACTIVE_NS before parking, so whenever it is already awake -- the
 * common case under load -- a submission is consumed without either thread
 * touching a futex. */
#define FIFO_SKEW_SPIN_NS  60000

/* Backstop on the sleeping path. The wait is for a signal sent under
 * pfifo.lock, so a lost wakeup should be impossible; a timeout is here so
 * that being wrong about that costs a frame rather than the machine. */
#define FIFO_SKEW_WAIT_MS  250

static int fifo_skew_bound_enabled(void)
{
    static int v = -1;

    if (v < 0) {
        const char *e = getenv("HAKUX_FIFO_SKEW_BOUND");
        v = (e && e[0]) ? (e[0] != '0') : XEMU_OPT_FIFO_SKEW_BOUND;
    }
    return v;
}

/*
 * GUEST<->PGRAPH SKEW, and what bounds it.
 *
 * The guest CPU writes texture and vertex data into guest memory with plain
 * stores, then publishes a pushbuffer segment by writing DMA_PUT, and
 * `user_write` returns immediately. The PFIFO thread consumes that segment
 * later and, when it reaches the draw, reads the memory the guest wrote --
 * synchronously on this thread, in `get_texture_layout` for a texture and in
 * `pgraph_vk_update_vertex_ram_buffer` for vertex data. So between the
 * publish and the consume there is a window in which the guest is free to
 * overwrite the very bytes that draw is going to read.
 *
 * #44 is that window, measured texel-exact: the upload for draw N reads guest
 * memory after the guest has begun writing iteration N+1's surface to the
 * same address, and the draw renders with its SUCCESSOR's texture. A forward
 * model explains 12,596 of 12,596 wrong pixels across a ten-run noise floor,
 * with the tear always a row-major prefix of the successor's surface, cut at
 * a different offset every run. Real silicon races the same way and wins on
 * speed; we lose about 46% of the time.
 *
 * NOTHING IN THIS FILE BOUNDS THAT WINDOW TODAY. `user_write` stores DMA_PUT
 * and calls pfifo_kick(); the guest's next instruction runs. The only
 * backpressure that exists is the guest's own: a pushbuffer ring that fills,
 * at which point nxdk spins on DMA_GET until the pusher makes room. That is a
 * bound in RING BYTES, not in draws, and the ring is large enough that a
 * whole iteration of #44's eighteen-draw loop fits in it many times over. The
 * `ring=` field below is that capacity, read out of the guest's own DMA
 * object rather than assumed, so the claim is a number.
 *
 * The two quantities this measures are the ones the race is a function of:
 *
 *   - `backlog`, the bytes between DMA_GET and DMA_PUT at the instant the
 *     guest publishes. Zero means PGRAPH was already current and the guest is
 *     not ahead at all.
 *   - `drain`, the time from that publish until DMA_GET reaches it. That IS
 *     the skew, in nanoseconds, and it is the width of the window in which a
 *     guest store can beat PGRAPH's read of the same address.
 *
 * Cost is two clock reads and a handful of increments per submission. A
 * measurement per pushbuffer WORD was the obvious alternative and is exactly
 * the mistake AGENTS.md records: a syscall added to this inner loop, at
 * 144,712 calls in a few seconds, throttled the emulator until it presented
 * as a renderer deadlock. Per submission is three orders of magnitude
 * cheaper, and `kicks=` says how many that is rather than leaving it assumed.
 */
#ifdef __ANDROID__

#define FSK_BUCKET_NS   50000    /* 50 us, matching the VBLANK histogram */
#define FSK_BUCKETS     1024     /* 0 .. 51.2 ms, then one overflow bin */
#define FSK_WINDOW_NS   2000000000LL

static struct {
    int64_t  window_start_ns;

    uint32_t kicks;          /* submissions: DMA_PUT advanced */
    uint32_t kicks_behind;   /* ... with PGRAPH not yet current */
    uint32_t wrap;           /* backlog not linearly measurable (a JMP) */

    uint64_t backlog_sum;    /* bytes of un-consumed pushbuffer at publish */
    uint32_t backlog_max;
    uint32_t ring_len;       /* the guest's DMA object limit: today's bound */

    uint32_t drain_n;        /* submissions whose consumption was timed */
    uint64_t drain_sum_ns;
    int64_t  drain_max_ns;
    uint32_t drain_bucket[FSK_BUCKETS + 1];

    /* Only non-zero once the bound below is enabled: how long the guest was
     * actually held, and by which of the two mechanisms. `gave` is the
     * escape: the pusher parked without catching up, which happens when it is
     * stalled on something only the guest or the VBLANK can clear, and is
     * the one path on which the bound does not hold. */
    uint32_t held_n;
    uint64_t held_sum_ns;
    int64_t  held_max_ns;
    uint32_t held_spun;
    uint32_t held_slept;
    uint32_t gave;

    /*
     * Publish timestamps still waiting to be consumed. Timed per submission
     * rather than "oldest outstanding to caught up", because the race is
     * per draw: what matters is how long THIS segment sat unread, not how
     * long the backlog took to clear.
     *
     * Retired in a batch when the pusher reports DMA_GET == DMA_PUT, which is
     * the only moment every outstanding segment is provably consumed. Testing
     * each `put` against DMA_GET individually would be wrong: the pushbuffer
     * is a ring walked with JMP, so DMA_GET passing an address does not order
     * against it.
     */
#define FSK_PEND 256
    int64_t  pend_ts[FSK_PEND];
    uint32_t pend_head;
    uint32_t pend_tail;
    uint32_t pend_lost;      /* submissions dropped from the ring, untimed */
} s_fsk;

static void fsk_note_ring(hwaddr dma_len)
{
    s_fsk.ring_len = (uint32_t)dma_len;
}

static void fsk_dump_and_reset(int64_t now)
{
    int64_t span = now - s_fsk.window_start_ns;
    int64_t backlog_mean = s_fsk.kicks
        ? (int64_t)(s_fsk.backlog_sum / s_fsk.kicks) : 0;
    int64_t drain_mean = s_fsk.drain_n
        ? (int64_t)(s_fsk.drain_sum_ns / s_fsk.drain_n) : 0;
    int64_t held_mean = s_fsk.held_n
        ? (int64_t)(s_fsk.held_sum_ns / s_fsk.held_n) : 0;

    int64_t p50 = 0, p90 = 0, p99 = 0;
    if (s_fsk.drain_n) {
        const uint32_t pcts[3] = { 50, 90, 99 };
        int64_t *out[3] = { &p50, &p90, &p99 };
        for (int k = 0; k < 3; k++) {
            uint32_t want = (s_fsk.drain_n * pcts[k] + 99) / 100;
            uint32_t acc = 0;
            if (!want) {
                want = 1;
            }
            *out[k] = (int64_t)(FSK_BUCKETS + 1) * FSK_BUCKET_NS;
            for (int i = 0; i <= FSK_BUCKETS; i++) {
                acc += s_fsk.drain_bucket[i];
                if (acc >= want) {
                    *out[k] = (int64_t)(i + 1) * FSK_BUCKET_NS;
                    break;
                }
            }
        }
    }

    __android_log_print(
        ANDROID_LOG_INFO, "hakuX-perf",
        "fifoskew win=%lldms kicks=%u behind=%u wrap=%u ring=%u "
        "backlog(mean=%lld max=%u) "
        "drain(n=%u mean=%lld p50=%lld p90=%lld p99=%lld max=%lld) "
        "bound=%d held(n=%u mean=%lld max=%lld spun=%u slept=%u gave=%u) "
        "lost=%u",
        (long long)(span / 1000000), s_fsk.kicks, s_fsk.kicks_behind,
        s_fsk.wrap, s_fsk.ring_len,
        (long long)backlog_mean, s_fsk.backlog_max,
        s_fsk.drain_n, (long long)drain_mean, (long long)p50,
        (long long)p90, (long long)p99, (long long)s_fsk.drain_max_ns,
        fifo_skew_bound_enabled(),
        s_fsk.held_n, (long long)held_mean, (long long)s_fsk.held_max_ns,
        s_fsk.held_spun, s_fsk.held_slept, s_fsk.gave, s_fsk.pend_lost);

    memset(s_fsk.drain_bucket, 0, sizeof(s_fsk.drain_bucket));
    s_fsk.kicks = 0;
    s_fsk.kicks_behind = 0;
    s_fsk.wrap = 0;
    s_fsk.backlog_sum = 0;
    s_fsk.backlog_max = 0;
    s_fsk.drain_n = 0;
    s_fsk.drain_sum_ns = 0;
    s_fsk.drain_max_ns = 0;
    s_fsk.held_n = 0;
    s_fsk.held_sum_ns = 0;
    s_fsk.held_max_ns = 0;
    s_fsk.held_spun = 0;
    s_fsk.held_slept = 0;
    s_fsk.gave = 0;
    s_fsk.pend_lost = 0;
    s_fsk.window_start_ns = now;
}

static void fsk_note_submit(NV2AState *d, uint32_t put, int64_t now)
{
    uint32_t get = d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET];

    s_fsk.kicks++;
    if (put != get) {
        s_fsk.kicks_behind++;
    }
    /* The pushbuffer is a ring walked with JMP, so DMA_GET is not monotonic
     * and `put - get` is only the backlog when the segment is linear. The
     * non-linear case is counted rather than folded in, because a wrapped
     * difference would read as a 4 GB backlog and swamp the mean. */
    if (put >= get) {
        uint32_t backlog = put - get;
        s_fsk.backlog_sum += backlog;
        if (backlog > s_fsk.backlog_max) {
            s_fsk.backlog_max = backlog;
        }
    } else {
        s_fsk.wrap++;
    }

    if (s_fsk.pend_head - s_fsk.pend_tail < FSK_PEND) {
        s_fsk.pend_ts[s_fsk.pend_head % FSK_PEND] = now;
        s_fsk.pend_head++;
    } else {
        s_fsk.pend_lost++;
    }

    if (!s_fsk.window_start_ns) {
        s_fsk.window_start_ns = now;
    }
}

/* Called with pfifo.lock held, at the one moment every outstanding
 * submission is provably consumed: the pusher has walked DMA_GET all the way
 * to DMA_PUT. Retires the whole pending ring, each entry timed from its own
 * publish. */
static void fsk_note_caught_up(int64_t now)
{
    while (s_fsk.pend_tail != s_fsk.pend_head) {
        int64_t skew_ns = now - s_fsk.pend_ts[s_fsk.pend_tail % FSK_PEND];
        int idx;

        s_fsk.pend_tail++;
        if (skew_ns < 0) {
            skew_ns = 0;
        }
        idx = (int)(skew_ns / FSK_BUCKET_NS);
        if (idx > FSK_BUCKETS) {
            idx = FSK_BUCKETS;
        }
        s_fsk.drain_bucket[idx]++;
        s_fsk.drain_n++;
        s_fsk.drain_sum_ns += (uint64_t)skew_ns;
        if (skew_ns > s_fsk.drain_max_ns) {
            s_fsk.drain_max_ns = skew_ns;
        }
    }
}

static void fsk_note_held(int64_t held_ns, bool spun, bool gave)
{
    s_fsk.held_n++;
    s_fsk.held_sum_ns += (uint64_t)(held_ns > 0 ? held_ns : 0);
    if (held_ns > s_fsk.held_max_ns) {
        s_fsk.held_max_ns = held_ns;
    }
    if (spun) {
        s_fsk.held_spun++;
    } else {
        s_fsk.held_slept++;
    }
    if (gave) {
        s_fsk.gave++;
    }
}

static void fsk_maybe_dump(int64_t now)
{
    if (s_fsk.window_start_ns &&
        now - s_fsk.window_start_ns >= FSK_WINDOW_NS) {
        fsk_dump_and_reset(now);
    }
}

#else
/*
 * Off Android the whole histogram is compiled out: `hakuX-perf` is a logcat
 * tag and core-QEMU fprintf(stderr) does not reach it, so there is nothing
 * for the desktop build to emit into. The arguments are deliberately left
 * UNEVALUATED where they cost something -- `now` and `ns` are clock reads --
 * and cast to void where they do not, so the desktop build neither pays for
 * the instrument nor warns about a variable only the instrument reads.
 */
#define fsk_note_ring(len)                    ((void)0)
#define fsk_note_submit(d, put, now)          ((void)0)
#define fsk_note_caught_up(now)               ((void)0)
#define fsk_note_held(ns, spun, gave)         ((void)(spun), (void)(gave))
#define fsk_maybe_dump(now)                   ((void)0)
#endif

#if defined(__ANDROID__) && XEMU_OPT_THREAD_AFFINITY
#include <sys/syscall.h>
#include <sys/resource.h>

static void xemu_pin_to_big_cores(const char *label)
{
    int ncpus = sysconf(_SC_NPROCESSORS_CONF);
    if (ncpus <= 0 || ncpus > 64) return;

    unsigned long max_freq = 0;
    unsigned long freqs[64];
    for (int i = 0; i < ncpus; i++) {
        char path[128];
        snprintf(path, sizeof(path),
                 "/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq", i);
        FILE *f = fopen(path, "r");
        if (f) {
            if (fscanf(f, "%lu", &freqs[i]) != 1) freqs[i] = 0;
            fclose(f);
        } else {
            freqs[i] = 0;
        }
        if (freqs[i] > max_freq) max_freq = freqs[i];
    }

    if (max_freq == 0) return;

    unsigned long threshold = max_freq * 9 / 10;
    /* Build affinity mask manually (avoid cpu_set_t header issues on bionic) */
    unsigned long mask = 0;
    int big_count = 0;
    for (int i = 0; i < ncpus && i < (int)(sizeof(mask) * 8); i++) {
        if (freqs[i] >= threshold) {
            mask |= (1UL << i);
            big_count++;
        }
    }

    if (big_count > 0 && big_count < ncpus) {
        if (syscall(__NR_sched_setaffinity, 0, sizeof(mask), &mask) == 0) {
            fprintf(stderr, "[xemu] %s: pinned to %d big cores (max_freq=%lu)\n",
                    label, big_count, max_freq);
        }
    }

    setpriority(PRIO_PROCESS, 0, -10);
}
#endif

typedef struct RAMHTEntry {
    uint32_t handle;
    hwaddr instance;
    enum FIFOEngine engine;
    unsigned int channel_id : 5;
    bool valid;
} RAMHTEntry;

static void pfifo_run_pusher(NV2AState *d);
static uint32_t ramht_hash(NV2AState *d, uint32_t handle);
static RAMHTEntry ramht_lookup(NV2AState *d, uint32_t handle);

/* PFIFO - MMIO and DMA FIFO submission to PGRAPH and VPE */
uint64_t pfifo_read(void *opaque, hwaddr addr, unsigned int size)
{
    NV2AState *d = (NV2AState *)opaque;

    qemu_mutex_lock(&d->pfifo.lock);

    uint64_t r = 0;
    switch (addr) {
    case NV_PFIFO_INTR_0:
        r = d->pfifo.pending_interrupts;
        break;
    case NV_PFIFO_INTR_EN_0:
        r = d->pfifo.enabled_interrupts;
        break;
    case NV_PFIFO_RUNOUT_STATUS:
        r = NV_PFIFO_RUNOUT_STATUS_LOW_MARK; /* low mark empty */
        break;
    default:
        r = d->pfifo.regs[addr];
        break;
    }

    qemu_mutex_unlock(&d->pfifo.lock);

#ifdef __ANDROID__
    {
        static int pfifo_poll_log = 0;
        CPUState *cpu = first_cpu;
        if (cpu && pfifo_poll_log < 200) {
            CPUX86State *env = &X86_CPU(cpu)->env;
            uint32_t eip = (uint32_t)env->eip;
            if (eip >= 0x80015000 && eip <= 0x80016000) {
                extern int __android_log_print(int, const char*, const char*, ...);
                __android_log_print(3, "hakuX-mmio",
                    "PFIFO read: eip=0x%x reg=0x%x val=0x%x",
                    eip, (uint32_t)addr, (uint32_t)r);
                pfifo_poll_log++;
            }
        }
    }
#endif

    nv2a_reg_log_read(NV_PFIFO, addr, size, r);
    return r;
}

void pfifo_write(void *opaque, hwaddr addr, uint64_t val, unsigned int size)
{
    NV2AState *d = (NV2AState *)opaque;

    nv2a_reg_log_write(NV_PFIFO, addr, size, val);

    qemu_mutex_lock(&d->pfifo.lock);

    switch (addr) {
    case NV_PFIFO_INTR_0:
        d->pfifo.pending_interrupts &= ~val;
        nv2a_update_irq(d);
        break;
    case NV_PFIFO_INTR_EN_0:
        d->pfifo.enabled_interrupts = val;
        nv2a_update_irq(d);
        break;
    default:
        d->pfifo.regs[addr] = val;
        break;
    }

    pfifo_kick(d);

    qemu_mutex_unlock(&d->pfifo.lock);
}

/*
 * Hold the guest at its own submission point until PGRAPH has caught up.
 *
 * WHY THIS IS THE ONLY BOUND THAT MAKES #44 IMPOSSIBLE RATHER THAN RARER.
 * The guest writes the texture, publishes the draw, then writes the NEXT
 * iteration's texture to the same address. Its only observable act between
 * those two writes is the DMA_PUT store, so that store is the only place the
 * emulator can interpose. And the interposition has to be a full catch-up,
 * not a smaller skew allowance: at the moment the guest resumes, draw N is
 * already in the segment just published, so ANY amount of un-consumed
 * pushbuffer leaves draw N's texture read still to come while the guest is
 * free to overwrite its source. Zero is not a tuned value; it is the only
 * value with a proof.
 *
 * What the guarantee actually is, stated so the one hole in it is visible:
 * while the guest is executing, the FIFO holds no unprocessed method, so
 * PGRAPH performs no read of guest memory concurrently with guest execution.
 * That covers texture uploads (`get_texture_layout`) and vertex RAM
 * (`pgraph_vk_update_vertex_ram_buffer`) alike, because both happen on this
 * thread inside method processing. THE HOLE is the `gave` path below: if the
 * pusher parks without catching up -- stalled on a flip, on a NOP
 * acknowledgement or on a context switch, none of which can clear until the
 * guest runs again -- the guest is released with work outstanding, because
 * the alternative is a deadlock. #44's eighteen draws are inside one frame
 * with no FLIP_STALL between them, so the hole is not on its path; `gave=` is
 * reported per window so that stays a measurement rather than an assumption.
 *
 * Locks: pfifo.lock and the BQL are both held on entry and on exit. The BQL
 * has to be released around the sleep -- the pgraph method path takes it
 * (pgraph.c's IRQ raises), and the VBLANK a FLIP_STALL waits for is a main
 * loop timer -- and it is released in the order this device already uses
 * everywhere else: the device lock goes first, the BQL is the outer one. See
 * nv2a_set_surface_scale_factor and the NOP-error path in pgraph.c.
 */
static void pfifo_bound_skew(NV2AState *d, uint32_t put)
{
    int64_t t0 = nv2a_clock_ns();
    bool spun = false;
    bool caught;
    int64_t deadline = t0 + FIFO_SKEW_SPIN_NS;

    if (qatomic_read(&d->pfifo.halt)) {
        return;
    }

    /*
     * Phase 1, no sleeping. Drop only the FIFO lock -- the pusher needs it to
     * run at all -- and watch DMA_GET. Reading it unlocked is a benign race:
     * the pusher is the only writer and we are looking for one value.
     */
    qemu_mutex_unlock(&d->pfifo.lock);
    for (unsigned i = 0; ; i++) {
        if (qatomic_read(&d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET]) == put) {
            spun = true;
            break;
        }
        if ((i & 0x3F) == 0 && nv2a_clock_ns() >= deadline) {
            break;
        }
#ifdef __aarch64__
        __asm__ volatile("yield" ::: "memory");
#endif
    }
    qemu_mutex_lock(&d->pfifo.lock);

    caught = d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET] == put;

    /*
     * Phase 2, sleep until the pusher says it has caught up or has parked.
     * The re-check above is what makes a lost wakeup harmless: the signal is
     * sent under pfifo.lock, which we now hold, so either DMA_GET already
     * reads `put` and there is nothing to wait for, or the signal cannot have
     * been sent yet.
     */
    if (!caught && !qatomic_read(&d->pfifo.halt)) {
        /*
         * The BQL must go before sleeping, and this is the deadlock it
         * avoids rather than a tidiness measure. The PFIFO thread takes the
         * BQL to raise a PGRAPH interrupt, and a FLIP_STALL in the segment we
         * are waiting on can only clear when a VBLANK fires from a main-loop
         * timer. Sleeping with the BQL held would stop both, and the wait
         * would then never be satisfiable by anything but its own timeout.
         *
         * Releasing it does not invert the order: bql_unlock() cannot block.
         * REACQUIRING it does, so pfifo.lock is dropped first and the two are
         * taken outer-to-inner -- the order nv2a_lock_fifo() uses, and the
         * order pgraph.c's IRQ paths use.
         */
        bql_unlock();
        qemu_cond_timedwait(&d->pfifo.fifo_drained_cond, &d->pfifo.lock,
                            FIFO_SKEW_WAIT_MS);
        qemu_mutex_unlock(&d->pfifo.lock);
        bql_lock();
        qemu_mutex_lock(&d->pfifo.lock);
        caught = d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET] == put;
    }

    fsk_note_held(nv2a_clock_ns() - t0, spun, !caught);
}

void pfifo_kick(NV2AState *d)
{
    if (!d->pfifo.fifo_kick) {
        d->pfifo.fifo_kick = true;
        qemu_cond_broadcast(&d->pfifo.fifo_cond);
    }

    /*
     * Which of this function's many callers is a SUBMISSION.
     *
     * pfifo_kick() is called from the guest's DMA_PUT store, from other guest
     * MMIO writes, from the VBLANK callback on the main loop, and from PGRAPH
     * on the PFIFO thread itself. Only the first publishes new pushbuffer,
     * and only the first may be held. Telling them apart on DMA_PUT having
     * ADVANCED is what keeps this inside one file: the caller does not have
     * to be changed to say so, and the test is exact because the guest CPU is
     * the only writer of that register.
     *
     * It also keeps the dangerous callers out by construction. `pgraph_write`
     * reaches here holding pgraph.lock as well as pfifo.lock, and holding
     * pgraph.lock while waiting for the PFIFO thread -- which needs it to
     * process a method -- is a deadlock. DMA_PUT cannot have advanced on that
     * path, so it never enters the wait.
     */
    uint32_t put = d->pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT];

    if (put == d->pfifo.skew_last_put) {
        return;
    }
    d->pfifo.skew_last_put = put;

    fsk_note_submit(d, put, nv2a_clock_ns());

    if (fifo_skew_bound_enabled() && bql_locked()) {
        pfifo_bound_skew(d, put);
    }
}

static bool can_fifo_access(NV2AState *d) {
    return qatomic_read(&d->pgraph.regs_[NV_PGRAPH_FIFO]) &
           NV_PGRAPH_FIFO_ACCESS;
}

/* If NV097_FLIP_STALL was executed, check if the flip has completed.
 * This will usually happen in the VSYNC interrupt handler.
 */
static bool is_flip_stall_complete(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;

    uint32_t s = pgraph_reg_r(pg, NV_PGRAPH_SURFACE);

    NV2A_DPRINTF("flip stall read: %d, write: %d, modulo: %d\n",
        GET_MASK(s, NV_PGRAPH_SURFACE_READ_3D),
        GET_MASK(s, NV_PGRAPH_SURFACE_WRITE_3D),
        GET_MASK(s, NV_PGRAPH_SURFACE_MODULO_3D));

    if (GET_MASK(s, NV_PGRAPH_SURFACE_READ_3D)
        != GET_MASK(s, NV_PGRAPH_SURFACE_WRITE_3D)) {
        return true;
    }

    return false;
}

static bool pfifo_stall_for_flip(NV2AState *d)
{
    bool should_stall = false;

    if (qatomic_read(&d->pgraph.waiting_for_flip)) {
        NV2A_PHASE_TIMER_BEGIN(flip_idle);
        qemu_mutex_lock(&d->pgraph.lock);
        if (!is_flip_stall_complete(d)) {
            should_stall = true;
        } else {
            d->pgraph.waiting_for_flip = false;
        }
        qemu_mutex_unlock(&d->pgraph.lock);
        NV2A_PHASE_TIMER_END(flip_idle);
    }

    return should_stall;
}

static bool pfifo_puller_should_stall(NV2AState *d)
{
    return pfifo_stall_for_flip(d) || qatomic_read(&d->pgraph.waiting_for_nop) ||
           qatomic_read(&d->pgraph.waiting_for_context_switch) ||
           !can_fifo_access(d);
}

static ssize_t pfifo_run_puller(NV2AState *d, uint32_t method_entry,
                                uint32_t parameter, uint32_t *parameters,
                                size_t num_words_available,
                                size_t max_lookahead_words)
{
    if (pfifo_puller_should_stall(d)) {
        return -1;
    }

    int64_t _puller_t0 = NV2A_PERF_LOG ? nv2a_clock_ns() : 0;

    uint32_t *pull0 = &d->pfifo.regs[NV_PFIFO_CACHE1_PULL0];
    uint32_t *pull1 = &d->pfifo.regs[NV_PFIFO_CACHE1_PULL1];
    uint32_t *engine_reg = &d->pfifo.regs[NV_PFIFO_CACHE1_ENGINE];
    uint32_t *status = &d->pfifo.regs[NV_PFIFO_CACHE1_STATUS];
    ssize_t num_proc = -1;

    // TODO think more about locking

    if (!GET_MASK(*pull0, NV_PFIFO_CACHE1_PULL0_ACCESS) ||
        (*status & NV_PFIFO_CACHE1_STATUS_LOW_MARK)) {
        return -1;
    }

    uint32_t method = method_entry & 0x1FFC;
    uint32_t subchannel =
        GET_MASK(method_entry, NV_PFIFO_CACHE1_METHOD_SUBCHANNEL);
    bool inc = !GET_MASK(method_entry, NV_PFIFO_CACHE1_METHOD_TYPE);


    if (method == 0) {
        RAMHTEntry entry = ramht_lookup(d, parameter);
        assert(entry.valid);
        // assert(entry.channel_id == state->channel_id);
        assert(entry.engine == ENGINE_GRAPHICS);

        /* the engine is bound to the subchannel */
        assert(subchannel < 8);
        SET_MASK(*engine_reg, 3 << (4*subchannel), entry.engine);
        SET_MASK(*pull1, NV_PFIFO_CACHE1_PULL1_ENGINE, entry.engine);

#if XEMU_OPT_PFIFO_LOCK_BATCH
        qemu_mutex_lock(&d->pgraph.lock);
        qemu_mutex_unlock(&d->pfifo.lock);

        if (can_fifo_access(d)) {
            pgraph_context_switch(d, entry.channel_id);
            if (!d->pgraph.waiting_for_context_switch) {
                num_proc =
                    pgraph_method(d, subchannel, 0, entry.instance, parameters,
                                  num_words_available, max_lookahead_words, inc);
                g_nv2a_stats.cpu_working.method_count++;
            }
        }

        qemu_mutex_unlock(&d->pgraph.lock);
        qemu_mutex_lock(&d->pfifo.lock);
#else
        qemu_mutex_unlock(&d->pfifo.lock);
        qemu_mutex_lock(&d->pgraph.lock);

        if (can_fifo_access(d)) {
            pgraph_context_switch(d, entry.channel_id);
            if (!d->pgraph.waiting_for_context_switch) {
                num_proc =
                    pgraph_method(d, subchannel, 0, entry.instance, parameters,
                                  num_words_available, max_lookahead_words, inc);
                g_nv2a_stats.cpu_working.method_count++;
            }
        }

        qemu_mutex_unlock(&d->pgraph.lock);
        qemu_mutex_lock(&d->pfifo.lock);
#endif

    } else if (method >= 0x100) {
        // method passed to engine

        /* methods that take objects.
         * TODO: Check this range is correct for the nv2a */
        if (method >= 0x180 && method < 0x200) {
            //bql_lock();
            RAMHTEntry entry = ramht_lookup(d, parameter);
            assert(entry.valid);
            // assert(entry.channel_id == state->channel_id);
            parameter = entry.instance;
            //bql_unlock();
        }

        enum FIFOEngine engine = GET_MASK(*engine_reg, 3 << (4*subchannel));
        assert(engine == ENGINE_GRAPHICS);
        SET_MASK(*pull1, NV_PFIFO_CACHE1_PULL1_ENGINE, engine);

#if XEMU_OPT_PFIFO_LOCK_BATCH
#if XEMU_OPT_LOCKLESS_FAST_DISPATCH
        if (inc && can_fifo_access(d)) {
            int64_t _meth_t0 = NV2A_PERF_LOG ? nv2a_clock_ns() : 0;
            num_proc = pgraph_method_try_fast(
                d, subchannel, method, parameter,
                parameters, num_words_available, max_lookahead_words);
            if (num_proc > 0) {
                if (NV2A_PERF_LOG) {
                    g_nv2a_stats.cpu_working.method_fast_hit += num_proc;
                    g_nv2a_stats.cpu_working.method_count++;
                    g_nv2a_stats.cpu_working.method_exec_ns +=
                        nv2a_clock_ns() - _meth_t0;
                }
                goto puller_done;
            }
        }
#endif
        {
            int64_t _lock_t0 = NV2A_PERF_LOG ? nv2a_clock_ns() : 0;
            qemu_mutex_lock(&d->pgraph.lock);
            if (NV2A_PERF_LOG) {
                g_nv2a_stats.cpu_working.puller_lock_ns +=
                    nv2a_clock_ns() - _lock_t0;
            }
        }
        qemu_mutex_unlock(&d->pfifo.lock);

        if (can_fifo_access(d)) {
            int64_t _meth_t0 = NV2A_PERF_LOG ? nv2a_clock_ns() : 0;
            num_proc =
                pgraph_method(d, subchannel, method, parameter, parameters,
                              num_words_available, max_lookahead_words, inc);
            if (NV2A_PERF_LOG) {
                g_nv2a_stats.cpu_working.puller_method_ns +=
                    nv2a_clock_ns() - _meth_t0;
                g_nv2a_stats.cpu_working.method_count++;
            }
            if (!inc && num_proc > 0) {
                g_nv2a_stats.cpu_working.method_noninc_words += num_proc;
            }
        }

        qemu_mutex_unlock(&d->pgraph.lock);
        qemu_mutex_lock(&d->pfifo.lock);
#else
        qemu_mutex_unlock(&d->pfifo.lock);
        qemu_mutex_lock(&d->pgraph.lock);

        if (can_fifo_access(d)) {
            num_proc =
                pgraph_method(d, subchannel, method, parameter, parameters,
                              num_words_available, max_lookahead_words, inc);
            g_nv2a_stats.cpu_working.method_count++;
            if (!inc && num_proc > 0) {
                g_nv2a_stats.cpu_working.method_noninc_words += num_proc;
            }
        }

        qemu_mutex_unlock(&d->pgraph.lock);
        qemu_mutex_lock(&d->pfifo.lock);
#endif
    } else {
        assert(false);
    }

puller_done:
    if (num_proc > 0) {
        *status |= NV_PFIFO_CACHE1_STATUS_LOW_MARK;
    }

    if (NV2A_PERF_LOG) {
        g_nv2a_stats.cpu_working.puller_total_ns += nv2a_clock_ns() - _puller_t0;
    }

    return num_proc;
}

static bool pfifo_pusher_should_stall(NV2AState *d)
{
    return !can_fifo_access(d) ||
           qatomic_read(&d->pgraph.waiting_for_nop);
}

static void pfifo_run_pusher(NV2AState *d)
{
    uint32_t *push0 = &d->pfifo.regs[NV_PFIFO_CACHE1_PUSH0];
    uint32_t *push1 = &d->pfifo.regs[NV_PFIFO_CACHE1_PUSH1];
    uint32_t *dma_subroutine = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_SUBROUTINE];
    uint32_t *dma_state = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_STATE];
    uint32_t *dma_push = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_PUSH];
    uint32_t *dma_get = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET];
    uint32_t *dma_put = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT];
    uint32_t *dma_dcount = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_DCOUNT];
    uint32_t *status = &d->pfifo.regs[NV_PFIFO_CACHE1_STATUS];

    if (!GET_MASK(*push0, NV_PFIFO_CACHE1_PUSH0_ACCESS) ||
        !GET_MASK(*dma_push, NV_PFIFO_CACHE1_DMA_PUSH_ACCESS) ||
        GET_MASK(*dma_push, NV_PFIFO_CACHE1_DMA_PUSH_STATUS)) {
        return;
    }

    // TODO: should we become busy here??
    // NV_PFIFO_CACHE1_DMA_PUSH_STATE _BUSY

    unsigned int channel_id = GET_MASK(*push1,
                                       NV_PFIFO_CACHE1_PUSH1_CHID);


    /* Channel running DMA mode */
    uint32_t channel_modes = d->pfifo.regs[NV_PFIFO_MODE];
    assert(channel_modes & (1 << channel_id));

    assert(GET_MASK(*push1, NV_PFIFO_CACHE1_PUSH1_MODE)
            == NV_PFIFO_CACHE1_PUSH1_MODE_DMA);

    /* We're running so there should be no pending errors... */
    assert(GET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_ERROR)
            == NV_PFIFO_CACHE1_DMA_STATE_ERROR_NONE);

    hwaddr dma_instance =
        GET_MASK(d->pfifo.regs[NV_PFIFO_CACHE1_DMA_INSTANCE],
                 NV_PFIFO_CACHE1_DMA_INSTANCE_ADDRESS) << 4;

    hwaddr dma_len;
    uint8_t *dma = nv_dma_map(d, dma_instance, &dma_len);

    /* The guest's own DMA object limit, i.e. how far ahead of PGRAPH the
     * guest can get before its ring fills and nxdk spins on DMA_GET. That is
     * the only bound on the skew that exists without the one above, so it is
     * reported rather than described. */
    fsk_note_ring(dma_len);

    uint32_t dma_get_start = *dma_get;

    while (!pfifo_pusher_should_stall(d)) {
        uint32_t dma_get_v = *dma_get;
        uint32_t dma_put_v = *dma_put;
        if (dma_get_v == dma_put_v) {
            /*
             * Caught up. This is the moment every published segment has
             * provably been consumed -- including every guest-memory read the
             * methods in it performed, which all happen synchronously on this
             * thread -- so it is where the skew is measured.
             *
             * The wake-up for a guest held at its submission point is NOT
             * here but in pfifo_thread(), after this function returns. Every
             * other way out of this loop -- the pusher stalling, the puller
             * refusing a method, a DMA error -- leaves a waiter with nothing
             * to wake it, and a 250 ms timeout in place of a signal reads as
             * a hang. One broadcast at the call site covers all of them.
             */
            fsk_note_caught_up(nv2a_clock_ns());
            break;
        }
        if (dma_get_v >= dma_len) {
            assert(false);
            SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_ERROR,
                     NV_PFIFO_CACHE1_DMA_STATE_ERROR_PROTECTION);
            break;
        }

        size_t num_words_available = dma_put_v - dma_get_v;
        assert(num_words_available % 4 == 0);
        num_words_available /= 4;

        uint32_t *word_ptr = (uint32_t*)(dma + dma_get_v);
        uint32_t word = ldl_le_p(word_ptr);
        dma_get_v += 4;

        uint32_t method_type =
            GET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD_TYPE);
        uint32_t method_subchannel =
            GET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_SUBCHANNEL);
        uint32_t method =
            GET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD) << 2;
        uint32_t method_count =
            GET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD_COUNT);

        uint32_t subroutine_state =
            GET_MASK(*dma_subroutine, NV_PFIFO_CACHE1_DMA_SUBROUTINE_STATE);

        if (method_count) {
            /* data word of methods command */
            d->pfifo.regs[NV_PFIFO_CACHE1_DMA_DATA_SHADOW] = word;

            assert((method & 3) == 0);
            uint32_t method_entry = 0;
            SET_MASK(method_entry, NV_PFIFO_CACHE1_METHOD_ADDRESS, method >> 2);
            SET_MASK(method_entry, NV_PFIFO_CACHE1_METHOD_TYPE, method_type);
            SET_MASK(method_entry, NV_PFIFO_CACHE1_METHOD_SUBCHANNEL,
                     method_subchannel);

            *status &= ~NV_PFIFO_CACHE1_STATUS_LOW_MARK;

            ssize_t num_words_processed =
                pfifo_run_puller(d, method_entry, word, word_ptr,
                                 MIN(method_count, num_words_available),
                                 num_words_available);
            if (num_words_processed < 0) {
                break;
            }

            dma_get_v += (num_words_processed-1)*4;

            if (method_type == NV_PFIFO_CACHE1_DMA_STATE_METHOD_TYPE_INC) {
                SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD,
                         (method + 4*num_words_processed) >> 2);
            }
            SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD_COUNT,
                     method_count - MIN(method_count, num_words_processed));

            (*dma_dcount) += num_words_processed;
        } else {
            /* no command active - this is the first word of a new one */
            d->pfifo.regs[NV_PFIFO_CACHE1_DMA_RSVD_SHADOW] = word;

            /* match all forms */
            if ((word & 0xe0000003) == 0x20000000) {
                /* old jump */
                d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET_JMP_SHADOW] =
                    dma_get_v;
                dma_get_v = word & 0x1fffffff;
                NV2A_DPRINTF("pb OLD_JMP 0x%x\n", dma_get_v);
            } else if ((word & 3) == 1) {
                /* jump */
                d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET_JMP_SHADOW] =
                    dma_get_v;
                dma_get_v = word & 0xfffffffc;
                NV2A_DPRINTF("pb JMP 0x%x\n", dma_get_v);
            } else if ((word & 3) == 2) {
                /* call */
                if (subroutine_state) {
                    SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_ERROR,
                             NV_PFIFO_CACHE1_DMA_STATE_ERROR_CALL);
                    break;
                } else {
                    *dma_subroutine = dma_get_v;
                    SET_MASK(*dma_subroutine,
                             NV_PFIFO_CACHE1_DMA_SUBROUTINE_STATE, 1);
                    dma_get_v = word & 0xfffffffc;
                    NV2A_DPRINTF("pb CALL 0x%x\n", dma_get_v);
                }
            } else if (word == 0x00020000) {
                /* return */
                if (!subroutine_state) {
                    SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_ERROR,
                             NV_PFIFO_CACHE1_DMA_STATE_ERROR_RETURN);
                    // break;
                } else {
                    dma_get_v = *dma_subroutine & 0xfffffffc;
                    SET_MASK(*dma_subroutine,
                             NV_PFIFO_CACHE1_DMA_SUBROUTINE_STATE, 0);
                    NV2A_DPRINTF("pb RET 0x%x\n", dma_get_v);
                }
            } else if ((word & 0xe0030003) == 0) {
                /* increasing methods */
                SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD,
                         (word & 0x1fff) >> 2 );
                SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_SUBCHANNEL,
                         (word >> 13) & 7);
                SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD_COUNT,
                         (word >> 18) & 0x7ff);
                SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD_TYPE,
                         NV_PFIFO_CACHE1_DMA_STATE_METHOD_TYPE_INC);
                *dma_dcount = 0;
            } else if ((word & 0xe0030003) == 0x40000000) {
                /* non-increasing methods */
                SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD,
                         (word & 0x1fff) >> 2 );
                SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_SUBCHANNEL,
                         (word >> 13) & 7);
                SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD_COUNT,
                         (word >> 18) & 0x7ff);
                SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_METHOD_TYPE,
                         NV_PFIFO_CACHE1_DMA_STATE_METHOD_TYPE_NON_INC);
                *dma_dcount = 0;
            } else {
                NV2A_DPRINTF("pb reserved cmd 0x%x - 0x%x\n",
                             dma_get_v, word);
                SET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_ERROR,
                         NV_PFIFO_CACHE1_DMA_STATE_ERROR_RESERVED_CMD);
                // break;
                assert(false);
            }
        }

        *dma_get = dma_get_v;

        if (GET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_ERROR)) {
            break;
        }
    }

    // NV2A_DPRINTF("DMA pusher done: max 0x%" HWADDR_PRIx ", 0x%" HWADDR_PRIx " - 0x%" HWADDR_PRIx "\n",
    //      dma_len, control->dma_get, control->dma_put);

    uint32_t dma_get_end = *dma_get;
    if (dma_get_end >= dma_get_start) {
        g_nv2a_stats.cpu_working.pusher_words +=
            (dma_get_end - dma_get_start) / 4;
    }

    uint32_t error = GET_MASK(*dma_state, NV_PFIFO_CACHE1_DMA_STATE_ERROR);
    if (error) {
        NV2A_DPRINTF("pb error: %d\n", error);
        assert(false);

        SET_MASK(*dma_push, NV_PFIFO_CACHE1_DMA_PUSH_STATUS, 1); /* suspended */

        // d->pfifo.pending_interrupts |= NV_PFIFO_INTR_0_DMA_PUSHER;
        // nv2a_update_irq(d);
    }
}

void *pfifo_thread(void *arg)
{
    NV2AState *d = (NV2AState *)arg;

#if defined(__ANDROID__) && XEMU_OPT_THREAD_AFFINITY
    xemu_pin_to_big_cores("pfifo_thread");
#endif

    pgraph_init_thread(d);

#ifdef __ANDROID__
    __android_log_print(ANDROID_LOG_INFO, "hakuX-threads",
                        "tid=%d role=pfifo (pusher, puller, pgraph methods, "
                        "vulkan translation)", (int)gettid());
#endif

    rcu_register_thread();

    qemu_mutex_lock(&d->pfifo.lock);
    bool was_active = true;
    while (true) {
        was_active = d->pfifo.fifo_kick;
        d->pfifo.fifo_kick = false;

        pgraph_process_pending(d);

        if (!d->pfifo.halt) {
            uint32_t get_before = d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET];
            bool was_post_flip = NV2A_PERF_LOG
                                 ? g_nv2a_stats.phase_working.post_flip
                                 : false;
            int64_t push_t0 = NV2A_PERF_LOG ? nv2a_clock_ns() : 0;
            pfifo_run_pusher(d);
            if (NV2A_PERF_LOG) {
                g_nv2a_stats.cpu_working.pusher_run_ns +=
                    nv2a_clock_ns() - push_t0;
            }
            if (d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET] != get_before
                && was_post_flip) {
                g_nv2a_stats.phase_working.post_flip = false;
            }
        }

        /*
         * Release anything held at its submission point by pfifo_bound_skew().
         *
         * Unconditional, and placed here rather than at the caught-up break
         * inside the pusher, because the pusher has five other exits -- a
         * stall on the flip, on a NOP acknowledgement or on a context switch,
         * a puller that refused the method, a DMA protection error -- and a
         * waiter that only ever hears about the happy one waits out its whole
         * timeout instead. The waiter re-checks DMA_GET under this same lock,
         * so a broadcast it cannot act on costs it nothing, and when the
         * bound is off there is never a waiter at all.
         *
         * Signalled here and not at the idle park below on purpose: the park
         * is FIFO_SPIN_ACTIVE_NS later, and adding 100 us to every
         * submission the guest makes would price the bound out of existence
         * before it was measured.
         */
        qemu_cond_broadcast(&d->pfifo.fifo_drained_cond);

        pgraph_process_pending_reports(d);

        /* One line every two seconds, from the thread that is always running
         * when there is anything to measure. Emitted whether or not the bound
         * is enabled, because the unbounded numbers are the finding. */
        fsk_maybe_dump(nv2a_clock_ns());

        /* When a diag capture is pending or active and the PFIFO has no
         * more commands to process, force a flip_stall so the capture
         * progresses even for idle games.  This is intentionally placed
         * AFTER command processing so the game's own FLIP_STALL gets
         * first chance to handle the capture with proper draw data. */
        if ((nv2a_dbg_diag_frame_pending() || nv2a_dbg_diag_frame_active())
            && !d->pfifo.fifo_kick) {
            qemu_mutex_unlock(&d->pfifo.lock);
            qemu_mutex_lock(&d->pgraph.lock);
            d->pgraph.renderer->ops.surface_update(d, false, true, true);
            d->pgraph.renderer->ops.flip_stall(d);
            qemu_mutex_unlock(&d->pgraph.lock);
            qemu_mutex_lock(&d->pfifo.lock);
        }

        if (!d->pfifo.fifo_kick) {
            int64_t idle_t0 = nv2a_clock_ns();

#if XEMU_OPT_FIFO_SPIN
            if (was_active) {
                qemu_mutex_unlock(&d->pfifo.lock);

                bool spun_awake = false;
                int64_t spin_deadline = idle_t0 + FIFO_SPIN_ACTIVE_NS;
                for (unsigned spin_i = 0; ; spin_i++) {
                    if (qatomic_read(&d->pfifo.fifo_kick)) {
                        spun_awake = true;
                        break;
                    }
                    if ((spin_i & 0xFF) == 0 &&
                        nv2a_clock_ns() >= spin_deadline) {
                        break;
                    }
#ifdef __aarch64__
                    __asm__ volatile("yield" ::: "memory");
#endif
                }
                if (spun_awake) {
                    g_nv2a_stats.cpu_working.kick_count_spun++;
                }

                qemu_mutex_lock(&d->pfifo.lock);

                if (!spun_awake && !d->pfifo.fifo_kick) {
                    qemu_cond_signal(&d->pfifo.fifo_idle_cond);
                    qemu_cond_wait(&d->pfifo.fifo_cond, &d->pfifo.lock);
                }
            } else {
                g_nv2a_stats.cpu_working.kick_count_idle++;
                qemu_cond_signal(&d->pfifo.fifo_idle_cond);
                qemu_cond_wait(&d->pfifo.fifo_cond, &d->pfifo.lock);
            }
#else
            qemu_cond_signal(&d->pfifo.fifo_idle_cond);
            qemu_cond_wait(&d->pfifo.fifo_cond, &d->pfifo.lock);
#endif

            {
                /* Always on: idle_t0 above is read unconditionally, so this
                 * costs one more clock read per wait and answers the
                 * critical-path question without the phase instrumentation,
                 * which perturbs the thing it measures. */
                g_nv2a_stats.pacing.renderer_idle_acc_ns +=
                    nv2a_clock_ns() - idle_t0;
            }
            if (NV2A_PERF_LOG) {
                int64_t idle_ns = nv2a_clock_ns() - idle_t0;
                g_nv2a_stats.phase_working.fifo_idle_ns += idle_ns;
                if (g_nv2a_stats.phase_working.post_flip) {
                    g_nv2a_stats.phase_working.fifo_idle_frame_ns += idle_ns;
                } else {
                    g_nv2a_stats.phase_working.fifo_idle_starve_ns += idle_ns;
                }
            }
        }

        if (d->exiting) {
            break;
        }
    }
    qemu_mutex_unlock(&d->pfifo.lock);

    rcu_unregister_thread();

    return NULL;
}

static uint32_t ramht_hash(NV2AState *d, uint32_t handle)
{
    unsigned int ramht_size =
        1 << (GET_MASK(d->pfifo.regs[NV_PFIFO_RAMHT], NV_PFIFO_RAMHT_SIZE)+12);

    /* XXX: Think this is different to what nouveau calculates... */
    unsigned int bits = ctz32(ramht_size)-1;

    uint32_t hash = 0;
    while (handle) {
        hash ^= (handle & ((1 << bits) - 1));
        handle >>= bits;
    }

    unsigned int channel_id = GET_MASK(d->pfifo.regs[NV_PFIFO_CACHE1_PUSH1],
                                       NV_PFIFO_CACHE1_PUSH1_CHID);
    hash ^= channel_id << (bits - 4);

    return hash;
}


static RAMHTEntry ramht_lookup(NV2AState *d, uint32_t handle)
{
    hwaddr ramht_size =
        1 << (GET_MASK(d->pfifo.regs[NV_PFIFO_RAMHT], NV_PFIFO_RAMHT_SIZE)+12);

    uint32_t hash = ramht_hash(d, handle);
    assert(hash * 8 < ramht_size);

    hwaddr ramht_address =
        GET_MASK(d->pfifo.regs[NV_PFIFO_RAMHT],
                 NV_PFIFO_RAMHT_BASE_ADDRESS) << 12;

    assert(ramht_address + hash * 8 < memory_region_size(&d->ramin));

    uint8_t *entry_ptr = d->ramin_ptr + ramht_address + hash * 8;

    uint32_t entry_handle = ldl_le_p((uint32_t*)entry_ptr);
    uint32_t entry_context = ldl_le_p((uint32_t*)(entry_ptr + 4));

    return (RAMHTEntry){
        .handle = entry_handle,
        .instance = (entry_context & NV_RAMHT_INSTANCE) << 4,
        .engine = (entry_context & NV_RAMHT_ENGINE) >> 16,
        .channel_id = (entry_context & NV_RAMHT_CHID) >> 24,
        .valid = entry_context & NV_RAMHT_STATUS,
    };
}
