#!/usr/bin/env python3
"""Guest interrupts per frame by wake key, per [rr425w] window, against the
nearest hakuX-perf gfps line. Key vv.uu: vector vv (30 timer, 33 NV2A, 3e
IDE) and NV2A units uu from hakux_nv2a_irq_units() (01 PFIFO, 02 PCRTC, 04
PGRAPH, 08 NOTIFY, 10 CONTEXT_SWITCH, 20 BUFFER_NOTIFY, 40 ERROR; 33.44 is
the NO_OPERATION trap, a push-buffer callback). n counts wakes from idle, nb
interrupts taken while busy. Usage:

    irqrate.py LOGCAT [--from HH:MM:SS] [--to HH:MM:SS] [--keys 33.44,30.00]
"""
import argparse
import re
import sys
from datetime import datetime

TS = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d)\s')
KEY = re.compile(r' ([0-9a-f]{2}\.[0-9a-f]{2}):(\d+):(\d+):(\d+):'
                 r'[\d/]+:[\d/]+:(\d+)')


def ts(line):
    m = TS.match(line)
    if not m:
        return None
    return datetime.strptime('2026-' + m.group(1),
                             '%Y-%m-%d %H:%M:%S.%f').timestamp()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--from', dest='t_from')
    ap.add_argument('--to', dest='t_to')
    ap.add_argument('--keys', default='33.44,33.02,30.00')
    a = ap.parse_args()
    want = a.keys.split(',')

    perf, rrw = [], []
    with open(a.log, errors='replace') as f:
        for line in f:
            t = ts(line)
            if t is None:
                continue
            if 'hakuX-perf' in line and 'gfps=' in line:
                m = re.search(r'gfps=(\d+) G:([\d.]+)', line)
                if m:
                    perf.append((t, int(m.group(1)), float(m.group(2))))
            elif '[rr425w]' in line:
                body = line.split('[rr425w]', 1)[1]
                m = re.search(r'idle_us=(\d+) busy_us=(\d+) n=(\d+) nb=(\d+)',
                              body)
                if not m:
                    continue
                keys = {k: (int(n), int(i), int(b), int(nb))
                        for k, n, i, b, nb in KEY.findall(body)}
                rrw.append((t, int(m.group(1)), int(m.group(2)),
                            int(m.group(3)), int(m.group(4)), keys))

    if not rrw:
        print('no [rr425w] lines')
        return 1

    def clock(s):
        if not s:
            return None
        d = datetime.fromtimestamp(rrw[0][0]).strftime('%Y-%m-%d ')
        return datetime.strptime(d + s, '%Y-%m-%d %H:%M:%S').timestamp()

    t0, t1 = clock(a.t_from), clock(a.t_to)
    hdr = '%8s %4s %6s %5s %7s' % ('t', 'gfps', 'G', 'vbusy', 'nb/fr')
    for k in want:
        hdr += ' %8s %8s' % (k + ' n', k + ' nb')
    hdr += ' %9s' % 'k/fr'
    print(hdr)
    for t, idle, busy, n, nb, keys in rrw:
        if t0 and t < t0 or t1 and t > t1:
            continue
        p = min(perf, key=lambda x: abs(x[0] - t)) if perf else None
        if not p or abs(p[0] - t) > 1.5:
            continue
        span = (idle + busy) / 1e6
        frames = p[1] * span if p[1] else 0
        row = '%8s %4d %6.1f %5.2f %7.0f' % (
            datetime.fromtimestamp(t).strftime('%H:%M:%S'), p[1], p[2],
            busy / (idle + busy) if idle + busy else 0,
            (n + nb) / frames if frames else float('nan'))
        tot = 0
        for k in want:
            kn, ki, kb, knb = keys.get(k, (0, 0, 0, 0))
            row += ' %8d %8d' % (kn, knb)
            if k == want[0]:
                tot = kn + knb
        row += ' %9.0f' % (tot / frames if frames else float('nan'))
        print(row)
    return 0


if __name__ == '__main__':
    sys.exit(main())
