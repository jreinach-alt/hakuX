#!/usr/bin/env python3
"""Runs of video frames by whole-frame look, over a Nova result's screen video: how long the screen showed black, a
picture, the Xbox logo, static or streaks, in screen frames and ms (pts), from the video's start. Asked for the
after arm's Halo run, where the probe shows the kernel's logo drawn for one present with the screen on (n144)
between screen-off windows, which R1 now blanks: is the logo on the screen as a blink?

usage: vidruns.py RESULT_DIR [MAX_S]

Each frame is decoded at 320 wide; its look is judge_nova.full_frame's (static, streaks, black, picture), with
"logo" for a picture whose lit share is 0.02-0.15 and green share >= 0.4 of the lit pixels (the logo's green X on
black; the logo frames of 1792282757 measure lit 0.083, grn 0.056).
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def look(a):
    a = a.astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    litm = np.maximum(np.maximum(r, g), b) > 24
    lit = float(litm.mean())
    grn = float(((g >= 48) & (g > r + 32) & (g > b + 32)).mean())
    nbh = float(np.abs(a[:, 1:] - a[:, :-1]).mean())
    nbv = float(np.abs(a[1:] - a[:-1]).mean())
    if nbh >= 20 and lit >= 0.10:
        return "static"
    if nbv >= 5 and nbv >= 4 * nbh and lit >= 0.05:
        return "streaks"
    if lit < 0.01:
        return "black"
    if 0.02 <= lit <= 0.15 and grn >= 0.4 * lit:
        return "logo"
    return "picture"


def main():
    rd = sys.argv[1]
    mx = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
    vd = os.path.join(rd, "video")
    mp4 = sorted(f for f in os.listdir(vd) if f.endswith(".mp4"))[0]
    path = os.path.join(vd, mp4)
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts_time",
                         "-read_intervals", "%%+%g" % mx, "-of", "json", path], capture_output=True, text=True)
    pts = [float(f["pts_time"]) for f in json.loads(pr.stdout)["frames"] if "pts_time" in f]
    w, h = 320, 240
    raw = subprocess.run(["ffmpeg", "-v", "error", "-t", str(mx), "-i", path, "-vf", "scale=%d:%d" % (w, h),
                          "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    n = len(raw) // (w * h * 3)
    fr = np.frombuffer(raw[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)
    runs = []
    for i in range(n):
        lk = look(fr[i])
        t = pts[i] if i < len(pts) else float("nan")
        if runs and runs[-1][0] == lk:
            runs[-1][2], runs[-1][3] = t, runs[-1][3] + 1
        else:
            runs.append([lk, t, t, 1])
    print("%s: %d frames to %.1f s" % (mp4, n, mx))
    for lk, a, b, c in runs:
        print("%-8s %6.3f-%6.3f s  %4d frames  %6.0f ms" % (lk, a, b, c, (b - a) * 1000 + 16.7))
    return 0


if __name__ == "__main__":
    sys.exit(main())
