#!/usr/bin/env python3
"""Which of #200's register holes does a per-test PGRAPH diff show SET?

    python3 docs/lanes/xbox/region200_parse.py <pgraph_progress_log.txt> [--json OUT]

Reads the log that nxdk_pgraph_tests' per-test instrument writes
(`docs/testing/patches/pgraph-per-test-instrument.patch`, forced on by
`region200_force_diff.patch`). A log is a sequence of blocks:

    PGRAPH-DIFF <Suite>::<Test>          (or PGRAPH-DIFF SUITE-RESIDUAL <Suite>)
    PMC BOOT_0(canary) 0xFD000000 = 0x02A000A3
    PMC INTR_0 ... / PMC INTR_EN_0 ... / PMC ENABLE ...
    0xFD4xxxxx: 0x<from> => 0x<to>       one line per register that CHANGED

For each of the 20 field-rebuilt registers in #200's table (the [job.cloud]
comment of 2026-09-25 07:44Z), it reports the bits inside
- HOLE: the "undeclared, never written" mask, and
- DNW: the "declared, never written" fields (TRAPPED_ADDR DHV, CSV0_D
  FOG_MODE, CSV1_A T0_ENABLE/MODE/TEXTURE),
seen SET in any from/to value, and seen TOGGLING within a test.

What it cannot see, and says so: DumpDiff lists a register only when it
changed inside the bracket, so a hole bit that silicon holds constant is
visible only through a register that moved for another reason. "Never seen
set" is not "zero". A register that never appears is reported as NOT SEEN,
never as clean.

The canary is checked per block. If BOOT_0 is not 0x02A000A3 the read path is
not trustworthy and the whole log is refused, because a byte-swapped MMIO
window has produced confident nonsense here before.

This file writes nothing unless --json is given.
"""
import argparse
import json
import re
import sys

PGRAPH = 0xFD400000
CANARY = 0x02A000A3

# offset: (name, hole mask, declared-never-written mask), from #200's table.
REGS = {
    0x0108: ("NSOURCE", 0xFFFFFFFE, 0),
    0x0704: ("TRAPPED_ADDR", 0xEE08E000, 0x10000000),
    0x0710: ("SURFACE", 0x888FFFFF, 0),
    0x0FB4: ("CSV0_D", 0x20030000, 0x00200000),
    0x0FB8: ("CSV0_C", 0x200000FF, 0),
    0x0FBC: ("CSV1_B", 0x000F000F, 0),
    0x0FC0: ("CSV1_A", 0x00080008, 0x00070007),
    0x0FC4: ("CHEOPS_OFFSET", 0xFFFF0000, 0),
    0x1800: ("ANTIALIASING", 0xFFFFFFFE, 0),
    0x1804: ("BLEND", 0xFFFE0000, 0),
    0x194C: ("CONTROL_0", 0xC020A000, 0),
    0x1950: ("CONTROL_1", 0x0000000E, 0),
    0x1954: ("CONTROL_2", 0xFFFFF000, 0),
    0x1958: ("CONTROL_3", 0xFFF8FC7E, 0),
    0x1990: ("SETUPRASTER", 0x4F1FE030, 0),
    0x1998: ("SHADERCTL", 0xF0000000, 0),
    0x19A4: ("SHADOWCTL", 0xFFFFFFF8, 0),
    0x1A84: ("ZCOMPRESSOCCLUDE", 0xFFFFFFEF, 0),
}
for _i in range(4):
    REGS[0x1A04 + 4 * _i] = ("TEXFMT%d" % _i, 0x00008031, 0)
    REGS[0x1A34 + 4 * _i] = ("TEXPALETTE%d" % _i, 0x00000032, 0)

LABEL = re.compile(r"^PGRAPH-DIFF (.+?)\s*$")
PMC = re.compile(r"^PMC (\S+) 0x([0-9A-Fa-f]{8}) = 0x([0-9A-Fa-f]{8})\s*$")
REG = re.compile(r"^0x([0-9A-Fa-f]{8}): 0x([0-9A-Fa-f]{8}) => 0x([0-9A-Fa-f]{8})\s*$")


def parse(lines):
    label, blocks, canary_bad, completed = None, 0, [], False
    seen = {}  # offset -> {"set", "toggle", "dnw_set", "dnw_toggle", "n", "tests"}
    tests, other_regs = set(), set()
    for raw in lines:
        line = raw.rstrip("\r\n")
        if "Testing completed normally" in line:
            completed = True
        m = LABEL.match(line)
        if m:
            label, blocks = m.group(1), blocks + 1
            if not label.startswith("SUITE-RESIDUAL "):
                tests.add(label)
            continue
        m = PMC.match(line)
        if m:
            if m.group(1).startswith("BOOT_0") and int(m.group(3), 16) != CANARY:
                canary_bad.append((label, m.group(3)))
            continue
        m = REG.match(line)
        if not m:
            continue
        addr, frm, to = (int(g, 16) for g in m.groups())
        off = addr - PGRAPH
        if off not in REGS:
            other_regs.add(off)
            continue
        _name, hole, dnw = REGS[off]
        s = seen.setdefault(off, {"set": 0, "toggle": 0, "dnw_set": 0,
                                  "dnw_toggle": 0, "n": 0, "tests": set()})
        s["n"] += 1
        s["set"] |= (frm | to) & hole
        s["toggle"] |= (frm ^ to) & hole
        s["dnw_set"] |= (frm | to) & dnw
        s["dnw_toggle"] |= (frm ^ to) & dnw
        if (frm | to) & (hole | dnw):
            s["tests"].add(label or "(before any label)")
    return dict(blocks=blocks, tests=tests, completed=completed,
                canary_bad=canary_bad, seen=seen, other_regs=other_regs)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--json", metavar="OUT")
    a = ap.parse_args(argv)
    with open(a.log, errors="replace") as fh:
        r = parse(fh)
    print("%s: %d diff blocks, %d tests, log %s" % (
        a.log, r["blocks"], len(r["tests"]),
        "COMPLETED" if r["completed"] else "has NO completion marker"))
    if not r["blocks"]:
        print("REFUSED: no PGRAPH-DIFF block; the instrument did not run")
        return 2
    if r["canary_bad"]:
        print("REFUSED: BOOT_0 canary is not 0x%08X in %d block(s), first %r"
              % (CANARY, len(r["canary_bad"]), r["canary_bad"][0]))
        return 2
    print("%-16s %6s  %-10s %-10s %-10s %-10s  %s" % (
        "register", "lines", "hole set", "hole tog", "dnw set", "dnw tog", "tests showing it"))
    out = {}
    for off in sorted(REGS):
        name, hole, dnw = REGS[off]
        s = r["seen"].get(off)
        if not s:
            print("%-16s %6s  NOT SEEN (never moved; says nothing about its holes)" % (name, 0))
            out[name] = None
            continue
        print("%-16s %6d  %08X   %08X   %08X   %08X    %d" % (
            name, s["n"], s["set"], s["toggle"], s["dnw_set"], s["dnw_toggle"],
            len(s["tests"])))
        out[name] = {k: (v if k != "tests" else sorted(v)) for k, v in s.items()}
    print("registers outside the 20 that moved: %d" % len(r["other_regs"]))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"log": a.log, "blocks": r["blocks"], "tests": len(r["tests"]),
                       "completed": r["completed"], "registers": out,
                       "other_offsets": sorted(r["other_regs"])}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
