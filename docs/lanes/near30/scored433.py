#!/usr/bin/env python3
"""lane.near30: the scored window for Blinx 2 on the held Nova (#433).

    python3 scored433.py <out_dir> <batch> <cycles>

Each cycle: walk forward (LY max, 2 s), walk back (LY min, 2 s), and every
fourth cycle a right-stick yaw pulse (RX 22000, 1 s). A frame is taken every
six cycles (~30 s). Marks go to logcat as `hakuX-route: mark scored<batch>-<n>`.
Drives b2.py, the same hands as the ocean run.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
B2 = os.path.join(HERE, "b2.py")
out, batch, cycles = sys.argv[1], sys.argv[2], int(sys.argv[3])
steps = ["mark", f"scored{batch}_start"]
for c in range(cycles):
    steps += ["axis", "LY", "max", "wait", "2", "axis", "LY", "0", "wait", "0.5"]
    steps += ["axis", "LY", "min", "wait", "2", "axis", "LY", "0", "wait", "0.5"]
    if c % 4 == 3:
        steps += ["axis", "RX", "22000", "wait", "1", "axis", "RX", "0", "wait", "0.5"]
    if c % 6 == 5:
        steps += ["shot", f"sc{batch}-{c:03d}"]
steps += ["mark", f"scored{batch}_end"]
rc = subprocess.call(["python3", B2, out] + steps)
sys.exit(rc)
