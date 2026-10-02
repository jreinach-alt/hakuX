#!/usr/bin/env python3
"""Split a Forza soak's logcat into fixed windows after `mark play`.

lane.forzadecay414, section 13: what changes at the +11 min step. One row per
window: fps, guest frame time G and its spread, pacing divisor counts, guest
idle from [rr425w], host vCPU run time from [idlehalt], pipeline misses from
[shd413], the invalid list, the txw scan, page-invalidator traffic, tier1
drops, and the surface-update rate. Usage:

  step_split.py <result dir> [--win 60] [--end 1300]
"""
import argparse
import datetime
import os
import re
import statistics as st

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--win", type=float, default=60.0)
ap.add_argument("--end", type=float, default=1300.0)
a = ap.parse_args()

YEAR = 2026


def ts(s):
    return datetime.datetime.strptime(f"{YEAR}-{s}", "%Y-%m-%d %H:%M:%S.%f")


mark = None
for line in open(os.path.join(a.dir, "run.log"), errors="replace"):
    m = re.match(r"ROUTE (\d+:\d+:\d+\.\d+) mark play", line)
    if m:
        mark = m.group(1)
assert mark, "no mark play"
date = None
rows = {}


def row(t):
    k = int(t // a.win)
    return rows.setdefault(k, {})


def add(r, key, v):
    r.setdefault(key, []).append(v)


for line in open(os.path.join(a.dir, "logcat.txt"), errors="replace"):
    m = re.match(r"(\d\d-\d\d) (\d\d:\d\d:\d\d\.\d+) ", line)
    if not m:
        continue
    if date is None:
        date = m.group(1)
        t0 = ts(f"{date} {mark}")
    t = (ts(f"{m.group(1)} {m.group(2)}") - t0).total_seconds()
    if t < 0 or t > a.end:
        continue
    r = row(t)
    if "hakuX-perf" in line and " gfps=" in line:
        g = re.search(r"gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\) D:([\d.]+).*? S:([\d.]+) J:([\d.]+) Df:(\d+).*?Ri:([\d.]+) Tq:(\d+)", line)
        if g:
            for i, k in enumerate(["gfps", "G", "Gmin", "Gmax", "D", "S", "J", "Df", "Ri", "Tq"]):
                add(r, k, float(g.group(i + 1)))
    elif "hakuX-pace" in line:
        g = re.search(r"v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+) max=([\d.]+) ms=([\d.]+)", line)
        if g:
            for i, k in enumerate(["v0", "v1", "v2", "v3", "v4", "vb", "pmax", "pms"]):
                add(r, k, float(g.group(i + 1)))
    elif "[rr425w]" in line:
        g = re.search(r"idle_us=(\d+) busy_us=(\d+)", line)
        if g:
            i, b = int(g.group(1)), int(g.group(2))
            add(r, "gidle", 100.0 * i / max(1, i + b))
    elif "[idlehalt]" in line:
        g = re.search(r"span_us=(\d+) run_us=(\d+)", line)
        if g:
            add(r, "vrun", 100.0 * int(g.group(2)) / max(1, int(g.group(1))))
    elif "[shd413]" in line:
        g = re.search(r"dpm=(\d+).*?dsm=(\d+).*?dvm=(\d+)", line)
        if g:
            add(r, "pmiss", sum(int(x) for x in g.groups()))
    elif "[watch311]" in line:
        g = re.search(r"invalid=(\d+)", line)
        if g:
            add(r, "invalid", int(g.group(1)))
    elif "[rdc]" in line:
        g = re.search(r"tcpu=([\d.]+)", line)
        if g:
            add(r, "rtcpu", float(g.group(1)))
    elif "hakuX-pages" in line and "slow stores" in line:
        g = re.search(r"slow stores (\d+)", line)
        if g:
            add(r, "slow", int(g.group(1)))
    elif "requests FULL" in line:
        add(r, "t1drop", 1)
    elif "[surf92]" in line:
        add(r, "surf92", 1)
    elif "fifoskew" in line:
        g = re.search(r"kicks=(\d+)", line)
        if g:
            add(r, "kicks", int(g.group(1)))
    elif "starve:" in line:
        g = re.search(r"= ([\d.]+)% of output", line)
        if g:
            add(r, "starve", float(g.group(1)))

cols = [("gfps", "med"), ("G", "med"), ("Gmax", "max"), ("D", "med"), ("S", "med"),
        ("J", "med"), ("Ri", "med"), ("Tq", "med"), ("v1", "sum"), ("v2", "sum"),
        ("v3", "sum"), ("v4", "sum"), ("gidle", "mean"), ("vrun", "mean"),
        ("rtcpu", "mean"), ("pmiss", "sum"), ("invalid", "max"), ("slow", "sum"),
        ("t1drop", "sum"), ("surf92", "sum"), ("kicks", "sum"), ("starve", "max")]
print("t0 " + " ".join(f"{c:>7}" for c, _ in cols))
for k in sorted(rows):
    r = rows[k]
    out = []
    for c, how in cols:
        v = r.get(c)
        if not v:
            out.append(f"{'-':>7}")
            continue
        x = {"med": st.median, "max": max, "sum": sum, "mean": st.mean}[how](v)
        out.append(f"{x:7.1f}")
    print(f"{int(k * a.win):<4}" + " ".join(out))
