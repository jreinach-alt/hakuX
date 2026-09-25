#!/usr/bin/env python3
"""Per-capture probe for Shade_model (#224): what the differing pixels are.

For each named test: the signed per-channel histogram of ours - golden over
the differing pixels, the distinct colours on each side inside the diff mask,
and the diff bbox.  usage: probe.py <captures dir> <goldens dir> test [...]
"""
import collections
import os
import sys

import numpy as np
from PIL import Image


def load(p):
    return np.asarray(Image.open(p).convert('RGB')).astype(int)


def main():
    caps, golds = sys.argv[1], sys.argv[2]
    for t in sys.argv[3:]:
        a = load(os.path.join(caps, 'Shade_model::' + t + '.png'))
        b = load(os.path.join(golds, t + '.png'))
        d = a - b
        m = np.abs(d).max(2) > 0
        print('==', t, 'diff px', int(m.sum()))
        if not m.any():
            continue
        ys, xs = np.nonzero(m)
        print('  bbox', xs.min(), ys.min(), xs.max(), ys.max())
        for ch, name in enumerate('RGB'):
            h = collections.Counter(d[..., ch][m].tolist())
            print('  %s %s' % (name, dict(sorted(h.most_common(8)))))
        for side, img in (('ours', a), ('gold', b)):
            c = collections.Counter(map(tuple, img[m].tolist()))
            print('  %s colours %d top %s' % (side, len(c), c.most_common(4)))


if __name__ == '__main__':
    main()
