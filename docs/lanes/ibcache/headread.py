#!/usr/bin/env python3
"""Leg 5a/5b readings on the head (#507), from soakread.py's scratch copies.

    headread.py <request id> ...

Per run: the static-window check, power.flips, power.scored_s, the
time-weighted fps (flips / scored_s), J/frame and the power fields. Run
soakread.py on the same ids first; it writes scratch/res/<id>/verdict.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCR = os.path.normpath(os.path.join(HERE, "..", "..", "..", "scratch", "res"))

for rid in sys.argv[1:]:
    v = json.load(open(os.path.join(SCR, rid, "verdict.json")))
    p = v.get("power") or {}
    flips, sc = p.get("flips"), p.get("scored_s")
    fps = round(flips / sc, 3) if flips and sc else None
    sw = v.get("static_window") or {}
    print(json.dumps({
        "id": rid, "fps_tw": fps, "flips": flips, "scored_s": sc,
        "jpf": p.get("j_per_frame"),
        "power": {k: x for k, x in p.items() if not isinstance(x, (list, dict))},
        "static": {k: sw.get(k) for k in ("measured", "reason", "frozen_frac", "n")},
    }))
