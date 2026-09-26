#!/usr/bin/env python3
"""List the four-literal selector fits that survive ClipF-300-008 (#31).

    python3 docs/lanes/wbuf31sel/fits57.py

Adds ClipF-300-008 to wbuf_anchor_recover.py's PRIMS the way
docs/lanes/xbox/score_clipf300.py (PR #243) does, runs the tool's
--selectors search over the goldens plus every 2026-09-25 silicon run, and
prints each surviving 'a | (b & (c | d))' fit with the literals it reads.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
import wbuf_anchor_recover as w  # noqa: E402

RUNS = "/home/justin/hakux-work/hardware/runs"
ROOTS = [os.path.join(RUNS, "2026-09-25-wbuf31-%s" % n, "console-run", "console")
         for n in ("c300", "clipf35", "clipf04", "t0")]
ROOTS.append("/home/justin/goldens/results")

w.PRIMS.setdefault("ClipF-300-008", (w.FLOOR, 300, 8, "FloorQuad"))
w._QUADS.add("ClipF-300-008")


def main():
    got = {}
    real = w._selectors

    def keep(rows):
        got["fit4"] = real(rows)
        return got["fit4"]

    w._selectors = keep
    argv = []
    for r in ROOTS:
        argv += ["--goldens", r]
    rc = w.main(["--selectors"] + argv + sys.argv[1:])
    w._selectors = real
    if rc or "fit4" not in got:
        return 2

    def nm(l):
        return ("" if l[1] else "!") + l[0]

    print()
    print("SURVIVING FITS (%d)" % len(got["fit4"]))
    for a, b, c, d in got["fit4"]:
        print("  %s | (%s & (%s | %s))" % (nm(a), nm(b), nm(c), nm(d)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
