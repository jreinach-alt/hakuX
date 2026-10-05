#!/usr/bin/env python3
"""One thread's off-CPU intervals, each paired EXACTLY with its sched_switch
sample: the sample must fall after the thread's previous context-switch
record and at or before this switch-out. (waitsite.py's +-200 us window can
hand a short bounce's sample to the long sleep that follows it.)

    exact.py <report.txt> <tid> [--other <tid>]

With --other: for the long waits (>= 5 ms), when the other thread switched in
and out during the wait.
"""
import bisect, collections, statistics, sys
sys.path.insert(0, 'docs/lanes/vcpuwait433')
from waitsite import records, SKIP

txt, want = sys.argv[1], sys.argv[2]
other = sys.argv[sys.argv.index('--other') + 1] if '--other' in sys.argv else None
ev = []      # (time, kind, payload): kind 0 = cs, 1 = sched_switch sample
oev = []
for kind, rec, chain in records(open(txt, errors='replace')):
    tid, t = rec.get('tid'), rec.get('time')
    if t is None:
        continue
    if tid == want:
        if kind == 'cs':
            ev.append((t, 0, bool(rec.get('on'))))
        elif rec.get('ev') == 'sched:sched_switch':
            emu = [f for f in chain if not f.startswith(SKIP) and not f.startswith('*')]
            ev.append((t, 1, ' <- '.join(emu[:4]) or '(no emu frame)'))
    elif other and tid == other and kind == 'cs':
        oev.append((t, bool(rec.get('on'))))
ev.sort(key=lambda x: (x[0], -x[1]))   # a sample at the same ns goes first
oev.sort()
ot = [x[0] for x in oev]
bins = [0.1, 1, 5, 10, 20, 1e9]
site = collections.defaultdict(collections.Counter)
pending = None
last_out = None
long_rows = collections.defaultdict(list)
for t, k, p in ev:
    if k == 1:
        pending = p
        continue
    if not p:                      # switch-out
        last_out = (t, pending or '(unsampled)')
        pending = None
    else:                          # switch-in
        pending = None
        if last_out:
            t0, s = last_out
            d = (t - t0) / 1e6
            site[s][next(x for x in bins if d < x)] += d
            if other and d >= 5:
                a, b = bisect.bisect_left(ot, t0), bisect.bisect_left(ot, t)
                ins = [x[0] for x in oev[a:b] if x[1]]
                outs = [x[0] for x in oev[a:b] if not x[1]]
                long_rows[s].append((d, (ins[0] - t0) / 1e6 if ins else None,
                                     (t - outs[-1]) / 1e6 if outs else None, len(ins)))
            last_out = None
tot = {s: sum(c.values()) for s, c in site.items()}
print(f'tid {want}: off-CPU {sum(tot.values()):.0f} ms')
for s in sorted(tot, key=lambda x: -tot[x])[:12]:
    c = site[s]
    print(f'  {tot[s]:8.0f} ms  ' + ' '.join(f'<{b}:{c[b]:.0f}' for b in bins) + f'  {s[:120]}')
for s, rows in sorted(long_rows.items(), key=lambda x: -sum(r[0] for r in x[1]))[:4]:
    fi = sorted(r[1] for r in rows if r[1] is not None)
    lo = sorted(r[2] for r in rows if r[2] is not None)
    print(f'  waits >= 5 ms at {s[:80]}: n={len(rows)} median {statistics.median(r[0] for r in rows):.1f} ms; '
          f'other ran in {sum(1 for r in rows if r[3])}')
    if fi:
        print(f'     other first switch-in after wait start: median {statistics.median(fi):.2f} ms, p90 {fi[int(.9 * len(fi))]:.2f}')
    if lo:
        print(f'     other last switch-out before waiter woke: median {statistics.median(lo):.2f} ms before, p90 {lo[int(.9 * len(lo))]:.2f}')
