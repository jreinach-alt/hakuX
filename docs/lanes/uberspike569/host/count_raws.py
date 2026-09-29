#!/usr/bin/env python3
"""Recount render_check's kept DIFF pairs (build/render/N.{spec,uber}.raw):
float- and 8-bit-differing pixels per pair, and the totals."""
import os
import struct
import sys

d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "build", "render")


def q8(x):
    return -1 if x != x else int(round(min(max(x, 0.0), 1.0) * 255.0))


ids = sorted(f[:4] for f in os.listdir(d) if f.endswith(".spec.raw"))
tot8 = pairs8 = 0
for i in ids:
    a = open(os.path.join(d, i + ".spec.raw"), "rb").read()
    b = open(os.path.join(d, i + ".uber.raw"), "rb").read()
    fa = struct.unpack("<%df" % (len(a) // 4), a)
    fb = struct.unpack("<%df" % (len(b) // 4), b)
    pf = p8 = 0
    for p in range(len(fa) // 4):
        if a[16 * p:16 * p + 16] != b[16 * p:16 * p + 16]:
            pf += 1
            if [q8(x) for x in fa[4 * p:4 * p + 4]] != [q8(x) for x in fb[4 * p:4 * p + 4]]:
                p8 += 1
    if p8:
        pairs8 += 1
        tot8 += p8
        print("%s float %d px, 8-bit %d px" % (i, pf, p8))
print("%d kept pairs; %d with 8-bit differences, %d px in all" % (len(ids), pairs8, tot8))
