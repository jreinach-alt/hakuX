#!/usr/bin/env python3
"""Price #224 family B candidates: the lit flat colour of every Shade_model
normal through vsh-ff.c's lighting and vsh.c's colorPrecision(), in float32.

Inputs re-derived from nxdk_pgraph_tests src/tests/shade_model_tests.cpp
(6743b6ab): infinite light (0,0,1), diffuse (0,1,0.7), COLOR_MATERIAL all
from material, ambient/emission/specular 0, modelview a pure look-down-+z
(rotation identity) so the eye-space normal is the input normal.

usage: price.py
"""
import struct

import numpy as np

f = np.float32
NORMALS = [
    (0.5773502691896258, -0.5773502691896258, 0.5773502691896258),
    (0.0, 0.0, 1.0),
    (0.4082482904638631, 0.4082482904638631, 0.8164965809277261),
    (-0.66667, 0.66667, 0.3333333),
    (0.3015, 0.3015, 0.9045), (0.4851, 0.4851, 0.7276),
    (0.6247, 0.6247, 0.4685), (0.2673, 0.5345, 0.8018),
    (0.6767, 0.6767, 0.29), (0.7317, 0.3049, 0.6097),
    (0.6172, 0.7715, 0.1543), (0.6527, 0.272, 0.7071),
    (0.7861, 0.3276, 0.5241), (0.6509, 0.6509, 0.3906),
]
LIGHT = (f(0), f(0), f(1))
DIFFUSE = (f(0), f(1), f(0.7))


def bits(x):
    return struct.unpack('<I', struct.pack('<f', float(f(x))))[0]


def fb(u):
    return f(struct.unpack('<f', struct.pack('<I', u & 0xffffffff))[0])


def lt(x):
    """vsh-ff.c ltBits(): round to a 13-bit fraction (envytools xf_s2lt)."""
    u = bits(x)
    if ((u >> 10) & 0xff) != 0xff:
        u += 0x200
    return fb(u & 0xFFFFFC00)


def trunc13(x):
    return fb(bits(x) & 0xFFFFFC00)


def color_precision(x):
    """vsh.c colorPrecision(): truncate to 13 bits, then floor(x*255+0.5)."""
    t = trunc13(min(max(f(x), f(0)), f(1)))
    return int(np.floor(f(t * f(255)) + f(0.5)))


def dot(a, b, tr=False):
    s = f(0)
    for x, y in zip(a, b):
        p = f(f(x) * f(y))
        if tr:
            p = trunc13(p)
        s = f(s + p)
        if tr:
            s = trunc13(s)
    return s


def lit(n, cand):
    n = tuple(f(c) for c in n)
    if cand in ('ltN', 'ltN+trunc'):
        n = tuple(lt(c) for c in n)
    tr = cand == 'ltN+trunc'
    ndl = max(f(0), dot(n, LIGHT, tr=tr))
    out = []
    for c in DIFFUSE:
        p = f(0) if lt(c) == 0 or ndl == 0 else f(lt(c) * ndl)
        if tr:
            p = trunc13(p)
        out.append(color_precision(p))
    return out[1], out[2]


# Silicon's flat colours read from the goldens (shade224 NOTES 1B).
GOLDEN = {0: (147, 103), 1: (255, 179), 2: (208, 146), 3: (85, 60),
          4: (231, 161), 5: (186, 130), 6: (119, 84), 7: (204, 143),
          8: (74, 52)}

if __name__ == '__main__':
    cands = ('master', 'ltN', 'ltN+trunc')
    print('n   golden     ' + '  '.join('%-12s' % c for c in cands))
    for i, n in enumerate(NORMALS):
        g = GOLDEN.get(i)
        row = [lit(n, c) for c in cands]
        mark = ['' if g is None else ('ok' if r == g else 'XX')
                for r in row]
        print('%-3d %-10s ' % (i, '%d/%d' % g if g else '-') + '  '.join(
            '%-12s' % ('%d/%d %s' % (r[0], r[1], m)) for r, m in
            zip(row, mark)))
