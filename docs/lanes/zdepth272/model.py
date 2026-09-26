"""Candidate silicon arithmetic for the fixed-function z/w, in exact rationals.

rnd(x, mode, bits): round a rational to a binary float with `bits` mantissa bits.
"""
from fractions import Fraction as F
import itertools
import math

C22 = F(16861522)
C32 = F(101169136)


def rnd(x, mode, bits=24):
    if mode == 'exact' or x == 0:
        return x
    s = -1 if x < 0 else 1
    a = abs(x)
    e = math.floor(math.log2(a.numerator) - math.log2(a.denominator))
    # fix e so that 2^e <= a < 2^(e+1)
    while F(2) ** e > a:
        e -= 1
    while F(2) ** (e + 1) <= a:
        e += 1
    ulp = F(2) ** (e - bits + 1)
    q = a / ulp
    fl = q.numerator // q.denominator
    r = q - fl
    if mode == 'rtz':
        n = fl
    elif mode == 'rne':
        if r > F(1, 2) or (r == F(1, 2) and fl % 2 == 1):
            n = fl + 1
        else:
            n = fl
    elif mode == 'rna':
        n = fl + 1 if r >= F(1, 2) else fl
    elif mode == 'up':  # away from zero
        n = fl + (1 if r > 0 else 0)
    else:
        raise ValueError(mode)
    return s * n * ulp


def vertex_z(zw, m):
    """m: dict of modes. zw: world z as Fraction (float32 value)."""
    b = m.get('bits', 24)
    p = rnd(zw * C22, m['mul'], b)
    zc = rnd(p + C32, m['add'], b)
    w = rnd(zw + 7, m['add'], b)
    if m['div'] == 'div':
        q = rnd(zc / w, m['fin'], b)
    else:
        rx = 1 / w
        if m.get('rdef'):  # approximation deficit before rounding
            if m.get('rdef_kind', 'rel') == 'rel':
                rx = rx * (1 - F(m['rdef']) / 2 ** 24)
            else:  # in units of the result's own ULP
                ulp = rnd(rx, 'rtz', m.get('rbits', b))
                ulp = ulp - rnd(ulp * (1 - F(1, 2 ** 30)), 'rtz', m.get('rbits', b))
                rx = rx - F(m['rdef']) * ulp
        r = rnd(rx, m['rcp'], m.get('rbits', b))
        q = rnd(zc * r, m['fin'], b)
    return q


HELD = [  # (name, world z, silicon stored)
    ('near', F(-6), 8),
    ('Swap', F(180), 0xFFE916),
    ('ZetaIntoColor', F(192), 0xFFFE54),
]

if __name__ == "__main__":
    modes = ['rne', 'rtz', 'rna', 'up', 'exact']
    hits = []
    for mul, add, fin in itertools.product(modes, modes, modes):
        for div, rcp, rbits in [('div', None, 24)] + [('rcp', r, rb) for r in modes for rb in (22, 23, 24, 25)]:
            m = dict(mul=mul, add=add, fin=fin, div=div, rcp=rcp, rbits=rbits)
            res = []
            for name, zw, sil in HELD:
                q = vertex_z(zw, m)
                st = max(0, math.floor(q))
                res.append(st - sil)
            if all(r == 0 for r in res):
                hits.append(m)
            elif mul == 'rtz' and add == 'rtz':
                print('near-miss', m, res)
    print(len(hits), 'hits')
    for h in hits:
        print(h)
    print('ours (rne all):', [math.floor(vertex_z(zw, dict(mul='rne', add='rne', fin='rne', div='div'))) - s for _, zw, s in HELD])
