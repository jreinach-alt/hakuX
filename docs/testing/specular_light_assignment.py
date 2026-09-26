#!/usr/bin/env python3
"""#53: read silicon's per-vertex light association off the goldens, mapping-free.

`Specular`/`Specular_back`'s `ControlFlags*` tests draw 16 screen-space quads
over a 0x00/0x20 checkerboard at material alpha 0.75, in four rows of four.
Rows 1 and 3 put the DIFFUSE channel on screen, so they carry the light loop's
diffuse term; those are the eight "lit quads".  Rows 0 and 2 put SPECULAR on
screen.

Two facts make the light term recoverable exactly, with no model of the blend
and no model of the lighting arithmetic:

* `ControlFlagsNoLight_*` is the same scene with `LIGHT_ENABLE_MASK = 0`, so
  its quads hold the constant term alone -- measured here as a flat source
  grey of 8 (`kSceneAmbientColor` = 0.031373) over the two checkerboard tones.
  Subtracting it from `ControlFlags_*` cancels the checkerboard *and* the
  constant term, whatever they are.
* The destination weight is exactly 0.25 and the source weight exactly 0.75:
  the no-light quad reads 6 over background 0 and 14 over background 32, which
  pins both from a source of 8.  (Note that it is NOT the framebuffer alpha,
  which reads 207.)

So `light = (lit - unlit) / 0.75` per channel, to within one byte of
quantisation, and a quad's field is piecewise linear on the two triangles the
quad is split into.  Fitting a plane per triangle recovers the four per-vertex
values without fitting a total and without assuming which vertex feeds which
corner -- which is the question.

What this reports, and why each line is the measurement rather than a model:

1. **Which diagonal the quad is split on.**  Least squares over both
   candidates; the winner is the one whose residual sits at the quantisation
   floor.
2. **The level set.**  Every fitted corner value is snapped to the nearest
   member of the two-element set the fixed-function capture produces.  The
   residual of that snap is the check: if silicon's programmable path used a
   different arithmetic, the levels would not coincide with the
   fixed-function ones.
3. **The assignment**, as a four-character code over the corners in submission
   order (UL, UR, LR, LL), and whether it is a permutation of the four values
   the four submitted normals can supply -- per quad and per triangle.

Run with no arguments to read the goldens only.  Pass result directories to
have our own captures decomposed the same way, which says which assignment
our shader currently emits.

    python3 docs/testing/specular_light_assignment.py [RESULTDIR ...]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures as captures_mod

GOLDENS = os.environ.get("HAKUX_GOLDENS", "/home/justin/goldens/results")

# Geometry, straight out of specular_tests.cpp TestControlFlags().
FB_W, FB_H = 640.0, 480.0
QW, QH = FB_W / 6.0, FB_H / 6.0
SPACING = 15.0
LEFTS = [QW + j * (QW + SPACING) for j in range(4)]
TOPS = [QH + SPACING + i * (QH + SPACING) for i in range(4)]
LIT_ROWS = (1, 3)          # the rows whose combiner puts DIFFUSE on screen
DST_WEIGHT = 0.25          # measured, see module docstring
SRC_WEIGHT = 1.0 - DST_WEIGHT

# SET_LIGHT_CONTROL per column, for the report.
COLUMN_STATE = ["SEP_SPEC|ALPHA_FROM_MAT", "SEP_SPEC", "ALPHA_FROM_MAT", "0"]

CORNERS = ("UL", "UR", "LR", "LL")


def _load(path):
    from PIL import Image
    return np.array(Image.open(path)).astype(float)


def golden(suite, test):
    return _load(os.path.join(GOLDENS, suite, test + ".png"))


def light_field(lit, unlit):
    """The light loop's contribution, checkerboard and constant term removed."""
    return (lit - unlit) / SRC_WEIGHT


def quad_pixels(i, j):
    """Interior pixel indices of quad (row i, column j), inset to avoid edges."""
    x0, y0 = LEFTS[j], TOPS[i]
    left = int(np.ceil(x0)) + 2
    right = int(np.floor(x0 + QW)) - 3
    top = int(np.ceil(y0)) + 2
    bot = int(np.floor(y0 + QH)) - 3
    ys, xs = np.mgrid[top:bot + 1, left:right + 1]
    u = (xs + 0.5 - x0) / QW
    w = (ys + 0.5 - y0) / QH
    return ys, xs, u, w


def fit_quad(field, i, j, ch, diag):
    """Plane-fit each triangle of the quad; return corner values per triangle.

    `diag` is 'ULLR' for the (UL,UR,LR)+(UL,LR,LL) split and 'URLL' for
    (UL,UR,LL)+(UR,LR,LL).  Corner values come from the triangle that owns
    them; the two triangles are reported separately at the shared pair so a
    discontinuity along the diagonal would be visible rather than averaged
    away.
    """
    ys, xs, u, w = quad_pixels(i, j)
    v = field[ys, xs, ch].ravel()
    u, w = u.ravel(), w.ravel()
    mask = (w < u) if diag == "ULLR" else ((u + w) < 1.0)
    planes, worst = {}, 0.0
    for name, m in (("T1", mask), ("T2", ~mask)):
        A = np.stack([np.ones(int(m.sum())), u[m], w[m]], 1)
        c, _, _, _ = np.linalg.lstsq(A, v[m], rcond=None)
        worst = max(worst, float(np.abs(v[m] - A @ c).max()))
        planes[name] = c

    def at(c, uu, ww):
        return float(c[0] + c[1] * uu + c[2] * ww)

    uv = {"UL": (0.0, 0.0), "UR": (1.0, 0.0), "LR": (1.0, 1.0), "LL": (0.0, 1.0)}
    if diag == "ULLR":
        owner = {"UL": ("T1", "T2"), "UR": ("T1",), "LR": ("T1", "T2"), "LL": ("T2",)}
    else:
        owner = {"UL": ("T1",), "UR": ("T1", "T2"), "LR": ("T2",), "LL": ("T1", "T2")}
    per_tri = {}
    for corner, tris in owner.items():
        for t in tris:
            per_tri[(t, corner)] = at(planes[t], *uv[corner])
    return per_tri, owner, worst


def levels_from(values, tol=1.5):
    """Collapse a list of values into the distinct levels they occupy."""
    out = []
    for v in sorted(values):
        if not out or abs(v - out[-1][-1]) > tol:
            out.append([v])
        else:
            out[-1].append(v)
    return [float(np.mean(g)) for g in out]


def snap(v, levels):
    return int(np.argmin([abs(v - l) for l in levels]))


def analyse(suite, path, field, levels=None, label=""):
    """Report the assignment for the eight lit quads of one capture pair."""
    rows = []
    # Decide the diagonal on the pooled residual, not per quad.
    resid = {}
    for diag in ("ULLR", "URLL"):
        worst = 0.0
        for i in LIT_ROWS:
            for j in range(4):
                _, _, w = fit_quad(field, i, j, 0, diag)
                worst = max(worst, w)
        resid[diag] = worst
    diag = min(resid, key=resid.get)

    fits = {}
    allvals = []
    for i in LIT_ROWS:
        for j in range(4):
            per_tri, owner, worst = fit_quad(field, i, j, 0, diag)
            fits[(i, j)] = (per_tri, owner, worst)
            allvals.extend(per_tri.values())
    if levels is None:
        levels = levels_from(allvals)

    print("  %s%s  split=%s (worst residual %.2f, other diagonal %.2f)"
          % (suite, label, diag, resid[diag], resid[max(resid, key=resid.get)]))
    print("     levels in red: %s" % ", ".join("%.2f" % l for l in levels))
    snap_err = max(abs(v - levels[snap(v, levels)]) for v in allvals)
    print("     worst distance from a level: %.2f" % snap_err)
    for i in LIT_ROWS:
        for j in range(4):
            per_tri, owner, worst = fits[(i, j)]
            code = ""
            disc = 0.0
            for c in CORNERS:
                vals = [per_tri[(t, c)] for t in owner[c]]
                if len(vals) == 2:
                    disc = max(disc, abs(vals[0] - vals[1]))
                code += "LH"[snap(float(np.mean(vals)), levels)] if len(levels) == 2 else "?"
            rows.append((i, j, code, disc, worst))
            print("     q%d%d  %-24s %s   diag discontinuity %.2f  fit %.2f"
                  % (i, j, COLUMN_STATE[j], code, disc, worst))
    return levels, rows


def permutation_check(rows, correct):
    """A count-only test: can this assignment come from reordering the vertices?"""
    want = sorted(correct)
    print("     correct (fixed-function) assignment: %s" % correct)
    bad = []
    for i, j, code, _, _ in rows:
        if sorted(code) != want:
            bad.append("q%d%d=%s" % (i, j, code))
    if bad:
        print("     NOT a permutation of the vertex stream on %d of %d quads: %s"
              % (len(bad), len(rows), " ".join(bad)))
    else:
        print("     every quad is a permutation of the vertex stream")
    return bad



def synth_quad(i, j, vals):
    """Gouraud a candidate corner assignment over the measured UL-LR split.

    `vals` is (UL, UR, LR, LL).  Triangle 1 is (UL, UR, LR) and covers w < u;
    triangle 2 is (UL, LR, LL) and covers the rest.  Returns the pixel box and
    the field, so a candidate can be scored against the golden without any
    free parameter.
    """
    x0, y0 = LEFTS[j], TOPS[i]
    left, right = int(np.ceil(x0)), int(np.floor(x0 + QW)) - 1
    top, bot = int(np.ceil(y0)), int(np.floor(y0 + QH)) - 1
    ys, xs = np.mgrid[top:bot + 1, left:right + 1]
    u = (xs + 0.5 - x0) / QW
    w = (ys + 0.5 - y0) / QH
    UL, UR, LR, LL = vals
    out = np.empty(u.shape)
    m = w < u
    out[m] = UL + (u[m] - w[m]) * (UR - UL) + w[m] * (LR - UL)
    n = ~m
    out[n] = UL + u[n] * (LR - UL) + (w[n] - u[n]) * (LL - UL)
    return (top, bot, left, right), out


def score_uniform_candidates(suite, field, levels, correct, ch=0):
    """Every one of the sixteen uniform assignments, scored on the goldens.

    This is the "rivals excluded" half.  A uniform assignment is the only kind
    a shader can emit without a rule, so if one of them reproduced the golden
    the association would not be an open question.  Scored in bytes beyond
    quantisation, which is why the threshold is 1 and not 0: a difference of
    one byte is what rounding two independently-quantised ramps produces.
    """
    # One byte is what rounding two independently-quantised ramps gives; the
    # back suite's ramp is three times steeper, so half a byte of origin error
    # lands just above that. 1.5 keeps the criterion the same for both suites.
    TOL = 1.5
    rows = []
    for cand in ("%s%s%s%s" % (a, b, c, d)
                 for a in "LH" for b in "LH" for c in "LH" for d in "LH"):
        vals = tuple(levels[1] if k == "H" else levels[0] for k in cand)
        total, matched = 0, 0
        for i in LIT_ROWS:
            for j in range(4):
                (t, b, l, r), pred = synth_quad(i, j, vals)
                d = np.abs(pred - field[t:b + 1, l:r + 1, ch]) * SRC_WEIGHT
                total += int((d > TOL).sum())
                if d.max() <= TOL:
                    matched += 1
        rows.append((total, -matched, cand))
    rows.sort()
    print("     uniform candidates, red channel, px beyond quantisation:")
    for total, neg, cand in rows[:4]:
        tag = "   <== fixed function" if cand == correct else ""
        print("       %s  %7d px   quads reproduced exactly: %d%s"
              % (cand, total, -neg, tag))
    me = [r for r in rows if r[2] == correct][0]
    print("       fixed function %s: rank %d of 16, %d px, %d of 8 quads exact"
          % (correct, rows.index(me) + 1, me[0], -me[1]))
    return rows


def main():
    for suite in ("Specular", "Specular_back"):
        print("=== %s" % suite)
        ff = light_field(golden(suite, "ControlFlags_FF"),
                         golden(suite, "ControlFlagsNoLight_FF"))
        vs = light_field(golden(suite, "ControlFlags_VS"),
                         golden(suite, "ControlFlagsNoLight_VS"))
        levels, ff_rows = analyse(suite, None, ff, label=" golden FF")
        ff_codes = set(c for _, _, c, _, _ in ff_rows)
        if len(ff_codes) == 1:
            correct = ff_rows[0][2]
            print("     fixed function is UNIFORM across all eight lit quads: %s" % correct)
        else:
            correct = None
            print("     fixed function is NOT uniform: %s" % sorted(ff_codes))
        _, vs_rows = analyse(suite, None, vs, levels=levels, label=" golden VS")
        if correct:
            permutation_check(vs_rows, correct)
            score_uniform_candidates(suite, vs, levels, correct)
        print()

    for d in sys.argv[1:]:
        root = captures_mod.resolve(d, "*.png")
        print("=== ours, %s" % root)
        for suite in ("Specular", "Specular_back"):
            lit = captures_mod.find(d, suite, "ControlFlags_VS")
            unlit = captures_mod.find(d, suite, "ControlFlagsNoLight_VS")
            ff_l = captures_mod.find(d, suite, "ControlFlags_FF")
            ff_u = captures_mod.find(d, suite, "ControlFlagsNoLight_FF")
            if not (lit and unlit):
                print("  %s: captures MISSING" % suite)
                continue
            gff = light_field(golden(suite, "ControlFlags_FF"),
                              golden(suite, "ControlFlagsNoLight_FF"))
            levels, _ = analyse(suite, None, gff, label=" golden FF (levels)")
            analyse(suite, None, light_field(_load(lit), _load(unlit)),
                    levels=levels, label=" ours VS")
            if ff_l and ff_u:
                analyse(suite, None, light_field(_load(ff_l), _load(ff_u)),
                        levels=levels, label=" ours FF")
            print()


if __name__ == "__main__":
    main()
