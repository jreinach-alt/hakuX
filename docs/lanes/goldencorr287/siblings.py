#!/usr/bin/env python3
"""Sibling query for #287: goldens where console == ours != golden.

The console set K (hardware/runs/2026-09-19-calib/full/out/run1) differs
from the goldens on only a handful of captures; a sibling must be one of
them. For each capture where K != golden, compare K to our capture from an
emulator sweep (one directory per suite, captures1/Suite::Test.png).

    siblings.py K_DIR GOLDENS SWEEP_PREFIX
"""
import glob
import os
import sys

import numpy as np
from PIL import Image


def load(p):
    return np.asarray(Image.open(p).convert('RGBA')).astype(int)


def ndiff(a, b):
    if a.shape != b.shape:
        return -1
    return int(np.abs(a - b).any(axis=2).sum())


kdir, goldens, prefix = sys.argv[1:4]
ours = {}
for p in glob.glob(prefix + '-*/captures1/*.png'):
    ours[os.path.basename(p)] = p

rows = 0
for f in sorted(os.listdir(kdir)):
    if not f.endswith('.png') or '::' not in f:
        continue
    suite, test = f[:-4].split('::', 1)
    gp = os.path.join(goldens, suite, test + '.png')
    if not os.path.exists(gp):
        continue
    k = load(os.path.join(kdir, f))
    g = load(gp)
    kg = ndiff(k, g)
    if kg == 0:
        continue
    rows += 1
    op = ours.get(f)
    if op is None:
        print(f'{suite}::{test}\tK~golden {kg}\tours: no capture')
        continue
    o = load(op)
    print(f'{suite}::{test}\tK~golden {kg}\tours~K {ndiff(o, k)}\t'
          f'ours~golden {ndiff(o, g)}\tsibling={ndiff(o, k) == 0}')
print(f'{rows} captures where console != golden')
