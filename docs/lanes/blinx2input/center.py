#!/usr/bin/env python3
"""lane.blinx2input: finish Blinx 2's balloon step on a RUNNING game.

Continuous proportional yaw instead of pulses (run 6: a 0.1 s pulse at RX
22000 plus adb latency overshot +-0.1 screen widths for 210 s): RX is held
just past the game's dead zone (~11000), scaled by the balloon's offset, and
re-aimed every frame; centred, the stick is let go and the lock-on arc fills.
Stops when the tutorial's green card appears.

    SERIAL=ee317437 python3 center.py <out_dir> [seconds]
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.expanduser("~/hakux-work/wt/pathfind/docs/testing/titles"))
import pathfind  # noqa: E402

OUT = sys.argv[1]
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 240
os.makedirs(OUT, exist_ok=True)
dev = pathfind.Device("nova")
log = open(os.path.join(OUT, "log.jsonl"), "a")
t0 = time.time()


def note(what, **kw):
    rec = dict(t=round(time.time() - t0, 1), what=what, **kw)
    log.write(json.dumps(rec) + "\n")
    log.flush()
    print(json.dumps(rec), flush=True)


def frame(i):
    p = os.path.join(OUT, f"{i:03d}.png")
    dev.capture(p)
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def balloon(a):
    h, w, _ = a.shape
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (g > 100) & (g - r > 20) & (g - r < 80) & (b < 0.5 * g) & (r > 60) & (r < 150)   # r < 150: not the first-person crosshair
    m[: int(0.18 * h), : int(0.30 * w)] = False
    m[int(0.50 * h):, :] = False
    ys, xs = np.nonzero(m)
    if len(xs) < 150:
        return None
    return xs.mean() / w - 0.5, ys.mean() / h


def card(a):
    h, w, _ = a.shape
    z = a[int(0.86 * h):int(0.94 * h), int(0.45 * w):int(0.9 * w)]
    return ((z[..., 1] > z[..., 0] + 30) & (z[..., 1] > z[..., 2])).mean() > 0.5


# Calibration (scratch/cal): RX 12500 does not yaw, 13500 already turns
# half a screen in 1 s, so there is no proportional range: pulse at 22000
# as run 5 did. Run 5 popped balloons only once the pitch was -30000 or more
# (balloon near vertical centre, y ~0.36); run 6 at -22000 (y 0.26) never
# drew the lock-on arc. So start at -30000 and steer y toward 0.36.


def pulse(sign, secs):
    dev.pad("axis", "RX", str(22000 * sign))
    time.sleep(secs)
    dev.pad("axis", "RX", "mid")


pitch = -30000
dev.pad("axis", "RY", str(pitch))
i = 0
skip = 0
while time.time() - t0 < SECS:
    a = frame(i)
    if card(a):
        note("card", frame=i)
        break
    bl = balloon(a)
    note("aim", frame=i, at=bl and [round(bl[0], 3), round(bl[1], 2)], pitch=pitch, skip=skip)
    i += 1
    if bl is None or skip:
        skip = max(0, skip - 1)
        pulse(1, 0.8)
        continue
    dx, y = bl
    want = max(-32767, min(-12000, pitch - 4000 if y < 0.30 else (pitch + 4000 if y > 0.44 else pitch)))
    if want != pitch:
        pitch = want
        dev.pad("axis", "RY", str(pitch))
    if abs(dx) > 0.06:
        pulse(1 if dx > 0 else -1, min(1.2, abs(dx) * 2.0))
        continue
    note("dwell", frame=i)
    time.sleep(4.0)
    skip = 1
    pulse(1, 1.5)
dev.pad("axis", "RX", "mid")
dev.pad("axis", "RY", "mid")
note("done", frames=i)
