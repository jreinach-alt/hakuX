#!/usr/bin/env python3
"""#303 region scorer: green-tinted cells per frame.

A pixel is tinted when G >= 40, G >= 1.7 R and G >= 2.5 B. A cell is 32x32
screen px (one 16x16 guest macroblock at ~2x). It counts as green when more
than half its pixels are tinted, and as lit when more than half have
R+G+B > 60. Prints green/lit per frame.

Validated on the Nova soak (gamecheck/spikeout-soak): f00028 (bad) 477/887,
f00054 and f00058 (clean) 0/259 and 0/858. An R<=6 predicate does NOT carry
over to Thor, whose green is (117,251,76), (59,133,36): it read 0 on frames
that are visibly green.

usage: green_cells.py FRAME.png|FRAMES_DIR ...
"""
import os
import sys

import numpy as np
from PIL import Image


def measure(path):
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    sig = (g >= 40) & (g * 10 >= r * 17) & (g * 10 >= b * 25)
    H, W = sig.shape
    h, w = H // 32 * 32, W // 32 * 32
    cells = sig[:h, :w].reshape(h // 32, 32, w // 32, 32).mean(axis=(1, 3)) > 0.5
    lit = (a[:h, :w].sum(axis=2) > 60).reshape(
        h // 32, 32, w // 32, 32).mean(axis=(1, 3)) > 0.5
    return int(cells.sum()), int(lit.sum())


if __name__ == '__main__':
    for p in sys.argv[1:]:
        if os.path.isdir(p):
            fs = sorted(os.listdir(p))
            print('==', p)
            print(' '.join('%s:%d/%d' % ((f[4:6],) + measure(os.path.join(p, f)))
                           for f in fs))
        else:
            print(p, measure(p))
