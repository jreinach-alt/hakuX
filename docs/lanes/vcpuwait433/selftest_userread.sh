#!/usr/bin/env bash
# selftest_userread.sh -- the lock-free user_read (#433), on the real source.
#
# Compiles hw/xbox/nv2a/user.c verbatim (copied next to a stub nv2a_int.h, so
# its quoted include finds the stub) with the real include/qemu/atomic.h and
# nv2a_regs.h, -Wall -Werror, and drives it from a host harness:
#
#   1. user_read of DMA_GET, DMA_PUT and REF returns the stored word in under
#      100 ms while another thread holds pfifo.lock for 400 ms (the PFIFO
#      thread inside a STALLED pgraph_vk_finish, as tron2 measured);
#   2. user_write still takes pfifo.lock: a DMA_PUT store started while the
#      lock is held does not complete until it is released (>= 300 ms);
#   3. a DMA_PUT store is visible to the next user_read on the same thread;
#   4. pfifo_run_pusher publishes DMA_GET with a release store (static).
#
# The falsifier: the same harness on the pre-fix user.c (BASE below, git show)
# must FAIL check 1 by blocking for the holder's 400 ms. If it passes there,
# the harness cannot see the lock and checks 1-2 mean nothing.
#
# Usage: bash docs/lanes/vcpuwait433/selftest_userread.sh   (from the repo root)
# Exit 0 when every check passes and the falsifier fails as it must.
set -u
REPO=$(git rev-parse --show-toplevel) || exit 2
BASE=${BASE:-5661db4f2b}          # master before the fix (lane merge parent)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
ok()  { echo "  ok   $*"; }
bad() { echo "  FAIL $*"; fail=$((fail+1)); }

mkdir -p "$T/stub"
cat > "$T/stub/nv2a_int.h" <<'EOF'
/* Stub of hw/xbox/nv2a/nv2a_int.h: exactly what user.c touches. */
#include <assert.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <time.h>
#include "qemu/compiler.h"
#define qemu_build_assert(test) _Static_assert(test, #test)   /* osdep.h's, statically */
#include "qemu/atomic.h"
typedef uint64_t hwaddr;
static inline int ctz32(uint32_t v) { return v ? __builtin_ctz(v) : 32; }
#include "hw/xbox/nv2a/nv2a_regs.h"
typedef pthread_mutex_t QemuMutex;
#define qemu_mutex_lock(m) pthread_mutex_lock(m)
#define qemu_mutex_unlock(m) pthread_mutex_unlock(m)
#define QEMU_CLOCK_REALTIME 0
static inline int64_t qemu_clock_get_ns(int c)
{
    struct timespec ts; (void)c;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000LL + ts.tv_nsec;
}
typedef struct NV2AState {
    struct { QemuMutex lock; uint32_t regs[0x2000]; } pfifo;
} NV2AState;
extern struct { struct { int64_t lock_wait_ns; uint32_t kick_count; } cpu_working; } g_nv2a_stats;
static inline void nv2a_reg_log_read(int b, hwaddr a, unsigned s, uint64_t v) { (void)b; (void)a; (void)s; (void)v; }
static inline void nv2a_reg_log_write(int b, hwaddr a, unsigned s, uint64_t v) { (void)b; (void)a; (void)s; (void)v; }
void pfifo_kick(NV2AState *d);
uint64_t user_read(void *opaque, hwaddr addr, unsigned int size);
void user_write(void *opaque, hwaddr addr, uint64_t val, unsigned int size);
EOF

cat > "$T/harness.c" <<'EOF'
#include "nv2a_int.h"
#include <stdio.h>
#include <unistd.h>
__typeof__(g_nv2a_stats) g_nv2a_stats;
static int kicks;
void pfifo_kick(NV2AState *d) { (void)d; kicks++; }

static NV2AState s;
static volatile int held;
static void *holder(void *arg)
{
    pthread_mutex_lock(&s.pfifo.lock);
    held = 1;
    usleep(400 * 1000);            /* a STALLED finish, ~GPU batch */
    pthread_mutex_unlock(&s.pfifo.lock);
    (void)arg; return NULL;
}
static int64_t now(void) { return qemu_clock_get_ns(0); }
static void hold_lock(pthread_t *t) { held = 0; pthread_create(t, NULL, holder, NULL); while (!held) usleep(100); }

static void *writer(void *arg) { user_write(&s, NV_USER_DMA_PUT, 0x2468, 4); (void)arg; return NULL; }

int main(void)
{
    int bad = 0;
    pthread_mutex_init(&s.pfifo.lock, NULL);
    s.pfifo.regs[NV_PFIFO_MODE] = 1;                     /* channel 0: DMA mode */
    s.pfifo.regs[NV_PFIFO_CACHE1_PUSH1] = 0;             /* CHID 0 */
    s.pfifo.regs[NV_PFIFO_CACHE1_DMA_GET] = 0x1234;
    s.pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT] = 0x1234;
    s.pfifo.regs[NV_PFIFO_CACHE1_REF] = 0xabcd;

    struct { hwaddr a; uint32_t want; const char *n; } rd[] = {
        { NV_USER_DMA_GET, 0x1234, "DMA_GET" },
        { NV_USER_DMA_PUT, 0x1234, "DMA_PUT" },
        { NV_USER_REF,     0xabcd, "REF" },
    };
    for (unsigned i = 0; i < 3; i++) {
        pthread_t t; hold_lock(&t);
        int64_t t0 = now();
        uint64_t r = user_read(&s, rd[i].a, 4);
        int64_t ms = (now() - t0) / 1000000;
        pthread_join(t, NULL);
        int pass = r == rd[i].want && ms < 100;
        printf("READ %s %s value=0x%llx ms=%lld\n", pass ? "ok" : "FAIL", rd[i].n,
               (unsigned long long)r, (long long)ms);
        bad += !pass;
    }

    {   /* user_write must still serialize with the pusher */
        pthread_t t, w; hold_lock(&t);
        int64_t t0 = now();
        pthread_create(&w, NULL, writer, NULL);
        pthread_join(w, NULL);
        int64_t ms = (now() - t0) / 1000000;
        pthread_join(t, NULL);
        int pass = ms >= 300 && kicks == 1;
        printf("WRITE_LOCKED %s ms=%lld kicks=%d\n", pass ? "ok" : "FAIL", (long long)ms, kicks);
        bad += !pass;
    }
    {
        uint64_t r = user_read(&s, NV_USER_DMA_PUT, 4);
        int pass = r == 0x2468;
        printf("PUT_VISIBLE %s value=0x%llx\n", pass ? "ok" : "FAIL", (unsigned long long)r);
        bad += !pass;
    }
    return bad ? 1 : 0;
}
EOF

build_run() {   # <user.c source path> <tag> -> prints the harness output; rc = harness rc
    mkdir -p "$T/$2"
    cp "$1" "$T/$2/user.c"
    cp "$T/stub/nv2a_int.h" "$T/$2/nv2a_int.h"
    if ! gcc -std=gnu11 -O2 -Wall -Werror -pthread -I"$REPO/include" -I"$REPO" \
            -o "$T/$2/h" "$T/$2/user.c" "$T/harness.c" -I"$T/$2" 2> "$T/$2/cc.log"; then
        echo "COMPILE_FAIL"; sed 's/^/    /' "$T/$2/cc.log" | head -20; return 3
    fi
    "$T/$2/h"
}

echo "== user.c at the working tree (the fix)"
OUT=$(build_run "$REPO/hw/xbox/nv2a/user.c" fix); RC=$?
echo "$OUT" | sed 's/^/    /'
if [ $RC -eq 0 ]; then ok "compiles -Wall -Werror; reads do not wait on pfifo.lock; writes still do"
else bad "the fix's harness (rc $RC)"; fi

echo "== pfifo.c: the pusher publishes DMA_GET with a release store"
if grep -q 'qatomic_store_release(dma_get, dma_get_v);' "$REPO/hw/xbox/nv2a/pfifo.c" \
   && ! grep -qE '^\s*\*dma_get = ' "$REPO/hw/xbox/nv2a/pfifo.c"; then
    ok "pfifo_run_pusher: qatomic_store_release(dma_get, ...) and no plain *dma_get store"
else bad "pfifo.c GET store is not a release store"; fi

echo "== falsifier: user.c at $BASE (pre-fix) must block on the held lock"
git -C "$REPO" show "$BASE:hw/xbox/nv2a/user.c" > "$T/base_user.c" 2>/dev/null \
    || { bad "cannot read $BASE:hw/xbox/nv2a/user.c"; }
OUT=$(build_run "$T/base_user.c" base); RC=$?
echo "$OUT" | sed 's/^/    /'
if echo "$OUT" | grep -q '^READ FAIL DMA_GET .*ms=[0-9]\{3,\}'; then
    ok "pre-fix read blocked for the holder's hold: the harness sees the lock"
else bad "pre-fix read did not block; the harness cannot discriminate"; fi

echo "== $([ $fail -eq 0 ] && echo PASS || echo "FAIL ($fail)")"
exit $((fail > 0))
