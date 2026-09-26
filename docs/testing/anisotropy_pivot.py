#!/usr/bin/env python3
"""Texture_anisotropy: determinism across runs, and whether the residual is ours or the host's.

Reproduces every number in
docs/investigations/anisotropy-is-the-hosts-filter-not-ours.md and the
predictions in
docs/testing/predictions/2026-09-15-anisotropy-is-the-hosts-filter.md.

Usage:  anisotropy_pivot.py <pgraph_run_root> <goldens_root>

The determinism check reads ELEVEN runs already on disk rather than spending an
emulator run -- the run-twice rule satisfied from data we already had. Each run
dir's run_<tag>.log names the exact binary; do not assume, and do not glob
score_* and take the first hit (different binaries live side by side).
"""
import collections
import os
import sys

import numpy as np
from PIL import Image

SUITE = 'Texture_anisotropy'
LEVELS = ['Anisotropy-1', 'Anisotropy-2', 'Anisotropy-4', 'Anisotropy-8']


def version_of(root, tag):
    p = os.path.join(root, f'run_{tag}.log')
    if os.path.exists(p):
        for line in open(p, errors='ignore'):
            if line.startswith('xemu_version:'):
                return line.split(':', 1)[1].strip()
    return '?'


def load(sub, goldens, name):
    o = np.asarray(Image.open(os.path.join(sub, f'{SUITE}::{name}.png')).convert('RGB')).astype(np.int16)
    g = np.asarray(Image.open(os.path.join(goldens, SUITE, f'{name}.png')).convert('RGB')).astype(np.int16)
    return o, g


def main(root, goldens):
    print('=== determinism: every run carrying the suite ===')
    print(f'{"dir":16s} {"binary":26s} ' + ' '.join(f'{l[-1]:>9s}' for l in LEVELS) + '     total')
    runs = []
    for d in sorted(os.listdir(root)):
        full = os.path.join(root, d)
        if not d.startswith('score_') or not os.path.isdir(full):
            continue
        for s in os.listdir(full):
            sub = os.path.join(full, s)
            if not os.path.isdir(sub):
                continue
            if not any(f.startswith(SUITE + '::') for f in os.listdir(sub)):
                continue
            per = {}
            for name in LEVELS:
                try:
                    o, g = load(sub, goldens, name)
                except FileNotFoundError:
                    continue
                per[name] = int((np.abs(o - g) > 0).sum())
            if per:
                runs.append((d, s, per))
    for d, s, per in runs:
        cells = ' '.join(f'{per.get(n, -1):9d}' for n in LEVELS)
        print(f'{d:16s} {version_of(root, s)[:26]:26s} {cells} {sum(per.values()):9d}')
    totals = {sum(p.values()) for _, _, p in runs}
    print(f'  distinct totals across {len(runs)} runs: {sorted(totals)}')

    corpus = next((os.path.join(root, d, s) for d, s, _ in runs if d == 'score_cx_tex3'), None)
    if corpus is None:
        corpus = os.path.join(root, runs[-1][0], runs[-1][1])
    print(f'\n(using {corpus} for the rest)')

    print('\n=== P1: movement from Anisotropy-1, OURS vs HARDWARE, measured separately ===')
    ro, rg = load(corpus, goldens, LEVELS[0])
    print(f'{"level":14s} {"ours moves":>12s} {"gold moves":>12s} {"ratio":>9s}')
    for n in LEVELS[1:]:
        o, g = load(corpus, goldens, n)
        do = int((np.abs(o - ro) > 0).sum())
        dg = int((np.abs(g - rg) > 0).sum())
        print(f'{n:14s} {do:12d} {dg:12d} {do / dg if dg else float("nan"):8.2f}x')
    print('  KILL was ours/gold < 0.05 -- that would mean the setting never reaches the sampler.')

    print('\n=== P2: magnitude distribution (a filter differs broadly; quantisation does not) ===')
    h = collections.Counter()
    tot = 0
    for n in LEVELS:
        o, g = load(corpus, goldens, n)
        d = np.abs(o - g)
        v = d[d > 0]
        tot += v.size
        for k, c in zip(*np.unique(v, return_counts=True)):
            h[int(k)] += int(c)
    le2 = sum(c for k, c in h.items() if k <= 2)
    print(f'  differing channels={tot}  |d|<=2 = {100.0 * le2 / tot:.2f}% (P2 needs < 50%)  '
          f'max |d| = {max(h)}')
    print('  ' + '  '.join(f'|d|={k}:{100.0 * h[k] / tot:.1f}%' for k in sorted(h)[:6]))

    print('\n=== P2/C1: spatial extent ===')
    for n in LEVELS:
        o, g = load(corpus, goldens, n)
        m = (np.abs(o - g) > 0).any(axis=2)
        if not m.any():
            print(f'  {n:14s} no differing pixels')
            continue
        ys, xs = np.where(m)
        print(f'  {n:14s} px={int(m.sum()):7d} ({100.0 * m.sum() / m.size:5.2f}% of frame) '
              f'rows y[{ys.min()}..{ys.max()}] cols x[{xs.min()}..{xs.max()}]')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
