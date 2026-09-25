#!/usr/bin/env python3
"""Split every W_param capture's residual into three populations (#223).

  small : max-channel |d| in 1..2 -- the interpolation wash (#12's floor)
  cov   : |d| > 2 and exactly one side is the clear colour -- coverage
  value : |d| > 2 and both sides drew -- a wrong value inside the primitive

usage: wparam_split.py <captures dir> <goldens suite dir> [--all] [--suite S]
The captures dir holds '<S>::<test>.png' (dispatch/results/<id>/captures1);
S defaults to W_param.
"""
import collections
import os
import re
import sys

import numpy as np
from PIL import Image

CLEAR = np.array([0x25, 0x11, 0x35])  # PrepareDraw(0xFE251135)


def split(cap, gold):
    a = np.asarray(Image.open(cap).convert('RGB')).astype(int)
    b = np.asarray(Image.open(gold).convert('RGB')).astype(int)
    d = np.abs(a - b).max(2)
    a_bg = np.abs(a - CLEAR).max(2) <= 2
    b_bg = np.abs(b - CLEAR).max(2) <= 2
    big = d > 2
    cov = big & (a_bg ^ b_bg)
    val = big & ~cov
    out = dict(diff=int((d > 0).sum()), small=int(((d > 0) & ~big).sum()),
               cov=int(cov.sum()), cov_we_miss=int((cov & a_bg).sum()),
               value=int(val.sum()))
    if val.any():
        ys, xs = np.nonzero(val)
        out['value_bbox'] = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    if cov.any():
        ys, xs = np.nonzero(cov)
        out['cov_bbox'] = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    return out


def family(test):
    f = re.sub(r'_(w|z)-?[0-9.e+-]*(inf)?$', '', test)
    return re.sub(r'_tex_persp$', '', f)


def main():
    caps, golds = sys.argv[1], sys.argv[2]
    show_all = '--all' in sys.argv
    suite = sys.argv[sys.argv.index('--suite') + 1] if '--suite' in sys.argv else 'W_param'
    fam = collections.defaultdict(collections.Counter)
    for f in sorted(os.listdir(golds)):
        test = f[:-4]
        cap = os.path.join(caps, suite + '::' + f)
        if not os.path.exists(cap):
            print('MISSING', test)
            continue
        r = split(cap, os.path.join(golds, f))
        for k in ('diff', 'small', 'cov', 'cov_we_miss', 'value'):
            fam[family(test)][k] += r[k]
            fam['TOTAL'][k] += r[k]
        fam[family(test)]['n'] += 1
        if show_all or r['diff'] > 20000:
            print(test, r)
    print()
    print('%-24s %4s %9s %9s %9s %9s %9s' % ('family', 'n', 'diff', 'small', 'cov', 'we_miss', 'value'))
    for k, v in sorted(fam.items(), key=lambda kv: -kv[1]['diff']):
        print('%-24s %4d %9d %9d %9d %9d %9d' % (k, v['n'], v['diff'], v['small'], v['cov'],
                                                   v['cov_we_miss'], v['value']))


if __name__ == '__main__':
    main()
