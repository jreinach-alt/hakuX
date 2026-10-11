#!/usr/bin/env python3
"""List a dispatch result's files and result.json scalars (lane.gpunonrender).

    rls.py <request-id> ...
"""
import json, os, sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
for rid in sys.argv[1:]:
    r = os.path.join(D, rid)
    print("==", rid)
    for root, dirs, files in os.walk(r):
        for f in sorted(files):
            p = os.path.join(root, f)
            print("   %9d %s" % (os.path.getsize(p), os.path.relpath(p, r)))
    try:
        d = json.load(open(os.path.join(r, "result.json")))
    except Exception as e:
        print("   result.json:", e)
        continue
    for k, v in d.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v)[:200]
        print("   %s: %s" % (k, v))
