#!/usr/bin/env python3
"""Print a result's files, route marks and a sampled gfps/pace timeline.
Usage: timeline.py <result id> [every-nth-line]"""
import glob, os, re, sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
d = os.path.join(D, "results", sys.argv[1])
every = int(sys.argv[2]) if len(sys.argv) > 2 else 10
print("files:", sorted(os.listdir(d)))
n = 0
for lc in sorted(glob.glob(os.path.join(d, "*logcat*"))):
    for line in open(lc, errors="replace"):
        if "hakuX-route" in line or "[pace526]" in line or "[rate526]" in line:
            print(line.rstrip()[:260])
        elif "gfps=" in line:
            if n % every == 0:
                print(line.rstrip()[:200])
            n += 1
