#!/usr/bin/env python3
"""Build each mutant of pmc.c in its own scratch tree and check that
pmc_enable_selftest.sh goes red on it -- and, for the two the audit's L1/L2
named, that it no longer goes red on a file whose pmc_write is untouched.

A guard that has never been seen to refuse anything is an assertion about a
script, not a check. An exit code is also a coarse discriminator, so every
expectation below names the LINE the run must go red on, not just the status.

    python3 docs/lanes/pmc188/mutants.py
    python3 docs/lanes/pmc188/mutants.py --at c2e57d8d86   # the pre-remediation
                                                           # script, to show the
                                                           # new rows were red
`--at <rev>` runs the same mutants against the selftest as it was at <rev>,
which is what makes "newly caught" a measurement rather than a claim. The
expectations below describe the CURRENT script, so under `--at` a row that the
remediation fixed is expected to disagree -- that disagreement IS the evidence.

Scratch trees only: the real docs/testing and hw/ are never written to, and
the tree is assembled by copy rather than by redirecting a path, so a crash
cannot leave the mutated file behind in the worktree.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PMC = ROOT / "hw/xbox/nv2a/pmc.c"
REGS = ROOT / "hw/xbox/nv2a/nv2a_regs.h"
SH = ROOT / "docs/testing/pmc_enable_selftest.sh"
C = ROOT / "docs/testing/pmc_enable_selftest.c"

ORIG = PMC.read_text()

WRITE_HEAD = "void pmc_write(void *opaque, hwaddr addr, uint64_t val, unsigned int size)"
WRITE_SWITCH = "    switch (addr) {\n    case NV_PMC_INTR_0:\n        /* the bits"


def in_write(case_body):
    """Insert an arm at the top of pmc_write's switch."""
    i = ORIG.index(WRITE_HEAD)
    j = ORIG.index("    switch (addr) {", i) + len("    switch (addr) {\n")
    return ORIG[:j] + case_body + ORIG[j:]


def after_read_case(old, new):
    return ORIG.replace(old, new, 1)


MUTANTS = [
    # id, description, mutated source, expected exit, expected text in output
    ("M0", "unmutated tree", ORIG, 0, "8 checks, 0 failures"),
    ("M1", "pmc_write gains `case NV_PMC_ENABLE:`",
     in_write("    case NV_PMC_ENABLE:\n        d->pmc.pending_interrupts = val;\n        break;\n"),
     1, "REFUSED: pmc_write has a case for NV_PMC_ENABLE"),
    ("M1b", "pmc_write gains `case 0x200:` -- the spelling that defeated the old guard (audit M1)",
     in_write("    case 0x200:\n        d->pmc.pending_interrupts = val;\n        break;\n"),
     1, "REFUSED: pmc_write has a case for NV_PMC_ENABLE"),
    ("M1c", "pmc_write gains a GCC range arm `case 0x00000200 ... 0x2FC:`",
     in_write("    case 0x00000200 ... 0x2FC:\n        break;\n"),
     1, "REFUSED: pmc_write has a case for NV_PMC_ENABLE"),
    ("M2", "the measured constant appears in pmc_write",
     in_write("    case NV_PMC_INTR_EN_0 + 0x40:\n        val |= 0x01110000;\n        break;\n"),
     1, "REFUSED: the measured read-back constant appears in pmc_write"),
    ("M2b", "...spelled without the leading zero, 0x1110000",
     in_write("    case NV_PMC_INTR_EN_0 + 0x40:\n        val |= 0x1110000;\n        break;\n"),
     1, "REFUSED: the measured read-back constant appears in pmc_write"),
    ("M3", "the read reverts to 0",
     after_read_case("        r = 0x01110000;", "        r = 0;"),
     1, "FAIL NV_PMC_ENABLE"),
    ("M4", "the case widens to NV_PMC_ENABLE + 4",
     after_read_case("    case NV_PMC_ENABLE:\n",
                     "    case NV_PMC_ENABLE:\n    case NV_PMC_ENABLE + 4:\n"),
     1, "FAIL unmodelled 0x204"),
    ("M5", "the constant lands on NV_PMC_BOOT_0's arm",
     ORIG.replace("        r = 0x02A000A3;", "        r = 0x01110000;", 1),
     1, "FAIL NV_PMC_BOOT_0"),
    ("M6", "pmc_read is renamed", ORIG.replace("uint64_t pmc_read(", "uint64_t pmc_read_mmio(", 1),
     2, "anchors not found in pmc.c"),
    ("M7", "the trace logs 0 instead of r",
     ORIG.replace("    nv2a_reg_log_read(NV_PMC, addr, size, r);",
                  "    nv2a_reg_log_read(NV_PMC, addr, size, 0);", 1),
     1, "the trace is wrong"),
    # `size` must stay USED or -Werror=unused-parameter reddens the build
    # first and the run proves nothing about the new assertion.
    ("M7b", "the trace logs the wrong width -- newly caught (audit L3)",
     ORIG.replace("    nv2a_reg_log_read(NV_PMC, addr, size, r);",
                  "    nv2a_reg_log_read(NV_PMC, addr, size - 1, r);", 1),
     1, "the trace is wrong"),
    # The two below must now PASS. Before this remediation the write extract
    # ran to EOF and the read extract ran to pmc_write's signature, so each of
    # these was refused or failed to compile against a file whose pmc_write is
    # byte-identical to the tree's (audit L1, L2).
    ("L1", "an unrelated later function contains the constant -- must PASS",
     ORIG + "\nstatic uint32_t pmc_enable_debug_mask(void)\n{\n    return 0x01110000;\n}\n",
     0, "8 checks, 0 failures"),
    ("L2", "a helper using an unstubbed QEMU type sits between the two -- must PASS",
     ORIG.replace("\nvoid pmc_write(",
                  "\nstatic MemoryRegion *pmc_region(NV2AState *d)\n{\n"
                  "    return &d->mmio;\n}\n\nvoid pmc_write(", 1),
     0, "8 checks, 0 failures"),
]


def at_rev(rev, path):
    """The selftest file as it was at <rev>, for the --at comparison."""
    rel = path.relative_to(ROOT)
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{rel}"],
                          capture_output=True, text=True, check=True).stdout


def run(name, desc, src, want_exit, want_text, rev=None):
    tmp = Path(tempfile.mkdtemp(prefix=f"pmcmut-{name}-"))
    try:
        (tmp / "hw/xbox/nv2a").mkdir(parents=True)
        (tmp / "docs/testing").mkdir(parents=True)
        (tmp / "hw/xbox/nv2a/pmc.c").write_text(src)
        shutil.copy(REGS, tmp / "hw/xbox/nv2a/nv2a_regs.h")
        if rev:
            (tmp / "docs/testing/pmc_enable_selftest.sh").write_text(at_rev(rev, SH))
            (tmp / "docs/testing/pmc_enable_selftest.c").write_text(at_rev(rev, C))
        else:
            shutil.copy(SH, tmp / "docs/testing/pmc_enable_selftest.sh")
            shutil.copy(C, tmp / "docs/testing/pmc_enable_selftest.c")
        p = subprocess.run(["bash", str(tmp / "docs/testing/pmc_enable_selftest.sh")],
                           capture_output=True, text=True)
        out = p.stdout + p.stderr
        ok = p.returncode == want_exit and want_text in out
        print(f"{'ok  ' if ok else 'FAIL'} {name:4s} exit={p.returncode} "
              f"(want {want_exit})  {desc}")
        if not ok:
            print(re.sub(r"^", "         | ", out.strip() or "(no output)", flags=re.M))
            print(f"         | wanted text: {want_text!r}")
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    rev = None
    if len(sys.argv) == 3 and sys.argv[1] == "--at":
        rev = sys.argv[2]
    elif len(sys.argv) != 1:
        sys.exit(__doc__)
    bad = [m[0] for m in MUTANTS if not run(*m, rev=rev)]
    if rev:
        print(f"\nagainst the selftest at {rev}: {len(bad)} of {len(MUTANTS)} "
              f"disagree with the current expectations" + (f": {bad}" if bad else ""))
        sys.exit(0)
    print(f"\n{len(MUTANTS)} mutants, {len(bad)} unexpected" + (f": {bad}" if bad else ""))
    sys.exit(1 if bad else 0)
