#!/usr/bin/env python3
"""Golden | ours | diff panels for captures the blank rule re-files.

For each suite/test given, takes the newest capture on disk, and writes
<out>/<suite>__<test>.png: golden, ours, and a diff map (differing pixels in
red over a darkened golden), each 2x upscaled. Prints the differing-pixel
count and its bounding box so the panel can be read against the numbers.

Usage: eyecheck.py OUTDIR SUITE/TEST [...]
"""
import csv
import glob
import os
import sys

import numpy as np
from PIL import Image

GOLDENS = os.environ.get("GOLDENS", "/home/justin/goldens/results")
RESULTS = os.path.join(os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch"),
                       "results")


# Only captures whose TSV row carries this status (default: the rows the old
# rule tagged blank), so the panel shows the capture that was actually judged.
STATUS = os.environ.get("STATUS", "blank")


def status_of(cap, suite, test):
    d, name = os.path.split(os.path.dirname(cap))
    tsv = os.path.join(d, "scores" + name[len("captures"):] + ".tsv")
    try:
        for r in csv.DictReader(open(tsv), delimiter="\t"):
            if r.get("suite") == suite and r.get("test") == test:
                return r.get("status")
    except OSError:
        pass
    return None


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for st in sys.argv[2:]:
        suite, test = st.split("/", 1)
        caps = [c for c in glob.glob(os.path.join(RESULTS, "*", "captures*",
                                                  f"{suite}::{test}.png"))
                if status_of(c, suite, test) == STATUS]
        if not caps:
            print(f"{st}: no capture on disk")
            continue
        cap = max(caps, key=os.path.getmtime)
        g = np.asarray(Image.open(os.path.join(GOLDENS, suite, test + ".png")).convert("RGB"))
        o = np.asarray(Image.open(cap).convert("RGB"))
        d = (g != o).any(axis=2)
        ys, xs = np.nonzero(d)
        box = (f"x {xs.min()}-{xs.max()} y {ys.min()}-{ys.max()}" if len(xs) else "none")
        m = (g // 3).copy()
        m[d] = (255, 0, 0)
        panel = np.concatenate([g, o, m], axis=1)
        im = Image.fromarray(panel).resize((panel.shape[1] * 2, panel.shape[0] * 2),
                                           Image.NEAREST)
        p = os.path.join(out, f"{suite}__{test}.png")
        im.save(p)
        print(f"{st}: {d.sum()} px differ, box {box}; {cap} -> {p}")


if __name__ == "__main__":
    main()
