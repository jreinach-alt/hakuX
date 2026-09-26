#!/usr/bin/env python3
"""Extract every scorable tie pixel's direction from the goldens (#282).

Uses cloud-282's tie_rule.py for the tones and the edge/tie reading, and
writes one row per tie pixel: suite, vs (vertex program bound), axis, texel,
line (framebuffer row for v, column for u), pos (position along the line),
down (1 if the golden copies the lower texel). plane_model.py scores against
this file.

Usage: extract.py OUT.npz CAPDIR [CAPDIR ...] [--gold DIR] [--suffix .png]
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloud-282"))
import tie_rule  # noqa: E402


def flat_pairs(capdirs, root):
    """tie_rule.iter_pairs over a console run: the same (suite, test) set as
    the capture dirs name, silicon read from ROOT/SUITE::TEST.png."""
    seen = set()
    for d in capdirs:
        cap = tie_rule.captures.resolve(d)
        for f in sorted(os.listdir(cap)):
            if "::" not in f or not f.endswith(".png"):
                continue
            suite, test = f[:-4].split("::", 1)
            if suite not in tie_rule.TONES or (suite, test) in seen:
                continue
            gp = os.path.join(root, f)
            if not os.path.exists(gp):
                continue
            seen.add((suite, test))
            g = tie_rule.load(gp)
            if g.shape[:2] != (480, 640):
                continue
            yield suite, test, g, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("capdirs", nargs="+")
    ap.add_argument("--gold", default=tie_rule.GOLD,
                    help="silicon image root laid out SUITE/TEST.png (goldens, or a console run)")
    ap.add_argument("--flat", action="store_true",
                    help="silicon root is laid out SUITE::TEST.png (a console run's out/run1)")
    a = ap.parse_args()
    tie_rule.GOLD = a.gold
    suites, cols = [], {k: [] for k in ("suite", "test", "vs", "axis", "tex", "line", "pos", "down")}
    tests = []
    pairs = tie_rule.iter_pairs(a.capdirs, set())
    if a.flat:
        pairs = flat_pairs(a.capdirs, a.gold)
    for suite, test, g, c in pairs:
        if suite not in suites:
            suites.append(suite)
        tests.append(suite + "/" + test)
        for axis in ("u", "v"):
            for tex, i, e, d, u in tie_rule.lines(g, axis, tie_rule.TONES[suite]):
                xs = np.nonzero(e & (d | u))[0]
                n = len(xs)
                cols["suite"].append(np.full(n, suites.index(suite), np.int8))
                cols["test"].append(np.full(n, len(tests) - 1, np.int16))
                cols["vs"].append(np.full(n, "VS" in test, bool))
                cols["axis"].append(np.full(n, axis == "v", bool))
                cols["tex"].append(np.full(n, tex, np.int16))
                cols["line"].append(np.full(n, i, np.int16))
                cols["pos"].append(xs.astype(np.int16))
                cols["down"].append(d[xs])
    np.savez_compressed(a.out, suites=np.array(suites), tests=np.array(tests),
                        **{k: np.concatenate(v) for k, v in cols.items()})
    print("tests:", len(tests), "tie px:", sum(len(v) for v in cols["pos"]))


if __name__ == "__main__":
    main()
