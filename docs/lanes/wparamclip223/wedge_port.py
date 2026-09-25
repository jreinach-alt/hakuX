#!/usr/bin/env python3
"""A float32 port of emit_wedge() in hw/xbox/nv2a/pgraph/glsl/geom.c, run on
the W_param vertices wedge_price.py regenerates.

For each triangle that takes the new path it checks, against the analytic
wedge of wedge_price.py:

  - coverage: pixel centres inside the emitted strip's triangles vs the model
    mask (centres exactly on an edge are counted, so this scores the union,
    not tie rules);
  - winding: every strip triangle's signed area has the sign of the host
    clipper's polygon (P1, P2, far P2, far P1), i.e. opposite to the screen
    triangle (N, P1, P2);
  - the span of w' over the polygon, and whether the clamp at 2^-64 bit.

Usage: wedge_port.py [--family prog|ff|all]
"""
import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wedge_price as wp  # noqa: E402

f = np.float32
SURF = (640.0, 480.0)


def cross(a, b):
    return f(a[0] * b[1] - a[1] * b[0])


def clip(P, y, bound):
    Q = []
    s = f(math.copysign(1.0, bound))
    for i in range(len(P)):
        j = (i + 1) % len(P)
        da = s * (f(bound) - P[i][1 if y else 0])
        db = s * (f(bound) - P[j][1 if y else 0])
        if da >= 0 and len(Q) < 8:
            Q.append(P[i])
        if ((da < 0) != (db < 0)) and len(Q) < 8:
            t = da / (da - db)
            c = P[i] * (f(1) - t) + P[j] * t
            c = c.copy()
            c[1 if y else 0] = f(bound)
            Q.append(c.astype(f))
    return Q


def to_clip(v):
    """vsh-prog.c / vsh-ff.c: gl_Position = (ndc * w, z, w)."""
    x, y, w = v
    ndc = np.array([(2 * x - SURF[0]) / SURF[0], (2 * y - SURF[1]) / SURF[1]],
                   dtype=f)
    return np.array([ndc[0] * f(w), ndc[1] * f(w), f(0), f(w)], dtype=f)


def grid_area(tri):
    """geom.c's garea: the area on v_vtxPos, the 1/16 px grid (kahan_det is
    exact enough that coincident or collinear grid points give 0)."""
    g = [np.array(v[:2], dtype=np.float64) for v in tri]
    return float((g[1][0] - g[0][0]) * (g[2][1] - g[0][1])
                 - (g[2][0] - g[0][0]) * (g[1][1] - g[0][1]))


# How the GPU divides gl_Position by w: "div" is IEEE float32 division, "rcp"
# is x * (1 / w), which is how many GPUs implement it (GLSL allows 2.5 ulp).
DIVIDE = "div"


def emit_wedge(tri, grid_gate=True):
    g = [to_clip(v) for v in tri]
    w = np.array([p[3] for p in g], dtype=f)
    neg = w < 0
    if neg.sum() != 1:
        return None
    with np.errstate(all="ignore"):
        if DIVIDE == "rcp":
            q = [np.array([p[0] * (f(1) / p[3]), p[1] * (f(1) / p[3])],
                          dtype=f) for p in g]
        else:
            q = [np.array([p[0] / p[3], p[1] / p[3]], dtype=f) for p in g]
    if any(not np.all(np.isfinite(x)) for x in q):
        return None
    n = int(np.argmax(neg))
    N, P1, P2 = q[n], q[(n + 1) % 3], q[(n + 2) % 3]
    if grid_gate and grid_area(tri) == 0:
        return None
    area = cross(q[1] - q[0], q[2] - q[0])
    if not (abs(area) > 0) or not np.isfinite(area):
        return None
    mu = f(1)
    for c in range(4):
        k = np.array([-1.0 if (c & 1) == 0 else 1.0, -1.0 if c < 2 else 1.0], dtype=f)
        mu = max(mu, f(1) - cross(P1 - k, P2 - k) / area)
    K = f(2) * mu
    P = [P1, N + K * (P1 - N), N + K * (P2 - N), P2]
    for bound, y in ((1.0, False), (-1.0, False), (1.0, True), (-1.0, True)):
        P = clip(P, y, bound)
    S, A = [], []
    for p in P:
        lam = np.array([cross(q[1] - p, q[2] - p), cross(q[2] - p, q[0] - p),
                        cross(q[0] - p, q[1] - p)], dtype=f) / area
        with np.errstate(all="ignore"):
            al = np.maximum(lam / w, 0).astype(f)
        s = f(al.sum())
        if not (s > 0) or not np.isfinite(s):
            return None
        S.append(s)
        A.append(al / s)
    if not P:
        return {"strip": [], "W": [], "screen_area": area}
    smin = min(S)
    Ws = [max(smin / s, f(2.0 ** -64)) for s in S]
    order = [(k >> 1) if (k & 1) == 0 else (len(P) - 1 - (k >> 1))
             for k in range(len(P))]
    strip = [(P[j], Ws[j]) for j in order]
    return {"strip": strip, "W": Ws, "S": S, "screen_area": area,
            "clamped": sum(1 for s in S if smin / s < 2.0 ** -64)}


def raster(strip):
    """Pixel centres covered by the strip's triangles (closed)."""
    H, W = wp.H, wp.W
    yy, xx = np.mgrid[0:H, 0:W]
    cx = (xx + 0.5) * 2 / SURF[0] - 1
    cy = (yy + 0.5) * 2 / SURF[1] - 1
    m = np.zeros((H, W), dtype=bool)
    signs = []
    for t in range(len(strip) - 2):
        a, b, c = strip[t][0], strip[t + 1][0], strip[t + 2][0]
        if t & 1:
            a, b = b, a
        ar = float(cross(b - a, c - a))
        if ar == 0:
            continue
        signs.append(math.copysign(1, ar))
        e = [((b[0] - a[0]) * (cy - a[1]) - (b[1] - a[1]) * (cx - a[0])),
             ((c[0] - b[0]) * (cy - b[1]) - (c[1] - b[1]) * (cx - b[0])),
             ((a[0] - c[0]) * (cy - c[1]) - (a[1] - c[1]) * (cx - c[0]))]
        tol = 1e-6
        if ar > 0:
            m |= (e[0] >= -tol) & (e[1] >= -tol) & (e[2] >= -tol)
        else:
            m |= (e[0] <= tol) & (e[1] <= tol) & (e[2] <= tol)
    return m, signs


def gaps_triangles():
    """w_param_tests.cpp:149-230 (CreateGeometryWGaps) on a 640x480 surface,
    through the passthrough program and vsh-prog.c: roundScreenCoords, then
    clampAwayZeroInf.  Returns (label, triangle) for the strip and for the
    translated triangle list."""
    left, top = math.floor(640 / 5.0), math.floor(480 / 6.0)
    bottom = top + (480 - top * 2.0)
    width = (left + (640 - left * 2.0)) - left
    mid = top + (bottom - top) * 0.5 - 4
    inc = f(width / 14.0)
    INF = math.inf
    v, x = [], f(left)

    def add(xx, yy, w):
        v.append((f(xx), f(yy), w))

    def visible():
        nonlocal x
        add(x, mid, INF)
        add(x, top, INF)
        x = f(x + inc)
        add(x, mid, INF)
        add(x, top, INF)

    visible()
    for wt, wm in ((0.0, 0.0), (0.9, 0.0), (10.9, 0.0), (-0.9, 0.0),
                   (-10.9, 10.0), (INF, INF)):
        add(x, top, wt)
        x = f(x + inc)
        add(x, mid, wm)
        visible()

    def vsh(p, dx=0.0, dy=0.0):
        sx = math.trunc(float(f(p[0] + dx)) * 16) / 16.0
        sy = math.trunc(float(f(p[1] + dy)) * 16) / 16.0
        w = float(np.clip(f(p[2]), 2.0 ** -64, 2.0 ** 64)) if p[2] >= 0 \
            else float(np.clip(f(p[2]), -2.0 ** 64, -2.0 ** -64))
        return (sx, sy, w)

    out = []
    for i in range(len(v) - 2):
        out.append(("strip%d" % i, [vsh(p) for p in v[i:i + 3]]))
        out.append(("tris%d" % i, [vsh(p, -6.0, 6.0 + (bottom - top) * 0.5)
                                   for p in v[i:i + 3]]))
    return out


def gaps_main():
    """Every one-negative triangle of w_gaps: the old test (area on q) and
    geom.c's grid test.  Silicon draws none of them (the golden)."""
    global DIVIDE
    print("divide\ttri\tgrid_area\tq_gate\tgrid_gate\tq_wedge_px")
    for DIVIDE in ("div", "rcp"):
        for label, tri in gaps_triangles():
            if sum(1 for p in tri if p[2] < 0) != 1:
                continue
            old = emit_wedge(tri, grid_gate=False)
            new = emit_wedge(tri, grid_gate=True)
            px = int(raster(old["strip"])[0].sum()) if old else 0
            print("%s\t%s\t%g\t%s\t%s\t%d" % (
                DIVIDE, label, grid_area(tri), "WEDGE" if old else "-",
                "WEDGE" if new else "-", px))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="all")
    ap.add_argument("--gaps", action="store_true",
                    help="run w_gaps' one-negative triangles instead")
    args = ap.parse_args()
    if args.gaps:
        return gaps_main()
    fams = ["prog", "ff"] if args.family == "all" else [args.family]
    print("capture\ttri\tnverts\tcover_xor_model\twinding_ok\tW_span_log2\tclamped")
    for fam in fams:
        for quad in (False, True):
            for label, m in wp.MULTIPLIERS:
                name = "%s_w_zero_inf__%s_w%s" % (fam, "quad" if quad else "bitri", label)
                for ti, tri in enumerate(wp.triangles(fam, quad, m)):
                    cls = wp.classify(tri)
                    r = emit_wedge(tri)
                    if cls != "WEDGE" and r is None:
                        continue
                    if (cls == "WEDGE") != (r is not None):
                        print("%s\ttri%d\tCLASS MISMATCH model=%s port=%s" % (
                            name, ti + 1, cls, r is not None))
                        continue
                    mask, signs = raster(r["strip"])
                    model = wp.wedge_mask(tri)
                    xor = int((mask ^ model).sum())
                    want = -math.copysign(1, float(r["screen_area"]))
                    # y is flipped between NDC here and framebuffer rows, but
                    # both areas are measured in the same NDC frame.
                    ok = all(s == want for s in signs)
                    span = (math.log2(max(r["W"]) / min(r["W"]))
                            if r["W"] else 0.0)
                    print("%s\ttri%d\t%d\t%d\t%s\t%.1f\t%d" % (
                        name, ti + 1, len(r["strip"]), xor, ok, span,
                        r.get("clamped", 0)))


if __name__ == "__main__":
    main()
