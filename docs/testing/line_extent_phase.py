#!/usr/bin/env python3
"""Silicon's wide-line extent PHASE, derived from the goldens.  No device, no build.

#13 recorded the extent rule as `w * (1 + tan(theta)/2)` -- the alpha-max-plus-
beta-min hypot approximation -- measured 100% "in-band" over 9,611 clean cuts,
where in-band means the observed integer run LENGTH is floor(E) or ceil(E).  The
blocker inherited from that reading was that the PHASE (which of the two) is
UNDETERMINED by the available goldens, so a correct widening could never be
scored pixel-exact and a leg demanding exactness would fail on a right fix.

THAT IS FALSE, and this tool is the measurement.  The in-band reading threw away
the two most informative numbers in every sample: `line_priority.py --extent`
records only `b - a + 1`, while the goldens also carry `a` and `b` themselves.
The run's POSITION is what pins the phase.

THE RULE, three discrete choices each SELECTED by the data (see --rivals):

  1. Vertex screen coordinates are TRUNCATED to 1/16 of a pixel.  That is the
     NV2A rasteriser's fixed-point vertex format; round-to-nearest, 1/8 and
     1/32 all score worse, and no snap at all scores worse still.
  2. The minor-axis extent is E = w * (max + min/2) / max, evaluated on the
     TRUNCATED coordinates (max, min = larger and smaller of |dx|, |dy|).
  3. A pixel is lit iff its CENTRE lies in the LOW-OPEN band
     (c - E/2, c + E/2],  c the edge centre at that scanline's pixel centre:
         a = floor(c - E/2 - 1/2) + 1        b = floor(c + E/2 - 1/2)
     No fitted offset: the sample point is the pixel centre on both axes.

Measured against the goldens, both endpoints of every clean cut:

     8,890 cuts at widths 6-48 (the set #13's extent rule was fitted on) 100.00%
    12,056 cuts at widths <= 5, NEVER used in any #13 derivation           100.00%

and on whole-capture coverage over all 48 non-void Line_* captures the rule
misses 495 of 1,967,133 ink pixels (0.025%), 14 captures pixel-exact, against
59,605 (3.030%) for the perpendicular rectangle we draw today.  493 of the 495
are ours-only and 98.8% sit within w/2 + 2 of a vertex: what is left is the CAP
and JOIN phase, which this measurement does not settle.

  --controls    what the instrument cannot see: how many cuts can separate
                floor from ceil at all, and an impossible-row check
  --rivals      every competing choice scored on the same cuts
  --reconstruct whole-capture coverage, derived rule vs what we draw today
  --grid        scan the sample-point offsets, to show 1/2 is not fitted
  --per-edge    where a model fails, by edge
  --captures D  score OUR captures instead of the goldens
  --vs-goldens D  THE ARM LEG.  Find the clean cuts in the GOLDENS, then read
                the same scanline out of the capture set D and compare the two
                runs endpoint for endpoint.  This is golden-constrained: it
                asks whether our render agrees with silicon, never whether it
                agrees with the model above, so a patch cannot make it true by
                construction.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import line_priority as lp

CLEAR = 4.0
EPS = 1e-9
SNAP = 16.0            # vertex coordinates truncate to 1/16 px
BETA = 0.5             # alpha-max-plus-beta-min, beta = 1/2

# Line_0064.0-.7 have goldens byte-identical to Line_0001.0: the width register
# holds nine bits of eighths and 64.0 does not fit, so hardware drew them at
# 1.0.  Any model draws them at 64.  They are VOID, not evidence -- see #13.
VOID = {f"Line_0064.{i}" for i in range(8)}


def snap(v, grid=SNAP, mode="floor"):
    f = np.floor if mode == "floor" else np.round
    return float(f(v * grid) / grid) if grid else float(v)


def cuts(golden_dir, lo, hi, clear=CLEAR):
    """Clean minor-axis cuts: (test, w, edge_index, xmaj, line, a, b).

    `line` is the major-axis pixel index; (a, b) the first and last lit minor-
    axis index of the run through the edge.  A cut is kept only when the whole
    scanline through this edge's perpendicular footprint is free of every other
    edge's footprint dilated by `clear`, the run does not touch the frame, and
    the run's two neighbours are inside that free region too -- so the observed
    endpoints are this edge's own and not a collision with a neighbour.
    """
    out = []
    for test, w, g in lp.captures(golden_dir, lo, hi):
        if test in VOID:
            continue
        lit = (np.abs(g[:, :, :3] - lp.BG).max(axis=2) > 8) & (g[:, :, 3] == 255)
        mine, theirs, geo = [], [], []
        for e in lp.EDGES:
            (ax, ay), (bx, by) = e[3][0], e[4][0]
            dx, dy = bx - ax, by - ay
            L = float(np.hypot(dx, dy))
            ux, uy = dx / L, dy / L
            along = (lp.PX - ax) * ux + (lp.PY - ay) * uy
            across = (lp.PX - ax) * (-uy) + (lp.PY - ay) * ux
            mine.append((np.abs(across) <= w / 2) & (along >= 0) & (along <= L))
            theirs.append((np.abs(across) <= w / 2 + clear) &
                          (along >= -clear) & (along <= L + clear))
            geo.append((L, (ax, ay), (ux, uy), abs(dx) >= abs(dy)))
        for i, e in enumerate(lp.EDGES):
            others = np.zeros_like(mine[i])
            for j in range(len(lp.EDGES)):
                if j != i:
                    others |= theirs[j]
            free = mine[i] & ~others
            if not free.any():
                continue
            L, (ax, ay), (ux, uy), xmaj = geo[i]
            ax_ = 0 if xmaj else 1
            for line in np.nonzero(free.any(axis=ax_))[0]:
                cm = mine[i][:, line] if xmaj else mine[i][line, :]
                cf = free[:, line] if xmaj else free[line, :]
                if not np.array_equal(cm, cf):
                    continue
                idx = np.nonzero(cm)[0]
                if len(idx) < 2:
                    continue
                mid = idx[(len(idx) - 1) // 2]
                p = (line + 0.5, mid + 0.5) if xmaj else (mid + 0.5, line + 0.5)
                al = (p[0] - ax) * ux + (p[1] - ay) * uy
                if al < w or al > L - w:          # keep clear of the butt caps
                    continue
                v = lit[:, line] if xmaj else lit[line, :]
                nf = (~others)[:, line] if xmaj else (~others)[line, :]
                if not v[mid]:
                    continue
                a = b = mid
                while a > 0 and v[a - 1]:
                    a -= 1
                while b < len(v) - 1 and v[b + 1]:
                    b += 1
                if a == 0 or b == len(v) - 1:
                    continue
                if not (nf[a - 1] and nf[b + 1]):  # endpoints must be this edge's
                    continue
                out.append((test, w, i, xmaj, int(line), int(a), int(b)))
    return out


def tabulate(rows, grid=SNAP, mode="floor", beta=BETA, perp=False):
    """Row-wise geometry: (E, xmaj, line, p, q, obs_a, obs_b).

    The minor-axis centre at major-axis pixel `line` is p + q * (line + off).
    """
    E, xm, ln, p, q, oa, ob = [], [], [], [], [], [], []
    for (_t, w, i, xmaj, line, a, b) in rows:
        (ax, ay), (bx, by) = lp.EDGES[i][3][0], lp.EDGES[i][4][0]
        ax, ay, bx, by = (snap(ax, grid, mode), snap(ay, grid, mode),
                          snap(bx, grid, mode), snap(by, grid, mode))
        dx, dy = bx - ax, by - ay
        mx, mn = max(abs(dx), abs(dy)), min(abs(dx), abs(dy))
        E.append(w * np.hypot(dx, dy) / mx if perp else w * (mx + beta * mn) / mx)
        xm.append(xmaj)
        ln.append(line)
        s = (dy / dx) if xmaj else (dx / dy)
        p.append((ay - ax * s) if xmaj else (ax - ay * s))
        q.append(s)
        oa.append(a)
        ob.append(b)
    return (np.array(E), np.array(xm, bool), np.array(ln, float), np.array(p),
            np.array(q), np.array(oa, float), np.array(ob, float))


def predict(T, dxo=0.5, dyo=0.5, rule="low_open"):
    """Predicted (a, b) for every cut."""
    E, xm, ln, p, q, _oa, _ob = T
    c = p + q * (ln + np.where(xm, dxo, dyo))
    off = np.where(xm, dyo, dxo)
    lo, hi = c - E / 2 - off, c + E / 2 - off
    if rule == "low_open":
        return np.floor(lo + EPS) + 1, np.floor(hi + EPS)
    if rule == "closed":
        return np.ceil(lo - EPS), np.floor(hi + EPS)
    if rule == "high_open":
        return np.ceil(lo - EPS), np.ceil(hi - EPS) - 1
    return np.floor(lo + EPS) + 1, np.ceil(hi - EPS) - 1


def exact(T, **kw):
    pa, pb = predict(T, **kw)
    return (pa == T[5]) & (pb == T[6])


def edge_mask(e, w, cap="perp"):
    """The pixels this edge lights under the derived rule."""
    H, Wd = lp.H, lp.W
    (ax, ay), (bx, by) = e[3][0], e[4][0]
    ax, ay, bx, by = snap(ax), snap(ay), snap(bx), snap(by)
    dx, dy = bx - ax, by - ay
    m = np.zeros((H, Wd), bool)
    if dx == 0 and dy == 0:
        return m
    mx, mn = max(abs(dx), abs(dy)), min(abs(dx), abs(dy))
    E = w * (mx + BETA * mn) / mx
    L = float(np.hypot(dx, dy))
    ux, uy = dx / L, dy / L
    xmaj = abs(dx) >= abs(dy)
    n, lim = (Wd, H) if xmaj else (H, Wd)
    s = (dy / dx) if xmaj else (dx / dy)
    p0 = (ay - ax * s) if xmaj else (ax - ay * s)
    for k in range(n):
        M = k + 0.5
        c = p0 + s * M
        a = int(np.floor(c - E / 2 - 0.5 + EPS)) + 1
        b = int(np.floor(c + E / 2 - 0.5 + EPS))
        a, b = max(a, 0), min(b, lim - 1)
        if b < a:
            continue
        idx = np.arange(a, b + 1)
        if cap == "perp":                 # butt cap, perpendicular to the line
            al = ((M - ax) * ux + (idx + 0.5 - ay) * uy if xmaj
                  else (idx + 0.5 - ax) * ux + (M - ay) * uy)
            idx = idx[(al >= 0) & (al <= L)]
        if xmaj:
            m[idx, k] = True
        else:
            m[k, idx] = True
    return m


def ours_mask(e, w):
    """What we draw today: perpendicular rectangle, pixel centres, closed band."""
    (ax, ay), (bx, by) = e[3][0], e[4][0]
    dx, dy = bx - ax, by - ay
    L = float(np.hypot(dx, dy))
    ux, uy = dx / L, dy / L
    across = (lp.PX - ax) * (-uy) + (lp.PY - ay) * ux
    along = (lp.PX - ax) * ux + (lp.PY - ay) * uy
    return (np.abs(across) <= w / 2) & (along >= 0) & (along <= L)


def ink(g):
    """Golden ink, excluding the text overlay and the POINTS block."""
    lit = (np.abs(g[:, :, :3] - lp.BG).max(axis=2) > 8) & (g[:, :, 3] == 255)
    bad = lp.text_mask(g)
    for (px, py) in lp.POINTS:
        X, Y = int(px + lp.OX), int(py + lp.OY)
        bad[max(0, Y - 2):Y + 3, max(0, X - 2):X + 3] = True
    return lit, ~bad


def run_at(lit, xmaj, line, mid):
    """The lit run through (line, mid), or None if it touches the frame."""
    v = lit[:, line] if xmaj else lit[line, :]
    if not v[mid]:
        return None
    a = b = mid
    while a > 0 and v[a - 1]:
        a -= 1
    while b < len(v) - 1 and v[b + 1]:
        b += 1
    if a == 0 or b == len(v) - 1:
        return None
    return a, b


def vs_goldens(golden_dir, cap_dir, lo, hi):
    """Compare a capture set's runs with the goldens' runs, cut by cut."""
    rows = cuts(golden_dir, lo, hi)
    by_test = {}
    for r in rows:
        by_test.setdefault(r[0], []).append(r)
    ours = {t: g for t, _w, g in lp.captures(cap_dir, lo, hi)}
    n = same = missing = 0
    per = {}
    for test, rs in sorted(by_test.items()):
        g = ours.get(test)
        if g is None:
            missing += len(rs)
            continue
        lit = (np.abs(g[:, :, :3] - lp.BG).max(axis=2) > 8) & (g[:, :, 3] == 255)
        ok = 0
        for (_t, _w, _i, xmaj, line, a, b) in rs:
            n += 1
            r = run_at(lit, xmaj, line, (a + b) // 2)
            if r == (a, b):
                ok += 1
        same += ok
        per[test] = (ok, len(rs))
    return n, same, missing, per


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", default=os.path.expanduser("~/goldens/results"))
    ap.add_argument("--captures", default=None,
                    help="score OUR captures instead of the goldens")
    ap.add_argument("--min-width", type=float, default=0.125)
    ap.add_argument("--max-width", type=float, default=999.0)
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--rivals", action="store_true")
    ap.add_argument("--reconstruct", action="store_true")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--step", type=float, default=0.01)
    ap.add_argument("--per-edge", action="store_true")
    ap.add_argument("--vs-goldens", metavar="CAPTUREDIR", default=None)
    a = ap.parse_args()

    if a.vs_goldens:
        n, same, missing, per = vs_goldens(a.goldens, a.vs_goldens,
                                           a.min_width, a.max_width)
        print(f"{'test':<16}{'agree':>8}{'cuts':>8}{'%':>9}")
        for test, (ok, tot) in per.items():
            print(f"{test:<16}{ok:>8}{tot:>8}{100 * ok / tot:>8.2f}%")
        print(f"\n{a.vs_goldens}\n  agrees with the goldens on {same} of {n} "
              f"golden clean cuts = {100 * same / max(n, 1):.4f}%"
              + (f"  ({missing} cuts had no matching capture)" if missing else ""))
        return

    src = a.captures or a.goldens
    if a.reconstruct:
        H, Wd = lp.H, lp.W
        tot = {"derived": 0, "ours": 0}
        n_ink = n_exact = n_cap = 0
        print(f"{'test':<14}{'w':>8}{'gold ink':>10}{'derived':>10}{'ours':>10}")
        for test, w, g in lp.captures(src, a.min_width, a.max_width):
            if test in VOID:
                continue
            lit, valid = ink(g)
            n_ink += int((lit & valid).sum())
            u = np.zeros((H, Wd), bool)
            for e in lp.EDGES:
                u |= edge_mask(e, w)
            d = int(((u ^ lit) & valid).sum())
            tot["derived"] += d
            n_exact += (d == 0)
            v = np.zeros((H, Wd), bool)
            for e in lp.EDGES:
                v |= ours_mask(e, w)
            o = int(((v ^ lit) & valid).sum())
            tot["ours"] += o
            n_cap += 1
            print(f"{test:<14}{w:>8.3f}{int((lit & valid).sum()):>10}{d:>10}{o:>10}")
        print(f"\n{n_cap} captures, {n_ink} golden ink px, "
              f"{n_exact} pixel-exact in coverage under the derived rule")
        for k, v in tot.items():
            print(f"  {k:<10}{v:>10} mismatched px = {100 * v / n_ink:.4f}%")
        return

    rows = cuts(src, a.min_width, a.max_width)
    if not rows:
        print("no clean cuts")
        return
    T = tabulate(rows)
    E, xm = T[0], T[1]
    ok = exact(T)
    print(f"{len(rows)} clean cuts from {src}: "
          f"{int((~xm).sum())} x-minor, {int(xm.sum())} y-minor, "
          f"{len(set(r[2] for r in rows))} edges")
    print(f"widths {sorted(set(r[1] for r in rows))}")
    print(f"\nDERIVED RULE (1/16 truncate, beta=1/2, low-open, pixel centres): "
          f"{100 * ok.mean():.4f}% exact on BOTH endpoints, "
          f"{int((~ok).sum())} wrong\n")

    if a.controls:
        oa, ob = T[5], T[6]
        obs_len = ob - oa + 1
        disc = (E - np.floor(E)) > 1e-9
        print(f"phase-discriminating cuts (frac(E) != 0): "
              f"{int(disc.sum())}/{len(rows)}  -- if this were 0 the corpus "
              f"could not separate floor from ceil at all")
        print(f"  of those, {int((disc & (obs_len == np.ceil(E))).sum())} take "
              f"ceil and {int((disc & (obs_len == np.floor(E))).sum())} floor")
        print(f"  integer-E cuts: {int((~disc).sum())}; "
              f"length - E values seen: "
              f"{sorted(set((obs_len[~disc] - E[~disc]).round(9).tolist()))}")
        print(f"  impossible rows (length outside [floor,ceil]): "
              f"{int(((obs_len < np.floor(E)) | (obs_len > np.ceil(E))).sum())}")
        print()

    if a.rivals:
        print(f"{'variant':<42}{'exact':>10}{'wrong':>8}")
        for lab, kw, rule in (
                ("DERIVED", {}, "low_open"),
                ("no sub-pixel truncation", {"grid": None}, "low_open"),
                ("1/16 round-to-nearest", {"mode": "round"}, "low_open"),
                ("1/8 truncate", {"grid": 8}, "low_open"),
                ("1/32 truncate", {"grid": 32}, "low_open"),
                ("beta = 1   w(1+tan)", {"beta": 1.0}, "low_open"),
                ("beta = 0   w  (Bresenham)", {"beta": 0.0}, "low_open"),
                ("perpendicular rectangle w/cos", {"perp": True}, "low_open"),
                ("tie-break closed", {}, "closed"),
                ("tie-break high-open", {}, "high_open"),
                ("tie-break open", {}, "open")):
            TT = tabulate(rows, **kw)
            k = exact(TT, rule=rule)
            print(f"{lab:<42}{100 * k.mean():>9.4f}%{int((~k).sum()):>8}")
        print()

    if a.grid:
        oa, ob = T[5], T[6]
        gs = np.round(np.arange(0.0, 1.0, a.step), 6)
        best, plateau = -1, []
        for dxo in gs:
            for dyo in gs:
                pa, pb = predict(T, dxo, dyo)
                n = int(((pa == oa) & (pb == ob)).sum())
                if n > best:
                    best, plateau = n, [(dxo, dyo)]
                elif n == best:
                    plateau.append((dxo, dyo))
        print(f"sample-point scan: best {best}/{len(rows)} at "
              f"{len(plateau)} grid points, "
              f"dx in [{min(z[0] for z in plateau):.3f}, "
              f"{max(z[0] for z in plateau):.3f}], "
              f"dy in [{min(z[1] for z in plateau):.3f}, "
              f"{max(z[1] for z in plateau):.3f}]\n")

    if a.per_edge:
        idx = np.array([r[2] for r in rows])
        print(f"{'edge':<18}{'minor':>6}{'n':>7}{'exact':>9}")
        for i in sorted(set(idx.tolist())):
            for want in (False, True):
                m = (idx == i) & (xm == want)
                if m.any():
                    print(f"{lp.LAB(i):<18}{'y' if want else 'x':>6}"
                          f"{int(m.sum()):>7}{100 * ok[m].mean():>8.2f}%")


if __name__ == "__main__":
    main()
