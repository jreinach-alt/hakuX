#!/usr/bin/env python3
"""lane.blinx2input: drive Blinx 2 from launch through Test 1's balloon steps.

Phases (argv[2], default "boot"; a later phase starts on a running game):
  boot  launch, START at the title, A until Test 1's HUD (rstick_probe.py)
  tp    third-person balloons: RY held at -32000, RX pulses (run 5's recipe)
  fp    A, R3, A, then first-person balloons: RX and RY both pulsed
  after A through any cards, leave the game running for nav.sh

    SERIAL=ee317437 python3 test1.py <out_dir> [phase]
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.expanduser("~/hakux-work/wt/pathfind/docs/testing/titles"))
import pathfind  # noqa: E402

ISO = ("/storage/E6C6-D7AA/Games/XBox/"
       "4D530065-Blinx_2_Battle_of_Time_Space_Blinx_2_Masters_of_Time_Space.xiso.iso")
OUT = sys.argv[1]
PHASES = ["boot", "tp", "fp", "after"]
start = PHASES.index(sys.argv[2] if len(sys.argv) > 2 else "boot")
os.makedirs(OUT, exist_ok=True)
dev = pathfind.Device("nova")
log = open(os.path.join(OUT, "log.jsonl"), "a")
t0 = time.time()
n = len([f for f in os.listdir(OUT) if f.endswith(".png")])


def note(what, **kw):
    rec = dict(t=round(time.time() - t0, 1), what=what, **kw)
    log.write(json.dumps(rec) + "\n")
    log.flush()
    print(json.dumps(rec), flush=True)


def shot(label):
    global n
    n += 1
    p = os.path.join(OUT, f"{n:03d}-{label}.png")
    dev.capture(p)
    return p, np.asarray(Image.open(p).convert("RGB")).astype(int)


def press(btn, after=0.35):
    dev.pad("press", btn, 120)
    note("press", btn=btn)
    time.sleep(after)


REF = os.path.dirname(os.path.abspath(__file__)) + "/ref"


def sig(path):
    im = Image.open(path).convert("L").resize((16, 12), Image.BOX)
    return np.frombuffer(im.tobytes(), np.uint8).astype(int)


def dist(a, b):
    return float(np.abs(a - b).mean())


TITLE = sig(REF + "/title.png")
TEST1 = sig(REF + "/test1.png")


def card(a):
    """The tutorial's green dialogue box across the bottom (run 5 frame 053)."""
    h, w, _ = a.shape
    z = a[int(0.86 * h):int(0.94 * h), int(0.45 * w):int(0.9 * w)]
    return ((z[..., 1] > z[..., 0] + 30) & (z[..., 1] > z[..., 2])).mean() > 0.5


def olive(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (g > 100) & (g - r > 20) & (g - r < 80) & (b < 0.5 * g) & (r > 60)


def blob(m, w, h, near=None):
    """Mean of the olive pixels round the densest 32 px cell, so a second
    balloon or a stray HUD pixel does not pull the aim between them."""
    ys, xs = np.nonzero(m)
    if len(xs) < 200:
        return None
    if near:
        cells = (ys // 32) * 1000 + xs // 32
        vals, counts = np.unique(cells, return_counts=True)
        c = vals[counts.argmax()]
        cy, cx = (c // 1000) * 32 + 16, (c % 1000) * 32 + 16
        keep = np.hypot(xs - cx, ys - cy) < near * w
        xs, ys = xs[keep], ys[keep]
    return round(float(xs.mean()) / w - 0.5, 3), round(float(ys.mean()) / h, 3), int(len(xs))


def balloon_tp(a):
    h, w, _ = a.shape
    m = olive(a)
    m[: int(0.18 * h), : int(0.30 * w)] = False      # HUD health bar
    m[int(0.50 * h):, :] = False                     # radar, the player (green at y 0.57-0.6)
    return blob(m, w, h)


CX, CY = 0.5, 0.49     # first-person crosshair centre (center3 frames)


def balloon_fp(a):
    """center3 failed on two things: the crosshair ring's edge passes olive(),
    and the balloons sat in the masked lower half. Mask the ring annulus
    (radius ~0.06 w, ticks to ~0.085 w) and only the HUD corners."""
    h, w, _ = a.shape
    m = olive(a)
    yy, xx = np.mgrid[0:h, 0:w]
    rr = np.hypot((xx - CX * w), (yy - CY * h)) / w
    m[(rr < 0.015) | ((rr > 0.045) & (rr < 0.09))] = False   # centre dot, ring
    m[: int(0.18 * h), : int(0.30 * w)] = False      # health bar
    m[int(0.60 * h):, : int(0.22 * w)] = False       # radar
    m[int(0.75 * h):, int(0.30 * w):] = False        # item bar, TS-5000X counter
    return blob(m, w, h, near=0.1)


def pulse(axis, sign, secs):
    dev.pad("axis", axis, str(22000 * sign))
    time.sleep(max(0.08, secs))
    dev.pad("axis", axis, "mid")


def boot():
    dev.launch(ISO)
    note("launch", iso=ISO)
    while time.time() - t0 < 300:
        _, a = shot("boot")
        s = sig(os.path.join(OUT, f"{n:03d}-boot.png"))
        if dist(s, TITLE) < 25:
            press("START")
            break
        time.sleep(3)
    for _ in range(40):
        time.sleep(4)
        shot("menu")
        d = dist(sig(os.path.join(OUT, f"{n:03d}-menu.png")), TEST1)
        note("menu", test1=round(d, 1))
        if d < 12:
            return True
        press("A")
    return False


def tp(limit=300):
    dev.pad("axis", "RY", "-32000")
    end = time.time() + limit
    skip = 0
    while time.time() < end:
        _, a = shot("tp")
        if card(a):
            note("tp card")
            dev.pad("axis", "RY", "mid")
            return True
        bl = balloon_tp(a)
        note("tp", at=bl, skip=skip)
        if bl is None or skip:
            skip = max(0, skip - 1)
            pulse("RX", 1, 0.8)
            continue
        dx = bl[0]
        if abs(dx) > 0.06:
            # run 7: x2.0 swung +-0.4 widths for 200 s; adb adds ~0.15 s to every pulse
            pulse("RX", 1 if dx > 0 else -1, min(0.6, abs(dx) * 0.6))
            time.sleep(0.4)
            continue
        note("tp dwell")
        time.sleep(4.0)
        skip = 1
        pulse("RX", 1, 1.5)
    dev.pad("axis", "RY", "mid")
    return False


def fp(limit=300):
    press("A", 1.5)                       # "Now let's try first-person view. Click the Right thumbstick."
    press("R3", 1.5)
    _, a = shot("r3")
    if card(a):
        press("A", 1.0)                   # "Now locate the 3 balloons in first-person view."
    end = time.time() + limit
    held = 0
    while time.time() < end:
        _, a = shot("fp")
        if card(a):
            note("fp card")
            return True
        bl = balloon_fp(a)
        note("fp", at=bl, held=held)
        if bl is None or held > 6:
            held = 0
            pulse("RX", 1, 0.8)
            continue
        dx, dy = bl[0], bl[1] - CY
        if abs(dx) > 0.03:
            pulse("RX", 1 if dx > 0 else -1, min(0.6, abs(dx) * 0.6))
        if abs(dy) > 0.04:                # RY > 0 looks down (run 2 frame 066)
            pulse("RY", 1 if dy > 0 else -1, min(0.6, abs(dy) * 0.6))
        if abs(dx) <= 0.03 and abs(dy) <= 0.04:
            held += 1
            time.sleep(1.5)
        else:
            held = 0
            time.sleep(0.2)
    return False


def after():
    for _ in range(6):
        time.sleep(1.5)
        _, a = shot("after")
        if not card(a):
            break
        press("A", 1.0)
    note("left running for nav.sh")


ok = True
for ph in PHASES[start:]:
    note("phase", name=ph)
    ok = {"boot": boot, "tp": tp, "fp": fp, "after": after}[ph]() is not False
    note("phase end", name=ph, ok=ok)
    if not ok:
        break
dev.pad("axis", "RX", "mid")
dev.pad("axis", "RY", "mid")
