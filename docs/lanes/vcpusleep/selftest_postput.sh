#!/usr/bin/env bash
# selftest_postput.sh -- the posted DMA_PUT store (#507), on the real source.
#
# Compiles hw/xbox/nv2a/user.c verbatim, and the `posted-put` block of
# hw/xbox/nv2a/pfifo.c verbatim (cut between its BEGIN/END markers), against a
# stub nv2a_int.h with the real include/qemu/atomic.h and nv2a_regs.h,
# -Wall -Werror, and drives them from a host harness:
#
#   1. POSTED: a DMA_PUT store made while another thread holds pfifo.lock for
#      400 ms (the PFIFO thread in a STALLED finish, as simp1 measured) returns
#      in under 100 ms, stores the value, and sets the kick;
#   2. FREE: with the lock free the store takes the locked path, unchanged
#      (pfifo_kick runs under the lock);
#   3. BOUND: with the skew bound on, the store still waits for the lock;
#   4. NO LOST WAKEUP: a PFIFO-thread stand-in with the real loop shape (clear
#      the kick with xchg, consume DMA_PUT, sometimes work holding the lock,
#      then pfifo_park() unless kicked) and a guest that stores DMA_PUT and
#      waits for it to be consumed, 100,000 times. Every store must be
#      consumed within 1 s, and both the posted and the locked path must run
#      at least 1,000 times, or the check cannot discriminate. The stub's
#      condition wait spins 20 us under the lock before it sleeps, which
#      widens the window between the kick check and the sleep, where a
#      preempted PFIFO thread could sit for as long;
#   5. STATIC: the pusher loads DMA_PUT with acquire, the PFIFO thread clears
#      the kick with xchg, and parks only through pfifo_park().
#
# Falsifiers (each must FAIL a check, or the check means nothing):
#   F1. pfifo.c's block with the parked-wakeup removed (`if (0)`): check 4 must
#       report a lost wakeup;
#   F2. user.c at BASE (before the fix): check 1 must block for the 400 ms.
#
# Usage: bash docs/lanes/vcpusleep/selftest_postput.sh   (from the repo root)
# Exit 0 when every check passes and every falsifier fails as it must.
set -u
REPO=$(git rev-parse --show-toplevel) || exit 2
BASE=${BASE:-425ffe1ad1}          # master the lane branched from
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
ok()  { echo "  ok   $*"; }
bad() { echo "  FAIL $*"; fail=$((fail+1)); }

cat > "$T/nv2a_int.h" <<'EOF'
/* Stub of hw/xbox/nv2a/nv2a_int.h: what user.c and pfifo.c's posted-put
 * block touch. */
#include <assert.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
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
#define qemu_cond_broadcast(c) pthread_cond_broadcast(c)
#define qemu_cond_signal(c) pthread_cond_signal(c)
#define QEMU_CLOCK_REALTIME 0
static inline int64_t qemu_clock_get_ns(int c)
{
    struct timespec ts; (void)c;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000LL + ts.tv_nsec;
}
/* A preempted thread between its kick check and its sleep, still holding
 * the lock: spin `stub_widen_ns` first. */
extern int64_t stub_widen_ns;
static inline void stub_cond_wait(QemuCond *c, QemuMutex *m)
{
    int64_t until = qemu_clock_get_ns(0) + stub_widen_ns;
    while (qemu_clock_get_ns(0) < until) { }
    pthread_cond_wait(c, m);
}
#define qemu_cond_wait(c, m) stub_cond_wait(c, m)
typedef struct NV2AState {
    struct {
        QemuMutex lock; QemuCond fifo_cond; uint32_t regs[0x2000];
        bool fifo_kick; bool parked; int64_t posted_ts;
    } pfifo;
} NV2AState;
extern struct { struct { int64_t lock_wait_ns; uint32_t kick_count; } cpu_working; } g_nv2a_stats;
static inline void nv2a_reg_log_read(int b, hwaddr a, unsigned s, uint64_t v) { (void)b; (void)a; (void)s; (void)v; }
static inline void nv2a_reg_log_write(int b, hwaddr a, unsigned s, uint64_t v) { (void)b; (void)a; (void)s; (void)v; }
void pfifo_kick(NV2AState *d);
bool pfifo_dma_put_may_post(NV2AState *d, unsigned int channel_id);
void pfifo_post_dma_put(NV2AState *d, uint32_t val);
uint64_t user_read(void *opaque, hwaddr addr, unsigned int size);
void user_write(void *opaque, hwaddr addr, uint64_t val, unsigned int size);
EOF

cat > "$T/harness.c" <<'EOF'
#include "nv2a_int.h"
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
__typeof__(g_nv2a_stats) g_nv2a_stats;
int64_t stub_widen_ns;

/* What pfifo.c's posted-put block needs from the rest of pfifo.c. */
#define XEMU_OPT_POSTED_DMA_PUT 1
#define FIFO_SKEW_OFF 0
static int bound_mode;
static int fifo_skew_bound_mode(void) { return bound_mode; }
#define fsk_note_post(d) ((void)(d))
#include "postput_block.c"

/* pfifo_kick's wake, as pfifo.c has it; called under the lock. */
static int locked_kicks;
void pfifo_kick(NV2AState *d)
{
    locked_kicks++;
    if (!qatomic_read(&d->pfifo.fifo_kick)) {
        qatomic_set(&d->pfifo.fifo_kick, true);
        qemu_cond_broadcast(&d->pfifo.fifo_cond);
    }
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

/* Check 4's PFIFO thread: pfifo_thread()'s loop, less the work. */
static uint32_t consumed;
static int stop;
static void *pfifo_sim(void *arg)
{
    unsigned seed = 1;
    pthread_mutex_lock(&s.pfifo.lock);
    while (!qatomic_read(&stop)) {
        qatomic_xchg(&s.pfifo.fifo_kick, false);
        qatomic_store_release(&consumed,
            qatomic_load_acquire(&s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT]));
        if (rand_r(&seed) % 2) {             /* a method or a finish */
            int64_t until = now() + (rand_r(&seed) % 20000);
            while (now() < until) { }
        }
        if (!qatomic_read(&s.pfifo.fifo_kick)) {
            pfifo_park(&s);
        }
    }
    pthread_mutex_unlock(&s.pfifo.lock);
    (void)arg; return NULL;
}

int main(void)
{
    int bad = 0;
    pthread_mutex_init(&s.pfifo.lock, NULL);
    pthread_cond_init(&s.pfifo.fifo_cond, NULL);
    s.pfifo.regs[NV_PFIFO_MODE] = 1;                     /* channel 0: DMA mode */
    s.pfifo.regs[NV_PFIFO_CACHE1_PUSH1] = 0;             /* CHID 0 */

    {   /* 1. posted while the lock is held */
        pthread_t t; hold_lock(&t);
        int k0 = locked_kicks;
        int64_t t0 = now();
        user_write(&s, NV_USER_DMA_PUT, 0x2468, 4);
        int64_t ms = (now() - t0) / 1000000;
        pthread_join(t, NULL);
        int pass = ms < 100 && s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT] == 0x2468 &&
                   s.pfifo.fifo_kick && locked_kicks == k0 &&
                   user_read(&s, NV_USER_DMA_PUT, 4) == 0x2468;
        printf("POSTED %s ms=%lld put=0x%x kick=%d\n", pass ? "ok" : "FAIL", (long long)ms,
               s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT], s.pfifo.fifo_kick);
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
    {   /* 4. no lost wakeup */
        stub_widen_ns = 20000;
        s.pfifo.fifo_kick = false;
        qatomic_set(&consumed, 0x1100);
        s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT] = 0x1100;
        pthread_t p; pthread_create(&p, NULL, pfifo_sim, NULL);
        int n = 100000, lost = 0, i;
        int k0 = locked_kicks;
        unsigned seed = 7;
        for (i = 1; i <= n && !lost; i++) {
            uint32_t v = 0x2000 + 4 * (uint32_t)i;
            if (rand_r(&seed) % 2) {             /* land in every phase of the loop */
                int64_t until = now() + (rand_r(&seed) % 60000);
                while (now() < until) { }
            }
            user_write(&s, NV_USER_DMA_PUT, v, 4);
            int64_t dl = now() + 1000000000LL;
            while (qatomic_load_acquire(&consumed) != v) {
                if (now() > dl) { lost = i; break; }
            }
        }
        int locked = locked_kicks - k0, posted = (i - 1) - locked;
        qatomic_set(&stop, 1);
        pfifo_post_kick(&s);
        if (lost) {
            /* the stand-in is asleep for good: wake it so it can exit */
            pthread_mutex_lock(&s.pfifo.lock);
            pthread_cond_broadcast(&s.pfifo.fifo_cond);
            pthread_mutex_unlock(&s.pfifo.lock);
        }
        pthread_join(p, NULL);
        int pass = !lost && posted >= 1000 && locked >= 1000;
        printf("WAKEUP %s stores=%d posted=%d locked=%d lost_at=%d\n", pass ? "ok" : "FAIL",
               i - 1, posted, locked, lost);
        bad += !pass;
    }
    return bad ? 1 : 0;
}
EOF

block() {   # <pfifo.c path> -> the posted-put block on stdout
    sed -n '/^\/\* BEGIN posted-put/,/^\/\* END posted-put \*\//p' "$1"
}

build_run() {   # <user.c path> <block file> <tag>
    mkdir -p "$T/$3"
    cp "$1" "$T/$3/user.c"
    cp "$2" "$T/$3/postput_block.c"
    cp "$T/nv2a_int.h" "$T/$3/nv2a_int.h"
    if ! gcc -std=gnu11 -O2 -Wall -Werror -pthread -I"$T/$3" -I"$REPO/include" -I"$REPO" \
            -o "$T/$3/h" "$T/$3/user.c" "$T/harness.c" 2> "$T/$3/cc.log"; then
        echo "COMPILE_FAIL"; sed 's/^/    /' "$T/$3/cc.log" | head -20; return 3
    fi
    "$T/$3/h"
}

block "$REPO/hw/xbox/nv2a/pfifo.c" > "$T/block.c"
if ! grep -q 'pfifo_park' "$T/block.c"; then
    bad "no posted-put block in pfifo.c"; echo "== FAIL ($fail)"; exit 1
fi

echo "== user.c and pfifo.c's posted-put block at the working tree (the fix)"
OUT=$(build_run "$REPO/hw/xbox/nv2a/user.c" "$T/block.c" fix); RC=$?
echo "$OUT" | sed 's/^/    /'
if [ $RC -eq 0 ]; then ok "posted under a held lock, locked when free, locked under the bound, no lost wakeup"
else bad "the fix's harness (rc $RC)"; fi

echo "== pfifo.c: pusher acquire, kick xchg, parks only through pfifo_park()"
P="$REPO/hw/xbox/nv2a/pfifo.c"
if grep -q 'dma_put_v = qatomic_load_acquire(dma_put);' "$P" \
   && grep -q 'was_active = qatomic_xchg(&d->pfifo.fifo_kick, false);' "$P" \
   && [ "$(grep -c 'qemu_cond_wait(&d->pfifo.fifo_cond' "$P")" = 1 ] \
   && ! grep -qE 'd->pfifo\.fifo_kick = ' "$P"; then
    ok "acquire load of DMA_PUT; xchg clear; one fifo_cond wait (in pfifo_park); no plain kick store"
else bad "pfifo.c static checks"; fi

echo "== falsifier F1: the block without the parked wakeup must lose one"
sed 's/if (qatomic_read(&d->pfifo.parked)) {/if (0) {/' "$T/block.c" > "$T/block_f1.c"
if cmp -s "$T/block.c" "$T/block_f1.c"; then bad "F1 mutation did not apply"; fi
OUT=$(build_run "$REPO/hw/xbox/nv2a/user.c" "$T/block_f1.c" f1); RC=$?
echo "$OUT" | sed 's/^/    /'
if echo "$OUT" | grep -q '^WAKEUP FAIL .*lost_at=[1-9]'; then
    ok "F1 lost a wakeup: check 4 sees the race"
else bad "F1 did not lose a wakeup; check 4 cannot discriminate"; fi

echo "== falsifier F2: user.c at $BASE (before the fix) must block on the held lock"
git -C "$REPO" show "$BASE:hw/xbox/nv2a/user.c" > "$T/base_user.c" 2>/dev/null \
    || bad "cannot read $BASE:hw/xbox/nv2a/user.c"
OUT=$(build_run "$T/base_user.c" "$T/block.c" f2); RC=$?
echo "$OUT" | sed 's/^/    /'
if echo "$OUT" | grep -q '^POSTED FAIL ms=[0-9]\{3,\}'; then
    ok "F2 blocked for the holder's hold: check 1 sees the lock"
else bad "F2 did not block; check 1 cannot discriminate"; fi

echo "== $([ $fail -eq 0 ] && echo PASS || echo "FAIL ($fail)")"
exit $((fail > 0))
