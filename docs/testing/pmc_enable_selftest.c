/* Standalone behaviour test for pmc_read's register table (#188).
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

static void expect_read(const char *what, hwaddr addr, uint64_t want,
                        NV2AState *d)
{
    memset(&g_log, 0, sizeof(g_log));
    uint64_t got = pmc_read(d, addr, 4);
    checks++;
    if (got != want) {
        failures++;
        printf("FAIL %-28s addr=0x%03x got=0x%08llx want=0x%08llx\n", what,
               (unsigned)addr, (unsigned long long)got,
               (unsigned long long)want);
        return;
    }
    /* The traced value must be the returned one, at the read's own offset. */
    if (g_log.calls != 1 || g_log.val != want || g_log.addr != addr) {
        failures++;
        printf("FAIL %-28s addr=0x%03x value 0x%08llx is right but the trace "
               "is wrong: calls=%d logged addr=0x%03x val=0x%08llx\n",
               what, (unsigned)addr, (unsigned long long)got, g_log.calls,
               (unsigned)g_log.addr, (unsigned long long)g_log.val);
        return;
    }
    printf("ok   %-28s addr=0x%03x -> 0x%08llx\n", what, (unsigned)addr,
           (unsigned long long)got);
}

int main(void)
{
    NV2AState d;
    memset(&d, 0, sizeof(d));

    /* THE FALSIFIER (#188). Two independent read-only sweeps of real NV2A
     * silicon, with a reboot between them, read 0x01110000 at PMC+0x200,
     * 1,024/1,024 dwords reproducible. Before this lane pmc_read had no case
     * for it and fell through to `default: r = 0`, so this line printed
     * got=0x00000000 want=0x01110000. */
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

    /* An unmodelled offset must still read 0. #188 measured one register; it
     * did not license inventing values for the rest of the block. These pin
     * the new case to the exact offset: a case written against a mask or a
     * range, or a `default` quietly given the constant, answers 0x204 and
     * 0x00c too. */
    expect_read("unmodelled 0x204", 0x204, 0, &d);
    expect_read("unmodelled 0x000c", 0x00c, 0, &d);

    printf("\n%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
