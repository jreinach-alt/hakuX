#!/usr/bin/env python3
"""A bit-exact port of envytools' Celsius lighting-unit (LT) arithmetic.

Source: envytools nvhw/pgraph_celsius_xfrm.c (pgraph_celsius_lt_mul,
_lt_add3, _lts_mul, _lts_add, _lt_rcp, _lt_full) and nvhw/xf.c (xf_s2lt,
xf_rcp_lut_v1), with the shr32/norm32/fp32_mkfin helpers from
include/nvhw/fp.h. envytools checks these functions against the hardware in
hwtest, so this is a model of the silicon's LT that is independent of any
tie point here. NV2A keeps the same LT register file (LTCTXA/LTCTXB and
LTC0..3), and vsh-ff.c already cites xf_s2lt from this file.

Everything works on float32 bit patterns (ints). Only the paths the three
#224 tie points use are ported: an infinite light, a non-local eye (the
precomputed half vector), and no colour material.
"""
import struct

IONE = 0x800000


def f2u(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def u2f(u):
    return struct.unpack('<f', struct.pack('<I', u & 0xffffffff))[0]


def S(x):
    return x >> 31 & 1


def E(x):
    return x >> 23 & 0xff


def F(x):
    return x & 0x7fffff


def s2lt(x):
    """xf_s2lt << 10: round to a 13-bit fraction, half up."""
    if (x >> 10 & 0xff) != 0xff:
        x += 0x200
    return (x >> 10) << 10 & 0xffffffff


def shr32_rz(x, shift):
    if shift >= 0:
        return x >> shift if shift < 32 else 0
    return x << -shift


def norm32(x, e, bit):
    assert x & ~((2 << bit) - 1) == 0
    if not x:
        return 0, e
    while not x & (1 << bit):
        x <<= 1
        e -= 1
    return x, e


def mkfin_rz_ftz(s, e, f):
    if not f:
        e = 1
    if f == 2 * IONE:
        f >>= 1
        e += 1
    if e <= 0 or f < IONE:
        return s << 31
    if e >= 0xff:
        return s << 31 | 0xfe << 23 | (IONE - 1)
    return s << 31 | e << 23 | (f - IONE)


def lt_mul(a, b):
    sign = S(a) ^ S(b)
    ea, eb = E(a), E(b)
    fa = (a >> 10 & 0x1fff) | 1 << 13
    fb = (b >> 10 & 0x1fff) | 1 << 13
    if (ea == 0xff and fa > 0x2000) or (eb == 0xff and fb > 0x2000):
        return 0x7ffffc00
    if not ea or not eb:
        return 0
    if ea == 0xff or eb == 0xff:
        return 0x7f800000
    e = ea + eb - 0x7f
    fr = (fa * fb) >> 13
    if fr > 0x3fff:
        fr >>= 1
        e += 1
    if e <= 0:
        e, fr = 0, 0
    elif e >= 0xff:
        e, fr = 0xfe, 0x1fff
    return sign << 31 | e << 23 | (fr & 0x1fff) << 10


lts_mul = lt_mul  # identical on finite, in-range operands


def lt_add3(v):
    er = 0
    sv, ev, fv = [], [], []
    for x in v:
        s, e, f = S(x), E(x), F(x)
        if e:
            f |= IONE
        f >>= 10
        sv.append(s)
        ev.append(e)
        fv.append(f)
        er = max(er, e + 2)
    res = 0
    for s, e, f in zip(sv, ev, fv):
        f = shr32_rz(f, er - e - 7)
        res += -f if s else f
    if res == 0:
        er, sr = 0, 0
    else:
        sr = 1 if res < 0 else 0
        res = abs(res)
        res, er = norm32(res, er, 20)
        res = shr32_rz(res, 7)
    if er >= 0xff:
        er, res = 0xfe, 0x3fff
    return mkfin_rz_ftz(sr, er, res << 10)


def lt_add(a, b):
    return lt_add3([a, b, 0])


def lts_add(a, b):
    sa, ea, fa = S(a), E(a), F(a) >> 10
    sb, eb, fb = S(b), E(b), F(b) >> 10
    fa = fa | (IONE >> 10) if ea else 0
    fb = fb | (IONE >> 10) if eb else 0
    er = max(ea, eb) + 1
    fa = shr32_rz(fa, er - ea - 1)
    fb = shr32_rz(fb, er - eb - 1)
    res = (-fa if sa else fa) + (-fb if sb else fb)
    if res == 0:
        er, sr = 0, 0
    else:
        sr = 1 if res < 0 else 0
        res = abs(res)
        res, er = norm32(res, er, 14)
        res = shr32_rz(res, 1)
    return mkfin_rz_ftz(sr, er, res << 10)


RCP_LUT_V1 = [
    0x7f, 0x7d, 0x7b, 0x79, 0x77, 0x75, 0x74, 0x72, 0x70, 0x6f, 0x6d, 0x6c,
    0x6b, 0x69, 0x68, 0x67, 0x65, 0x64, 0x63, 0x62, 0x60, 0x5f, 0x5e, 0x5d,
    0x5c, 0x5b, 0x5a, 0x59, 0x58, 0x57, 0x56, 0x55, 0x54, 0x54, 0x53, 0x52,
    0x51, 0x50, 0x4f, 0x4f, 0x4e, 0x4d, 0x4c, 0x4c, 0x4b, 0x4a, 0x4a, 0x49,
    0x48, 0x48, 0x47, 0x46, 0x46, 0x45, 0x45, 0x44, 0x43, 0x43, 0x42, 0x42,
    0x41, 0x41, 0x40, 0x40,
]


def lt_rcp(x):
    sx, ex, fx = S(x), E(x), F(x)
    if not ex:
        return 0x7f800000
    er = 0xfd - ex
    fx = (fx + IONE) >> 10
    s0 = RCP_LUT_V1[fx >> 7 & 0x3f]
    s1 = (((1 << 21) - s0 * fx) * s0 >> 14) & 0xffffffffffffffff
    s1 = (s1 << 11) - IONE
    assert 0 <= s1 < IONE
    fr = s1
    if er <= 0:
        er, fr = 0, 0
    return sx << 31 | er << 23 | fr


def lt_dp(a, b):
    return lt_add3([lt_mul(x, y) for x, y in zip(a, b)])


def light_infinite(nrm, ldir, half, k, amb, dif, spc, scene):
    """pgraph_celsius_lt_full for one infinite light (mode 1), non-local
    eye, no colour material. All arguments are float32 bit patterns
    already through s2lt, as the LT holds them. Returns (col0, col1)."""
    ca = 0x3f800000
    zero = False
    cd = lt_dp(nrm, ldir)
    if S(cd):
        zero = True
    if zero:
        cd = 0
    cd = lt_mul(ca, cd)
    s = lt_dp(nrm, half)
    t = lts_add(s, k[0])
    if S(t):
        zero = True
    bm = lts_mul(s, k[1])
    b = lts_add(bm, k[2])
    rb = lt_rcp(b)
    cs = lts_mul(t, rb)
    if zero:
        cs = 0
    cs = lt_mul(ca, cs)
    col0 = list(scene)
    col0 = [lt_add(c, lt_mul(ca, a)) for c, a in zip(col0, amb)]
    col0 = [lt_add(c, lt_mul(cd, d)) for c, d in zip(col0, dif)]
    col1 = [lt_mul(cs, x) for x in spc]
    col1 = [lt_add(0, c) for c in col1]
    return col0, col1, {'cd': cd, 's': s, 't': t, 'b': b, 'rb': rb, 'cs': cs}
