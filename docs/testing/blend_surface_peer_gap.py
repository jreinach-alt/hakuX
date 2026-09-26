#!/usr/bin/env python3
"""Blend_surface across runs: determinism, GL vs Vulkan, and the gap to the peer branch.

Reproduces every number in
docs/investigations/blend-surface-is-already-fixed-on-the-peer-branch.md.

Usage:  blend_surface_peer_gap.py <pgraph_run_root> <goldens_root>

Each run dir's run_<tag>.log gives the exact xemu_version, which is what makes
the comparison a measurement rather than a guess -- the runs span two DIVERGENT
lines of development, and the version count (e.g. -381-) is per-branch, so it
orders commits only within one line.
"""
import os
import sys

import numpy as np
from PIL import Image

SUITE = 'Blend_surface'
# Runs chosen to show, in order: this lane's line (deterministic, GL == Vulkan),
# and the peer line where the suite is already substantially better.
INTEREST = ['score_nf_g1', 'score_nf_g2', 'score_nf_g3',      # GL,  66fdd6d7
            'score_nf_v1', 'score_nf_v2', 'score_nf_v3',      # VK,  66fdd6d7
            'score_cx_aborts', 'score_surfver',               # this lane, later
            'score_i60a1', 'score_i60a2',                     # peer, 1a879e56
            'score_i60b1', 'score_i60b2',                     # peer, a105a51a
            'score_i60c1', 'score_i60c2',                     # peer, 082bc0ac
            'score_i60d1', 'score_i60d2']                     # peer, 082bc0ac


def version_of(root, tag):
    p = os.path.join(root, f'run_{tag}.log')
    if os.path.exists(p):
        for line in open(p, errors='ignore'):
            if line.startswith('xemu_version:'):
                return line.split(':', 1)[1].strip()
    return '?'


def score(root, d, goldens):
    base = os.path.join(root, d)
    if not os.path.isdir(base):
        return None, None
    subs = [s for s in os.listdir(base) if os.path.isdir(os.path.join(base, s))]
    if not subs:
        return None, None
    sub = os.path.join(base, subs[0])
    per = {}
    for f in sorted(os.listdir(sub)):
        if not f.startswith(SUITE + '::'):
            continue
        name = f.split('::', 1)[1][:-4]
        g = os.path.join(goldens, SUITE, name + '.png')
        if not os.path.exists(g):
            continue
        a = np.asarray(Image.open(os.path.join(sub, f)).convert('RGB')).astype(np.int16)
        b = np.asarray(Image.open(g).convert('RGB')).astype(np.int16)
        if a.shape != b.shape:
            continue
        per[name] = int((np.abs(a - b) > 0).sum())
    return per, subs[0]


def main(root, goldens):
    print(f'{"dir":16s} {"xemu_version":26s} {"n":>3s} {"total":>10s} {"exact":>6s}')
    scores = {}
    for d in INTEREST:
        per, tag = score(root, d, goldens)
        if per is None:
            continue
        scores[d] = per
        print(f'{d:16s} {version_of(root, tag)[:26]:26s} {len(per):3d} '
              f'{sum(per.values()):10d} {sum(1 for v in per.values() if v == 0):6d}')

    print('\n=== GL vs Vulkan at the SAME commit: images, not just totals ===')
    g = os.path.join(root, 'score_nf_g1', 'nf_g1')
    v = os.path.join(root, 'score_nf_v1', 'nf_v1')
    if os.path.isdir(g) and os.path.isdir(v):
        same = differ = 0
        for f in sorted(os.listdir(g)):
            if not f.startswith(SUITE + '::'):
                continue
            pv = os.path.join(v, f)
            if not os.path.exists(pv):
                continue
            a = np.asarray(Image.open(os.path.join(g, f)).convert('RGB'))
            b = np.asarray(Image.open(pv).convert('RGB'))
            same += int(a.shape == b.shape and np.array_equal(a, b))
            differ += int(not (a.shape == b.shape and np.array_equal(a, b)))
        print(f'  byte-identical={same}  differ={differ}')

    print('\n=== per-capture: this lane vs the peer line ===')
    mine = scores.get('score_cx_aborts')
    peer = scores.get('score_i60a1')
    if mine and peer:
        rows = sorted(((mine[k] - peer[k], k, mine[k], peer[k])
                       for k in mine if k in peer), reverse=True)
        for delta, k, a, b in rows[:8]:
            print(f'  {k:28s} {a:8d} -> {b:8d}  {-delta:+9d}')
        print('  ...')
        for delta, k, a, b in rows[-3:]:
            print(f'  {k:28s} {a:8d} -> {b:8d}  {-delta:+9d}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
