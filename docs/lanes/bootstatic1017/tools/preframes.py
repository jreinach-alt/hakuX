#!/usr/bin/env python3
"""What the screen showed before the emulator's first present (#1045, H4): judge_video found a 5-frame "green"
episode about 0.7-0.8 s before the probe's first present in both Nova videos that start before the launch (Halo
before 1792284283, Halo R5 1792287441), with no probe present in its window. Is it the app's own UI, the
SurfaceView's first buffers, or a flash?

For one result dir: every video frame from the video's start to the probe's first present + AFTER_S, with
judge_video's numbers (centre-half nb, lit, grn, whole-frame look, class) and the frame's time relative to the
probe's first present (wall, before judge_video's content alignment, which is printed). A contact sheet
(PNG, 4 per row, 320 wide each) of every green or noise frame with NEIGH frames either side.

usage: preframes.py RESULT_DIR OUT_PNG [AFTER_S]
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge_boot  # noqa: E402
import judge_video as jv  # noqa: E402

NEIGH = 3


def main():
    rd, out = sys.argv[1], sys.argv[2]
    after = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    meta = json.load(open(os.path.join(rd, "video", "meta.json")))
    seg = meta["segments"][0]
    path = os.path.join(rd, "video", seg["file"])
    rows = judge_boot.parse_log(os.path.join(rd, "pulled", "boot1045_log.txt"))
    probe0 = int(rows[0]["raw"]["wall_us"]) / 1e6
    lim = probe0 - seg["start_wall"] + after
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts_time",
                         "-of", "csv=p=0", path], capture_output=True, text=True)
    pts = [float(x.split(",")[0]) for x in pr.stdout.split() if x.strip() and x.split(",")[0] not in ("", "N/A")]
    w, h = 640, 480
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-fps_mode", "passthrough", "-vf",
                          "scale=%d:%d:flags=neighbor" % (w, h), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    frames = []
    i = 0
    while True:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        t = pts[i] if i < len(pts) else pts[-1]
        if t > lim:
            break
        px = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
        nb, lit, grn, look = jv.frame_metrics(px)
        cls = jv.classify(nb, lit, grn, judge_boot.NB_FLOOR, look)
        mean = px.reshape(-1, 3).mean(0)
        frames.append({"i": i, "pts": t, "rel": seg["start_wall"] + t - probe0, "nb": nb, "lit": lit, "grn": grn,
                       "look": look, "cls": cls, "mean": mean, "px": px[::2, ::2].copy()})
        i += 1
    p.kill()
    print("%s: video start_wall %.3f, probe first present %.3f (video +%.3f s), %d frames to +%.1f s" % (
        os.path.basename(rd), seg["start_wall"], probe0, probe0 - seg["start_wall"], len(frames), after))
    prev = None
    for f in frames:
        key = (f["cls"], f["look"], tuple(int(x) // 8 for x in f["mean"]))
        if key != prev or f["cls"] in ("green", "noise"):
            print("f%04d pts %.3f rel %+.3f cls %-7s look %-7s nb %5.1f lit %.3f grn %.3f mean %s" % (
                f["i"], f["pts"], f["rel"], f["cls"], f["look"] or "-", f["nb"], f["lit"], f["grn"],
                "/".join("%d" % x for x in f["mean"])))
        prev = key
    bad = [k for k, f in enumerate(frames) if f["cls"] in ("green", "noise")]
    pick = sorted({j for k in bad for j in range(max(0, k - NEIGH), min(len(frames), k + NEIGH + 1))})
    if not pick:
        print("no green or noise frames")
        return 0
    cols = 4
    tw, th = 320, 240
    sheet = Image.new("RGB", (cols * tw, ((len(pick) + cols - 1) // cols) * (th + 14)), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    for k, j in enumerate(pick):
        f = frames[j]
        x, y = (k % cols) * tw, (k // cols) * (th + 14)
        sheet.paste(Image.fromarray(f["px"]), (x, y + 14))
        d.text((x + 2, y + 1), "f%d %+.3fs %s" % (f["i"], f["rel"], f["cls"]), fill=(255, 255, 0))
    sheet.save(out)
    print("sheet: %s (%d frames)" % (out, len(pick)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
