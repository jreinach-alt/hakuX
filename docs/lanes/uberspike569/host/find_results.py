#!/usr/bin/env python3
"""Where are this lane's dispatch requests: queue, running or results (lane.uberspike569)."""
import glob
import os
import sys

dd = os.environ.get('DISPATCH_DIR') or os.path.expanduser('~/hakux-work/dispatch')
print('dispatch dir:', dd)
for rid in sys.argv[1:]:
    hits = glob.glob(os.path.join(dd, '*', rid + '*')) + glob.glob(os.path.join(dd, '*', '*', rid + '*'))
    print(rid, hits or 'NOT FOUND')
for sub in ('queue', 'running', 'results'):
    p = os.path.join(dd, sub)
    if os.path.isdir(p):
        names = sorted(x for x in os.listdir(p) if 'uberspike' in x)
        print(sub, len(names), names[-12:])
