#!/usr/bin/env python3
"""Blinx gameplay reader for #424's M4' leg (lane.tbflip424).

    python3 playread.py <result-id-or-suffix> [...]

This is docs/lanes/tbchurn424/churn.py with one change: the window hangs on the
survey route's `mark play` line, not `mark gameplay` (the survey route never
writes that). The window is `mark play` + 30 s to the end of the log. A run
with no `mark play` line is VOID. churn.py would fall back to the first log
line, which would put the menus back in the window.

On Blinx the survey route is already in the first stage before `mark play`.
The START/A rounds pause and resume the stage. After the mark, the route only
plays: stick, A presses and camera. The pass-1 frames show the stage from the
first play frame on (0-0-y-1790433159-titleplay-p1-blinx, 110116-play.png
onward).

Extra columns over churn.py:
  ng    hakuX-perf gfps samples in the window (M0 needs >= 20)
  rt    the [tlb68] rt= values seen in the window (A: 0 only, B: 1 only)
  fatal lines in logcat.txt carrying `Fatal signal` or `FATAL` (M4': 0)
  tail  seconds from the window's last gfps sample to `soak end` (M4': <= 15)
  m50   gfps samples >= 50 between `mark booted` and `mark play`. The title
        and menu screens run at the 59 cap, so a run with few of them had a
        slow device, not a slow build (tbflip424-blinx2.json M0 needs >= 4;
        the Thor's slow run 1790467161-titlebench-2612887 reads 1)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, '..', 'tbchurn424', 'churn.py')).read()

OLD_MARK = "'mark gameplay' in x]"
OLD_T0 = "t0 = marks[0] if marks else ts(L[0])"
assert SRC.count(OLD_MARK) == 1 and SRC.count(OLD_T0) == 1, 'churn.py changed'
SRC = SRC.replace(OLD_MARK, "'mark play' in x]")
SRC = SRC.replace(OLD_T0, "t0 = marks[0] if marks else None\n"
                  "    if t0 is None:\n"
                  "        return run, 'NO mark play', None")
SRC = SRC.replace("if __name__ == '__main__':", "if False:")
churn = {}
exec(compile(SRC, 'churn.py(mark play)', 'exec'), churn)


def extra(run, lo=30.0):
    L = open(churn['R'] + run + '/logcat.txt', errors='replace').read().splitlines()
    L = [x for x in L if len(x) > 18 and x[2] == '-' and x[5] == ' ']
    fatal = sum(1 for x in L if 'Fatal signal' in x or 'FATAL' in x)
    marks = [churn['ts'](x) for x in L if 'hakuX-route' in x and 'mark play' in x]
    if not marks:
        return 0, '-', fatal, -1, 0
    t0 = marks[0]
    boot = [churn['ts'](x) for x in L if 'hakuX-route' in x and 'mark booted' in x]
    m50 = sum(1 for x in L if 'hakuX-perf' in x and boot
              and boot[0] <= churn['ts'](x) < t0
              and int((re.search(r'gfps=(\d+)', x) or [0, 0])[1]) >= 50)
    win = [x for x in L if (churn['ts'](x) - t0).total_seconds() >= lo]
    gf = [x for x in win if 'hakuX-perf' in x and 'gfps=' in x]
    rt = sorted(set(re.findall(r'\brt=(\d)', '\n'.join(x for x in win if '[tlb68]' in x))))
    ends = [churn['ts'](x) for x in L if 'hakuX-route' in x and 'soak end' in x]
    tail = (ends[-1] - churn['ts'](gf[-1])).total_seconds() if ends and gf else -1
    return len(gf), ','.join(rt) or '-', fatal, tail, m50


def main():
    cols = ['n', 'gfps', 'G', 'cpu', 'churn%', 'di/s', 'pr/s', 'slow/s',
            'inv/s', 'fs/s', 'xx']
    print('run | ng | rt | fatal | tail s | m50 | ' + ' | '.join(cols))
    for r in sys.argv[1:]:
        run, route, o = churn['one'](churn['find'](r), 30.0, None)
        if o is None:
            print(run, '| VOID:', route if route.startswith('NO') else 'no [tlb68] line in the window')
            continue
        ng, rt, fatal, tail, m50 = extra(run)
        cells = [('%.1f' % o[c]) if isinstance(o[c], float) else str(o[c]) for c in cols]
        print('%s | %d | %s | %d | %.1f | %d | %s' % (run, ng, rt, fatal, tail, m50, ' | '.join(cells)))


if __name__ == '__main__':
    main()
