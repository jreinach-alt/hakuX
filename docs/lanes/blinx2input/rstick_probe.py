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
    return list(im.getdata())


def dist(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


# Grey 16x12 signatures. Title vs other title frames 8-19, vs anything else
# >= 37; bearings card vs itself 0.2, vs the Test 1 card before it 14.
TITLE = sig(REF + "/title.png")        # "Press START to begin." (run 1 frame 015)
BEARINGS = sig(REF + "/bearings.jpg")  # "Move the Right thumbstick..." (unguided 009)


def look(label):
    shot(label)
    s = sig(os.path.join(OUT, f"{n:03d}-{label}.png"))
    d = dict(title=round(dist(s, TITLE), 1), bearings=round(dist(s, BEARINGS), 1))
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
    if look("menu")["bearings"] < 7:
        break
    press("A")
press("A")
time.sleep(2.5)
shot("test1-start")

# The card's instruction: the right stick. Sweep all the way round, twice.
for rnd in (1, 2):
    hold_axes(f"rx-max-{rnd}", [("RX", "max")], 3.0)
    hold_axes(f"rx-min-{rnd}", [("RX", "min")], 3.0)
    hold_axes(f"ry-min-{rnd}", [("RY", "min")], 1.5)
    hold_axes(f"ry-max-{rnd}", [("RY", "max")], 1.5)
    hold_axes(f"rx-max-long-{rnd}", [("RX", "max")], 6.0)
    press("A")                          # any card that came up
    time.sleep(2.0)
    shot(f"after-round-{rnd}")

# Then movement and jump.
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
