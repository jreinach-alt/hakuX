#!/usr/bin/env python3
"""Print the titles-disk records (hdd.json / hdd.after.json / hdd.build.json) of result dirs."""
import json, os, sys

RES = os.path.expanduser("~/hakux-work/dispatch/results")
for rid in sys.argv[1:]:
    d = os.path.join(RES, rid)
    print("==", rid, "exists" if os.path.isdir(d) else "MISSING")
    if not os.path.isdir(d):
        continue
    names = sorted(os.listdir(d))
    print("   files:", " ".join(n for n in names if not n.endswith(".png"))[:600])
    for n in ("hdd.json", "hdd.build.json", "hdd.after.json", "request.json", "verdict.json"):
        p = os.path.join(d, n)
        if os.path.exists(p):
            try:
                j = json.load(open(p))
            except Exception as e:
                print("  ", n, "unreadable", e)
                continue
            s = json.dumps(j)
            print("  ", n, s[:900])
