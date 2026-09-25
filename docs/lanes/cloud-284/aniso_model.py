#!/usr/bin/env python3
"""#284: offline model of NV2A anisotropic filtering on Texture_anisotropy.

texture_anisotropy_tests.cpp draws one textured quad, FF path under
SetXDKDefaultViewportAndFixedFunctionMatrices (camera (0,0,-7) looking at the
origin, fovY pi/4, aspect 4/3), plane y = -1.5 from z = 200 (v = 0) to z = 0
(v = 32), x in [-4, 4] (u 0..1). Texture 128x128 A8R8G8B8 swizzled checker,
4-texel boxes, 0xFFFFFF00 / 0xFF663333, WRAP both axes. The stage keeps
TextureStage::Reset()'s filter word 0x1012000: MIN = MAG = BOX_LOD0 (point),
one mip level. So every isotropic pixel is one of two colours and an
anisotropic pixel is a mix, whose weight w (share of yellow) reads straight
off the golden: w = (R - 102) / 153.

Usage:
  aniso_model.py [--goldens DIR] [--capture DIR ...] [--sweep]

Prints, per level, differing pixels in rows 245..364 (any channel differs)
for each --capture dir and for the model, with the |d| = 1 / 2..8 / >8
split. --sweep also scores every model variant (NOTES.md, "what was tried").
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image

GOLDENS = '/home/justin/goldens/results'
SUITE = 'Texture_anisotropy'
W, H = 640, 480
YS = 1.0 / math.tan(math.pi / 8)       # fovY pi/4
ASPECT = W / H
CAM_Z = -7.0
PLANE_Y = -1.5
TEX = 128
BOX = 4
VREP = 32.0
YELLOW = np.array([255, 255, 0], float)
BROWN = np.array([102, 51, 51], float)
ROWS = slice(245, 365)                  # the plane, the region the brief names
VOFF = 0.53125                          # SetXDKDefaultViewport...: viewport offset


def golden(level, root=GOLDENS):
    return np.asarray(Image.open(os.path.join(root, SUITE, f'Anisotropy-{level}.png')).convert('RGB')).astype(int)


VERTS = [(-4.0, 200.0, 0.0, 0.0), (4.0, 200.0, 1.0, 0.0),
         (4.0, 0.0, 1.0, VREP), (-4.0, 0.0, 0.0, VREP)]   # (x, z, u, v), draw order


def project(x, y, z, xscale=None):
    """World -> (screen x, screen y, w) through LookAtLH and the D3D
    perspective-fov viewport, vertices snapped to the 1/16 grid."""
    ze = z - CAM_Z
    xs = YS / ASPECT if xscale is None else xscale
    sx = W / 2 + (W / 2) * xs * x / ze + VOFF
    sy = H / 2 - (H / 2) * YS * y / ze + VOFF
    snap = lambda a: np.floor(a * 16.0) / 16.0
    return snap(sx), snap(sy), ze


def raster(ox=0.0, oy=0.0, xscale=None):
    """Perspective-correct (s, t) per pixel sample point, plus coverage, for
    the quad as two triangles v0 v1 v2 and v0 v2 v3. Top-left fill rule is
    approximated by a half-open inside test."""
    P = [project(x, PLANE_Y, z, xscale) + (u, v) for x, z, u, v in VERTS]
    px, py = grid(ox, oy)
    S = np.full((H, W), np.nan)
    T = np.full((H, W), np.nan)
    ZE = np.full((H, W), np.nan)
    for tri in ((0, 1, 2), (0, 2, 3)):
        (x0, y0, w0, u0, v0), (x1, y1, w1, u1, v1), (x2, y2, w2, u2, v2) = (P[i] for i in tri)
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        e0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / area
        e1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / area
        e2 = 1.0 - e0 - e1
        inside = (e0 >= 0) & (e1 >= 0) & (e2 >= 0) & np.isnan(S)
        iw = e0 / w0 + e1 / w1 + e2 / w2
        s = (e0 * u0 / w0 + e1 * u1 / w1 + e2 * u2 / w2) / iw
        t = (e0 * v0 / w0 + e1 * v1 / w1 + e2 * v2 / w2) / iw
        S = np.where(inside, s * TEX, S)
        T = np.where(inside, t * TEX, T)
        ZE = np.where(inside, 1.0 / iw, ZE)
    return S, T, ZE


def checker(s, t, parity=0):
    """1.0 where the point sample is yellow."""
    c = (np.floor(s / BOX).astype(np.int64) + np.floor(t / BOX).astype(np.int64) + parity) & 1
    return (c == 0).astype(float)


def grid(ox, oy):
    y, x = np.mgrid[0:H, 0:W].astype(float)
    return x + ox, y + oy


def to_rgb(w):
    """Round-half-up blend of the two texel colours, per channel."""
    return np.floor(BROWN + (YELLOW - BROWN) * w[..., None] + 0.5).astype(int)


def score(pred_rgb, gold, valid):
    pred_rgb = np.where(valid[..., None], pred_rgb, 32)       # 0xFE202020 clear
    d = np.abs(pred_rgb - gold).max(-1)
    region = np.zeros_like(valid)
    region[ROWS] = True
    d = np.where(region, d, 0)
    return int((d > 0).sum()), int(d.max())


# ---------------------------------------------------------------------------
# models

# The sample point that makes Anisotropy-1 agree (141 px, all checker-edge
# ties): pixel centre at +0.5 after the 0.53125 viewport offset.
OX = OY = 0.5


def model_iso(ox=OX, oy=OY, parity=0, xscale=None):
    s, t, z = raster(ox, oy, xscale)
    v = np.isfinite(s)
    return checker(np.nan_to_num(s), np.nan_to_num(t), parity), v


def jacobian(deriv='central'):
    """(s, t) at the sample point and d(s,t)/dx, d(s,t)/dy in texels/pixel.

    central: analytic-equivalent central difference at the pixel.
    quad:    what a GPU's fragment derivatives give -- one forward difference
             per 2x2 quad, shared by its four pixels.
    """
    S, T, _ = raster(OX, OY)
    if deriv == 'central':
        h = 0.25
        sx1, tx1, _ = raster(OX + h, OY); sx0, tx0, _ = raster(OX - h, OY)
        sy1, ty1, _ = raster(OX, OY + h); sy0, ty0, _ = raster(OX, OY - h)
        return S, T, (sx1 - sx0) / (2 * h), (tx1 - tx0) / (2 * h), (sy1 - sy0) / (2 * h), (ty1 - ty0) / (2 * h)
    ev = lambda a: np.repeat(np.repeat(a[0::2, 0::2], 2, 0), 2, 1)
    dsx = ev(np.pad(S[:, 1:] - S[:, :-1], ((0, 0), (0, 1)), mode='edge'))
    dtx = ev(np.pad(T[:, 1:] - T[:, :-1], ((0, 0), (0, 1)), mode='edge'))
    dsy = ev(np.pad(S[1:] - S[:-1], ((0, 1), (0, 0)), mode='edge'))
    dty = ev(np.pad(T[1:] - T[:-1], ((0, 1), (0, 0)), mode='edge'))
    return S, T, dsx, dtx, dsy, dty


def probes(nf, spacing, rule):
    """Offsets (in units of `spacing`, along the major axis) and weights.

    nf is the fractional probe count Pmaj / Pmin_eff, in [1, L].
      'even-frac': 2*floor(nf/2) full probes at +-(k+1/2), the remainder split
                   as a fractional outer pair; below 2 the pair closes in to
                   +-(nf-1)/2 so that nf = 1 is one probe.
      'ceil-even': ceil(nf) probes, equal weight, evenly over (nf-1)*spacing.
      'round':     round(nf) probes, equal weight, evenly over (nf-1)*spacing.
    Returns a list of (offset_array, weight_array) with weights summing to 1.
    """
    out = []
    if rule == 'even-frac':
        full = 2 * np.floor(nf / 2)
        frac = nf - full
        small = nf < 2
        # below two probes: a pair at +-(nf-1)/2, equal weights
        d = (nf - 1) / 2
        out.append((np.where(small, -d, -0.5), np.where(small, 0.5, 1 / nf)))
        out.append((np.where(small, d, 0.5), np.where(small, 0.5, 1 / nf)))
        for k in range(1, 4):  # up to 8 full probes
            have = (full >= 2 * (k + 1)) & ~small
            for sgn in (-1, 1):
                out.append((np.full_like(nf, sgn * (k + 0.5)), np.where(have, 1 / nf, 0.0)))
        for sgn in (-1, 1):
            out.append((sgn * (full / 2 + 0.5), np.where(small, 0.0, frac / 2 / nf)))
        return out
    n = np.ceil(nf - 1e-9) if rule == 'ceil-even' else np.maximum(np.round(nf), 1)
    for i in range(8):
        have = i < n
        pos = np.where(n > 1, (i / np.maximum(n - 1, 1) - 0.5) * (nf - 1), 0.0)
        out.append((pos, np.where(have, 1 / n, 0.0)))
    return out


def model_aniso(L, rule='even-frac', deriv='central', pmin_floor=1.0, clamp='raise-pmin', parity=0, kmaj=1.0,
                wbits=0, wround=np.round):
    """Render the weight (yellow share) under a probe model.

    Pmaj/Pmin from the Jacobian's column lengths (texels per pixel); the probe
    line runs along the major column. Pmin_eff = max(Pmin, pmin_floor); when
    Pmaj/Pmin_eff > L the count is capped at L by raising Pmin_eff to Pmaj/L
    ('raise-pmin') or keeping the spacing and truncating ('truncate').
    """
    S, T, dsx, dtx, dsy, dty = jacobian(deriv)
    valid = np.isfinite(S)
    S, T = np.nan_to_num(S), np.nan_to_num(T)
    Px, Py = np.hypot(dsx, dtx), np.hypot(dsy, dty)
    ymaj = Py >= Px
    pmaj = kmaj * np.nan_to_num(np.where(ymaj, Py, Px), nan=1.0)
    pmin = np.nan_to_num(np.where(ymaj, Px, Py), nan=1.0)
    ax_s = np.nan_to_num(np.where(ymaj, dsy, dsx) / np.maximum(pmaj, 1e-9))
    ax_t = np.nan_to_num(np.where(ymaj, dty, dtx) / np.maximum(pmaj, 1e-9))
    pe = np.maximum(pmin, pmin_floor)
    if clamp == 'raise-pmin':
        pe = np.maximum(pe, pmaj / L)
    nf = np.clip(pmaj / pe, 1.0, L)
    w = np.zeros_like(S)
    for off, wt in probes(nf, pe, rule):
        if wbits:
            wt = wround(wt * (1 << wbits)) / (1 << wbits)
        d = off * pe
        w += wt * checker(S + d * ax_s, T + d * ax_t, parity)
    return w, valid


# ---------------------------------------------------------------------------
# the result

BEST = dict(rule='even-frac', deriv='quad', pmin_floor=1.0, clamp='raise-pmin')


def split(pred_rgb, gold):
    d = np.abs(pred_rgb - gold).max(-1)[ROWS]
    return (int((d > 0).sum()), int((d == 1).sum()), int(((d >= 2) & (d <= 8)).sum()),
            int((d > 8).sum()), int(d.max()))


def render(L, **kw):
    w, v = model_iso() if L == 1 else model_aniso(L, **kw)
    return np.where(v[..., None], to_rgb(w), 32)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--goldens', default=GOLDENS)
    ap.add_argument('--capture', action='append', default=[],
                    help='a directory holding Texture_anisotropy::Anisotropy-N.png')
    ap.add_argument('--sweep', action='store_true')
    a = ap.parse_args()
    np.seterr(all='ignore')
    levels = (1, 2, 4, 8)
    gold = {L: golden(L, a.goldens) for L in levels}
    print('rows 245..364; cells are px (|d|=1, 2..8, >8, max)')
    for c in a.capture:
        for L in levels:
            img = np.asarray(Image.open(os.path.join(c, f'{SUITE}::Anisotropy-{L}.png')).convert('RGB')).astype(int)
            print(f'  {os.path.basename(os.path.dirname(c.rstrip("/"))) or c:48s} x{L}', split(img, gold[L]))
    for L in levels:
        print(f'  {"model " + str(BEST):48s} x{L}', split(render(L, **BEST), gold[L]))
    if a.sweep:
        print('variants (x2, x4, x8):')
        for rule in ('even-frac', 'ceil-even', 'round'):
            for deriv in ('central', 'quad'):
                for clamp in ('raise-pmin', 'truncate'):
                    kw = dict(rule=rule, deriv=deriv, pmin_floor=1.0, clamp=clamp)
                    print(f'  {rule:9s} {deriv:7s} {clamp:10s}',
                          [split(render(L, **kw), gold[L])[0] for L in (2, 4, 8)])


if __name__ == '__main__':
    sys.exit(main())
