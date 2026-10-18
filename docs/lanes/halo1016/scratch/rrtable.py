#!/usr/bin/env python3
"""Per-window [rr425] dispatcher account of a cinematic run, against `mark cinematic`.

usage: rrtable.py <result dir> [from_s] [to_s]

Prints, per 2-s window: TBs dispatched, plain exits by mode, lookup misses, longjmps,
the sampled loop time (gapus) and TB time (tbus) as a share of the window, and the
window's top [rr425pc] entries. Read only.
"""
import re
import sys
from datetime import datetime

d = sys.argv[1]
lo = float(sys.argv[2]) if len(sys.argv) > 2 else -10
hi = float(sys.argv[3]) if len(sys.argv) > 3 else 340

TS = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)')


def ts(line):
    m = TS.match(line)
    return datetime.strptime('2026-' + m.group(1), '%Y-%m-%d %H:%M:%S.%f') if m else None


mark = None
rows = []
pcs = {}
with open(d + '/logcat.txt', errors='replace') as f:
    for line in f:
        if mark is None and 'mark cinematic' in line:
            mark = ts(line)
            continue
        if mark is None:
            continue
        if '[rr425] ' in line:
            kv = dict(re.findall(r'(\w+)=(\d+)', line.split('[rr425]', 1)[1]))
            t = (ts(line) - mark).total_seconds()
            if lo <= t <= hi:
                rows.append((t, {k: int(v) for k, v in kv.items()}))
        elif '[rr425pc] ' in line:
            t = (ts(line) - mark).total_seconds()
            if lo <= t <= hi:
                w = re.search(r'w=(\d+)', line).group(1)
                ent = re.findall(r'(\w):([0-9a-f]+):([0-9a-f]+):(\d+)', line)
                pcs[w] = ent

print('| t-mark | dt ms | it k | e k | en k | es k | eo k | m k | x k | r k | gap % | tb % | top pcs |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for t, r in rows:
    dt = r.get('dt', 2000) * 1000.0
    top = pcs.get(str(r.get('w')), [])[:4]
    tops = ' '.join('%s:%s:%s:%dk' % (c, pc, b, int(n) // 1000) for c, pc, b, n in top)
    print('| %.0f | %d | %d | %d | %d | %d | %d | %d | %d | %d | %.1f | %.1f | %s |' % (
        t, r.get('dt', 0), r.get('it', 0) // 1000, r.get('e', 0) // 1000, r.get('en', 0) // 1000,
        r.get('es', 0) // 1000, r.get('eo', 0) // 1000, r.get('m', 0) // 1000, r.get('x', 0) // 1000,
        r.get('r', 0) // 1000, 100.0 * r.get('gapus', 0) / dt, 100.0 * r.get('tbus', 0) / dt, tops))
