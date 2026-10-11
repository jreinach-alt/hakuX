#!/usr/bin/env python3
"""For a thread's long UNSAMPLED off-CPU intervals: the thread's last cpu-clock
sample since its previous switch-in, i.e. the code it ran just before it slept.

    lastrun.py <report.txt> <tid> [min_ms]
"""
import collections, sys
sys.path.insert(0, 'docs/lanes/vcpuwait433')
from waitsite import records, SKIP

txt, want = sys.argv[1], sys.argv[2]
mn = float(sys.argv[3]) if len(sys.argv) > 3 else 10
ev = []
for kind, rec, chain in records(open(txt, errors='replace')):
    if rec.get('tid') != want or rec.get('time') is None:
        continue
    t = rec['time']
    if kind == 'cs':
        ev.append((t, 0, bool(rec.get('on'))))
    elif rec.get('ev') == 'sched:sched_switch':
        ev.append((t, 1, None))
    elif rec.get('ev') == 'cpu-clock':
        emu = [f for f in chain if not f.startswith('*')]
        ev.append((t, 2, ' <- '.join(f[:48] for f in emu[:7])))
ev.sort(key=lambda x: (x[0], -x[1]))
agg = collections.Counter()
n = collections.Counter()
sampled = False
last = None
out = None
for t, k, p in ev:
    if k == 2:
        last = p
    elif k == 1:
        sampled = True
    elif not p:
        out = (t, sampled, last)
    else:
        if out:
            d = (t - out[0]) / 1e6
            if d >= mn and not out[1]:
                agg[out[2] or '(no sample since switch-in)'] += d
                n[out[2] or '(no sample since switch-in)'] += 1
        out, sampled, last = None, False, None
print(f'tid {want}: unsampled off-CPU >= {mn} ms: {sum(agg.values()):.0f} ms in {sum(n.values())}')
for s, d in agg.most_common(14):
    print(f'  {d:7.0f} {n[s]:5d}  {s[:260]}')
