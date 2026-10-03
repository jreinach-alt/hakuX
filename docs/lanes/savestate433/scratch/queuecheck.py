#!/usr/bin/env python3
"""Resolve every line of lane.local's overnight-queue.tsv the way request.sh
will: the route from the line's worktree, the title from its ISO, the golden
from the live store. Prints the refusal (or OK) per key."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "docs", "testing", "titles"))
os.environ.setdefault("TITLESTATE_DIR", "/home/justin/hakux-work/dispatch/titlestate")
import titlestate  # noqa: E402

q = sys.argv[1] if len(sys.argv) > 1 else "/home/justin/hakux-work/pm/overnight-queue.tsv"
for line in open(q):
    if line.startswith("#") or not line.strip():
        continue
    f = line.rstrip("\n").split("\t")
    key, iso, route, wt = f[0], f[1], f[2], f[3]
    tid = titlestate.tid_for_iso(iso)
    rd = os.path.join(wt, "docs", "testing", "titles", "routes")
    r = titlestate.resolve_route(route, title_id=tid, device="nova", routes_dir=rd)
    g = titlestate.golden(tid) if tid else None
    dirs = len(titlestate.save_dirs(titlestate.disk_tid(tid), g["save"])) if g else 0
    print(f"{key:20} tid={tid} golden={g['save'] if g else None} dirs={dirs} route={r['route_name']} "
          f"state={r['state']} -> {'REFUSE: ' + r['refuse'] if r['refuse'] else 'OK'}")
