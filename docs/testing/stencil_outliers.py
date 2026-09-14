#!/usr/bin/env python3
"""Count the Stencil suite's WRONG RUNS, per run, and say what shape each is.

#79's whole finding is that a Stencil number from a single run means nothing:
for every unstable capture the MAJORITY image is golden-exact and the outliers
are wrong. So the quantity to judge is not a differing-pixel total and not a
median -- `ab_compare` compares medians, and a capture wrong in one run of four
has median 0 and reads as a pass. The quantity is **how many (run, capture)
observations are not bit-identical to the golden**, counted over every run of
an arm.

    stencil_outliers.py RESULTDIR [RESULTDIR ...]      # one line per run
    stencil_outliers.py --json RESULTDIR               # machine-readable
    stencil_outliers.py --floor                        # the published floor

The shape column classifies the DIFFERENCE mask (golden XOR ours) against the
two quads of `stencil_tests.cpp`, and it is a triage aid, not the mechanism
argument. A difference mask is a symmetric difference of two drawn regions, so
a torn draw usually lands in `quad-other` rather than in `half-quad`; the
torn-vertex fit that identifies the mechanism is done on the DRAWN regions --
"which pixels did we colour green" -- and lives in
docs/investigations/stencil-is-the-guest-pgraph-skew.md. Read `half-quad` as
"this one is unambiguous", never `quad-other` as "this one is not torn".

Accepts a dispatcher result directory or a captures directory, via captures.py
-- a tool that reads captures and silently finds none answers anyway, and that
has cost two falsifiers on this project.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures as caps  # noqa: E402

SUITE = "Stencil"
DEFAULT_GOLDENS = os.environ.get("GOLDENS", "/home/justin/goldens/results")

# Geometry from stencil_tests.cpp: a 200x200 quad and a 100x100 quad, both
# centred on a 640x480 framebuffer.
OUTER = (220, 419, 140, 339)   # x0, x1, y0, y1 inclusive
INNER = (270, 369, 190, 289)


def _mask(box, shape):
    x0, x1, y0, y1 = box
    m = np.zeros(shape[:2], bool)
    m[y0:y1 + 1, x0:x1 + 1] = True
    return m


def _tri(shape, p0, p1, p2):
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    px, py = xx + 0.5, yy + 0.5
    (x0, y0), (x1, y1), (x2, y2) = p0, p1, p2
    d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(d) < 1e-9:
        return np.zeros((h, w), bool)
    a = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / d
    b = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / d
    return (a >= 0) & (b >= 0) & (1 - a - b >= 0)


def _bitri_halves(shape, box):
    """The two triangles DefineBiTri lays down for a quad."""
    x0, x1, y0, y1 = box
    l, t, r, b = float(x0), float(y0), float(x1 + 1), float(y1 + 1)
    return [_tri(shape, (l, t), (l, b), (r, b)),
            _tri(shape, (l, t), (r, b), (r, t))]


def classify(diff, shape):
    """Name the shape of a differing-pixel mask."""
    outer, inner = _mask(OUTER, shape), _mask(INNER, shape)
    if (diff & ~outer).any():
        return "outside-quad"
    halves = _bitri_halves(shape, OUTER) + _bitri_halves(shape, INNER)
    n = int(diff.sum())
    for h in halves:
        inter = int((diff & h).sum())
        union = int((diff | h).sum())
        # 1-px slack: the fill rule at a shared diagonal is not the guest's.
        if union and inter / union >= 0.97:
            return "half-quad"
    if n == int(outer.sum()) and (diff == outer).all():
        return "whole-quad"
    if n == int(inner.sum()) and (diff == inner).all():
        return "whole-inner"
    if (diff & inner).sum() == 0 and (diff & outer).sum() == n:
        return "quad-ring"
    return "quad-other"


def score_run(capdir, goldens):
    gdir = os.path.join(goldens, SUITE)
    rows = []
    root = caps.resolve(capdir, "%s::*.png" % SUITE)
    for png in sorted(os.listdir(gdir)):
        if not png.endswith(".png"):
            continue
        test = png[:-4]
        p = caps.find(root, SUITE, test)
        if p is None:
            rows.append(dict(test=test, px=None, shape="MISSING"))
            continue
        a = np.array(Image.open(p).convert("RGBA"))
        g = np.array(Image.open(os.path.join(gdir, png)).convert("RGBA"))
        if a.shape != g.shape:
            rows.append(dict(test=test, px=None, shape="SHAPE-MISMATCH"))
            continue
        diff = np.any(a != g, axis=-1)
        n = int(diff.sum())
        if n:
            rows.append(dict(test=test, px=n, shape=classify(diff, a.shape)))
    return rows


def run_dirs(d):
    subs = sorted(glob.glob(os.path.join(d, "captures*")))
    return subs or [d]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--goldens", default=DEFAULT_GOLDENS)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--floor", action="store_true",
                    help="score every Stencil-disc run in the dispatch "
                         "results tree, to validate this tool against the "
                         "published flake before an arm is judged with it")
    args = ap.parse_args()

    targets = []
    if args.floor:
        res = os.environ.get("DISPATCH_RESULTS",
                             "/home/justin/hakux-work/dispatch/results")
        for d in sorted(os.listdir(res)):
            rj = os.path.join(res, d, "result.json")
            if not os.path.exists(rj):
                continue
            try:
                j = json.load(open(rj))
            except Exception:
                continue
            if str(j.get("disc_id", "")) != SUITE:
                continue
            for cd in run_dirs(os.path.join(res, d)):
                if glob.glob(os.path.join(cd, "%s::*.png" % SUITE)):
                    targets.append(cd)
    for d in args.dirs:
        targets.extend(run_dirs(d))

    if not targets:
        print("no capture directories found", file=sys.stderr)
        return 2

    out = []
    total_obs = total_wrong = 0
    for cd in targets:
        rows = score_run(cd, args.goldens)
        gdir = os.path.join(args.goldens, SUITE)
        n_gold = len([p for p in os.listdir(gdir) if p.endswith(".png")])
        total_obs += n_gold
        total_wrong += len(rows)
        out.append(dict(dir=cd, wrong=len(rows), of=n_gold, rows=rows))

    if args.json:
        print(json.dumps(dict(runs=out, observations=total_obs,
                              wrong=total_wrong), indent=2))
        return 0

    for r in out:
        label = "/".join(r["dir"].rstrip("/").split("/")[-2:])
        print("%-58s wrong %2d of %d" % (label, r["wrong"], r["of"]))
        for row in r["rows"]:
            print("    %-28s %-14s %s"
                  % (row["test"], row["shape"], row["px"]))
    print()
    print("TOTAL: %d wrong of %d (run, capture) observations over %d runs"
          % (total_wrong, total_obs, len(out)))
    print("       %d of %d runs carry at least one wrong capture"
          % (sum(1 for r in out if r["wrong"]), len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
