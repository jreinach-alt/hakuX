#!/usr/bin/env python3
"""Read a doa413b soak A/B: per 60-frame [surf413] line, gfps and the segment columns.

Usage: ab_read.py <result dir> [<result dir> ...]
Prints every [surf413] line's parsed fields as a table, the [lazy413] counters,
and the median gfps / cdef / Surf over the lines with gfps < 20 (the fight window).
"""
import json
import os
import re
import statistics
import sys

KV = re.compile(r"(\w+)=([-\d.]+)")


def read(rdir):
    res = json.load(open(os.path.join(rdir, "result.json")))
    req = json.load(open(os.path.join(rdir, "request.json")))
    print("==", os.path.basename(rdir))
    print("  state", res.get("state") or res.get("status"), "device", res.get("device") or req.get("device"),
          "env", req.get("env"), "ref", req.get("ref"))
    rows = []
    lazy = []
    perf = []
    with open(os.path.join(rdir, "logcat.txt"), errors="replace") as f:
        for line in f:
            if "[lazy413]" in line:
                lazy.append(line.strip())
            if "[surf413]" in line and "xemu-surf" not in line:
                d = {k: float(v) for k, v in KV.findall(line.split("[surf413]", 1)[1])}
                d["_t"] = line[:18]
                rows.append(d)
            if "[perf]" in line or "gfps" in line and "[surf413]" not in line:
                perf.append(line.strip())
    print("  lazy413:", lazy[-1] if lazy else "NONE", "(%d lines)" % len(lazy))
    if rows:
        print("  surf413 keys:", sorted(k for k in rows[0] if k != "_t"))
    return rows, perf


def secs(t):
    # "09-26 20:12:19.413" -> seconds of day
    hh, mm, ss = t.split()[1].split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(ss)


def main():
    verbose = "-v" in sys.argv
    for rdir in [a for a in sys.argv[1:] if a != "-v"]:
        rows, perf = read(rdir)
        print("  %d surf413 lines" % len(rows))
        # Each line covers 60 guest frames, so fps = 60 / (gap to the previous line).
        fight = []
        for prev, r in zip(rows, rows[1:]):
            dt = secs(r["_t"]) - secs(prev["_t"])
            fps = 60.0 / dt if dt > 0 else 0.0
            ms = 1000.0 / fps if fps else 0.0
            if verbose:
                print("   %s fps=%.1f cdef=%.2f lazy=%d active=%d"
                      % (r["_t"], fps, r["cdef"], r.get("lazy", 0), r["active"]))
            # Fight window: 6 active surfaces (the fight's set) and under 25 fps.
            if r["active"] == 6 and fps < 25:
                fight.append((fps, r["cdef"], ms, r.get("lazy", 0)))
        if fight:
            med = lambda i: statistics.median(x[i] for x in fight)
            print("  fight lines %d: median fps %.1f (min %.1f max %.1f), cdef %.1f ms/frame, "
                  "frame %.1f ms, lazy/60f %.0f"
                  % (len(fight), med(0), min(x[0] for x in fight), max(x[0] for x in fight),
                     med(1), med(2), med(3)))


if __name__ == "__main__":
    main()
