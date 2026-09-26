#!/usr/bin/env python3
"""List every soak title a past dispatch result ran, per device, with whether
the worker found the ISO. Reads $DISPATCH_DIR/results only; never a device.

    isoseen.py [substring ...]
"""
import json
import os
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
subs = [s.lower() for s in sys.argv[1:]]
seen = {}
for rid in os.listdir(os.path.join(D, "results")):
    p = os.path.join(D, "results", rid)
    try:
        req = json.load(open(os.path.join(p, "request.json")))
    except Exception:
        continue
    t = req.get("title")
    if not t:
        continue
    if subs and not any(s in t.lower() for s in subs):
        continue
    dev = req.get("device") or "?"
    status = "?"
    if os.path.exists(os.path.join(p, "ERROR")):
        status = "ERROR " + open(os.path.join(p, "ERROR")).read().strip()[:60]
    elif os.path.exists(os.path.join(p, "DONE")):
        status = "done"
    try:
        res = json.load(open(os.path.join(p, "result.json")))
        dev = res.get("device") or dev
    except Exception:
        pass
    k = (t, dev)
    seen.setdefault(k, []).append((rid, str(status)))
for (t, dev), runs in sorted(seen.items()):
    runs.sort()
    ok = sum(1 for _, s in runs if s == "done")
    print(f"{dev:6} {len(runs):3} ok={ok:<3} {t}   last={runs[-1][0]} {runs[-1][1][:70]}")
