/* Standalone behaviour test for pmc_read's register table (#188, #190).
 *
 * Two issues, one instrument, deliberately: both are claims about what the
 * same switch statement returns, measured by the same read-only silicon
 * survey, and #190's region starts four bytes after #188's register. A second
 * script extracting the same function would drift from this one and the two
 * would disagree about a shared switch without anybody noticing. The file
 * keeps its #188 name so pmc188's committed mutant suite still drives it.
 *
 * An agent worktree cannot build the native side, so pmc_read is extracted
 * VERBATIM from hw/xbox/nv2a/pmc.c by pmc_enable_selftest.sh (which produces
 * pmc_read_extract.c) and exercised against stubs. Same approach as
 * audio_starve_selftest.c and glerr_report_selftest.c.
 *
 * The register constants are NOT restated here: the real
 * hw/xbox/nv2a/nv2a_regs.h is included, so a test asserting "0x200 reads
 * 0x01110000" is asserting it about the offset the header actually defines,
 * and would fail if NV_PMC_ENABLE moved.
 *
 * pmc_write and pmc_reset are extracted the same way (#188's storage), so
 * the NV_PMC_ENABLE checks run the real write and the real reset value.
 *
 * What this does NOT check: that pmc.c compiles in tree, the reset wiring in
 * nv2a.c or the savestate subsection, writes anywhere but NV_PMC_ENABLE and
 * the two INTR registers, and anything about the __ANDROID__ logging blocks,
 * which are not compiled here and do not alter the returned value on any
 * path.
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* --- stubs for what pmc_read, pmc_write and pmc_reset touch --- */

typedef uint64_t hwaddr;

#include "nv2a_regs.h"

typedef struct NV2AState {
    struct {
        uint32_t pending_interrupts;
        uint32_t enabled_interrupts;
        uint32_t enable;
    } pmc;
} NV2AState;

/* Recorded rather than discarded: the log call is the only side effect
 * pmc_read has, and a case that returned the right value while logging a
 * different one would be a real defect in the trace. */
static struct {
    int calls;
    int block;
    hwaddr addr;
    unsigned int size;
    uint64_t val;
} g_log;

static void nv2a_reg_log_read(int block, hwaddr addr, unsigned int size,
                              uint64_t val)
{
    g_log.calls++;
    g_log.block = block;
    g_log.addr = addr;
    g_log.size = size;
    g_log.val = val;
}

/* The write side's two calls. Counted, because "a write to NV_PMC_ENABLE
 * has no effect but the stored word" includes raising no interrupt. Anything
 * else pmc_write might call -- an engine reset on a bit, say -- has no stub
 * here and fails to compile, which is the loudest form of that check. */
static int g_update_irq_calls;
static int g_log_write_calls;

static void nv2a_update_irq(NV2AState *d)
{
    (void)d;
    g_update_irq_calls++;
}

static void nv2a_reg_log_write(int block, hwaddr addr, unsigned int size,
                               uint64_t val)
{
    (void)block; (void)addr; (void)size; (void)val;
    g_log_write_calls++;
}

#include "pmc_read_extract.c"
#include "pmc_write_extract.c"
#include "pmc_reset_extract.c"

/* --- the checks --- */

static int checks, failures;

/* Returns 1 on agreement. `size` is a parameter rather than a hardcoded 4
 * because #190's alignment narrowing is only expressible at sub-dword width:
 * see the 0x204/0x205 pair at the bottom of main(). Every other call passes
 * 4, which is the only width the silicon survey used. */
static int read_is(const char *what, hwaddr addr, unsigned int size,
                   uint64_t want, NV2AState *d, int quiet)
{
    memset(&g_log, 0, sizeof(g_log));
    uint64_t got = pmc_read(d, addr, size);
    if (got != want) {
        if (!quiet) {
            printf("FAIL %-28s addr=0x%03x got=0x%08llx want=0x%08llx\n", what,
                   (unsigned)addr, (unsigned long long)got,
                   (unsigned long long)want);
        }
        return 0;
    }
    /* The traced value must be the returned one, at the read's own offset and
     * the read's own width. g_log.block is captured but NOT asserted, and
     * deliberately: NV_PMC lives in nv2a_int.h, which this stub set does not
     * include (it would drag in the QEMU headers this whole approach exists to
     * avoid). So a case logging the read under the wrong block is outside what
     * this check can see -- audit pass 1, L3. */
    if (g_log.calls != 1 || g_log.val != want || g_log.addr != addr
        || g_log.size != size) {
        if (!quiet) {
            printf("FAIL %-28s addr=0x%03x value 0x%08llx is right but the "
                   "trace is wrong: calls=%d logged addr=0x%03x size=%u "
                   "val=0x%08llx\n", what, (unsigned)addr,
                   (unsigned long long)got, g_log.calls, (unsigned)g_log.addr,
                   g_log.size, (unsigned long long)g_log.val);
        }
        return 0;
    }
    return 1;
}

static void expect_read_sz(const char *what, hwaddr addr, unsigned int size,
                           uint64_t want, NV2AState *d)
{
    checks++;
    if (!read_is(what, addr, size, want, d, 0)) {
        failures++;
        return;
    }
    printf("ok   %-28s addr=0x%03x/%u -> 0x%08llx\n", what, (unsigned)addr,
           size, (unsigned long long)want);
}

/* Every dword-aligned offset in [lo, hi] must read `want`. One check, not
 * one per offset: 63 ok lines would bury the fifteen that carry information.
 * The failure path names the offending offsets, so a partial region -- an
 * off-by-one at either end, or a case that lost its range -- is diagnosable
 * from the output without rerunning anything. */
static void expect_region(const char *what, hwaddr lo, hwaddr hi,
                          uint64_t want, NV2AState *d)
{
    unsigned n = 0, bad = 0;
    hwaddr first_bad = 0, last_bad = 0;

    checks++;
    for (hwaddr a = lo; a <= hi; a += 4) {
        n++;
        if (!read_is(what, a, 4, want, d, 1)) {
            if (!bad) {
                first_bad = a;
            }
            last_bad = a;
            bad++;
        }
    }
    if (bad) {
        failures++;
        printf("FAIL %-28s 0x%03x-0x%03x: %u of %u dwords wrong "
               "(first 0x%03x, last 0x%03x), want 0x%08llx\n", what,
               (unsigned)lo, (unsigned)hi, bad, n, (unsigned)first_bad,
               (unsigned)last_bad, (unsigned long long)want);
        /* Re-run the first offender loudly: the aggregate line above says
         * how many and where, this says whether it was the value or the
         * trace. */
        (void)read_is(what, first_bad, 4, want, d, 0);
        return;
    }
    printf("ok   %-28s 0x%03x-0x%03x, %u dwords -> 0x%08llx\n", what,
           (unsigned)lo, (unsigned)hi, n, (unsigned long long)want);
}

static void expect_read(const char *what, hwaddr addr, uint64_t want,
                        NV2AState *d)
{
    expect_read_sz(what, addr, 4, want, d);
}

/* Write `val` to NV_PMC_ENABLE, then require that it reads back `want` AND
 * that nothing else moved: every other field of the state byte-identical,
 * no interrupt update, one trace line. That is #188's "gate nothing" -- the
 * bit->engine map is unmeasured, so a write may change the stored word and
 * must change nothing else. */
static void expect_enable_write(const char *what, uint32_t val, uint64_t want,
                                NV2AState *d)
{
    NV2AState before = *d;
    g_update_irq_calls = 0;
    g_log_write_calls = 0;
    pmc_write(d, NV_PMC_ENABLE, val, 4);

    NV2AState after = *d;
    before.pmc.enable = after.pmc.enable = 0;
    checks++;
    if (memcmp(&before, &after, sizeof(before)) != 0 || g_update_irq_calls
        || g_log_write_calls != 1) {
        failures++;
        printf("FAIL %-28s write 0x%08x had a side effect: other state %s, "
               "update_irq x%d, log_write x%d\n", what, val,
               memcmp(&before, &after, sizeof(before)) ? "CHANGED" : "same",
               g_update_irq_calls, g_log_write_calls);
        return;
    }
    printf("ok   %-28s write 0x%08x, no side effect\n", what, val);
    expect_read(what, NV_PMC_ENABLE, want, d);
}

int main(void)
{
    NV2AState d;
    memset(&d, 0, sizeof(d));
    pmc_reset(&d);

    /* THE FALSIFIER (#188), now of pmc_reset: the reset value is what a
     * guest reads before it writes anything. Two independent read-only sweeps of real NV2A
     * silicon, with a reboot between them, read 0x01110000 at PMC+0x200,
     * 1,024/1,024 dwords reproducible. Both sweeps were the console idle out
     * of the dashboard, so that is repeatability in one state and not
     * state-independence; nobody has read this register on a machine that is
     * rendering. Before this lane pmc_read had no case for it and fell
     * through to `default: r = 0`, so this line printed got=0x00000000
     * want=0x01110000.
     *
     * The endian rival is already dead, and it is recorded here because the
     * coincidence is arresting enough to stop the next reader: 0x01110000
     * byte-swapped is 0x00001101, i.e. bits 0, 8 and 12 -- the header's
     * _PFIFO/_PGRAPH pair -- and this same probe campaign has already
     * retracted one bit-position claim as an endian artefact. It does not
     * apply to this value. The endian switch is NV_PMC_BOOT_1, flipped only
     * by a write, and the sweep that read 0x01110000 issued no writes at all;
     * NV_PMC_BOOT_0 read its correct 0x02A000A3 in that same run as the
     * control. See nv2a-probe-pmc-findings.md. */
    expect_read("NV_PMC_ENABLE reset", NV_PMC_ENABLE, 0x01110000, &d);

    /* Controls. Adding a case to a switch is exactly the kind of edit that can
     * land inside the wrong case and silently take another register's arm with
     * it, so every offset pmc_read already answered is re-checked -- including
     * the two that read live state rather than a constant, which a
     * misplaced `case` would strand. */
    expect_read("NV_PMC_BOOT_0", NV_PMC_BOOT_0, 0x02A000A3, &d);
    expect_read("NV_PMC_INTR_0 (zero)", NV_PMC_INTR_0, 0, &d);
    expect_read("NV_PMC_INTR_EN_0 (zero)", NV_PMC_INTR_EN_0, 0, &d);

    d.pmc.pending_interrupts = NV_PMC_INTR_0_PGRAPH | NV_PMC_INTR_0_PCRTC;
    d.pmc.enabled_interrupts = NV_PMC_INTR_EN_0_HARDWARE;
    expect_read("NV_PMC_INTR_0 (live)", NV_PMC_INTR_0,
                NV_PMC_INTR_0_PGRAPH | NV_PMC_INTR_0_PCRTC, &d);
    expect_read("NV_PMC_INTR_EN_0 (live)", NV_PMC_INTR_EN_0,
                NV_PMC_INTR_EN_0_HARDWARE, &d);

    /* THE FALSIFIER (#190). The same two read-only sweeps, the same
     * 1,024/1,024 reproducibility, no write issued: 0x160 and every dword in
     * 0x204-0x2FC read 0x00000001 where pmc_read fell through to
     * `default: r = 0`. Sixty-three dwords in the region, contiguous, plus
     * 0x160 on its own.
     *
     * Reported and modelled as a region rather than as 63 registers, and the
     * distinction is not cosmetic: a solid run of one value directly after a
     * live register is equally the signature of address aliasing or of a
     * fixed unimplemented-read pattern, and nothing measured separates the
     * three. Separating them needs a WRITE into the range -- four bytes from
     * the register whose write halted the physical console -- so it has not
     * been attempted and this test asserts nothing about writes. Whichever
     * reading is right, the read side returns 1, which is all that is
     * claimed here. */
    expect_read("0x160 (#190, unnamed)", 0x160, 0x00000001, &d);
    expect_region("0x204-0x2FC (#190)", 0x204, 0x2FC, 0x00000001, &d);

    /* #188's register is EXPLICITLY NOT part of #190's region and is
     * re-asserted after it, not before: 0x200 is one dword below 0x204, the
     * natural spelling of the region is a range, and `case 0x200 ... 0x2FC:`
     * would swallow it and still leave this file's first check green if that
     * check ran before the region existed. It sits here so the two issues
     * stay disjoint in the output as well as in the source. */
    expect_read("NV_PMC_ENABLE still #188's", NV_PMC_ENABLE, 0x01110000, &d);

    /* The edges, in all four directions. #190 measured a bounded region; it
     * did not license widening the case until it swallows a neighbour. Each
     * of these reads 0 on silicon (the survey's other 957 dwords) and 0 here.
     */
    expect_read("below 0x160", 0x15c, 0, &d);
    expect_read("above 0x160", 0x164, 0, &d);
    expect_read("below the region", 0x1fc, 0, &d);
    expect_read("above the region", 0x300, 0, &d);

    /* An unmodelled offset far from either must still read 0. #188 and #190
     * between them measured 65 dwords; that did not license inventing values
     * for the rest of the block. */
    expect_read("unmodelled 0x000c", 0x00c, 0, &d);

    /* The alignment narrowing, and it is OURS, not silicon's. The probe read
     * dword-aligned offsets and nothing else. `case 0x204 ... 0x2FC:` covers
     * every byte address in between, so pmc_read guards on (addr & 3) and
     * unaligned offsets keep the 0 they returned before this change -- which
     * is also what all three readings of the region predict, since byte 1 of
     * a register holding 0x00000001 is 0 whether that register is live,
     * aliased, or a fixed pattern.
     *
     * The aligned half is not merely our choice: a 1-byte read at 0x204 of a
     * dword reading 0x00000001 is 0x01 on a little-endian part, so the value
     * below is the measurement, at a narrower width. The unaligned half is a
     * deliberate refusal to answer, and a later lane with a sub-dword
     * measurement should change this line rather than work around it. */
    expect_read_sz("aligned byte in the region", 0x204, 1, 0x00000001, &d);
    expect_read_sz("unaligned byte, not ours", 0x205, 1, 0, &d);

    /* ---- NV_PMC_ENABLE's write side (#188, after #203) ----
     *
     * The sequence every graphics title runs, in pbkit's own order.
     * pb_init() saves the register and writes NV_PMC_ENABLE_ALL_ENABLE,
     * 0xFFFFFFFF; silicon then reads 0x13111113, the ten implemented bits
     * (0, 1, 4, 8, 12, 16, 20, 24, 25, 28). The constant read this replaces
     * answered 0x01110000 here. */
    memset(&d, 0, sizeof(d));
    pmc_reset(&d);
    /* Live interrupt state for the WHOLE sequence, not just one write: the
     * side-effect check can only see a field it is not already zero in. A
     * mutant ANDing the written word into enabled_interrupts passed when
     * only one write ran over non-zero state (mutants.py U7). */
    d.pmc.pending_interrupts = NV_PMC_INTR_0_PGRAPH | NV_PMC_INTR_0_PCRTC;
    d.pmc.enabled_interrupts = NV_PMC_INTR_EN_0_HARDWARE;
    uint32_t saved = (uint32_t)pmc_read(&d, NV_PMC_ENABLE, 4);
    expect_enable_write("pb_init all-ones", 0xFFFFFFFF, 0x13111113, &d);

    /* The only other writes pbkit issues clear and re-set bit 12. Read-
     * modify-write, as pbkit does it, so this is also the storage feeding
     * its own next write. */
    expect_enable_write("pbkit clears bit 12",
                        (uint32_t)pmc_read(&d, NV_PMC_ENABLE, 4) & ~0x1000u,
                        0x13110113, &d);
    expect_enable_write("pbkit re-sets bit 12",
                        (uint32_t)pmc_read(&d, NV_PMC_ENABLE, 4) | 0x1000u,
                        0x13111113, &d);

    /* pb_kill() writes the saved value back, and it must round-trip. */
    expect_enable_write("pb_kill restores", saved, 0x01110000, &d);

    /* THE CHOICE, stated: bits 16, 20 and 24 are modelled as STORAGE, so a
     * write that clears them reads back clear. Silicon has never been read
     * after such a write -- all three read 1 before any write, so settable
     * and hardwired-1 predict every read anyone has taken. Under hardwired-1
     * this would read 0x01111000. The falsifier is in pmc_write's comment;
     * if silicon answers "hardwired", this is the line to change. */
    expect_enable_write("0x1000: 16/20/24 = storage", 0x00001000, 0x00001000,
                        &d);

    /* Unimplemented bits ignore a 1: every bit outside the ten. */
    expect_enable_write("unimplemented bits only", ~0x13111113u, 0, &d);

    /* Zero is NV_PMC_ENABLE_ALL_DISABLE, the write that halted the console.
     * Not modelled as a halt or as an engine reset: stored, nothing else. */
    expect_enable_write("ALL_DISABLE stores 0", 0, 0, &d);

    /* The stored word is NV_PMC_ENABLE's alone. The interrupt state seeded
     * above survived every write, as the registers read it; #190's region
     * and BOOT_0 still read their constants; and a write elsewhere does not
     * reach it. */
    expect_enable_write("back to all-ones", 0xFFFFFFFF, 0x13111113, &d);
    expect_read("NV_PMC_INTR_0 after enable", NV_PMC_INTR_0,
                NV_PMC_INTR_0_PGRAPH | NV_PMC_INTR_0_PCRTC, &d);
    expect_read("NV_PMC_INTR_EN_0 after enable", NV_PMC_INTR_EN_0,
                NV_PMC_INTR_EN_0_HARDWARE, &d);
    expect_read("NV_PMC_BOOT_0 after enable", NV_PMC_BOOT_0, 0x02A000A3, &d);
    expect_region("0x204-0x2FC after enable", 0x204, 0x2FC, 0x00000001, &d);
    pmc_write(&d, NV_PMC_INTR_EN_0, 0, 4);
    pmc_write(&d, 0x204, 0, 4);
    expect_read("enable after other writes", NV_PMC_ENABLE, 0x13111113, &d);

    /* A guest reboot returns the idle value whatever was written. */
    pmc_reset(&d);
    expect_read("NV_PMC_ENABLE re-reset", NV_PMC_ENABLE, 0x01110000, &d);

    printf("\n%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
