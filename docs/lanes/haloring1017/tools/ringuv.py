"""Texture u per radian of ring angle, per ring draw (#939, symptom (c)).

usage: ringuv.py RAM.bin AXIS_DRAW NAME:ADDR:NVERT [NAME:ADDR:NVERT ...]

The menu ring turns by scrolling c13.w (oT0.x = c13.x*u + c13.y*v + c13.w),
not by moving geometry. Two draws turn together only when their scroll
rates are the same in radians: d(c13.w)/dt / (c13.x * du/dtheta) must agree.
constmove.py gives d(c13.w)/dt per draw; this gives du/dtheta, from the
vertex records in a guest RAM image (32-byte records: position f32x3 at 0,
texcoord S1x2 at 24, the format every ring draw's vr reports).

The ring axis is the smallest-variance direction of AXIS_DRAW's positions
(the hull, a band much wider in radius than in height). theta is the angle
about that axis through the band's centroid. du/dtheta is the median over
nearest-neighbour vertex pairs whose angle differs by a usable amount, so
a texture seam (u jumps) is outvoted, not averaged in.
"""
import struct
import sys

import numpy as np

STRIDE = 32


def records(ram, addr, n):
    pos = np.zeros((n, 3))
    uv = np.zeros((n, 2))
    for i in range(n):
        o = addr + i * STRIDE
        pos[i] = struct.unpack_from("<3f", ram, o)
        s, t = struct.unpack_from("<2h", ram, o + 24)
        uv[i] = ((2 * s + 1) / 65535.0, (2 * t + 1) / 65535.0)
    return pos, uv


def axis_of(pos):
    c = pos.mean(axis=0)
    w, v = np.linalg.eigh(np.cov((pos - c).T))
    return c, v[:, 0], w


def angles(pos, c, ax):
    a = np.cross(ax, [1.0, 0.0, 0.0])
    if np.linalg.norm(a) < 0.1:
        a = np.cross(ax, [0.0, 1.0, 0.0])
    a /= np.linalg.norm(a)
    b = np.cross(ax, a)
    d = pos - c
    h = d @ ax
    r = np.linalg.norm(d - np.outer(h, ax), axis=1)
    return np.arctan2(d @ b, d @ a), r, h


ram = open(sys.argv[1], "rb").read()
draws = []
for spec in sys.argv[3:]:
    name, addr, n = spec.split(":")
    draws.append((name, int(addr, 16), int(n)))
names = [d[0] for d in draws]
axis_name = sys.argv[2]
pos0, _ = records(ram, *[d[1:] for d in draws if d[0] == axis_name][0])
c, ax, w = axis_of(pos0)
print(f"axis from {axis_name}: centre {np.round(c, 4)} axis {np.round(ax, 4)} eig {np.round(w, 5)}")

for name, addr, n in draws:
    pos, uv = records(ram, addr, n)
    th, r, h = angles(pos, c, ax)
    # nearest neighbours (brute force; a few hundred vertices)
    d2 = ((pos[:, None, :] - pos[None, :, :]) ** 2).sum(-1)
    np.fill_diagonal(d2, np.inf)
    rates_u, rates_v = [], []
    for i in range(n):
        for j in np.argsort(d2[i])[:6]:
            dth = (th[j] - th[i] + np.pi) % (2 * np.pi) - np.pi
            if abs(dth) < 1e-3:
                continue
            rates_u.append((uv[j, 0] - uv[i, 0]) / dth)
            rates_v.append((uv[j, 1] - uv[i, 1]) / dth)
    ru, rv = np.array(rates_u), np.array(rates_v)
    med_u, med_v = np.median(ru), np.median(rv)
    agree = np.mean(np.abs(ru - med_u) < 0.1 * max(abs(med_u), 1e-9)) if len(ru) else 0
    span = np.ptp(np.unwrap(np.sort(th)))
    print(f"{name}: {n} verts  r {r.min():.4f}..{r.max():.4f}  h {h.min():+.4f}..{h.max():+.4f}"
          f"  theta span {np.degrees(span):.1f} deg  u {uv[:, 0].min():+.4f}..{uv[:, 0].max():+.4f}"
          f"  v {uv[:, 1].min():+.4f}..{uv[:, 1].max():+.4f}")
    print(f"   du/dtheta median {med_u:+.6f} per rad ({len(ru)} pairs, {100 * agree:.0f}% within 10%)"
          f"  dv/dtheta median {med_v:+.6f}")
