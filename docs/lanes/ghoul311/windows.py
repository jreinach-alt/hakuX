"""Per-120-frame window table from a soak's hakuX-pages lines (#311).

The pages lines print every 120 guest frames, so window seconds / 120 is the
mean guest frame time over the window. (ms-33)/pr charges all frame time above
the 30 fps cap to the arming walks; it is a model, not a measurement.

    python3 windows.py <result-id> [<result-id> ...]
"""
import re
import sys
from datetime import datetime

R = '/home/justin/hakux-work/dispatch/results/'


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


for run in sys.argv[1:]:
    L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
    t0 = ts(L[1])
    prev = None
    slow = 0
    print(run)
    print('     t  win_s ms/frame  ev/f  di/f  pr/f  slow/f  cg/f  (ms-33)/pr')
    for l in L:
        if '/hakuX-pages(' not in l:
            continue
        s = (ts(l) - t0).total_seconds()
        if 'slow stores' in l:
            slow = int(re.search(r'slow stores (\d+)', l)[1])
            continue
        d = dict(re.findall(r'(\w+)=(\d+)', l))
        if prev is not None:
            dt = s - prev
            fm = dt * 1000 / 120
            pr = int(d['pr']) / 120
            print(f'{s:6.1f} {dt:6.1f} {fm:8.1f} {int(d["ev"])/120:5.0f} '
                  f'{int(d["di"])/120:5.0f} {pr:5.0f} {slow/120:7.0f} '
                  f'{int(d["cg"])/120:5.1f}   {(fm-33)/pr:6.3f}')
        prev = s
