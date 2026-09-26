#!/usr/bin/env python3
"""Classify each capture of a fogfirst session against its golden.

    fogfirst_score.py <captures root> [--goldens /home/justin/goldens/results]

<captures root> is a console run's `console/` directory (Suite_dir/Test.png)
or a dispatcher result's `captures1/` (Suite_dir::Test.png). Each capture is
reported as one of:

  golden  bit-identical to its golden
  halved  an exp-mode capture whose fog coordinate is half the golden's: for
          every f8 band with at least 500 px, the mean ratio of the
          coordinate the capture renders to the coordinate the golden renders
          is within 0.49..0.51, inverting f = 2^(16 m d) with Fog gen's
          m = -0.00225 over the golden's f8 >= 20
  other   anything else, with its differing px

The ratio is read over whole bands, not single pixels. Writes nothing.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

K = 16 * -0.00225
BANDS = [(20, 40), (40, 80), (80, 140), (140, 200), (200, 256)]
EXP_MODES = ("FogGen_FF-exp-", "FogGen_FF-exp_abs-")


def find(root, suite_dir, name):
    for p in (os.path.join(root, suite_dir, name + ".png"),
              os.path.join(root, "%s::%s.png" % (suite_dir, name))):
        if os.path.exists(p):
            return p
    return None


def rgb(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(float)


def f8(a):
    m = (a[..., 0] + a[..., 2] == 255) & (a[..., 1] == 0)
    return np.where(m, a[..., 2], np.nan)


def classify(cap, gold, name):
    a, g = rgb(cap), rgb(gold)
    if a.shape == g.shape and np.array_equal(a, g):
        return "golden", ""
    px = int((np.abs(a - g).max(axis=2) > 0).sum()) if a.shape == g.shape else -1
    if not name.startswith(EXP_MODES):
        return "other", "%d px" % px
    r, gg = f8(a), f8(g)
    ratios = []
    for lo, hi in BANDS:
        s = (gg >= lo) & (gg < hi) & (gg < 255) & (r > 0) & (r < 255) & ~np.isnan(r)  # log2(1) = 0
        if s.sum() < 500:
            continue
        ratios.append(float(np.mean(np.log2(r[s] / 255.0) / np.log2(gg[s] / 255.0))))
    halved = bool(ratios) and all(0.49 <= x <= 0.51 for x in ratios)
    return ("halved" if halved else "other"), "%d px, band ratios %s" % (px, " ".join("%.3f" % x for x in ratios))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    a = ap.parse_args()
    rows = []
    for suite_dir in ("Alpha_func", "Fog_gen"):
        gdir = os.path.join(a.goldens, suite_dir)
        for f in sorted(os.listdir(gdir)):
            name = f[:-4]
            cap = find(a.root, suite_dir, name)
            if cap:
                rows.append((suite_dir, name) + classify(cap, os.path.join(gdir, f), name))
    if not rows:
        print("no Alpha_func or Fog_gen captures under %s" % a.root)
        return 2
    for suite_dir, name, verdict, detail in rows:
        print("%-10s %-28s %-7s %s" % (suite_dir, name, verdict, detail))
    return 0


if __name__ == "__main__":
    sys.exit(main())
