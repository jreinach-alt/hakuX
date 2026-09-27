#!/usr/bin/env python3
"""Print a result dir's composition and its scores for the X1A7 arm's suites.

    python3 docs/lanes/cloud-271/base_rows.py <result dir> [suite ...]
"""
import json
import os
import sys

R = sys.argv[1]
SUITES = sys.argv[2:] or ["Blend_surface", "Surface_format", "Clear"]
for f in ("suites.txt", "skip_tests.txt", ".only_tests"):
    p = os.path.join(R, f)
    if os.path.exists(p):
        print("%s: %s" % (f, open(p).read().strip().replace("\n", " | ")[:600]))
rq = json.load(open(os.path.join(R, "request.json")))
for k in ("ref", "device", "apk_sha", "id"):
    if k in rq:
        print("%s: %s" % (k, rq[k]))
for n in ("scores1.tsv", "scores2.tsv"):
    p = os.path.join(R, n)
    if not os.path.exists(p):
        continue
    lines = open(p).read().splitlines()
    print("==", n, "|", lines[0])
    for l in lines[1:]:
        if l.split("\t")[0] in SUITES:
            print(l)
