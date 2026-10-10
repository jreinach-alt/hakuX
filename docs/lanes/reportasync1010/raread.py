#!/usr/bin/env python3
"""NFS Most Wanted race start: frame period, VBLANK histogram and the report
trace, per run and pooled (#433, lane.reportasync1010).

    raread.py <result dir> [...] [--window LO,HI] [--post LO,HI] [--label X]

Reads logcat.txt. The route writes `hakuX-route: mark gameplay` (start 1, cold:
menus -> load -> race) and `mark go2` .. `mark go12` (warm restarts), each about
1.5 s before GO. Every 60 guest flips the build prints

  hakuX-pace  f=F v0=.. v1=.. v2=.. v3=.. v4=.. vb=.. max=.. ms=MS

MS is the wall time of those 60 flips (exact, not an EMA) and vK the flips
that took K VBLANKs (v4 = four or more). A pace line whose PRINT TIME falls in
[mark+LO, mark+HI] counts for that start. Default countdown window -2,1.5 (the
restart's OK is at mark-2.1, GO at mark+1.5), as phaseread.py
(docs/lanes/nfs30plan1010) selects it; post-GO window 1.5,12.

Period = sum(ms) / sum(60) over the selected lines, so a start with two lines
weighs twice. The histogram is the share of those flips in each vK.

With HAKUX_REPORT_TRACE=1 the build also prints, on hakuX-lane every 2 s,
`[rtrace] w ...` (reports.c rt_window_locked); those lines are summed over the
countdown + post-GO span of every start (mark+LO .. mark+post HI) and over the
whole run, into the step-1 table.
"""
import argparse
import os
import re
import sys

TS = re.compile(r'^(\d+)-(\d+) (\d+):(\d+):([\d.]+) ')
PACE = re.compile(r'hakuX-pace\(\s*\d+\): f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+) '
                  r'max=([\d.]+) ms=([\d.]+)')
MARK = re.compile(r'hakuX-route.*mark (gameplay|go\d+)')
RTW = re.compile(r'\[rtrace\] w mode=(\w+) (.*)$')
ON = re.compile(r'\[reportasync\] on')

HIST = ['e', 'f', 'w', 'flip', 'next']
FOUR = ['fle', 'flw']
COUNTS = ['n', 'late', 'flipb4w', 'noflip', 'reuse', 'reuseb4w', 'armed', 'stchg', 'tsours']
EDGES = ['<0.25', '<0.5', '<1', '<2', '<4', '<8', '<16.7', '<33.3', '<66.7', '>=66.7']


def secs(m):
    return int(m.group(3)) * 3600 + int(m.group(4)) * 60 + float(m.group(5))


def parse_w(s):
    out = {}
    for tok in s.split():
        if '=' not in tok:
            continue
        k, v = tok.split('=', 1)
        if k in HIST or k in FOUR:
            out[k] = [int(x) for x in v.split(',')]
        elif k in ('gate', 'wait'):
            a, b = v.split('/')
            out[k] = (int(a), int(b))
        elif k in COUNTS:
            out[k] = int(v)
    return out


def read(d):
    marks, pace, rtw = [], [], []
    mode_on = False
    with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
        for ln in f:
            m = TS.match(ln)
            if not m:
                continue
            t = secs(m)
            if 'hakuX-route' in ln:
                k = MARK.search(ln)
                if k:
                    marks.append((t, k.group(1)))
                continue
            p = PACE.search(ln)
            if p:
                pace.append((t, [int(p.group(i)) for i in range(2, 7)], float(p.group(9))))
                continue
            if '[rtrace] w' in ln:
                w = RTW.search(ln)
                if w:
                    rtw.append((t, w.group(1), parse_w(w.group(2))))
                continue
            if ON.search(ln):
                mode_on = True
    return marks, pace, rtw, mode_on


def sel(evs, marks, lo, hi, which):
    out = []
    for t0, name in marks:
        if which == 'cold' and name != 'gameplay':
            continue
        if which == 'warm' and name == 'gameplay':
            continue
        out += [e for e in evs if t0 + lo <= e[0] <= t0 + hi]
    return out


def pace_line(lines):
    if not lines:
        return 'no pace lines'
    flips = 60 * len(lines)
    ms = sum(x[2] for x in lines) / flips
    v = [sum(x[1][k] for x in lines) for k in range(5)]
    share = ' '.join(f'v{k} {100 * v[k] / flips:.0f}%' for k in range(1, 5))
    return f'{ms:5.1f} ms/frame ({1000 / ms:4.1f} fps), {len(lines):2d} lines; {share}'


def add_w(acc, w):
    for k, v in w.items():
        if k in HIST or k in FOUR:
            a = acc.setdefault(k, [0] * len(v))
            for i, x in enumerate(v):
                a[i] += x
        elif k in ('gate', 'wait'):
            a = acc.setdefault(k, [0, 0])
            a[0] += v[0]
            a[1] += v[1]
        else:
            acc[k] = acc.get(k, 0) + v


def pct(a, b):
    return f'{100 * a / b:.1f}%' if b else '-'


def median_bucket(h):
    n = sum(h)
    if not n:
        return '-'
    c = 0
    for i, x in enumerate(h):
        c += x
        if c * 2 >= n:
            return EDGES[i]
    return EDGES[-1]


def trace_table(name, acc):
    n = acc.get('n', 0)
    if not n:
        print(f'  {name}: no [rtrace] records')
        return
    print(f'  {name}: {n} reports written')
    for k, label in (('e', 'queued -> handed off (finish)'), ('f', 'queued -> fence passed'),
                     ('w', 'queued -> written'), ('flip', 'queued -> next flip'),
                     ('next', 'queued -> next GET_REPORT, same offset')):
        h = acc.get(k, [0] * 10)
        tot = sum(h)
        cum, row = 0, []
        for i in range(len(h)):
            cum += h[i]
            row.append(f'{EDGES[i]} {pct(cum, tot)}')
        print(f'    {label:40s} n={tot:6d} median {median_bucket(h):7s} cum: ' + ', '.join(row[3:9]))
    fle, flw = acc.get('fle', [0] * 4), acc.get('flw', [0] * 4)
    print(f'    flips between queue and hand-off: 0 {pct(fle[0], n)}, 1 {pct(fle[1], n)}, 2 {pct(fle[2], n)}, '
          f'3+ {pct(fle[3], n)}')
    print(f'    flips between queue and write:    0 {pct(flw[0], n)}, 1 {pct(flw[1], n)}, 2 {pct(flw[2], n)}, '
          f'3+ {pct(flw[3], n)}')
    print(f'    written after a flip the hand-off preceded (late): {acc.get("late", 0)} = {pct(acc.get("late", 0), n)}')
    print(f'    next flip before the write (flipb4w): {acc.get("flipb4w", 0)} = {pct(acc.get("flipb4w", 0), n)}'
          f'  (no flip seen yet: {acc.get("noflip", 0)})')
    reuse = acc.get('reuse', 0)
    print(f'    offset reused: {reuse}; reused before the previous write landed: {acc.get("reuseb4w", 0)} '
          f'= {pct(acc.get("reuseb4w", 0), reuse)}')
    print(f'    status word nonzero at GET_REPORT (armed): {acc.get("armed", 0)}; changed between queue and write: '
          f'{acc.get("stchg", 0)}; previous value was ours (timestamp): {acc.get("tsours", 0)}')
    g, w = acc.get('gate', [0, 0]), acc.get('wait', [0, 0])
    print(f'    finishing thread: gate waits {g[0]} ({g[1] / 1000:.1f} ms total), report waits {w[0]} '
          f'({w[1] / 1000:.1f} ms total)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--window', default='-2,1.5')
    ap.add_argument('--post', default='1.5,12')
    ap.add_argument('--label', default='')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))
    plo, phi = (float(x) for x in a.post.split(','))
    print(f'countdown: pace lines printed in mark{lo:+.1f} .. mark{hi:+.1f} s; post-GO mark{plo:+.1f} .. '
          f'mark{phi:+.1f} s {a.label}')
    pool = {'cold': [], 'warm': [], 'post_cold': [], 'post_warm': []}
    tr_race, tr_all = {}, {}
    for d in a.dirs:
        marks, pace, rtw, on = read(d)
        name = os.path.basename(d.rstrip('/'))
        print(f'{name}: {len(marks)} marks, async log {"seen" if on else "not seen"}')
        if not marks:
            continue
        rows = {'cold': sel(pace, marks, lo, hi, 'cold'), 'warm': sel(pace, marks, lo, hi, 'warm'),
                'post_cold': sel(pace, marks, plo, phi, 'cold'), 'post_warm': sel(pace, marks, plo, phi, 'warm')}
        for k in rows:
            pool[k] += rows[k]
            print(f'  {k:9s} {pace_line(rows[k])}')
        r1, r2 = {}, {}
        for t, mode, w in rtw:
            add_w(r2, w)
        for t, mode, w in sel(rtw, marks, lo, phi, 'all'):
            add_w(r1, w)
        add_w(tr_race, r1)
        add_w(tr_all, r2)
        if rtw:
            trace_table(f'trace, race starts ({rtw[0][1]})', r1)
    if len(a.dirs) > 1:
        print('POOLED:')
        for k in pool:
            print(f'  {k:9s} {pace_line(pool[k])}')
        trace_table('trace, race starts, pooled', tr_race)
        trace_table('trace, whole runs, pooled', tr_all)


if __name__ == '__main__':
    sys.exit(main())
