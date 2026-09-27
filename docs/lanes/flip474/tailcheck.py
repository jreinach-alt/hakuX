"""H0's 'lines to the end': seconds of the last [lock474] and hakuX-perf lines against the last logcat line."""
import sys
from datetime import datetime

R = '/home/justin/hakux-work/dispatch/results/'


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


for run in sys.argv[1:]:
    L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
    t0 = ts(L[1])
    last = {'lock474': None, 'hakuX-perf': None, 'any': None}
    for l in L:
        try:
            s = (ts(l) - t0).total_seconds()
        except ValueError:
            continue
        last['any'] = s
        for k in ('lock474', 'hakuX-perf'):
            if k in l:
                last[k] = s
    print(run, ' '.join('%s=%.1f' % (k, v or -1) for k, v in last.items()))
