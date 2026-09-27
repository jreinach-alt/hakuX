#!/usr/bin/env python3
"""Why K0 failed: the GPU timestamp clock against the PFIFO thread's clock.

    python3 o4clock.py <result id> [--from 151 --to 288]

Per [o4] line, the fence-seen time w1 (CPU ns) less the command buffer's last
timestamp ce (ticks x the device's timestampPeriod). If the two clocks tick at
the rate the period says, the lower envelope of (w1 - ce) is flat. It is not:
this fits the envelope's slope (by 5 s bins) and the tick period that would
make it flat, then re-derives span and the position of the span inside the
wait with that period.
"""
import os
import re
import sys
from statistics import median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from o4read import LONG_WAIT_MS, R, parse_o4, ts  # noqa: E402

PAT = re.compile(r'\[o4\] .*?pre=(\d+) post=(\d+) w0=(-?\d+) w1=(-?\d+) '
                 r'per=([0-9.]+) cs=(\d+) ce=(\d+)')


def main():
    args = sys.argv[1:]
    lo, hi = 151.0, 288.0
    if '--from' in args:
        i = args.index('--from'); lo = float(args[i + 1]); del args[i:i + 2]
    if '--to' in args:
        i = args.index('--to'); hi = float(args[i + 1]); del args[i:i + 2]
    run = args[0]
    d = run if os.path.isdir(run) else R + run
    t0 = None
    rows, lines = [], []
    for l in open(os.path.join(d, 'logcat.txt'), errors='replace'):
        if len(l) < 18 or not l[:2].isdigit():
            continue
        try:
            t = ts(l)
        except ValueError:
            continue
        if t0 is None:
            t0 = t
        s = (t - t0).total_seconds()
        if s < lo or s > hi:
            continue
        m = PAT.search(l)
        if not m:
            continue
        lines.append(l)
        pre, post, w0, w1 = (int(m.group(k)) for k in (1, 2, 3, 4))
        per = float(m.group(5))
        cs, ce = int(m.group(6)), int(m.group(7))
        if (w1 - w0) < 4e6:
            continue
        rows.append((w1, cs, ce, per, pre, w0))
    if len(rows) < 20:
        print('too few [o4] lines:', len(rows))
        return 1
    per = rows[0][3]
    # Envelope: min (w1 - ce*per) per 5 s bin of CPU time.
    tmin = rows[0][0]
    bins = {}
    for w1, cs, ce, _, _, _ in rows:
        b = int((w1 - tmin) / 5e9)
        v = w1 - ce * per
        if b not in bins or v < bins[b][1]:
            bins[b] = (w1, v)
    pts = sorted(bins.values())
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    slope = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
    # w1 - ce*per = off + slope*w1  =>  ce*per = (1 - slope)*w1 - off, so the
    # tick period that tracks the CPU clock is per / (1 - slope).
    per2 = per / (1 - slope)
    # Ticks per CPU second, directly, from first and last envelope points.
    print(f'lines={len(rows)} bins={n} envelope slope={slope:.5f} (ns per ns)')
    print(f'period in the line={per:.4f} ns/tick ({1e3 / per:.3f} MHz); '
          f'period that tracks the CPU clock={per2:.4f} ns/tick '
          f'({1e3 / per2:.3f} MHz)')
    resid = [p[1] - (my + slope * (p[0] - mx)) for p in pts]
    print('envelope residual after the fit, ms: min %.2f max %.2f' %
          (min(resid) / 1e6, max(resid) / 1e6))
    # Re-derive with per2 and the fitted offset (lower envelope).
    off = min(w1 - ce * per2 for w1, _, ce, _, _, _ in rows)
    span, start, end, wait = [], [], [], []
    for w1, cs, ce, _, pre, w0 in rows:
        gs, ge = cs * per2 + off, ce * per2 + off
        span.append((ce - cs) * per2 / 1e6)
        start.append((gs - pre) / 1e6)  # GPU start after the flip's finish began
        end.append((w1 - ge) / 1e6)  # fence seen after the last timestamp
        wait.append((w1 - pre) / 1e6)
    for k, v in (('finish+wait', wait), ('span', span), ('start', start),
                 ('end', end)):
        v = sorted(v)
        print(f'  {k:<12} med={median(v):7.1f} p10={v[len(v) // 10]:7.1f} '
              f'p90={v[len(v) * 9 // 10]:7.1f}')
    # S2's second half: which pass the longest gap follows, per long-wait flip.
    after = {}
    for l in lines:
        f = parse_o4(l)
        if not f or f['wait'] < LONG_WAIT_MS or len(f['passes']) < 2:
            continue
        p = f['passes']
        g, i = max((p[j + 1][0] - p[j][1], j) for j in range(len(p) - 1))
        after[i] = after.get(i, 0) + 1
    tot = sum(after.values())
    if tot:
        i, c = max(after.items(), key=lambda x: x[1])
        print(f'  longest gap follows pass {i} on {c}/{tot} flips '
              f'({100.0 * c / tot:.1f}%)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
