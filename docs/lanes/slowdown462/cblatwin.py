#!/usr/bin/env python3
"""lane.flip474's [cblat] split, summed over a held session's profile window.

    cblatwin.py <session dir>

[cblat] (hakuX-perf `cblat win=... flips=N ... split(k=v ...)`, 76cba82fd2
perflog) writes, every ~2 s, the ms each part of the push-buffer callback's
kick-to-dispatch spans took (wall time on the PFIFO thread). Summed over the
lines inside `prof start` / `prof end` and divided by their flips, it gives
[cblat]'s ms/frame for the same seconds the profile sampled, so the two
instruments read one window.
"""
import re
import sys
from collections import Counter
from datetime import datetime

d = sys.argv[1]
ts = lambda l: datetime.strptime(l[:18], "%m-%d %H:%M:%S.%f")
start = end = None
rows = []
for l in open(f"{d}/logcat.txt", errors="replace"):
    if "hakuX-route" in l and "prof start" in l:
        start = ts(l)
    elif "hakuX-route" in l and "prof end" in l:
        end = ts(l)
    elif "hakuX-perf" in l and " cblat win=" in l:
        m = re.search(r"split\(([^)]*)\)", l)
        f = re.search(r"flips=(\d+)", l)
        if m and f:
            kv = Counter({k: float(v) for k, v in (x.split("=") for x in m.group(1).split())})
            rows.append((ts(l), int(f.group(1)), kv))
if not (start and end):
    sys.exit("no prof start/end in logcat")
inw = [r for r in rows if start <= r[0] <= end]
flips = sum(r[1] for r in inw)
tot = Counter()
for _, _, kv in inw:
    tot.update(kv)
print(f"{len(inw)} cblat lines, {flips} flips in {start:%H:%M:%S}-{end:%H:%M:%S}")
for k, v in tot.most_common():
    print(f"  {k:7s} {v:9.1f} ms  {v / max(flips, 1):7.2f} ms/frame")
