#!/usr/bin/env python3
"""Leg R of region200-prediction.md: does the console reproduce #201's two constants?

    python3 docs/lanes/xbox/region200_rleg.py <pgraph_progress_log.txt>

#201 saw, on this console, SURFACE (0x710) bit 0 set in 53/53 observations and
TEXFMT0 (0x1A04) bits 4-5 equal to 3 in 40/40. An observation is one diff line
for the register; both its from and its to value must carry the bits. Prints
the counts and the first counter-example, if any. Writes nothing.
"""
import re
import sys

REG = re.compile(r"^0x([0-9A-Fa-f]{8}): 0x([0-9A-Fa-f]{8}) => 0x([0-9A-Fa-f]{8})\s*$")
CHECKS = (
    ("SURFACE bit 0 = 1", 0xFD400710, lambda v: v & 1 == 1),
    ("TEXFMT0 bits 4-5 = 3", 0xFD401A04, lambda v: (v >> 4) & 3 == 3),
)


def main(path):
    hits = {name: [0, 0, None] for name, _, _ in CHECKS}
    with open(path, errors="replace") as fh:
        for line in fh:
            m = REG.match(line.rstrip("\r\n"))
            if not m:
                continue
            addr, frm, to = (int(g, 16) for g in m.groups())
            for name, where, ok in CHECKS:
                if addr != where:
                    continue
                h = hits[name]
                h[0] += 1
                if ok(frm) and ok(to):
                    h[1] += 1
                elif h[2] is None:
                    h[2] = line.strip()
    bad = 0
    for name, (n, good, first) in hits.items():
        verdict = "NOT SEEN" if n == 0 else ("held" if good == n else "BROKEN")
        bad += verdict != "held"
        print("%-22s %d / %d observations  %s%s" % (
            name, good, n, verdict, "" if first is None else "; first counter-example: " + first))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
