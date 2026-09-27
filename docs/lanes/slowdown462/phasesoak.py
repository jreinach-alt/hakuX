#!/usr/bin/env python3
"""phasewin.py's means, over a soak's window in seconds instead of a profile's.

    phasesoak.py <result dir> <from s> <to s>

Seconds count from the first hakuX-route line, as txwwin.py does. Prints
the mean of every `Name:value` field of the hakuX-phase lines in the window.
"""
import re
import sys
from collections import defaultdict
from datetime import datetime

d, lo, hi = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
ts = lambda l: datetime.strptime(l[:18], "%m-%d %H:%M:%S.%f")
t0 = None
vals = defaultdict(list)
n = 0
for l in open(f"{d}/logcat.txt", errors="replace"):
    if t0 is None and "hakuX-route" in l:
        t0 = ts(l)
    if t0 and "hakuX-phase" in l and lo <= (ts(l) - t0).total_seconds() <= hi:
        n += 1
        for k, v in re.findall(r"([A-Za-z.]+):([0-9.]+)", l.split("): ", 1)[1]):
            vals[k].append(float(v))
print(f"{n} phase lines in {lo:.0f}-{hi:.0f} s")
print(", ".join(f"{k} {sum(v) / len(v):.1f}" for k, v in vals.items()))
