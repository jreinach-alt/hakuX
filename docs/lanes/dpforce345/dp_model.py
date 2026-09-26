#!/usr/bin/env python3
"""The #345 DP helpers as written in glsl/vsh-prog.c, in float32, against the
five silicon DP rows of docs/testing/xbox-special-raw-2026-09-25.md.

Models _MUL (a zero factor, NaN counting as 1, forces +0), _PosNaN, and
_DotZeroForced (the forced sum is used only when dot() is NaN). Prints each
row before and after, and exits 1 on any disagreement with silicon. The
DP3((-0,0,0),(5,5,5)) row is the registered control and takes a zero of
either sign.
"""
import math
import struct
import sys


def f(h):
    return struct.unpack("<f", struct.pack("<I", h))[0]


def r32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def bits(x):
    if math.isnan(x):
        return 0x7FC00000  # _PosNaN
    return struct.unpack("<I", struct.pack("<f", x))[0]


def ieee_mul(x, y):
    if (x == 0.0 and math.isinf(y)) or (y == 0.0 and math.isinf(x)):
        return math.nan
    return r32(x * y)


def ieee_dot(a, b):
    s = 0.0
    for x, y in zip(a, b):
        s = r32(s + ieee_mul(x, y))
    return s


def mul_forced(x, y):
    zx = 1.0 if math.isnan(x) else x
    zy = 1.0 if math.isnan(y) else y
    if zx == 0.0 or zy == 0.0:
        return 0.0
    return ieee_mul(x, y)


def dot_zero_forced(d, a, b):
    if not math.isnan(d):
        return d
    s = 0.0
    for x, y in zip(a, b):
        s = r32(s + mul_forced(x, y))
    return s


def dp3(a, b):
    return dot_zero_forced(ieee_dot(a[:3], b[:3]), a[:3] + [0.0], b[:3] + [0.0])


def dph(a, b):
    ah = a[:3] + [1.0]
    return dot_zero_forced(ieee_dot(ah, b), ah, b)


def dp4(a, b):
    return dot_zero_forced(ieee_dot(a, b), a, b)


ROWS = [  # op, a, b, silicon
    ("DP3", [0x00000000, 0x3F800000, 0x40000000, 0], [0x7F800000, 0x3F800000, 0x3F800000, 0], 0x40400000),
    ("DP3", [0x80000000, 0, 0, 0], [0x40A00000, 0x40A00000, 0x40A00000, 0], 0x00000000),
    ("DP3", [0, 0, 0, 0], [0x7FC00000, 0x3F800000, 0x3F800000, 0], 0x00000000),
    ("DP4", [0, 0x3F800000, 0x3F800000, 0x3F800000], [0x7F800000, 0x3F800000, 0x3F800000, 0x3F800000], 0x40400000),
    ("DP4", [0x3F800000, 0x3F800000, 0x3F800000, 0], [0x3F800000, 0x3F800000, 0x3F800000, 0x7FC00000], 0x40400000),
]
OPS = {"DP3": dp3, "DPH": dph, "DP4": dp4}

bad = 0
for op, a, b, sil in ROWS:
    fa, fb = [f(x) for x in a], [f(x) for x in b]
    before = ieee_dot(fa[:3], fb[:3]) if op == "DP3" else ieee_dot(fa, fb)
    after = OPS[op](fa, fb)
    ok = bits(after) == sil or (sil == 0 and after == 0.0)
    bad += not ok
    print("%s silicon=0x%08X before=0x%08X after=0x%08X %s"
          % (op, sil, bits(before), bits(after), "ok" if ok else "DIFFERS"))

# DPH's implicit w=1 term is not forced: 1 is not a zero, so 1 x NaN stays NaN.
print("DPH (0,0,0).(inf,1,1,5) = %r" % dph([0.0, 0.0, 0.0, 9.0], [math.inf, 1.0, 1.0, 5.0]))
print("DPH (1,0,0).(1,1,1,NaN) = %r" % dph([1.0, 0.0, 0.0, 9.0], [1.0, 1.0, 1.0, math.nan]))
print("%d / %d silicon DP rows agree" % (len(ROWS) - bad, len(ROWS)))
sys.exit(1 if bad else 0)
