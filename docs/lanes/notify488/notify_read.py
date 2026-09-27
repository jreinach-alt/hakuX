#!/usr/bin/env python3
"""Read a #488 game soak: gfps and the [notify488] signal counts over a window.

    python3 notify_read.py [--from S] [--to S] <result-id> [...]

Seconds are from logcat line 1, as in docs/lanes/flip474/lockread.py. Per run:
the gfps median in the window; the semaphore releases and NOTIFYs the guest
sent (sums of the perflog [notify488] lines, one per 60 frames, which both
arms carry); whether the NOTIFY method was logged as unhandled (A has no
handler, so a title that sends it logs `method 0x0104` once); whether a
write-then-awaken NOTIFY was seen (B only); the longest gap between
hakuX-perf lines; and any fatal-signal line.
"""
import os
import re
import sys
from datetime import datetime
from statistics import median

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


def read(run, lo, hi):
    L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
    t0 = ts(L[1])
    out = {'gfps': [], 'sem': 0, 'ntf': 0, 'sig_lines': 0, 'stamps': [],
           'unhandled_notify': False, 'awaken': False, 'fatal': []}
    for l in L:
        if 'method 0x0104' in l and 'class 0x0097' in l:
            out['unhandled_notify'] = True
        if '[notify488] NOTIFY write-then-awaken' in l:
            out['awaken'] = True
        if 'Fatal signal' in l or 'F DEBUG' in l:
            out['fatal'].append(l.strip()[:160])
        try:
            s = (ts(l) - t0).total_seconds()
        except ValueError:
            continue
        if not lo <= s <= hi:
            continue
        m = re.search(r'\[notify488\] sem_release (\d+) notify (\d+)', l)
        if m:
            out['sig_lines'] += 1
            out['sem'] += int(m.group(1))
            out['ntf'] += int(m.group(2))
            continue
        if 'hakuX-perf' not in l:
            continue
        out['stamps'].append(s)
        m = re.search(r'gfps[= ]([\d.]+)', l)
        if m:
            out['gfps'].append(float(m.group(1)))
    st = out.pop('stamps')
    out['gap'] = max((b - a for a, b in zip(st, st[1:])), default=0.0)
    return out


def main():
    a = sys.argv[1:]
    lo, hi = 0.0, 1e9
    while a and a[0].startswith('--'):
        if a[0] == '--from':
            lo = float(a[1])
        elif a[0] == '--to':
            hi = float(a[1])
        else:
            sys.exit('unknown option ' + a[0])
        a = a[2:]
    for run in a:
        o = read(run, lo, hi)
        g = o['gfps']
        print(f'{run}  window {lo:g}-{hi:g} s')
        print(f'  gfps median {median(g):.2f} (n={len(g)}, min {min(g):.1f}, '
              f'max {max(g):.1f})' if g else '  gfps: NO LINES (VOID)')
        print(f'  [notify488] lines {o["sig_lines"]}: sem_release {o["sem"]}, '
              f'notify {o["ntf"]}')
        print(f'  NOTIFY logged unhandled: {o["unhandled_notify"]}; '
              f'write-then-awaken seen: {o["awaken"]}')
        print(f'  longest hakuX-perf gap {o["gap"]:.1f} s; fatal lines '
              f'{len(o["fatal"])}')
        for f in o['fatal'][:3]:
            print('    ' + f)


if __name__ == '__main__':
    main()
