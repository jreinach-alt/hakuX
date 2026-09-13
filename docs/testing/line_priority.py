#!/usr/bin/env python3
"""Derive silicon's wide-line EDGE PRIORITY and EXTENT rules from the goldens.

Offline: needs only `goldens/results/Line_width`.  No device, no build.

`Line width` draws seven primitives in eight known palette colours at known
screen positions, with the depth test off and every palette entry opaque, so
the colour at a pixel covered by several wide edges names *the edge silicon
drew last*.  Two questions fall out of that and this tool answers both by
reading pixels whose answer each candidate rule predicts differently, rather
than by fitting a pixel total.

  --order    the pairwise "which edge wins" relation, and whether it is a
             consistent emission order at all (a cycle would kill every
             ordering rule outright and force a geometric one)
  --rules    every candidate rule scored on the decisive pixels
  --extent   golden minor-axis extent against cos(theta) on CLEAN,
             non-overlapping edges -- the sweep the coverage hypothesis wanted

CONVENTIONS MEASURED, NOT ASSUMED
  * SET_DIFFUSE takes the suite's kPalette words as ABGR: the sixteen POINTS
    read back with R and B exchanged (0->2, 1->1, 2->0, 3->4, 4->3, 5->5,
    6->6, 7->7 is exactly swap(R,B)).  Get this wrong and every colour
    identification is a different edge.
  * A pixel's colour on an edge is lerp(c_a, c_b, t) with t the projection of
    the pixel centre onto the segment.  Verified on solo-covered pixels:
    97.7% within 4/255 at w = 16.
  * The text overlay is drawn last with alpha 0; those pixels and a 2px
    dilation of them are excluded.
"""
import argparse
import itertools
import os
import re
import sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

H, W = 480, 640
SUITE = "Line_width"
BG = np.array([0x20, 0x22, 0x24])
OX, OY = 160.0, 48.0          # framebuffer * (0.25, 0.10)
NAME = re.compile(r"Line_(\d+)\.(\d)$")

# Decisive-pixel thresholds.  MARGIN keeps the sample away from every
# rectangle boundary, so neither the half-pixel centre question nor the extent
# rule can decide the answer; SEP demands the candidates predict visibly
# different colours; TOL demands the golden name exactly one of them.
MARGIN, SEP, TOL = 3.0, 48, 10
CLEAR = 4.0                   # extent sweep: clearance from every other edge

PALETTE_RAW = [0xFFFF3333, 0xFF33FF33, 0xFF3333FF, 0xFFFFFF33,
               0xFF33FFFF, 0xFFFF33FF, 0xFF808080, 0xFFFFFFFF]
PALETTE = [(c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF) for c in PALETTE_RAW]

POINTS = [(19.0,15.0),(56.0,29.0),(74.0,77.0),(45.694406,101.330152),
          (36.0,38.369815),(14.0,23.0),(85.0,98.0),(31.0,40.0),
          (98.0,38.0),(17.0,104.0),(78.0,65.0),(31.644774,49.0),
          (105.0,11.968842),(9.0,40.0),(105.962647,76.068491),(80.0,87.0)]
LOOP = [(196.0,47.0),(194.0,19.0),(182.0,97.0),(106.18625,80.0),
        (127.0,94.58163),(133.597443,13.763389),(205.0,62.0),(115.54392,16.0),
        (122.0,3.0),(117.062706,87.735558),(201.0,28.664894),(146.114091,10.0),
        (205.356591,88.0),(125.0,107.0),(190.828953,35.510304),(163.0,105.956814)]
TRIS = [(265.185925,35.0),(249.778838,22.523717),(310.0,19.0),
        (243.978231,47.650185),(304.0,37.0),(232.0,102.522615)]
QSTRIP = [(0.0,239.0),(0.0,120.0),(52.5,225.4),(54.75,175.5),(105.0,239.0),(105.0,120.0)]
TFAN = [(158.5,205.0),(115.545455,239.0),(120.318182,120.0),(147.045455,157.4),
        (158.5,128.5),(166.136364,145.5),(204.318182,159.1),(209.75,239.0)]
POLY = [(218.0,232.0),(237.772727,142.1),(258.772727,120.0),
        (302.681818,169.3),(317.0,230.5)]
QUADS = [(0.0,350.0),(60.0,340.0),(58.5,425.4),(12.75,407.5)]

# Submission order of the blocks, which is also their painter order.
BLOCKS = [("LLoop", LOOP), ("Tri", TRIS), ("QStrip", QSTRIP),
          ("TFan", TFAN), ("Poly", POLY), ("Quad", QUADS)]

YY, XX = np.mgrid[0:H, 0:W]
PX, PY = XX + 0.5, YY + 0.5


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
def our_edges(block, n):
    """The index pairs OUR renderer emits, in OUR order (prim_rewrite.c)."""
    if block == "LLoop":
        return [(i, (i + 1) % n) for i in range(n)]
    if block == "Tri":
        return [e for t in range(0, n - 2, 3)
                for e in ((t, t+1), (t+1, t+2), (t+2, t))]
    if block == "TFan":
        return [e for t in range(1, n - 1)
                for e in ((0, t), (t, t+1), (t+1, 0))]
    if block == "QStrip":
        return [e for i in range(0, n - 3, 2)
                for e in ((i, i+1), (i+1, i+3), (i+3, i+2), (i+2, i))]
    if block == "Poly":
        return [(i, i + 1) for i in range(n - 1)] + [(n - 1, 0)]
    if block == "Quad":
        return [e for i in range(0, n - 3, 4)
                for e in ((i, i+1), (i+1, i+2), (i+2, i+3), (i+3, i))]
    raise KeyError(block)


def all_edges():
    """[(block, k, (i,j), (pos_a, col_a), (pos_b, col_b))] in OUR order."""
    out = []
    for name, blk in BLOCKS:
        vs = [((x + OX, y + OY), PALETTE[i % 8]) for i, (x, y) in enumerate(blk)]
        for k, (i, j) in enumerate(our_edges(name, len(blk))):
            out.append((name, k, (i, j), vs[i], vs[j]))
    return out


EDGES = all_edges()
NEDGE = Counter(e[0] for e in EDGES)
BASE = {}
for _i, _e in enumerate(EDGES):
    BASE.setdefault(_e[0], _i)
LAB = lambda i: f"{EDGES[i][0]}#{EDGES[i][1]}{EDGES[i][2]}"


def field(e, w, bias=(0.0, 0.0), margin=0.0, extent_rule=False):
    """(coverage, t, |across|, length) for one edge at one width."""
    (ax, ay), (bx, by) = e[3][0], e[4][0]
    ax += bias[0]; bx += bias[0]; ay += bias[1]; by += bias[1]
    dx, dy = bx - ax, by - ay
    L = float(np.hypot(dx, dy))
    ux, uy = dx / L, dy / L
    along = (PX - ax) * ux + (PY - ay) * uy
    across = (PX - ax) * (-uy) + (PY - ay) * ux
    hw = w / 2.0
    if extent_rule:
        # silicon's perpendicular half-width: w/2 scaled by the
        # alpha-max-plus-beta-min hypot approximation (max + min/2) / L.
        mx, mn = max(abs(dx), abs(dy)), min(abs(dx), abs(dy))
        hw *= (mx + mn / 2.0) / L
    cov = (np.abs(across) <= hw - margin) & (along >= margin) & (along <= L - margin)
    return cov, np.clip(along / L, 0.0, 1.0), np.abs(across), L


def edge_colour(e, t):
    ca = np.array(e[3][1], dtype=np.float64)
    cb = np.array(e[4][1], dtype=np.float64)
    return ca[None, None, :] * (1 - t[..., None]) + cb[None, None, :] * t[..., None]


# --------------------------------------------------------------------------
# candidate emission-order schemes
# --------------------------------------------------------------------------
def _perm(ab, bc, ca, which):
    """The three edges of one triangle, in the order a scheme submits them."""
    return {"opp_abc": [bc, ca, ab],   # edge opposite a, then opposite b, then c
            "opp_acb": [bc, ab, ca],
            "tri_rev": [ca, bc, ab],
            "tri_rot": [ca, ab, bc],
            "tri_id":  [ab, bc, ca],
            "tri_acb": [ab, ca, bc]}[which]


def order_for(block, which):
    """OUR edge indices, in the order `which` says silicon submits them.

    Every scheme but `ours`/`reverse` triangulates exactly as the FILL path
    does (`prim_rewrite.c`: QUADS on the v0-v2 diagonal, QUAD_STRIP on
    v1-v2, POLYGON as a fan from v0), drops the tessellation's internal
    edges -- which the goldens confirm are absent at width 1 -- and orders
    each triangle's surviving edges by `_perm`.
    """
    n = NEDGE[block]
    if which == "ours":
        return list(range(n))
    if which == "reverse":
        return list(range(n))[::-1]
    if block == "LLoop":
        return list(range(n))
    if block in ("Tri", "TFan"):
        return [e for t in range(n // 3) for e in _perm(3*t, 3*t+1, 3*t+2, which)]
    if block == "Quad":
        out = []
        for q in range(n // 4):
            b = 4 * q
            out += [e for e in _perm(b+0, b+1, None, which) if e is not None]
            out += [e for e in _perm(None, b+2, b+3, which) if e is not None]
        return out
    if block == "QStrip":
        out = []
        for q in range(n // 4):
            b = 4 * q
            out += [e for e in _perm(b+0, None, b+3, which) if e is not None]
            out += [e for e in _perm(None, b+1, b+2, which) if e is not None]
        return out
    if block == "Poly":
        out = []
        for t in range(1, n - 1):
            ab = 0 if t == 1 else None
            ca = n - 1 if t == n - 2 else None
            out += [e for e in _perm(ab, t, ca, which) if e is not None]
        return out
    raise KeyError(block)


SCHEMES = ["ours", "reverse", "opp_abc", "opp_acb",
           "tri_rev", "tri_rot", "tri_id", "tri_acb"]
GEOMETRIC = ["nearest_centre", "farthest_centre", "longest_edge",
             "shortest_edge", "highest_index", "lowest_index", "nearest_vertex"]


def rank_table(which):
    rank, base = {}, 0
    for blk, _ in BLOCKS:
        for r, e in enumerate(order_for(blk, which)):
            rank[BASE[blk] + e] = base + r
        base += 1000
    return rank


RANK = {s: rank_table(s) for s in SCHEMES}


def pick(cands, rule):
    """cands = [(edge, across, t, length)]; the edge the rule says wins."""
    if rule in RANK:
        return max(cands, key=lambda c: RANK[rule][c[0]])[0]
    if rule == "nearest_centre":  return min(cands, key=lambda c: c[1])[0]
    if rule == "farthest_centre": return max(cands, key=lambda c: c[1])[0]
    if rule == "longest_edge":    return max(cands, key=lambda c: c[3])[0]
    if rule == "shortest_edge":   return min(cands, key=lambda c: c[3])[0]
    if rule == "highest_index":   return max(cands, key=lambda c: c[0])[0]
    if rule == "lowest_index":    return min(cands, key=lambda c: c[0])[0]
    if rule == "nearest_vertex":  return min(cands, key=lambda c: min(c[2], 1-c[2]) * c[3])[0]
    raise KeyError(rule)


# --------------------------------------------------------------------------
# captures
# --------------------------------------------------------------------------
def captures(golden_dir, lo, hi):
    d = os.path.join(golden_dir, SUITE)
    for f in sorted(os.listdir(d)):
        m = NAME.match(f[:-4])
        if not m:
            continue
        w = int(m.group(1)) + int(m.group(2)) / 8.0
        if lo <= w <= hi:
            yield f[:-4], w, np.asarray(
                Image.open(os.path.join(d, f)).convert("RGBA")).astype(np.int16)


def text_mask(g):
    t = g[:, :, 3] != 255
    d = t.copy()
    for s in (1, -1, 2, -2):
        d |= np.roll(t, s, axis=0)
        d |= np.roll(t, s, axis=1)
    return d


def decisive(g, w, extent_rule=False):
    """Pixels whose colour is decided by the priority rule alone.

    Deep inside >= 2 rectangles under BOTH candidate x-conventions, inside no
    third rectangle even marginally, candidate colours pairwise >= SEP apart,
    and the golden within TOL of exactly one of them.
    """
    d = text_mask(g)
    deep = np.ones((len(EDGES), H, W), dtype=bool)
    full = np.zeros((len(EDGES), H, W), dtype=bool)
    cols = np.empty((len(EDGES), H, W, 3))
    acr = np.empty((len(EDGES), H, W))
    alo = np.empty((len(EDGES), H, W))
    lns = np.empty(len(EDGES))
    for i, e in enumerate(EDGES):
        for bias in ((0.0, 0.0), (0.5, 0.0)):
            c, t, a, L = field(e, w, bias, MARGIN, extent_rule)
            deep[i] &= c
            f, _, _, _ = field(e, w, bias, 0.0, extent_rule)
            full[i] |= f
        cols[i], acr[i], alo[i], lns[i] = edge_colour(e, t), a, t, L
    nd, nf = deep.sum(0), full.sum(0)
    ys, xs = np.nonzero((nd >= 2) & (nd == nf) & ~d)
    out = []
    for y, x in zip(ys, xs):
        which = np.nonzero(deep[:, y, x])[0]
        cc = cols[which, y, x]
        if min(np.abs(cc[i] - cc[j]).max()
               for i, j in itertools.combinations(range(len(which)), 2)) < SEP:
            continue
        errs = np.abs(cc - g[y, x, :3].astype(float)).max(axis=1)
        o = np.argsort(errs)
        if errs[o[0]] > TOL or errs[o[1]] <= TOL * 3:
            continue
        out.append((int(which[o[0]]),
                    [(int(e), float(acr[e, y, x]), float(alo[e, y, x]),
                      float(lns[e])) for e in which]))
    return out


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------
def collect(golden_dir, lo, hi, extent_rule=False):
    pixels = []
    for test, w, g in captures(golden_dir, lo, hi):
        d = decisive(g, w, extent_rule)
        pixels += d
        print(f"  {test:<14} w={w:<8} decisive={len(d)}", file=sys.stderr)
    return pixels


def report_order(pixels, min_n=200, max_minority=0.05):
    tally = defaultdict(Counter)
    for win, cands in pixels:
        for (e, _, _, _) in cands:
            if e != win:
                tally[tuple(sorted((e, win)))][win] += 1
    rel = {}
    print(f"{len(pixels)} decisive pixels, {len(tally)} contested pairs\n")
    print(f"{'winner':<24}{'loser':<24}{'n':>8}{'minority':>10}")
    for (a, b), c in sorted(tally.items(), key=lambda kv: -sum(kv[1].values())):
        na, nb = c.get(a, 0), c.get(b, 0)
        n, mn = na + nb, min(na, nb)
        if n < min_n or mn / n >= max_minority:
            continue
        wn, ls = (a, b) if na > nb else (b, a)
        rel[(wn, ls)] = n
        print(f"{LAB(wn):<24}{LAB(ls):<24}{n:>8}{mn/n*100:>9.2f}%")
    print()
    for blk, _ in BLOCKS:
        nodes = [BASE[blk] + i for i in range(NEDGE[blk])]
        succ = defaultdict(set)
        for (wn, ls) in rel:
            if wn in nodes and ls in nodes:
                succ[ls].add(wn)
        indeg = {n_: 0 for n_ in nodes}
        for u in succ:
            for v in succ[u]:
                indeg[v] += 1
        q = sorted(n_ for n_ in nodes if not indeg[n_])
        order = []
        while q:
            u = q.pop(0); order.append(u)
            for v in sorted(succ[u]):
                indeg[v] -= 1
                if not indeg[v]:
                    q.append(v)
        ok = len(order) == len(nodes)
        rels = sum(1 for (wn, ls) in rel if wn in nodes and ls in nodes)
        print(f"{blk:<8} {rels:>3} relations  acyclic={ok}")
        if ok:
            print("         earliest first: " + " < ".join(LAB(i) for i in order))


def report_rules(pixels, label=""):
    print(f"\n=== {label}: {len(pixels)} decisive pixels ===")
    res = []
    for r in SCHEMES + GEOMETRIC:
        ok = sum(1 for win, c in pixels if pick(c, r) == win)
        res.append((ok / max(len(pixels), 1), r, ok))
    print(f"{'rule':<18}{'correct':>10}{'%':>9}")
    for frac, r, ok in sorted(res, reverse=True):
        print(f"{r:<18}{ok:>10}{frac*100:>8.2f}%")
    byblk = defaultdict(list)
    for win, c in pixels:
        byblk["/".join(sorted({EDGES[e[0]][0] for e in c}))].append((win, c))
    print(f"\n{'candidates in':<18}{'n':>8}" +
          "".join(f"{r:>12}" for r in ("opp_abc", "opp_acb", "ours", "nearest_centre")))
    for b in sorted(byblk, key=lambda b: -len(byblk[b])):
        px = byblk[b]
        cells = "".join(
            f"{sum(1 for w,c in px if pick(c,r)==w)/len(px)*100:>11.2f}%"
            for r in ("opp_abc", "opp_acb", "ours", "nearest_centre"))
        print(f"{b:<18}{len(px):>8}{cells}")


def report_extent(golden_dir, lo, hi):
    """Golden minor-axis extent vs cos(theta), on clean non-overlapping cuts."""
    rows = []
    for test, w, g in captures(golden_dir, lo, hi):
        lit = (np.abs(g[:, :, :3] - BG).max(axis=2) > 8) & (g[:, :, 3] == 255)
        mine, theirs, geo = [], [], []
        for e in EDGES:
            (ax, ay), (bx, by) = e[3][0], e[4][0]
            dx, dy = bx - ax, by - ay
            L = float(np.hypot(dx, dy))
            ux, uy = dx / L, dy / L
            along = (PX - ax) * ux + (PY - ay) * uy
            across = (PX - ax) * (-uy) + (PY - ay) * ux
            mine.append((np.abs(across) <= w/2) & (along >= 0) & (along <= L))
            theirs.append((np.abs(across) <= w/2 + CLEAR) &
                          (along >= -CLEAR) & (along <= L + CLEAR))
            xmaj = abs(dx) >= abs(dy)
            geo.append((L, (ax, ay), (ux, uy), xmaj,
                        (abs(dx) if xmaj else abs(dy)) / L))
        for i, e in enumerate(EDGES):
            others = np.zeros_like(mine[i])
            for j in range(len(EDGES)):
                if j != i:
                    others |= theirs[j]
            free = mine[i] & ~others
            if not free.any():
                continue
            L, (ax, ay), (ux, uy), xmaj, cos = geo[i]
            ax_ = 0 if xmaj else 1               # 0: scan columns, 1: scan rows
            lines = np.nonzero(free.any(axis=ax_))[0]
            for line in lines:
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
                if al < w or al > L - w:
                    continue
                v = lit[:, line] if xmaj else lit[line, :]
                if not v[mid]:
                    continue
                a = b = mid
                while a > 0 and v[a-1]: a -= 1
                while b < len(v) - 1 and v[b+1]: b += 1
                if a == 0 or b == len(v) - 1:
                    continue
                rows.append((e[0], e[1], cos, w, b - a + 1))
    if not rows:
        print("no clean samples")
        return
    blk = np.array([r[0] for r in rows])
    k = np.array([r[1] for r in rows])
    cos = np.array([r[2] for r in rows])
    w = np.array([r[3] for r in rows])
    ext = np.array([r[4] for r in rows])
    tan = np.sqrt(np.clip(1 - cos**2, 0, 1)) / cos
    models = {
        "Bresenham      w":          w,
        "perp rect      w/cos":      w / cos,
        "coverage       w/cos+tan+1": w / cos + tan + 1,
        "w/cos^2":                   w / cos**2,
        "w(1+tan)":                  w * (1 + tan),
        "hypot-approx   w(1+tan/2)": w * (1 + tan / 2),
    }
    print(f"{len(rows)} clean samples over {len(set(zip(blk,k)))} edges, "
          f"cos in [{cos.min():.4f}, {cos.max():.4f}]\n")
    print(f"{'model':<28}{'in {floor,ceil}':>16}{'mean resid':>12}")
    for name, L in models.items():
        ok = (ext >= np.floor(L)) & (ext <= np.ceil(L))
        print(f"{name:<28}{ok.mean()*100:>15.2f}%{(ext-L).mean():>12.3f}")
    A, B = w * (1 + tan / 2), w / cos
    for gap in (1.0, 2.0):
        m = (A - B) >= gap
        if not m.any():
            continue
        print(f"\ndecisive subset, the two differ by >= {gap:.0f}px: {m.sum()} samples")
        for name, L in models.items():
            ok = (ext >= np.floor(L)) & (ext <= np.ceil(L))
            print(f"  {name:<28}{ok[m].mean()*100:>8.2f}%")
    print(f"\n{'edge':<14}{'cos':>8}{'n':>6}{'in-band':>9}{'mean resid':>12}")
    ok = (ext >= np.floor(A)) & (ext <= np.ceil(A))
    for key in sorted(set(zip(blk, k)), key=lambda kk: cos[(blk == kk[0]) & (k == kk[1])][0]):
        m = (blk == key[0]) & (k == key[1])
        print(f"{key[0]+'#'+str(key[1]):<14}{cos[m][0]:>8.4f}{m.sum():>6}"
              f"{ok[m].mean()*100:>8.1f}%{(ext-A)[m].mean():>12.3f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", default="goldens/results")
    ap.add_argument("--min-width", type=float, default=8.0)
    ap.add_argument("--max-width", type=float, default=999.0)
    ap.add_argument("--order", action="store_true")
    ap.add_argument("--rules", action="store_true")
    ap.add_argument("--extent", action="store_true")
    ap.add_argument("--extent-rule", action="store_true",
                    help="build candidate footprints with the derived "
                         "hypot-approximation width instead of the "
                         "perpendicular rectangle")
    a = ap.parse_args()
    if not (a.order or a.rules or a.extent):
        ap.error("pick at least one of --order / --rules / --extent")
    if a.extent:
        report_extent(a.goldens, a.min_width, a.max_width)
    if a.order or a.rules:
        px = collect(a.goldens, a.min_width, a.max_width, a.extent_rule)
        if a.order:
            report_order(px)
        if a.rules:
            report_rules(px, f"widths {a.min_width}-{a.max_width}"
                             + (" (derived extent)" if a.extent_rule else ""))


if __name__ == "__main__":
    main()
