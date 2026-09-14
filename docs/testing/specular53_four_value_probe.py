#!/usr/bin/env python3
"""#53: can anything in the corpus name the SOURCE VERTEX of a duplicated light term?

#53's blocker:

    the corpus supplies only two distinct N.L values per lit quad, so no 3-1
    code can name its source vertex; the three settling observations all need
    captures we cannot produce

That is two claims and this tool measures both, offline from the goldens.

PART A -- the premise.  How many distinct levels does the light term actually
take over a lit quad?  Measured model-free: the light field is
(ControlFlags - ControlFlagsNoLight)/0.75, which cancels the checkerboard and
the constant term whatever they are, and each quad's field is plane-fitted per
triangle to recover four per-vertex values without assuming which vertex feeds
which corner.  If that count is 2, a 3-1 code is ambiguous and the number of
source maps consistent with it is reported.  If it is ever 3 or 4, the blocker
is false.

PART B -- the escape route the premise does not cover.  The blocker is about the
LIGHT term.  The same draw also carries per-vertex DIFFUSE colour, whose four
components are DISTINCT by construction (0.25/0.50/0.75/1.00), and
`ControlFlagsLightDisable_*` renders it with the lighting unit switched OFF.
So there IS a four-valued probe of the vertex->corner association in the corpus.
If it reads PERMUTED, the association is readable from four distinct values and
the blocker is false.  If it reads IDENTITY, the anomaly is confined to the
lighting unit, where only two values exist, and the blocker stands with a
non-empty control behind it.

`specular_light_assignment.py` plane-fits channel 0 of the light field only.
This one also fits the lighting-disabled capture, modelling the checkerboard the
quads are blended over rather than subtracting a partner capture.

Usage:  python3 docs/testing/specular53_four_value_probe.py
"""
import os
import sys
from itertools import product

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GOLDENS = os.environ.get("HAKUX_GOLDENS", "/home/justin/goldens/results")

# Geometry, straight out of specular_tests.cpp TestControlFlags().
FB_W, FB_H = 640.0, 480.0
QW, QH = FB_W / 6.0, FB_H / 6.0
SPACING = 15.0
LEFTS = [QW + j * (QW + SPACING) for j in range(4)]
TOPS = [QH + SPACING + i * (QH + SPACING) for i in range(4)]
CORNERS = ("UL", "UR", "LR", "LL")
CHANNELS = ("R", "G", "B", "A")
CELL = 14                      # DrawCheckerboardUnproject(..., 14)
LIT_ROWS = (1, 3)              # the rows whose combiner puts DIFFUSE on screen
SRC_WEIGHT = 0.75              # measured; see specular-light-association.md

# Per-vertex DIFFUSE colour submitted by TestControlFlags(), submission order
# UL, UR, LR, LL.  Front puts it in BLUE (kDiffuseUL{0,0,0.5} ..), back in RED
# (kDiffuseUL{0.5,0,0} ..).  Four DISTINCT values either way.
VERTEX_DIFFUSE = {
    "Specular":      (2, [0.50, 0.75, 1.00, 0.25]),
    "Specular_back": (0, [0.50, 0.75, 1.00, 0.25]),
}


def load(suite, test):
    from PIL import Image
    return np.array(Image.open(os.path.join(GOLDENS, suite, test + ".png"))).astype(float)


def quad_pixels(i, j):
    x0, y0 = LEFTS[j], TOPS[i]
    left = int(np.ceil(x0)) + 2
    right = int(np.floor(x0 + QW)) - 3
    top = int(np.ceil(y0)) + 2
    bot = int(np.floor(y0 + QH)) - 3
    ys, xs = np.mgrid[top:bot + 1, left:right + 1]
    u = (xs + 0.5 - x0) / QW
    w = (ys + 0.5 - y0) / QH
    return ys, xs, u, w


def fit_corners(img, i, j, ch, phase=None):
    """Plane-fit both triangles of the ULLR split; return corner values + worst residual.

    With `phase`, a checkerboard-parity indicator is added to the design matrix so
    the blended-through destination step is absorbed rather than left in the
    residual.  Without it the field is assumed already checkerboard-free.
    """
    ys, xs, u, w = quad_pixels(i, j)
    v = img[ys, xs, ch].ravel().astype(float)
    u, w = u.ravel(), w.ravel()
    cols = [np.ones_like(u), u, w]
    if phase is not None:
        ox, oy = phase
        cols.append((((xs - ox) // CELL + (ys - oy) // CELL) % 2).ravel().astype(float))
    mask = w < u                      # T1 = (UL,UR,LR), T2 = (UL,LR,LL)
    planes, worst = {}, 0.0
    for name, m in (("T1", mask), ("T2", ~mask)):
        if m.sum() < 16:
            return None, None
        A = np.stack([c[m] for c in cols], 1)
        c, _, _, _ = np.linalg.lstsq(A, v[m], rcond=None)
        worst = max(worst, float(np.abs(v[m] - A @ c).max()))
        planes[name] = c

    def at(c, uu, ww):
        return float(c[0] + c[1] * uu + c[2] * ww)

    uv = {"UL": (0.0, 0.0), "UR": (1.0, 0.0), "LR": (1.0, 1.0), "LL": (0.0, 1.0)}
    out = {}
    for corner in CORNERS:
        tri = "T2" if corner == "LL" else "T1"
        out[corner] = at(planes[tri], *uv[corner])
    return out, worst


def find_phase(img):
    best, best_ph = None, (0, 0)
    for ox in range(CELL):
        for oy in range(CELL):
            tot = 0.0
            for (i, j) in ((0, 0), (1, 1), (2, 2), (3, 3)):
                r = fit_corners(img, i, j, 0, (ox, oy))
                if r[0] is not None:
                    tot += r[1]
            if best is None or tot < best:
                best, best_ph = tot, (ox, oy)
    return best_ph, best


def levels_of(vals, tol):
    out = []
    for v in sorted(vals):
        if not out or abs(v - out[-1]) > tol:
            out.append(v)
        else:
            out[-1] = (out[-1] + v) / 2.0
    return out


def part_a(suite, tol):
    """How many distinct levels does the LIGHT term take, per lit quad and pooled?"""
    lit = load(suite, "ControlFlags_VS")
    unlit = load(suite, "ControlFlagsNoLight_VS")
    field = (lit - unlit) / SRC_WEIGHT
    print("-" * 78)
    print("PART A  %s :: light field = (ControlFlags_VS - ControlFlagsNoLight_VS)/0.75" % suite)
    print("  quad    UL      UR      LR      LL    levels-in-quad   worst-resid")
    allvals, per_quad = [], []
    for i in LIT_ROWS:
        for j in range(4):
            corners, worst = fit_corners(field, i, j, 0)
            vals = [corners[c] for c in CORNERS]
            lv = levels_of(vals, tol)
            allvals.extend(vals)
            per_quad.append(len(lv))
            print("  q%d%d  %7.2f %7.2f %7.2f %7.2f          %d            %5.2f"
                  % (i, j, vals[0], vals[1], vals[2], vals[3], len(lv), worst))
    pooled = levels_of(allvals, tol)
    print("  pooled over all %d corner values of the 8 lit quads: %d distinct levels %s"
          % (len(allvals), len(pooled), ["%.2f" % x for x in pooled]))
    print("  max levels within any single quad: %d" % max(per_quad))
    return len(pooled), max(per_quad), allvals


def ambiguity(n_levels):
    """With `n_levels` distinct source values over 4 vertices (2 of each when
    n_levels==2), how many vertex->corner source maps produce an identical image?"""
    if n_levels != 2:
        return None
    # vertices supply values [A,B,B,A] in submission order (front) -- two of each.
    src = ["A", "B", "B", "A"]
    counts = {}
    for m in product(range(4), repeat=4):
        code = tuple(src[k] for k in m)
        counts.setdefault(code, []).append(m)
    sizes = sorted({len(v) for v in counts.values()})
    return counts, sizes


def part_b(suite, tol):
    """Does a FOUR-distinct-valued per-vertex quantity name the source vertex?"""
    ch, expect = VERTEX_DIFFUSE[suite]
    print("-" * 78)
    print("PART B  %s :: ControlFlagsLightDisable_VS, channel %s (per-vertex DIFFUSE)"
          % (suite, CHANNELS[ch]))
    exp = [v * 255.0 for v in expect]
    print("  submitted UL,UR,LR,LL = %s  (four DISTINCT values -- the class is non-empty)"
          % ["%.1f" % e for e in exp])
    img = load(suite, "ControlFlagsLightDisable_VS")
    phase, _ = find_phase(img)
    ok, tot = 0, 0
    print("  quad    UL      UR      LR      LL    max|err| vs submission order  resid")
    for i in LIT_ROWS:
        for j in range(4):
            corners, worst = fit_corners(img, i, j, ch, phase)
            vals = [corners[c] for c in CORNERS]
            err = max(abs(v - e) for v, e in zip(vals, exp))
            tot += 1
            if err <= tol:
                ok += 1
            print("  q%d%d  %7.2f %7.2f %7.2f %7.2f            %6.2f            %5.2f"
                  % (i, j, vals[0], vals[1], vals[2], vals[3], err, worst))
    print("  quads matching SUBMISSION ORDER within %.1f byte: %d of %d" % (tol, ok, tot))
    return ok, tot


def part_c(tol):
    """Is the four-valued probe still READABLE once the lighting unit is on?

    Part B reads the four submitted diffuse values in
    `ControlFlagsLightDisable_*`, where LIGHTING_ENABLE is 0.  The anomaly only
    exists when LIGHTING_ENABLE is 1.  So the question that decides whether the
    probe can settle anything is whether those four values survive into the
    lighting-enabled captures at all.

    Searched over every channel of every lit quad: does any channel reproduce the
    submitted 0.50/0.75/1.00/0.25 set, in any order?  If none does, the lighting
    unit has REPLACED the per-vertex diffuse with its own output, and the
    four-valued probe and the anomaly are mutually exclusive in this corpus.
    """
    print("-" * 78)
    print("PART C  is the four-valued probe readable while LIGHTING_ENABLE = 1?")
    hits = 0
    for suite in ("Specular", "Specular_back"):
        _, expect = VERTEX_DIFFUSE[suite]
        exp = sorted(v * 255.0 for v in expect)
        for test in ("ControlFlagsNoLight_VS", "ControlFlags_VS"):
            img = load(suite, test)
            phase, _ = find_phase(img)
            best = None
            for i in LIT_ROWS:
                for j in range(4):
                    for ch in range(4):
                        corners, worst = fit_corners(img, i, j, ch, phase)
                        if corners is None:
                            continue
                        got = sorted(corners[c] for c in CORNERS)
                        err = max(abs(g - e) for g, e in zip(got, exp))
                        if best is None or err < best[0]:
                            best = (err, i, j, CHANNELS[ch], got)
                        if err <= tol:
                            hits += 1
            print("  %-14s %-24s closest channel to the submitted set: "
                  "q%d%d %s err %.1f  %s"
                  % (suite, test, best[1], best[2], best[3], best[0],
                     ["%.0f" % g for g in best[4]]))
    print("  channels anywhere in the lit rows carrying the four submitted"
          " diffuse values: %d" % hits)
    return hits


def part_d():
    """Within-capture replicate: the corpus's only determinism evidence.

    Settling observation 1 on #53 asks for `ControlFlags_VS` run TWICE on
    silicon, to decide whether the association is deterministic at all.  No
    second silicon capture exists (the goldens repo carries one commit).  What
    the corpus does carry is a within-capture repeat: q10/q13 and q30/q33 are
    separate draws of identical geometry differing only in SET_LIGHT_CONTROL and
    in x position, and SET_LIGHT_CONTROL does not enter the diffuse light term.
    If the association were resolved per draw, these would disagree.

    This is weaker than observation 1 -- it cannot see a per-RUN resolution that
    is stable within a frame -- and is reported as such.
    """
    print("-" * 78)
    print("PART D  within-capture replicate (NOT a run-to-run replicate)")
    for suite in ("Specular", "Specular_back"):
        lit = load(suite, "ControlFlags_VS")
        unlit = load(suite, "ControlFlagsNoLight_VS")
        field = (lit - unlit) / SRC_WEIGHT
        for a, b in (((1, 0), (1, 3)), ((3, 0), (3, 3))):
            va = [fit_corners(field, a[0], a[1], 0)[0][c] for c in CORNERS]
            vb = [fit_corners(field, b[0], b[1], 0)[0][c] for c in CORNERS]
            d = max(abs(x - y) for x, y in zip(va, vb))
            print("  %-14s q%d%d vs q%d%d   max|difference| over the four corners: %.4f L-units"
                  % (suite, a[0], a[1], b[0], b[1], d))


def main():
    tol = float(os.environ.get("TOL", "3.0"))
    print("tolerance = %.2f byte units" % tol)
    summary = {}
    for suite in ("Specular", "Specular_back"):
        pooled, per_quad_max, _ = part_a(suite, tol)
        ok, tot = part_b(suite, tol)
        summary[suite] = (pooled, per_quad_max, ok, tot)
    part_c(tol)
    part_d()
    counts, sizes = ambiguity(2)
    print("=" * 78)
    print("SUMMARY")
    for s, (p, q, ok, tot) in summary.items():
        print("  %-14s light-term levels: pooled %d, max-in-quad %d |"
              " vertex-diffuse in submission order: %d/%d" % (s, p, q, ok, tot))
    print()
    print("  AMBIGUITY with two distinct source values over four vertices [A,B,B,A]:")
    print("    %d source maps over 4 corners; they produce only %d distinct images,"
          % (4 ** 4, len(counts)))
    print("    and every observed image is produced by %s different source maps."
          % " or ".join(str(s) for s in sizes))


if __name__ == "__main__":
    main()
