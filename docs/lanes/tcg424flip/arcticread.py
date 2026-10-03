#!/usr/bin/env python3
"""Arctic Thunder gameplay reader for tcg424flip-arctic.json (#424).

    python3 arcticread.py <result-id-or-suffix> [...]

This is docs/lanes/tbflip424/playread.py, loaded unchanged from its file, with
two strings swapped before it runs:

  'mark play'   -> 'mark gameplay'  the arctic-thunder route writes `mark
                   gameplay` (docs/testing/titles/routes/arctic-thunder.route);
                   the survey route playread was written for writes `mark play`.
  'mark booted' -> 'soak start'     the arctic-thunder route writes no `mark
                   booted`, so m50 counts gfps samples >= 50 from `soak start`
                   to `mark gameplay`: the intro video and the menus, which
                   run at the 55-60 cap on the Thor (bins 0-60 s on both
                   titleroutes runs on disk).

The window is therefore `mark gameplay` + 30 s to the end of the log, and a
run with no `mark gameplay` line is VOID. Every playread/churn.py column is
kept. Two columns are added:

  on%   the vCPU thread's on-CPU share over the window: sum of [tlb68] cpu=
        over sum of [tlb68] dt= (both ms), x 100
  cpf   vCPU on-CPU ms per game frame: on% x 10 / gfps (the window's median
        gfps). on% alone cannot tell a saving the vCPU spent on more frames
        from no saving; cpf can.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLAYREAD = os.path.join(HERE, '..', 'tbflip424', 'playread.py')
SRC = open(PLAYREAD).read()
assert SRC.count("'mark play'") == 2 and SRC.count("'mark booted'") == 1, \
    'playread.py changed'
SRC = SRC.replace("'mark play'", "'mark gameplay'")
SRC = SRC.replace("'mark booted'", "'soak start'")
SRC = SRC.replace("'NO mark play'", "'NO mark gameplay'")
pr = {'__file__': PLAYREAD, '__name__': 'playread'}
exec(compile(SRC, 'playread.py(mark gameplay)', 'exec'), pr)
churn = pr['churn']


def onshare(run, lo=30.0):
    L = open(churn['R'] + run + '/logcat.txt', errors='replace').read().splitlines()
    L = [x for x in L if len(x) > 18 and x[2] == '-' and x[5] == ' ']
    marks = [churn['ts'](x) for x in L if 'hakuX-route' in x and 'mark gameplay' in x]
    if not marks:
        return -1.0
    tl = [churn['kv'](x) for x in L if '[tlb68]' in x
          and (churn['ts'](x) - marks[0]).total_seconds() >= lo]
    dt = sum(churn['num'](d, 'dt') for d in tl)
    return 100.0 * sum(churn['num'](d, 'cpu') for d in tl) / dt if dt else -1.0


def main():
    cols = ['n', 'gfps', 'G', 'cpu', 'churn%', 'di/s', 'pr/s', 'slow/s',
            'inv/s', 'fs/s', 'xx']
    print('run | ng | rt | fatal | tail s | m50 | on% | cpf | ' + ' | '.join(cols))
    for r in sys.argv[1:]:
        run, route, o = churn['one'](churn['find'](r), 30.0, None)
        if o is None:
            print(run, '| VOID:', route if route.startswith('NO') else 'no [tlb68] line in the window')
            continue
        ng, rt, fatal, tail, m50 = pr['extra'](run)
        cells = [('%.1f' % o[c]) if isinstance(o[c], float) else str(o[c]) for c in cols]
        on = onshare(run)
        cpf = on * 10 / o['gfps'] if o['gfps'] > 0 else -1.0
        print('%s | %d | %s | %d | %.1f | %d | %.1f | %.1f | %s' % (
            run, ng, rt, fatal, tail, m50, on, cpf, ' | '.join(cells)))


if __name__ == '__main__':
    main()
