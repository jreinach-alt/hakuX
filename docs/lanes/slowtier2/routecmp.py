#!/usr/bin/env python3
"""Is each parked request's route the one its last good run played?

Compares the route text in each parked .req with that run's route.txt and
with master's docs/testing/titles/routes/<name>.route.
Usage (from the worktree root): python3 docs/lanes/slowtier2/routecmp.py
"""
import json, os

P = "/home/justin/hakux-work/dispatch/parked/slowtier2-cold-20260928/"
R = "/home/justin/hakux-work/dispatch/results/"
LAST = {
    "midtown-madness-3.returning": "1-1790506491-titleroutes-1032854",
    "black.returning": "1-1790482599-titleroutes-3358750",
    "burnout": "1-1790513065-titleroutes-1150288",
    "alias": "1-1790519290-titleroutes-2113140",
    "pgr.returning": "1-1790483525-titleroutes-3587419",
    "crash-twinsanity": "1-1790489396-titleroutes-512742",
    "bloodrayne": "1-1790548501-titleroutes-1530145r",
    "otogi": "1-1790511808-titleroutes-1129571",
}
for f in sorted(os.listdir(P)):
    if not f.endswith(".req"):
        continue
    q = json.load(open(P + f))
    rn = q["route_name"]
    old = open(R + LAST[rn] + "/route.txt").read()
    repo = open("docs/testing/titles/routes/" + rn + ".route").read()
    print(f, rn,
          "same-as-last-run" if q["route"] == old else "DIFFERS-from-last-run",
          "same-as-master" if q["route"] == repo else "DIFFERS-from-master")
