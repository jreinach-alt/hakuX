#!/usr/bin/env python3
"""pause_census.py -- per device, how many soak results with a thermal.jsonl
had a thermal pause (thermal_state.first_episode), and the start xo of each
paused run. Checks sustain507-levers.json's "no Nova soak on disk has paused"."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
import thermal_state  # noqa: E402

RESULTS = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
count = {}
for d in sorted(os.listdir(RESULTS)):
    p = os.path.join(RESULTS, d)
    if os.path.islink(p):
        continue
    tj = os.path.join(p, "thermal.jsonl")
    if not os.path.isfile(tj):
        continue
    try:
        dev = json.load(open(os.path.join(p, "result.json"))).get("device_label")
    except (OSError, ValueError):
        dev = None
    recs = thermal_state.load(tj) or []
    fe = thermal_state.first_episode(recs)
    c = count.setdefault(dev, [0, 0, []])
    c[0] += 1
    if fe:
        c[1] += 1
        c[2].append(d)
for dev, (n, np_, ids) in sorted(count.items(), key=lambda x: str(x[0])):
    print("%s: %d runs with thermal.jsonl, %d paused" % (dev, n, np_))
    if dev != "thor":
        for i in ids:
            print("   ", i)
