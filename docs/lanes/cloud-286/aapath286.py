#!/usr/bin/env python3
"""#286: is the AA-surface path transparent, on silicon and on ours?

The -ls/-ps tests switch to an AA_CENTER_CORNER_2 surface at double pitch
whenever either flag is set (three_d_primitive_tests.cpp:936), so a capture
where the flag has no geometric effect -- LINESMOOTH on a filled primitive,
POLYSMOOTH on a line, either on points -- isolates the AA path alone.

For those 'no-op' captures, count below the label band:
  gold_moved   golden(X) != golden(P)  -- silicon's AA path changed anything
  ours_moved   ours(X)   != ours(P)    -- our AA path changed anything
  wrong_X / wrong_P  structural(ours, golden) for X and for its twin P
and split wrong_X into pixels our AA path moved and pixels it did not.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import decompose286 as D  # noqa: E402

FILLED = ['Polygon', 'QuadStrip', 'Quads', 'TriFan', 'TriStrip', 'Triangles']
LINES = ['Lines', 'LineLoop', 'LineStrip']
NOOP = [(p, '-ls') for p in FILLED] + [(p, '-ps') for p in LINES] + \
       [('Points', f) for f in D.FLAGS]
body = np.zeros((480, 640), bool)
body[D.LABEL_ROWS:] = True
print('| capture (x4 paths) | gold_moved | ours_moved | wrong_P | wrong_X | wrong_X on ours_moved | wrong_X not moved |')
print('|---|---:|---:|---:|---:|---:|---:|')
T = np.zeros(6, int)
for prim, flag in NOOP:
    t = np.zeros(6, int)
    for path in D.PATHS:
        P = prim + path
        X = P + flag
        gp, op = D.ld(D.GOLD + P + '.png'), D.ld(D.OURS + P + '.png')
        gx, ox = D.ld(D.GOLD + X + '.png'), D.ld(D.OURS + X + '.png')
        gm = (np.abs(gx - gp).max(2) > 0) & body
        om = (np.abs(ox - op).max(2) > 0) & body
        wx = D.struct(ox, gx) & body
        wp = D.struct(op, gp) & body
        t += [gm.sum(), om.sum(), wp.sum(), wx.sum(), (wx & om).sum(), (wx & ~om).sum()]
    T += t
    print('| %s%s | ' % (prim, flag) + ' | '.join('{:,}'.format(v) for v in t) + ' |')
print('| **total** | ' + ' | '.join('{:,}'.format(v) for v in T) + ' |')
