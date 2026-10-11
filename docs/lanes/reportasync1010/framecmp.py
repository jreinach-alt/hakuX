#!/usr/bin/env python3
"""framecmp.py -- NFS race-start route frames, arm against arm, by region.

  framecmp.py A_RUN B_RUN [--floor C_RUN D_RUN] [--shot go] [--skip go4,go9]

For each start (shot names `goN`/`gameplay`, or `sN-g11` with --shot g11) present in both runs, the mean absolute
difference (0-255, RGB) of the two frames in each named region, and in each cell of a 4x4 grid. `--floor` reads a
second pair of runs (two runs of one arm) and prints the same numbers, so the A/B column has a noise floor beside it:
a region that moves on A/B but not on the floor is the switch, one that moves on both is the scene (opponent cars
and the flag-waver animate at the start line; the camera does not move until GO).

Regions (fractions of the frame, x0 y0 x1 y1): sky (top band, where the sun glare and lens flare draw), road
(centre, the start line and the cars ahead), player (bottom centre: the player's car), hud_place (top right:
position and timer), map and speedo (bottom corners).
"""
import argparse
import os
import re
import sys

import numpy as np
from PIL import Image

REGIONS = {
    'sky':       (0.00, 0.06, 1.00, 0.30),
    'road':      (0.20, 0.30, 0.80, 0.62),
    'player':    (0.25, 0.55, 0.75, 0.95),
    'hud_place': (0.66, 0.06, 0.98, 0.30),
    'map':       (0.02, 0.62, 0.30, 0.95),
    'speedo':    (0.70, 0.62, 0.98, 0.95),
}


def shots(run, kind):
    d = os.path.join(run, 'route-frames')
    out = {}
    for f in sorted(os.listdir(d)):
        m = re.match(r'^\d+-(.+)\.png$', f)
        if not m:
            continue
        n = m.group(1)
        if kind == 'go' and (n == 'gameplay' or re.fullmatch(r'go\d+', n)):
            out['go1' if n == 'gameplay' else n] = os.path.join(d, f)
        elif kind == 'g11' and re.fullmatch(r's\d+-g11', n):
            out['go' + n[1:].split('-')[0]] = os.path.join(d, f)
    return out


def load(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)


def diff(a, b):
    h, w = a.shape[:2]
    d = np.abs(a - b).mean(axis=2)
    reg = {}
    for k, (x0, y0, x1, y1) in REGIONS.items():
        reg[k] = float(d[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)].mean())
    grid = [[float(d[i * h // 4:(i + 1) * h // 4, j * w // 4:(j + 1) * w // 4].mean()) for j in range(4)]
            for i in range(4)]
    return reg, grid


def pair(a, b, kind, skip):
    sa, sb = shots(a, kind), shots(b, kind)
    keys = sorted(set(sa) & set(sb) - skip, key=lambda k: int(k[2:]))
    rows = {}
    for k in keys:
        rows[k] = diff(load(sa[k]), load(sb[k]))
    return rows, sorted(set(sa) ^ set(sb))


def show(label, rows, missing):
    print(f'{label}: {len(rows)} starts compared' + (f'; in one run only: {", ".join(missing)}' if missing else ''))
    print('  start   ' + ' '.join(f'{k:>9s}' for k in REGIONS) + '   grid max')
    for k, (reg, grid) in rows.items():
        gm = max(max(r) for r in grid)
        print(f'  {k:7s} ' + ' '.join(f'{reg[r]:9.1f}' for r in REGIONS) + f'   {gm:8.1f}')
    if rows:
        med = {r: float(np.median([v[0][r] for v in rows.values()])) for r in REGIONS}
        print('  median  ' + ' '.join(f'{med[r]:9.1f}' for r in REGIONS))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--floor', nargs=2, metavar=('C', 'D'))
    ap.add_argument('--shot', choices=('go', 'g11'), default='go')
    ap.add_argument('--skip', default='', help='comma list of starts to leave out (dropped by raread.py)')
    a = ap.parse_args()
    skip = set(x for x in a.skip.split(',') if x)
    show(f'A/B {os.path.basename(a.a)} vs {os.path.basename(a.b)}', *pair(a.a, a.b, a.shot, skip))
    if a.floor:
        show(f'floor {os.path.basename(a.floor[0])} vs {os.path.basename(a.floor[1])}',
             *pair(a.floor[0], a.floor[1], a.shot, skip))


if __name__ == '__main__':
    sys.exit(main())
