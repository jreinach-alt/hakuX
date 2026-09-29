#!/usr/bin/env python3
"""soaks.py PATTERN...: every finished title soak in $DISPATCH_DIR/results
whose request's ISO matches a pattern (case-insensitive substring), newest
last: id, device, ISO, route, seconds, env, verdict (if any), and the time
from `soak start` to the route's `mark gameplay` in logcat. Reads only."""
import glob
import json
import os
import re
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")


def load(p):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def mark_after_start(rdir):
    start = mark = None
    try:
        with open(os.path.join(rdir, "logcat.txt"), errors="replace") as f:
            for ln in f:
                if "hakuX-route" not in ln:
                    continue
                t = ln[:18]
                if "soak start" in ln and start is None:
                    start = t
                elif "mark gameplay" in ln and mark is None:
                    mark = t
    except OSError:
        return None
    if not (start and mark):
        return None
    import datetime as dt
    f = lambda s: dt.datetime.strptime("2000-" + s.strip(), "%Y-%m-%d %H:%M:%S.%f").timestamp()
    return round(f(mark) - f(start))


pats = [p.lower() for p in sys.argv[1:]]
rows = []
for rj in glob.glob(os.path.join(D, "results", "*", "request.json")):
    r = load(rj)
    t = (r.get("title") or "")
    if not t or not any(p in t.lower() for p in pats):
        continue
    rdir = os.path.dirname(rj)
    res = load(os.path.join(rdir, "result.json"))
    v = load(os.path.join(rdir, "verdict.json"))
    rows.append((os.path.basename(rdir).split("-")[1] if "-" in os.path.basename(rdir) else "",
                 os.path.basename(rdir), res.get("device_label") or r.get("device"), t[:40],
                 r.get("route_name") or r.get("route"), r.get("seconds"), r.get("env"),
                 ("PASS" if v.get("pass") else (v.get("failing") or "")[:60]) if v else "-",
                 mark_after_start(rdir), (res.get("ref") or r.get("ref") or "")[:10]))
rows.sort()
for x in rows:
    print(" | ".join(str(y) for y in x[1:]))
