#!/usr/bin/env python3
"""Measure the Attrib_carryover residual: is it a carryover defect, and is the floor dither?

Reproduces EVERY number in
docs/investigations/attrib-carryover-is-reproduced-not-ignored.md, and every
prediction and kill condition in
  docs/testing/predictions/2026-09-15-attrib-carryover-is-the-filled-floor.md
  docs/testing/predictions/2026-09-15-the-filled-floor-is-gl-dither.md

Two instrument notes, both earned the hard way in this file:

* The gradient comparison (P3) MUST erode the in-primitive mask. Primitive
  boundaries against the background carry huge gradients and we happen to agree
  there, so an un-eroded comparison reports ratio 0.53-0.92 -- an apparent
  ANTI-correlation -- where the eroded one reports 4.23-10.24. The uneroded
  number is measuring "edges have big gradients", not the floor.
* P4 must test non-dither lags (3, 5) alongside the dither lags (2, 4, 8). The
  dither lags are elevated over density; so is everything else, and lags 3 and 5
  are elevated MORE. Without the non-dither controls the elevation reads as a
  confirmation.

Usage:  attrib_carryover_floor.py <ours_dir> <goldens_root>
"""
import collections
import os
import re
import sys

import numpy as np
from PIL import Image

ATTR_RX = re.compile(r'^([a-z]+[0-9]?)(\d\.\d.*)$')
FILLED_PRIMS = ('Quads', 'TriFan', 'QuadStrip', 'Polygon', 'Triangles', 'TriStrip')
ATTRS = ['w', 'n', 'd', 's', 'fc', 'ps', 'bd', 'bs', 't0', 't1', 't2', 't3']
COL = {'da': '0.1_0.0_1.0_1.0', 'ib': '0.8_0.0_0.0_1.0',
       'ia': '0.5_0.0_0.0_1.0', 'ie': '0.2_0.0_0.6_1.0'}
CASES = [('Attrib_carryover', 'T-t00.1_0.0_1.0_1.0-da'),
         ('Attrib_carryover', 'T-t00.2_0.0_0.6_1.0-ie'),
         ('3D_primitive', 'Polygon'),
         ('3D_primitive', 'TriStrip')]


def pair(od, gd, suite, name):
    a = np.asarray(Image.open(os.path.join(od, f'{suite}::{name}.png')).convert('RGB')).astype(np.int16)
    b = np.asarray(Image.open(os.path.join(gd, suite, f'{name}.png')).convert('RGB')).astype(np.int16)
    return a, b


def names_for(od, suite):
    pre = suite + '::'
    return sorted(f[len(pre):-4] for f in os.listdir(od) if f.startswith(pre) and f.endswith('.png'))


def background(img):
    f = img.reshape(-1, 3)
    c, n = np.unique(f, axis=0, return_counts=True)
    return c[n.argmax()]


def gradient(img):
    """Local colour gradient of the GOLDEN: max |delta| to the 4-neighbours."""
    g = np.zeros(img.shape[:2], np.int16)
    d = np.abs(img[1:, :, :] - img[:-1, :, :]).max(axis=2)
    g[1:, :] = np.maximum(g[1:, :], d); g[:-1, :] = np.maximum(g[:-1, :], d)
    d = np.abs(img[:, 1:, :] - img[:, :-1, :]).max(axis=2)
    g[:, 1:] = np.maximum(g[:, 1:], d); g[:, :-1] = np.maximum(g[:, :-1], d)
    return g


def erode(m, k):
    o = m.copy()
    for _ in range(k):
        e = o.copy()
        e[1:, :] &= o[:-1, :]; e[:-1, :] &= o[1:, :]
        e[:, 1:] &= o[:, :-1]; e[:, :-1] &= o[:, 1:]
        o = e
    return o


def neighbour_stats(mask):
    n = np.zeros(mask.shape, np.int16)
    n[1:, :] += mask[:-1, :]; n[:-1, :] += mask[1:, :]
    n[:, 1:] += mask[:, :-1]; n[:, :-1] += mask[:, 1:]
    v = n[mask]
    if v.size == 0:
        return 0.0, 0.0, 0
    return float(v.mean()), float((v >= 3).mean() * 100.0), int(v.size)


def main(od, gd):
    rng = np.random.default_rng(20260915)

    rows = []
    for name in names_for(od, 'Attrib_carryover'):
        a, b = pair(od, gd, 'Attrib_carryover', name)
        d = np.abs(a - b)
        p = name.split('-'); m = ATTR_RX.match(p[1])
        rows.append(dict(prim=p[0], mode=p[-1], attr=m.group(1) if m else '?',
                         col=m.group(2) if m else '?',
                         ch=int((d > 0).sum()), tot=int(d.sum())))
    print(f'Attrib_carryover: {len(rows)} captures, {sum(r["ch"] for r in rows)} differing channels')
    for key in ('mode', 'attr', 'prim', 'col'):
        agg = collections.defaultdict(lambda: [0, 0, 0])
        for r in rows:
            e = agg[r[key]]; e[0] += 1; e[1] += r['ch']; e[2] += r['tot']
        print(f'--- by {key} ---')
        for k, (n, ch, tot) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
            print(f'  {k:18s} n={n:3d} ch={ch:9d} per-cap={ch // n:8d} mean|d|={tot / ch if ch else 0:5.2f}')

    print('\n=== are the difference maps IDENTICAL across attributes? (T/da) ===')
    ref = None
    for at in ATTRS:
        a, b = pair(od, gd, 'Attrib_carryover', f'T-{at}{COL["da"]}-da')
        d = np.abs(a - b)
        if ref is None:
            ref = d; print(f'  {at:3s} reference ch={int((d > 0).sum())}')
        else:
            print(f'  {at:3s} identical={np.array_equal(d, ref)} ch={int((d > 0).sum())} '
                  f'map-differs-at={int((d != ref).any(axis=2).sum())} px')

    print('\n=== does the image RESPOND to the attribute -- ours vs hardware ===')
    ident = differ = 0
    for prim in ('T', 'L'):
        for mode in COL:
            ro, rg = pair(od, gd, 'Attrib_carryover', f'{prim}-w{COL[mode]}-{mode}')
            for at in ATTRS:
                if at == 'w':
                    continue
                o, g = pair(od, gd, 'Attrib_carryover', f'{prim}-{at}{COL[mode]}-{mode}')
                do, dg = int((np.abs(o - ro) > 0).sum()), int((np.abs(g - rg) > 0).sum())
                if do == dg:
                    ident += 1
                else:
                    differ += 1
                    print(f'  {prim}/{mode} {at:3s} ours={do:8d} gold={dg:8d} delta={do - dg:+5d}')
    print(f'  identical response: {ident}/{ident + differ}')

    print('\n=== P1 shape / C1 background / C2 shuffled ===')
    print(f'{"capture":30s} {"diff px":>8s} {"bg-diff":>7s} {"mean nbr":>8s} {">=3":>6s} '
          f'{"shuf":>6s} {"shuf>=3":>8s}')
    for mode in ('da', 'ib', 'ia', 'ie'):
        name = f'T-t0{COL[mode]}-{mode}'
        a, b = pair(od, gd, 'Attrib_carryover', name)
        mask = (np.abs(a - b) > 0).any(axis=2)
        bg = background(b)
        both_bg = (a == bg).all(axis=2) & (b == bg).all(axis=2)
        mean, ge3, _ = neighbour_stats(mask)
        flat = np.zeros(mask.size, bool); flat[:int(mask.sum())] = True; rng.shuffle(flat)
        smean, sge3, _ = neighbour_stats(flat.reshape(mask.shape))
        print(f'{name:30s} {int(mask.sum()):8d} {int((mask & both_bg).sum()):7d} '
              f'{mean:8.2f} {ge3:5.1f}% {smean:6.2f} {sge3:7.1f}%')

    print('\n=== P2 magnitude: 3D_primitive FILLED arm vs Attrib_carryover ===')
    for suite, sel in (('3D_primitive', lambda n: n.split('-')[0] in FILLED_PRIMS),
                       ('Attrib_carryover', lambda n: True)):
        h = collections.Counter(); ncap = 0
        for name in names_for(od, suite):
            if not sel(name):
                continue
            a, b = pair(od, gd, suite, name)
            v = np.abs(a - b); v = v[v > 0]; ncap += 1
            for k, c in zip(*np.unique(v, return_counts=True)):
                h[int(k)] += int(c)
        tot = sum(h.values()); le2 = sum(c for k, c in h.items() if k <= 2)
        print(f'  {suite}: {ncap} captures, {tot} channels, |d|<=2 = {100.0 * le2 / tot:.2f}% '
              f'(P2 needs >=95%)')
        for k in sorted(h)[:4]:
            print(f'    |d|={k:3d} {h[k]:9d} {100.0 * h[k] / tot:6.2f}%')

    print('\n=== P3 gradient ratio -- UNERODED (confounded) vs ERODED ===')
    print(f'{"capture":30s} {"erode":>5s} {"g_diff":>7s} {"g_same":>7s} {"ratio":>6s}')
    for s, n in CASES:
        a, b = pair(od, gd, s, n)
        mask = (np.abs(a - b) > 0).any(axis=2)
        inp = ~(b == background(b)).all(axis=2); g = gradient(b)
        for k in (0, 3):
            m = erode(inp, k) if k else inp
            ggd, ggs = g[mask & m], g[(~mask) & m]
            r = ggd.mean() / ggs.mean() if ggs.size and ggs.mean() else float('nan')
            print(f'{n[:30]:30s} {k:5d} {ggd.mean():7.3f} {ggs.mean():7.3f} {r:6.2f}')

    print('\n=== P4 periodicity: P(differ at p+L | differ at p) / density ===')
    print(f'{"capture":30s} {"axis":4s} ' + ' '.join(f'L{L:<5d}' for L in (2, 3, 4, 5, 8)))
    for s, n in CASES:
        a, b = pair(od, gd, s, n)
        mask = (np.abs(a - b) > 0).any(axis=2)
        roi = erode(~(b == background(b)).all(axis=2), 3)
        mm = mask & roi; dens = mm.sum() / roi.sum()
        for axis in ('x', 'y'):
            out = []
            for L in (2, 3, 4, 5, 8):
                if axis == 'x':
                    p = mm[:, :-L] & roi[:, L:]; sh = mm[:, L:]
                else:
                    p = mm[:-L, :] & roi[L:, :]; sh = mm[L:, :]
                base = p.sum()
                out.append(((p & sh).sum() / base) / dens if base else float('nan'))
            print(f'{n[:30]:30s} {axis:4s} ' + ' '.join(f'{v:<6.3f}' for v in out)
                  + f'   density={dens:.3f}')

    print('\n=== P5 phase (x mod 4, y mod 4), gradient>0 interior ===')
    for s, n in CASES:
        a, b = pair(od, gd, s, n)
        mask = (np.abs(a - b) > 0).any(axis=2)
        roi = erode(~(b == background(b)).all(axis=2), 3) & (gradient(b) > 0)
        ys, xs = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
        rate = np.full((4, 4), np.nan)
        for i in range(4):
            for j in range(4):
                sel = roi & (ys % 4 == i) & (xs % 4 == j)
                if sel.sum():
                    rate[i, j] = (mask & sel).sum() / sel.sum()
        mx, mn = np.nanmax(rate), np.nanmin(rate)
        print(f'{n[:30]:30s} max={mx:.3f} min={mn:.3f} ratio={mx / mn:.2f} (P5 needs >=1.5)')

    print('\n=== C5 control: FLAT interior (gradient==0) ===')
    for s, n in CASES:
        a, b = pair(od, gd, s, n)
        mask = (np.abs(a - b) > 0).any(axis=2)
        roi = erode(~(b == background(b)).all(axis=2), 3) & (gradient(b) == 0)
        if not roi.sum():
            print(f'{n[:30]:30s} no flat interior pixels')
            continue
        print(f'{n[:30]:30s} flat px={int(roi.sum()):7d} differing={int((mask & roi).sum()):6d} '
              f'rate={100.0 * (mask & roi).sum() / roi.sum():7.3f}%')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
