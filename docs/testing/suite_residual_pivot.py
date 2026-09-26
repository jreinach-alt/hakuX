#!/usr/bin/env python3
"""Pivot a pgraph suite's residual by every axis its capture NAMES encode.

Reproduces every table in docs/investigations/3d-primitive-is-the-aa-surface.md.

The method this implements is the one that localised both Blend_tests and
3D_primitive without building a probe: score the captures, then pivot by each
axis the names encode, then look at the MAGNITUDE distribution and the SIGN
before forming any hypothesis. Capture names are the test author's own
factorisation of the test matrix and are free information.

For 3D_primitive the names are <Primitive>-<submission>[-ls][-ps]. Note that
-ls/-ps are NOT merely smoothing flags: three_d_primitive_tests.cpp:936 switches
the render surface to AA_CENTER_CORNER_2 when EITHER is set, so the arm this
prints as "AA" is the axis that actually matters.

Usage:  suite_residual_pivot.py <ours_dir> <goldens_dir> <suite>

  ours_dir     holds "<suite>::<name>.png"
  goldens_dir  holds "<suite>/<name>.png"
"""
import collections
import os
import sys

import numpy as np
from PIL import Image

LINE_PRIMS = ('Lines', 'LineStrip', 'LineLoop')
BUCKETS = [1, 2, 4, 8, 16, 32, 64, 128, 256]
BUCKET_LABELS = ['1', '2-3', '4-7', '8-15', '16-31', '32-63', '64-127', '128-255', '256+']


def classify(name):
    """Split a capture name into the axes it encodes."""
    parts = name[:-4].split('-') if name.endswith('.png') else name.split('-')
    prim = parts[0]
    flags = [p for p in parts[1:] if p in ('ls', 'ps')]
    method = '-'.join(p for p in parts[1:] if p not in ('ls', 'ps')) or 'default'
    group = 'LINES' if prim in LINE_PRIMS else ('POINTS' if prim == 'Points' else 'FILLED')
    return dict(prim=prim, method=method, group=group,
                ls='ls' in flags, ps='ps' in flags,
                aa='AA' if flags else 'no-AA')


def load(ours_dir, goldens_dir, suite):
    rows, missing = [], []
    for f in sorted(os.listdir(ours_dir)):
        if not f.startswith(suite + '::'):
            continue
        name = f.split('::', 1)[1]
        g = os.path.join(goldens_dir, suite, name)
        if not os.path.exists(g):
            missing.append(name)
            continue
        a = np.asarray(Image.open(os.path.join(ours_dir, f)).convert('RGB')).astype(np.int16)
        b = np.asarray(Image.open(g).convert('RGB')).astype(np.int16)
        if a.shape != b.shape:
            missing.append(name + ' (shape)')
            continue
        signed = b - a                      # golden - ours
        d = np.abs(signed)
        nz = d > 0
        r = classify(name)
        r.update(name=name[:-4], diff=int(nz.sum()), absum=int(d.sum()), maxd=int(d.max()),
                 hist=np.bincount(np.digitize(d[nz], BUCKETS[1:]),
                                  minlength=len(BUCKETS))[:len(BUCKETS)].astype(np.int64),
                 pos1=int((signed[d == 1] > 0).sum()), neg1=int((signed[d == 1] < 0).sum()),
                 posB=int((signed[d >= 16] > 0).sum()), negB=int((signed[d >= 16] < 0).sum()))
        rows.append(r)
    return rows, missing


def _cells(rows, keyfn):
    b = collections.OrderedDict()
    for r in rows:
        b.setdefault(keyfn(r), []).append(r)
    return b


def pivot(rows, keyfn, title, total):
    print('\n--- by %s ---' % title)
    print('%-20s %3s %12s %7s %13s %8s %6s' % (title, 'n', 'differing', 'share', 'abs-sum', 'mean|d|', 'exact'))
    cells = _cells(rows, keyfn)
    for k, v in sorted(cells.items(), key=lambda kv: -sum(r['diff'] for r in kv[1])):
        d = sum(r['diff'] for r in v)
        s = sum(r['absum'] for r in v)
        print('%-20s %3d %12s %6.1f%% %13s %8.2f %6d'
              % (str(k), len(v), format(d, ','), 100.0 * d / max(total, 1), format(s, ','),
                 s / max(d, 1), sum(1 for r in v if r['diff'] == 0)))


def magnitudes(rows):
    print('\n--- magnitude of |golden - ours| over differing channels ---')
    print('%-14s %12s ' % ('group', 'differing') + ' '.join('%8s' % l for l in BUCKET_LABELS))
    groups = [('ALL', lambda r: True)]
    groups += [(g, (lambda g: (lambda r: r['group'] == g))(g)) for g in ('FILLED', 'LINES', 'POINTS')]
    groups += [(p, (lambda p: (lambda r: r['prim'] == p))(p))
               for p in sorted({r['prim'] for r in rows})]
    for label, sel in groups:
        v = [r for r in rows if sel(r)]
        if not v:
            continue
        h = sum(r['hist'] for r in v)
        t = int(h.sum()) or 1
        print('%-14s %12s ' % (label, format(t, ',')) + ' '.join('%7.1f%%' % (100.0 * x / t) for x in h))


def signs(rows):
    print('\n--- sign of (golden - ours): is the one-step floor a CONVENTION or noise? ---')
    print('%-14s %17s %11s %9s    %19s %11s %9s'
          % ('group', '|d|=1: gold>ours', 'ours>gold', 'split', '|d|>=16: gold>ours', 'ours>gold', 'split'))
    groups = [('ALL', lambda r: True)]
    groups += [(g, (lambda g: (lambda r: r['group'] == g))(g)) for g in ('FILLED', 'LINES')]
    groups += [(p, (lambda p: (lambda r: r['prim'] == p))(p))
               for p in sorted({r['prim'] for r in rows})]
    for label, sel in groups:
        v = [r for r in rows if sel(r)]
        if not v:
            continue
        p1 = sum(r['pos1'] for r in v); n1 = sum(r['neg1'] for r in v)
        pB = sum(r['posB'] for r in v); nB = sum(r['negB'] for r in v)
        print('%-14s %17s %11s %8.1f%%    %19s %11s %8.1f%%'
              % (label, format(p1, ','), format(n1, ','), 100.0 * p1 / max(p1 + n1, 1),
                 format(pB, ','), format(nB, ','), 100.0 * pB / max(pB + nB, 1)))


def flag_cross(rows, total):
    """The cross-tabulation that exposed -ls moving the FILLED residual, which
    line smoothing cannot do -- and so led to the AA surface at :936."""
    print('\n--- smooth flags x primitive class (the cross-tab that caught the AA surface) ---')
    print('%-8s %3s %3s %3s %12s %13s %8s' % ('class', 'ls', 'ps', 'n', 'differing', 'abs-sum', 'mean|d|'))
    cells = _cells(rows, lambda r: (r['group'], 'ls' if r['ls'] else '--', 'ps' if r['ps'] else '--'))
    for k in sorted(cells):
        v = cells[k]
        d = sum(r['diff'] for r in v); s = sum(r['absum'] for r in v)
        print('%-8s %3s %3s %3d %12s %13s %8.2f'
              % (k[0], k[1], k[2], len(v), format(d, ','), format(s, ','), s / max(d, 1)))
    print('\n  effect of each flag on each class, against its own no-flag baseline:')
    for grp in ('FILLED', 'LINES', 'POINTS'):
        def tot(ls, ps):
            return sum(r['diff'] for r in rows if r['group'] == grp and r['ls'] == ls and r['ps'] == ps)
        base = tot(False, False)
        if not base:
            print('    %-8s baseline 0 (byte-exact) -> +ls %s  +ps %s  +both %s'
                  % (grp, format(tot(True, False), ','), format(tot(False, True), ','),
                     format(tot(True, True), ',')))
            continue
        print('    %-8s baseline %10s   +ls %+7.1f%%   +ps %+7.1f%%   +both %+7.1f%%'
              % (grp, format(base, ','), 100.0 * (tot(True, False) - base) / base,
                 100.0 * (tot(False, True) - base) / base, 100.0 * (tot(True, True) - base) / base))


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    ours_dir, goldens_dir, suite = sys.argv[1:4]
    rows, missing = load(ours_dir, goldens_dir, suite)
    total = sum(r['diff'] for r in rows)
    print('%d captures scored, %d missing golden' % (len(rows), len(missing)))
    if missing:
        print('  missing: %s' % missing[:5])
    print('TOTAL differing channels: %s   abs-sum %s'
          % (format(total, ','), format(sum(r['absum'] for r in rows), ',')))
    exact = [r['name'] for r in rows if r['diff'] == 0]
    print('EXACT: %d%s' % (len(exact), (' -> %s' % exact[:12]) if exact else ''))

    pivot(rows, lambda r: r['prim'], 'primitive', total)
    pivot(rows, lambda r: r['method'], 'submission', total)
    pivot(rows, lambda r: r['aa'], 'AA surface', total)
    pivot(rows, lambda r: r['aa'] + ' / ' + r['group'], 'AA surface x class', total)
    flag_cross(rows, total)
    magnitudes(rows)
    signs(rows)


if __name__ == '__main__':
    main()
