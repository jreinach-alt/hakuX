#!/usr/bin/env python3
"""Mutants for #188's NV_PMC_ENABLE storage: build each in its own scratch
tree and check pmc_enable_selftest.sh goes red on it, on the LINE named, not
just with a non-zero exit.

    python3 docs/lanes/cloud-188/mutants.py

One mutant per invariant the lane added: the reset value, the mask (in both
directions), storage rather than a constant read, the write not dropped, the
16/20/24 storage choice, and "gate nothing" three ways (an interrupt update,
another field touched, a call into another engine). Two controls must stay
GREEN: the unmutated tree, and the arm spelled `case 0x200:`, which #190's
region guard excludes on purpose.

This supersedes docs/lanes/pmc188/mutants.py's M1-M2b, which asserted that
pmc_write had NO arm for NV_PMC_ENABLE. That was the invariant until this
lane; those rows now go the other way by design. The copy-into-a-scratch-tree
shape is pmc188's: the real hw/ and docs/testing are never written.
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
STORE = "        d->pmc.enable = val & 0x13111113;\n"
READ = "        r = d->pmc.enable;\n"
RESET = "    d->pmc.enable = 0x01110000;\n"
for anchor in (STORE, READ, RESET, "    case NV_PMC_ENABLE:\n"):
    assert ORIG.count(anchor) >= 1, f"anchor gone from pmc.c: {anchor!r}"
assert ORIG.count(STORE) == 1 and ORIG.count(READ) == 1 and ORIG.count(RESET) == 1


def sub(old, new):
    assert ORIG.count(old) == 1, old
    return ORIG.replace(old, new, 1)


def write_arm_label(new_label):
    """Respell the case label of pmc_write's NV_PMC_ENABLE arm only."""
    w = ORIG.index("\nvoid pmc_write(")
    i = ORIG.index("    case NV_PMC_ENABLE:\n", w)
    return ORIG[:i] + new_label + ORIG[i + len("    case NV_PMC_ENABLE:\n"):]


def in_write(case_body):
    """Insert an arm at the top of pmc_write's switch."""
    w = ORIG.index("\nvoid pmc_write(")
    j = ORIG.index("    switch (addr) {\n", w) + len("    switch (addr) {\n")
    return ORIG[:j] + case_body + ORIG[j:]


MUTANTS = [
    # id, description, mutated source, expected exit, expected text in output
    ("U0", "unmutated tree -- must PASS", ORIG, 0, "38 checks, 0 failures"),
    ("U1", "unmasked storage", sub(STORE, "        d->pmc.enable = val;\n"),
     1, "FAIL pb_init all-ones"),
    ("U1b", "mask loses bit 1 (0x13111111)",
     sub(STORE, "        d->pmc.enable = val & 0x13111111;\n"),
     1, "FAIL pb_init all-ones"),
    ("U1c", "mask gains bit 2 (0x13111117)",
     sub(STORE, "        d->pmc.enable = val & 0x13111117;\n"),
     1, "FAIL pb_init all-ones"),
    ("U2", "constant read, the pre-#188 model",
     sub(READ, "        r = 0x01110000;\n"), 1, "FAIL pb_init all-ones"),
    ("U3", "write dropped (the arm stores nothing)",
     sub(STORE, ""), 1, "FAIL pb_init all-ones"),
    ("U4", "reset value 0, the pre-#198 read",
     sub(RESET, "    d->pmc.enable = 0;\n"), 1, "FAIL NV_PMC_ENABLE reset"),
    ("U5", "16/20/24 hardwired-1 instead of storage",
     sub(READ, "        r = d->pmc.enable | 0x01110000;\n"),
     1, "FAIL 0x1000: 16/20/24 = storage"),
    ("U6", "gating: the write raises an interrupt update",
     sub(STORE, STORE + "        nv2a_update_irq(d);\n"),
     1, "had a side effect"),
    ("U7", "gating: the write touches other PMC state",
     sub(STORE, STORE + "        d->pmc.enabled_interrupts &= val;\n"),
     1, "other state CHANGED"),
    ("U8", "gating: a halt/engine reset on ALL_DISABLE",
     sub(STORE, STORE + "        if (!val) {\n            pgraph_reset(d);\n        }\n"),
     1, "did not compile"),
    ("U9", "#190's region gains a write arm -- still refused",
     in_write("    case 0x204 ... 0x2FC:\n        break;\n"),
     1, "REFUSED: pmc_write has a case in #190's read-1 region"),
    ("U10", "the arm spelled `case 0x200:` -- must PASS",
     write_arm_label("    case 0x200:\n"), 0, "38 checks, 0 failures"),
    ("U11", "pmc_reset renamed", sub("void pmc_reset(", "void pmc_reset_state("),
     2, "anchors not found in pmc.c"),
]


def run(name, desc, src, want_exit, want_text):
    tmp = Path(tempfile.mkdtemp(prefix=f"pmc188mut-{name}-"))
    try:
        (tmp / "hw/xbox/nv2a").mkdir(parents=True)
        (tmp / "docs/testing").mkdir(parents=True)
        (tmp / "hw/xbox/nv2a/pmc.c").write_text(src)
        shutil.copy(REGS, tmp / "hw/xbox/nv2a/nv2a_regs.h")
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
    if len(sys.argv) != 1:
        sys.exit(__doc__)
    bad = [m[0] for m in MUTANTS if not run(*m)]
    print(f"\n{len(MUTANTS)} mutants, {len(bad)} unexpected" + (f": {bad}" if bad else ""))
    sys.exit(1 if bad else 0)
