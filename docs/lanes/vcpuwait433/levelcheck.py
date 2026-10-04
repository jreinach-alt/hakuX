#!/usr/bin/env python3
"""lane.vcpuwait433 (#433): is Tron 2.0 in a level, read from the route's frames.

  levelcheck.py <route-frames dir> [--last N] [--since HHMMSS] [--each]

The capture's gate asks this before it records (owner order 2026-10-02 20:05:
confirm the level from the frames, not from the route's mark). Two features,
both from Tron's own screen, both deterministic:

  hud    Tron's in-level health and energy bars, bottom centre of the frame
         (1280x960 screencap): a green bar ending at x~525 and a red bar
         starting at x~755, both at y~862-878. Menus, the loading card and the
         opening-credits cinematic draw neither (tron1, tron2).
  moves  the view between consecutive in-loop shots (fwd/right/left, which the
         route takes after a stick input) differs: mean absolute grey-level
         difference of the play area, HUD rows cut, >= MOVE_MIN. A paused or
         frozen level keeps its HUD but stops moving.

LEVEL when at least HUD_MIN of the last N loop frames show the HUD and at least
one consecutive pair of HUD frames moves. Prints one line per frame with
--each, then `level=1|0 hud=k/n moves=m/p reason=...`; exit 0 on level, 1 not.

Thresholds (fixed from these frames before any capture used them):
  positive  dispatch/results/0-1790974820-tronhang672-2186958 (Auto Load,
            in-level, 28-34 fps): see NOTES.md section 4 for the table.
  negative  perf/2026-10-02-vcpuwait433/tron1 (Options menu),
            perf/2026-10-02-vcpuwait433/tron2 (credits cinematic, loading card).
"""
import argparse
import os
import re
import sys

import numpy as np
from PIL import Image

LOOP_SHOTS = ("fwd", "right", "left")
GREEN = (862, 878, 440, 520)   # y0, y1, x0, x1: the green bar's centre end
RED = (862, 878, 760, 840)     # the red bar's centre end
VIEW = (120, 820)              # rows of the play area (HUD bars and FPS text cut)
BAR_FRAC = 0.8                 # share of bar pixels that must be the bar colour
HUD_MIN = 4                    # of the last N frames
MOVE_MIN = 12.0                # grey levels (0-255), mean abs diff of the view


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int16)


def hud(a):
    if a.shape[0] < 960 or a.shape[1] < 1280:
        return False
    y0, y1, x0, x1 = GREEN
    g = a[y0:y1, x0:x1].reshape(-1, 3)
    gok = ((g[:, 1] > 100) & (g[:, 1] > g[:, 0] + 50) & (g[:, 1] > g[:, 2] + 50)).mean()
    y0, y1, x0, x1 = RED
    r = a[y0:y1, x0:x1].reshape(-1, 3)
    rok = ((r[:, 0] > 120) & (r[:, 0] > r[:, 1] + 80) & (r[:, 0] > r[:, 2] + 80)).mean()
    return gok >= BAR_FRAC and rok >= BAR_FRAC


def grey_view(a):
    v = a[VIEW[0]:VIEW[1]]
    g = v[..., 0] * 0.299 + v[..., 1] * 0.587 + v[..., 2] * 0.114
    return g[::4, ::4]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--last", type=int, default=6)
    ap.add_argument("--since", default="", help="HHMMSS: only frames at or after this stamp")
    ap.add_argument("--each", action="store_true")
    o = ap.parse_args()
    names = []
    for n in sorted(os.listdir(o.dir)):
        m = re.match(r"(\d{6})-(\w+)\.png$", n)
        if m and m.group(2) in LOOP_SHOTS and m.group(1) >= o.since:
            names.append(n)
    names = names[-o.last:]
    if len(names) < o.last:
        print(f"level=0 hud=0/{len(names)} moves=0/0 reason=only {len(names)} loop frames (need {o.last})")
        return 1
    hs, views = [], []
    for n in names:
        try:
            a = load(os.path.join(o.dir, n))
        except Exception as e:  # a frame still being written reads as not-level
            print(f"level=0 hud=0/{len(names)} moves=0/0 reason=unreadable {n}: {e}")
            return 1
        hs.append(hud(a))
        views.append(grey_view(a) if a.shape[0] >= VIEW[1] else None)
    moves, pairs = 0, 0
    for i in range(1, len(names)):
        d = None
        if hs[i] and hs[i - 1] and views[i] is not None and views[i - 1] is not None \
                and views[i].shape == views[i - 1].shape:
            d = float(np.abs(views[i] - views[i - 1]).mean())
            pairs += 1
            moves += d >= MOVE_MIN
        if o.each:
            print(f"{names[i]} hud={int(hs[i])} diff={'-' if d is None else f'{d:.1f}'}")
    k = sum(hs)
    if k < HUD_MIN:
        reason = f"HUD bars in {k} of {len(names)} frames (need {HUD_MIN})"
    elif moves < 1:
        reason = f"view never moved ({pairs} HUD pairs, none >= {MOVE_MIN})"
    else:
        reason = "in level"
    ok = k >= HUD_MIN and moves >= 1
    print(f"level={int(ok)} hud={k}/{len(names)} moves={moves}/{pairs} reason={reason} last={names[-1]}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
