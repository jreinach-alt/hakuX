#!/usr/bin/env python3
"""Every value a capture has taken in dispatch/results, split by device and by
whether the build carries the fix (NOTES section 10). A mover in a pixel arm is
noise if master takes the fix's value too, at a similar rate.

    pixel_survey.py Suite/Test [Suite/Test ...]

Each run is counted once: the 0-0-x- alias of a result dir is folded into it.
The last block is a one-sided Fisher exact test, fix vs not, per value.
"""
import collections
import glob
import json
import os
import sys
from math import comb

RESULTS = os.environ.get('RESULTS', '/home/justin/hakux-work/dispatch/results')
FIX = ('10fe2f59a7', 'eec025dd37', '387ff6fb41')


def fisher(a, b, c, d):
    n, r1, c1 = a + b + c + d, a + b, a + c
    return sum(comb(c1, x) * comb(n - c1, r1 - x) / comb(n, r1)
               for x in range(a, min(r1, c1) + 1))


def main(keys):
    want = set(tuple(k.split('/', 1)) for k in keys)
    seen, rows = set(), []
    for d in sorted(os.listdir(RESULTS)):
        tsvs = sorted(glob.glob(os.path.join(RESULTS, d, 'scores*.tsv')))
        if not tsvs:
            continue
        try:
            rj = json.load(open(os.path.join(RESULTS, d, 'result.json')))
        except (OSError, ValueError):
            rj = {}
        ref = rj.get('ref') or ''
        fix = 'fix' if any(ref.startswith(f) for f in FIX) else 'nofix'
        for t in tsvs:
            for line in open(t, errors='replace'):
                f = line.rstrip('\n').split('\t')
                if len(f) > 4 and (f[0], f[1]) in want:
                    k = (d.replace('0-0-x-', ''), os.path.basename(t), f[0], f[1])
                    if k in seen:
                        continue
                    seen.add(k)
                    rows.append((f[0] + '/' + f[1], str(rj.get('device_label')),
                                 fix, f[4], d, ref))
    for key in sorted(set(r[0] for r in rows)):
        rr = [r for r in rows if r[0] == key]
        print('==', key, '(%d captures)' % len(rr))
        c = collections.Counter((r[1], r[2], r[3]) for r in rr)
        for k in sorted(c):
            print('   %-6s %-6s differing=%-8s x%d' % (k + (c[k],)))
        for val in sorted(set(r[3] for r in rr if r[2] == 'fix')):
            a = sum(1 for r in rr if r[2] == 'fix' and r[3] == val)
            b = sum(1 for r in rr if r[2] == 'fix') - a
            cc = sum(1 for r in rr if r[2] == 'nofix' and r[3] == val)
            dd = sum(1 for r in rr if r[2] == 'nofix') - cc
            print('   value %s: fix %d/%d, nofix %d/%d, one-sided Fisher p=%.4f'
                  % (val, a, a + b, cc, cc + dd, fisher(a, b, cc, dd)))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
