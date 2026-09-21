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
 * What this does NOT check: that pmc.c compiles in tree, anything on the
 * write path (deliberately -- see below), and anything about the __ANDROID__
 * logging blocks, which are not compiled here and do not alter the returned
 * value on any path.
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* --- stubs for the three things pmc_read touches --- */

typedef uint64_t hwaddr;

#include "nv2a_regs.h"

typedef struct NV2AState {
    struct {
        uint32_t pending_interrupts;
        uint32_t enabled_interrupts;
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

#include "pmc_read_extract.c"

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

int main(void)
{
    NV2AState d;
    memset(&d, 0, sizeof(d));

    /* THE FALSIFIER (#188). Two independent read-only sweeps of real NV2A
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
    expect_read("NV_PMC_ENABLE", NV_PMC_ENABLE, 0x01110000, &d);

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

    printf("\n%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
