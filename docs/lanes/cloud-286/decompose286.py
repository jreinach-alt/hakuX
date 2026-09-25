#!/usr/bin/env python3
"""#286: split the 3D_primitive -ls/-ps structural residual by region.

For every smoothed capture X (120 = 10 primitives x 4 submission paths x
{-ls, -ps, -ls-ps}) and its unsmoothed twin P (same primitive and path, no
flag), with G = golden, O = ours, K = the 2026-09-19 console run:

  structural(a, b)  = some RGBA channel differs by more than 1 -- the same
                      "differing minus off_by_one" split score_sweep.py makes.
  footprint(X)      = structural(G_X, G_P) below the label band, dilated by
                      one pixel: the region where silicon's own smoothing
                      changes the image. No smoothing emulation can move a
                      pixel outside it.

Every structural(O_X, G_X) pixel then falls in exactly one class:

  label       y < 64 (the scorer's label band; the name gains "-ls"/"-ps")
  fp-alpha    inside the footprint, RGB within 1, only alpha differs
  fp-rgb      inside the footprint, RGB differs
  shared      outside the footprint, and structural(O_P, G_P) there too:
              the same pixel is wrong with smoothing off, so it is not
              smoothing and not the AA surface either
  aa-path     outside the footprint, O_P right there, O_X != O_P: our AA
              surface redirect (AA_CENTER_CORNER_2 + Z16 + render-to-texture
              and resolve, three_d_primitive_tests.cpp:936) changed OUR output
              where silicon's did not change
  other       outside the footprint, O_P right, O_X == O_P (should be ~0)

Usage: decompose286.py [--tsv out.tsv]
"""
import argparse
import csv
import os
import sys

import numpy as np
from PIL import Image

GOLD = '/home/justin/goldens/results/3D_primitive/'
OURS = ('/home/justin/hakux-work/dispatch/results/'
        '0-a-now-8e683b3a26-002-3D_primitive/captures1/3D_primitive::')
CONS = ('/home/justin/hakux-work/hardware/runs/2026-09-19-calib/full/out/'
        'run1/3D_primitive::')
LABEL_ROWS = 64
PRIMS = ['Lines', 'LineLoop', 'LineStrip', 'Points', 'Polygon', 'QuadStrip',
         'Quads', 'TriFan', 'TriStrip', 'Triangles']
PATHS = ['', '-inlinearrays', '-inlinebuf', '-inlineelements']
FLAGS = ['-ls', '-ps', '-ls-ps']
CLASSES = ['label', 'fp-alpha', 'fp-rgb', 'shared', 'aa-path', 'other']


def ld(p):
    return np.asarray(Image.open(p).convert('RGBA'), dtype=np.int16)


def struct(a, b):
    return np.abs(a - b).max(axis=2) > 1


def dilate(m):
    out = m.copy()
    out[1:] |= m[:-1]; out[:-1] |= m[1:]
    out[:, 1:] |= out[:, :-1].copy(); out[:, :-1] |= out[:, 1:].copy()
    return out


def lum(img):
    return (img[..., 0] * 299 + img[..., 1] * 587 + img[..., 2] * 114) // 1000


def edge_mask(g):
    """golden local 3x3 luminance range > 16 (the 09-12 edge definition)"""
    L = lum(g)
    p = np.pad(L, 1, mode='edge')
    stack = [p[dy:dy + L.shape[0], dx:dx + L.shape[1]]
             for dy in range(3) for dx in range(3)]
    s = np.stack(stack)
    return (s.max(0) - s.min(0)) > 16


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tsv')
    args = ap.parse_args()
    body = np.zeros((480, 640), bool)
    body[LABEL_ROWS:] = True
    rows = []
    for prim in PRIMS:
        for path in PATHS:
            P = prim + path
            gp, op, kp = ld(GOLD + P + '.png'), ld(OURS + P + '.png'), ld(CONS + P + '.png')
            for flag in FLAGS:
                X = P + flag
                gx, ox, kx = ld(GOLD + X + '.png'), ld(OURS + X + '.png'), ld(CONS + X + '.png')
                s_gold = struct(gx, gp) & body          # silicon's own difference
                s_cons = struct(kx, kp) & body          # same, from the 09-19 console
                fp = dilate(s_gold) & body
                wrong = struct(ox, gx)
                rgb_ok = np.abs(ox - gx)[..., :3].max(2) <= 1
                wrong_p = struct(op, gp)
                ours_moved = struct(ox, op)
                cls = {
                    'label': wrong & ~body,
                    'fp-alpha': wrong & fp & rgb_ok,
                    'fp-rgb': wrong & fp & ~rgb_ok,
                }
                out = wrong & body & ~fp
                cls['shared'] = out & wrong_p
                cls['aa-path'] = out & ~wrong_p & ours_moved
                cls['other'] = out & ~wrong_p & ~ours_moved
                assert sum(int(v.sum()) for v in cls.values()) == int(wrong.sum())
                edge = edge_mask(gx)
                aa = cls['aa-path']
                # what the aa-path pixels are: is ours brighter or darker, and
                # is the pixel on a golden edge or in the interior
                dl = lum(ox) - lum(gx)
                rows.append(dict(
                    capture=X, prim=prim, flag=flag,
                    wrong=int(wrong.sum()),
                    ceiling_gold=int(s_gold.sum()),
                    ceiling_cons=int(s_cons.sum()),
                    cons_vs_gold=int(struct(kx, gx).sum()),
                    cons_vs_gold_plain=int(struct(kp, gp).sum()),
                    **{c: int(cls[c].sum()) for c in CLASSES},
                    aa_edge=int((aa & edge).sum()),
                    aa_interior=int((aa & ~edge).sum()),
                    aa_darker=int((aa & (dl < 0)).sum()),
                    aa_brighter=int((aa & (dl > 0)).sum()),
                    shared_edge=int((cls['shared'] & edge).sum()),
                    # ours inside silicon's footprint: how much of silicon's
                    # own smoothed-vs-plain change do we get wrong
                    fp_hit=int((wrong & s_gold).sum()),
                ))
    keys = list(rows[0])
    w = csv.DictWriter(open(args.tsv, 'w') if args.tsv else sys.stdout,
                       fieldnames=keys, delimiter='\t', lineterminator='\n')
    w.writeheader()
    for r in rows:
        w.writerow(r)
    tot = {k: sum(r[k] for r in rows) for k in keys if k not in ('capture', 'prim', 'flag')}
    sys.stderr.write('TOTAL ' + ' '.join('%s=%d' % kv for kv in tot.items()) + '\n')


if __name__ == '__main__':
    main()
