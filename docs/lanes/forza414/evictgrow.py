"""[evict372] growth per mask over a soak window.

    evictgrow.py [--from S] [--to S] RESULT_ID...

t = 0 is the first `soak start` line, as in abread.py. The dirty/clean-by-mask
summary line is cumulative, so the growth is the last line at or before the
window's end minus the last at or before its start. Masks: 1 role, 2 format,
4 pitch, 8 small, 10 swizzle, 20 overlap, 40 zdim.
"""
import argparse
import re

R = '/home/justin/hakux-work/dispatch/results/'


def secs(l):
    h, m, s = l.split()[1].split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


ap = argparse.ArgumentParser()
ap.add_argument('--from', dest='t_from', type=float, default=125)
ap.add_argument('--to', dest='t_to', type=float, default=240)
ap.add_argument('ids', nargs='+')
args = ap.parse_args()

for x in args.ids:
    t0 = None
    rows = []
    for l in open(R + x + '/logcat.txt', errors='replace'):
        if t0 is None and 'soak start' in l:
            t0 = secs(l)
        if t0 is None:
            continue
        if 'dirty/clean by mask' in l:
            d = dict((k, int(a) + int(b))
                     for k, a, b in re.findall(r'm([0-9a-f]{2}):(\d+)/(\d+)', l))
            rows.append((secs(l) - t0, d))

    def at(t):
        best = None
        for tt, d in rows:
            if tt <= t:
                best = (tt, d)
        return best
    a = at(args.t_from)
    b = at(args.t_to)
    print(x, 'lines', len(rows), 'from', a and round(a[0]), 'to', b and round(b[0]))
    if a and b:
        ks = sorted(set(a[1]) | set(b[1]))
        print('  growth', dict((k, b[1].get(k, 0) - a[1].get(k, 0)) for k in ks))
