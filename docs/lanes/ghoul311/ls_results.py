#!/usr/bin/env python3
"""List the state of this lane's dispatch requests (queue/results) and the
files in each result dir. Lane-safe: walks the dispatch tree with os, no ls."""
import os, sys

D = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch')
tag = sys.argv[1] if len(sys.argv) > 1 else 'ghoul311'
for sub in sorted(os.listdir(D)):
    p = os.path.join(D, sub)
    if not os.path.isdir(p) or sub in ('bin', 'results'):
        continue
    for e in sorted(os.listdir(p)):
        if tag in e:
            print(f'{sub}/{e}')
R = os.path.join(D, 'results')
for e in sorted(os.listdir(R)):
    if tag not in e:
        continue
    r = os.path.join(R, e)
    print('==', e)
    for f in sorted(os.listdir(r)):
        fp = os.path.join(r, f)
        sz = os.path.getsize(fp) if os.path.isfile(fp) else 'dir'
        print(f'   {f:40s} {sz}')
