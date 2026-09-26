#!/usr/bin/env python3
"""Where are CENTER_CORNER_2's two samples?  Read it off Antialiasing_tests.

FBSurfaceWithCenterCorner2 draws a flat diamond, vertices (64,240) (320,64)
(576,240) (320,416), into a CC2 surface whose 1280-px rows are displayed at a
640-px pitch.  So display row 2r is AA row r, columns 0-639, and display row
2r+1 is AA row r, columns 640-1279.  That un-interleaves to the raw AA surface
(rows 0-239), and each AA column k is one sample of guest pixel k // 2.

Model: the sample for column parity p sits at guest (k//2 + sx[p], r + sy[p]).
A pixel is covered iff its sample is inside the diamond (edges at a sample
count as inside: ties are few and scored as whatever they are).

1. Calibrate the diamond's screen offset (ox, oy) on FBSurfaceWithCenter1,
   where every sample is at (x+0.5, y+0.5).
2. With that offset, score candidate (sx, sy) per parity on the CC2 image by
   mismatched pixels, for silicon (golden) and for ours.
"""
import itertools
import sys

import numpy as np
from PIL import Image

GOLD = '/home/justin/goldens/results/Antialiasing_tests/'
OURS = ('/home/justin/hakux-work/dispatch/results/0-a-now-8e683b3a26-004-'
        'Antialiasing_tests/captures1/Antialiasing_tests::')
V = [(64.0, 240.0), (320.0, 64.0), (576.0, 240.0), (320.0, 416.0)]
ROW0 = 70   # below the label


def ld(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)


def cov(img):
    return (img[..., 1] > 128) & (img[..., 0] < 128)


def inside(px, py, ox, oy):
    """diamond test, convex, clockwise in screen space"""
    ok = np.ones(px.shape, bool)
    for i in range(4):
        x0, y0 = V[i]
        x1, y1 = V[(i + 1) % 4]
        x0 += ox; x1 += ox; y0 += oy; y1 += oy
        ok &= (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0) >= 0
    return ok


def unweave(d):
    a = np.zeros((240, 1280), bool)
    a[:, :640] = d[0::2]
    a[:, 640:] = d[1::2]
    return a


def main():
    grid = np.arange(-16, 17) / 16.0
    c1 = cov(ld(GOLD + 'FBSurfaceWithCenter1.png'))[ROW0:]
    ys, xs = np.mgrid[ROW0:480, 0:640]
    best = min((int((inside(xs + .5, ys + .5, ox, oy) != c1).sum()), ox, oy)
               for ox in grid for oy in grid)
    print('Center1 golden: best offset ox=%+.4f oy=%+.4f, %d px mismatched'
          % (best[1], best[2], best[0]))
    _, ox, oy = best

    rows, cols = np.mgrid[ROW0 // 2:240, 0:1280]
    gx = cols // 2
    par = cols % 2
    cand = [0.0, 0.25, 0.5, 0.75, 1.0]
    for name, path in (('golden', GOLD), ('ours', OURS)):
        a = unweave(cov(ld(path + 'FBSurfaceWithCenterCorner2.png')))[ROW0 // 2:]
        res = []
        for p in (0, 1):
            m = par == p
            for sx, sy in itertools.product(cand, cand):
                pred = inside(gx[m] + sx, rows[m] + sy, ox, oy)
                res.append((int((pred != a[m]).sum()), p, sx, sy))
        print('%s CC2 (%d px per parity):' % (name, (par == 0).sum()))
        for p in (0, 1):
            r = sorted(x for x in res if x[1] == p)[:3]
            print('  col parity %d: ' % p +
                  ', '.join('(%.2f,%.2f) %d' % (sx, sy, n) for n, _, sx, sy in r))


if __name__ == '__main__':
    sys.exit(main())
