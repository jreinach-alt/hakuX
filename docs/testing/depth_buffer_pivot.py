#!/usr/bin/env python3
"""Pivot Depth_buffer_fixed_function's residual on every axis its names encode.

Reproduces every table in docs/investigations/depth-buffer-is-floating-point-z.md.

Capture names factor the test completely:

    z16|z24 _ Cy|Cn _ FZy|FZn _ M<hex> [ _ZB ]

named at depth_format_fixed_function_tests.cpp:286 -- C is compress_z, FZ is
format.floating_point -- and _ZB is appended by the harness at
test_host.cpp:254. _ZB is NOT a visualisation: TestHost::SaveZBuffer writes the
raw depth bytes out of guest memory, so those captures compare stored depth
values directly with no shader on either side.

Usage:  depth_buffer_pivot.py <ours_dir> <goldens_dir>

  ours_dir     holds "Depth_buffer_fixed_function::z16_Cn_FZn_M000003.png" etc.
  goldens_dir  holds "Depth_buffer_fixed_function/z16_Cn_FZn_M000003.png" etc.
"""
import collections
import os
import sys

import numpy as np
from PIL import Image

SUITE = 'Depth_buffer_fixed_function'


def load(ours_dir, goldens_dir):
    gold_dir = os.path.join(goldens_dir, SUITE)
    rows, missing = [], []
    for f in sorted(os.listdir(ours_dir)):
        if not f.startswith(SUITE + '::'):
            continue
        name = f.split('::', 1)[1]
        g = os.path.join(gold_dir, name)
        if not os.path.exists(g):
            missing.append(name)
            continue
        a = np.asarray(Image.open(os.path.join(ours_dir, f)).convert('RGB')).astype(np.int16)
        b = np.asarray(Image.open(g).convert('RGB')).astype(np.int16)
        if a.shape != b.shape:
            missing.append(name + ' (shape)')
            continue
        signed = b - a
        d = np.abs(signed)
        nz = d > 0
        p = name[:-4].split('_')
        rows.append(dict(name=name[:-4], zfmt=p[0], c=p[1], fz=p[2], m=p[3],
                         buf='ZB' if p[-1] == 'ZB' else 'colour',
                         diff=int(nz.sum()), absum=int(d.sum()), maxd=int(d.max()),
                         le3=int((d[nz] <= 3).sum()) if nz.any() else 0,
                         ge16=int((d[nz] >= 16).sum()) if nz.any() else 0,
                         pos=int((signed[nz] > 0).sum()) if nz.any() else 0))
    return rows, missing


def pivot(rows, keyfn, title, total):
    cells = collections.defaultdict(list)
    for r in rows:
        cells[keyfn(r)].append(r)
    print('\n--- by %s ---' % title)
    print('%-18s %3s %12s %7s %8s %7s %7s %10s %6s'
          % (title, 'n', 'differing', 'share', 'mean|d|', '<=3', '>=16', 'gold>ours', 'exact'))
    for k, v in sorted(cells.items(), key=lambda kv: -sum(r['diff'] for r in kv[1])):
        d = sum(r['diff'] for r in v)
        s = sum(r['absum'] for r in v)
        print('%-18s %3d %12s %6.1f%% %8.2f %6.1f%% %6.1f%% %9.1f%% %6d'
              % (str(k), len(v), format(d, ','), 100.0 * d / max(total, 1), s / max(d, 1),
                 100.0 * sum(r['le3'] for r in v) / max(d, 1),
                 100.0 * sum(r['ge16'] for r in v) / max(d, 1),
                 100.0 * sum(r['pos'] for r in v) / max(d, 1),
                 sum(1 for r in v if r['diff'] == 0)))


def compression_is_reproduced(ours_dir, goldens_dir):
    """Cn/Cy differ as CAPTURES but must be identical as RESIDUALS -- that is
    what says we reproduce the hardware's compression delta rather than merely
    being insensitive to the flag."""
    gold_dir = os.path.join(goldens_dir, SUITE)
    pre = SUITE + '::'
    same = diff = captures_differ = 0
    for f in sorted(os.listdir(ours_dir)):
        if not f.startswith(pre) or '_Cn_' not in f:
            continue
        cy = f.replace('_Cn_', '_Cy_')
        if not os.path.exists(os.path.join(ours_dir, cy)):
            continue
        gn, gy = f[len(pre):], cy[len(pre):]
        if not (os.path.exists(os.path.join(gold_dir, gn)) and os.path.exists(os.path.join(gold_dir, gy))):
            continue
        L = lambda p: np.asarray(Image.open(p).convert('RGB')).astype(np.int16)
        an, ay = L(os.path.join(ours_dir, f)), L(os.path.join(ours_dir, cy))
        bn, by = L(os.path.join(gold_dir, gn)), L(os.path.join(gold_dir, gy))
        if not np.array_equal(an, ay) or not np.array_equal(bn, by):
            captures_differ += 1
        if np.array_equal(bn - an, by - ay):
            same += 1
        else:
            diff += 1
    print('\n--- compress_z: is the flag reproduced, or merely ignored? ---')
    print('  Cn/Cy pairs: %d' % (same + diff))
    print('  captures DIFFER between Cn and Cy in %d pairs (so the flag does something)' % captures_differ)
    print('  RESIDUAL identical in %d pairs, different in %d' % (same, diff))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    ours_dir, goldens_dir = sys.argv[1:3]
    rows, missing = load(ours_dir, goldens_dir)
    total = sum(r['diff'] for r in rows)
    print('%d captures scored, %d missing golden' % (len(rows), len(missing)))
    print('TOTAL differing channels: %s   abs-sum %s'
          % (format(total, ','), format(sum(r['absum'] for r in rows), ',')))
    exact = [r['name'] for r in rows if r['diff'] == 0]
    print('EXACT: %d%s' % (len(exact), (' -> %s' % exact[:10]) if exact else ''))

    pivot(rows, lambda r: r['buf'], 'buffer', total)
    pivot(rows, lambda r: r['zfmt'], 'z format', total)
    pivot(rows, lambda r: r['c'], 'compress_z', total)
    pivot(rows, lambda r: r['fz'], 'floating_point', total)
    pivot(rows, lambda r: r['m'], 'depth cutoff', total)
    pivot(rows, lambda r: r['zfmt'] + '/' + r['fz'], 'zfmt x float', total)
    pivot(rows, lambda r: r['zfmt'] + '/' + r['fz'] + '/' + r['buf'], 'zfmt x float x buffer', total)
    compression_is_reproduced(ours_dir, goldens_dir)


if __name__ == '__main__':
    main()
