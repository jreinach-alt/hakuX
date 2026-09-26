#!/usr/bin/env python3
"""Price the CC2 half-pixel viewport shift over the 120 AA captures.

With the shift, AA column 2x+1 is shaded at guest (x+0.5, y+0.5): exactly the
non-AA sample, for triangles and for lines (the geometry stage emits lines as
filled parallelograms in guest units).  We emulate no smoothing, so the fixed
ours(X) is ours(P) below the label band.  The one exception is points: a 1-px
Vulkan point is half a guest pixel wide, and points.py shows 3 of the 12
(f = 0.0625, 0.0625, 0.9375) still miss column 2x+1.  Those pixels are set to
ours(X)'s value today (background: dropped now too).

Label band (y < 64) is kept from ours(X): the label is drawn after the resolve
and its text differs from P's.

Reports per primitive: structural px (|d| > 1, any channel) and differing px
(any channel) against golden(X), now and fixed.  Also the 48 inert captures
(flag with no geometric effect) and the falsifier O_X == O_P there.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/cloud-286')
import decompose286 as D  # noqa: E402

FILLED = ['Polygon', 'QuadStrip', 'Quads', 'TriFan', 'TriStrip', 'Triangles']
LINES = ['Lines', 'LineLoop', 'LineStrip']
INERT = set([(p, '-ls') for p in FILLED] + [(p, '-ps') for p in LINES] +
            [('Points', f) for f in D.FLAGS])
STILL_DROPPED = [(417, 240), (392, 216), (248, 204)]   # points.py 3, 4, 5


def diff(a, b):
    d = np.abs(a[..., :3] - b[..., :3]).max(2)
    return int((d > 1).sum()), int((d > 0).sum())


def main():
    print('| primitive (x4 paths, 3 flags) | struct now | struct fixed | net | differing now | differing fixed |')
    print('|---|---:|---:|---:|---:|---:|')
    tot = np.zeros(4, int)
    inert = np.zeros(4, int)
    inert_moved_now = inert_moved_fixed = 0
    for prim in ['Lines', 'LineLoop', 'LineStrip', 'Points'] + FILLED:
        t = np.zeros(4, int)
        for path in D.PATHS:
            P = prim + path
            op = D.ld(D.OURS + P + '.png')
            for flag in D.FLAGS:
                X = P + flag
                gx = D.ld(D.GOLD + X + '.png')
                ox = D.ld(D.OURS + X + '.png')
                fx = ox.copy()
                fx[D.LABEL_ROWS:] = op[D.LABEL_ROWS:]
                if prim == 'Points':
                    for (x, y) in STILL_DROPPED:
                        fx[y, x] = ox[y, x]
                sn, dn = diff(ox, gx)
                sf, df = diff(fx, gx)
                row = [sn, sf, dn, df]
                t += row
                if (prim, flag) in INERT:
                    inert += row
                    body = slice(D.LABEL_ROWS, None)
                    inert_moved_now += diff(ox[body], op[body])[1]
                    inert_moved_fixed += diff(fx[body], op[body])[1]
        tot += t
        print('| %s | %s | %s | %s | %s | %s |' % (
            prim, *('{:,}'.format(v) for v in (t[0], t[1], t[0] - t[1], t[2], t[3]))))
    print('| **all 120** | %s | %s | **%s** | %s | %s |' % tuple(
        '{:,}'.format(v) for v in (tot[0], tot[1], tot[0] - tot[1], tot[2], tot[3])))
    print()
    print('48 inert captures: struct %s -> %s, differing %s -> %s' % tuple(
        '{:,}'.format(v) for v in inert))
    print('falsifier O_X != O_P below band on the 48: now %s px, fixed-model %s px'
          % ('{:,}'.format(inert_moved_now), '{:,}'.format(inert_moved_fixed)))


if __name__ == '__main__':
    main()
