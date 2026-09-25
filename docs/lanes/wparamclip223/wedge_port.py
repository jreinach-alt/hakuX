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


def emit_wedge(tri):
    g = [to_clip(v) for v in tri]
    w = np.array([p[3] for p in g], dtype=f)
    neg = w < 0
    if neg.sum() != 1:
        return None
    with np.errstate(all="ignore"):
        q = [np.array([p[0] / p[3], p[1] / p[3]], dtype=f) for p in g]
    if any(not np.all(np.isfinite(x)) for x in q):
        return None
    n = int(np.argmax(neg))
    N, P1, P2 = q[n], q[(n + 1) % 3], q[(n + 2) % 3]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="all")
    args = ap.parse_args()
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
