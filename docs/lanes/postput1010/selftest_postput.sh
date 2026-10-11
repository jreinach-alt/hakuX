#!/usr/bin/env bash
# selftest_postput.sh -- the posted DMA_PUT store behind HAKUX_POSTED_PUT=1
# (#433), on the real source. Ported from docs/lanes/vcpusleep's (c2dfca18a1).
#
# Compiles hw/xbox/nv2a/user.c verbatim, and the `posted-put` block of
# hw/xbox/nv2a/pfifo.c verbatim (cut between its BEGIN/END markers), against a
# stub nv2a_int.h with the real include/qemu/atomic.h and nv2a_regs.h,
# -Wall -Werror, and runs the harness twice: with HAKUX_POSTED_PUT=1 (on) and
# without it (off). The switch is read once per process, as in the build.
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
#      no plain kick store outside the switch-off branch; user.c keeps
#      master's timed lock on the path that does not post.
#
# Falsifiers (each must FAIL a check, or the check means nothing):
#   F1. the block with the parked wakeup removed (`if (0)`): check 4 must
#       report a lost wakeup;
#   F2. user.c at BASE (before the change): check 1 (on) must block for the
#       hold;
#   F3. the block with both smp_mb() removed: check 5 must count lost rounds.
#       The host is x86-64, whose only reordering is a store passing a later
#       load -- exactly the one the barriers forbid -- so this is the mutant
#       the host can show.
#   F4, F5. the same with only pfifo_park()'s, then only pfifo_post_kick()'s
#       barrier removed: check 5 must count lost rounds for each.
#
# What it cannot show: the DMA_PUT re-check in pfifo_park() covers a third
# kick writer under the C11 model (see the block's comment). Neither x86-64
# nor ARMv8 can produce that case, so no host run can fail without it.
#
# Usage: bash docs/lanes/postput1010/selftest_postput.sh   (from the repo root)
# Exit 0 when every check passes and every falsifier fails as it must.
set -u
REPO=$(git rev-parse --show-toplevel) || exit 2
BASE=${BASE:-b74cff74ed}          # master the lane branched from
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
typedef struct NV2AState {
    struct {
        QemuMutex lock; QemuCond fifo_cond; uint32_t regs[0x2000];
        bool fifo_kick; bool parked; uint32_t put_seen; int64_t posted_ts;
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
#include <unistd.h>
__typeof__(g_nv2a_stats) g_nv2a_stats;
int64_t stub_widen_ns;
int stub_litmus, stub_waited, stub_round, stub_posted_round;
uint32_t stub_broadcasts;

/* What pfifo.c's posted-put block needs from the rest of pfifo.c. */
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
static void spin_ns(int64_t ns) { int64_t until = now() + ns; while (now() < until) { } }
static void wake_for_exit(void)
{
    pthread_mutex_lock(&s.pfifo.lock);
    qatomic_set(&s.pfifo.fifo_kick, true);
    pthread_cond_broadcast(&s.pfifo.fifo_cond);
    pthread_mutex_unlock(&s.pfifo.lock);
}

/* Check 4's PFIFO thread: pfifo_thread()'s loop, less the work. */
static uint32_t consumed;
static int stop;
static void *pfifo_sim(void *arg)
{
    unsigned seed = 1;
    pthread_mutex_lock(&s.pfifo.lock);
    while (!qatomic_read(&stop)) {
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
        if (!qatomic_read(&s.pfifo.fifo_kick)) {
            qatomic_set(&s.pfifo.fifo_kick, true);
            qemu_cond_broadcast(&s.pfifo.fifo_cond);
        }
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

int main(int argc, char **argv)
{
    int on = argc > 1 && !strcmp(argv[1], "on");
    int bad = 0;
    if (on) setenv("HAKUX_POSTED_PUT", "1", 1); else unsetenv("HAKUX_POSTED_PUT");
    pthread_mutex_init(&s.pfifo.lock, NULL);
    pthread_cond_init(&s.pfifo.fifo_cond, NULL);
    s.pfifo.regs[NV_PFIFO_MODE] = 1;                     /* channel 0: DMA mode */
    s.pfifo.regs[NV_PFIFO_CACHE1_PUSH1] = 0;             /* CHID 0 */
    printf("SWITCH %s\n", pfifo_posted_put_on() ? "on" : "off");
    bad += pfifo_posted_put_on() != on;

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
    {   /* 4. no lost wakeup, end to end */
        stub_widen_ns = 20000;
        s.pfifo.fifo_kick = false;
        qatomic_set(&consumed, 0x1100);
        s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT] = 0x1100;
        pthread_t p, k;
        pthread_create(&p, NULL, pfifo_sim, NULL);
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
            if (w && qatomic_read(&stub_broadcasts) == b0) {
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
    return bad ? 1 : 0;
}
EOF

block() {   # <pfifo.c path> -> the posted-put block on stdout
    sed -n '/^\/\* BEGIN posted-put/,/^\/\* END posted-put \*\//p' "$1"
}

build() {   # <user.c path> <block file> <tag>
    mkdir -p "$T/$3"
    cp "$1" "$T/$3/user.c"
    cp "$2" "$T/$3/postput_block.c"
    cp "$T/nv2a_int.h" "$T/$3/nv2a_int.h"
    if ! gcc -std=gnu11 -O2 -Wall -Werror -pthread -I"$T/$3" -I"$REPO/include" -I"$REPO" \
            -o "$T/$3/h" "$T/$3/user.c" "$T/harness.c" 2> "$T/$3/cc.log"; then
        echo "COMPILE_FAIL"; sed 's/^/    /' "$T/$3/cc.log" | head -20; return 3
    fi
}

run() {     # <tag> on|off
    "$T/$1/h" "$2"
}

block "$REPO/hw/xbox/nv2a/pfifo.c" > "$T/block.c"
if ! grep -q 'pfifo_park' "$T/block.c"; then
    bad "no posted-put block in pfifo.c"; echo "== FAIL ($fail)"; exit 1
fi

build "$REPO/hw/xbox/nv2a/user.c" "$T/block.c" fix || { bad "the fix does not compile"; echo "== FAIL ($fail)"; exit 1; }
for sw in on off; do
    echo "== user.c and pfifo.c's posted-put block at the working tree, switch $sw"
    OUT=$(run fix $sw); RC=$?
    echo "$OUT" | sed 's/^/    /'
    if [ $RC -eq 0 ]; then
        if [ $sw = on ]; then ok "on: posted under a held lock, locked when free, locked under the bound, no lost wakeup, no lost round"
        else ok "off: locked under a held lock, as master; nothing posted; no lost wakeup"; fi
    else bad "switch $sw (rc $RC)"; fi
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
if grep -A3 '^    } else {$' "$U" | grep -q 'int64_t lock_t0 = qemu_clock_get_ns(QEMU_CLOCK_REALTIME);' \
   && grep -q 'qemu_mutex_trylock(&d->pfifo.lock) != 0' "$U"; then
    ok "user.c: master's timed lock on the path that does not post; trylock only where it may"
else bad "user.c lost master's timed lock"; fi

echo "== falsifier F1: the block without the parked wakeup must lose one"
sed 's/if (qatomic_read(&d->pfifo.parked)) {/if (0) {/' "$T/block.c" > "$T/block_f1.c"
if cmp -s "$T/block.c" "$T/block_f1.c"; then bad "F1 mutation did not apply"; fi
build "$U" "$T/block_f1.c" f1 && OUT=$(run f1 on)
echo "$OUT" | sed 's/^/    /'
if echo "$OUT" | grep -q '^WAKEUP FAIL .*lost_at=[1-9]'; then
    ok "F1 lost a wakeup: check 4 sees the race"
else bad "F1 did not lose a wakeup; check 4 cannot discriminate"; fi

echo "== falsifier F2: user.c at $BASE (before the change) must block on the held lock"
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
build "$U" "$T/block_f3.c" f3 && OUT=$(run f3 on)
echo "$OUT" | sed 's/^/    /'
if echo "$OUT" | grep -q '^RACE FAIL .*lost=[1-9]'; then
    ok "F3 lost rounds: check 5 sees a missing barrier"
else bad "F3 lost no round; check 5 cannot discriminate"; fi

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
    build "$U" "$T/block_$1.c" "$1" && OUT=$(run "$1" on)
    echo "$OUT" | grep '^RACE' | sed 's/^/    /'
    if echo "$OUT" | grep -q '^RACE FAIL .*lost=[1-9]'; then
        ok "$1 lost rounds: $2()'s barrier is load-bearing"
    else bad "$1 lost no round"; fi
done

echo "== $([ $fail -eq 0 ] && echo PASS || echo "FAIL ($fail)")"
exit $((fail > 0))
