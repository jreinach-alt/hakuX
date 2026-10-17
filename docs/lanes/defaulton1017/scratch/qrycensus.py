#!/usr/bin/env python3
"""Free census of which titles run visibility tests: every title run whose logcat
carries the perflog line `hakuX-rpbrk RP:n(fin f fb b qry Q ...)` (draw.c ~1048,
once per 60 flips). qry counts render-pass breaks from query begin/end, so qry > 0
means the guest ran visibility tests in that window (accuracy804: RalliSport's
race is 400-1788 a window, its menus 0).

REPORT_EARLY can act only where the guest runs visibility tests AND arms the
report's status word; this lists the first condition for every title that has a
perflog run, at no device cost.

usage: qrycensus.py
"""
import glob
import json
import os
import re
import statistics

R = "/home/justin/hakux-work/dispatch/results"
Q = re.compile(r"hakuX-rpbrk.*RP:(\d+)\(fin(\d+) fb(\d+) qry(\d+)")
out = {}
for d in glob.glob(R + "/*"):
    lc = os.path.join(d, "logcat.txt")
    rq = os.path.join(d, "request.json")
    if not os.path.exists(lc) or not os.path.exists(rq):
        continue
    try:
        r = json.load(open(rq))
    except Exception:
        continue
    title = r.get("title") or ""
    if not title:
        continue
    q = []
    try:
        with open(lc, errors="replace") as f:
            for line in f:
                if "hakuX-rpbrk" not in line:
                    continue
                m = Q.search(line)
                if m:
                    q.append(int(m.group(4)))
    except OSError:
        continue
    if not q:
        continue
    t = out.setdefault(title, {"runs": 0, "win": 0, "pos": 0, "vals": [], "ex": ""})
    t["runs"] += 1
    t["win"] += len(q)
    t["pos"] += sum(1 for v in q if v > 0)
    t["vals"] += [v for v in q if v > 0]
    if sum(1 for v in q if v > 0) and not t["ex"]:
        t["ex"] = os.path.basename(d)

rows = sorted(out.items(), key=lambda kv: -kv[1]["pos"] / max(kv[1]["win"], 1))
print("%-50s %4s %6s %6s %7s %7s  %s" % ("title", "runs", "wins", "qry>0", "med>0", "max", "example"))
for title, t in rows:
    v = t["vals"]
    print("%-50s %4d %6d %5.0f%% %7s %7s  %s" % (
        title[:50], t["runs"], t["win"], 100.0 * t["pos"] / max(t["win"], 1),
        int(statistics.median(v)) if v else "-", max(v) if v else "-", t["ex"]))
