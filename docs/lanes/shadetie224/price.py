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

def three_ties():
    """shadetie224b: every candidate against all three tie points at once.

    Directional is Lighting_range/Directional's flat quads
    (lighting_range_tests.cpp): N = (+-0.0990148, +-0.0990148, -0.9901475),
    infinite light, direction and precomputed half vector both (0,0,-1),
    specular colour (0,0,1), SPECULAR_PARAMS[0..2] = 0xBF56C33A 0xC038C729
    0x4043165A. Its blue is diffuse 21 (ambients 0.031373 + 0.05) plus the
    specular byte; silicon's 224 needs the specular byte to be 203.
    """
    import math
    import celsius_lt as C
    k_raw = [fb(u) for u in (0xBF56C33A, 0xC038C729, 0x4043165A)]
    DN = (f(0.099014754297667), f(0.099014754297667), f(-0.990147542976674))
    HV = (f(0), f(0), f(-1))
    n1, n3 = NORMALS[1], NORMALS[3]

    def rn13(x):
        return lt(x)

    def spec(n, cand):
        """The Directional specular byte, vsh-ff.c's specular path."""
        if cand == 'celsius':
            L = lambda v: [C.s2lt(C.f2u(x)) for x in v]
            _, c1, _ = C.light_infinite(
                L(n), L(HV), L(HV), [C.s2lt(bits(x)) for x in k_raw],
                L([0.05] * 3), L([1, 1, 0]), L([0, 0, 1]), L([0.031373] * 3))
            return color_precision(C.u2f(c1[2]))
        n = tuple(f(c) for c in n)
        if cand == 'ltN':
            n = tuple(lt(c) for c in n)
        x = max(f(0), dot(n, HV))
        if cand == 'ltDots':
            x = lt(x)
        num = f(x + k_raw[0])
        den = f(f(x * k_raw[1]) + k_raw[2])
        pf = f(num / den)
        p = f(lt(f(1)) * pf)
        if cand == 'ltProds':
            p = rn13(p)
        return color_precision(p)

    def diff(n, cand):
        """Shade_model's lit blue."""
        if cand == 'celsius':
            L = lambda v: [C.s2lt(C.f2u(x)) for x in v]
            Z = L([0, 0, 0])
            c0, _, _ = C.light_infinite(L(n), L(LIGHT), L(LIGHT), Z, Z,
                                        L(DIFFUSE), Z, Z)
            return color_precision(C.u2f(c0[2]))
        n = tuple(f(c) for c in n)
        if cand == 'ltN':
            n = tuple(lt(c) for c in n)
        x = max(f(0), dot(n, LIGHT))
        if cand in ('ltNL', 'ltDots'):
            x = lt(x)
        p = f(lt(DIFFUSE[2]) * x)
        if cand in ('ltDiffProd', 'ltProds'):
            p = rn13(p)
        if cand == 'rnColorPrecision':
            return int(np.floor(f(rn13(p) * f(255)) + f(0.5)))
        return color_precision(p)

    # 0.1f through colorPrecision: the Point size goldens say 25.
    def point01(cand):
        if cand == 'rnColorPrecision':
            return int(np.floor(f(rn13(f(0.1)) * f(255)) + f(0.5)))
        return color_precision(f(0.1))

    cands = ['master', 'ltN', 'ltNL', 'ltDots', 'ltDiffProd', 'ltProds',
             'rnColorPrecision', 'celsius']
    print('%-17s %6s %6s %8s %8s  %s' % ('candidate', 'n3=60', 'n1=179',
                                        'Dir=203', 'pt0.1=25', 'fits'))
    for c in cands:
        r = (diff(n3, c), diff(n1, c), spec(DN, c), point01(c))
        ok = r == (60, 179, 203, 25)
        print('%-17s %6d %6d %8d %8d  %s' % ((c,) + r + ('ALL' if ok else '',)))
    # The nine Shade_model colours under the full Celsius model.
    L = lambda v: [C.s2lt(C.f2u(x)) for x in v]
    Z = L([0, 0, 0])
    bad = 0
    for i, g in GOLDEN.items():
        c0, _, _ = C.light_infinite(L(NORMALS[i]), L(LIGHT), L(LIGHT), Z, Z,
                                    L(DIFFUSE), Z, Z)
        got = (color_precision(C.u2f(c0[1])), color_precision(C.u2f(c0[2])))
        bad += got != g
    print('celsius: Shade_model goldens wrong: %d of %d' % (bad, len(GOLDEN)))
    # Lighting accumulation: n ambient-only lights of 0.1 (the vsh-ff.c
    # header's "Directional-5 is 127, not 128").
    a, s = C.s2lt(C.f2u(0.1)), 0
    for n in range(5):
        s = C.lt_add(s, C.lt_mul(0x3f800000, a))
    print('celsius: five 0.1 ambients -> %d (silicon 127)'
          % color_precision(C.u2f(s)))


if __name__ == '__main__':
    import sys
    if '--three' in sys.argv:
        three_ties()
        sys.exit(0)
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
