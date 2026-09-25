#!/usr/bin/env python3
"""Evaluate score_sweep.py's `blank` rule, and a replacement, on every capture
that rule has ever fired on.

The rule today (score_sweep.py:229-230) asks three things: is OUR capture
> 90% one colour, does it have <= 4 colours, does the GOLDEN have > 4. The
last is the golden alone, and a golden that is 99% background with a sliver
of ink passes it -- which is how 13 near-exact captures (#297) came to be
filed as `blank` in every run since 09-13.

The replacement keys on what OUR capture lost: `lost` = pixels below the
label band where the golden is ink (not its own dominant colour) and ours is
our dominant colour. A capture is blank when it is flat AND it lost at
least BLANK_MIN_LOST of the image.

Usage: blank_rule_eval.py   (walks $DISPATCH_DIR/results/*/scores*.tsv)
"""
import csv
import glob
import os

import numpy as np
from PIL import Image

GOLDENS = os.environ.get("GOLDENS", "/home/justin/goldens/results")
RESULTS = os.path.join(os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch"),
                       "results")
LABEL_ROWS = 64          # score_sweep.py's label band
BLANK_MIN_LOST = 0.01    # proposed: 1% of the image


def dominant(rgb):
    flat = rgb.reshape(-1, 3)
    cols, counts = np.unique(flat, axis=0, return_counts=True)
    return cols[counts.argmax()], counts


def main():
    latest = {}
    for tsv in glob.glob(os.path.join(RESULTS, "*", "scores*.tsv")):
        try:
            rows = list(csv.DictReader(open(tsv), delimiter="\t"))
        except Exception:
            continue
        cap_dir = os.path.join(os.path.dirname(tsv),
                               "captures" + os.path.basename(tsv)[6:-4])
        for r in rows:
            if r.get("status") != "blank":
                continue
            key = (r["suite"], r["test"])
            p = os.path.join(cap_dir, f"{key[0]}::{key[1]}.png")
            if os.path.exists(p) and (key not in latest
                                      or os.path.getmtime(p) > os.path.getmtime(latest[key])):
                latest[key] = p
    print(f"{'capture':58s} {'differ':>7} {'g_ink':>7} {'lost':>7} {'lost%':>6}  today  proposed")
    for (suite, test), p in sorted(latest.items()):
        g = np.asarray(Image.open(os.path.join(GOLDENS, suite, test + ".png")).convert("RGBA"),
                       dtype=np.int16)
        o = np.asarray(Image.open(p).convert("RGBA"), dtype=np.int16)
        npx = g.shape[0] * g.shape[1]
        gdom, _ = dominant(g[..., :3])
        odom, counts = dominant(o[..., :3])
        gold_colours = len(np.unique(g[..., :3].reshape(-1, 3), axis=0))
        flat = counts.max() / npx > 0.90 and len(counts) <= 4
        today = flat and gold_colours > 4
        body = np.zeros(g.shape[:2], bool)
        body[LABEL_ROWS:] = True
        ink = body & (g[..., :3] != gdom).any(axis=2)
        lost = ink & (o[..., :3] == odom).all(axis=2)
        differ = int((g != o).any(axis=2).sum())
        proposed = flat and lost.sum() >= BLANK_MIN_LOST * npx
        print(f"{suite + '/' + test:58s} {differ:>7} {int(ink.sum()):>7} {int(lost.sum()):>7} "
              f"{100 * lost.sum() / npx:>5.2f}%  {'blank' if today else 'ok':5s}  "
              f"{'blank' if proposed else 'ok'}")


if __name__ == "__main__":
    main()
