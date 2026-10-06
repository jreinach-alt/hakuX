#!/usr/bin/env python3
"""Count hakuX-rpbrk lines and those that end a render pass for an
occlusion query (qry > 0), per run, over the whole logcat (lane.gpunonrender,
scope (D)). #527's rule: no sysmem default for a title whose sysmem run has
qry lines, since the ZPASS report a guest reads changes value in sysmem.

    qrycount.py <label>=<request-id> [...]
"""
import os, re, sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
RX = re.compile(r"RP:(\d+)\(fin\d+ fb\d+ qry(\d+)")
for arg in sys.argv[1:]:
    label, rid = arg.split("=", 1)
    n = q = mx = 0
    first = None
    with open(os.path.join(D, rid, "logcat.txt"), errors="replace") as f:
        for line in f:
            m = RX.search(line)
            if not m:
                continue
            n += 1
            v = int(m.group(2))
            if v > 0:
                q += 1
                mx = max(mx, v)
                first = first or line.strip()[:160]
    print("%-10s rpbrk %5d  qry_lines %4d  qry_max %d" % (label, n, q, mx))
    if first:
        print("    first:", first)
