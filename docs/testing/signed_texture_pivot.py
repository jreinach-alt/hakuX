#!/usr/bin/env python3
"""Measure Texture_signed_component_tests per signed-channel mask.

Reproduces every table in
docs/investigations/signed-textures-gl-has-no-snorm-path.md.

texture_signed_component_tests.cpp:84-87 names the mask bits: 0x01 signed
ALPHA, 0x02 red, 0x04 green, 0x08 blue, fed to NV097_SET_TEXTURE_FILTER's
[ARGB]SIGNED bits.

The second table is the control that makes the first one mean anything. Eight
masks are byte-exact, which proves we are right only if the flag actually
changes pixels -- so each mask is also compared against 0x0000 to show how much
the GOLDEN moves and how much OURS moves. The test prints the active flags into
its own on-screen label, so the top 40 rows are excluded: that band accounts for
98-130 channels and would otherwise be mistaken for image content.

Usage:  signed_texture_pivot.py <ours_dir> <goldens_dir>
"""
import os
import sys

import numpy as np
from PIL import Image

SUITE = 'Texture_signed_component_tests'
LABEL_ROWS = 40


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    ours_dir, goldens_dir = sys.argv[1:3]
    gold_dir = os.path.join(goldens_dir, SUITE)
    load = lambda p: np.asarray(Image.open(p).convert('RGB')).astype(np.int16)
    ours = lambda n: load(os.path.join(ours_dir, '%s::%s.png' % (SUITE, n)))
    gold = lambda n: load(os.path.join(gold_dir, '%s.png' % n))

    names = sorted(f.split('::', 1)[1][:-4] for f in os.listdir(ours_dir)
                   if f.startswith(SUITE + '::'))
    rows = []
    for n in names:
        try:
            a, b = ours(n), gold(n)
        except FileNotFoundError:
            continue
        d = np.abs(a - b)
        nz = int((d > 0).sum())
        rows.append((n, nz, int(d.sum()), int(d.max())))
    total = sum(r[1] for r in rows)
    print('%d captures, TOTAL differing %s' % (len(rows), format(total, ',')))

    print('\n--- every capture ---')
    print('%-24s %10s %7s %8s %5s' % ('capture', 'differing', 'share', 'mean|d|', 'max'))
    for n, nz, s, mx in sorted(rows, key=lambda r: -r[1]):
        print('%-24s %10s %6.1f%% %8.2f %5d'
              % (n, format(nz, ','), 100.0 * nz / max(total, 1), s / max(nz, 1), mx))

    masks = [r for r in rows if '_0x' in r[0]]
    print('\n--- the sixteen masks (%s of the suite) ---'
          % ('%.1f%%' % (100.0 * sum(r[1] for r in masks) / max(total, 1))))
    print('%-8s %2s %2s %2s %2s %10s %8s %5s' % ('mask', 'A', 'R', 'G', 'B', 'differing', 'mean|d|', 'max'))
    for n, nz, s, mx in sorted(masks, key=lambda r: int(r[0][-4:], 16)):
        m = int(n[-4:], 16)
        print('%-8s %2s %2s %2s %2s %10s %8.2f %5d'
              % (n[-6:], 'A' if m & 1 else '-', 'R' if m & 2 else '-',
                 'G' if m & 4 else '-', 'B' if m & 8 else '-',
                 format(nz, ','), s / max(nz, 1), mx))

    print('\n--- CONTROL: does the flag move real pixels, and do we move with it? ---')
    print('    (top %d rows excluded -- the test prints the flags into its own label)' % LABEL_ROWS)
    base = names[0] if names[0].endswith('0x0000') else 'A8R8G8B8_0x0000'
    try:
        bo, bg = ours(base), gold(base)
    except FileNotFoundError:
        print('  baseline %s not present; skipped' % base)
        return
    print('%-14s %14s %14s %10s %10s' % ('flag', 'golden moves', 'ours moves', 'label(g)', 'label(o)'))
    for m, lab in [(1, 'A'), (2, 'R'), (4, 'G'), (8, 'B'), (15, 'ARGB')]:
        n = 'A8R8G8B8_0x%04X' % m
        try:
            o, g = ours(n), gold(n)
        except FileNotFoundError:
            continue
        do = (np.abs(o - bo) > 0).any(axis=2)
        dg = (np.abs(g - bg) > 0).any(axis=2)
        print('%-14s %14s %14s %10d %10d'
              % ('0x%04X %s' % (m, lab), format(int(dg[LABEL_ROWS:].sum()), ','),
                 format(int(do[LABEL_ROWS:].sum()), ','),
                 int(dg[:LABEL_ROWS].sum()), int(do[:LABEL_ROWS].sum())))


if __name__ == '__main__':
    main()
