#!/usr/bin/env python3
"""Distinct titles soaked on the Nova since a date, with the count, newest route and seconds.

usage: novatitles.py [since-utc, default 2026-10-05]
"""
import glob
import json
import os
import sys

R = "/home/justin/hakux-work/dispatch/results"
since = sys.argv[1] if len(sys.argv) > 1 else "2026-10-05"
seen = {}
for d in glob.glob(R + "/*"):
    rq = os.path.join(d, "request.json")
    if not os.path.exists(os.path.join(d, "DONE")) or not os.path.exists(rq):
        continue
    try:
        r = json.load(open(rq))
    except Exception:
        continue
    if r.get("device") != "nova" or not r.get("title") or r.get("queued_utc", "") < since:
        continue
    k = r["title"]
    n, best = seen.get(k, (0, None))
    if best is None or r.get("queued_utc", "") > best.get("queued_utc", ""):
        best = r
    seen[k] = (n + 1, best)
for k in sorted(seen):
    n, r = seen[k]
    print(f"{n:4d} {k[:48]:48s} {r.get('title_id','')} {r.get('route_name','')} {r.get('seconds')}")
