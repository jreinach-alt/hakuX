#!/usr/bin/env python3
"""Block up to N seconds (default 570) for the six #428 arm runs; print state."""
import os
import sys
import time

D = "/home/justin/hakux-work/dispatch/"
IDS = ["1790454357-vcpuprime428-3938872", "1790454370-vcpuprime428-3939641",
       "1790454370-vcpuprime428-3939708", "1790454371-vcpuprime428-3939754",
       "1790454371-vcpuprime428-3939794", "1790454372-vcpuprime428-3939872"]


def state(i):
    r = D + "results/" + i
    for f in ("DONE", "ERROR"):
        if os.path.exists(os.path.join(r, f)):
            return f
    if os.path.exists(D + "running/" + i + ".req"):
        return "running"
    q = sorted(os.listdir(D + "queue"))
    return "queued@%d" % q.index(i + ".req") if i + ".req" in q else "?"


t0, lim = time.time(), float(sys.argv[1]) if len(sys.argv) > 1 else 570
first = [state(i) for i in IDS]
while time.time() - t0 < lim:
    s = [state(i) for i in IDS]
    if all(x in ("DONE", "ERROR") for x in s) or [x[:6] for x in s] != [x[:6] for x in first]:
        break
    time.sleep(20)
print(time.strftime("%H:%M:%S"), "waited %.0fs" % (time.time() - t0), list(zip(["A1", "B1", "A2", "B2", "A3", "B3"], s)))
print("running now:", [n for n in os.listdir(D + "running") if n.endswith(".req")])
