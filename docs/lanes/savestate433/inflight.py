#!/usr/bin/env python3
"""Part E: for each title in flight, its golden and whether a route of the
matching state exists today. Read-only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "testing", "titles"))
import titlestate as ts  # noqa: E402

INFLIGHT = [("Tron 2.0", "42560001", None), ("Blinx 2", "4D530065", None),
            ("Kabuki Warriors", "43560001", None), ("Dead or Alive 3", "4D53002D", None),
            ("ToeJam & Earl III", "5345000F", None), ("Battlefield 2: MC", "45410062", None),
            ("GTA San Andreas", "54540082", None), ("Crimson Skies", "4D530021", None),
            ("007 Nightfire", "45410026", None), ("Castlevania CoD", "4B4E002D", None)]
T = ts.targets()
for name, tid, _ in INFLIGHT:
    g = ts.golden(tid)
    route = (T.get(tid) or {}).get("route")
    res = ts.resolve_route(route, tid) if route else {"refuse": "no route in targets.toml", "state": None,
                                                        "route_name": None}
    dt = ts.disk_tid(tid)
    named = ""
    if g:
        d = os.path.join(ts.store_dir(dt, g["save"]), "UDATA", dt)
        named = ",".join(sorted(f for f in os.listdir(d) if os.path.isdir(os.path.join(d, f)))) if os.path.isdir(d) else ""
    print(f"| {name} | {tid}{' -> ' + dt if dt != tid else ''} | "
          f"{(g['save'] + ' ' + g['status']) if g else 'none'} | {named or '(no save dir: settings only)'} | "
          f"{res.get('route_name') or '-'} | {res.get('state') or '-'} | {res.get('refuse') or 'OK'} |")
