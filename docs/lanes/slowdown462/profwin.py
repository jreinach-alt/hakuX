#!/usr/bin/env python3
"""Flips and fps inside a held session's profile window, from its logcat.

    profwin.py <session dir>

The window is the `prof start` / `prof end` hakuX-route lines that
capture_profile.sh writes. Each hakuX-perf `gfps=` line closes 60 flips, so
the flips in the window are 60 x (lines after the first one in it), over the
time between the first and the last of those lines. Prints the gfps values
too, so a window that changed scene shows it.
"""
import re
import sys
from datetime import datetime

d = sys.argv[1]
ts = lambda l: datetime.strptime(l[:18], "%m-%d %H:%M:%S.%f")
start = end = None
lines = []
for l in open(f"{d}/logcat.txt", errors="replace"):
    if "hakuX-route" in l and "prof start" in l:
        start = ts(l)
    elif "hakuX-route" in l and "prof end" in l:
        end = ts(l)
    elif "hakuX-perf" in l and "gfps=" in l:
        lines.append((ts(l), int(re.search(r"gfps=(\d+)", l).group(1))))
if not (start and end):
    sys.exit("no prof start/end in logcat")
inw = [x for x in lines if start <= x[0] <= end]
if len(inw) < 2:
    sys.exit(f"{len(inw)} gfps lines in the window")
span = (inw[-1][0] - inw[0][0]).total_seconds()
flips = 60 * (len(inw) - 1)
print(f"window {start:%H:%M:%S}-{end:%H:%M:%S} ({(end - start).total_seconds():.1f} s); "
      f"{flips} flips in {span:.1f} s = {flips / span:.2f} fps, {1000 * span / flips:.1f} ms/flip")
print("gfps:", " ".join(str(g) for _, g in inw))
