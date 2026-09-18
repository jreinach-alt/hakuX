#!/usr/bin/env python3
"""Characterise a capture's residual against its golden as a LAYOUT question.

    swizzle_residual.py <ours.png> <golden.png>

Prints the differing-pixel count and bounding box, the colour multiset of
each side over the differing pixels (identical multisets mean the right
pixels are in the wrong places -- a permutation, not a wrong value), which
colours the golden holds that we never produce, a 16x16-cell map of the
differing region, the colour distribution per 64-pixel column of that region,
the horizontal run lengths of differing pixels, and the single translation of
the golden that explains the most differing pixels.

Written for Surface_pitch::Swizzle once #39's skew-bound measurement had
removed the guest/pgraph race from it: the 10,240 px both renderers then
share turned out to be exactly such a rearrangement. A multiset test on the
race-affected capture had said the opposite, because it was measuring the
race.
"""
import sys
from collections import Counter

import numpy as np
from PIL import Image


def hexc(c):
    return '#%02X%02X%02X' % tuple(int(v) for v in c)


def multiset(a):
    c = Counter(hexc(p) for p in a.reshape(-1, 3))
    return ' '.join(f'{k}x{v}' for k, v in sorted(c.items()))


def main(ours_p, gold_p):
    o = np.asarray(Image.open(ours_p).convert('RGB')).astype(int)
    g = np.asarray(Image.open(gold_p).convert('RGB')).astype(int)
    d = (np.abs(o - g).max(axis=2) > 0)
    H, W = d.shape
    ys, xs = np.nonzero(d)
    if len(ys) == 0:
        print('byte-identical to the golden')
        return
    print(f'differing: {d.sum():,} of {d.size:,}; '
          f'bbox x[{xs.min()}..{xs.max()}] y[{ys.min()}..{ys.max()}]')
    co = Counter(hexc(o[y, x]) for y, x in zip(ys, xs))
    cg = Counter(hexc(g[y, x]) for y, x in zip(ys, xs))
    print('ours at differing px:', ', '.join(f'{k}x{v}' for k, v in co.most_common(8)))
    print('gold at differing px:', ', '.join(f'{k}x{v}' for k, v in cg.most_common(8)))
    print('same multiset:', co == cg)
    missing = sorted(set(hexc(c) for c in g.reshape(-1, 3))
                     - set(hexc(c) for c in o.reshape(-1, 3)))
    print('colours in gold but nowhere in ours (whole frame):', missing[:8])

    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    print(f'region {x1 - x0}x{y1 - y0}; 16x16 cell map (#=all differ, +=part, .=none):')
    for y in range(y0, y1, 16):
        row = ''
        for x in range(x0, x1, 16):
            s = d[y:y + 16, x:x + 16].sum()
            row += '#' if s == 256 else ('+' if s else '.')
        print(f'   y{y:3d} {row}')
    print('per 64-px column of the region, ours | gold:')
    for x in range(x0, x1, 64):
        print(f'   x{x:3d}: {multiset(o[y0:y1, x:x + 64])} | {multiset(g[y0:y1, x:x + 64])}')

    runs = Counter()
    for y in range(H):
        n = 0
        for v in d[y]:
            if v:
                n += 1
            elif n:
                runs[n] += 1
                n = 0
        if n:
            runs[n] += 1
    print('horizontal run lengths:', ', '.join(
        f'{k}px x{v}' for k, v in sorted(runs.items(), key=lambda kv: -kv[1])[:8]))

    best = []
    for dy in range(-64, 65):
        for dx in range(-192, 193, 4):
            yy, xx = ys + dy, xs + dx
            ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W)
            if ok.sum() < len(ys) * 0.9:
                continue
            m = (o[ys[ok], xs[ok]] == g[yy[ok], xx[ok]]).all(axis=1).mean()
            best.append((m, dy, dx))
    best.sort(reverse=True)
    print('best single translation of the golden explaining our differing px:')
    for m, dy, dx in best[:3]:
        print(f'   {m:.3f} at dy={dy:+d} dx={dx:+d}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
