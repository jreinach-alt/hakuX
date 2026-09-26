#!/usr/bin/env python3
"""Reproduce every number in the "GL aliased wide lines are axis-offset copies"
section of docs/investigations/line-width-first-gl-baseline.md.

Our wide lines come from glLineWidth (gl/draw.c:394; glsl/geom.c emits
line_strip, so nothing expands them into geometry on our side). The GL
specification defines a non-antialiased wide line as the width-1 line replicated
with an integer offset along the MINOR screen axis. The Xbox hardware draws a
true perpendicular-width line. Two consequences, both measured here:

  perpendicular thickness   = W * max(|cos t|, |sin t|)      (exact)
  cross-width colour spread = grad * W * min(|cos t|, |sin t|)  (directional)

Segment geometry is taken from the test's own source rather than eyeballed from
the image -- nxdk_pgraph_tests/src/tests/line_width_tests.cpp, offset by
(640*0.25, 480*0.10) = (160, 48).

Usage:  line_width_axis_offset.py <ours_dir> <goldens_dir>

  ours_dir     holds "Line_width::Line_0032.0.png" etc.
  goldens_dir  holds "Line_width/Line_0032.0.png" etc.
"""
import math
import os
import statistics as st
import sys

from PIL import Image

BG = (32, 34, 36)
OX, OY = 640 * 0.25, 480 * 0.10
WIDTHS = [8, 16, 32, 48]

# --- the test's own geometry, verbatim from line_width_tests.cpp -------------
LINE_LOOP = [(196, 47), (194, 19), (182, 97), (106.18625, 80), (127, 94.58163),
             (133.597443, 13.763389), (205, 62), (115.54392, 16), (122, 3),
             (117.062706, 87.735558), (201, 28.664894), (146.114091, 10),
             (205.356591, 88), (125, 107), (190.828953, 35.510304), (163, 105.956814)]
TRIANGLES = [(265.185925, 35), (249.778838, 22.523717), (310, 19),
             (243.978231, 47.650185), (304, 37), (232, 102.522615)]
QUAD_STRIP = [(0, 239), (0, 120), (52.5, 225.4), (54.75, 175.5), (105, 239), (105, 120)]
TRIANGLE_FAN = [(158.5, 205), (115.545455, 239), (120.318182, 120), (147.045455, 157.4),
                (158.5, 128.5), (166.136364, 145.5), (204.318182, 159.1), (209.75, 239)]
POLYGON = [(218, 232), (237.772727, 142.1), (258.772727, 120), (302.681818, 169.3), (317, 230.5)]
QUADS = [(0, 350), (60, 340), (58.5, 425.4), (12.75, 407.5)]


def _build_segments():
    """Every edge the test draws, in screen space. Polygon mode is LINE, so
    filled primitives contribute their outlines."""
    segs = []

    def add(prim, pts, pairs):
        for i, j in pairs:
            segs.append((prim, (pts[i][0] + OX, pts[i][1] + OY),
                         (pts[j][0] + OX, pts[j][1] + OY)))

    n = len(LINE_LOOP)
    add('LINE_LOOP', LINE_LOOP, [(i, (i + 1) % n) for i in range(n)])
    for t in range(len(TRIANGLES) // 3):
        b = 3 * t
        add('TRIANGLES', TRIANGLES, [(b, b + 1), (b + 1, b + 2), (b + 2, b)])
    for q in range(len(QUAD_STRIP) // 2 - 1):
        b = 2 * q
        add('QUAD_STRIP', QUAD_STRIP, [(b, b + 1), (b + 1, b + 3), (b + 3, b + 2), (b + 2, b)])
    for t in range(len(TRIANGLE_FAN) - 2):
        add('TRIANGLE_FAN', TRIANGLE_FAN, [(0, t + 1), (t + 1, t + 2), (t + 2, 0)])
    n = len(POLYGON)
    add('POLYGON', POLYGON, [(i, (i + 1) % n) for i in range(n)])
    n = len(QUADS)
    add('QUADS', QUADS, [(i, (i + 1) % n) for i in range(n)])
    return segs


SEGS = _build_segments()


def _is_bg(p):
    return all(abs(p[i] - BG[i]) <= 2 for i in range(3))


def _point_to_segment(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    if l2 == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / l2))
    return math.hypot(p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy))


def _clearance(p, skip):
    """Distance to every other segment -- ADJACENT EDGES INCLUDED. Excluding
    them is what let a contaminated sample through in d913c9dd: near a
    segment's ends the adjacent edge is well inside W/2."""
    return min(_point_to_segment(p, o[1], o[2])
               for j, o in enumerate(SEGS) if j != skip)


def _walk(px, size, c, n, limit):
    """Perpendicular run through the line, stopping at background."""
    w, h = size
    out = {}
    for sgn in (1, -1):
        bgrun = 0
        for k in range(limit + 1):
            x, y = int(round(c[0] + sgn * k * n[0])), int(round(c[1] + sgn * k * n[1]))
            if not (0 <= x < w and 0 <= y < h):
                break
            p = px[x, y]
            if _is_bg(p):
                bgrun += 1
                if bgrun >= 2:
                    break
            else:
                bgrun = 0
                out[sgn * k] = p
    if 0 not in out:
        return {}
    lo = hi = 0
    while lo - 1 in out:
        lo -= 1
    while hi + 1 in out:
        hi += 1
    return {k: out[k] for k in range(lo, hi + 1)}


def _samples(ours_dir, goldens_dir, width):
    tag = '%04d.0' % width
    o_img = Image.open(os.path.join(ours_dir, 'Line_width::Line_%s.png' % tag)).convert('RGB')
    g_img = Image.open(os.path.join(goldens_dir, 'Line_width', 'Line_%s.png' % tag)).convert('RGB')
    po, pg, size = o_img.load(), g_img.load(), o_img.size
    need = width / 2.0 + 4
    limit = int(width * 1.5) + 8

    for i, (prim, a, b) in enumerate(SEGS):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < width * 1.2:
            continue
        d = (dx / length, dy / length)
        n = (-d[1], d[0])
        theta = math.degrees(math.atan2(dy, dx)) % 180.0
        hi, lo = max(abs(d[0]), abs(d[1])), min(abs(d[0]), abs(d[1]))
        for si in range(3, 8):
            s = si / 10.0
            c = (a[0] + s * dx, a[1] + s * dy)
            if min(s, 1 - s) * length < need:
                continue
            if _clearance(c, i) < need:
                continue
            ro, rg = _walk(po, size, c, n, limit), _walk(pg, size, c, n, limit)
            if not ro or not rg:
                continue
            # The golden is the control: it has no angle dependence, so a
            # golden run far from W means the walk met something that is not
            # this line and the sample is discarded rather than interpreted.
            if abs(len(rg) - width) > width * 0.5:
                continue
            yield dict(theta=theta, prim=prim, hi=hi, lo=lo, w=width, d=d, n=n, c=c,
                       size=size, po=po, pg=pg, limit=limit,
                       ours=ro, gold=rg)


def thickness(ours_dir, goldens_dir):
    cells, rows, hi_of = {}, [], []
    for w in WIDTHS:
        for s in _samples(ours_dir, goldens_dir, w):
            key = (round(s['theta'], 1), s['prim'], round(s['hi'], 3))
            cells.setdefault(key, []).append((len(s['ours']) / w, len(s['gold']) / w))
            rows.append((len(s['ours']) / w - s['hi'], len(s['gold']) / w))
            hi_of.append(s['hi'])

    print('| angle | from axis | primitive | max(|cos|,|sin|) | ours / W | golden / W | n |')
    print('|---:|---:|---|---:|---:|---:|---:|')
    for (theta, prim, hi), v in sorted(cells.items(), key=lambda kv: kv[0][2]):
        if len(v) < 3:
            continue
        off = min(theta % 90, 90 - (theta % 90))
        print('| %.1f | %.1f | %s | %.3f | **%.3f** | %.3f | %d |'
              % (theta, off, prim, hi, st.median(x for x, _ in v),
                 st.median(y for _, y in v), len(v)))

    err = [e for e, _ in rows]
    gold = [g for _, g in rows]
    ours = [e + h for (e, _), h in zip(rows, hi_of)]

    # Per-cell: one entry per (angle, primitive, width), which is what the
    # table rows above are. Per-sample: every accepted walk. Both are reported
    # because they answer different questions and differ by a factor of ~1.6
    # in scatter -- quoting only the tighter one would be picking a number.
    cell_err = []
    for (theta, prim, hi), v in cells.items():
        cell_err.append(st.median(x for x, _ in v) - hi)

    print('\nper-cell   N=%3d  mean(ours/W - max(|cos|,|sin|)) = %+.4f  sd %.4f  max|err| %.3f'
          % (len(cell_err), sum(cell_err) / len(cell_err), st.pstdev(cell_err),
             max(abs(x) for x in cell_err)))
    print('per-sample N=%3d  mean(ours/W - max(|cos|,|sin|)) = %+.4f  sd %.4f  max|err| %.3f'
          % (len(err), sum(err) / len(err), st.pstdev(err), max(abs(x) for x in err)))
    print('golden/W: mean %.4f  sd %.4f  range %.3f..%.3f'
          % (sum(gold) / len(gold), st.pstdev(gold), min(gold), max(gold)))
    for k in (1.00, 0.90):
        e2 = [o - k for o in ours]
        print('null model ours/W = %.2f constant: sd %.4f  max|err| %.3f'
              % (k, st.pstdev(e2), max(abs(x) for x in e2)))


def _centre_colour(px, size, c, n, limit):
    r = _walk(px, size, c, n, limit)
    if not r:
        return None
    ks = sorted(r)
    return r[ks[len(ks) // 2]]


def shear(ours_dir, goldens_dir):
    raw = []
    for w in WIDTHS:
        for s in _samples(ours_dir, goldens_dir, w):
            d, c, n = s['d'], s['c'], s['n']
            g1 = _centre_colour(s['pg'], s['size'], (c[0] - 6 * d[0], c[1] - 6 * d[1]), n, s['limit'])
            g2 = _centre_colour(s['pg'], s['size'], (c[0] + 6 * d[0], c[1] + 6 * d[1]), n, s['limit'])
            if g1 is None or g2 is None:
                continue
            grad = [abs(g2[k] - g1[k]) / 12.0 for k in range(3)]
            ch = max(range(3), key=lambda k: grad[k])
            if grad[ch] < 0.5:
                continue
            vo = [v[ch] for v in s['ours'].values()]
            vg = [v[ch] for v in s['gold'].values()]
            raw.append(dict(theta=round(s['theta'], 1), prim=s['prim'], w=w, lo=s['lo'],
                            grad=grad[ch], ours=max(vo) - min(vo), gold=max(vg) - min(vg)))

    # A +/-6px probe that crosses a vertex sees a colour discontinuity and
    # reports a gradient several times too large. Take the per-segment median
    # and drop the samples that disagree with it.
    med = {}
    for r in raw:
        med.setdefault((r['theta'], r['prim']), []).append(r['grad'])
    med = {k: st.median(v) for k, v in med.items()}
    keep = [r for r in raw
            if med[(r['theta'], r['prim'])] > 0
            and abs(r['grad'] - med[(r['theta'], r['prim'])]) / med[(r['theta'], r['prim'])] <= 0.25]

    ratios = []
    for r in keep:
        pred = med[(r['theta'], r['prim'])] * r['w'] * r['lo']
        if pred > 2:
            ratios.append(r['ours'] / pred)
    axis = [r for r in keep if r['lo'] < 0.05]
    diag = [r for r in keep if r['lo'] > 0.60]

    print('\n%d shear samples, %d dropped as vertex-crossing gradient estimates'
          % (len(raw), len(raw) - len(keep)))
    print('axis-aligned (min<0.05)  n=%3d  ours mean %.2f max %d | golden mean %.2f max %d'
          % (len(axis), sum(r['ours'] for r in axis) / len(axis), max(r['ours'] for r in axis),
             sum(r['gold'] for r in axis) / len(axis), max(r['gold'] for r in axis)))
    print('near 45 deg  (min>0.60)  n=%3d  ours mean %.2f max %d | golden mean %.2f max %d'
          % (len(diag), sum(r['ours'] for r in diag) / len(diag), max(r['ours'] for r in diag),
             sum(r['gold'] for r in diag) / len(diag), max(r['gold'] for r in diag)))
    print('observed / predicted where predicted > 2:  mean %.3f  sd %.3f  n=%d'
          % (sum(ratios) / len(ratios), st.pstdev(ratios), len(ratios)))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    thickness(sys.argv[1], sys.argv[2])
    shear(sys.argv[1], sys.argv[2])
