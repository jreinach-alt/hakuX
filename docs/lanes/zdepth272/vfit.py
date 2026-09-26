"""Fit silicon's per-vertex depth from the golden, per primitive, by region.

For each primitive, take the per-column (or per-row) median of the golden over
pixels the primitive owns in the replay, add 0.5 (centre of the floor cell)
and least-squares a line in k -> (a, b), the depths at the two vertices.
Compare with a model's vertex depths.
"""
import os
import sys
from fractions import Fraction as F
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from dbff import render, zeta_word, GOLD, primitives, vz  # noqa: E402
from model import C22, C32  # noqa: E402

RTZ = dict(mul='rtz', add='rtz', fin='rtz', div='rcp', rcp='rtz', rbits=24)


def fit(img, pid, prims):
    out = []
    for n, (kind, x0, x1, y0, y1, za, zb, span) in enumerate(prims):
        own = pid[y0:y1, x0:x1] == n
        sub = img[y0:y1, x0:x1].astype(float)
        sub = np.where(own, sub, np.nan)
        if kind == 'x':
            col = np.nanmedian(sub, axis=0) if own.any() else None
            cnt = own.sum(axis=0)
        else:
            col = np.nanmedian(sub, axis=1) if own.any() else None
            cnt = own.sum(axis=1)
        if col is None:
            continue
        k = np.arange(len(col))
        ok = (cnt >= 3) & ~np.isnan(col)
        if ok.sum() < 4:
            continue
        A = np.stack([1 - k[ok] / span, k[ok] / span], axis=1)
        (a, b), *_ = np.linalg.lstsq(A, col[ok] + 0.5, rcond=None)
        out.append((n, za, zb, a, b, int(ok.sum())))
    return out


def exact(z):
    z = F(float(z))
    return (z * C22 + C32) / (z + 7)


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "z24_Cn_FZn_Mffffff_ZB"
    cutoff = int(name.split("_M")[1].split("_")[0], 16)
    g = zeta_word(os.path.join(GOLD, name + ".png"))
    prims = primitives()
    _, pid = render(RTZ, cutoff, tag=True)
    rows = []
    for n, za, zb, a, b, nk in fit(g, pid, prims):
        for z, v in ((za, a), (zb, b)):
            w = float(z) + 7
            rows.append((w, v - float(exact(z)), v - float(vz(z, RTZ)), n))
    rows.sort()
    # bin by w
    rows = np.array(rows)
    edges = [0, 1.01, 2, 4, 8, 16, 32, 64, 100, 130, 160, 180, 190, 195, 201]
    print("%-12s %5s %14s %14s" % ("w band", "n", "sil-exact med", "sil-RTZ med"))
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (rows[:, 0] >= lo) & (rows[:, 0] < hi)
        if m.any():
            print("[%6.2f,%6.2f) %5d %14.2f %14.2f   (RTZ p10/p90 %.2f %.2f)" % (
                lo, hi, m.sum(), np.median(rows[m, 1]), np.median(rows[m, 2]),
                np.percentile(rows[m, 2], 10), np.percentile(rows[m, 2], 90)))
    for r in rows:
        if r[3] >= 324:
            print("prim %d w=%.3f sil-exact %.3f sil-RTZ %.3f" % (r[3], r[0], r[1], r[2]))
