#!/usr/bin/env python3
"""The main-loop returns of a cinematic run, split by kind, per 2-s window against `mark cinematic`.

usage: rrsplit.py <result dir> [from_s] [to_s] [step]

Columns (k per window): it dispatched; eo EOB_ONLY exits (0x1ec3a's fldcw is ~97% of them in the plateau);
g unpatched goto_tb exits split gs (target spans two pages, never chained), gi (a block was CF_INVALID),
ga (patched at this dispatch); x longjmps; m lookup misses; hc helper_lookup_tb_ptr calls; gap % of the window.
Every `step`-th window is printed (default 1). Read only.
"""
import re
import sys
from datetime import datetime

d = sys.argv[1]
lo = float(sys.argv[2]) if len(sys.argv) > 2 else -10
hi = float(sys.argv[3]) if len(sys.argv) > 3 else 340
step = int(sys.argv[4]) if len(sys.argv) > 4 else 1
TS = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)')


def ts(line):
    m = TS.match(line)
    return datetime.strptime('2026-' + m.group(1), '%Y-%m-%d %H:%M:%S.%f') if m else None


mark = None
rows = []
with open(d + '/logcat.txt', errors='replace') as f:
    for line in f:
        if mark is None and 'mark cinematic' in line:
            mark = ts(line)
            continue
        if mark is not None and '[rr425] ' in line:
            t = (ts(line) - mark).total_seconds()
            if lo <= t <= hi:
                rows.append((t, {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', line.split('[rr425]', 1)[1])}))

cols = ['it', 'eo', 'g', 'gs', 'gi', 'ga', 'x', 'm', 'hc']
print('| t-mark | ' + ' | '.join(c + ' k' for c in cols) + ' | gap % |')
print('|---' * (len(cols) + 2) + '|')
for i, (t, r) in enumerate(rows):
    if i % step:
        continue
    print('| %.0f | ' % t + ' | '.join('%d' % (r.get(c, 0) // 1000) for c in cols)
          + ' | %.1f |' % (100.0 * r.get('gapus', 0) / (r.get('dt', 2000) * 1000.0)))
