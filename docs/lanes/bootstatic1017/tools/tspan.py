#!/usr/bin/env python3
"""Summarise the probe's texture numbers (tnb/tlit/tgrn) and window numbers over runs of the same SR01 screen state.

usage: tspan.py <probe dir>
One line per maximal run of presents with the same (start, sr01): presents, ms, and min/median/max of tlit, tnb, and
the window's lit. Answers "what would a present path with no screen-off check draw in each window".
"""
import os
import re
import sys

KV = re.compile(r"(\w+)=(\S+)")


def mmm(v):
    v = sorted(v)
    return "%.3f/%.3f/%.3f" % (v[0], v[len(v) // 2], v[-1]) if v else "-"


def main():
    d = sys.argv[1]
    rows = []
    with open(os.path.join(d, "boot1045_log.txt"), errors="replace") as f:
        for line in f:
            kv = dict(KV.findall(line))
            if "n" in kv and "src" in kv:
                rows.append(kv)
    spans = []
    for kv in rows:
        k = (kv.get("start"), kv.get("sr01"), kv.get("vga"))
        if spans and spans[-1][0] == k:
            spans[-1][1].append(kv)
        else:
            spans.append((k, [kv]))
    for (start, sr01, vga), seg in spans:
        t0, t1 = float(seg[0]["t_ms"]), float(seg[-1]["t_ms"])
        tl = [float(r.get("tlit", "-1")) for r in seg if float(r.get("tlit", "-1")) >= 0]
        tn = [float(r.get("tnb", "-1")) for r in seg if float(r.get("tnb", "-1")) >= 0]
        wl = [float(r["lit"]) for r in seg]
        print("n %5s-%5s %8.1f-%8.1f ms %5d x start=%s sr01=%s vga=%s  tlit %s  tnb %s  window lit %s" % (
            seg[0]["n"], seg[-1]["n"], t0, t1, len(seg), start, sr01, vga, mmm(tl), mmm(tn), mmm(wl)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
