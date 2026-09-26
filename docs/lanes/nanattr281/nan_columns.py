#!/usr/bin/env python3
"""Attrib_float NaN captures: what silicon draws per column, by region.

Usage: nan_columns.py <console_dir> <ours_dir>

Both dirs hold flat captures named 'Attrib_float::<name>.png'. Column geometry
is the test's own arithmetic (attribute_float_tests.cpp:143-154): inset 0.2,
seven slots of 0.1 of the width, each quad 0.8 of its slot; rows 0.3..0.9 of
the height. The quad's colour ramps from attribute_value[0] (top) to [1]
(bottom). Column 0 is a MOV-only passthrough shader; columns 1..6 MUL the
diffuse by 1.0, 0.0, -INF, +INF, -NaNq, +NaNq.
"""
import sys

import numpy as np
from PIL import Image

W, H = 640, 480
COLS = [(int((0.2 + i * 0.1) * W), int((0.2 + i * 0.1) * W) + int(0.08 * W)) for i in range(7)]
MUL = ['passthru', 'x1.0', 'x0.0', 'x-INF', 'x+INF', 'x-NaNq', 'x+NaNq']
# Interior of every quad: two pixels in from each edge, clear of the text.
TOP, BOT = int(0.3 * H) + 2, int(0.9 * H) - 2
NAMES = ['0_1', '-INF_INF', '-Max_Max', '-NaNq_NaNq', '-NaNs_NaNs']


def load(d, n):
    return np.asarray(Image.open(f'{d}/Attrib_float::{n}.png').convert('RGB')).astype(int)


def region(img, i):
    l, r = COLS[i]
    return img[TOP:BOT, l + 2:r - 2]


def main(kdir, odir):
    k = {n: load(kdir, n) for n in NAMES}
    o = {n: load(odir, n) for n in NAMES}

    print('=== console column 0 (MOV passthrough) against other captures, whole interior ===')
    for a in ('-NaNq_NaNq', '-NaNs_NaNs'):
        for b in ('0_1', '-INF_INF', '-Max_Max', '-NaNq_NaNq'):
            if a == b:
                continue
            d = int((region(k[a], 0) != region(k[b], 0)).any(2).sum())
            print(f'  {a:11s} vs {b:11s}: {d:6d} px differ of {region(k[a], 0).shape[0] * region(k[a], 0).shape[1]}')

    print('\n=== per column: distinct colours in the interior, console | ours ===')
    for n in ('-NaNq_NaNq', '-NaNs_NaNs', '-INF_INF'):
        print(f'  {n}')
        for i in range(7):
            kr, orr = region(k[n], i).reshape(-1, 3), region(o[n], i).reshape(-1, 3)
            ku, ou = np.unique(kr, axis=0), np.unique(orr, axis=0)
            diff = int((region(k[n], i) != region(o[n], i)).any(2).sum())
            print(f'    {MUL[i]:8s} console {len(ku):4d} [{ku[0].tolist()}..{ku[-1].tolist()}]'
                  f' | ours {len(ou):4d} [{ou[0].tolist()}..{ou[-1].tolist()}]  differ={diff}')

    print('\n=== whole-frame console vs ours ===')
    for n in NAMES:
        m = (k[n] != o[n]).any(2)
        print(f'  {n:11s} total={int(m.sum()):6d} per col=' + str([int(m[:, l:r].sum()) for l, r in COLS]))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
