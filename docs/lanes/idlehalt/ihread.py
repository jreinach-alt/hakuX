#!/usr/bin/env python3
"""#525 idle halt: read a soak's [idlehalt] lines (and gfps) over a window.

    python3 ihread.py [--from S] [--to S] [--play [+A[,-B]]] <result-id | logcat> [...]

Windows are seconds since the logcat's first line, as rr425.py counts them.
--play takes the window from the route's `mark play` instead: from the mark
plus A seconds (default 10) to the log's end minus B (default 10).

Per result it prints, over the [idlehalt] windows whose line falls inside:
  on                the HAKUX_IDLE_HALT the build ran with
  fps               1000 / mean(G) of the hakuX-perf lines in the span
  run%, rq%         the vCPU thread's on-CPU and run-queue wait share of
                    wall time (schedstat deltas over span_us)
  halts/s, imm      idiom halts per second; halts with work already pending
  slept%            share of wall time the vCPU spent halted in the idiom
  wakes             by class at the first kick: pg (PGRAPH ERROR, the
                    push-buffer callback), pgo, vb, fifo, ot
  to, tp, tr        timeouts: idle; with work pending and no kick (a missed
                    wake); with work pending after a kick (timedwait race)
  lpg, lall         raise-to-run histogram (us: <5 <10 <20 <50 <100 <200
                    >=200), share at >= 50 us, and the maximum
  pc, xpc           the idiom's cli, and halts at any other pc
And from [rr425w] in the same span, the guest's idle share (idle_us /
(idle_us + busy_us)), which is what run% should fall towards.

The checks owed before a number is read: at least 20 windows; span_us sums
to within 5% of the window's wall clock; run_us >= 0 in every window (a
failed schedstat read prints -1). A failed check prints FAIL and the row is
VOID, not a zero.

--selftest runs it on a built-in logcat.
"""
import os
import re
import sys
from datetime import datetime

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
KV = re.compile(r'(\w+)=(-?[0-9a-f]+)')
BINS = ['<5', '<10', '<20', '<50', '<100', '<200', '>=200']
CLASSES = ['pg', 'pgo', 'vb', 'fifo', 'ot']


def ts(line):
    return datetime.strptime('2026-' + line[:18], '%Y-%m-%d %H:%M:%S.%f')


def parse(body):
    out = {}
    for k, v in KV.findall(body):
        if k in ('lpg', 'lall', 'pc'):
            continue
        try:
            out[k] = int(v)
        except ValueError:
            pass
    for k in ('lpg', 'lall'):
        m = re.search(r' %s=([\d/]+)' % k, body)
        out[k] = [int(x) for x in m.group(1).split('/')] if m else [0] * 7
    m = re.search(r' pc=([0-9a-f]{8})', body)
    out['pc'] = m.group(1) if m else '?'
    return out


def read(lines, lo, hi, play=None):
    rows = []
    stamp = []
    t0 = None
    mark = None
    for line in lines:
        try:
            t = ts(line)
        except ValueError:
            continue
        if t0 is None:
            t0 = t
        s = (t - t0).total_seconds()
        stamp.append((s, line))
        if mark is None and 'mark play' in line:
            mark = s
    end = stamp[-1][0] if stamp else 0
    if play is not None:
        if mark is None:
            return None, 'no `mark play` in the log'
        lo, hi = mark + play[0], end - play[1]
    ih, gms, idle, busy = [], [], 0, 0
    for s, line in stamp:
        if not lo <= s <= hi:
            continue
        if '[idlehalt] w=' in line:
            ih.append(parse(line.split('[idlehalt]', 1)[1]))
        elif '[rr425w] ' in line:
            m = re.search(r'idle_us=(\d+) busy_us=(\d+)', line)
            if m:
                idle += int(m.group(1))
                busy += int(m.group(2))
        elif 'hakuX-perf' in line:
            m = re.search(r' G:([\d.]+)', line)
            if m and float(m.group(1)) > 0:
                gms.append(float(m.group(1)))
    return dict(lo=lo, hi=hi, ih=ih, gms=gms, idle=idle, busy=busy), None


def summarize(d):
    ih = d['ih']
    tot = {}
    for r in ih:
        for k, v in r.items():
            if isinstance(v, int):
                tot[k] = tot.get(k, 0) + v
    lpg = [sum(r['lpg'][i] for r in ih) for i in range(7)]
    lall = [sum(r['lall'][i] for r in ih) for i in range(7)]
    span = tot.get('span_us', 0)
    wall_us = (d['hi'] - d['lo']) * 1e6
    checks = [
        ('>= 20 windows', len(ih) >= 20),
        ('span within 5% of the window', span > 0 and wall_us > 0
         and abs(span - wall_us) <= 0.05 * wall_us + 2.1e6),
        ('schedstat read in every window', all(r.get('run_us', -1) >= 0 for r in ih)),
    ]
    out = dict(n=len(ih), checks=checks,
               on=sorted({r.get('on', -1) for r in ih}),
               fps=1000.0 / (sum(d['gms']) / len(d['gms'])) if d['gms'] else None,
               run=tot.get('run_us', 0) / span if span else None,
               rq=tot.get('rq_us', 0) / span if span else None,
               slept=tot.get('slept_us', 0) / span if span else None,
               halts_s=tot.get('halts', 0) / (span / 1e6) if span else None,
               tot=tot, lpg=lpg, lall=lall,
               pcs=sorted({r['pc'] for r in ih}),
               guest_idle=(d['idle'] / (d['idle'] + d['busy'])
                           if d['idle'] + d['busy'] else None))
    return out


def pct(x):
    return 'n/a' if x is None else '%.1f%%' % (100 * x)


def at_or_above_50(h):
    n = sum(h)
    return None if not n else sum(h[4:]) / n


def report(name, s):
    t = s['tot']
    ok = all(c for _, c in s['checks'])
    print('== %s  windows=%d  on=%s  %s' % (name, s['n'], s['on'],
                                            'ok' if ok else 'VOID'))
    for label, c in s['checks']:
        print('   check %-34s %s' % (label, 'ok' if c else 'FAIL'))
    print('   fps %s  run %s  rq %s  guest idle (rr425w) %s' % (
        '%.2f' % s['fps'] if s['fps'] else 'n/a', pct(s['run']), pct(s['rq']),
        pct(s['guest_idle'])))
    print('   halts/s %s  imm %d  slept %s  pit %d  pc %s  xpc %d' % (
        '%.0f' % s['halts_s'] if s['halts_s'] is not None else 'n/a',
        t.get('imm', 0), pct(s['slept']), t.get('pit', 0),
        ','.join(s['pcs']), t.get('xpc', 0)))
    print('   wakes ' + ' '.join('%s=%d' % (c, t.get(c, 0)) for c in CLASSES))
    print('   timeouts to=%d tp=%d tr=%d' % (t.get('to', 0), t.get('tp', 0),
                                            t.get('tr', 0)))
    for k, h in (('lpg', s['lpg']), ('lall', s['lall'])):
        print('   %-4s %s  >=50us %s' % (
            k, ' '.join('%s:%d' % (b, n) for b, n in zip(BINS, h)),
            pct(at_or_above_50(h))))
    return ok


def load(arg):
    path = arg if os.path.isfile(arg) else os.path.join(R, arg, 'logcat.txt')
    return open(path, errors='replace').read().splitlines()


SELFTEST = """09-27 20:00:00.000 I/boot: start
09-27 20:00:01.000 I/hakuX: mark play
""" + ''.join(
    '09-27 20:00:%02d.000 W/hakuX(1): [idlehalt] w=%d on=1 span_us=2000000 '
    'run_us=900000 rq_us=20000 halts=1000 pc=8001b031 xpc=0 imm=10 pg=4 '
    'pgo=0 vb=6 fifo=0 ot=980 to=5 tp=0 tr=1 slept_us=1100000 pit=990 '
    'lpg=0/2/2/0/0/0/0 lpgmax=15 lall=100/800/80/10/0/0/0 lallmax=60\n'
    '09-27 20:00:%02d.500 I/hakuX-perf(1): gfps=20 G:50.0(3.3-340.2) D:16.7\n'
    '09-27 20:00:%02d.600 W/hakuX(1): [rr425w] w=%d idlepc=8001b02e '
    'idle_us=1200000 busy_us=800000 n=1 nb=0 drop=0\n'
    % ((2 + i * 2) % 60, i, (2 + i * 2) % 60, (2 + i * 2) % 60, i)
    for i in range(29))


def selftest():
    d, err = read(SELFTEST.splitlines(), 0, 1e9, play=(0, 0))
    assert err is None, err
    s = summarize(d)
    assert s['n'] == 29, s['n']
    assert abs(s['run'] - 0.45) < 1e-9, s['run']
    assert abs(s['guest_idle'] - 0.6) < 1e-9, s['guest_idle']
    assert s['tot']['halts'] == 29000 and s['tot']['tr'] == 29
    assert s['lpg'] == [0, 58, 58, 0, 0, 0, 0]
    assert at_or_above_50(s['lall']) == 0.0
    assert abs(s['fps'] - 20.0) < 1e-9
    assert all(c for _, c in s['checks']), s['checks']
    # A failed schedstat read voids the row.
    bad = SELFTEST.replace('run_us=900000', 'run_us=-1', 1)
    d, _ = read(bad.splitlines(), 0, 1e9, play=(0, 0))
    assert not all(c for _, c in summarize(d)['checks'])
    # Too few windows voids it too.
    d, _ = read(SELFTEST.splitlines(), 0, 10)
    assert not summarize(d)['checks'][0][1]
    print('selftest ok')


def main(argv):
    if argv[:1] == ['--selftest']:
        selftest()
        return 0
    lo, hi, play, ids = 0, 1e9, None, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--from':
            lo = float(argv[i + 1]); i += 2
        elif a == '--to':
            hi = float(argv[i + 1]); i += 2
        elif a == '--play':
            play = (10.0, 10.0)
            if i + 1 < len(argv) and argv[i + 1].startswith('+'):
                p = argv[i + 1][1:].split(',')
                play = (float(p[0]), float(p[1].lstrip('-')) if len(p) > 1 else 10.0)
                i += 1
            i += 1
        else:
            ids.append(a); i += 1
    rc = 0
    for x in ids:
        d, err = read(load(x), lo, hi, play)
        if err:
            print('== %s  VOID: %s' % (x, err))
            rc = 1
            continue
        print('   window %.0f-%.0f s' % (d['lo'], d['hi']))
        if not report(x, summarize(d)):
            rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
