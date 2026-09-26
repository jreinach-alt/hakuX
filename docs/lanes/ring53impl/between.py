#!/usr/bin/env python3
"""List the stream pgraph weighed between each fixed-function lit draw and the
next lit program draw, from a `dc_run.py --methods` ring.log.

    between.py <ring.log> [N]     N: which FF->VS gap to print in full (0-based)

For every gap prints the number of weighed words, the vertices of any draw in
between, and the implemented phase. With N, prints each method address and a
count, in first-seen order, so a gap's composition can be read.
"""
import collections
import sys

WEIGHT0 = {0x100, 0x294, 0x17FC}


def weight(m):
    if m in WEIGHT0:
        return 0
    if 0x1500 <= m < 0x16D0 or 0x1800 <= m < 0x181C or 0x1880 <= m < 0x1B00:
        return 0
    if 0xB00 <= m < 0xC00 and ((m >> 2) & 3) != 3:
        return 0
    return 1


def main():
    lines = open(sys.argv[1]).read().split("\n")
    want = int(sys.argv[2]) if len(sys.argv) > 2 else None
    gaps, cur, verts, in_gap = [], None, 0, False
    for l in lines:
        f = l.split()
        if not f:
            continue
        if f[0] == "RING53M":
            if in_gap:
                cur.append(int(f[1], 16))
        elif f[0] == "RING53":
            kind = f[1]
            n = int(f[2][2:])
            p = f[-1]
            if kind == "FFlit" and int(f[3][3:]):
                cur, verts, in_gap = [], 0, True
            elif kind == "VSlit" and in_gap and n:
                gaps.append((cur, verts, p))
                in_gap = False
            elif in_gap:
                verts += n
    for i, (ms, v, p) in enumerate(gaps):
        w = sum(weight(m) for m in ms)
        print("gap %2d: %5d words, weighed %4d, draw vertices %3d, first VS %s, total mod 6 = %d"
              % (i, len(ms), w, v, p, (w + v) % 6))
        if want == i:
            c = collections.OrderedDict()
            for m in ms:
                c[m] = c.get(m, 0) + 1
            for m, k in c.items():
                print("    %04x x%-4d w%d" % (m, k, weight(m)))


if __name__ == "__main__":
    main()
