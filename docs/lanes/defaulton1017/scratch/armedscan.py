#!/usr/bin/env python3
"""Free census of where REPORT_EARLY can act: every Nova/Thor result whose logcat has
`[rtrace] w` window lines (HAKUX_REPORT_TRACE=1) or `[rearly1018] w` lines.

REPORT_EARLY answers only an ARMED GET_REPORT (status word nonzero at queue), so a
title with armed=0 in every window is a title where it cannot act. Also reports the
reuse interval histogram (`next=`, buckets 0.25 0.5 1 2 4 8 16.7 33.3 66.7 ms, over):
an offset re-queued inside one frame (< 16.7 ms) is the one mechanism by which an
early answer could be another test's count.

usage: armedscan.py
"""
import glob
import json
import os
import re

R = "/home/justin/hakux-work/dispatch/results"
W = re.compile(r"\[rtrace\] w mode=(\w+).* n=(\d+) .*next=([\d,]+) .*reuse=(\d+) reuseb4w=(\d+) armed=(\d+)")
E = re.compile(r"\[rearly1018\] w early=(\d+) cold=(\d+) unarmed=(\d+)")
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
    env = " ".join(r.get("env", []))
    if "REPORT_TRACE" not in env and "REPORT_EARLY" not in env:
        continue
    t = (r.get("title") or "")[:40]
    agg = dict(win=0, n=0, armed=0, reuse=0, next=[0] * 10, early=0, cold=0, unarmed=0, ewin=0, mode=set())
    for ln in open(lc, errors="replace"):
        m = W.search(ln)
        if m:
            agg["win"] += 1
            agg["mode"].add(m.group(1))
            agg["n"] += int(m.group(2))
            agg["armed"] += int(m.group(6))
            agg["reuse"] += int(m.group(4))
            for i, v in enumerate(m.group(3).split(",")[:10]):
                agg["next"][i] += int(v)
            continue
        m = E.search(ln)
        if m:
            agg["ewin"] += 1
            agg["early"] += int(m.group(1))
            agg["cold"] += int(m.group(2))
            agg["unarmed"] += int(m.group(3))
    if agg["win"] or agg["ewin"]:
        out.setdefault(t, []).append((os.path.basename(d), r.get("device"), r.get("route_name"), agg))

for t in sorted(out):
    print(f"== {t}")
    for rid, dev, route, a in sorted(out[t])[-4:]:
        print(f"  {rid} {dev} {route} rtwin={a['win']} mode={','.join(sorted(a['mode']))} n={a['n']} armed={a['armed']} "
              f"reuse={a['reuse']} next={a['next']} | rearly win={a['ewin']} early={a['early']} cold={a['cold']} unarmed={a['unarmed']}")
