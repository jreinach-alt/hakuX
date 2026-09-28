#!/usr/bin/env python3
"""Draw self time from a perflog soak logcat (lane.forza414, #414 hunk 3).

    drawself.py <logcat.txt> [<logcat.txt> ...]

Window: `hakuX-route: mark play` + 10 s to the last hakuX-phase line - 10 s,
as forza414-snap-soak.json names it. DRAW SELF is Draw minus the bracketed
children the prediction names (Vtx Syn Prw Pipe Desc Setup Cmd); `self+` also
subtracts Sfp Mfp FTx, which the prediction did not name. Medians over lines.
"""
import re
import statistics
import sys

TS = re.compile(r'^\d\d-\d\d (\d\d):(\d\d):(\d\d)\.(\d\d\d) ')
KV = re.compile(r'([A-Za-z]+):([\d.]+)')
CHILD = ['Vtx', 'Syn', 'Prw', 'Pipe', 'Desc', 'Setup', 'Cmd']
EXTRA = ['Sfp', 'Mfp', 'FTx']
BAD = ('FATAL', 'Abort message', 'SIGABRT', 'Assertion', 'hakuX-crash')


def secs(line):
    m = TS.match(line)
    return None if not m else int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000


def read(path):
    lines = open(path, errors='replace').read().splitlines()
    play = next((secs(l) for l in lines if 'hakuX-route' in l and 'mark play' in l), None)
    phase = [(secs(l), l) for l in lines if 'hakuX-phase' in l and 'Draw:' in l]
    bad = [l for l in lines if any(b in l for b in BAD)]
    if play is None or not phase:
        return {'play': play, 'bad': len(bad)}, bad
    lo, hi = play + 10, phase[-1][0] - 10
    rows = []
    for t, l in phase:
        if t is None or not lo <= t <= hi:
            continue
        head, _, tail = l.partition('[')
        inner, _, rest = tail.partition(']')
        inner = re.sub(r'\(.*?\)', '', inner)
        h = dict((k, float(v)) for k, v in KV.findall(head))
        c = dict((k, float(v)) for k, v in KV.findall(inner))
        r = dict((k, float(v)) for k, v in KV.findall(re.sub(r'\(.*?\)', '', rest)))
        g = re.search(r'GPU:([\d.]+)', rest)
        sub = re.search(r'Sub:([\d.]+)', rest)
        self_ = h['Draw'] - sum(c.get(k, 0) for k in CHILD)
        rows.append({'Draw': h['Draw'], 'self': self_,
                     'self+': self_ - sum(c.get(k, 0) for k in EXTRA),
                     'Pipe': c.get('Pipe', 0), 'Tot': r.get('Tot', 0),
                     'Sub': float(sub[1]) if sub else 0, 'GPU': float(g[1]) if g else 0})
    out = {'play': play, 'window_s': round(hi - lo, 1), 'lines': len(rows), 'bad': len(bad),
           'draw>0': sum(1 for x in rows if x['Draw'] > 0)}
    for k in ['Draw', 'self', 'self+', 'Pipe', 'Sub', 'Tot', 'GPU']:
        out[k] = round(statistics.median(x[k] for x in rows), 2) if rows else None
    paces = []
    for t, l in [(secs(l), l) for l in lines if 'hakuX-pace' in l]:
        if t is not None and lo <= t <= hi:
            m = re.search(r' ms=([\d.]+)', l)
            if m and float(m[1]) > 0:
                paces.append(60 / (float(m[1]) / 1000))
    out['fps'] = round(statistics.median(paces), 2) if paces else None
    return out, bad


cols = [read(p) for p in sys.argv[1:]]
keys = list(cols[0][0].keys())
for k in keys:
    print(f'{k:>9} ' + ' '.join(f'{str(c[0].get(k)):>12}' for c in cols))
for p, (_, bad) in zip(sys.argv[1:], cols):
    for l in bad[:5]:
        print(p.split('/')[-2], l[:200])
