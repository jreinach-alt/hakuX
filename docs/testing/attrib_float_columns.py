#!/usr/bin/env python3
"""Attrib_float: determinism, per-multiplier-column isolation, and the two populations.

Reproduces every number in
docs/investigations/attrib-float-is-nantoone-and-the-colour-floor.md.

Usage:  attrib_float_columns.py <pgraph_run_root> <goldens_root>

The suite draws SEVEN columns of one quad each: a plain passthrough, then six
where a vertex shader multiplies the diffuse colour by 1.0, 0.0, -INF, +INF,
-NaNq, +NaNq (attribute_float_tests.cpp:139-140). So even the mundane "0 to 1"
capture carries infinities and NaNs -- via the MULTIPLIER, not the attribute.
Column geometry is derived from the test's own arithmetic (inset 0.2, six
columns over 0.6 of the width, each drawn 0.8 of its slot).
"""
import os
import sys

import numpy as np
from PIL import Image

SUITE = 'Attrib_float'
MUL = ['passthru', 'x1.0', 'x0.0', 'x-INF', 'x+INF', 'x-NaNq', 'x+NaNq']
NAMES = ['0_1', '0_8', '-1_1', '-8_1', '-INF_INF', '-Max_Max', '-MinN_MinN',
         '-NaNq_NaNq', '-NaNs_NaNs', '-MaxSN_MaxSN', '-Min_Min']
W, H = 640, 480
TOP, BOT = 144, 432


def column_bounds():
    out = []
    for i in range(7):
        left = int((0.2 + i * 0.10) * W)
        out.append((left, left + int(0.8 * 0.10 * W)))
    return out


def version_of(root, tag):
    p = os.path.join(root, f'run_{tag}.log')
    if os.path.exists(p):
        for line in open(p, errors='ignore'):
            if line.startswith('xemu_version:'):
                return line.split(':', 1)[1].strip()
    return '?'


def runs_with_suite(root):
    out = []
    for d in sorted(os.listdir(root)):
        full = os.path.join(root, d)
        if not d.startswith('score_') or not os.path.isdir(full):
            continue
        for s in os.listdir(full):
            sub = os.path.join(full, s)
            if os.path.isdir(sub) and any(f.startswith(SUITE + '::') for f in os.listdir(sub)):
                out.append((d, s, sub))
    return out


def pair(sub, goldens, name):
    a = np.asarray(Image.open(os.path.join(sub, f'{SUITE}::{name}.png')).convert('RGB')).astype(np.int16)
    b = np.asarray(Image.open(os.path.join(goldens, SUITE, f'{name}.png')).convert('RGB')).astype(np.int16)
    return a, b


def main(root, goldens):
    print('=== determinism: every run carrying the suite ===')
    runs = runs_with_suite(root)
    per_run = {}
    for d, tag, sub in runs:
        per = {}
        for n in NAMES:
            try:
                a, b = pair(sub, goldens, n)
            except FileNotFoundError:
                continue
            per[n] = int((np.abs(a - b) > 0).sum())
        per_run[d] = (sub, per)
        print(f'  {d:16s} {version_of(root, tag)[:26]:26s} total={sum(per.values()):8d} '
              f'exact={sum(1 for v in per.values() if v == 0)}')
    print(f'  distinct totals across {len(per_run)} runs: '
          f'{sorted({sum(p.values()) for _, p in per_run.values()})}')

    sub = per_run.get('score_cx_attr', (None, None))[0] or runs[-1][2]
    cols = column_bounds()

    print(f'\n=== differing pixels per multiplier column ({os.path.basename(sub)}) ===')
    print(f'{"capture":13s} ' + ' '.join(f'{m:>8s}' for m in MUL))
    for n in NAMES:
        a, b = pair(sub, goldens, n)
        m = (np.abs(a - b) > 0).any(axis=2)
        print(f'{n:13s} ' + ' '.join(f'{int(m[:, l:r].sum()):8d}' for l, r in cols))

    print('\n=== does each side RESPOND to the multiplier? (vs its own column 0) ===')
    for n in ('0_1', '-1_1', '-NaNq_NaNq', '-MinN_MinN'):
        a, b = pair(sub, goldens, n)
        ca = [a[TOP:BOT, l:r] for l, r in cols]
        cb = [b[TOP:BOT, l:r] for l, r in cols]
        print(f'  {n}')
        for i in range(1, 7):
            do = int((np.abs(ca[i] - ca[0]) > 0).sum())
            dg = int((np.abs(cb[i] - cb[0]) > 0).sum())
            print(f'    {MUL[i]:8s} ours={do:7d}  gold={dg:7d}')

    print('\n=== the two populations ===')
    for n, ci, label in (('-NaNq_NaNq', 0, 'NaN attribute'), ('0_1', 0, 'ordinary attribute')):
        l, r = cols[ci]
        a, b = pair(sub, goldens, n)
        m = (np.abs(a - b) > 0).any(axis=2)[:, l:r]
        ao, go = a[:, l:r][m], b[:, l:r][m]
        d = ao.astype(int) - go.astype(int)
        print(f'  {n} col0 ({label}): {int(m.sum())} px  '
              f'ours_unique={len(np.unique(ao, axis=0))} gold_unique={len(np.unique(go, axis=0))}  '
              f'delta min={d.min()} max={d.max()}  |d|<=2: {100.0 * (np.abs(d) <= 2).mean():.1f}%')
        if len(np.unique(ao, axis=0)) == 1:
            print(f'      ours is ONE colour: {np.unique(ao, axis=0)[0].tolist()}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
