#!/usr/bin/env python3
"""Regenerate docs/lanes/gpuclock/out/ from the dispatch results: for each pair,
gpuclock.py --pair (out/<pair>.out, .tsv), align.py (out/<pair>.align.out),
near30's decompose.py (out/<pair>.decomp.out, .decomp.tsv), align_decomp.py
with the lag align.py found (out/<pair>.adecomp.out; Forza at lag 0, since
its correlation, 0.27, does not support a lag), and cpu7share.py
(out/cpu7share.out). Run from the worktree root.

    readpairs.py
"""
import subprocess

R = '/home/justin/hakux-work/dispatch/results/'
L = 'docs/lanes/gpuclock/'
O = L + 'out/'
# name: (low run, high run, lag for align_decomp)
PAIRS = {
    'nightfire-pair1': ('1-1791215562-lane.gpuclock-2286132', '1-1791215567-lane.gpuclock-2286266', None),
    'nightfire-pair2': ('1-1791220912-lane.gpuclock-2642033', '1-1791220908-lane.gpuclock-2641880', '4'),
    'tron-pair1': ('1-1791220914-lane.gpuclock-2642143', '1-1791220916-lane.gpuclock-2642242', '-12'),
    'forza-pair1': ('1-1791221184-lane.gpuclock-2660193', '1-1791221182-lane.gpuclock-2660089', '0'),
}


def run(args, out, head=''):
    o = subprocess.run(['python3'] + args, capture_output=True, text=True)
    open(out, 'w').write(head + o.stdout + o.stderr)


for n, (lo, hi, lag) in PAIRS.items():
    if n != 'nightfire-pair1':
        run([L + 'gpuclock.py', '--pair', R + lo, R + hi, '--tsv', O + n + '.tsv'], O + n + '.out')
        run([L + 'align.py', O + n + '.tsv', lo, hi], O + n + '.align.out', '## %s\n' % n)
    run(['docs/lanes/near30/decompose.py', R + lo, R + hi, '--tsv', O + n + '.decomp.tsv'], O + n + '.decomp.out',
        '## %s (low %s, high %s)\n' % (n, lo, hi))
    if lag is not None:
        run([L + 'align_decomp.py', O + n + '.decomp.tsv', lo, hi, lag], O + n + '.adecomp.out', '## %s\n' % n)
run([L + 'cpu7share.py'] + [r for lo, hi, _ in PAIRS.values() for r in (lo, hi)], O + 'cpu7share.out')
