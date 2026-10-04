#!/usr/bin/env python3
"""Score a burst of CONSECUTIVE frames for flicker: something on screen in frame
N that is gone (or somewhere else) in N+1 and back in N+2.

    flicker_score.py <burst> [--out DIR] [--gate RATE] [--json]
    flicker_score.py --selftest

<burst> is a directory of frames (png/jpg/ppm, read in name order) or a video
file (screenrecord's mp4; decoded with ffmpeg, see find_ffmpeg). Prints one
line:

    flicker: rate=<hits per 100 triples> p90=<..> max=<..> worst=<a|b|c> ...

and, with --out, flicker.tsv (one row per frame) and flicker_worst.png (the
worst triple side by side, then the middle frame with the blinking pixels in
red). --gate RATE exits 1 when rate > RATE, so a Playable check is one line.

WHY A TRIPLE AND NOT A PAIR. Frame-to-frame difference alone is motion: a
rally car at speed changes half the screen every frame and is not a defect.
A blink is the one thing motion does not do: frame N differs from BOTH of its
neighbours while the neighbours agree with each other. Per pixel, per triple
(N-1, N, N+1):

    blink = max(0, min(|N - (N-1)|, |N - (N+1)|) - |(N+1) - (N-1)|)

Smooth motion puts N between its neighbours, so the min is at most about the
outer difference and blink ~ 0. A scene cut changes N against one neighbour
only, so the min is ~0. An object that vanishes for one frame on a background
that holds still or moves slowly scores the object's contrast. A two-frame
blink is scored the same way with the pair (N, N+1) against (N-1, N+2).

|x| is the largest of the three channel differences (a red car on brown
earth is a small luma step and a large one in R). A pixel is a hit pixel when
blink > PIXEL_T; a 3x3 erosion keeps only pixels whose whole neighbourhood
hit, so single-pixel shimmer on fences and H.264 noise drop out and an object
the size of a car does not. A TRIPLE is a hit when its eroded hit pixels are
more than HIT_PERMILLE of the frame. rate = hit triples per 100.

Consecutive duplicates (mean |diff| < DUP_EPS) are dropped first: a 30 fps
title presented on a 60 Hz panel repeats each frame, and a repeat would make
every real blink look like two frames and every real change look like a
blink of zero. The duplicate share is printed: it is the capture-vs-game rate.

The FPS overlay corner is masked (classify.FPS_CORNER, 1280x960 space).

THRESHOLDS WERE FIXED BEFORE ANY CAPTURE EXISTED (2026-10-04, lane
flicker801, #801): PIXEL_T 40, 3x3 erosion, HIT_PERMILLE 1.0 at 320 px wide,
DUP_EPS 0.6. A change after the first positive control is recorded in
docs/lanes/flicker801/NOTES.md with the reason, not made silently.

WHAT IT CANNOT SEE. A blink faster than the capture (a 60 fps title on a
capture that sustains 30) is invisible here, and so is flicker that always
alternates on the same two frames of a 30 fps repeat once duplicates are
removed (that reads as motion). A legitimate one-frame effect -- a muzzle
flash, a blinking HUD prompt -- scores exactly like a defect: that is why the
negatives are part of the result, not decoration.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image

W = 320                      # analysis width; height follows the aspect
PIXEL_T = 40.0               # grey levels (0-255) of blink to count a pixel
HIT_PERMILLE = 1.0           # eroded hit pixels per 1000 to count a triple
DUP_EPS = 0.6                # mean |diff| below this is a repeated frame
FPS_CORNER = (0, 0, 130, 50)  # x, y, w, h in 1280x960 space (classify.py)
REF_W, REF_H = 1280, 960
EXTS = (".png", ".jpg", ".jpeg", ".ppm")


def find_ffmpeg():
    """$FFMPEG, then ffmpeg on PATH, then the imageio-ffmpeg wheel's static
    binary (pip install imageio-ffmpeg in any venv; the host has no system
    ffmpeg)."""
    cand = [os.environ.get("FFMPEG", "")]
    for d in os.environ.get("PATH", "").split(os.pathsep):
        cand.append(os.path.join(d, "ffmpeg"))
    try:
        import imageio_ffmpeg  # noqa
        cand.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    for root in (os.path.join(here, "..", ".."), os.path.expanduser("~")):
        cand += glob.glob(os.path.join(root, ".flkvenv", "lib", "python3*", "site-packages",
                                       "imageio_ffmpeg", "binaries", "ffmpeg-*"))
    for c in cand:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def mask_corner(a):
    h, w = a.shape[:2]
    x, y, bw, bh = FPS_CORNER
    a[int(y * h / REF_H):int((y + bh) * h / REF_H) + 1,
      int(x * w / REF_W):int((x + bw) * w / REF_W) + 1] = 0
    return a


def load_dir(path):
    names = sorted(f for f in os.listdir(path) if f.lower().endswith(EXTS)
                   and not f.startswith("flicker_"))
    frames, labels = [], []
    for n in names:
        im = Image.open(os.path.join(path, n)).convert("RGB")
        h = max(1, round(im.height * W / im.width))
        frames.append(mask_corner(np.asarray(im.resize((W, h), Image.BOX), dtype=np.float32).copy()))
        labels.append(n)
    return frames, labels, None


def load_video(path):
    ff = find_ffmpeg()
    if not ff:
        raise SystemExit("flicker_score: no ffmpeg ($FFMPEG, PATH, or pip install imageio-ffmpeg)")
    probe = subprocess.run([ff, "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", probe)
    if not m:
        raise SystemExit("flicker_score: cannot read the video size of %s" % path)
    vw, vh = int(m.group(1)), int(m.group(2))
    h = max(2, round(vh * W / vw) // 2 * 2)
    p = subprocess.run([ff, "-hide_banner", "-loglevel", "info", "-i", path,
                        "-fps_mode", "passthrough", "-vf", "scale=%d:%d:flags=area,showinfo" % (W, h),
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True)
    raw = p.stdout
    n = len(raw) // (W * h * 3)
    pts = [float(x) for x in re.findall(rb"pts_time:\s*([0-9.]+)", p.stderr)][:n]
    frames = [mask_corner(np.frombuffer(raw, np.uint8, W * h * 3, i * W * h * 3)
                          .reshape(h, W, 3).astype(np.float32)) for i in range(n)]
    labels = ["f%05d@%.3f" % (i, pts[i]) if i < len(pts) else "f%05d" % i for i in range(n)]
    return frames, labels, pts if len(pts) == n else None


def cdiff(a, b):
    return np.abs(a - b).max(axis=2)


def erode3(m):
    """True where the whole 3x3 neighbourhood is True (edges count as False)."""
    out = np.zeros_like(m)
    c = m[1:-1, 1:-1].copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            c &= m[1 + dy:m.shape[0] - 1 + dy, 1 + dx:m.shape[1] - 1 + dx]
    out[1:-1, 1:-1] = c
    return out


def blink_map(prev, cur, nxt):
    return np.clip(np.minimum(cdiff(cur, prev), cdiff(cur, nxt)) - cdiff(nxt, prev), 0, None)


def blink2_map(prev, c0, c1, nxt):
    inner = np.minimum(np.minimum(cdiff(c0, prev), cdiff(c0, nxt)),
                       np.minimum(cdiff(c1, prev), cdiff(c1, nxt)))
    return np.clip(inner - cdiff(nxt, prev), 0, None)


def permille(bmap):
    m = erode3(bmap > PIXEL_T)
    return 1000.0 * m.sum() / m.size, m


def score(frames, labels, pts=None):
    keep, dups = [0] if frames else [], 0
    for i in range(1, len(frames)):
        if float(np.abs(frames[i] - frames[keep[-1]]).mean()) < DUP_EPS:
            dups += 1
        else:
            keep.append(i)
    F = [frames[i] for i in keep]
    L = [labels[i] for i in keep]
    rows = []
    for j in range(1, len(F) - 1):
        s1 = float(permille(blink_map(F[j - 1], F[j], F[j + 1]))[0])
        s2 = float(permille(blink2_map(F[j - 1], F[j], F[j + 1], F[j + 2]))[0]) if j + 2 < len(F) else 0.0
        rows.append({"j": j, "frame": L[j], "b1": s1, "b2": s2, "s": max(s1, s2)})
    n = len(rows)
    hits = sum(1 for r in rows if r["s"] > HIT_PERMILLE)
    ss = sorted(r["s"] for r in rows)
    res = {
        "frames": len(frames), "unique": len(F), "dup_share": round(dups / max(1, len(frames) - 1), 3),
        "triples": n, "hits": hits, "rate": round(100.0 * hits / n, 2) if n else None,
        "p90": round(float(ss[int(0.9 * (n - 1))]), 3) if n else None,
        "max": round(float(ss[-1]), 3) if n else None,
    }
    if pts and len(pts) > 2:
        kp = [pts[i] for i in keep]
        dt = np.diff(kp)
        if len(dt):
            res["unique_fps"] = round(len(dt) / max(1e-9, kp[-1] - kp[0]), 1)
            res["dt_median_ms"] = round(1000 * float(np.median(dt)), 1)
            res["dt_max_ms"] = round(1000 * float(dt.max()), 1)
    if rows:
        w = max(rows, key=lambda r: r["s"])
        res["worst"] = "%s|%s|%s" % (L[w["j"] - 1], L[w["j"]], L[w["j"] + 1])
        res["_worst_j"] = w["j"]
    return res, rows, F, L


def write_out(out, res, rows, F):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "flicker.tsv"), "w") as f:
        f.write("j\tframe\tblink1_permille\tblink2_permille\thit\n")
        for r in rows:
            f.write("%d\t%s\t%.3f\t%.3f\t%d\n" % (r["j"], r["frame"], r["b1"], r["b2"],
                                                 int(r["s"] > HIT_PERMILLE)))
    j = res.get("_worst_j")
    if j is None:
        return
    _, m = permille(blink_map(F[j - 1], F[j], F[j + 1]))
    over = F[j].copy()
    over[m] = [255, 0, 0]
    strip = np.concatenate([F[j - 1], F[j], F[j + 1], over], axis=1).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(strip)
    im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(os.path.join(out, "flicker_worst.png"))


def run(path, out=None):
    if os.path.isdir(path):
        frames, labels, pts = load_dir(path)
    else:
        frames, labels, pts = load_video(path)
    if len(frames) < 3:
        raise SystemExit("flicker_score: %d frames in %s; need 3 or more" % (len(frames), path))
    res, rows, F, L = score(frames, labels, pts)
    if out:
        write_out(out, res, rows, F)
    res.pop("_worst_j", None)
    return res


def fmt(res):
    keys = ["rate", "p90", "max", "hits", "triples", "frames", "unique", "dup_share",
            "unique_fps", "dt_median_ms", "dt_max_ms", "worst"]
    return "flicker: " + " ".join("%s=%s" % (k, res[k]) for k in keys if k in res)


# ---------------------------------------------------------------- selftest

def _synthetic(gone=lambda i: False, seed=1, n=60, cut_at=30, flash_at=None):
    """A textured background panning 3 px/frame, a 'car' (24x12 at 320x240)
    driving across it, sensor noise, one scene cut. The car is not drawn on
    frames where gone(i)."""
    rng = np.random.default_rng(seed)
    big = rng.normal(110, 40, (240 // 8 + 2, (320 + 3 * n) // 8 + 2, 3))
    bg = np.asarray(Image.fromarray(big.clip(0, 255).astype(np.uint8)).resize(
        ((320 + 3 * n) + 16, 240 + 16), Image.BICUBIC), dtype=np.float32)
    bg2 = bg[::-1, ::-1].copy()
    out = []
    for i in range(n):
        src = bg if i < cut_at else bg2
        f = src[8:248, 8 + 3 * i:8 + 3 * i + 320].copy()
        x = 40 + 2 * i
        if not gone(i):
            f[150:162, x:x + 24] = [200, 30, 30]
        if flash_at is not None and i == flash_at:
            f[100:110, 150:170] = 255
        f += rng.normal(0, 3, f.shape)
        out.append(f.clip(0, 255))
    return out


def selftest():
    bad = 0

    def check(name, ok, detail):
        nonlocal bad
        print("%s %s: %s" % ("ok  " if ok else "FAIL", name, detail))
        bad += 0 if ok else 1

    lab = ["s%03d" % i for i in range(60)]
    every4 = lambda i: i % 4 == 3  # noqa: E731
    neg, _, _, _ = score(_synthetic(), lab)
    pos, _, _, _ = score(_synthetic(every4), lab)
    pos2, _, _, _ = score(_synthetic(lambda i: i % 6 in (4, 5), seed=2), lab)
    one, _, _, _ = score(_synthetic(flash_at=12), lab)
    rep = []
    for f in _synthetic(every4):
        rep += [f, f.copy()]
    dup, _, _, _ = score(rep, ["d%03d" % i for i in range(120)])
    check("clean pan + cut is quiet", neg["hits"] == 0, neg)
    check("car gone 1 frame in 4 is caught", pos["rate"] >= 20.0, pos)
    check("car gone 2 frames in 6 is caught by blink2", pos2["rate"] >= 15.0, pos2)
    check("one flash is one hit (a real effect reads like a defect)", one["hits"] == 1, one)
    check("a 30-on-60 repeat is de-duplicated, same rate", dup["dup_share"] >= 0.45 and
          abs(dup["rate"] - pos["rate"]) < 5, dup)
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("burst", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--gate", type=float)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.burst:
        ap.error("a burst directory or video is required")
    worst = 0
    for b in a.burst:
        res = run(b, a.out if len(a.burst) == 1 else (a.out and os.path.join(a.out, os.path.basename(b.rstrip("/")))))
        res["burst"] = b
        print(json.dumps(res) if a.json else fmt(res) + " burst=" + b)
        if a.gate is not None and res["rate"] is not None and res["rate"] > a.gate:
            worst = 1
    return worst


if __name__ == "__main__":
    sys.exit(main())
