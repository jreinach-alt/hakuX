#!/usr/bin/env python3
"""For the titles qrycensus.py found running visibility tests: which device each run
was on, its route and seconds, the windows with qry > 0, and whether the run's
route reached the part with qry (first window index with qry > 0 of how many).

usage: qryroutes.py <title substring> [...]
"""
import glob
import json
import os
import re
import sys

R = "/home/justin/hakux-work/dispatch/results"
Q = re.compile(r"hakuX-rpbrk.*qry(\d+)")
subs = [s.lower() for s in sys.argv[1:]]
for d in sorted(glob.glob(R + "/*"), key=lambda p: os.path.basename(p).split("-")[-3:]):
    rq = os.path.join(d, "request.json")
    lc = os.path.join(d, "logcat.txt")
    if not os.path.exists(rq) or not os.path.exists(lc):
        continue
    try:
        r = json.load(open(rq))
    except Exception:
        continue
    title = r.get("title") or ""
    if not any(s in title.lower() for s in subs):
        continue
    q = []
    with open(lc, errors="replace") as f:
        for line in f:
            if "hakuX-rpbrk" in line:
                m = Q.search(line)
                if m:
                    q.append(int(m.group(1)))
    dev = r.get("device") or ""
    try:
        dev = json.load(open(os.path.join(d, "result.json"))).get("device_label", dev)
    except Exception:
        pass
    pos = [i for i, v in enumerate(q) if v > 0]
    print("%-44s %-5s %-28s %5s win=%4d qry>0=%4d first=%s %s" % (
        os.path.basename(d)[:44], dev, (r.get("route_name") or "")[:28], r.get("seconds"),
        len(q), len(pos), pos[0] if pos else "-", title[:30]))
