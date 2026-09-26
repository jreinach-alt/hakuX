#!/usr/bin/env python3
"""Per-bucket counters from a titleplay/soak logcat (lane.forza414, #414).

    timeline.py <logcat.txt> [--bucket 30] [--t0 HH:MM:SS.mmm] [--rows]

t = 0 is the first `hakuX-route: soak start` line (or --t0). One row per
bucket, every counter the non-perflog runner spec carries:

  fps      flips per second from gfps lines (60 flips per line / line span)
  G, Ri    gfps line median flip interval and renderer-idle ms (Ri/G = idle)
  cpu      vCPU thread ms per 2 s ([tlb68] cpu / dt)
  pf, rd, rdus, sd, tw   [tlb68] page flushes, reset_dirty calls and their us,
           set_dirty, TLB entries walked, per 2 s
  kicks, drain  fifoskew kicks and mean drain ms per 2 s window
  live, ins, act, shv, inv  [watch311]: live CPU-access watches, cumulative
           inserts, and the active/shelved/invalid surface list lengths
  slow, iv, ic  hakuX-pages slow stores, invalidations and invalidate calls
  starve   audiocap zero-filled share

--rows prints every [watch311] line with its t, to read the growth directly.
"""
import re
import statistics
import sys

TS = re.compile(r'^\d\d-\d\d (\d\d):(\d\d):(\d\d)\.(\d\d\d) ')


def secs(line):
    m = TS.match(line)
    if not m:
        return None
    h, mi, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000.0


def kv(line):
    return {k: v for k, v in re.findall(r'(\w+)=([-\d.]+)', line)}


def main(argv):
    path = argv[1]
    bucket = 30.0
    t0 = None
    rows = '--rows' in argv
    if '--bucket' in argv:
        bucket = float(argv[argv.index('--bucket') + 1])
    if '--t0' in argv:
        h, mi, s = argv[argv.index('--t0') + 1].split(':')
        t0 = int(h) * 3600 + int(mi) * 60 + float(s)
    lines = open(path, errors='replace').read().splitlines()
    if t0 is None:
        for l in lines:
            if 'soak start' in l:
                t0 = secs(l)
                break
    B = {}

    def b(t):
        return B.setdefault(int((t - t0) // bucket), {
            'gfps_t': [], 'G': [], 'Ri': [], 'cpu': [], 'pf': [], 'rd': [],
            'rdus': [], 'sd': [], 'tw': [], 'kicks': [], 'drain': [],
            'live': [], 'ins': [], 'act': [], 'shv': [], 'inv': [],
            'slow': [], 'iv': [], 'ic': [], 'starve': []})

    for l in lines:
        t = secs(l)
        if t is None or t < t0:
            continue
        if 'hakuX-perf' in l and 'gfps=' in l:
            m = re.search(r'G:([\d.]+)\(.*Ri:([\d.]+)', l)
            d = b(t)
            d['gfps_t'].append(t)
            d['G'].append(float(m.group(1)))
            d['Ri'].append(float(m.group(2)))
        elif '[tlb68]' in l:
            k = kv(l)
            d = b(t)
            dt = float(k['dt']) or 1
            d['cpu'].append(float(k['cpu']) * 2000 / dt)
            for f in ('pf', 'rd', 'rdus', 'sd', 'tw'):
                d[f].append(float(k[f]) * 2000 / dt)
        elif 'fifoskew' in l:
            m = re.search(r'kicks=(\d+).*drain\(n=(\d+) mean=(\d+)', l)
            d = b(t)
            d['kicks'].append(int(m.group(1)))
            d['drain'].append(int(m.group(3)) / 1e6)
        elif '[watch311]' in l:
            k = kv(l)
            d = b(t)
            d['live'].append(int(k['live']))
            d['ins'].append(int(k['inserts']))
            d['act'].append(int(k['active']))
            d['shv'].append(int(k['shelved']))
            d['inv'].append(int(k['invalid']))
            if rows:
                print('%7.1f %s' % (t - t0, l[l.index('[watch311]'):]))
        elif 'hakuX-pages' in l and 'slow stores' in l:
            m = re.search(r'slow stores (\d+)', l)
            b(t)['slow'].append(int(m.group(1)))
        elif 'hakuX-pages' in l and 'inval ev=' in l:
            k = kv(l)
            d = b(t)
            d['iv'].append(int(k['iv']))
            d['ic'].append(int(k['ic']))
        elif 'starve:' in l:
            m = re.search(r'= ([\d.]+)% of output', l)
            b(t)['starve'].append(float(m.group(1)))
    if rows:
        return

    def med(x, fmt='%.0f'):
        return fmt % statistics.median(x) if x else '-'

    def last(x):
        return str(x[-1]) if x else '-'

    hdr = ('t', 'fps', 'G', 'Ri', 'cpu', 'pf', 'rd', 'rdus', 'sd', 'tw',
           'kicks', 'drain', 'live', 'ins', 'act', 'shv', 'inv', 'slow', 'iv',
           'ic', 'starve')
    print('| ' + ' | '.join(hdr) + ' |')
    print('|' + '---|' * len(hdr))
    for i in sorted(B):
        d = B[i]
        gt = sorted(d['gfps_t'])
        fps = '-'
        if gt:
            # 60 flips per gfps line; count lines landing in the bucket
            fps = '%.1f' % (60.0 * len(gt) / bucket)
        print('| ' + ' | '.join([
            '%d' % (i * bucket), fps, med(d['G'], '%.1f'), med(d['Ri'], '%.1f'),
            med(d['cpu']), med(d['pf']), med(d['rd']), med(d['rdus']),
            med(d['sd']), med(d['tw']), med(d['kicks']),
            med(d['drain'], '%.1f'), last(d['live']), last(d['ins']),
            last(d['act']), last(d['shv']), last(d['inv']),
            med(d['slow']), med(d['iv']), med(d['ic']),
            med(d['starve'], '%.0f')]) + ' |')


if __name__ == '__main__':
    main(sys.argv)
