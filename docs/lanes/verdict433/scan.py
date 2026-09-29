#!/usr/bin/env python3
"""scan.py [PATTERN...]: every title soak verdict in $DISPATCH_DIR/results,
one line each, newest last, for titles whose name or ISO matches a pattern
(case-insensitive substring). Reads verdict.json and perf_regimen.json only;
judges nothing."""
import glob
import json
import os
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")


def load(p):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


pats = [p.lower() for p in sys.argv[1:]]
out = []
for p in glob.glob(os.path.join(D, "results", "*", "verdict.json")):
    v = load(p)
    rdir = os.path.dirname(p)
    name = v.get("name") or v.get("title") or "?"
    hay = (name + " " + (v.get("title") or "")).lower()
    if pats and not any(x in hay for x in pats):
        continue
    reg = load(os.path.join(rdir, "perf_regimen.json")).get("regimen")
    th = v.get("thermal") or {}
    out.append((os.path.basename(rdir), name, v.get("device"), v.get("route"),
                reg, v.get("gameplay_s"), v.get("fps_window_median"), v.get("fps_ok_share"),
                v.get("pass"), v.get("pass_kind"), (v.get("failing") or "")[:90],
                th.get("first_pause_s"), v.get("ref")))
out.sort(key=lambda r: r[0].split("-")[1] if r[0].count("-") > 1 else r[0])
for r in out:
    print("%s | %s | %s | route=%s reg=%s gp=%s med=%s share=%s pass=%s/%s | %s | pause=%s ref=%s" % r)
