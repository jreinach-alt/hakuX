#!/usr/bin/env python3
"""lane.blinx2input run 1: does Blinx 2's Challenge Test 1 wait on the RIGHT stick?

Launches Blinx 2 on the Nova with pathfind's Device class (imported, not
edited), replays the unguided run's START/A schedule to the "Test 1 of 7"
card, dismisses it, then sends right-stick holds (the card's instruction),
then left-stick holds and A, with a frame before, during and after each.

    SERIAL=ee317437 python3 rstick_probe.py <out_dir>
"""
import json
import os
import sys
import time

PF = os.path.expanduser("~/hakux-work/wt/pathfind/docs/testing/titles")
sys.path.insert(0, PF)
import pathfind  # noqa: E402

ISO = ("/storage/E6C6-D7AA/Games/XBox/"
       "4D530065-Blinx_2_Battle_of_Time_Space_Blinx_2_Masters_of_Time_Space.xiso.iso")
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
dev = pathfind.Device("nova")
log = open(os.path.join(OUT, "log.jsonl"), "a")
t0 = None
n = 0


def t():
    return round(time.time() - t0, 1)


def note(what, **kw):
    rec = dict(t=t(), what=what, **kw)
    log.write(json.dumps(rec) + "\n")
    log.flush()
    print(json.dumps(rec), flush=True)


def shot(label):
    global n
    n += 1
    p = os.path.join(OUT, f"{n:03d}-{label}.png")
    dev.capture(p)
    note("shot", path=p)


def press(btn):
    dev.pad("press", btn, 120)
    note("press", btn=btn)
    time.sleep(0.35)


def hold_axes(label, axes, secs):
    for ax, v in axes:
        dev.pad("axis", ax, v)
    note("axis", label=label, axes=axes)
    time.sleep(secs * 0.5)
    shot(label + "-during")
    time.sleep(secs * 0.5)
    for ax, _ in axes:
        dev.pad("axis", ax, "mid")
    note("release", label=label)
    time.sleep(0.6)
    shot(label + "-after")


def until(sec):
    d = sec - (time.time() - t0)
    if d > 0:
        time.sleep(d)


REF = os.path.dirname(os.path.abspath(__file__)) + "/ref"


def sig(path):
    from PIL import Image
    im = Image.open(path).convert("L").resize((16, 12), Image.BOX)
    return list(im.tobytes())


def dist(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


# Grey 16x12 signatures. Title vs other title frames 8-19, vs anything else
# >= 37; bearings card vs itself 0.2, vs the Test 1 card before it 14.
TITLE = sig(REF + "/title.png")        # "Press START to begin." (run 1 frame 015)
BEARINGS = sig(REF + "/bearings.jpg")  # "Move the Right thumbstick..." (unguided 009)
TEST1 = sig(REF + "/test1.png")        # Test 1's start view, HUD up (run 2 frame 025; 0.3-0.7 to itself)


def look(label):
    shot(label)
    s = sig(os.path.join(OUT, f"{n:03d}-{label}.png"))
    d = dict(title=round(dist(s, TITLE), 1), bearings=round(dist(s, BEARINGS), 1),
             test1=round(dist(s, TEST1), 1))
    note("look", **d)
    return d


dev.launch(ISO)
t0 = time.time()
note("launch", iso=ISO)
while t() < 300:                        # wait for the title, START once
    if look("boot")["title"] < 25:
        press("START")
        break
    time.sleep(3)
for _ in range(40):                     # menus and cards: A until the bearings card
    time.sleep(4)
    d = look("menu")
    if d["test1"] < 12:
        break
    press("A")
time.sleep(1.0)
shot("test1-start")

# Run 3: slow orbits at part deflection, tilted progressively up (RY < 0
# looks up, run 2 frame 064), a frame every ~1.2 s while held.
def sweep(label, rx, ry, secs):
    dev.pad("axis", "RX", str(rx))
    dev.pad("axis", "RY", str(ry))
    note("sweep", label=label, rx=rx, ry=ry)
    end = time.time() + secs
    while time.time() < end:
        shot(label)
    dev.pad("axis", "RX", "mid")
    dev.pad("axis", "RY", "mid")
    note("release", label=label)
    time.sleep(1.5)
    shot(label + "-after")


# Run 5: run 4 frame 072 showed a red lock-on arc round a CENTRED balloon,
# and yaw persists after a pulse (pitch springs back). So: hold the pitch up,
# find the balloon's olive-green blob, pulse yaw toward it at RX 22000 (~36
# deg/s), dwell while centred, then yaw on to the next.
import numpy as np                      # noqa: E402
from PIL import Image                   # noqa: E402


def balloon(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    h, w, _ = a.shape
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (g > 100) & (g - r > 20) & (g - r < 80) & (b < 0.5 * g) & (r > 60)
    m[: int(0.18 * h), : int(0.30 * w)] = False      # HUD health bar
    m[int(0.50 * h):, :] = False                     # radar, player (run 4: Arch is green at y 0.57-0.6)
    ys, xs = np.nonzero(m)
    if len(xs) < 150:
        return None
    return xs.mean() / w - 0.5, ys.mean() / h, len(xs)


def pulse(sign, secs):
    dev.pad("axis", "RX", str(22000 * sign))
    time.sleep(secs)
    dev.pad("axis", "RX", "mid")


pitch = -22000
dev.pad("axis", "RY", str(pitch))
skip = 0
dwells = 0
end = time.time() + 210
def card(path):
    """The tutorial's green dialogue box across the bottom (run 5 frame 053)."""
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    h, w, _ = a.shape
    z = a[int(0.86 * h):int(0.94 * h), int(0.45 * w):int(0.9 * w)]
    g = (z[..., 1] > z[..., 0] + 30) & (z[..., 1] > z[..., 2])
    return g.mean() > 0.5


while time.time() < end:
    shot("seek")
    if card(os.path.join(OUT, f"{n:03d}-seek.png")):
        note("card: balloons done")
        break
    bl = balloon(os.path.join(OUT, f"{n:03d}-seek.png"))
    note("balloon", at=bl and [round(bl[0], 2), round(bl[1], 2), bl[2]], pitch=pitch, skip=skip)
    if bl is None or skip:
        skip = max(0, skip - 1)
        pulse(1, 0.8)
        continue
    dx, y, _ = bl
    want = pitch - 8000 if y < 0.22 else (pitch + 8000 if y > 0.42 else pitch)
    want = max(-32000, min(-6000, want))
    if want != pitch:
        pitch = want
        dev.pad("axis", "RY", str(pitch))
    if abs(dx) > 0.06:
        pulse(1 if dx > 0 else -1, min(1.2, abs(dx) * 1.2))   # run 5: 2.0 overshot
        time.sleep(0.2)
        continue
    dwells += 1
    note("dwell", n=dwells)
    time.sleep(1.5)
    shot("dwell")
    time.sleep(2.5)
    shot("dwell-end")
    skip = 1
    pulse(1, 1.5)
dev.pad("axis", "RX", "mid")
dev.pad("axis", "RY", "mid")
note("seek done", dwells=dwells)
if os.environ.get("LEAVE_RUNNING"):
    note("left running for nav.py")
    sys.exit(0)
press("A")                              # a card, if the test passed
time.sleep(2.0)
shot("after-sweeps")
press("A")
time.sleep(2.0)
shot("after-sweeps2")
hold_axes("ly-up", [("LY", "min")], 2.0)
hold_axes("lx-left", [("LX", "min")], 2.0)
hold_axes("ly-down", [("LY", "max")], 2.0)
press("A")
time.sleep(0.4)
shot("jump")
time.sleep(2.0)
shot("end")
dev.stop(screen_off=True)
note("stopped")
