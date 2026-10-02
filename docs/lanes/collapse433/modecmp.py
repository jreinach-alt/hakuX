#!/usr/bin/env python3
"""Compare perflog soaks of one title by draw load (lane.collapse433, #433).

    modecmp.py <result-dir> [<result-dir> ...] [--from S] [--to S]

Every 60th guest frame a perflog build prints, at the same instant,
hakuX-pace (60-flip window), hakuX-phase (renderer phases, ~5-frame EMA, ms)
and xemu-work (the LAST frame's counts). Each such group is one row; S is
seconds after the run's `mark gameplay`. The view changes what a frame
draws, so runs are compared within bins of BE (begin/end draws in the last
frame), not as whole-run medians.

Per run and BE bin: rows, median fps of the 60-flip window, GPU Tot, Fin/Fen,
Draw and Idle ms per frame, render passes (RP), and the share of windows at
>= 29.5 fps. The render mode the run used is read from its `render_mode:`
line.
"""
import argparse, os, re, statistics

ap = argparse.ArgumentParser()
ap.add_argument('dirs', nargs='+')
ap.add_argument('--from', dest='lo', type=float, default=-40.0)
ap.add_argument('--to', dest='hi', type=float, default=1e9)
ap.add_argument('--bins', default='0,600,1200,1800,2400,9999')
a = ap.parse_args()
bins = [int(x) for x in a.bins.split(',')]
TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')


def sec(m):
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def num(rx, s):
    m = re.search(rx, s)
    return float(m.group(1)) if m else None


for d in a.dirs:
    runlog = open(os.path.join(d, 'run.log'), errors='replace').read()
    mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', runlog)
    mark = int(mk.group(1)) * 3600 + int(mk.group(2)) * 60 + float(mk.group(3))
    mode = '?'
    rows, cur = [], None
    for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
        if 'render_mode:' in line:
            mode = line.split('render_mode:', 1)[1].strip()[:60]
        m = TS.match(line)
        if not m:
            continue
        t = sec(m) - mark
        if 'hakuX-pace' in line:
            ms = num(r' ms=([\d.]+)', line)
            cur = {'t': t, 'fps': 60000.0 / ms if ms else None}
            rows.append(cur)
        elif cur is not None and abs(t - cur['t']) < 0.3:
            if 'hakuX-phase' in line:
                for k in ('Tot', 'Fin', 'Fen', 'Draw', 'Idle', 'Surf'):
                    cur[k] = num(r'(?<![A-Za-z])%s:([\d.]+)' % k, line)
                cur['GPU'] = num(r'GPU:([\d.]+)', line)
            elif 'xemu-work' in line:
                cur['BE'] = num(r'(?<![A-Za-z])BE:(\d+)', line)
                cur['RP'] = num(r'(?<![A-Za-z])RP:(\d+)', line)
    rows = [r for r in rows if a.lo <= r['t'] < a.hi and r.get('BE') is not None
            and r.get('GPU') is not None]
    print('== %s  render_mode: %s  rows %d (%.0f..%.0f s)' % (
        os.path.basename(os.path.normpath(d)), mode, len(rows),
        min([r['t'] for r in rows] or [0]), max([r['t'] for r in rows] or [0])))
    print('  %-11s %4s %6s %6s %6s %6s %6s %6s %5s %7s' % (
        'BE bin', 'n', 'fps', 'GPU', 'Fen', 'Draw', 'Idle', 'Tot', 'RP', 'ok30'))
    for lo, hi in zip(bins, bins[1:]):
        rs = [r for r in rows if lo <= r['BE'] < hi]
        if not rs:
            continue
        med = lambda k: statistics.median([r[k] for r in rs if r.get(k) is not None] or [float('nan')])
        ok = sum(1 for r in rs if r['fps'] >= 29.5)
        print('  %5d-%-5d %4d %6.1f %6.1f %6.1f %6.1f %6.1f %6.1f %5.0f %4d/%-3d' % (
            lo, hi, len(rs), med('fps'), med('GPU'), med('Fen'), med('Draw'),
            med('Idle'), med('Tot'), med('RP'), ok, len(rs)))
    rs = rows
    if rs:
        ok = sum(1 for r in rs if r['fps'] >= 29.5)
        print('  %-11s %4d %6.1f %6.1f %6.1f %6.1f %6.1f %6.1f %5.0f %4d/%-3d' % (
            'all', len(rs), statistics.median([r['fps'] for r in rs]),
            statistics.median([r['GPU'] for r in rs]),
            statistics.median([r['Fen'] for r in rs if r.get('Fen') is not None]),
            statistics.median([r['Draw'] for r in rs if r.get('Draw') is not None]),
            statistics.median([r['Idle'] for r in rs if r.get('Idle') is not None]),
            statistics.median([r['Tot'] for r in rs if r.get('Tot') is not None]),
            statistics.median([r['RP'] for r in rs]), ok, len(rs)))
