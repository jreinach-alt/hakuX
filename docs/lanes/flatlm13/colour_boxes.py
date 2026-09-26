#!/usr/bin/env python3
"""Every ink colour in an image, named by kTestDiffuse vertex, with its bbox.

  colour_boxes.py IMG [IMG ...]
"""
import collections
import sys

import numpy as np
from PIL import Image

DIFFUSE = [0xFF0000, 0x00FF00, 0x0000FF, 0xCCCCCC, 0xFF33CC, 0xFFCC33,
           0xCCFF33, 0x33FFCC, 0x33CCFF, 0xCC33FF, 0x991111, 0x119911,
           0x111199, 0x666666]
NAMES = {tuple((c >> s) & 255 for s in (0, 8, 16)): "v%d" % i
         for i, c in enumerate(DIFFUSE)}

for p in sys.argv[1:]:
    a = np.asarray(Image.open(p).convert("RGB")).astype(int)
    print(p, a.shape)
    cols = collections.Counter(map(tuple, a.reshape(-1, 3)))
    for c, n in cols.most_common(14):
        m = np.all(a == c, axis=2)
        ys, xs = np.nonzero(m)
        print("  %-18s %7d  x %3d-%3d  y %3d-%3d"
              % (NAMES.get(c, c), n, xs.min(), xs.max(), ys.min(), ys.max()))
