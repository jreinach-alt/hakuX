#!/usr/bin/env python3
"""Read the [mf0] census lines (lane.memfast phase 0, #507) from result dirs.

    mf0_read.py <result dir | logcat.txt> [...]

Per run: the line count, the wall time after the fast path activated (act=1)
and the share of it with no mem-access callback live (cb0ms: the path armed),
the install counts in the low window (li/ln/lo: identity / other RAM page /
device) and in the BAR1 window (vi/vn/vo), the distinct non-identity pages
(lnd/vnd, cumulative), and the `[mf0] first` samples.

A run with no [mf0] line is VOID, not zero: the census was not in that binary
or the logcat lost the hakuX tag.
"""
import os
import re
import sys

LINE = re.compile(r"\[mf0\] w=(\d+) (.*)")
FIRST = re.compile(r"\[mf0\] first (.*)")
KV = re.compile(r"(\w+)=(-?0x[0-9a-f]+|-?\d+)")


def read(path):
    if os.path.isdir(path):
        path = os.path.join(path, "logcat.txt")
    rows, firsts = [], []
    with open(path, errors="replace") as f:
        for ln in f:
            m = LINE.search(ln)
            if m:
                rows.append({k: int(v, 0) for k, v in KV.findall(m.group(2))})
                continue
            m = FIRST.search(ln)
            if m:
                firsts.append(m.group(1).strip())
    return path, rows, firsts


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    for arg in argv:
        path, rows, firsts = read(arg)
        print("== %s" % path)
        if not rows:
            print("  VOID: no [mf0] line")
            continue
        # act and cb0ms are separate facts. cb0ms reads -1 on every line of the
        # runs so far (the cb==0 span opens at the first insert and never
        # closes), and keying act on it printed "never activated" for runs
        # with act=1 on every line. The armed time is bounded from cb/up/dn:
        # a window that ends with cb > 0 and saw no transition held cb > 0
        # throughout; any other window may have been armed for all of its dt.
        act = [r for r in rows if r.get("act") == 1]
        tot = {k: sum(r.get(k, 0) for r in rows)
               for k in ("li", "ln", "lo", "vi", "vn", "vo", "up", "dn")}
        print("  lines=%d act_lines=%d" % (len(rows), len(act)))
        if act:
            wall = sum(r["dt"] for r in act)
            maybe = [r for r in act
                     if r.get("cb", 0) == 0 or r.get("up", 0) or r.get("dn", 0)]
            bound = sum(r["dt"] for r in maybe)
            print("  after act=1: wall=%.1fs armed(cb=0)<=%.1fs share<=%.4f "
                  "(windows that could hold cb=0: %s)"
                  % (wall / 1e3, bound / 1e3, bound / wall if wall else 0.0,
                     ",".join("w%d" % rows.index(r) for r in maybe) or "none"))
            if any(r.get("cb0ms", -1) >= 0 for r in act):
                armed = sum(min(r["cb0ms"], r["dt"]) for r in act
                            if r.get("cb0ms", -1) >= 0)
                print("  cb0ms (where printed): armed=%.1fs" % (armed / 1e3))
            print("  cb at last line=%d, max=%d, min=%d"
                  % (act[-1].get("cb", -1), max(r.get("cb", -1) for r in act),
                     min(r.get("cb", -1) for r in act)))
        else:
            print("  never act=1 (the path was never activated)")
        print("  installs low: id=%d nid=%d io=%d   bar1: id=%d nid=%d io=%d"
              % (tot["li"], tot["ln"], tot["lo"], tot["vi"], tot["vn"], tot["vo"]))
        print("  distinct nid pages at end: low=%d bar1=%d   cb 0->1=%d 1->0=%d"
              % (rows[-1].get("lnd", 0), rows[-1].get("vnd", 0),
                 tot["up"], tot["dn"]))
        print("  vram_pci_base=0x%x" % rows[-1].get("vb", 0))
        for s in firsts:
            print("  first: %s" % s)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
