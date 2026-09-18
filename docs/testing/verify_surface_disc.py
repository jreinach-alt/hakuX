#!/usr/bin/env python3
"""Score one run of the surface disc and byte-compare it with earlier runs.

    verify_surface_disc.py <captures_dir> <goldens_root> [<ref_captures_dir> ...]

<captures_dir> holds the PNGs extract_results.py wrote for one run, named
``<Suite>::<capture>.png``; <goldens_root> is the hardware goldens tree with
one directory per suite. For every suite it prints how many captures are
byte-exact against the golden and the four worst by differing pixels; for
every reference run it prints how many captures are byte-identical and, for
each that is not, both runs' distance from the golden.

Written for #66, whose closing legs are "the disc runs to completion under
renderer = 'OPENGL'" (236 captures, exit 0) and "nothing that already existed
moved", and reused for any run of that disc since.
"""
import glob
import hashlib
import os
import sys

import numpy as np
from PIL import Image


def caps(d):
    return {os.path.basename(p): p for p in glob.glob(os.path.join(d, '*.png'))}


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def diffpx(p, g):
    a = np.asarray(Image.open(p).convert('RGBA')).astype(int)
    b = np.asarray(Image.open(g).convert('RGBA')).astype(int)
    if a.shape != b.shape:
        return -1
    return int((np.abs(a - b).max(axis=2) > 0).sum())


def main(new_dir, goldens, refs):
    n = caps(new_dir)
    print(f'{new_dir}: {len(n)} captures')
    tot_exact = tot = 0
    for s in sorted({k.split('::', 1)[0] for k in n}):
        ex = cnt = 0
        worst = []
        for k in sorted(k for k in n if k.startswith(s + '::')):
            name = k.split('::', 1)[1]
            g = os.path.join(goldens, s, name)
            if not os.path.exists(g):
                continue
            d = diffpx(n[k], g)
            cnt += 1
            if d == 0:
                ex += 1
            else:
                worst.append((d, name))
        tot_exact += ex
        tot += cnt
        worst.sort(reverse=True)
        print(f'  {s:28s} exact {ex:3d}/{cnt:3d}   '
              + ', '.join(f'{nm}={d:,}' for d, nm in worst[:4]))
    print(f'  TOTAL exact {tot_exact}/{tot}')
    for r in refs:
        m = caps(r)
        common = sorted(set(n) & set(m))
        diff = [k for k in common if md5(n[k]) != md5(m[k])]
        print(f'vs {r}: {len(common)} common, {len(diff)} differ, '
              f'{len(set(n) - set(m))} only-new, {len(set(m) - set(n))} only-ref')
        for k in diff:
            s, name = k.split('::', 1)
            g = os.path.join(goldens, s, name)
            gn = diffpx(n[k], g) if os.path.exists(g) else None
            gr = diffpx(m[k], g) if os.path.exists(g) else None
            print(f'    {k}: vs golden new={gn} ref={gr}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
