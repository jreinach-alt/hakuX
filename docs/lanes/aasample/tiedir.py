#!/usr/bin/env python3
"""Which half-column does OUR resolve pick at the u = 2x+1 tie?

Our AA path shades the two half-columns at guest x+0.25 (texel 2x) and
x+0.75 (texel 2x+1).  If the resolve picks 2x+1, ours(X) is ours(P) sampled a
quarter pixel to the RIGHT, so along a horizontal colour gradient
d = ours(X) - ours(P) has the sign of the gradient g = P(x+1) - P(x-1).  If it
picks 2x, the sign is opposite.  Region statistic over every no-op capture:
count pixels with d*g > 0 and d*g < 0 (per channel, |g| >= 2, below the band).

Also on silicon: the same statistic on golden(X) vs golden(P), which must be
0/0 (silicon is transparent), as a check the instrument can see nothing there.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/cloud-286')
import decompose286 as D  # noqa: E402

FILLED = ['Polygon', 'QuadStrip', 'Quads', 'TriFan', 'TriStrip', 'Triangles']
LINES = ['Lines', 'LineLoop', 'LineStrip']
NOOP = [(p, '-ls') for p in FILLED] + [(p, '-ps') for p in LINES] + \
       [('Points', f) for f in D.FLAGS]


def stat(x, p):
    x = x[D.LABEL_ROWS:, 1:-1, :3]
    g = p[D.LABEL_ROWS:, 2:, :3] - p[D.LABEL_ROWS:, :-2, :3]
    p = p[D.LABEL_ROWS:, 1:-1, :3]
    d = x - p
    m = np.abs(g) >= 2
    s = d * g
    return int(((s > 0) & m).sum()), int(((s < 0) & m).sum())


def main():
    print('| capture | ours right | ours left | gold right | gold left |')
    print('|---|---:|---:|---:|---:|')
    T = np.zeros(4, int)
    for prim, flag in NOOP:
        t = np.zeros(4, int)
        for path in D.PATHS:
            P = prim + path
            X = P + flag
            o = stat(D.ld(D.OURS + X + '.png'), D.ld(D.OURS + P + '.png'))
            g = stat(D.ld(D.GOLD + X + '.png'), D.ld(D.GOLD + P + '.png'))
            t += o + g
        T += t
        print('| %s%s | ' % (prim, flag) + ' | '.join('{:,}'.format(v) for v in t) + ' |')
    print('| **total** | ' + ' | '.join('{:,}'.format(v) for v in T) + ' |')


if __name__ == '__main__':
    main()
