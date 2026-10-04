#!/usr/bin/env python3
"""Print the lines of a result's logcat matching patterns (scratch reader)."""
import os
import re
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results/"
rid, pats = sys.argv[1], sys.argv[2:]
p = rid if os.path.exists(rid) else D + rid
if os.path.isdir(p):
    print(sorted(os.listdir(p)))
    p = os.path.join(p, "logcat.txt")
lim = int(os.environ.get("N", "8"))
lines = open(p, errors="replace").read().splitlines()
print("lines", len(lines))
for pat in pats:
    rx = re.compile(pat)
    hit = [l for l in lines if rx.search(l)]
    print("== %s: %d" % (pat, len(hit)))
    for l in hit[:lim]:
        print("  ", l[:220])
    if len(hit) > lim:
        for l in hit[-3:]:
            print(" $", l[:220])
