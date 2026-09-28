#!/usr/bin/env python3
"""Summarise [adpf-probe] lines from a dispatch result's logcat by phase.

Usage: probe_summary.py <request id>
Prints per phase the mean and range of ipus, the share of periods per CPU,
uclamp.min and policy cur/min MHz, then high-minus-none paired by cycle.
"""
import os, re, sys, statistics as st

d = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
path = os.path.join(d, "results", sys.argv[1], "logcat.txt")
pat = re.compile(r"\[adpf-probe\] ph=(\w+) n=(\d+) ipus=([\d.]+) cpu=([\d/]+) "
                 r"um=(-?\d+) err=(\d+) p0=(-?\d+)/(-?\d+) p3=(-?\d+)/(-?\d+) "
                 r"p7=(-?\d+)/(-?\d+)")
rows = []
for line in open(path, errors="replace"):
    m = pat.search(line)
    if m:
        g = m.groups()
        rows.append(dict(ph=g[0], n=int(g[1]), ipus=float(g[2]),
                         cpu=[int(x) for x in g[3].split("/")], um=int(g[4]),
                         err=int(g[5]), p3=int(g[8]), p3min=int(g[9]),
                         p7=int(g[10]), p7min=int(g[11])))
print("phase  k  ipus mean [min-max]   cpu share % (0..7)            um  err  p3 cur  p7 cur  p3/p7 min")
for ph in ("none", "low", "high"):
    r = [x for x in rows if x["ph"] == ph]
    tot = [sum(x["cpu"][i] for x in r) for i in range(8)]
    share = "/".join("%d" % round(100 * t / sum(tot)) for t in tot)
    print("%-5s %2d  %5.1f [%5.1f-%5.1f]  %-28s  %s  %d  %6.0f  %6.0f  %s/%s" % (
        ph, len(r), st.mean(x["ipus"] for x in r), min(x["ipus"] for x in r),
        max(x["ipus"] for x in r), share, sorted({x["um"] for x in r}),
        sum(x["err"] for x in r), st.mean(x["p3"] for x in r),
        st.mean(x["p7"] for x in r), sorted({x["p3min"] for x in r}),
        sorted({x["p7min"] for x in r})))
# pair each high with the none that opened its cycle
cyc, cur = [], {}
for x in rows:
    if x["ph"] == "none" and cur:
        cyc.append(cur); cur = {}
    cur[x["ph"]] = x
if cur:
    cyc.append(cur)
dif = [c["high"]["ipus"] - c["none"]["ipus"] for c in cyc if "high" in c and "none" in c]
print("high - none ipus per cycle:", " ".join("%+.1f" % v for v in dif))
print("mean %+.1f, positive in %d of %d cycles" % (st.mean(dif), sum(v > 0 for v in dif), len(dif)))
