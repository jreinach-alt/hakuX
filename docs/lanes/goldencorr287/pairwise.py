#!/usr/bin/env python3
"""Pairwise RGBA diff of named captures: count, bbox, max per channel.

    pairwise.py name=path.png [name=path.png ...]

Whole-frame comparison, every pixel (region, not point samples).
"""
import itertools
import sys

import numpy as np
from PIL import Image

caps = {}
for arg in sys.argv[1:]:
    name, path = arg.split('=', 1)
    im = np.asarray(Image.open(path).convert('RGBA')).astype(int)
    caps[name] = im
    print(f'{name:10s} {im.shape} {path}')

for a, b in itertools.combinations(caps, 2):
    x, y = caps[a], caps[b]
    if x.shape != y.shape:
        print(f'{a} vs {b}: shape {x.shape} != {y.shape}')
        continue
    d = np.abs(x - y)
    mask = d.any(axis=2)
    n = int(mask.sum())
    if n:
        ys, xs = np.nonzero(mask)
        bbox = (xs.min(), ys.min(), xs.max(), ys.max())
        print(f'{a} vs {b}: {n} px differ ({100*n/mask.size:.2f}%), '
              f'max rgb {d[..., :3].max()} max a {d[..., 3].max()}, bbox {bbox}')
    else:
        print(f'{a} vs {b}: identical (0 px)')
