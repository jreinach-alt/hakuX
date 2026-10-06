#!/usr/bin/env python3
"""Run run_waits on the pathfind sweep runs behind the family issues.

The run dirs live in the pathfind lane's worktree, not in dispatch results.
Prints only the lines the report cites, per run, so the figures can be checked
against the issue titles (#839-#846, #851) that name the same run dirs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_waits  # noqa: E402

RUNS = "/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs"
NAMES = ["sweep-4541007B", "sweep-4541003E", "sweep-56550039", "sweep-54540008", "sweep-4156002B"]
KEEP = ("==", "phase Tot", "phase Fen", "phase Sub", "phase Idle ", "phase IdleFr",
        "phase GPU_R ", "frame ", "pace ", "vblank")

for name in NAMES:
    d = os.path.join(RUNS, name)
    if not os.path.exists(os.path.join(d, "logcat.txt")):
        print("== %s: no logcat.txt" % name)
        continue
    print("== %s" % name)
    sys.stdout.flush()
    run_waits.run(d)
