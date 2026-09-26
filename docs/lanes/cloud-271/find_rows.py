#!/usr/bin/env python3
"""List the newest result dirs scoring a given capture, newest first.

    python3 docs/lanes/cloud-271/find_rows.py Clear SCF_X1A7R8G8B8_O1A7R8G8B8 [N]
"""
import glob
import os
import sys

suite, test = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 12
R = "/home/justin/hakux-work/dispatch/results"
hits = []
for p in glob.glob(R + "/*/scores1.tsv"):
    for l in open(p, errors="replace"):
        f = l.rstrip("\n").split("\t")
        if len(f) > 9 and f[0] == suite and f[1] == test:
            hits.append((os.path.getmtime(p), os.path.dirname(p), f))
            break
hits.sort(reverse=True)
for t, d, f in hits[:n]:
    print("%s  differing=%s status=%s apk=%s disc=%s" % (
        os.path.basename(d), f[4], f[3], f[9], f[10] if len(f) > 10 else ""))
