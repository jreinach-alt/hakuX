#!/usr/bin/env python3
"""One row per 60-flip window of a perflog soak, for a title whose frame time
has more than one regime (GTA: San Andreas, #462).

    regimes.py <result-id> [--from S] [--to S] [--split MS]

Each hakuX-perf `gfps=` line closes a window of 60 guest flips. The row joins
it to the lines logged with it (hakuX-pace, hakuX-phase, hakuX-cpu) and to the
nearest earlier `[tlb68]`, hakuX-stall and hakuX-audiocap lines. It does
not read hakuX-pages: that line counts "since last" over a span that is not
the 60-flip window (2 s at 30 fps, 12 s at 5), so its counts do not compare
between regimes. Use tbchurn424/churn.py, which gives rates per second. Times are seconds after logcat line 1, the base
timeline.py prints.

With --split, the windows are put in two groups by ms per flip (pace `ms` /
60) and each column's median is printed per group, with the share of the
wall time each group took. A window's `max` is its slowest single frame, so
spikes are counted from it: a spike is a frame over --spike ms (default 700).
"""
import argparse
import os
import re
import statistics
import sys
from datetime import datetime

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\w/([\w-]+)\s*\(\s*\d+\): (.*)$")


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f").timestamp()


def num(pat, s, cast=float):
    m = re.search(pat, s)
    return cast(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rid")
    ap.add_argument("--from", dest="frm", type=float, default=0.0)
    ap.add_argument("--to", type=float, default=1e9)
    ap.add_argument("--split", type=float, default=None)
    ap.add_argument("--spike", type=float, default=700.0)
    ap.add_argument("--quiet", action="store_true", help="medians only, no rows")
    a = ap.parse_args()
    t0 = None
    last = {}
    rows = []
    cur = None
    for line in open(f"{D}/results/{a.rid}/logcat.txt", errors="replace"):
        m = TS.match(line)
        if not m:
            continue
        t = ts(m.group(1))
        if t0 is None:
            t0 = t
        tag, msg = m.group(2), m.group(3)
        if tag == "hakuX" and msg.startswith("[tlb68]"):
            dt = num(r"dt=(\d+)", msg)
            last["vcpu"] = 100.0 * num(r"cpu=(\d+)", msg) / dt if dt else None
            last["pf"] = num(r" pf=(\d+)", msg) * 1000.0 / dt if dt else None
            last["cr3s"] = num(r"cr3s=(\d+)", msg) * 1000.0 / dt if dt else None
        elif tag == "hakuX-stall" and msg.startswith("RPBreaks"):
            last["stl"] = num(r" stl(\d+)", msg)
            last["cdef"] = num(r"cDef(\d+)", msg)
        elif tag == "hakuX-audiocap" and msg.startswith("starve"):
            last["starve"] = num(r"= ([\d.]+)% of output", msg)
        elif tag == "hakuX-perf" and msg.startswith("gfps="):
            cur = dict(last)
            cur["t"] = t - t0
            cur["G"] = num(r"G:([\d.]+)", msg)
            cur["vpf"] = num(r"Vpf:([\d.]+)", msg)
            rows.append(cur)
        elif cur is not None and abs(t - t0 - cur["t"]) < 0.05:
            if tag == "hakuX-pace":
                cur["ms"] = num(r" ms=([\d.]+)", msg) / 60.0
                cur["max"] = num(r"max=([\d.]+)", msg)
            elif tag == "hakuX-phase":
                cur["tot"] = num(r"Tot:([\d.]+)", msg)
                cur["idle"] = num(r"Idle:([\d.]+)", msg)
                cur["st"] = num(r"St:([\d.]+)\)", msg)
                cur["shd"] = num(r"Shd:([\d.]+)", msg)
                cur["pipe"] = num(r"Pipe:([\d.]+)", msg)
                cur["draw"] = num(r"Draw:([\d.]+)", msg)
                cur["fin"] = num(r"Fin:([\d.]+)", msg)
                cur["gpu"] = num(r"GPU:([\d.]+)", msg)
            elif tag == "hakuX-cpu":
                cur["kicks"] = num(r"K:(\d+)", msg)
                cur["words"] = num(r"W:([\d.]+)K", msg)
                cur["pull"] = num(r"Pull:([\d.]+)", msg)
    rows = [r for r in rows if a.frm <= r["t"] <= a.to and "ms" in r]
    cols = ["t", "ms", "max", "vpf", "vcpu", "tot", "idle", "st", "draw", "pipe", "shd",
            "fin", "gpu", "kicks", "words", "pull", "stl", "cdef", "pf",
            "cr3s", "starve"]
    if not a.quiet:
        print(" ".join("%7s" % c for c in cols))
        for r in rows:
            print(" ".join("%7s" % ("-" if r.get(c) is None else "%.1f" % r[c]) for c in cols))
    if a.split is None:
        return
    wall = sum(r["ms"] * 60 for r in rows)
    print("\nwindows %d, wall %.1f s, split at %.0f ms/flip, spike = a window whose slowest frame is over %.0f ms"
          % (len(rows), wall / 1000, a.split, a.spike))
    for name, grp in (("fast", [r for r in rows if r["ms"] < a.split]),
                      ("slow", [r for r in rows if r["ms"] >= a.split])):
        if not grp:
            print(name, "none")
            continue
        w = sum(r["ms"] * 60 for r in grp)
        spikes = [r["max"] for r in grp if r["max"] >= a.spike]
        print("%s: %d windows (%d flips), %.1f s = %.0f%% of the wall; spikes %d (%s ms)" % (
            name, len(grp), 60 * len(grp), w / 1000, 100 * w / wall, len(spikes),
            " ".join("%.0f" % s for s in spikes)))
        # What the group lost above its own steady frame: each window's wall
        # minus 60 flips at the group's median ms per flip, floored at 0.
        med = statistics.median(r["ms"] for r in grp)
        exc = sum(max(0.0, (r["ms"] - med) * 60) for r in grp)
        spk = sum(r["max"] - med for r in grp if r["max"] >= a.spike)
        print("   steady %.1f ms/flip; time above it %.1f s (%.0f%% of the group's wall); of that, the spike frames %.1f s"
              % (med, exc / 1000, 100 * exc / w, spk / 1000))
        print("   " + "  ".join("%s %.1f" % (c, statistics.median(r[c] for r in grp if r.get(c) is not None))
                                for c in cols[1:] if any(r.get(c) is not None for r in grp)))


if __name__ == "__main__":
    sys.exit(main())
