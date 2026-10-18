"""Summarise bandfit.py's TSV: does each draw's on-screen offset follow c13.w, or stay put? (#939, M2)

usage: bandsum.py BANDFIT.tsv [minpx=N]

Per draw, over the frames with at least minpx pixels (default 1000):
  - the least-squares slope of d* on c13.w: 1 for a surface that turns on
    screen as the guest says, 0 for a static one;
  - the rms of d* - c13.w (the turning model's residual) and of d* - mean(d*)
    (the static model's), both in texels of the mip the fit used;
  - the median r at c13.w against r at the first frame's c13.w.
"""
import sys

import numpy as np

opt = dict(a.split("=", 1) for a in sys.argv[2:])
MINPX = int(opt.get("minpx", 1000))
rows = [ln.split("\t") for ln in open(sys.argv[1]).read().splitlines()[1:]]
TW = {"n4": 2048, "n5": 1024}
for k in sorted(set(r[1] for r in rows)):
    R = [r for r in rows if r[1] == k and r[4] and int(r[2]) >= MINPX]
    if len(R) < 3:
        print(f"{k}: {len(R)} frames with >= {MINPX} px, nothing to fit")
        continue
    c = np.array([float(r[3]) for r in R])
    d = np.array([float(r[4]) for r in R])
    rc = np.array([float(r[7]) for r in R])
    rf = np.array([float(r[8]) for r in R])
    lod = int(np.median([int(r[9]) for r in R]))
    tex = TW[k] >> lod
    s, i0 = np.polyfit(c, d, 1)
    resid = d - (s * c + i0)
    se = np.sqrt(np.sum(resid ** 2) / (len(c) - 2) / np.sum((c - c.mean()) ** 2))
    turn = np.sqrt(np.mean((d - c - np.mean(d - c)) ** 2)) * tex
    static = np.sqrt(np.mean((d - d.mean()) ** 2)) * tex
    print(f"{k}: {len(R)} frames f{R[0][0]}..f{R[-1][0]}, c13.w {c.min():.5f}..{c.max():.5f} "
          f"(span {(c.max() - c.min()) * tex:.1f} texels at lod {lod})")
    print(f"    slope d*/c13.w {s:.3f} +- {se:.3f}; rms about 'turns' {turn:.2f} texels, about 'static' {static:.2f}")
    print(f"    median r at c13.w {np.median(rc):.3f}, at the first frame's c13.w {np.median(rf):.3f}")
