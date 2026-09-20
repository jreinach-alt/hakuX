/* Tests for the generated write allow-list.
 *
 * The allow-list is the only thing standing between a typo on the wire and a
 * store into something that does not survive being stored into, so the tests
 * are checked by mutation: run_tests.sh rebuilds this against deliberately
 * broken copies of nv2a_window.h and requires each one to FAIL. A safety test
 * that has never been seen to fail is not evidence of anything.
 */
#include <stdio.h>
#include "nv2a_window.h"

static int fails;
#define CHECK(cond, ...) do { if (!(cond)) { \
    printf("  FAIL: "); printf(__VA_ARGS__); printf("\n"); fails++; } } while (0)

int main(void)
{
    /* The BAR is 16 MiB and nothing outside it is even readable. */
    CHECK(NV2A_MMIO_SIZE == 0x01000000u, "BAR size changed: %08x", NV2A_MMIO_SIZE);
    CHECK(nv2a_offset_readable(0x000000), "start of BAR must be readable");
    CHECK(nv2a_offset_readable(0xFFFFFC), "last dword of BAR must be readable");
    CHECK(!nv2a_offset_readable(0x1000000), "one past the BAR must not be readable");
    CHECK(!nv2a_offset_readable(0xFFFFFFFF), "wrap must not be readable");
    CHECK(!nv2a_offset_readable(0xFFFFFE), "a read straddling the end must be refused");

    /* Writes: inside a modelled, write-enabled block only. */
    CHECK(nv2a_offset_writable(0x000000), "PMC base must be writable");
    CHECK(nv2a_offset_writable(0x000FFC), "PMC last dword must be writable");
    CHECK(nv2a_offset_writable(0x400000), "PGRAPH base must be writable");
    CHECK(nv2a_offset_writable(0x401FFC), "PGRAPH last dword must be writable");

    /* Gaps between modelled blocks are inside the BAR and still refused. */
    CHECK(!nv2a_offset_writable(0x00E000), "gap after PTV must be refused");
    CHECK(!nv2a_offset_writable(0x200000), "gap before PGRAPH must be refused");
    CHECK(!nv2a_offset_writable(0x402000), "one past PGRAPH must be refused");
    CHECK(!nv2a_offset_writable(0x700000), "PRAMIN is unmodelled here; refuse");

    /* USER is inside the BAR, modelled, and deliberately write-excluded:
     * a store there submits pushbuffer work, which phase one does not do. */
    CHECK(nv2a_offset_readable(0x800000), "USER must still be readable");
    CHECK(!nv2a_offset_writable(0x800000), "USER must NOT be writable");
    CHECK(!nv2a_offset_writable(0xFFFFFC), "end of USER must NOT be writable");

    /* Alignment and overflow. */
    CHECK(!nv2a_offset_writable(0x000001), "unaligned must be refused");
    CHECK(!nv2a_offset_writable(0x000002), "unaligned must be refused");
    CHECK(!nv2a_offset_writable(0xFFFFFFFF), "wrap must be refused");

    /* Adjacent blocks: PMC ends where PBUS begins, so both sides are writable
     * and there is no seam to fall through. A real seam is PTV -> PRMFB. */
    CHECK(nv2a_offset_writable(0x000FFC), "last dword of PMC");
    CHECK(nv2a_offset_writable(0x001000), "first dword of PBUS");
    CHECK(nv2a_offset_writable(0x00DFFC), "last dword of PTV");
    CHECK(!nv2a_offset_writable(0x00E000), "the seam after PTV must be refused");

    /* Hazards: inside the allow-list, still refused. */
    CHECK(nv2a_offset_writable(0x000200), "0x200 IS inside a writable block");
    CHECK(!nv2a_offset_write_allowed(0x000200), "NV_PMC_ENABLE must be refused");
    CHECK(!nv2a_offset_write_allowed(0x000004), "the register that would not restore");
    CHECK(!nv2a_offset_write_allowed(0x680504), "MPLL coefficient must be refused");
    CHECK(!nv2a_offset_write_allowed(0x680508), "VPLL coefficient must be refused");
    CHECK(!nv2a_offset_write_allowed(0x003200), "pushbuffer cache control refused");
    CHECK(nv2a_offset_write_allowed(0x000140), "a harmless register still allowed");
    CHECK(nv2a_offset_readable(0x000200), "hazards stay READABLE");

    if (fails) { printf("%d check(s) failed\n", fails); return 1; }
    printf("all allow-list checks passed\n");
    return 0;
}
