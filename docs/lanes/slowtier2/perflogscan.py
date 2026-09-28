#!/usr/bin/env python3
"""Which results of the phase-2 titles carry perflog lines at all.

    perflogscan.py

For every result index.py lists, counts hakuX-phase, xemu-gpu, hakuX-stall,
hakuX-pace and [idlehalt] lines in its logcat. A soak whose request did not
ask for a perflog build logs none of the first three, whatever its logcat
spec says.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index  # noqa: E402

D = index.D
TAGS = ["hakuX-phase", "xemu-gpu", "hakuX-stall", "hakuX-pace", "[idlehalt]"]
pats = [re.compile(p, re.I) for p in index.TITLES]
for d in sorted(os.listdir(f"{D}/results")):
    r = index.load(f"{D}/results/{d}/result.json")
    if not r or not r.get("title") or not any(p.search(r["title"]) for p in pats):
        continue
    lc = f"{D}/results/{d}/logcat.txt"
    if not os.path.exists(lc):
        continue
    n = dict.fromkeys(TAGS, 0)
    for line in open(lc, errors="replace"):
        for t in TAGS:
            if t in line:
                n[t] += 1
    if n["hakuX-phase"] or n["xemu-gpu"] or n["hakuX-stall"] or n["[idlehalt]"]:
        print(d, r["title"][:40], r.get("device_label"), r.get("ref"), n)
