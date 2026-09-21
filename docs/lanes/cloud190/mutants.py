#!/usr/bin/env python3
"""Mutants for #190's half of pmc_enable_selftest.sh -- the 0x160 /
0x204-0x2FC read-1 region.

    python3 docs/lanes/cloud190/mutants.py

Same discipline and the same runner as docs/lanes/pmc188/mutants.py, imported
rather than copied: two copies of a scratch-tree runner drift, and this suite
drives the very same script. Every row names the LINE the run must go red on,
because an exit code is a coarse discriminator -- a script that exits non-zero
on everything "catches" everything. Three rows (P1-P3) must PASS, which is
the half that shows the guards are not simply always-on, and two more (K1,
K2) must pass UNCOMFORTABLY: they are the holes grep cannot close, recorded
as green rows so the guard's reach is re-runnable rather than a sentence.

    python3 docs/lanes/cloud190/mutants.py --newly-caught

pairs the OLD script with the OLD pmc.c to show the write-side guard was
missing rather than merely asserting it. A bare `--at <rev>` cannot show that:
it runs the old script against THIS pmc.c, where the old "unmodelled 0x204
reads 0" assertion fails and every write mutant goes red for a reason that has
nothing to do with the write side.

PRE is the falsification run and the one that makes the rest mean anything: it
builds the selftest against pmc.c as it was at the base commit, BEFORE this
lane touched it, and requires the #190 assertions to fail there. A check that
has never been seen to fail on the code it was written against is decoration.
Pinned to a sha, not to origin/master, because master will contain the fix as
soon as this folds and the row would then quietly invert.

Scratch trees only: hw/ and docs/testing/ are never written to, and the tree
is assembled by copy rather than by redirecting a path, so a crash cannot
leave a mutated pmc.c behind in the worktree.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "pmc188_mutants", ROOT / "docs/lanes/pmc188/mutants.py")
_pmc188 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pmc188)
run, in_write, ORIG = _pmc188.run, _pmc188.in_write, _pmc188.ORIG

# The commit this branch left master at: pmc.c there has #188's case and no
# #190 case at all.
BASE = "3fe18366cd"

CASE_LABELS = "    case 0x160:\n    case 0x204 ... 0x2FC:\n"
GUARDED = ("        if ((addr & 3) == 0) {\n"
           "            r = 0x00000001;\n"
           "        }\n")


def sub(old, new, src=None):
    s = ORIG if src is None else src
    assert old in s, f"anchor not found: {old!r}"
    return s.replace(old, new, 1)


def at_base():
    p = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{BASE}:hw/xbox/nv2a/pmc.c"],
        capture_output=True, text=True)
    if p.returncode != 0:
        print(f"cannot read pmc.c at {BASE} -- shallow clone? "
              f"PRE cannot run, and without it nothing below is a "
              f"falsification.\n{p.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return p.stdout


MUTANTS = [
    ("N0", "unmutated tree", ORIG, 0, "16 checks, 0 failures"),

    ("PRE", f"pmc.c at the base commit {BASE}, before this lane -- must FAIL",
     at_base(), 1, "FAIL 0x160 (#190, unnamed)"),

    # --- the read side: value, both ends of the range, and 0x160 ---
    ("N1", "the region case is deleted outright",
     sub(CASE_LABELS + "        /* Measured on real NV2A silicon (#190)", "        /* gone ("),
     1, "FAIL 0x160 (#190, unnamed)"),
    ("N2", "the region reads 0 again",
     sub("            r = 0x00000001;\n", "            r = 0;\n"),
     1, "63 of 63 dwords wrong"),
    ("N3", "the range stops one dword short, at 0x2F8",
     sub("    case 0x204 ... 0x2FC:\n", "    case 0x204 ... 0x2F8:\n"),
     1, "1 of 63 dwords wrong (first 0x2fc, last 0x2fc)"),
    ("N4", "the range runs one dword long, to 0x300",
     sub("    case 0x204 ... 0x2FC:\n", "    case 0x204 ... 0x300:\n"),
     1, "FAIL above the region"),
    # N4b is the mechanical half of "keep #188 and #190 disjoint", and it is
    # stronger than an assertion: extending the range down past 0x200 cannot
    # be written at all, because it overlaps `case NV_PMC_ENABLE:` and gcc
    # refuses the translation unit. Nothing this lane wrote enforces that --
    # the compiler does -- so it is recorded as a compile refusal rather than
    # dressed up as a check of ours. N4c below is the assertion that does
    # cover the lower edge, at an offset that does not collide.
    ("N4b", "the range starts low enough to swallow #188's 0x200 -- gcc refuses",
     sub("    case 0x204 ... 0x2FC:\n", "    case 0x1FC ... 0x2FC:\n"),
     1, "duplicate (or overlapping) case value"),
    ("N4c", "0x1FC is given the region's value by a separate label",
     sub("    case 0x160:\n", "    case 0x160:\n    case 0x1FC:\n"),
     1, "FAIL below the region"),
    ("N5", "0x160 loses its case", sub("    case 0x160:\n", ""),
     1, "FAIL 0x160 (#190, unnamed)"),
    ("N5b", "0x160 is off by one dword, at 0x164",
     sub("    case 0x160:\n", "    case 0x164:\n"),
     1, "FAIL 0x160 (#190, unnamed)"),
    ("N6", "the alignment guard is dropped -- unaligned offsets inherit the value",
     sub(GUARDED, "        r = 0x00000001;\n"),
     1, "FAIL unaligned byte, not ours"),
    ("N6b", "the alignment guard is widened to 8 bytes",
     sub("        if ((addr & 3) == 0) {\n", "        if ((addr & 7) == 0) {\n"),
     1, "32 of 63 dwords wrong"),
    ("N7", "the constant leaks into `default` -- the whole block reads 1",
     sub("    default:\n        break;\n", "    default:\n        r = 0x00000001;\n        break;\n"),
     1, "FAIL unmodelled 0x000c"),
    ("N8", "the region's constant lands on NV_PMC_ENABLE's arm",
     sub("        r = 0x01110000;\n", "        r = 0x00000001;\n"),
     1, "FAIL NV_PMC_ENABLE"),

    # --- the write side: #190's region must stay out of pmc_write ---
    # The pre-existing guard is anchored on 0x200 and sees none of these.
    # That is measured, not asserted, and it needs its own mode to measure:
    # `--at <old rev>` would run the old script against THIS pmc.c, where the
    # old "unmodelled 0x204 reads 0" assertion fails for a reason that has
    # nothing to do with the write side -- red, but for the wrong reason, one
    # level of the coarse-exit-code trap down. `--newly-caught` pairs the old
    # script with the OLD pmc.c so the write guard is the only variable.
    ("N9", "pmc_write gains `case 0x204 ... 0x2FC:` -- #190's own range form",
     in_write("    case 0x204 ... 0x2FC:\n        break;\n"),
     1, "REFUSED: pmc_write has a case in #190's read-1 region"),
    ("N10", "pmc_write gains `case 0x160:`",
     in_write("    case 0x160:\n        break;\n"),
     1, "REFUSED: pmc_write has a case in #190's read-1 region"),
    ("N11", "pmc_write gains `case 352:` -- 0x160 in decimal",
     in_write("    case 352:\n        break;\n"),
     1, "REFUSED: pmc_write has a case in #190's read-1 region"),
    ("N12", "pmc_write gains `case 0x2FC:` -- the far end alone",
     in_write("    case 0x2FC:\n        break;\n"),
     1, "REFUSED: pmc_write has a case in #190's read-1 region"),

    ("N13", "pmc_write gains `case 0x1FC ... 0x2FC:` -- a range that ENDS in "
            "the region; #188 audit pass 2's named hole (P2)",
     in_write("    case 0x1FC ... 0x2FC:\n        break;\n"),
     1, "REFUSED: pmc_write has a case in #190's read-1 region"),

    # --- the holes, as measurements rather than as a sentence ---
    # These two are what the guard CANNOT see. They are expected GREEN, which
    # is uncomfortable to write down and is the point: a limit recorded as a
    # passing row is re-runnable, and the day someone closes it these rows go
    # red and get deleted. Both need the case labels parsed and compared as
    # numbers -- grep cannot evaluate an interval.
    ("K1", "KNOWN HOLE: `case 0x100 ... 0x400:` spans the region with both "
           "endpoints outside it -- NOT caught",
     in_write("    case 0x100 ... 0x400:\n        break;\n"),
     0, "16 checks, 0 failures"),
    ("K2", "KNOWN HOLE: `case 516:` -- 0x204 in decimal -- NOT caught",
     in_write("    case 516:\n        break;\n"),
     0, "16 checks, 0 failures"),

    # --- must PASS: the guards are anchored on code, not on prose or shape ---
    ("P1", "pmc_write gains a COMMENT naming 0x204 and #190 -- must PASS",
     in_write("    /* 0x160 and case 0x204 ... 0x2FC are #190's, read-only. */\n"),
     0, "16 checks, 0 failures"),
    ("P2", "the region is implemented in `default` with an if instead -- must PASS",
     sub(CASE_LABELS, "    case 0x2FFFFFFF:  /* unreachable placeholder */\n").replace(
         "    default:\n        break;\n",
         "    default:\n"
         "        if (addr == 0x160 || (addr >= 0x204 && addr <= 0x2FC)) {\n"
         "            if ((addr & 3) == 0) {\n"
         "                r = 0x00000001;\n"
         "            }\n"
         "        }\n"
         "        break;\n", 1),
     0, "16 checks, 0 failures"),
    ("P3", "an unrelated later function contains 0x00000001 -- must PASS",
     ORIG + "\nstatic uint32_t pmc_region_debug(void)\n{\n    return 0x00000001;\n}\n",
     0, "16 checks, 0 failures"),
]


def newly_caught():
    """Did the pre-existing script certify a pmc_write that models #190's
    region? Old script, OLD pmc.c, one arm added to pmc_write: the write
    guard is then the only thing that could go red. Each row below must come
    back GREEN, which is the defect this lane's guard closes.
    """
    head = ("void pmc_write(void *opaque, hwaddr addr, uint64_t val, "
            "unsigned int size)")
    base = at_base()
    i = base.index(head)
    j = base.index("    switch (addr) {", i) + len("    switch (addr) {\n")
    ok = True
    for name, arm in [("N9", "    case 0x204 ... 0x2FC:\n        break;\n"),
                      ("N10", "    case 0x160:\n        break;\n"),
                      ("N11", "    case 352:\n        break;\n"),
                      ("N12", "    case 0x2FC:\n        break;\n")]:
        ok &= run(name, f"old script + old pmc.c + {arm.strip().splitlines()[0]}"
                  " in pmc_write -- must be CERTIFIED GREEN",
                  base[:j] + arm + base[j:], 0, "8 checks, 0 failures",
                  rev=BASE)
    print(f"\nagainst the selftest at {BASE}: the write side of #190's region "
          f"was {'UNGUARDED' if ok else 'ALREADY GUARDED -- this claim is false'}")
    return 0 if ok else 1


if __name__ == "__main__":
    rev = None
    if len(sys.argv) == 2 and sys.argv[1] == "--newly-caught":
        sys.exit(newly_caught())
    if len(sys.argv) == 3 and sys.argv[1] == "--at":
        rev = sys.argv[2]
    elif len(sys.argv) != 1:
        sys.exit(__doc__)
    bad = [m[0] for m in MUTANTS if not run(*m, rev=rev)]
    if rev:
        # The expectations describe the CURRENT script, so a row that
        # disagrees here is a row this lane newly catches. That is how
        # "newly caught" becomes a measurement instead of a claim -- see
        # NOTES.md for which of the disagreements are informative and which
        # are just the check count moving from 8 to 16.
        print(f"\nagainst the selftest at {rev}: {len(bad)} of {len(MUTANTS)} "
              f"disagree with the current expectations"
              + (f": {bad}" if bad else ""))
        sys.exit(0)
    print(f"\n{len(MUTANTS)} mutants, {len(bad)} unexpected"
          + (f": {bad}" if bad else ""))
    sys.exit(1 if bad else 0)
