#!/usr/bin/env python3
"""lane.blinx2input: Playable confirmation on a RUNNING Blinx 2 game.

Every ~20 s: a frame, walk forward 1.2 s (frame while walking), jump on
every third cycle, walk back 1.2 s (frame while walking). Logs the frame
difference each move made, the battery's current and level, for SECS
seconds (default 630).

    SERIAL=ee317437 python3 confirm.py <out_dir> [seconds]
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.expanduser("~/hakux-work/wt/pathfind/docs/testing/titles"))
import pathfind  # noqa: E402

OUT = sys.argv[1]
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 630
SERIAL = os.environ.get("SERIAL", "ee317437")
os.makedirs(OUT, exist_ok=True)
dev = pathfind.Device("nova")
log = open(os.path.join(OUT, "log.jsonl"), "a")
t0 = time.time()
n = 0


def note(what, **kw):
    rec = dict(t=round(time.time() - t0, 1), what=what, **kw)
    log.write(json.dumps(rec) + "\n")
    log.flush()
    print(json.dumps(rec), flush=True)


def shot(label):
    global n
    n += 1
    p = os.path.join(OUT, f"{n:03d}-{int(time.time() - t0):03d}s-{label}.png")
    dev.capture(p)
    return np.asarray(Image.open(p).convert("L").resize((160, 120), Image.BOX)).astype(int)


def battery():
    out = subprocess.run(
        ["adb", "-s", SERIAL, "shell",
         "cat /sys/class/power_supply/battery/current_now /sys/class/power_supply/battery/capacity"],
        capture_output=True, text=True, timeout=20).stdout.split()
    return dict(current_ua=int(out[0]), level=int(out[1])) if len(out) == 2 else dict(raw=out)


def walk(label, value):
    dev.pad("axis", "LY", value)
    time.sleep(0.6)
    a = shot(label)
    time.sleep(0.6)
    dev.pad("axis", "LY", "mid")
    return a


cycle = 0
note("start", **battery())
while time.time() - t0 < SECS:
    c0 = time.time()
    pre = shot("pre")
    fwd = walk("fwd", "min")
    if cycle % 3 == 2:
        dev.pad("press", "A", 120)
        time.sleep(0.15)
        dev.pad("press", "A", 120)
        time.sleep(0.8)
    back = walk("back", "max")
    note("cycle", n=cycle, moved_fwd=round(float(np.abs(fwd - pre).mean()), 1),
         moved_back=round(float(np.abs(back - fwd).mean()), 1), **battery())
    cycle += 1
    time.sleep(max(0.0, 20 - (time.time() - c0)))
shot("end")
note("end", cycles=cycle, **battery())
