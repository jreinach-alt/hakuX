#!/usr/bin/env python3
"""Measure the red/grey checker boundary displacement in the Bump_map captures.

Why this and not a pixel diff: the ``Bump_map`` goldens hold exactly two
colours wherever we are structurally wrong (measured -- see
bump_decompose.py), so a pixel count says only *how many* pixels fell on the
wrong side of a boundary, never *where the boundary should be*. The boundary
position, on the other hand, is a direct readout of the displacement the bump
stage applied: TEX1 is a fixed checkerboard, so a cell edge sits where
``pT + dsdt`` crosses a cell line. Comparing edge positions against the
goldens therefore measures hardware's dS in screen pixels, which is the
quantity a candidate rule has to reproduce.

Reported per capture: how many golden edges we place exactly, the mean signed
and mean absolute displacement, and the checker cell period (so a displacement
can be converted to cells and texels). A systematically wrong bump matrix,
scale or offset shows up as a mean displacement of whole pixels; filter
precision shows up as a mean near zero with a +-1 tail.

Usage: bump_edge_shift.py [--suite Bump_map] [--tsv OUT]
"""
import argparse
import os

import numpy as np
from PIL import Image

GOLD = "/home/justin/goldens/results"
CAPS = {
    "Bump_map": "/home/justin/hakux-work/dispatch/results/z-sweep-010-Bump_map/captures1",
    "Bump_env_lum": "/home/justin/hakux-work/dispatch/results/z-sweep-009-Bump_env_lum/captures1",
}
# The two colours TEX1's checkerboard resolves to in the framebuffer: the
# opaque red cell and the half-alpha grey cell over the 0xFE202020 clear.
RED = np.array([254, 0, 0])
GREY = np.array([33, 32, 32])


def load(p):
    return np.asarray(Image.open(p).convert("RGBA"), dtype=np.int16)


def classify(img):
    r = np.abs(img[..., :3] - RED).max(2) == 0
    g = np.abs(img[..., :3] - GREY).max(2) == 0
    return r, (r | g)


def row_edges(cellmask, valid):
    """Columns where the red/grey class flips, inside this row's quad span."""
    x = np.flatnonzero(valid)
    if len(x) < 8:
        return None, None
    a, b = x[0], x[-1]
    seg = cellmask[a:b + 1].astype(np.int8)
    return np.flatnonzero(np.diff(seg) != 0) + 1 + a, (int(a), int(b))


def measure(suite, test, cap=20):
    g = load(f"{GOLD}/{suite}/{test}.png")
    o = load(f"{CAPS[suite]}/{suite}::{test}.png")
    gm, gv = classify(g)
    om, ov = classify(o)
    d, periods = [], []
    unmatched = rows = gold_edges = 0
    for row in range(g.shape[0]):
        ge, s1 = row_edges(gm[row], gv[row])
        oe, s2 = row_edges(om[row], ov[row])
        if ge is None or oe is None or not len(ge) or not len(oe) or s1 != s2:
            continue
        rows += 1
        gold_edges += len(ge)
        if len(ge) > 2:
            periods.extend(np.diff(ge).tolist())
        for e in ge:
            k = int(np.argmin(np.abs(oe - e)))
            if abs(oe[k] - e) <= cap:
                d.append(int(oe[k] - e))
            else:
                unmatched += 1
    if not d:
        return None
    d = np.array(d)
    return dict(
        rows=rows, gold_edges=gold_edges, matched=len(d), unmatched=unmatched,
        mean=float(d.mean()), abs_mean=float(np.abs(d).mean()),
        frac_exact=float((d == 0).mean()),
        max_abs=int(np.abs(d).max()),
        cell_period=float(np.median(periods)) if periods else 0.0,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="Bump_map")
    ap.add_argument("--tsv")
    a = ap.parse_args()

    cols = ["suite", "test", "rows", "gold_edges", "matched", "unmatched",
            "mean_dx", "abs_mean_dx", "frac_exact", "max_abs_dx",
            "cell_period_px"]
    out = []
    for n in sorted(os.listdir(CAPS[a.suite])):
        if not (n.endswith(".png") and "::" in n):
            continue
        s, t = n[:-4].split("::", 1)
        r = measure(s, t)
        if r is None:
            print(f"{t}: no red/grey classification (not a two-colour capture)")
            continue
        r["suite"], r["test"] = s, t
        out.append(r)

    lines = ["\t".join(cols)]
    hdr = (f"{'test':32}{'goldE':>7}{'unm':>6}{'mean':>8}{'|mean|':>8}"
           f"{'exact':>8}{'maxabs':>8}{'cell':>7}")
    print(hdr)
    for r in sorted(out, key=lambda x: -x["abs_mean"]):
        print(f"{r['test']:32}{r['gold_edges']:7}{r['unmatched']:6}"
              f"{r['mean']:8.3f}{r['abs_mean']:8.3f}"
              f"{r['frac_exact']*100:7.1f}%{r['max_abs']:8}"
              f"{r['cell_period']:7.1f}")
        lines.append("\t".join([
            r["suite"], r["test"], str(r["rows"]), str(r["gold_edges"]),
            str(r["matched"]), str(r["unmatched"]), f"{r['mean']:.4f}",
            f"{r['abs_mean']:.4f}", f"{r['frac_exact']:.4f}",
            str(r["max_abs"]), f"{r['cell_period']:.1f}"]))
    if a.tsv:
        with open(a.tsv, "w") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
