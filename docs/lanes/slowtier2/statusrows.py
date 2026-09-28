#!/usr/bin/env python3
"""The status page's title rows for the phase-2 titles, as status.json holds them.

    statusrows.py [status.json]

For each title: its stage, and every reading the page holds (`soak_read`,
`measured`, `runs`) with the result id each came from, so the reading the
brief lists can be traced to one result dir.
"""
import json
import re
import sys

P = sys.argv[1] if len(sys.argv) > 1 else "/home/justin/hakux-work/status/status.json"
PAT = re.compile(r"jet set|jsrf|mechassault 2|arctic thunder|bloodrayne$|^alias$|xtreme beach|conker|"
                 r"twinsanity|dead or alive 3|project gotham racing$|brute force|otogi|^burnout$|^black$|"
                 r"midtown madness 3|crimson", re.I)


def rows(o):
    if isinstance(o, dict):
        if isinstance(o.get("title"), str) and "stage" in o and PAT.search(o["title"]):
            yield o
        for v in o.values():
            yield from rows(v)
    elif isinstance(o, list):
        for v in o:
            yield from rows(v)


def short(r):
    if not isinstance(r, dict):
        return str(r)
    return "%s %s fps=%s ref=%s mode=%s src=%s (%s)" % (
        r.get("id"), r.get("device"), r.get("fps"), r.get("ref"), r.get("mode"), r.get("src"), r.get("verdict", "")[:60])


s = json.load(open(P))
print("status.json generated:", s.get("generated"))
for o in rows(s):
    print("\n## %s (%s) stage=%s prim=%s" % (o["title"], o.get("tid"), o.get("stage"), short(o.get("prim"))))
    print("  soak_read:", short(o.get("soak_read")))
    for m in o.get("measured") or []:
        print("  measured:", short(m))
    for m in o.get("runs") or []:
        print("  run:", short(m))
