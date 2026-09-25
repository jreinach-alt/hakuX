#!/usr/bin/env python3
"""Classify the Shade_model residual (#224) by path x primitive x shade mode.

Reuses lane.wparam223's split() (docs/lanes/wparam223/wparam_split.py, PR #228)
for the wash / coverage / value split of each capture; this file only groups.
Test names are <path>_<primitive>_<Flat|Smooth>_<First|Last>, where path is
Fixed, FixedTex, Prog, ProgTex, ProgLM, W_Fixed or W_FixedTex.

usage: shade_split.py <captures dir> <goldens Shade_model dir>
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'wparam223'))
from wparam_split import split  # noqa: E402

KEYS = ('diff', 'small', 'cov', 'value')


def table(title, rows, key):
    agg = collections.defaultdict(collections.Counter)
    for test, r in rows:
        k = key(test)
        for f in KEYS:
            agg[k][f] += r[f]
        agg[k]['n'] += 1
    print('\n%-24s %3s %9s %9s %9s %9s' % (title, 'n', 'diff', 'wash', 'cov', 'value'))
    for k, v in sorted(agg.items(), key=lambda kv: -kv[1]['diff']):
        print('%-24s %3d %9d %9d %9d %9d' % (k, v['n'], v['diff'], v['small'], v['cov'], v['value']))


def main():
    caps, golds = sys.argv[1], sys.argv[2]
    rows = []
    for f in sorted(os.listdir(golds)):
        cap = os.path.join(caps, 'Shade_model::' + f)
        if not os.path.exists(cap):
            print('MISSING', f[:-4])
            continue
        rows.append((f[:-4], split(cap, os.path.join(golds, f))))
    parts = lambda t: t.split('_')  # noqa: E731
    path = lambda t: '_'.join(parts(t)[:-3])  # noqa: E731
    table('path', rows, path)
    table('shade', rows, lambda t: parts(t)[-2])
    table('path x shade', rows, lambda t: path(t) + ' ' + parts(t)[-2])
    table('primitive', rows, lambda t: parts(t)[-3])
    table('primitive x shade', rows, lambda t: parts(t)[-3] + ' ' + parts(t)[-2])
    table('TOTAL', rows, lambda t: 'total')


if __name__ == '__main__':
    main()
