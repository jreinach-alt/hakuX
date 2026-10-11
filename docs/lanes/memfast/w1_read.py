#!/usr/bin/env python3
"""W1's soak legs (#507, lane.memfast): what the per-page watch flush did, per
run, from the [tlb68] and [watch311] lines over the whole run.

    w1_read.py <result dir | logcat.txt> [...]

Per run, per second of wall time (sum of dt= over the [tlb68] lines):

  fo        full flushes tagged "other": on a build without W1, one per watch
            insert and one per remove
  ff        full flushes, all causes
  pf, pfl   INVLPG page flushes, and those that flushed a whole mode because
            the page fell in its recorded large-page region (W1 can widen
            that region's life: only a full flush resets it)
  inserts   NV2A surface-watch inserts ([watch311] inserts=, a running total;
            last minus first)
  wn        W1 walks (one per insert and one per remove); absent before W1
  wh        entries the walks dropped
  wx        entries only the host-pointer cross-check dropped. Must be 0
  wus       microseconds spent walking
  cpu       the vCPU thread's CPU ms per wall second (sum cpu= / sum dt=)

and w1=, the switch as the build read it, on every line (a set of values).

A run with no [tlb68] line is VOID, not zero.
"""
import os
import re
import sys

KV = re.compile(r"(\w+)=(-?\d+)\b")


def read(path):
    if os.path.isdir(path):
        path = os.path.join(path, "logcat.txt")
    tlb, inserts = [], []
    with open(path, errors="replace") as f:
        for ln in f:
            i = ln.find("[tlb68] w=")
            if i >= 0:
                tlb.append({k: int(v) for k, v in KV.findall(ln[i:])})
                continue
            i = ln.find("[watch311] live=")
            if i >= 0:
                m = re.search(r"inserts=(\d+)", ln[i:])
                if m:
                    inserts.append(int(m.group(1)))
    return tlb, inserts


def summary(path):
    tlb, ins = read(path)
    if not tlb:
        return {"void": "no [tlb68] line"}
    wall = sum(r.get("dt", 0) for r in tlb) / 1000.0
    out = {"lines": len(tlb), "wall_s": round(wall, 1),
           "w1": sorted({r["w1"] for r in tlb if "w1" in r}) or None,
           "watch_lines": len(ins)}
    for k in ("fo", "ff", "pf", "pfl", "wn", "wh", "wx", "wus", "cpu"):
        if any(k in r for r in tlb):
            out[k + "_per_s"] = round(sum(r.get(k, 0) for r in tlb) / wall, 2)
    out["wx_max_line"] = max((r.get("wx", 0) for r in tlb), default=0)
    if len(ins) >= 2:
        out["inserts_per_s"] = round((ins[-1] - ins[0]) / wall, 2)
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for p in sys.argv[1:]:
        print("==", p)
        for k, v in summary(p).items():
            print("  %-14s %s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
