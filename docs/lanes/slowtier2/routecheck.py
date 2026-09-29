#!/usr/bin/env python3
"""List every result that ran one of phase 2b's routes, with its route frames.

For each run: the route name, the claim time (route.txt's mtime, PDT), the
result dir, ref, perflog flag, device, and the route-frames it kept. Also the
seconds from the route's start to its `press START` lines and to the first
hakuX-perf gfps line (the game's first frame), because the Otogi pilot's
failure was a timing one (NOTES, "Attempt 3").
Usage: python3 docs/lanes/slowtier2/routecheck.py
"""
import json, os, re, time, datetime

R = "/home/justin/hakux-work/dispatch/results"
WANT = {"midtown-madness-3.returning", "black.returning", "burnout", "alias",
        "pgr.returning", "crash-twinsanity", "bloodrayne", "otogi"}


def hms(s):
    return datetime.datetime.strptime(s[:12], "%H:%M:%S.%f")


rows = []
for d in os.listdir(R):
    try:
        q = json.load(open(os.path.join(R, d, "request.json")))
    except Exception:
        continue
    rn = q.get("route_name")
    if rn not in WANT:
        continue
    rt = os.path.join(R, d, "route.txt")
    fd = os.path.join(R, d, "route-frames")
    fr = sorted(os.listdir(fd)) if os.path.isdir(fd) else []
    start = first = None
    starts = []
    rl = os.path.join(R, d, "run.log")
    if os.path.exists(rl):
        for l in open(rl, errors="replace"):
            m = re.match(r"ROUTE (\S+) (start route|press START|mark gameplay)", l)
            if m:
                if m.group(2) == "start route":
                    start = hms(m.group(1))
                elif start:
                    starts.append("%s@%.0f" % (m.group(2).split()[0], (hms(m.group(1)) - start).total_seconds()))
    lc = os.path.join(R, d, "logcat.txt")
    if start and os.path.exists(lc):
        for l in open(lc, errors="replace"):
            if "hakuX-perf" in l and "gfps=" in l:
                first = (hms(l[6:18]) - start).total_seconds()
                break
    rows.append((rn, os.path.getmtime(rt) if os.path.exists(rt) else 0, d,
                 q.get("ref", "")[:10], q.get("perflog") or "-", q.get("device"),
                 "first-gfps@%s" % (None if first is None else round(first)),
                 " ".join(starts), fr))
for r in sorted(rows):
    print(r[0], time.strftime("%m-%d %H:%M", time.localtime(r[1])), *r[2:])
