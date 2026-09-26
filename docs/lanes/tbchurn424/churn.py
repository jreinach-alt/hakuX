#!/usr/bin/env python3
"""Translation-cache churn over a soak's gameplay span, for #424.

    python3 churn.py [--from S] [--to S] <result-id-or-suffix> [...]

The span starts at the route's `mark gameplay` line (or the first log line
when the soak ran no route) plus --from seconds (default 30), and ends --to
seconds after that mark (default: end of log). Everything is summed over the
[tlb68] and hakuX-pages lines whose timestamps fall inside the span.

Columns
  gfps    median hakuX-perf gfps in the span; G = median game ms
  cpu     vCPU thread CPU ms summed over the [tlb68] windows (`cpu=`)
  jc%     tcg_flush_jmp_cache time (`jcus`) as a share of that CPU
  rd%     vCPU-thread tlb_reset_dirty time (`rdus`) as a share of it
  churn%  jc% + rd%: the time the two #424 mechanisms take on the vCPU
          thread, timed directly by the build rather than sampled
  rdo%    tlb_reset_dirty from other threads (`rdous`), against the same
          vCPU CPU total, for scale only -- it is not on the vCPU thread
  di/s    blocks discarded per second of span
  pr/s    arming walks (tlb_protect_code) per second
  slow/s  notdirty slow stores per second (`slow stores N`)
  inv/s   of those, the ones that reached the invalidator
  fs/s    stores the #424 code bitmap answered without the page walk
          (`cb=` on the pages line; absent before #424)
  xx      the impossible row, summed; must be 0

A span with no [tlb68] line is VOID, not zero.
"""
import os
import re
import sys
from datetime import datetime
from statistics import median

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def ts(line):
    return datetime.strptime('2026-' + line[:18], '%Y-%m-%d %H:%M:%S.%f')


def kv(line):
    return {k: v for k, v in re.findall(r'(\w+)=(-?[\w.:/,]+)', line)}


def num(d, k):
    try:
        return int(d.get(k, 0))
    except ValueError:
        return 0


def find(r):
    hits = sorted(d for d in os.listdir(R) if d == r or d.endswith(r))
    if not hits:
        sys.exit('no result matches ' + r)
    return hits[0]


def one(run, lo, hi):
    L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
    L = [x for x in L if len(x) > 18 and x[2] == '-' and x[5] == ' ']
    marks = [ts(x) for x in L if 'hakuX-route' in x and 'mark gameplay' in x]
    t0 = marks[0] if marks else ts(L[0])
    route = 'route' if marks else 'no-route'

    def inside(x):
        s = (ts(x) - t0).total_seconds()
        return s >= lo and (hi is None or s <= hi)

    tl = [kv(x) for x in L if '[tlb68]' in x and inside(x)]
    pg = [kv(x) for x in L if 'hakuX-pages' in x and 'inval ev=' in x and inside(x)]
    ss = [x for x in L if 'hakuX-pages' in x and 'slow stores' in x and inside(x)]
    gf = [x for x in L if 'hakuX-perf' in x and 'gfps=' in x and inside(x)]
    if not tl:
        return run, route, None
    cpu = sum(num(d, 'cpu') for d in tl)
    wall = sum(num(d, 'dt') for d in tl) / 1000.0
    jc = sum(num(d, 'jcus') for d in tl) / 1000.0
    rd = sum(num(d, 'rdus') for d in tl) / 1000.0
    rdo = sum(num(d, 'rdous') for d in tl) / 1000.0
    slow = inv = 0
    for x in ss:
        m = re.search(r'slow stores (\d+) \((\d+) reached', x)
        if m:
            slow += int(m.group(1))
            inv += int(m.group(2))
    g = [int(re.search(r'gfps=(\d+)', x).group(1)) for x in gf]
    gm = [float(m.group(1)) for m in (re.search(r' G:([\d.]+)', x) for x in gf) if m]
    out = {
        'n': len(tl), 'wall': wall,
        'gfps': median(g) if g else -1, 'G': median(gm) if gm else -1,
        'cpu': cpu,
        'jc%': 100 * jc / cpu if cpu else 0,
        'rd%': 100 * rd / cpu if cpu else 0,
        'rdo%': 100 * rdo / cpu if cpu else 0,
        'di/s': sum(num(d, 'di') for d in pg) / wall,
        'pr/s': sum(num(d, 'pr') for d in pg) / wall,
        'slow/s': slow / wall, 'inv/s': inv / wall,
        'fs/s': sum(num(d, 'cb') for d in pg) / wall,
        'xx': sum(num(d, 'xx') for d in pg),
        'fx': tl[-1].get('fx', '?'),
    }
    out['churn%'] = out['jc%'] + out['rd%']
    return run, route, out


def main():
    args = sys.argv[1:]
    lo, hi = 30.0, None
    while args and args[0].startswith('--'):
        k, v = args.pop(0), float(args.pop(0))
        if k == '--from':
            lo = v
        elif k == '--to':
            hi = v
    cols = ['n', 'gfps', 'G', 'cpu', 'jc%', 'rd%', 'churn%', 'rdo%',
            'di/s', 'pr/s', 'slow/s', 'inv/s', 'fs/s', 'xx', 'fx']
    print('run | span | ' + ' | '.join(cols))
    for r in args:
        run, route, o = one(find(r), lo, hi)
        if o is None:
            print(run, '|', route, '| VOID: no [tlb68] line in the span')
            continue
        cells = []
        for c in cols:
            v = o[c]
            cells.append(('%.1f' % v) if isinstance(v, float) else str(v))
        print(run + ' | ' + route + ' | ' + ' | '.join(cells))


if __name__ == '__main__':
    main()
