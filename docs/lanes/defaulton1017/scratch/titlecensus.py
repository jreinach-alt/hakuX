#!/usr/bin/env python3
"""Latest Nova soaks per candidate title: route, seconds, mark, and log signs that bear on the screen.

usage: titlecensus.py <title substring>...

For each title, the newest 4 Nova soak results: id, ref, route, seconds, env, and in logcat.txt
- whether the route reached a mark (`mark gameplay`/`mark cinematic`),
- the last [rdc]/report and [txdl794] why=cvt hints,
- crash lines.
"""
import glob
import json
import os
import re
import sys

R = "/home/justin/hakux-work/dispatch/results"
pats = [p.lower() for p in sys.argv[1:]]
rows = {p: [] for p in pats}
for d in glob.glob(R + "/*"):
    rq = os.path.join(d, "request.json")
    if not os.path.exists(os.path.join(d, "DONE")) or not os.path.exists(rq):
        continue
    try:
        r = json.load(open(rq))
    except Exception:
        continue
    if r.get("device") != "nova" or not r.get("title"):
        continue
    t = r["title"].lower()
    for p in pats:
        if p in t:
            rows[p].append((r.get("queued_utc", ""), d, r))

for p in pats:
    print(f"== {p}: {len(rows[p])} nova soaks")
    for q, d, r in sorted(rows[p], reverse=True)[:4]:
        lc = os.path.join(d, "logcat.txt")
        marks, cvt, rearly, crash, fld = [], 0, [], 0, []
        if os.path.exists(lc):
            for ln in open(lc, errors="replace"):
                if "hakuX-route" in ln and " mark " in ln:
                    marks.append(ln.strip()[-60:])
                if "why=cvt" in ln:
                    cvt += 1
                if "[rearly1018] w" in ln:
                    rearly.append(ln.strip()[-90:])
                if "[fldcw1018] n=" in ln:
                    fld.append(ln.strip()[-80:])
                if "hakuX-crash" in ln or "Fatal signal" in ln:
                    crash += 1
        print(f"  {q} {os.path.basename(d)} ref={r.get('ref')} route={r.get('route_name')} s={r.get('seconds')} "
              f"who={r.get('requester')} env={','.join(e.split('=')[0].replace('HAKUX_','') + '=' + e.split('=',1)[1] for e in r.get('env', []))}")
        print(f"     marks={marks[:2]} cvtlines={cvt} crash={crash} rearly={rearly[-1:] } fld={fld[-1:]}")
