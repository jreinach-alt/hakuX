#!/usr/bin/env python3
"""Flips and fps between two hakuX-route markers of a held session's logcat.

    winfps.py <session dir> [start marker] [end marker]

Defaults: 'prof start' .. 'prof on end' (capture_gta.sh's on-CPU record);
'prof on end' .. 'prof off end' is the off-CPU record. Same arithmetic as
docs/lanes/slowdown462/profwin.py: each hakuX-perf `gfps=` line closes 60
flips, so the flips in the window are 60 x (lines after the first one in it)
over the time between the first and last of those lines. Also prints the
hakuX-pace VBLANKs-per-flip (`Vpf`) values in the window.
"""
import re
import sys
from datetime import datetime

d = sys.argv[1]
m0 = sys.argv[2] if len(sys.argv) > 2 else "prof start"
m1 = sys.argv[3] if len(sys.argv) > 3 else "prof on end"
ts = lambda l: datetime.strptime(l[:18], "%m-%d %H:%M:%S.%f")
start = end = None
lines = []
for l in open(f"{d}/logcat.txt", errors="replace"):
    if "hakuX-route" in l and l.rstrip().endswith(m0):
        start = ts(l)
    elif "hakuX-route" in l and l.rstrip().endswith(m1) and start:
        end = ts(l)
        break
    elif start and "hakuX-perf" in l and "gfps=" in l:
        lines.append(l)
if not (start and end):
    sys.exit(f"markers {m0!r} / {m1!r} not both found")
if len(lines) < 2:
    sys.exit(f"{len(lines)} gfps lines in the window: too few to count flips")
t = [ts(l) for l in lines]
span = (t[-1] - t[0]).total_seconds()
flips = 60 * (len(lines) - 1)
g = [re.search(r"gfps=(\d+)", l).group(1) for l in lines]
v = [re.search(r"Vpf:([\d.]+)", l).group(1) for l in lines if "Vpf:" in l]
print(f"{m0} {start:%H:%M:%S} .. {m1} {end:%H:%M:%S}: {flips} flips in {span:.1f} s = "
      f"{flips / span:.2f} fps, {1000 * span / flips:.1f} ms/flip; gfps {' '.join(g)}; Vpf {' '.join(v)}")
