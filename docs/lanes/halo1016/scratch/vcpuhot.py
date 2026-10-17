#!/usr/bin/env python3
"""Where the vCPU goes in a cinematic run, plateau against a 30-fps window. Read only.

usage: vcpuhot.py <result dir> [plateau_lo plateau_hi] [calm_lo calm_hi]   (seconds after `mark cinematic`)

1. [rr425pc]: main-loop returns by (cause, pc), per 2-s window, top 12 per span.
2. [tpc787]: sampled time inside TBs by entry pc (1 in 64 dispatches), top 15 per span, as a share of the
   span's sampled us; also [tcg787] (cputlb) lines' totals if present.
3. The longjmp (x) and CF_INVALID (gi) pcs alone.
"""
import re
import sys
from collections import Counter
from datetime import datetime

d = sys.argv[1]
P = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (131.0, 191.0)
C = (float(sys.argv[4]), float(sys.argv[5])) if len(sys.argv) > 5 else (101.0, 115.0)
TS = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)')
PCE = re.compile(r' (\w):([0-9a-f]{8}):([0-9a-f]{6}):(\d+)')
TPE = re.compile(r' ([0-9a-f]{8}):([0-9a-f]{6}):(\d+):(\d+)')


def ts(line):
    m = TS.match(line)
    return datetime.strptime('2026-' + m.group(1), '%Y-%m-%d %H:%M:%S.%f') if m else None


mark = None
spans = {'plateau': P, 'calm': C}
rr = {k: Counter() for k in spans}
rrn = {k: 0 for k in spans}
tp = {k: Counter() for k in spans}
tpn = {k: Counter() for k in spans}
tpus = {k: 0 for k in spans}
tcg = {k: [] for k in spans}
other = Counter()
with open(d + '/logcat.txt', errors='replace') as f:
    for line in f:
        if mark is None:
            if 'mark cinematic' in line:
                mark = ts(line)
            continue
        if '[rr425pc]' not in line and '[tpc787]' not in line and '[tcg787]' not in line:
            continue
        t = ts(line)
        if t is None:
            continue
        s = (t - mark).total_seconds()
        for k, (lo, hi) in spans.items():
            if not lo < s <= hi + 2:
                continue
            if '[rr425pc]' in line:
                rrn[k] += 1
                for c, pc, b, n in PCE.findall(line):
                    rr[k][(c, pc, b)] += int(n)
            elif '[tpc787]' in line:
                m = re.search(r' us=(\d+)', line)
                tpus[k] += int(m.group(1)) if m else 0
                for pc, b, us, n in TPE.findall(line):
                    tp[k][(pc, b)] += int(us)
                    tpn[k][(pc, b)] += int(n)
            else:
                tcg[k].append(line.split('[tcg787]', 1)[1].strip()[:200])

for k, (lo, hi) in spans.items():
    print('## %s: mark+%.0f..%.0f (%d [rr425pc] windows)\n' % (k, lo, hi, rrn[k]))
    w = max(rrn[k], 1)
    print('| cause | pc | bytes | per 2 s |')
    print('|---|---|---|---|')
    for (c, pc, b), n in rr[k].most_common(12):
        print('| %s | %s | %s | %.0f |' % (c, pc, b, n / w))
    print('\n| cause | pc | bytes | per 2 s (x and g only) |')
    print('|---|---|---|---|')
    for (c, pc, b), n in [e for e in rr[k].most_common() if e[0][0] in 'xg'][:10]:
        print('| %s | %s | %s | %.0f |' % (c, pc, b, n / w))
    print('\n[tpc787] sampled us in span %d; top entry pcs:\n' % tpus[k])
    print('| pc | bytes | us | share | n |')
    print('|---|---|---|---|---|')
    for (pc, b), us in tp[k].most_common(15):
        print('| %s | %s | %d | %.1f%% | %d |' % (pc, b, us, 100.0 * us / max(tpus[k], 1), tpn[k][(pc, b)]))
    if tcg[k]:
        print('\n[tcg787] first lines:')
        for l in tcg[k][:3]:
            print('    ' + l)
    print()
