#!/usr/bin/env python3
"""Arctic Thunder race reader for tcg424flip-arctic2.json (#424).

    python3 arcticread2.py <result-id-or-suffix> [...]

arcticread.py (loaded unchanged) with the window closed at its far end. The
pilot (1-1790660189 A, 1-1790660193 B) showed two things the open window
counts as gameplay:

  - the Thor's thermal pause (#507): both runs paused, A at +451 s and B at
    +388 s after `soak start` (run.log THERMAL line), and gfps fell to 4-7;
  - the race ending: B's race gave way at mark + 100 s to a 59-60 gfps screen
    with no dropped frames (a results or menu screen), a load, and another race.
    Race gfps on the Thor at MAX never reached 45 in the four runs on disk.

So the window is `mark gameplay` + 30 s to `hi`, where hi is the earliest of:
  - the pause's earliest onset: soak start + N, N from run.log's
    `THERMAL: pause ... began after +N s` (no pause: no bound);
  - the first gfps sample >= 45 after mark + 30 s;
  - `soak end`.
Every churn column, on%, cpf, ng and rt is read over [lo, hi].

Columns over arcticread.py:
  hi    the window's end, seconds after `mark gameplay`, and why: p (pause),
        m (a >= 45 sample: race over), e (soak end)
  gap   the longest gap between gfps samples in the window, including the
        last sample to hi (M4' hang check: <= 15 s). Pre-pause gaps on all
        four runs on disk are <= 4.3 s; the 20-27 s gaps of the pilot's B
        were all after its pause began.
"""
import os
import re
import sys
from datetime import timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ar = {'__file__': os.path.join(HERE, 'arcticread.py'), '__name__': 'arcticread'}
exec(compile(open(ar['__file__']).read(), 'arcticread.py', 'exec'), ar)
churn = ar['churn']
LO = 30.0


def lines(run):
    L = open(churn['R'] + run + '/logcat.txt', errors='replace').read().splitlines()
    return [x for x in L if len(x) > 18 and x[2] == '-' and x[5] == ' ']


def gfps(x):
    m = re.search(r' gfps=(\d+)', x)
    return int(m.group(1)) if m and 'hakuX-perf' in x else None


def bound(run, L):
    ts = churn['ts']
    mark = [ts(x) for x in L if 'hakuX-route' in x and 'mark gameplay' in x]
    if not mark:
        return None, None, '-'
    t0 = mark[0]
    ends = [(t, 'e') for t in (ts(x) for x in L if 'hakuX-route' in x and 'soak end' in x)]
    start = [ts(x) for x in L if 'hakuX-route' in x and 'soak start' in x]
    rl = open(churn['R'] + run + '/run.log', errors='replace').read()
    p = re.search(r'THERMAL: pause .*?began after \+(\d+) s', rl)
    if p and start:
        ends.append((start[0] + timedelta(seconds=int(p.group(1))), 'p'))
    for x in L:
        g = gfps(x)
        if g is not None and g >= 45 and (ts(x) - t0).total_seconds() >= LO:
            ends.append((ts(x), 'm'))
            break
    if not ends:
        return t0, None, '?'
    t, why = min(ends)
    return t0, (t - t0).total_seconds(), why


def main():
    cols = ['n', 'gfps', 'G', 'cpu', 'churn%', 'di/s', 'pr/s', 'slow/s',
            'inv/s', 'fs/s', 'xx']
    print('run | hi s | ng | gap s | rt | fatal | m50 | on% | cpf | ' + ' | '.join(cols))
    for r in sys.argv[1:]:
        run = churn['find'](r)
        L = lines(run)
        t0, hi, why = bound(run, L)
        if t0 is None:
            print(run, '| VOID: NO mark gameplay')
            continue
        # one() keeps s <= hi; the >= 45 sample that sets hi must stay out
        run, route, o = churn['one'](run, LO, None if hi is None else hi - 0.001)
        if o is None:
            print(run, '| VOID: no [tlb68] line in the window')
            continue
        ts = churn['ts']

        def inside(x):
            s = (ts(x) - t0).total_seconds()
            return s >= LO and (hi is None or s < hi)
        win = [x for x in L if inside(x)]
        gt = [ts(x) for x in win if gfps(x) is not None]
        edge = [t0 + timedelta(seconds=LO)] + gt + ([t0 + timedelta(seconds=hi)] if hi is not None else [])
        gap = max((b - a).total_seconds() for a, b in zip(edge, edge[1:])) if len(edge) > 1 else -1
        rt = ','.join(sorted(set(re.findall(r'\brt=(\d)', '\n'.join(x for x in win if '[tlb68]' in x))))) or '-'
        ng, _, fatal, _, m50 = ar['pr']['extra'](run)
        tl = [churn['kv'](x) for x in win if '[tlb68]' in x]
        dt = sum(churn['num'](d, 'dt') for d in tl)
        on = 100.0 * sum(churn['num'](d, 'cpu') for d in tl) / dt if dt else -1.0
        cpf = on * 10 / o['gfps'] if o['gfps'] > 0 else -1.0
        cells = [('%.1f' % o[c]) if isinstance(o[c], float) else str(o[c]) for c in cols]
        print('%s | %.0f%s | %d | %.1f | %s | %d | %d | %.1f | %.1f | %s' % (
            run, hi if hi is not None else -1, why, len(gt), gap, rt, fatal, m50,
            on, cpf, ' | '.join(cells)))


if __name__ == '__main__':
    main()
