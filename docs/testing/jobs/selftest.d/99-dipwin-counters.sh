# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, ok/bad/check. Not executable, no shebang, no exit.
#
# The perflog [dipwin] line (vk/draw.c, #1049) is citable only if its counters
# lose nothing and count nothing twice. The g_opt_stats window it replaced did
# both: plain ++ from the PFIFO and render threads, a memset from whichever
# reached the 60th finish, and a "60-frame" window that was 30 to 60 flips
# depending on how many presenting finishes landed in it. This pins:
#
#   1. vk/dipwin.h: four writers add while a reader takes windows; the
#      windows sum to exactly the adds, and the caller-address table puts no
#      address in two slots. A plain += writer, or a reader that reads and
#      then stores zero, loses adds and fails (built -O0 so the compiler cannot
#      fold the loop away and hide the race).
#   2. vk/draw.c: dipwin_flip() is called from one place, the FLIP_STALL-only
#      branch of pgraph_vk_finish(), which also closes the old window; and
#      dw_c[] is written only through dipwin_add/dipwin_take.

echo "== vk/dipwin.h counters and the [dipwin] window's one emitter"
DW="$T/dipwin"
rm -rf "$DW"; mkdir -p "$DW/real" "$DW/add" "$DW/take"
HDR="$REPO/hw/xbox/nv2a/pgraph/vk/dipwin.h"
DRAW="$REPO/hw/xbox/nv2a/pgraph/vk/draw.c"

cat > "$DW/dipwin_test.c" <<'C'
#include <pthread.h>
#include <stdio.h>
#include <dipwin.h>

#define WRITERS 4
#define ADDS 2000000
#define PCS 8

static uint64_t counter;
static DipwinPc pcs;
static int done;

static void *writer(void *arg)
{
    uintptr_t id = (uintptr_t)arg;
    for (int i = 0; i < ADDS; i++) {
        dipwin_add(&counter, 1);
        if ((i & 63) == 0) {
            dipwin_pc_note(&pcs, 0x1000 + (((i >> 6) + id) % PCS) * 0x10);
        }
    }
    __atomic_fetch_add(&done, 1, __ATOMIC_RELEASE);
    return NULL;
}

static uint64_t take_pcs(void)
{
    uint64_t n = 0;
    for (int i = 0; i < DIPWIN_PC_SLOTS; i++) {
        uintptr_t pc;
        n += dipwin_pc_take(&pcs, i, &pc);
    }
    return n;
}

int main(void)
{
    pthread_t t[WRITERS];
    for (uintptr_t i = 0; i < WRITERS; i++) {
        pthread_create(&t[i], NULL, writer, (void *)i);
    }
    uint64_t total = 0, pc_total = 0, windows = 0, busy = 0;
    while (__atomic_load_n(&done, __ATOMIC_ACQUIRE) < WRITERS) {
        uint64_t w = dipwin_take(&counter);
        total += w;
        busy += w != 0;
        pc_total += take_pcs();
        windows++;
    }
    for (int i = 0; i < WRITERS; i++) {
        pthread_join(t[i], NULL);
    }
    total += dipwin_take(&counter);
    pc_total += take_pcs();

    uint64_t want = (uint64_t)WRITERS * ADDS;
    uint64_t pc_want = (uint64_t)WRITERS * ((ADDS + 63) / 64);
    int dup = 0, used = 0;
    for (int i = 0; i < DIPWIN_PC_SLOTS - 1; i++) {
        used += pcs.pc[i] != 0;
        for (int j = i + 1; j < DIPWIN_PC_SLOTS - 1; j++) {
            dup += pcs.pc[i] && pcs.pc[i] == pcs.pc[j];
        }
    }
    printf("windows=%llu busy=%llu total=%llu want=%llu pc=%llu/%llu "
           "slots=%d dup=%d\n", (unsigned long long)windows,
           (unsigned long long)busy, (unsigned long long)total,
           (unsigned long long)want, (unsigned long long)pc_total,
           (unsigned long long)pc_want, used, dup);
    /* busy: the reader took non-empty windows while writers ran, so the
     * race was exercised rather than run after the fact */
    return total == want && pc_total == pc_want && used == PCS && !dup &&
           busy >= 2 ? 0 : 1;
}
C

cp "$HDR" "$DW/real/dipwin.h"
sed 's/__atomic_fetch_add(c, n, __ATOMIC_RELAXED);/*c += n;/' "$HDR" > "$DW/add/dipwin.h"
sed 's/return __atomic_exchange_n(c, 0, __ATOMIC_RELAXED);/uint64_t v_ = *c; *c = 0; return v_;/' \
    "$HDR" > "$DW/take/dipwin.h"
for v in real add take; do
    cc -O0 -pthread -I"$DW/$v" "$DW/dipwin_test.c" -o "$DW/test-$v" 2> "$DW/cc-$v.log"
done
dw_run() { "$DW/test-$1" > "$DW/run-$1.log" 2>&1; }
check "dipwin_test builds against vk/dipwin.h" test -x "$DW/test-real"
check "four writers and a taking reader: windows sum to every add, no address in two slots" dw_run real
if [ -s "$DW/run-real.log" ]; then echo "       $(head -c 300 "$DW/run-real.log")"; fi

# The draw.c rules, as a script so a mutant can be run through it.
cat > "$DW/draw_rules.py" <<'PY'
import re, sys
lines = open(sys.argv[1]).read().split("\n")
calls = [i for i, l in enumerate(lines) if re.search(r"\bdipwin_flip\(\);", l)]
if len(calls) != 1:
    sys.exit("dipwin_flip() is called from %d places" % len(calls))
i = calls[0]
while i >= 0 and not re.match(r"\s*if \(", lines[i]):
    i -= 1
if i < 0 or not re.fullmatch(r"\s*if \(finish_reason == VK_FINISH_REASON_FLIP_STALL\) \{", lines[i]):
    sys.exit("dipwin_flip() is not in the FLIP_STALL-only branch: %r" % (lines[i] if i >= 0 else None))
if not any("opt_stats_log_and_reset();" in l for l in lines[i:calls[0]]):
    sys.exit("the FLIP_STALL-only branch does not close the old window")
for n, l in enumerate(lines, 1):
    if "dw_c[" in l and not re.search(r"static uint64_t dw_c\[DW__N\];|dipwin_(add|take)\(&dw_c\[", l):
        sys.exit("line %d writes dw_c[] outside dipwin_add/dipwin_take: %s" % (n, l.strip()))
PY
dw_rules() { python3 "$DW/draw_rules.py" "$1"; }
check "draw.c: one dipwin_flip() call, in the FLIP_STALL-only branch with the old window's close" dw_rules "$DRAW"

# ------------------------------------------------------------ falsifications
# A mutant counts as caught only if it built, ran to its summary, and its windows
# do not sum to the adds: a mutant that fails to compile must not read as one
# that miscounted. The += writer mostly counts twice (its stale store puts back
# a value the reader already took); the read-then-zero reader loses adds.
dw_miscounts() {
    [ -x "$DW/test-$1" ] || return 1
    ! dw_run "$1" || return 1
    python3 -c 'import re,sys; m=re.search(r"total=(\d+) want=(\d+)", open(sys.argv[1]).read()); sys.exit(0 if m and m[1] != m[2] else 1)' \
        "$DW/run-$1.log"
}
check "falsification ran: the += writer differs from dipwin.h" \
    bash -c '! cmp -s "$1" "$2"' _ "$HDR" "$DW/add/dipwin.h"
check "FALSIFIED: a plain += writer miscounts" dw_miscounts add
check "falsification ran: the read-then-zero reader differs from dipwin.h" \
    bash -c '! cmp -s "$1" "$2"' _ "$HDR" "$DW/take/dipwin.h"
check "FALSIFIED: a reader that reads and then stores zero miscounts" dw_miscounts take

# The window closes on presenting finishes again: two flips' worth of windows per flip.
sed 's/^\( *\)if (finish_reason == VK_FINISH_REASON_FLIP_STALL) {$/\1if (finish_reason == VK_FINISH_REASON_FLIP_STALL || finish_reason == VK_FINISH_REASON_PRESENTING) {/' \
    "$DRAW" > "$DW/draw-present.c"
check "falsification ran: the presenting-window draw.c differs" \
    bash -c '! cmp -s "$1" "$2"' _ "$DRAW" "$DW/draw-present.c"
check "FALSIFIED: a window also closed by the presenting finish fails" bash -c '! python3 "$1" "$2"' \
    _ "$DW/draw_rules.py" "$DW/draw-present.c"
# A second reader: the render pass end takes the window too.
sed 's/^\( *\)DW_INC(BRK);$/\1DW_INC(BRK); dipwin_flip();/' "$DRAW" > "$DW/draw-tworeaders.c"
check "falsification ran: the two-reader draw.c differs" \
    bash -c '! cmp -s "$1" "$2"' _ "$DRAW" "$DW/draw-tworeaders.c"
check "FALSIFIED: a second dipwin_flip() caller fails" bash -c '! python3 "$1" "$2"' \
    _ "$DW/draw_rules.py" "$DW/draw-tworeaders.c"
# The old race: a plain increment on the window's counters.
sed 's/^#define DW_INC(i) dipwin_add(&dw_c\[DW_##i\], 1)$/#define DW_INC(i) (dw_c[DW_##i]++)/' \
    "$DRAW" > "$DW/draw-plainc.c"
check "falsification ran: the plain-increment draw.c differs" \
    bash -c '! cmp -s "$1" "$2"' _ "$DRAW" "$DW/draw-plainc.c"
check "FALSIFIED: a plain dw_c[] increment fails" bash -c '! python3 "$1" "$2"' \
    _ "$DW/draw_rules.py" "$DW/draw-plainc.c"
