#!/usr/bin/env python3
"""Every targets.toml title with a route: its golden, whether the golden
carries a save directory, the route's declared state, and what request.sh
would do with it today (titlestate.resolve_route). Plus the titles whose
stored harvests differ in whether they carry a profile (menus that differ
with and without one). Read-only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "testing", "titles"))
import titlestate as ts  # noqa: E402

T = ts.targets()
print("| title | id | golden | save dirs | route | state | request.sh today |")
print("|---|---|---|---|---|---|---|")
for tid, t in sorted(T.items(), key=lambda kv: kv[1].get("name", "")):
    r = t.get("route")
    if not r:
        continue
    g = ts.golden(tid)
    dt = ts.disk_tid(tid)
    dirs = ts.save_dirs(dt, g["save"]) if g else []
    res = ts.resolve_route(r, tid)
    print(f"| {t.get('name', '?')[:30]} | {tid} | {(g['save'] + ' ' + g['status'][:4]) if g else 'none'} | "
          f"{len(dirs)} | {res.get('route_name') or r} | {res.get('state') or '-'} | "
          f"{('REFUSED: ' + res['refuse'][:70]) if res['refuse'] else 'queued'} |")

print("\nTitles whose harvests differ in carrying a profile (a save directory):")
sd = os.path.join(ts.root(), "saves")
for tid in sorted(os.listdir(sd)):
    if tid.startswith("."):
        continue
    ss = ts.store_saves(tid)
    have = [s for s in ss if ts.save_dirs(tid, s)]
    if have and len(have) < len(ss):
        canon = [k for k, v in ts.load_goldens().get("aliases", {}).items() if v == tid]
        tt = T.get(tid) or (T.get(canon[0]) if canon else {}) or {}
        print(f"- {tid} {tt.get('name') or ts.title_meta_name(tid)}: {len(have)} of {len(ss)} harvests carry a "
              f"save dir; route {tt.get('route') or '-'}")
