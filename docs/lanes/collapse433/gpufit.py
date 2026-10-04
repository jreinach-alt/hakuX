#!/usr/bin/env python3
"""Least-squares fit of GPU ms per frame against draws and render passes
(lane.collapse433, #433).

    gpufit.py <result-dir> [--from S]

Rows as in modecmp.py (one per 60-flip window: hakuX-phase GPU, xemu-work BE
and RP of the last frame). Fits GPU = a*BE + b*RP + c and the two
one-variable fits, and prints the residual spread of each. The phase GPU is a
~5-frame EMA and BE/RP are one frame's counts, so this is a coarse
attribution, not a per-draw cost measurement.
"""
import argparse, os, re, statistics

ap = argparse.ArgumentParser()
ap.add_argument('dir')
ap.add_argument('--from', dest='lo', type=float, default=-45.0)
a = ap.parse_args()
TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')
runlog = open(os.path.join(a.dir, 'run.log'), errors='replace').read()
mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', runlog)
mark = int(mk.group(1)) * 3600 + int(mk.group(2)) * 60 + float(mk.group(3))
rows, cur = [], None
for line in open(os.path.join(a.dir, 'logcat.txt'), errors='replace'):
    m = TS.match(line)
    if not m:
        continue
    t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) - mark
    if 'hakuX-pace' in line:
        cur = {'t': t}
        rows.append(cur)
    elif cur is not None and abs(t - cur['t']) < 0.3:
        if 'hakuX-phase' in line:
            g = re.search(r'GPU:([\d.]+)', line)
            cur['GPU'] = float(g.group(1)) if g else None
        elif 'xemu-work' in line:
            for k in ('BE', 'RP'):
                g = re.search(r'(?<![A-Za-z])%s:(\d+)' % k, line)
                cur[k] = float(g.group(1)) if g else None
rows = [r for r in rows if r['t'] >= a.lo and r.get('GPU') is not None
        and r.get('BE') is not None and r.get('RP') is not None]


def solve(X, y):
    # normal equations, tiny n, plain Gaussian elimination
    n = len(X[0])
    A = [[sum(X[k][i] * X[k][j] for k in range(len(X))) for j in range(n)] for i in range(n)]
    b = [sum(X[k][i] * y[k] for k in range(len(X))) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(A[r][i]))
        A[i], A[p], b[i], b[p] = A[p], A[i], b[p], b[i]
        for r in range(n):
            if r != i and A[i][i]:
                f = A[r][i] / A[i][i]
                A[r] = [A[r][c] - f * A[i][c] for c in range(n)]
                b[r] -= f * b[i]
    return [b[i] / A[i][i] for i in range(n)]


y = [r['GPU'] for r in rows]
print('%s: %d rows' % (os.path.basename(os.path.normpath(a.dir)), len(rows)))
for name, cols in (('BE+RP', ('BE', 'RP')), ('BE', ('BE',)), ('RP', ('RP',))):
    X = [[r[c] for c in cols] + [1.0] for r in rows]
    co = solve(X, y)
    res = [yy - sum(c * x for c, x in zip(co, xx)) for xx, yy in zip(X, y)]
    print('  GPU ~ %-6s coef %s  resid sd %.2f ms' % (
        name, ' '.join('%s=%.4f' % (n, c) for n, c in zip(list(cols) + ['c'], co)),
        statistics.pstdev(res)))
