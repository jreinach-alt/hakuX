#!/usr/bin/env python3
"""#13's remaining wide-line residual: the CAP phase, derived from the goldens.

Offline.  No device, no build.  `line_extent_phase.py` settled the minor-axis
extent and its band phase exactly and left 495 px of whole-capture coverage
residual over the 48 non-void `Line_*` captures -- 493 of them OURS-ONLY and
98.8% within w/2 + 2 of a vertex.  That residual is the CAP, and this tool is
the measurement for it.

THE RULE, read off the goldens (see --anatomy) and then scored (--rivals):

    the footprint is additionally clipped, on the MINOR axis, to the slab
    between the two endpoints' minor coordinates each extended by w/2:

        minor in ( min(m0, m1) - w/2 ,  max(m0, m1) + w/2 ]

    with m0, m1 the endpoints' minor coordinates on the same 1/16 grid the
    extent rule uses, w the line width (NOT the widened extent E), and the
    same LOW-OPEN tie-break the extent rule already selected.

It only ever bites at a corner: inside the segment the perpendicular slab and
the E-band are both tighter, so this clip removes the two tips of the
parallelogram that stick out past the endpoint's own w-tall span and changes
nothing else.  That is why it is invisible everywhere except within w/2 of a
vertex, which is exactly where the residual was.

  --anatomy     every residual pixel in edge coordinates, with the distance
                to each candidate boundary -- how the rule was read
  --rivals      candidate cap rules scored on whole-capture coverage
  --controls    what the instrument cannot see: how many pixels each rule can
                possibly touch, and the tie population that picks the phase
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import line_priority as lp
import line_extent_phase as lep


def geo(e):
    """Snapped endpoints and the derived per-edge geometry."""
    (ax, ay), (bx, by) = e[3][0], e[4][0]
    ax, ay = lep.snap(ax), lep.snap(ay)
    bx, by = lep.snap(bx), lep.snap(by)
    dx, dy = bx - ax, by - ay
    return ax, ay, bx, by, dx, dy


def edge_mask(e, w, cap="perp", clip=None, tie="low_open", pen=None,
              major_pen=False):
    """Pixels this edge lights.  `cap` is the along-axis rule, `clip` the
    minor-axis endpoint clip whose width is given in units of w/2."""
    H, Wd = lp.H, lp.W
    ax, ay, bx, by, dx, dy = geo(e)
    m = np.zeros((H, Wd), bool)
    if dx == 0 and dy == 0:
        return m
    mx, mn = max(abs(dx), abs(dy)), min(abs(dx), abs(dy))
    E = w * (mx + lep.BETA * mn) / mx
    L = float(np.hypot(dx, dy))
    ux, uy = dx / L, dy / L
    xmaj = abs(dx) >= abs(dy)
    n, lim = (Wd, H) if xmaj else (H, Wd)
    s = (dy / dx) if xmaj else (dx / dy)
    p0 = (ay - ax * s) if xmaj else (ax - ay * s)
    m0, m1 = (ay, by) if xmaj else (ax, bx)
    j0, j1 = (ax, bx) if xmaj else (ay, by)
    if clip is not None:
        clo, chi = min(m0, m1) - clip * w / 2, max(m0, m1) + clip * w / 2
    if pen is not None:
        plo = int(np.floor(min(m0, m1) - pen * w / 2 + lep.EPS))
        if tie == "floor1":                 # the measured rule
            phi = int(np.floor(max(m0, m1) + pen * w / 2 + lep.EPS)) + 1
        elif tie == "ceil":
            phi = int(np.ceil(max(m0, m1) + pen * w / 2 - lep.EPS))
        else:                               # symmetric floor
            phi = int(np.floor(max(m0, m1) + pen * w / 2 + lep.EPS))
        if major_pen:
            qlo = int(np.floor(min(j0, j1) - pen * w / 2 + lep.EPS))
            qhi = int(np.floor(max(j0, j1) + pen * w / 2 + lep.EPS)) + 1
    for k in range(n):
        M = k + 0.5
        if pen is not None and major_pen and not (qlo <= k <= qhi):
            continue
        c = p0 + s * M
        a = int(np.floor(c - E / 2 - 0.5 + lep.EPS)) + 1
        b = int(np.floor(c + E / 2 - 0.5 + lep.EPS))
        if pen is not None:
            a, b = max(a, plo), min(b, phi)
        if clip is not None:
            if tie == "low_open":
                a = max(a, int(np.floor(clo - 0.5 + lep.EPS)) + 1)
                b = min(b, int(np.floor(chi - 0.5 + lep.EPS)))
            else:                                    # closed
                a = max(a, int(np.ceil(clo - 0.5 - lep.EPS)))
                b = min(b, int(np.floor(chi - 0.5 + lep.EPS)))
        a, b = max(a, 0), min(b, lim - 1)
        if b < a:
            continue
        idx = np.arange(a, b + 1)
        if cap in ("perp", "perp_major"):
            al = ((M - ax) * ux + (idx + 0.5 - ay) * uy if xmaj
                  else (idx + 0.5 - ax) * ux + (M - ay) * uy)
            idx = idx[(al >= 0) & (al <= L)]
        if cap in ("major", "perp_major"):
            j0, j1 = (min(ax, bx), max(ax, bx)) if xmaj else (min(ay, by),
                                                              max(ay, by))
            if not (j0 <= M <= j1):
                idx = idx[:0]
        if len(idx) == 0:
            continue
        if xmaj:
            m[idx, k] = True
        else:
            m[k, idx] = True
    return m


def union(w, **kw):
    u = np.zeros((lp.H, lp.W), bool)
    for e in lp.EDGES:
        u |= edge_mask(e, w, **kw)
    return u


def score(golden_dir, lo, hi, variants, verbose=False):
    """Whole-capture coverage mismatch for each named cap variant."""
    tot = {k: 0 for k in variants}
    exact = {k: 0 for k in variants}
    n_ink = n_cap = 0
    for test, w, g in lp.captures(golden_dir, lo, hi):
        if test in lep.VOID:
            continue
        lit, valid = lep.ink(g)
        n_ink += int((lit & valid).sum())
        n_cap += 1
        row = []
        for name, kw in variants.items():
            u = union(w, **kw)
            d = int(((u ^ lit) & valid).sum())
            tot[name] += d
            exact[name] += (d == 0)
            row.append(d)
        if verbose:
            print(f"{test:<14}{w:>8.3f}{int((lit & valid).sum()):>10}"
                  + "".join(f"{v:>10}" for v in row))
    return tot, exact, n_ink, n_cap


def anatomy(golden_dir, lo, hi, kw=None):
    """Every residual pixel of a cap rule, in edge terms."""
    kw = kw or dict(cap="perp")
    for test, w, g in lp.captures(golden_dir, lo, hi):
        if test in lep.VOID:
            continue
        lit, valid = lep.ink(g)
        masks = [edge_mask(e, w, **kw) for e in lp.EDGES]
        u = np.zeros_like(lit)
        for m in masks:
            u |= m
        oo, go = u & ~lit & valid, lit & ~u & valid
        base = [edge_mask(e, w) for e in lp.EDGES]
        print(f"\n{test}  w={w}  ours_only={int(oo.sum())} "
              f"gold_only={int(go.sum())}")
        for lab, sel, ms in (("OURS-ONLY", oo, masks), ("GOLD-ONLY", go, base)):
            ys, xs = np.nonzero(sel)
            for y, x in zip(ys, xs):
                for i, m in enumerate(ms):
                    if not m[y, x]:
                        continue
                    e = lp.EDGES[i]
                    ax, ay, bx, by, dx, dy = geo(e)
                    L = float(np.hypot(dx, dy))
                    ux, uy = dx / L, dy / L
                    al = (x + 0.5 - ax) * ux + (y + 0.5 - ay) * uy
                    ac = (x + 0.5 - ax) * (-uy) + (y + 0.5 - ay) * ux
                    mx, mn = max(abs(dx), abs(dy)), min(abs(dx), abs(dy))
                    E = w * (mx + lep.BETA * mn) / mx
                    xmaj = abs(dx) >= abs(dy)
                    mp = (y + 0.5) if xmaj else (x + 0.5)
                    m0, m1 = (ay, by) if xmaj else (ax, bx)
                    out = min(min(m0, m1) - w / 2 - mp, mp - max(m0, m1) - w / 2)
                    print(f"  {lab} ({y},{x}) {e[0]}{e[1]} "
                          f"al={al:.3f} L-al={L - al:.3f} "
                          f"|ac|={abs(ac):.3f} E/2={E / 2:.3f} "
                          f"past w/2 clip by {out:+.3f}")


def corners(golden_dir, lo, hi):
    """The clip value at every CLEAN corner, read off the goldens.

    The footprint's extreme MINOR coordinate is attained at a corner of the
    parallelogram, so for each edge the golden's extreme lit minor coordinate
    in its own clean region minus the endpoints' extreme minor coordinate IS
    the clip, quantised to the pixel centres that happen to be there.  A
    corner counts only when no other edge's footprint dilated by 2 px reaches
    it -- reading a contaminated corner is how a join is mistaken for a cap --
    and only when our own unclipped footprint reaches further than the golden
    at that corner or exactly to it, so the reading is a bound on the clip and
    not on the band.
    """
    print(f"{'test':<14}{'w':>8}{'edge':<10}{'side':>5}{'|s|':>7}"
          f"{'E/2':>8}{'w/2':>8}{'h gold':>8}{'h ours':>8}{'m_end':>10}")
    rows = []
    for test, w, g in lp.captures(golden_dir, lo, hi):
        if test in lep.VOID:
            continue
        lit, valid = lep.ink(g)
        masks = [edge_mask(e, w) for e in lp.EDGES]
        fields = []
        for e in lp.EDGES:
            ax, ay, bx, by, dx, dy = geo(e)
            L = float(np.hypot(dx, dy)) or 1.0
            ux, uy = dx / L, dy / L
            al = (lp.PX - ax) * ux + (lp.PY - ay) * uy
            ac = (lp.PX - ax) * (-uy) + (lp.PY - ay) * ux
            mx, mn = max(abs(dx), abs(dy)), min(abs(dx), abs(dy))
            E = w * (mx + lep.BETA * mn) / mx
            fields.append((al, ac, L, E, abs(dx) >= abs(dy)))
        for i, e in enumerate(lp.EDGES):
            al, ac, L, E, xmaj = fields[i]
            ax, ay, bx, by, dx, dy = geo(e)
            mx, mn = max(abs(dx), abs(dy)), min(abs(dx), abs(dy))
            others = np.zeros_like(lit)
            for j in range(len(lp.EDGES)):
                if j == i:
                    continue
                alj, acj, Lj, Ej, _ = fields[j]
                others |= ((np.abs(acj) <= Ej / 2 + 2) & (alj >= -2) &
                           (alj <= Lj + 2))
            reg = ((np.abs(ac) <= E / 2 + 2) & (al >= -2) & (al <= L + 2) &
                   ~others & valid)
            minor = lp.PY if xmaj else lp.PX
            m0, m1 = (ay, by) if xmaj else (ax, bx)
            for side, m_end in ((+1, max(m0, m1)), (-1, min(m0, m1))):
                sel = reg & (side * (minor - m_end) > 0)
                gm, om = sel & lit, sel & masks[i]
                if not gm.any() or not om.any():
                    continue
                gh = float((side * (minor - m_end))[gm].max())
                oh = float((side * (minor - m_end))[om].max())
                print(f"{test:<14}{w:>8.3f}{e[0] + str(e[1]):<10}{side:>5}"
                      f"{mn / mx:>7.3f}{E / 2:>8.3f}{w / 2:>8.3f}"
                      f"{gh:>8.2f}{oh:>8.2f}{m_end:>10.4f}")
                rows.append((test, w, e[0] + str(e[1]), side, mn / mx, E / 2,
                             gh, oh, m_end))
    if rows:
        import collections
        print(f"\n{len(rows)} clean corners")
        c = collections.Counter(round(r[7] - r[6], 3) for r in rows)
        print("ours minus golden, px of tip we over-reach:")
        for k in sorted(c):
            print(f"  {k:>8}  {c[k]}")
        print("\nthe clip the golden implies, as h - w/2 (h is the last lit "
              "pixel centre, so the clip is in [h, h+1) ):")
        c2 = collections.Counter(round(r[6] - r[1] / 2, 3) for r in rows)
        for k in sorted(c2):
            print(f"  {k:>8}  {c2[k]}")


def shader_poly(e, w, tie=1.0 / 256.0):
    """A transliteration of what emit_line() now emits, corner for corner.

    This is NOT the model above.  It is the geometry-shader code path -- the
    same four corners, the same tie bias, the same two cap_clip() calls on the
    same bounds, in the same order -- so comparing the pixels it covers with
    the model's is what says the shader draws the rule that was derived rather
    than something next to it.  A rule measured offline and a shader that does
    not implement it is the failure this catches, and nothing else here would.
    """
    ax, ay, bx, by, dx, dy = geo(e)
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        return []
    adx, ady = abs(dx), abs(dy)
    k = (w / 2.0) * (max(adx, ady) + 0.5 * min(adx, ady)) / l2
    nx, ny = -dy * k, dx * k
    tx, ty = (0.0, tie) if adx >= ady else (tie, 0.0)
    P = [(ax + nx + tx, ay + ny + ty), (bx + nx + tx, by + ny + ty),
         (bx - nx + tx, by - ny + ty), (ax - nx + tx, ay - ny + ty)]
    xmaj = adx >= ady
    m0, m1 = (ay, by) if xmaj else (ax, bx)
    lo = float(np.floor(min(m0, m1) - w / 2.0))
    hi = float(np.ceil(max(m0, m1) + w / 2.0)) + 1.0

    def clip(poly, bound, dirn):
        out = []
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            da = dirn * ((a[1] if xmaj else a[0]) - bound)
            db = dirn * ((b[1] if xmaj else b[0]) - bound)
            if da >= 0.0 and len(out) < 6:
                out.append(a)
            if (da < 0.0) != (db < 0.0) and len(out) < 6:
                f = da / (da - db)
                out.append((a[0] + (b[0] - a[0]) * f,
                            a[1] + (b[1] - a[1]) * f))
        return out

    return clip(clip(P, lo, 1.0), hi, -1.0)


def shader_mask(e, w, tie=1.0 / 256.0):
    """The pixels that polygon covers, sampled at pixel centres."""
    poly = shader_poly(e, w, tie)
    if len(poly) < 3:
        return np.zeros((lp.H, lp.W), bool)
    area = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        area += x0 * y1 - x1 * y0
    sgn = 1.0 if area >= 0 else -1.0
    m = np.ones((lp.H, lp.W), bool)
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        side = (x1 - x0) * (lp.PY - y0) - (y1 - y0) * (lp.PX - x0)
        m &= (sgn * side) >= 0.0
    return m


def shader_check(golden_dir, lo, hi, tie=1.0 / 256.0):
    """Does the emitted polygon cover exactly the model's pixels?

    At the shipping tie bias of one subpixel quantum the two differ by a few
    pixels per capture BY CONSTRUCTION -- the bias exists to push a band edge
    off a pixel centre, and the analytic model has no bias in it.  Pass
    --shader-tie 1e-9 to take the bias out and leave only the geometry, which
    is the comparison that says the shader draws the derived rule.
    """
    hdr = ("test", "w", "model", "shader", "differ", "vs gold")
    print("%-14s%8s%10s%10s%8s%9s" % hdr)
    bad = tot = gold = 0
    for test, w, g in lp.captures(golden_dir, lo, hi):
        if test in lep.VOID:
            continue
        lit, valid = lep.ink(g)
        um = np.zeros((lp.H, lp.W), bool)
        us = np.zeros((lp.H, lp.W), bool)
        for e in lp.EDGES:
            um |= edge_mask(e, w, cap="perp", pen=1.0, tie="ceil")
            us |= shader_mask(e, w, tie)
        d = int((um ^ us).sum())
        vg = int(((us ^ lit) & valid).sum())
        bad += d
        gold += vg
        tot += 1
        print("%-14s%8.3f%10d%10d%8d%9d" %
              (test, w, int(um.sum()), int(us.sum()), d, vg))
    print("\n%d captures, %d px where the emitted polygon and the model "
          "disagree, %d px against the goldens" % (tot, bad, gold))


def vs_goldens(golden_dir, cap_dir, lo, hi):
    """THE ARM LEG.  Whole-capture INK mismatch between a capture set and the
    goldens, over the 48 non-void Line_* captures.

    Coverage only: it compares the ink MASKS, so the overlap-colour rule --
    #13's separate and much larger residual -- cannot move it in either
    direction, and neither can a palette difference.  That is what makes it
    the right leg for a cap change, and it is the same quantity the extent
    arm quoted as 72,181 px -> 908 px.

    It is golden-constrained: nothing here is derived from the model, so a
    patch cannot make it true by construction.
    """
    gold = {t: g for t, _w, g in lp.captures(golden_dir, lo, hi)}
    print("%-14s%8s%12s%12s%12s" % ("test", "w", "ours-only", "gold-only",
                                    "mismatch"))
    tot = oo_t = go_t = ink = n = 0
    missing = []
    for test, w, g in lp.captures(cap_dir, lo, hi):
        if test in lep.VOID:
            continue
        if test not in gold:
            missing.append(test)
            continue
        glit, gvalid = lep.ink(gold[test])
        olit, ovalid = lep.ink(g)
        valid = gvalid & ovalid
        oo = int((olit & ~glit & valid).sum())
        go = int((glit & ~olit & valid).sum())
        tot += oo + go
        oo_t += oo
        go_t += go
        ink += int((glit & gvalid).sum())
        n += 1
        print("%-14s%8.3f%12d%12d%12d" % (test, w, oo, go, oo + go))
    print("\n%s\n  %d captures, %d golden ink px, %d mismatched "
          "(%d ours-only, %d golden-only) = %.4f%%"
          % (cap_dir, n, ink, tot, oo_t, go_t, 100.0 * tot / max(ink, 1)))
    if missing:
        print("  NO GOLDEN for %d captures: %s" % (len(missing), missing[:6]))
    if n == 0:
        print("  READ NOTHING. A capture set this tool cannot find scores a "
              "perfect zero, so this line is the check on that.")


VARIANTS = {
    "perp": dict(cap="perp"),
    "pen": dict(cap="perp", pen=1.0, tie="floor1"),
    "pen ceil": dict(cap="perp", pen=1.0, tie="ceil"),
    "pen floor": dict(cap="perp", pen=1.0, tie="floor"),
    "pen w/4": dict(cap="perp", pen=0.5, tie="floor1"),
    "pen w": dict(cap="perp", pen=2.0, tie="floor1"),
    "pen both axes": dict(cap="perp", pen=1.0, tie="floor1", major_pen=True),
    "pen, centre band": dict(cap="perp", clip=1.0),
    "pen, no perp cap": dict(cap=None, pen=1.0, tie="floor1"),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", default=os.path.expanduser("~/goldens/results"))
    ap.add_argument("--min-width", type=float, default=0.125)
    ap.add_argument("--max-width", type=float, default=999.0)
    ap.add_argument("--anatomy", action="store_true")
    ap.add_argument("--rivals", action="store_true")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--corners", action="store_true")
    ap.add_argument("--shader", action="store_true",
                    help="rasterise emit_line()'s own polygon and compare it "
                         "with the model, pixel for pixel")
    ap.add_argument("--shader-tie", type=float, default=1.0 / 256.0)
    ap.add_argument("--vs-goldens", metavar="CAPTUREDIR", default=None,
                    help="THE ARM LEG: whole-capture ink mismatch of a "
                         "capture set against the goldens, coverage only")
    ap.add_argument("--only", default=None,
                    help="comma-separated subset of the rival names")
    a = ap.parse_args()

    if a.anatomy:
        kw = VARIANTS[a.only] if a.only else None
        anatomy(a.goldens, a.min_width, a.max_width, kw)
        return

    if a.vs_goldens:
        vs_goldens(a.goldens, a.vs_goldens, a.min_width, a.max_width)
        return

    if a.shader:
        shader_check(a.goldens, a.min_width, a.max_width, a.shader_tie)
        return

    if a.corners:
        corners(a.goldens, a.min_width, a.max_width)
        return

    if a.rivals:
        variants = dict(VARIANTS)
        if a.only:
            want = a.only.split(",")
            variants = {k: v for k, v in variants.items() if k in want}
        print(f"{'test':<14}{'w':>8}{'gold ink':>10}"
              + "".join(f"{k[:9]:>10}" for k in variants))
        tot, exact, n_ink, n_cap = score(a.goldens, a.min_width, a.max_width,
                                         variants, verbose=True)
        print(f"\n{n_cap} captures, {n_ink} golden ink px")
        print(f"{'variant':<28}{'mismatch':>10}{'%':>10}{'exact':>8}")
        for k in variants:
            print(f"{k:<28}{tot[k]:>10}{100 * tot[k] / n_ink:>9.4f}%"
                  f"{exact[k]:>8}")
        return

    if a.controls:
        controls(a.goldens, a.min_width, a.max_width)
        return


def controls(golden_dir, lo, hi):
    """What the instrument cannot see.

    1. How many pixels the clip can touch at all: if that population were
       empty the goldens could not select it, and a score that did not move
       would say nothing.
    2. Of those, how many the goldens actually agree with -- so a rule that
       merely removes disputed pixels is told apart from one that removes the
       right ones.
    3. The tie population: clip boundaries landing exactly on a pixel centre,
       which is what separates low-open from closed.
    """
    touch = agree = wrong = ties = 0
    for test, w, g in lp.captures(golden_dir, lo, hi):
        if test in lep.VOID:
            continue
        lit, valid = lep.ink(g)
        a_ = union(w, cap="perp")
        b_ = union(w, cap="perp", clip=1.0)
        removed = a_ & ~b_ & valid
        touch += int(removed.sum())
        agree += int((removed & ~lit).sum())
        wrong += int((removed & lit).sum())
        for e in lp.EDGES:
            ax, ay, bx, by, dx, dy = geo(e)
            m0, m1 = (ay, by) if abs(dx) >= abs(dy) else (ax, bx)
            for v in (min(m0, m1) - w / 2, max(m0, m1) + w / 2):
                if abs(v - np.floor(v) - 0.5) < 1e-9:
                    ties += 1
    print(f"pixels the w/2 clip removes from the perpendicular footprint: "
          f"{touch}")
    print(f"  of those, golden-dark (the clip was right):   {agree}")
    print(f"  of those, golden-lit  (the clip was wrong):   {wrong}")
    print(f"clip boundaries landing exactly on a pixel centre "
          f"(the tie population that separates low-open from closed): {ties}")


if __name__ == "__main__":
    main()
