"""The proposed GLSL, transcribed op for op into numpy float32 (IEEE RNE, no
FMA -- the same assumptions psh.c's Dekker floor already makes of the driver),
checked against exact-rational round-toward-zero on every vertex the tests
draw and on a random sweep.
"""
import os
import random
import struct
import sys
from fractions import Fraction as F

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import model  # noqa: E402
import price  # noqa: E402
import dbff  # noqa: E402

f = np.float32
np.seterr(all="ignore")


def bits(x):
    return int(np.array([x], dtype=np.float32).view(np.uint32)[0])


def frombits(u):
    return np.array([u & 0xFFFFFFFF], dtype=np.uint32).view(np.float32)[0]


def trunc_fix(r, e):
    # ffTrunc: step one ulp toward zero when the exact value lies nearer zero
    if r != 0 and e != 0 and ((e < 0) != (r < 0)) and np.isfinite(r):
        return frombits(bits(r) - 1)
    return r


def split(a):
    c = f(f(4097.0) * a)
    h = f(c - f(c - a))
    return h, f(a - h)


def two_prod(a, b):
    p = f(a * b)
    ah, al = split(a)
    bh, bl = split(b)
    e = f(f(f(f(f(ah * bh) - p) + f(ah * bl)) + f(al * bh)) + f(al * bl))
    return p, e


def mul_rtz(a, b):
    a, b = f(a), f(b)
    if not (abs(a) < f(1e34) and abs(b) < f(1e34)):
        return f(a * b)
    p, e = two_prod(a, b)
    return trunc_fix(p, e)


def add_rtz(a, b):
    a, b = f(a), f(b)
    s = f(a + b)
    bb = f(s - a)
    e = f(f(a - f(s - bb)) + f(b - bb))
    return trunc_fix(s, e)


def gt1(p, e):
    return p > 1 or (p == 1 and e > 0)


def rcp_rtz(w, gpu_err=0):
    w = f(w)
    aw = f(abs(w))
    r = f(f(1.0) / aw)
    if gpu_err:  # model a sloppy GPU reciprocal
        r = frombits(bits(r) + gpu_err)
    if aw < f(1e34) and aw > f(1e-34):
        for _ in range(3):
            p, e = two_prod(aw, r)
            if gt1(p, e):
                r = frombits(bits(r) - 1)
        for _ in range(3):
            rn = frombits(bits(r) + 1)
            p, e = two_prod(aw, rn)
            if not gt1(p, e):
                r = rn
    return f(-r) if w < 0 else r


def glsl_z(zw, c22, c32, gpu_err=0):
    zc = add_rtz(mul_rtz(f(zw), f(c22)), f(c32))
    w = add_rtz(mul_rtz(f(zw), f(1.0)), f(7.0))
    return mul_rtz(zc, rcp_rtz(w, gpu_err))


def ref_z(zw, c22, c32):
    zw = F(float(f(zw)))
    p = model.rnd(zw * c22, 'rtz')
    zc = model.rnd(p + c32, 'rtz')
    w = model.rnd(zw + 7, 'rtz')
    r = model.rnd(1 / w, 'rtz')
    return model.rnd(zc * r, 'rtz')


if __name__ == "__main__":
    fmts = [("z16", 65535.0), ("z24", 16777215.0),
            ("z16f", struct.unpack("f", struct.pack("I", 0x43FFF800))[0]),
            ("z24f", struct.unpack("f", struct.pack("I", 0x7149F2CA))[0])]
    zs = sorted({float(p[5]) for p in dbff.primitives()} | {float(p[6]) for p in dbff.primitives()}
                | {180.0, 192.0})
    random.seed(272)
    rnd_z = [float(f(random.uniform(-6.5, 400.0))) for _ in range(4000)]
    tot = bad = 0
    for name, vp in fmts:
        c22, c32 = price.consts(vp)
        for gpu_err in (0, -2, -1, 1, 2):
            nb = 0
            for zw in zs + rnd_z:
                if abs(zw + 7) < 1e-3:
                    continue
                got = F(float(glsl_z(zw, float(c22), float(c32), gpu_err)))
                want = ref_z(zw, c22, c32)
                tot += 1
                if got != want:
                    nb += 1
                    if nb <= 3:
                        print("  MISMATCH %s err%+d z=%r got %r want %r" % (name, gpu_err, zw, float(got), float(want)))
            bad += nb
            print("%-5s gpu rcp err %+d ulp: %d vertices, %d mismatches" % (name, gpu_err, len(zs) + len(rnd_z), nb))
    # component checks on random operands, including negatives and mixed magnitudes
    nb = n = 0
    for _ in range(20000):
        a = f(random.choice([-1, 1]) * 2 ** random.uniform(-20, 40))
        b = f(random.choice([-1, 1]) * 2 ** random.uniform(-20, 40))
        n += 3
        if F(float(mul_rtz(a, b))) != model.rnd(F(float(a)) * F(float(b)), 'rtz'):
            nb += 1
        if F(float(add_rtz(a, b))) != model.rnd(F(float(a)) + F(float(b)), 'rtz'):
            nb += 1
        if F(float(rcp_rtz(a))) != model.rnd(1 / F(float(a)), 'rtz'):
            nb += 1
    print("random operands: %d ops, %d mismatches" % (n, nb))
    print("TOTAL vertex mismatches %d of %d" % (bad, tot))
