#!/usr/bin/env python3
"""Route shots of two runs side by side, matched by shot label (sNN-...), with a mean absolute difference
on 64x48 greyscale (0 = same picture, ~10 = same screen with motion, 40+ = a different screen).
usage: shotdiff.py <result dir A> <result dir B>"""
import os
import sys

from PIL import Image

R = '/home/justin/hakux-work/dispatch/results'


def shots(d):
    d = d if d.startswith('/') else os.path.join(R, d)
    out = {}
    seen = {}
    for f in sorted(os.listdir(os.path.join(d, 'route-frames'))):
        lab = f.split('-', 1)[1].rsplit('.', 1)[0]
        seen[lab] = seen.get(lab, 0) + 1
        key = lab if seen[lab] == 1 else '%s#%d' % (lab, seen[lab])
        out[key] = os.path.join(d, 'route-frames', f)
    return out


def small(p):
    return list(Image.open(p).convert('L').resize((64, 48)).getdata())


a, b = shots(sys.argv[1]), shots(sys.argv[2])
for k in a:
    if k not in b:
        print('%-24s only in A' % k)
        continue
    pa, pb = small(a[k]), small(b[k])
    mad = sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)
    print('%-24s %6.1f  %s  %s' % (k, mad, os.path.basename(a[k]), os.path.basename(b[k])))
for k in b:
    if k not in a:
        print('%-24s only in B' % k)
