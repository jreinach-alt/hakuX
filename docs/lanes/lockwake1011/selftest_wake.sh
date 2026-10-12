#!/usr/bin/env bash
# selftest_wake.sh -- pfifo.c's posted-put block and user.c (#433), on the real
# source. The successor of docs/lanes/postput1010/selftest_postput.sh, whose
# checks 1-6 and falsifiers F1-F5 it keeps unchanged; that one no longer
# compiles, since lockwake1011 routes both of the vCPU's timed pfifo.lock
# acquisitions through pfifo_lock_timed().
#
# Compiles hw/xbox/nv2a/user.c verbatim, the `posted-put` block of
# hw/xbox/nv2a/pfifo.c verbatim (cut between its BEGIN/END markers), and
# pfifo_lock_timed_ft() verbatim, against a stub nv2a_int.h that carries the
# real NV2A_LOCKW_* enum (debug.h), the real pfifo_lock_timed() (nv2a_int.h),
# the real include/qemu/atomic.h, qemu/futex.h and nv2a_regs.h, and
# util/event.c's QemuEvent functions verbatim (the futex flavour the build
# uses on Linux and Android), -Wall -Werror, and runs the harness three times:
#   off   HAKUX_POSTED_PUT unset, HAKUX_LOCKFREE_WAKE=1 (which must be inert)
#   on    HAKUX_POSTED_PUT=1
#   wake  HAKUX_POSTED_PUT=1 HAKUX_LOCKFREE_WAKE=1
# The switches are read once per process, as in the build. Checks 1-7 run in
# every mode; their expectations for off and on are unchanged.
#
#   1. POSTED (on): a DMA_PUT store made while another thread holds pfifo.lock
#      for 400 ms returns in under 100 ms, stores the value, sets the kick, and
#      does not run the locked path.
#      LOCKED (off): the same store waits out the hold and runs the locked
#      path, as master does.
#   2. FREE: with the lock free the store takes the locked path, unchanged.
#   3. BOUND: with the skew bound on, the store still waits for the lock.
#   4. WAKEUP, no lost wakeup end to end: a PFIFO-thread stand-in with the
#      real loop shape -- pfifo_take_kick(), consume DMA_PUT with acquire,
#      sometimes work holding the lock, sometimes the unlocked idle spin, then
#      pfifo_park() unless kicked -- a third thread kicking under the lock as
#      PGRAPH and the VBLANK do, and a guest that stores DMA_PUT and waits for
#      it to be consumed, 100,000 times. Every store must be consumed within
#      1 s. On: both the posted and the locked path run at least 1,000 times,
#      or the check cannot discriminate. Off: nothing is posted. The stub's
#      condition wait spins 20 us under the lock before it sleeps, which
#      widens the window between the kick check and the sleep.
#   5. RACE, the handshake alone, as a store-buffering litmus test: each round
#      the PFIFO stand-in holds the lock and calls pfifo_park() while the guest
#      posts a DMA_PUT, both released at once with a random skew of a few
#      hundred ns. The stub's wait records that it would have slept and
#      returns. A round is lost when the stand-in would sleep and the poster
#      did not broadcast. Must be 0 in 2 s of rounds, on and off.
#   6. STATIC: the pusher loads DMA_PUT with acquire; the PFIFO thread clears
#      the kick through pfifo_take_kick() and parks only through pfifo_park();
#      no plain kick store outside the switch-off branch; user.c times every
#      lock it takes that it did not trylock, through pfifo_lock_timed(), by
#      register; nothing else in user.c or pfifo.c adds to lock_wait_ns.
#   7. SITES (lockwake1011): each of the vCPU's waits for a held pfifo.lock
#      is booked where it was made. With HAKUX_FRAMETRACE off (hakux_ft_on 0)
#      only lock_wait_ns moves, no site counter and no frametrace wait. On: a
#      DMA_GET, a REF and a DMA_PUT store under a 400 ms hold each book >= 300
#      ms, one acquisition and one long one to their own site -- the DMA_PUT
#      to PUT when it is not posted (off) and to KICK when it is posted to a
#      parked PFIFO thread (on), whose wait is also booked as parked; each
#      acquisition is one frametrace pfifo.lock wait with holder PFIFO; and
#      lock_wait_ns moves by exactly the sum of the sites. Wake: the posted
#      DMA_PUT takes no lock, so it books nothing anywhere.
#   8. LOCKFREE: a DMA_PUT store made while a third thread holds pfifo.lock
#      for 400 ms and the PFIFO thread is parked. Wake: returns in under
#      100 ms, stores the value, sets the kick and the event (one set), and
#      adds nothing to lock_wait_ns. On and off: it waits out the hold (the
#      wait this lane measured on the Nova) and sets no event.
#   9. IDLE: the event is reset at every park, so an idle PFIFO thread sleeps:
#      with an old set left on the event and nothing to do, check 4's
#      stand-in turns its loop at most twice in 200 ms (every mode).
#  10. EXIT (wake): 2,000 exits made as nv2a_exitfn() makes them -- `exiting`,
#      the broadcast and the event set, without the lock -- each at a random
#      point of a PFIFO-thread stand-in's loop (pfifo_thread()'s shape: take
#      the kick, work, park unless kicked, break on `exiting`). Each must be
#      joined within 1 s. Master's exit, a bare broadcast with no predicate,
#      can be lost the same way (NOTES.md section 2); it is not checked here.
#
# Falsifiers (each must FAIL a check, or the check means nothing):
#   F1. the block with the parked wakeup removed (`if (0)`): check 4 must
#       report a lost wakeup;
#   F2. user.c at BASE (before postput1010): check 1 (on) must block for the
#       hold;
#   F3. the block with both smp_mb() removed: check 5 must count lost rounds.
#       The host is x86-64, whose only reordering is a store passing a later
#       load -- exactly the one the barriers forbid -- so this is the mutant
#       the host can show.
#   F4, F5. the same with only pfifo_park()'s, then only pfifo_post_kick()'s
#       barrier removed: check 5 must count lost rounds for each.
#   F6. user.c booking the DMA_GET store to OTHER: check 7 must fail (off).
#   F7. pfifo_lock_timed() without its frametrace branch: check 7 must fail.
#   F8. pfifo_lock_timed_ft() without its lock_wait_ns add: check 7 must fail.
#   F9. pfifo_post_kick() booking its wait to PUT: check 7 must fail (on).
#   F1, F3, F4, F5 are also run in wake mode, where they must fail the same
#   checks: the wake keeps the handshake and both its barriers.
#   F10. pfifo_park() without the event reset: check 9 must fail (wake).
#   F11. the reset moved after the condition check, just before the wait:
#        check 5 must count lost rounds (wake). A set that lands between the
#        check and the reset is erased.
#   F12. pfifo_wake() without its event set: check 4 must lose a wakeup (wake).
#   F13. pfifo_park() without the `exiting` predicate: check 10 must hang (wake).
#   F14. pfifo_post_kick() without its lock-free branch: check 8 must fail (wake).
#
# What it cannot show: the DMA_PUT re-check in pfifo_park() covers a third
# kick writer under the C11 model (see the block's comment). Neither x86-64
# nor ARMv8 can produce that case, so no host run can fail without it. Nor
# does it run nv2a.c: nv2a_lock_fifo()'s and nv2a_exitfn()'s event sets are
# checked statically, and check 10 runs nv2a_exitfn()'s statements as copied
# into the harness.
#
# Usage: bash docs/lanes/lockwake1011/selftest_wake.sh   (from the repo root)
# Exit 0 when every check passes and every falsifier fails as it must.
set -u
REPO=$(git rev-parse --show-toplevel) || exit 2
BASE=${BASE:-b74cff74ed}          # master the lane branched from
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
ok()  { echo "  ok   $*"; }
bad() { echo "  FAIL $*"; fail=$((fail+1)); }

cat > "$T/stub_head.h" <<'EOF'
/* Stub of hw/xbox/nv2a/nv2a_int.h: what user.c and pfifo.c's posted-put
 * block touch. The NV2A_LOCKW_* enum and pfifo_lock_timed() are cut from the
 * real headers and pasted in by the script. */
#include <assert.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "qemu/compiler.h"
#define qemu_build_assert(test) _Static_assert(test, #test)
#include "qemu/atomic.h"
typedef uint64_t hwaddr;
static inline int ctz32(uint32_t v) { return v ? __builtin_ctz(v) : 32; }
#include "hw/xbox/nv2a/nv2a_regs.h"
typedef pthread_mutex_t QemuMutex;
typedef pthread_cond_t QemuCond;
#define qemu_mutex_lock(m) pthread_mutex_lock(m)
#define qemu_mutex_unlock(m) pthread_mutex_unlock(m)
#define qemu_mutex_trylock(m) pthread_mutex_trylock(m)
#define qemu_cond_signal(c) pthread_cond_signal(c)
#define QEMU_CLOCK_REALTIME 0
static inline int64_t qemu_clock_get_ns(int c)
{
    struct timespec ts; (void)c;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000LL + ts.tv_nsec;
}
/* Every broadcast is counted, for check 5. */
extern uint32_t stub_broadcasts;
static inline void stub_cond_broadcast(QemuCond *c)
{
    qatomic_inc(&stub_broadcasts);
    pthread_cond_broadcast(c);
}
#define qemu_cond_broadcast(c) stub_cond_broadcast(c)
/* A preempted thread between its kick check and its sleep, still holding
 * the lock: spin `stub_widen_ns` first. In check 5 (`stub_litmus`) the wait
 * records that it would sleep, then releases the lock, as a wait does, only
 * until this round's poster has returned: a lost wakeup is then a round in
 * which it would sleep and nobody broadcast, and the round still ends. */
extern int64_t stub_widen_ns;
extern int stub_litmus, stub_waited, stub_round, stub_posted_round;
static inline void stub_cond_wait(QemuCond *c, QemuMutex *m)
{
    if (qatomic_read(&stub_litmus)) {
        int r = qatomic_read(&stub_round);
        qatomic_set(&stub_waited, 1);
        pthread_mutex_unlock(m);
        while (qatomic_load_acquire(&stub_posted_round) != r) { }
        pthread_mutex_lock(m);
        return;
    }
    int64_t until = qemu_clock_get_ns(0) + stub_widen_ns;
    while (qemu_clock_get_ns(0) < until) { }
    pthread_cond_wait(c, m);
}
#define qemu_cond_wait(c, m) stub_cond_wait(c, m)
/* include/qemu/thread.h's QemuEvent with HAVE_FUTEX. The functions are
 * util/event.c's, cut by the script and wrapped in harness.c. */
typedef struct QemuEvent { unsigned value; bool initialized; } QemuEvent;
void qemu_event_init(QemuEvent *ev, bool init);
void qemu_event_set(QemuEvent *ev);
void qemu_event_reset(QemuEvent *ev);
void qemu_event_wait(QemuEvent *ev);
typedef struct NV2AState {
    bool exiting;
    struct {
        QemuMutex lock; QemuCond fifo_cond; uint32_t regs[0x2000];
        bool fifo_kick; bool parked; QemuEvent wake; uint32_t put_seen;
        int64_t posted_ts;
    } pfifo;
} NV2AState;
@LOCKW_ENUM@
typedef struct CpuTimingWork {
    int64_t lock_wait_ns;
    int64_t lockw_site_ns[NV2A_LOCKW_NSITE];
    uint32_t lockw_site_n[NV2A_LOCKW_NSITE];
    uint32_t lockw_site_nb[NV2A_LOCKW_NSITE];
    int64_t lockw_parked_ns;
    uint32_t kick_count;
} CpuTimingWork;
extern struct { CpuTimingWork cpu_working; } g_nv2a_stats;
/* profile.h's frametrace wait, counted for check 7. */
enum { HAKUX_FT_VCPU, HAKUX_FT_PFIFO, HAKUX_FT_RENDER };
enum { HAKUX_FT_W_BQL, HAKUX_FT_W_PFIFO_LOCK, HAKUX_FT_W_PGRAPH_LOCK };
typedef struct HakuxFtWait { int reason, holder; } HakuxFtWait;
extern int stub_ft_begun, stub_ft_ended, stub_ft_wrong;
static inline void hakux_ft_wait_begin(HakuxFtWait *w, int reason, int holder)
{
    w->reason = reason; w->holder = holder; stub_ft_begun++;
    stub_ft_wrong += reason != HAKUX_FT_W_PFIFO_LOCK || holder != HAKUX_FT_PFIFO;
}
static inline void hakux_ft_wait_end(HakuxFtWait *w) { (void)w; stub_ft_ended++; }
@LOCK_TIMED@
static inline void nv2a_reg_log_read(int b, hwaddr a, unsigned s, uint64_t v) { (void)b; (void)a; (void)s; (void)v; }
static inline void nv2a_reg_log_write(int b, hwaddr a, unsigned s, uint64_t v) { (void)b; (void)a; (void)s; (void)v; }
void pfifo_kick(NV2AState *d);
bool pfifo_dma_put_may_post(NV2AState *d, unsigned int channel_id);
void pfifo_post_dma_put(NV2AState *d, uint32_t val);
uint64_t user_read(void *opaque, hwaddr addr, unsigned int size);
void user_write(void *opaque, hwaddr addr, uint64_t val, unsigned int size);
EOF

cat > "$T/harness.c" <<'EOF'
#define _GNU_SOURCE
#include "nv2a_int.h"
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <unistd.h>
#define CONFIG_LINUX 1
#include "qemu/futex.h"
#include "event_real.c"   /* util/event.c from EV_SET on, as real_event_* */
__typeof__(g_nv2a_stats) g_nv2a_stats;
int hakux_ft_on;
int stub_ft_begun, stub_ft_ended, stub_ft_wrong;
int64_t stub_widen_ns;
int stub_litmus, stub_waited, stub_woken, stub_round, stub_posted_round;
uint32_t stub_broadcasts, stub_event_sets;

/* The event as the build has it, with what the checks read: sets are
 * counted; in check 5 a wait records that it would sleep and, once this
 * round's poster has returned, whether the event is set (a wait that would
 * not return then never would), and returns; otherwise a wait first spins
 * `stub_widen_ns` with the lock released. */
void qemu_event_init(QemuEvent *ev, bool init) { real_event_init(ev, init); }
void qemu_event_reset(QemuEvent *ev) { real_event_reset(ev); }
void qemu_event_set(QemuEvent *ev)
{
    qatomic_inc(&stub_event_sets);
    real_event_set(ev);
}
void qemu_event_wait(QemuEvent *ev)
{
    if (qatomic_read(&stub_litmus)) {
        int r = qatomic_read(&stub_round);
        qatomic_set(&stub_waited, 1);
        while (qatomic_load_acquire(&stub_posted_round) != r) { }
        qatomic_set(&stub_woken, qatomic_load_acquire(&ev->value) == EV_SET);
        return;
    }
    int64_t until = qemu_clock_get_ns(0) + stub_widen_ns;
    while (qemu_clock_get_ns(0) < until) { }
    real_event_wait(ev);
}

/* What pfifo.c's posted-put block needs from the rest of pfifo.c. */
#define FIFO_SKEW_OFF 0
static int bound_mode;
static int fifo_skew_bound_mode(void) { return bound_mode; }
#define fsk_note_post(d) ((void)(d))
#include "postput_block.c"
#include "lock_timed_ft.c"

/* pfifo_kick() as pfifo.c has it, less the submission bookkeeping: the
 * block's pfifo_wake(). Called under the lock. */
static int locked_kicks;
void pfifo_kick(NV2AState *d)
{
    locked_kicks++;
    pfifo_wake(d);
}

static NV2AState s;
static volatile int held;
static void *holder(void *arg)
{
    pthread_mutex_lock(&s.pfifo.lock);
    held = 1;
    usleep(400 * 1000);
    pthread_mutex_unlock(&s.pfifo.lock);
    (void)arg; return NULL;
}
static int64_t now(void) { return qemu_clock_get_ns(0); }
static void hold_lock(pthread_t *t) { held = 0; pthread_create(t, NULL, holder, NULL); while (!held) usleep(100); }
static void spin_ns(int64_t ns) { int64_t until = now() + ns; while (now() < until) { } }
static void wake_for_exit(void)     /* as nv2a_lock_fifo() wakes it */
{
    pthread_mutex_lock(&s.pfifo.lock);
    qatomic_set(&s.pfifo.fifo_kick, true);
    pthread_cond_broadcast(&s.pfifo.fifo_cond);
    qemu_event_set(&s.pfifo.wake);
    pthread_mutex_unlock(&s.pfifo.lock);
}

/* Check 4's PFIFO thread: pfifo_thread()'s loop, less the work. */
static uint32_t consumed;
static int stop, turns;
static void *pfifo_sim(void *arg)
{
    unsigned seed = 1;
    pthread_mutex_lock(&s.pfifo.lock);
    while (!qatomic_read(&stop)) {
        qatomic_inc(&turns);
        bool was_active = pfifo_take_kick(&s);
        qatomic_store_release(&consumed,
            qatomic_load_acquire(&s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT]));
        if (rand_r(&seed) % 2) {             /* a method or a finish */
            spin_ns(rand_r(&seed) % 20000);
        }
        if (!qatomic_read(&s.pfifo.fifo_kick)) {
            bool spun_awake = false;
            if (was_active && rand_r(&seed) % 2) {   /* XEMU_OPT_FIFO_SPIN */
                pthread_mutex_unlock(&s.pfifo.lock);
                int64_t until = now() + rand_r(&seed) % 10000;
                while (!(spun_awake = qatomic_read(&s.pfifo.fifo_kick)) &&
                       now() < until) { }
                pthread_mutex_lock(&s.pfifo.lock);
            }
            if (!spun_awake && !qatomic_read(&s.pfifo.fifo_kick)) {
                pfifo_park(&s);
            }
        }
    }
    pthread_mutex_unlock(&s.pfifo.lock);
    (void)arg; return NULL;
}

/* Check 4's third writer: PGRAPH and the VBLANK kick under the lock. */
static void *other_kicker(void *arg)
{
    unsigned seed = 3;
    while (!qatomic_read(&stop)) {
        spin_ns(rand_r(&seed) % 60000);
        pthread_mutex_lock(&s.pfifo.lock);
        pfifo_wake(&s);
        pthread_mutex_unlock(&s.pfifo.lock);
    }
    (void)arg; return NULL;
}

/* Check 5's PFIFO stand-in: one pfifo_park() per round, lock held. */
static int rounds_go, rounds_ready, rounds_done, rounds_acked, round_waited;
static void *park_round(void *arg)
{
    uint32_t x = 12345;
    for (int i = 1; ; i++) {
        while (qatomic_load_acquire(&rounds_acked) != i - 1) { }
        pthread_mutex_lock(&s.pfifo.lock);
        qatomic_set(&s.pfifo.fifo_kick, false);
        s.pfifo.put_seen = qatomic_read(&s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT]);
        qatomic_set(&stub_waited, 0);
        qatomic_set(&stub_woken, 0);
        qatomic_set(&stub_round, i);
        qatomic_store_release(&rounds_ready, i);
        int go;
        while ((go = qatomic_load_acquire(&rounds_go)) != i) {
            if (go < 0) { pthread_mutex_unlock(&s.pfifo.lock); return NULL; }
        }
        x ^= x << 13; x ^= x >> 17; x ^= x << 5;
        for (volatile unsigned k = x % 96; k; k--) { }
        pfifo_park(&s);
        round_waited = qatomic_read(&stub_waited);
        pthread_mutex_unlock(&s.pfifo.lock);
        qatomic_store_release(&rounds_done, i);
    }
    (void)arg;
}

/* Check 10's PFIFO thread: pfifo_thread()'s loop with its exit. */
static void *exit_sim(void *arg)
{
    unsigned seed = (unsigned)(uintptr_t)arg;
    pthread_mutex_lock(&s.pfifo.lock);
    while (true) {
        pfifo_take_kick(&s);
        if (rand_r(&seed) % 2) {
            spin_ns(rand_r(&seed) % 20000);
        }
        if (!qatomic_read(&s.pfifo.fifo_kick)) {
            pfifo_park(&s);
        }
        if (qatomic_read(&s.exiting)) {
            break;
        }
    }
    pthread_mutex_unlock(&s.pfifo.lock);
    return NULL;
}

int main(int argc, char **argv)
{
    const char *mode = argc > 1 ? argv[1] : "off";
    int wake = !strcmp(mode, "wake");
    int on = wake || !strcmp(mode, "on");
    int bad = 0;
    if (on) setenv("HAKUX_POSTED_PUT", "1", 1); else unsetenv("HAKUX_POSTED_PUT");
    /* off asks for the wake too: without the posted store it must be inert */
    if (wake || !on) setenv("HAKUX_LOCKFREE_WAKE", "1", 1); else unsetenv("HAKUX_LOCKFREE_WAKE");
    pthread_mutex_init(&s.pfifo.lock, NULL);
    pthread_cond_init(&s.pfifo.fifo_cond, NULL);
    qemu_event_init(&s.pfifo.wake, false);
    s.pfifo.regs[NV_PFIFO_MODE] = 1;                     /* channel 0: DMA mode */
    s.pfifo.regs[NV_PFIFO_CACHE1_PUSH1] = 0;             /* CHID 0 */
    printf("SWITCH %s WAKE %s\n", pfifo_posted_put_on() ? "on" : "off",
           pfifo_lockfree_wake_on() ? "on" : "off");
    bad += pfifo_posted_put_on() != on;
    bad += pfifo_lockfree_wake_on() != wake;

    {   /* 1. a store while the lock is held */
        pthread_t t; hold_lock(&t);
        int k0 = locked_kicks;
        int64_t t0 = now();
        user_write(&s, NV_USER_DMA_PUT, 0x2468, 4);
        int64_t ms = (now() - t0) / 1000000;
        pthread_join(t, NULL);
        int stored = s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT] == 0x2468 &&
                     s.pfifo.fifo_kick && user_read(&s, NV_USER_DMA_PUT, 4) == 0x2468;
        int pass = on ? ms < 100 && stored && locked_kicks == k0
                      : ms >= 300 && stored && locked_kicks == k0 + 1;
        printf("%s %s ms=%lld put=0x%x kick=%d locked_kicks+%d\n", on ? "POSTED" : "LOCKED",
               pass ? "ok" : "FAIL", (long long)ms,
               s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT], s.pfifo.fifo_kick, locked_kicks - k0);
        bad += !pass;
    }
    {   /* 2. free lock: the locked path */
        s.pfifo.fifo_kick = false;
        int k0 = locked_kicks;
        user_write(&s, NV_USER_DMA_PUT, 0x1000, 4);
        int pass = locked_kicks == k0 + 1 && s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT] == 0x1000;
        printf("FREE %s locked_kicks+%d\n", pass ? "ok" : "FAIL", locked_kicks - k0);
        bad += !pass;
    }
    {   /* 3. the skew bound needs the lock */
        bound_mode = 1;
        pthread_t t; hold_lock(&t);
        int64_t t0 = now();
        user_write(&s, NV_USER_DMA_PUT, 0x1100, 4);
        int64_t ms = (now() - t0) / 1000000;
        pthread_join(t, NULL);
        bound_mode = 0;
        int pass = ms >= 300;
        printf("BOUND %s ms=%lld\n", pass ? "ok" : "FAIL", (long long)ms);
        bad += !pass;
    }
    {   /* 7. each wait booked to its site (lockwake1011) */
        CpuTimingWork *w = &g_nv2a_stats.cpu_working, w0;
        int64_t sum = 0;
        /* wake: the posted DMA_PUT to a parked thread takes no lock at all */
        int ok7 = 1, acq = wake ? 2 : on ? 3 : 4, nsite = wake ? 2 : 3;
        int put_site = on ? NV2A_LOCKW_KICK : NV2A_LOCKW_PUT;
        pthread_t t;
        s.pfifo.fifo_kick = false;
        /* HAKUX_FRAMETRACE off: the sum only */
        w0 = *w;
        hold_lock(&t); user_write(&s, NV_USER_DMA_GET, 0x10, 4); pthread_join(t, NULL);
        int off_ok = w->lock_wait_ns - w0.lock_wait_ns >= 300000000LL &&
                     !memcmp(w->lockw_site_n, w0.lockw_site_n, sizeof(w0.lockw_site_n)) &&
                     !memcmp(w->lockw_site_ns, w0.lockw_site_ns, sizeof(w0.lockw_site_ns)) &&
                     stub_ft_begun == 0;
        /* on */
        qatomic_set(&hakux_ft_on, 1);
        w0 = *w;
        hold_lock(&t); user_write(&s, NV_USER_DMA_GET, 0x20, 4); pthread_join(t, NULL);
        hold_lock(&t); user_write(&s, NV_USER_REF, 0x30, 4); pthread_join(t, NULL);
        qatomic_set(&s.pfifo.parked, on);   /* on: the PFIFO thread is parked */
        hold_lock(&t); user_write(&s, NV_USER_DMA_PUT, 0x1200, 4); pthread_join(t, NULL);
        qatomic_set(&s.pfifo.parked, false);
        user_write(&s, NV_USER_DMA_PUT, 0x1210, 4);  /* free: off books PUT; on takes it by trylock */
        qatomic_set(&hakux_ft_on, 0);
        int sites[3] = { NV2A_LOCKW_GET, NV2A_LOCKW_REF, put_site };
        for (int k = 0; k < nsite; k++) {
            int st = sites[k];
            uint32_t want_n = st == NV2A_LOCKW_PUT ? 2 : 1;
            if (w->lockw_site_ns[st] - w0.lockw_site_ns[st] < 300000000LL ||
                w->lockw_site_n[st] - w0.lockw_site_n[st] != want_n ||
                w->lockw_site_nb[st] - w0.lockw_site_nb[st] < 1) {
                ok7 = 0;
            }
        }
        for (int k = 0; k < NV2A_LOCKW_NSITE; k++) {
            sum += w->lockw_site_ns[k] - w0.lockw_site_ns[k];
        }
        int other = w->lockw_site_n[NV2A_LOCKW_OTHER] != w0.lockw_site_n[NV2A_LOCKW_OTHER] ||
                    w->lockw_site_n[on ? NV2A_LOCKW_PUT : NV2A_LOCKW_KICK] !=
                        w0.lockw_site_n[on ? NV2A_LOCKW_PUT : NV2A_LOCKW_KICK] ||
                    (wake && w->lockw_site_n[NV2A_LOCKW_KICK] !=
                                 w0.lockw_site_n[NV2A_LOCKW_KICK]);
        int64_t parked = w->lockw_parked_ns - w0.lockw_parked_ns;
        int pass = off_ok && ok7 && !other && sum == w->lock_wait_ns - w0.lock_wait_ns &&
                   (on && !wake ? parked >= 300000000LL : parked == 0) &&
                   stub_ft_begun == acq && stub_ft_ended == acq && !stub_ft_wrong;
        printf("SITES %s off_ok=%d sites_ok=%d stray=%d sum_ms=%lld lockw_ms=%lld parked_ms=%lld "
               "ft=%d/%d/%d want %d\n", pass ? "ok" : "FAIL", off_ok, ok7, other,
               (long long)(sum / 1000000), (long long)((w->lock_wait_ns - w0.lock_wait_ns) / 1000000),
               (long long)(parked / 1000000), stub_ft_begun, stub_ft_ended, stub_ft_wrong, acq);
        bad += !pass;
    }
    {   /* 8. the posted store's wake to a parked PFIFO thread, the lock held by a third */
        CpuTimingWork *w = &g_nv2a_stats.cpu_working;
        int64_t lw0 = w->lock_wait_ns;
        uint32_t e0 = qatomic_read(&stub_event_sets);
        pthread_t t;
        s.pfifo.fifo_kick = false;
        qemu_event_reset(&s.pfifo.wake);
        qatomic_set(&s.pfifo.parked, true);
        hold_lock(&t);
        int64_t t0 = now();
        user_write(&s, NV_USER_DMA_PUT, 0x1300, 4);
        int64_t ms = (now() - t0) / 1000000;
        pthread_join(t, NULL);
        qatomic_set(&s.pfifo.parked, false);
        int set = qatomic_read(&s.pfifo.wake.value) == EV_SET;
        int sets = (int)(qatomic_read(&stub_event_sets) - e0);
        int64_t lw = (w->lock_wait_ns - lw0) / 1000000;
        int stored = s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT] == 0x1300 && s.pfifo.fifo_kick;
        int pass = wake ? ms < 100 && set && sets == 1 && lw == 0 && stored
                        : ms >= 300 && !set && sets == 0 && lw >= 300 && stored;
        printf("LOCKFREE %s ms=%lld event_set=%d sets=%d lockw_ms=%lld stored=%d\n",
               pass ? "ok" : "FAIL", (long long)ms, set, sets, (long long)lw, stored);
        bad += !pass;
    }
    {   /* 4. no lost wakeup, end to end; 9. an idle PFIFO thread sleeps */
        stub_widen_ns = 20000;
        s.pfifo.fifo_kick = false;
        qatomic_set(&consumed, 0x1100);
        s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT] = 0x1100;
        pthread_t p, k;
        pthread_create(&p, NULL, pfifo_sim, NULL);
        usleep(50 * 1000);
        qemu_event_set(&s.pfifo.wake);   /* an earlier wake's set: the next park must clear it */
        usleep(20 * 1000);
        int t0 = qatomic_read(&turns);
        usleep(200 * 1000);
        int idle = qatomic_read(&turns) - t0;
        printf("IDLE %s turns=%d in 200 ms\n", idle <= 2 ? "ok" : "FAIL", idle);
        bad += idle > 2;
        pthread_create(&k, NULL, other_kicker, NULL);
        int n = 100000, lost = 0, i;
        int k0 = locked_kicks;
        unsigned seed = 7;
        for (i = 1; i <= n && !lost; i++) {
            uint32_t v = 0x2000 + 4 * (uint32_t)i;
            if (rand_r(&seed) % 2) {             /* land in every phase of the loop */
                spin_ns(rand_r(&seed) % 60000);
            }
            user_write(&s, NV_USER_DMA_PUT, v, 4);
            int64_t dl = now() + 1000000000LL;
            while (qatomic_load_acquire(&consumed) != v) {
                if (now() > dl) { lost = i; break; }
            }
        }
        int locked = locked_kicks - k0, posted = (i - 1) - locked;
        qatomic_set(&stop, 1);
        wake_for_exit();
        pthread_join(p, NULL);
        pthread_join(k, NULL);
        int pass = !lost && (on ? posted >= 1000 && locked >= 1000 : posted == 0);
        printf("WAKEUP %s stores=%d posted=%d locked=%d lost_at=%d\n", pass ? "ok" : "FAIL",
               i - 1, posted, locked, lost);
        bad += !pass;
    }
    {   /* 5. the handshake alone: store-buffering litmus */
        stub_widen_ns = 0;
        qatomic_set(&stub_litmus, 1);
        pthread_t p; pthread_create(&p, NULL, park_round, NULL);
        int64_t end = now() + 2000000000LL;
        int i, lost = 0, waits = 0, first = 0;
        uint32_t x = 99;
        for (i = 1; now() < end; i++) {
            while (qatomic_load_acquire(&rounds_ready) != i) { }
            uint32_t b0 = qatomic_read(&stub_broadcasts);
            qatomic_store_release(&rounds_go, i);
            x ^= x << 13; x ^= x >> 17; x ^= x << 5;
            for (volatile unsigned k = x % 96; k; k--) { }
            user_write(&s, NV_USER_DMA_PUT, 0x4000 + 4 * (uint32_t)(i & 0xFFFF), 4);
            qatomic_store_release(&stub_posted_round, i);
            while (qatomic_load_acquire(&rounds_done) != i) { }
            int w = round_waited;
            waits += w;
            if (wake ? w && !qatomic_read(&stub_woken)
                     : w && qatomic_read(&stub_broadcasts) == b0) {
                lost++;
                if (!first) first = i;
            }
            qatomic_store_release(&rounds_acked, i);
        }
        while (qatomic_load_acquire(&rounds_ready) != i) { }
        qatomic_store_release(&rounds_go, -1);
        pthread_join(p, NULL);
        qatomic_set(&stub_litmus, 0);
        int pass = !lost && i > 100000;
        printf("RACE %s rounds=%d would_sleep=%d lost=%d first_lost=%d\n",
               pass ? "ok" : "FAIL", i - 1, waits, lost, first);
        bad += !pass;
    }
    if (wake) {   /* 10. the exit wakes a parked PFIFO thread */
        stub_widen_ns = 0;
        int n = 2000, hung = 0, i;
        unsigned seed = 11;
        for (i = 1; i <= n && !hung; i++) {
            qatomic_set(&s.exiting, false);
            pthread_t p;
            pthread_create(&p, NULL, exit_sim, (void *)(uintptr_t)i);
            spin_ns(rand_r(&seed) % 60000);
            /* nv2a_exitfn() */
            qatomic_set(&s.exiting, true);
            qemu_cond_broadcast(&s.pfifo.fifo_cond);
            qemu_event_set(&s.pfifo.wake);
            struct timespec dl;
            clock_gettime(CLOCK_REALTIME, &dl);
            dl.tv_sec += 1;
            if (pthread_timedjoin_np(p, NULL, &dl) != 0) {
                hung = i;
                qemu_event_set(&s.pfifo.wake);   /* release it, to join */
                pthread_join(p, NULL);
            }
        }
        printf("EXIT %s exits=%d hung_at=%d\n", hung ? "FAIL" : "ok", i - 1, hung);
        bad += hung != 0;
    }
    return bad ? 1 : 0;
}
EOF

block() {   # <pfifo.c path> -> the posted-put block on stdout
    sed -n '/^\/\* BEGIN posted-put/,/^\/\* END posted-put \*\//p' "$1"
}

lockw_enum() {   # <debug.h path> -> the NV2A_LOCKW_* enum
    sed -n '/^enum {$/,/^};$/p' "$1" | awk '/^enum \{$/ { buf = ""; f = 1 }
        f { buf = buf $0 "\n" } /^};$/ && f { if (buf ~ /NV2A_LOCKW_KICK/) printf "%s", buf; f = 0 }'
}
lock_timed() {   # <nv2a_int.h path> -> hakux_ft_on .. pfifo_lock_timed()
    sed -n '/^extern int hakux_ft_on;/,/^}/p' "$1"
}
ft_fn() {        # <pfifo.c path> -> pfifo_lock_timed_ft()
    sed -n '/^void pfifo_lock_timed_ft(/,/^}/p' "$1"
}

# build <user.c> <block> <tag> [<lock_timed chunk> [<ft fn>]]
build() {
    mkdir -p "$T/$3"
    cp "$1" "$T/$3/user.c"
    cp "$2" "$T/$3/postput_block.c"
    cp "${5:-$T/ftfn.c}" "$T/$3/lock_timed_ft.c"
    cp "$T/event_real.c" "$T/$3/event_real.c"
    python3 - "$T/stub_head.h" "$T/enum.h" "${4:-$T/lock_timed.h}" > "$T/$3/nv2a_int.h" <<'PY'
import sys
s = open(sys.argv[1]).read()
s = s.replace('@LOCKW_ENUM@\n', open(sys.argv[2]).read())
s = s.replace('@LOCK_TIMED@\n', open(sys.argv[3]).read())
sys.stdout.write(s)
PY
    if ! gcc -std=gnu11 -O2 -Wall -Werror -pthread -I"$T/$3" -I"$REPO/include" -I"$REPO" \
            -o "$T/$3/h" "$T/$3/user.c" "$T/harness.c" 2> "$T/$3/cc.log"; then
        echo "COMPILE_FAIL"; sed 's/^/    /' "$T/$3/cc.log" | head -20; return 3
    fi
}

run() {     # <tag> off|on|wake
    "$T/$1/h" "$2"
}

block "$REPO/hw/xbox/nv2a/pfifo.c" > "$T/block.c"
if ! grep -q 'pfifo_park' "$T/block.c"; then
    bad "no posted-put block in pfifo.c"; echo "== FAIL ($fail)"; exit 1
fi
lockw_enum "$REPO/hw/xbox/nv2a/debug.h" > "$T/enum.h"
lock_timed "$REPO/hw/xbox/nv2a/nv2a_int.h" > "$T/lock_timed.h"
ft_fn "$REPO/hw/xbox/nv2a/pfifo.c" > "$T/ftfn.c"
sed -n '/^#define EV_SET/,$p' "$REPO/util/event.c" | sed 's/qemu_event_/real_event_/g' > "$T/event_real.c"
for f in enum.h:NV2A_LOCKW_NSITE lock_timed.h:'static inline void pfifo_lock_timed(' ftfn.c:'lockw_site_nb\[site\]++' \
         event_real.c:'qemu_futex_wait(ev, EV_BUSY);'; do
    if ! grep -q "${f#*:}" "$T/${f%%:*}"; then
        bad "cannot cut ${f%%:*} from the source"; echo "== FAIL ($fail)"; exit 1
    fi
done

build "$REPO/hw/xbox/nv2a/user.c" "$T/block.c" fix || { bad "the fix does not compile"; echo "== FAIL ($fail)"; exit 1; }
for sw in on off wake; do
    echo "== user.c and pfifo.c's posted-put block at the working tree, mode $sw"
    OUT=$(run fix $sw); RC=$?
    echo "$OUT" | sed 's/^/    /'
    if [ $RC -eq 0 ]; then
        case $sw in
        on)   ok "on: posted under a held lock, locked when free, locked under the bound, every wait at its site, the posted wake waits for the lock, no lost wakeup, no lost round" ;;
        off)  ok "off: locked under a held lock, as master; nothing posted; the wake switch inert; every wait at its site; no lost wakeup" ;;
        wake) ok "wake: the posted wake takes no lock and books nothing; the idle thread sleeps; no lost wakeup, no lost round, no lost exit" ;;
        esac
    else bad "mode $sw (rc $RC)"; fi
done

echo "== static: pfifo.c and user.c"
P="$REPO/hw/xbox/nv2a/pfifo.c"; U="$REPO/hw/xbox/nv2a/user.c"
OUTSIDE=$(sed '/^\/\* BEGIN posted-put/,/^\/\* END posted-put \*\//d' "$P")
if grep -q 'posted_put ? qatomic_load_acquire(dma_put)' "$P"; then
    ok "the pusher loads DMA_PUT with acquire when the switch is on"
else bad "no acquire load of DMA_PUT in the pusher"; fi
if grep -q 'was_active = pfifo_take_kick(d);' "$P" \
   && grep -q 'bool was = qatomic_xchg(&d->pfifo.fifo_kick, false);' "$T/block.c"; then
    ok "the loop top clears the kick through pfifo_take_kick() (xchg when on)"
else bad "loop top does not clear the kick through pfifo_take_kick()"; fi
if [ "$(grep -c 'qemu_cond_wait(&d->pfifo.fifo_cond' "$P")" = 2 ] \
   && [ "$(grep -c 'qemu_cond_wait(&d->pfifo.fifo_cond' "$T/block.c")" = 2 ]; then
    ok "both fifo_cond waits are in pfifo_park() (master's when off, the handshake's when on)"
else bad "a fifo_cond wait outside pfifo_park()"; fi
if ! echo "$OUTSIDE" | grep -qE 'd->pfifo\.fifo_kick = ' \
   && [ "$(grep -cE 'd->pfifo\.fifo_kick = ' "$T/block.c")" = 1 ]; then
    ok "no plain kick store but the switch-off branch of pfifo_take_kick()"
else bad "a plain kick store outside pfifo_take_kick()'s off branch"; fi
if [ "$(grep -c 'smp_mb();' "$T/block.c")" = 2 ]; then
    ok "one full barrier on each side of the handshake"
else bad "expected two smp_mb() in the block"; fi
ELSE=$(sed -n '/^    } else {$/,/^    }$/p' "$U")
if [ "$(echo "$ELSE" | grep -cE 'pfifo_lock_timed\(d, NV2A_LOCKW_(PUT|GET|REF|OTHER)\);')" = 4 ] \
   && [ "$(grep -c 'qemu_mutex_lock(&d->pfifo.lock)' "$U")" = 0 ] \
   && grep -q 'qemu_mutex_trylock(&d->pfifo.lock) != 0' "$U"; then
    ok "user.c: every lock it does not trylock is timed through pfifo_lock_timed(), by register"
else bad "user.c takes pfifo.lock untimed, or not by register"; fi
if grep -q 'pfifo_lock_timed(d, NV2A_LOCKW_KICK);' "$T/block.c" \
   && [ "$(grep -c 'lock_wait_ns +=' "$P")" = 1 ] && [ "$(grep -c 'lock_wait_ns +=' "$U")" = 0 ] \
   && [ "$(grep -c 'lock_wait_ns +=' "$T/ftfn.c")" = 1 ]; then
    ok "pfifo_post_kick() books KICK; lock_wait_ns is added only by pfifo_lock_timed() and its _ft()"
else bad "a lock_wait_ns add outside pfifo_lock_timed(), or post_kick not at KICK"; fi

echo "== static: the lock-free wake (pfifo.c, nv2a.c)"
N="$REPO/hw/xbox/nv2a/nv2a.c"
KICKFN=$(sed -n '/^void pfifo_kick(NV2AState \*d)$/,/^}/p' "$P")
if echo "$KICKFN" | grep -q '^    pfifo_wake(d);$' \
   && ! echo "$KICKFN" | grep -q 'qemu_cond_broadcast'; then
    ok "pfifo_kick() wakes through the block's pfifo_wake()"
else bad "pfifo_kick() does not wake through pfifo_wake()"; fi
if [ "$(grep -c 'qemu_event_wait(&d->pfifo.wake)' "$P")" = 1 ] \
   && [ "$(grep -c 'qemu_event_wait(&d->pfifo.wake)' "$T/block.c")" = 1 ] \
   && [ "$(grep -c 'qemu_event_reset(&d->pfifo.wake)' "$P")" = 1 ] \
   && [ "$(grep -c 'qemu_event_reset(&d->pfifo.wake)' "$T/block.c")" = 1 ]; then
    ok "the event's one wait and one reset are pfifo_park()'s"
else bad "an event wait or reset outside the block"; fi
EXITFN=$(sed -n '/^static void nv2a_exitfn(/,/^}/p' "$N")
LOCKFN=$(sed -n '/^static void nv2a_lock_fifo(/,/^}/p' "$N")
if grep -q 'qemu_event_init(&d->pfifo.wake, false);' "$N" \
   && echo "$LOCKFN" | grep -q 'qemu_event_set(&d->pfifo.wake);' \
   && echo "$EXITFN" | awk '/qatomic_set\(&d->exiting, true\);/ { e = 1 }
        e && /qemu_event_set\(&d->pfifo.wake\);/ { ok = 1 } END { exit !ok }'; then
    ok "nv2a.c: the event is initialised, and nv2a_lock_fifo() and nv2a_exitfn() (after \`exiting\`) set it"
else bad "nv2a.c does not init the event, or a waker there does not set it"; fi

echo "== falsifier F1: the block without the parked wakeup must lose one"
sed 's/if (qatomic_read(&d->pfifo.parked)) {/if (0) {/' "$T/block.c" > "$T/block_f1.c"
if cmp -s "$T/block.c" "$T/block_f1.c"; then bad "F1 mutation did not apply"; fi
build "$U" "$T/block_f1.c" f1
for m in on wake; do
    OUT=$(run f1 $m)
    echo "$OUT" | grep '^WAKEUP' | sed "s/^/    $m: /"
    if echo "$OUT" | grep -q '^WAKEUP FAIL .*lost_at=[1-9]'; then
        ok "F1 ($m) lost a wakeup: check 4 sees the race"
    else bad "F1 ($m) did not lose a wakeup; check 4 cannot discriminate"; fi
done

echo "== falsifier F2: user.c at $BASE (before postput1010) must block on the held lock"
git -C "$REPO" show "$BASE:hw/xbox/nv2a/user.c" > "$T/base_user.c" 2>/dev/null \
    || bad "cannot read $BASE:hw/xbox/nv2a/user.c"
build "$T/base_user.c" "$T/block.c" f2 && OUT=$(run f2 on)
echo "$OUT" | sed 's/^/    /'
if echo "$OUT" | grep -q '^POSTED FAIL ms=[0-9]\{3,\}'; then
    ok "F2 blocked for the holder's hold: check 1 sees the lock"
else bad "F2 did not block; check 1 cannot discriminate"; fi

echo "== falsifier F3: the block without its barriers must lose a round"
sed '/^    smp_mb();$/d' "$T/block.c" > "$T/block_f3.c"
if [ "$(diff "$T/block.c" "$T/block_f3.c" | grep -c '^<')" != 2 ]; then
    bad "F3 mutation did not remove exactly the two barriers"
fi
build "$U" "$T/block_f3.c" f3
for m in on wake; do
    OUT=$(run f3 $m)
    echo "$OUT" | grep '^RACE' | sed "s/^/    $m: /"
    if echo "$OUT" | grep -q '^RACE FAIL .*lost=[1-9]'; then
        ok "F3 ($m) lost rounds: check 5 sees a missing barrier"
    else bad "F3 ($m) lost no round; check 5 cannot discriminate"; fi
done

# F4, F5: one barrier at a time. Each side's barrier is needed on its own.
for f in "F4 pfifo_park pfifo_post_kick" "F5 pfifo_post_kick pfifo_dma_put_may_post"; do
    set -- $f
    echo "== falsifier $1: the block without $2()'s barrier must lose a round"
    awk -v from="$2" -v to="$3" '
        index($0, from "(") && /^(static |bool |void )/ { f = 1 }
        index($0, to "(") && /^(static |bool |void )/ { f = 0 }
        f && /^    smp_mb\(\);$/ { next } { print }' "$T/block.c" > "$T/block_$1.c"
    if [ "$(diff "$T/block.c" "$T/block_$1.c" | grep -c '^<')" != 1 ]; then
        bad "$1 mutation did not remove exactly one barrier"
    fi
    build "$U" "$T/block_$1.c" "$1"
    for m in on wake; do
        OUT=$(run "$1" $m)
        echo "$OUT" | grep '^RACE' | sed "s/^/    $m: /"
        if echo "$OUT" | grep -q '^RACE FAIL .*lost=[1-9]'; then
            ok "$1 ($m) lost rounds: $2()'s barrier is load-bearing"
        else bad "$1 ($m) lost no round"; fi
    done
done

echo "== falsifier F6: user.c booking the DMA_GET store to OTHER must fail check 7"
sed 's/pfifo_lock_timed(d, NV2A_LOCKW_GET);/pfifo_lock_timed(d, NV2A_LOCKW_OTHER);/' "$U" > "$T/user_f6.c"
if cmp -s "$U" "$T/user_f6.c"; then bad "F6 mutation did not apply"; fi
build "$T/user_f6.c" "$T/block.c" f6 && OUT=$(run f6 off)
echo "$OUT" | grep '^SITES' | sed 's/^/    /'
if echo "$OUT" | grep -q '^SITES FAIL'; then ok "F6 failed check 7: the register split is checked"
else bad "F6 passed check 7"; fi

echo "== falsifier F7: pfifo_lock_timed() without its frametrace branch must fail check 7"
sed 's/if (unlikely(qatomic_read(&hakux_ft_on))) {/if (0) {/' "$T/lock_timed.h" > "$T/lock_timed_f7.h"
if cmp -s "$T/lock_timed.h" "$T/lock_timed_f7.h"; then bad "F7 mutation did not apply"; fi
build "$U" "$T/block.c" f7 "$T/lock_timed_f7.h" && OUT=$(run f7 off)
echo "$OUT" | grep '^SITES' | sed 's/^/    /'
if echo "$OUT" | grep -q '^SITES FAIL'; then ok "F7 failed check 7: the branch is load-bearing"
else bad "F7 passed check 7"; fi

echo "== falsifier F8: pfifo_lock_timed_ft() without its lock_wait_ns add must fail check 7"
sed '/w->lock_wait_ns += dt;/d' "$T/ftfn.c" > "$T/ftfn_f8.c"
if cmp -s "$T/ftfn.c" "$T/ftfn_f8.c"; then bad "F8 mutation did not apply"; fi
build "$U" "$T/block.c" f8 "" "$T/ftfn_f8.c" && OUT=$(run f8 off)
echo "$OUT" | grep '^SITES' | sed 's/^/    /'
if echo "$OUT" | grep -q '^SITES FAIL'; then ok "F8 failed check 7: lock_wait_ns stays the sum"
else bad "F8 passed check 7"; fi

echo "== falsifier F9: pfifo_post_kick() booking its wait to PUT must fail check 7 (on)"
sed 's/pfifo_lock_timed(d, NV2A_LOCKW_KICK);/pfifo_lock_timed(d, NV2A_LOCKW_PUT);/' "$T/block.c" > "$T/block_f9.c"
if cmp -s "$T/block.c" "$T/block_f9.c"; then bad "F9 mutation did not apply"; fi
build "$U" "$T/block_f9.c" f9 && OUT=$(run f9 on)
echo "$OUT" | grep '^SITES' | sed 's/^/    /'
if echo "$OUT" | grep -q '^SITES FAIL'; then ok "F9 failed check 7: the posted store's wake is told from the locked store"
else bad "F9 passed check 7"; fi

echo "== falsifier F10: pfifo_park() without the event reset must fail check 9 (wake)"
sed '/^        qemu_event_reset(&d->pfifo.wake);$/d' "$T/block.c" > "$T/block_f10.c"
if [ "$(diff "$T/block.c" "$T/block_f10.c" | grep -c '^<')" != 1 ]; then bad "F10 mutation did not apply"; fi
build "$U" "$T/block_f10.c" f10 && OUT=$(run f10 wake)
echo "$OUT" | grep '^IDLE' | sed 's/^/    /'
if echo "$OUT" | grep -q '^IDLE FAIL'; then ok "F10 failed check 9: the reset is what lets the idle thread sleep"
else bad "F10 passed check 9"; fi

echo "== falsifier F11: the reset after the condition check must lose a round (wake)"
awk '/^        qemu_event_reset\(&d->pfifo.wake\);$/ { next }
     /^            qemu_mutex_unlock\(&d->pfifo.lock\);$/ && !done {
         print "            qemu_event_reset(&d->pfifo.wake);"; done = 1 }
     { print }' "$T/block.c" > "$T/block_f11.c"
if [ "$(diff "$T/block.c" "$T/block_f11.c" | grep -c '^[<>]')" != 2 ]; then bad "F11 mutation did not apply"; fi
build "$U" "$T/block_f11.c" f11 && OUT=$(run f11 wake)
echo "$OUT" | grep '^RACE' | sed 's/^/    /'
if echo "$OUT" | grep -q '^RACE FAIL .*lost=[1-9]'; then ok "F11 lost rounds: the reset must come before the check"
else bad "F11 lost no round"; fi

echo "== falsifier F12: pfifo_wake() without its event set must lose a wakeup (wake)"
awk '/^static void pfifo_wake\(/ { f = 1 } f && /^}/ { f = 0 }
     f && /qemu_event_set\(&d->pfifo.wake\);/ { next } { print }' "$T/block.c" > "$T/block_f12.c"
if [ "$(diff "$T/block.c" "$T/block_f12.c" | grep -c '^<')" != 1 ]; then bad "F12 mutation did not apply"; fi
build "$U" "$T/block_f12.c" f12 && OUT=$(run f12 wake)
echo "$OUT" | grep '^WAKEUP' | sed 's/^/    /'
if echo "$OUT" | grep -q '^WAKEUP FAIL .*lost_at=[1-9]'; then ok "F12 lost a wakeup: the locked kickers must set the event"
else bad "F12 lost no wakeup"; fi

echo "== falsifier F13: pfifo_park() without the exiting predicate must hang on exit (wake)"
sed 's/} else if (!qatomic_read(&d->exiting)) {/} else if (1) {/' "$T/block.c" > "$T/block_f13.c"
if cmp -s "$T/block.c" "$T/block_f13.c"; then bad "F13 mutation did not apply"; fi
build "$U" "$T/block_f13.c" f13 && OUT=$(run f13 wake)
echo "$OUT" | grep '^EXIT' | sed 's/^/    /'
if echo "$OUT" | grep -q '^EXIT FAIL .*hung_at=[1-9]'; then ok "F13 hung: the exit needs the predicate, not only the set"
else bad "F13 did not hang; check 10 cannot discriminate"; fi

echo "== falsifier F14: pfifo_post_kick() without its lock-free branch must fail check 8 (wake)"
awk '/^static void pfifo_post_kick\(/ { f = 1 } f && /^}/ { f = 0 }
     f && /if \(pfifo_lockfree_wake_on\(\)\) \{/ { sub(/if \(pfifo_lockfree_wake_on\(\)\) \{/, "if (0) {") }
     { print }' "$T/block.c" > "$T/block_f14.c"
if [ "$(diff "$T/block.c" "$T/block_f14.c" | grep -c '^<')" != 1 ]; then bad "F14 mutation did not apply"; fi
build "$U" "$T/block_f14.c" f14 && OUT=$(run f14 wake)
echo "$OUT" | grep '^LOCKFREE' | sed 's/^/    /'
if echo "$OUT" | grep -q '^LOCKFREE FAIL'; then ok "F14 failed check 8: the lock-free branch is what skips the lock"
else bad "F14 passed check 8"; fi

echo "== $([ $fail -eq 0 ] && echo PASS || echo "FAIL ($fail)")"
exit $((fail > 0))
