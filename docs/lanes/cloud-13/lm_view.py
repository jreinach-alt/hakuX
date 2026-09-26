#!/usr/bin/env python3
"""golden | ours | diff mask (red golden-only ink, green ours-only), cropped."""
import os
import sys

import numpy as np
from PIL import Image

G = os.path.expanduser("~/goldens/results")


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def main(cap, suite, test, out, crop=None, scale=1):
    a = load(os.path.join(G, suite, test + ".png"))
    b = load(os.path.join(cap, "%s::%s.png" % (suite, test)))
    d = np.abs(a - b).max(2)
    m = np.zeros_like(a)
    m[d > 8] = (255, 255, 0)
    m[(d > 0) & (d <= 8)] = (60, 60, 60)
    img = np.concatenate([a, b, m], 1)
    if crop:
        x0, y0, x1, y1 = crop
        w = a.shape[1]
        img = np.concatenate([a[y0:y1, x0:x1], b[y0:y1, x0:x1],
                              m[y0:y1, x0:x1]], 1)
    im = Image.fromarray(img.astype(np.uint8))
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(out)


if __name__ == "__main__":
    crop = tuple(int(v) for v in sys.argv[5].split(",")) if len(sys.argv) > 5 else None
    scale = int(sys.argv[6]) if len(sys.argv) > 6 else 1
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], crop, scale)
