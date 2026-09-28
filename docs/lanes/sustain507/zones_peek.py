#!/usr/bin/env python3
"""zones_peek.py -- print the zone names and the first sample's temperatures of
thermal.jsonl in the newest Thor and Nova soak results (the battery sensor's
name differs per device)."""
import json
import os
import sys

RESULTS = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
want = sys.argv[1:] or ["thor", "nova"]
seen = {}
for d in sorted(os.listdir(RESULTS), reverse=True):
    p = os.path.join(RESULTS, d)
    tj = os.path.join(p, "thermal.jsonl")
    if not os.path.isfile(tj):
        continue
    try:
        dev = json.load(open(os.path.join(p, "result.json"))).get("device_label")
    except (OSError, ValueError):
        continue
    if dev in want and dev not in seen:
        with open(tj) as f:
            first = json.loads(f.readline())
        seen[dev] = d
        print(dev, d)
        print("  keys:", sorted(first.keys()))
        z = first.get("tz") or []
        print("  tz:", ", ".join("%s=%s" % (x[1], x[2]) for x in z
                                 if any(k in x[1] for k in ("batt", "xo", "skin", "therm"))))
        print("  battery pw:", json.dumps((first.get("pw") or {}).get("battery")))
        print("  pause-type cooling devices:", [c[1] for c in first.get("cool") or [] if "pause" in c[1]])
        print("  pause field:", json.dumps(first.get("pause"))[:300])
    if len(seen) == len(want):
        break
