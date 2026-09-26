#!/usr/bin/env python3
"""Where do white-on-one-side pixels fall?  (score_sweep.py's label test.)

    label_band.py golden.png ours.png

Prints the white-mismatch count in score_sweep's LABEL_ROWS=64 band and
below it, and the bbox of each, so the label check can be read against
where the text actually is.
"""
import sys

import numpy as np
from PIL import Image

g = np.asarray(Image.open(sys.argv[1]).convert('RGBA')).astype(int)
o = np.asarray(Image.open(sys.argv[2]).convert('RGBA')).astype(int)
gw = (g[..., :3] >= 250).all(axis=2)
ow = (o[..., :3] >= 250).all(axis=2)
wm = gw ^ ow
for name, sl in (('band <64', slice(0, 64)), ('body >=64', slice(64, None))):
    m = wm[sl]
    ys, xs = np.nonzero(m)
    off = sl.start or 0
    bbox = (xs.min(), ys.min() + off, xs.max(), ys.max() + off) if len(xs) else None
    print(f'{name}: {int(m.sum())} white-mismatch px, bbox {bbox}')
for name, w in (('golden', gw), ('ours', ow)):
    ys, xs = np.nonzero(w)
    print(f'{name}: {int(w.sum())} white px; rows with white: '
          f'{sorted(set(ys.tolist()))[:12]} ... {sorted(set(ys.tolist()))[-6:]}')
