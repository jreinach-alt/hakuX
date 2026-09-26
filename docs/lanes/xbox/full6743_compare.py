#!/usr/bin/env python3
"""Score the full6743 console reference set: C1, per-suite golden/calibration status, first hakuX comparison."""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

CON = "/home/justin/hakux-work/hardware/runs/2026-09-25-full6743/console-run/console"
GOLD = "/home/justin/goldens/results"
CAL = "/home/justin/hakux-work/hardware/runs/2026-09-19-calib/full/out/run1"
REFS = "/home/justin/hakux-work/hardware/runs/2026-09-25-refs6743/console-run/console"
D = "/home/justin/hakux-work/dispatch/results/"
EMU_RUNS = ["1790367037-xbox-full6743-dry1c-1030645", "1790359589-xbox-full6743-dry2-2802408",
            "1790359589-xbox-full6743-dry3-2802696", "1790367037-xbox-full6743-rtl2-1030692",
            "0-0-x-1790367876-xbox-full6743-wbuf1-1397876", "0-0-x-1790367877-xbox-full6743-wbuf2-1398442",
            "0-0-x-1790367877-xbox-full6743-tail-1398955"]


def same_bytes(a, b):
    if os.path.getsize(a) != os.path.getsize(b):
        return False
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return fa.read() == fb.read()


def px_diff(a, b):
    x = np.asarray(Image.open(a).convert("RGBA")).astype(np.int16)
    y = np.asarray(Image.open(b).convert("RGBA")).astype(np.int16)
    if x.shape != y.shape:
        return -1, -1
    d = np.abs(x - y).max(axis=2)
    return int((d > 0).sum()), int(d.max())


def main():
    emu = {}
    for r in EMU_RUNS:
        for p in glob.glob(os.path.join(D, r, "captures1", "*::*.png")):
            emu.setdefault(os.path.basename(p), p)   # first run wins; the W buffering #8 duplicate is identical in name
    rows = []
    for suite_dir in sorted(os.listdir(CON)):
        sd = os.path.join(CON, suite_dir)
        if not os.path.isdir(sd):
            continue
        for f in sorted(os.listdir(sd)):
            if not f.endswith(".png"):
                continue
            c = os.path.join(sd, f)
            row = {"suite": suite_dir, "file": f}
            g = os.path.join(GOLD, suite_dir, f)
            if os.path.exists(g):
                if same_bytes(c, g):
                    row["golden"] = "identical"
                else:
                    n, m = px_diff(c, g)
                    row["golden"] = "same-pixels" if n == 0 else "differs"
                    row["golden_px"], row["golden_max"] = n, m
            else:
                row["golden"] = "none"
            k = os.path.join(CAL, "%s::%s" % (suite_dir, f))
            if os.path.exists(k):
                if same_bytes(c, k):
                    row["calib"] = "identical"
                else:
                    n, m = px_diff(c, k)
                    row["calib"] = "same-pixels" if n == 0 else "differs"
                    row["calib_px"] = n
            else:
                row["calib"] = "none"
            e = emu.get("%s::%s" % (suite_dir, f))
            if e:
                n, m = px_diff(c, e)
                row["hakux_px"], row["hakux_max"] = n, m
            else:
                row["hakux_px"] = None
            rows.append(row)
    json.dump(rows, open("/tmp/claude-1000/-home-justin-hakuX/20b48eee-b954-42c8-afc3-497553bbc179/scratchpad/full_rows.json", "w"))
    print("captures scored:", len(rows))
    # C1
    af = [r for r in rows if r["suite"] == "Alpha_func"]
    print("C1 Alpha_func vs goldens: %d/%d identical" % (sum(r["golden"] == "identical" for r in af), len(af)))
    for sd in ("Fog_planar_vsh", "Surface_as_vertex_array"):
        ok = tot = 0
        for f in sorted(os.listdir(os.path.join(REFS, sd))):
            tot += 1
            ok += same_bytes(os.path.join(REFS, sd, f), os.path.join(CON, sd, f)) if os.path.exists(os.path.join(CON, sd, f)) else 0
        print("C1 %s vs PR #261 run: %d/%d identical" % (sd, ok, tot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
