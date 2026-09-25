#!/usr/bin/env python3
"""Census of nearest-sample tie breaks on DrawCheckerboardUnproject (#282).

The helper maps a 256x256 texture over the full 640x480 framebuffer with
normalised coordinates 0..1. NV2A samples at integer pixel coordinates, so
u = 0.4 * x and v = 256/480 * y: every column x = 5k sits exactly on texel
boundary u = 2k, and every row y = 15k exactly on v = 8k. A tie line only
shows when it is also a checker cell edge.

For each tie line, over the pixels where the two neighbours are two different
checker tones (a cell edge crosses the line there, and nothing is drawn over
it) we ask which neighbour the line copies: the one below/left (the lower
texel -- "down") or the one above/right (the upper texel -- "up"). That is
read from the golden and from our capture separately, per pixel, so a rule is
scored as the fraction of edge pixels whose direction it predicts -- regions,
not points.

Usage: tie_rule.py CAPDIR [CAPDIR ...] [--suites A,B] [--tsv OUT]
"""
import argparse
import collections
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "testing"))
import captures  # noqa: E402

GOLD = "/home/justin/goldens/results"

# The checker tones each suite passes to DrawCheckerboardUnproject (all grey),
# from nxdk_pgraph_tests src/tests/*.cpp. Only an edge between two of these
# is the checkerboard's own edge; anything else is geometry drawn over it.
TONES = {
    "Lighting_spotlight": (0x11, 0x00),
    "Lighting_control": (0x20, 0x00),
    "Lighting_accumulation": (0x20, 0x90),
    "Lighting_range": (0x20, 0x90),
    "Material_color_source": (0x20, 0x90),
    "Specular": (0x20, 0x00, 0x90),
    "Specular_back": (0x20, 0x00, 0x90),
    "Combiner": (0x33, 0x44),
    "Attrib_float": (0x33, 0x44),
    "Texture_border_color": (0x00, 0x44),
}


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)


def tone(px, tones):
    """Index of the checker tone px is (within 1 on every channel), else -1."""
    t = np.full(px.shape[0], -1)
    for k, v in enumerate(tones):
        t[np.abs(px - v).max(1) <= 1] = k
    return t


def lines(img, axis, tones):
    """Yield (texel, line, edge, down, up) masks for every tie line on one axis."""
    if axis == "v":
        img = img.transpose(1, 0, 2)  # img[:, y] is framebuffer row y
        step, texstep = 15, 8
    else:
        step, texstep = 5, 2  # img[:, x] is framebuffer column x
    for i in range(step, img.shape[1] - 1, step):
        a, m, b = img[:, i - 1], img[:, i], img[:, i + 1]
        ta, tb = tone(a, tones), tone(b, tones)
        edge = (ta >= 0) & (tb >= 0) & (ta != tb)
        down = edge & (np.abs(m - a).max(1) <= 2)
        up = edge & (np.abs(m - b).max(1) <= 2)
        yield i // step * texstep, i, edge, down & ~up, up & ~down


def census(g, c, tones):
    out = []
    for axis in ("u", "v"):
        for (tex, i, ge, gd, gu), (_, _, ce, cd, cu) in zip(lines(g, axis, tones), lines(c, axis, tones)):
            # score only pixels where both images show the checker edge and
            # both commit to one side of it
            ok = ge & ce & (gd | gu) & (cd | cu)
            if ok.sum() < 4:
                continue
            out.append((axis, tex, i, int(ok.sum()), int((gd & ok).sum()), int((gu & ok).sum()),
                        int((cd & ok).sum()), int((cu & ok).sum()), int((gd & cu & ok).sum()),
                        int((gu & cd & ok).sum())))
    return out


def iter_pairs(capdirs, want):
    seen = set()
    for d in capdirs:
        root = captures.resolve(d)
        for f in sorted(os.listdir(root)):
            if "::" not in f or not f.endswith(".png"):
                continue
            suite, test = f[:-4].split("::", 1)
            if suite not in TONES or (want and suite not in want) or (suite, test) in seen:
                continue
            gp = os.path.join(GOLD, suite, test + ".png")
            if not os.path.exists(gp):
                continue
            seen.add((suite, test))
            g, c = load(gp), load(os.path.join(root, f))
            if g.shape != c.shape or g.shape[:2] != (480, 640):
                continue
            yield suite, test, g, c


# Candidate rules: (vs, axis, texel, line, x) -> True when the tie goes DOWN
# (to the lower texel). "line" is the framebuffer row for v and column for u;
# "x" is the position along the line (the column for a v tie); "vs" is true
# when a vertex program is bound while the checkerboard is drawn (the tests
# named *VS*: Lighting_control's SetupVertexShader runs before the draw).
RULES = {
    # What we render today: GL nearest, floor(t) at an exact tie = up.
    "current(up)": lambda vs, ax, tex, y, x: False,
    # #9's note: down below texel 128, up from 144.
    "#9 index(v<=128)": lambda vs, ax, tex, y, x: ax == "v" and tex <= 128,
    # The quad is drawn as two triangles split on (0,0)-(640,480); down only
    # inside the v0-v1-v2 (upper-right) triangle.
    "diag(x>=4y/3,v<=128)": lambda vs, ax, tex, y, x: ax == "v" and tex <= 128 and 3 * x >= 4 * y,
    # ...and only on the fixed-function path.
    "diag+FF": lambda vs, ax, tex, y, x: not vs and ax == "v" and tex <= 128 and 3 * x >= 4 * y,
}


def score(capdirs, want):
    """Per suite and rule: pixels whose golden direction the rule predicts."""
    tot = collections.defaultdict(lambda: collections.Counter())
    for suite, test, g, c in iter_pairs(capdirs, want):
        for axis in ("u", "v"):
            for tex, i, ge, gd, gu in lines(g, axis, TONES[suite]):
                ok = ge & (gd | gu)
                xs = np.nonzero(ok)[0]
                for name, rule in RULES.items():
                    pred = np.array([rule("VS" in test, axis, tex, i, x) for x in xs], bool)
                    hit = int((pred == gd[xs]).sum())
                    tot[suite][name] += hit
                    tot["ALL"][name] += hit
                    if axis == "v" and tex <= 128:
                        tot[suite + " v<=128"][name] += hit
                        tot["ALL v<=128"][name] += hit
                tot[suite]["n"] += len(xs)
                tot["ALL"]["n"] += len(xs)
                if axis == "v" and tex <= 128:
                    tot[suite + " v<=128"]["n"] += len(xs)
                    tot["ALL v<=128"]["n"] += len(xs)
    names = list(RULES)
    print("%-36s %8s " % ("suite", "n") + " ".join("%22s" % n for n in names))
    for s in sorted(tot):
        n = tot[s]["n"]
        print("%-36s %8d " % (s, n) + " ".join("%22s" % ("%d %.1f%%" % (tot[s][k], 100.0 * tot[s][k] / max(n, 1)))
                                                for k in names))


def sign_map(capdirs, want):
    """Pool the goldens' v-tie votes per (row, column) over the FF draws and
    print each tie row as runs of D (lower texel) and U (upper texel)."""
    D = np.zeros((32, 640), int)
    U = np.zeros((32, 640), int)
    for suite, test, g, c in iter_pairs(capdirs, want):
        if "VS" in test:
            continue
        for tex, i, e, d, u in lines(g, "v", TONES[suite]):
            D[tex // 8] += d
            U[tex // 8] += u
    both = int(((D > 0) & (U > 0)).sum())
    print("pixels with votes both ways: %d of %d" % (both, int(((D + U) > 0).sum())))
    for k in range(1, 31):
        s = np.where(D[k] > U[k], "D", np.where(U[k] > D[k], "U", "."))
        runs, start = [], 0
        for x in range(1, 641):
            if x == 640 or s[x] != s[start]:
                if s[start] != ".":
                    runs.append("%s%d-%d" % (s[start], start, x - 1))
                start = x
        print("v=%3d row %3d  %s" % (k * 8, k * 15, " ".join(runs)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capdirs", nargs="+")
    ap.add_argument("--suites", default="")
    ap.add_argument("--tsv")
    ap.add_argument("--score", action="store_true", help="score RULES against the goldens")
    ap.add_argument("--map", action="store_true", help="print the goldens' v-tie sign map")
    a = ap.parse_args()
    want = set(filter(None, a.suites.split(",")))
    if a.score:
        score(a.capdirs, want)
        return
    if a.map:
        sign_map(a.capdirs, want)
        return
    rows = []
    ncap = 0
    for suite, test, g, c in iter_pairs(a.capdirs, want):
        ncap += 1
        for r in census(g, c, TONES[suite]):
            rows.append((suite, test) + r)
    if a.tsv:
        with open(a.tsv, "w") as fh:
            fh.write("suite\ttest\taxis\ttexel\tline\tn\tg_down\tg_up\tc_down\tc_up\tgdown_cup\tgup_cdown\n")
            for r in rows:
                fh.write("\t".join(map(str, r)) + "\n")
    agg = collections.defaultdict(lambda: np.zeros(7, int))
    for r in rows:
        agg[(r[2], r[3])] += r[5:]
    print("axis texel line      n  g_down   g_up  c_down   c_up  gD/cU  gU/cD")
    for (ax, tex), v in sorted(agg.items()):
        line = tex * 15 // 8 if ax == "v" else tex * 5 // 2
        print("%-4s %5d %4d %6d %7d %6d %7d %6d %6d %6d" % ((ax, tex, line) + tuple(v)))
    print("captures:", ncap, "lines:", len(rows))


if __name__ == "__main__":
    main()
