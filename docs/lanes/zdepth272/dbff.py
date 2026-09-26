"""Replay Depth_buffer_fixed_function z24 FZn frames under a vertex-depth model.

The XDK composite's z and w columns have no x/y terms, so a vertex's screen z
depends only on its float32 world z.  Every vertex snaps (trunc(x*16)/16 of
v + 0.53125) onto a pixel-centre half-integer, so a quad of span n px samples
its depth at t = k/n exactly.  Depth is screen-linear between the two vertex
depths of each quad (the quads are planar: both left vertices share a z, both
right/top/bottom ones share the other).
"""
import math
import os
import sys
from fractions import Fraction as F

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from model import vertex_z  # noqa: E402

f32 = np.float32
W, H = 640, 480
GOLD = "/home/justin/goldens/results/Depth_buffer_fixed_function"


def zeta_word(path):
    a = np.array(Image.open(path).convert("RGBA"), dtype=np.int64)
    return (a[:, :, 3] << 16) | (a[:, :, 0] << 8) | a[:, :, 1]


def primitives():
    """[(kind, x0, x1, y0, y1, z_a, z_b, span)] in draw order.

    kind 'x': depth goes z_a at x0 -> z_b at x0+span, constant in y.
    kind 'y': the same along y.  Pixel ranges are half-open.
    """
    out = []
    kZNear, kZFar = f32(-6.0), f32(193.0)
    qpr = qpc = 18
    num_quads = 3 + qpr * qpc
    z_inc = f32(f32(kZFar - kZNear) / f32(f32(num_quads) + f32(1.0)))
    z_left = kZNear
    right_offset = f32(z_inc * f32(0.75))
    for j in range(qpc):
        for i in range(qpr):
            z_right = f32(z_left + right_offset)
            x0, y0 = 136 + 20 * i, 56 + 20 * j
            out.append(('x', x0, x0 + 16, y0, y0 + 16, z_left, z_right, 16))
            z_left = f32(z_left + z_inc)
            right_offset = f32(-right_offset)
    # bottom quad: kLeft+4=132 .. kRight-20=492, y kBottom-10=422 .. 427
    out.append(('x', 132, 492, 422, 427, f32(kZFar * f32(0.75)), kZNear, 360))
    # right quad: x kRight-10=502 .. 510, y kTop+5=53 .. kBottom-5=427
    out.append(('y', 502, 510, 53, 427, kZNear, f32(kZFar * f32(0.5)), 374))
    # big quad: 128..512, 48..432
    top = f32(f32(kZFar * f32(2.0)) / f32(3.0))
    out.append(('y', 128, 512, 48, 432, top, kZFar, 384))
    return out


_cache = {}


def vz(z, m):
    key = (float(z), tuple(sorted(m.items())))
    if key not in _cache:
        _cache[key] = vertex_z(F(float(z)), m)
    return _cache[key]


def render(m, cutoff, prims=None, tag=False):
    """floor depth after LESS in draw order; optional primitive-id map."""
    prims = prims or primitives()
    z = np.full((H, W), cutoff, dtype=np.int64)
    pid = np.full((H, W), -1, dtype=np.int64)
    for n, (kind, x0, x1, y0, y1, za, zb, span) in enumerate(prims):
        a, b = vz(za, m), vz(zb, m)
        if kind == 'x':
            k = np.arange(x1 - x0)
        else:
            k = np.arange(y1 - y0)
        # exact floor of a + (b-a)*k/span, clamped at 0 (depth clip 0..2^24)
        num = [a + (b - a) * F(int(kk), span) for kk in k]
        v = np.array([max(0, math.floor(q)) for q in num], dtype=np.int64)
        if kind == 'x':
            v2 = np.broadcast_to(v[None, :], (y1 - y0, x1 - x0))
        else:
            v2 = np.broadcast_to(v[:, None], (y1 - y0, x1 - x0))
        sub = z[y0:y1, x0:x1]
        msk = v2 < sub
        sub[msk] = v2[msk]
        pid[y0:y1, x0:x1][msk] = n
    return (z, pid) if tag else z


OURS = dict(mul='rne', add='rne', fin='rne', div='div')


def label_mask(g, o):
    """True where a pixel is usable: outside the text label."""
    m = np.ones((H, W), bool)
    m[:120, :] = True
    return m


if __name__ == "__main__":
    run = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else "z24_Cn_FZn_Mffffff_ZB"
    cutoff = int(name.split("_M")[1].split("_")[0], 16)
    g = zeta_word(os.path.join(GOLD, name + ".png"))
    o = zeta_word(os.path.join(run, "captures1", "Depth_buffer_fixed_function::%s.png" % name))
    ours_model, pid = render(OURS, cutoff, tag=True)
    d = o - ours_model
    print("ours capture - ours model: exact %d / %d; hist %s" % (
        (d == 0).sum(), d.size, np.unique(np.clip(d, -5, 5), return_counts=True)))
    ys, xs = np.nonzero(np.abs(d) > 5)
    print("big-diff pixel bbox", ys.min() if len(ys) else None, ys.max() if len(ys) else None,
          xs.min() if len(xs) else None, xs.max() if len(xs) else None, len(ys))
