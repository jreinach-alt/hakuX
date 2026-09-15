#!/usr/bin/env python3
"""Window_clip: score every run that has the suite, in time order, and show that
the differing region is EXACTLY the window-clip rectangle.

Reproduces every number in
docs/investigations/window-clip-differs-by-exactly-the-clip-rect.md.

Usage:  window_clip_bisect.py <pgraph_run_root> <goldens_root>

Each run directory carries run_<tag>.log naming the exact xemu commit, so the
time series is a bisect, not a guess. Do NOT collapse this to a glob over
score_*/ and take the first hit -- the ~140 older dirs are different binaries,
and that is precisely how this suite first read as byte-exact when the corpus
binary is not.
"""
import datetime
import os
import sys

import numpy as np
from PIL import Image

SUITE = 'Window_clip'
# Scored alongside, as co-variation controls: if Window_clip's failures were a
# code regression these would not flake independently of it, and Viewport -- which
# is stable at 2,601 in 30 of 31 runs -- would not be stable across the boundary.
CONTROLS = ('Stencil', 'Viewport')


def score_dir(sub, goldens):
    return _score_suite(sub, goldens, SUITE)


def _score_suite(sub, goldens, SUITE):
    gd = os.path.join(goldens, SUITE)
    rows = []
    for f in sorted(os.listdir(sub)):
        if not f.startswith(SUITE + '::') or not f.endswith('.png'):
            continue
        name = f.split('::', 1)[1][:-4]
        g = os.path.join(gd, name + '.png')
        if not os.path.exists(g):
            continue
        a = np.asarray(Image.open(os.path.join(sub, f)).convert('RGB')).astype(np.int16)
        b = np.asarray(Image.open(g).convert('RGB')).astype(np.int16)
        if a.shape != b.shape:
            continue
        d = np.abs(a - b)
        rows.append((name, int((d > 0).sum()), int((d > 0).any(axis=2).sum())))
    return rows


def commit_of(root, tag):
    log = os.path.join(root, f'run_{tag}.log')
    if not os.path.exists(log):
        return '?'
    with open(log, errors='ignore') as fh:
        for line in fh:
            if line.startswith('xemu_version:'):
                return line.split(':', 1)[1].strip()
    return '?'


def main(root, goldens):
    print('=== every run carrying Window_clip, in time order ===')
    print(f'{"mtime(UTC)":14s} {"dir":24s} {"xemu_version":34s} {"n":>4s} {"channels":>10s} {"exact":>6s}')
    series = []
    for d in sorted(os.listdir(root)):
        full = os.path.join(root, d)
        if not d.startswith('score_') or not os.path.isdir(full):
            continue
        for s in os.listdir(full):
            sub = os.path.join(full, s)
            if not os.path.isdir(sub):
                continue
            rows = score_dir(sub, goldens)
            if not rows:
                continue
            ch = sum(r[1] for r in rows)
            ex = sum(1 for r in rows if r[1] == 0)
            series.append((os.path.getmtime(sub), d, s, len(rows), ch, ex))
    series.sort()
    for t, d, s, n, ch, ex in series:
        ts = datetime.datetime.utcfromtimestamp(t).strftime('%m-%d %H:%M')
        print(f'{ts:14s} {d[:24]:24s} {commit_of(root, s)[:34]:34s} {n:4d} {ch:10d} {ex:6d}'
              f'  {"BROKEN" if ch else "ok"}')

    print('\n=== co-variation with the control suites ===')
    print(f'{"mtime":12s} {"dir":22s} {"WinClip":>10s} {"ex":>3s} | '
          + ' | '.join(f'{c:>12s}' for c in CONTROLS))
    for t, d, s_, n, ch, ex in series:
        ts = datetime.datetime.utcfromtimestamp(t).strftime('%m-%d %H:%M')
        sub2 = os.path.join(root, d, s_)
        cells = []
        for c in CONTROLS:
            rows2 = [r for r in _score_suite(sub2, goldens, c)]
            cells.append(f'{sum(r[1] for r in rows2):12d}' if rows2 else f'{"-":>12s}')
        print(f'{ts:12s} {d[:22]:22s} {ch:10d} {ex:3d} | ' + ' | '.join(cells))

    broken = [x for x in series if x[4]]
    if not broken:
        print('\nno broken run found; nothing further to show')
        return
    sub = os.path.join(root, broken[-1][1], broken[-1][2])

    print(f'\n=== per-capture, worst run ({broken[-1][1]}) ===')
    rows = sorted(score_dir(sub, goldens), key=lambda r: -r[1])
    print(f'  total channels={sum(r[1] for r in rows)} captures={len(rows)} '
          f'exact={sum(1 for r in rows if r[1] == 0)}')
    for name, ch, px in rows[:4] + rows[-6:]:
        print(f'    ch={ch:9d} px={px:8d}  {name}')

    print('\n=== is the differing region EXACTLY the clip rectangle? ===')
    for name in ('E_x0y0_w256h256-x0y0_w0h0', 'E_x0y0_w255h255-x0y0_w0h0',
                 'E_x0y0_w1h1-x0y0_w0h0', 'E_x0y0_w0h0-x0y0_w0h0'):
        p = os.path.join(sub, f'{SUITE}::{name}.png')
        g = os.path.join(goldens, SUITE, f'{name}.png')
        if not (os.path.exists(p) and os.path.exists(g)):
            continue
        a = np.asarray(Image.open(p).convert('RGB')).astype(np.int16)
        b = np.asarray(Image.open(g).convert('RGB')).astype(np.int16)
        m = (np.abs(a - b) > 0).any(axis=2)
        ys, xs = np.where(m)
        w = name.split('_w')[1].split('h')[0]
        side = int(w) + 1 if w.isdigit() else -1
        box = np.zeros(m.shape, bool)
        box[0:side, 0:side] = True
        # (w+1) because the rect reads as inclusive of both bounds. w=256 is
        # the one case that does NOT match: it comes back 256x256, not 257x257,
        # so something clamps at 256. What sets that bound is NOT established
        # here -- it is reported, not explained.
        box = np.zeros(m.shape, bool)
        box[0:side, 0:side] = True
        print(f'  {name:32s} px={int(m.sum()):7d}  bbox x[{xs.min()}..{xs.max()}] '
              f'y[{ys.min()}..{ys.max()}]  expected {side}x{side}  exact? '
              f'{np.array_equal(m, box)}')
        inb = a[m]
        gin = b[m]
        print(f'      ours in region {np.unique(inb, axis=0)[:2].tolist()}   '
              f'gold {np.unique(gin, axis=0)[:2].tolist()}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
