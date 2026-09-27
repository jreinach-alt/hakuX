#!/usr/bin/env python3
"""Kick -> push-buffer callback latency, and the PFIFO thread's waits in it.

    python3 cblread.py [--from 299 --to 420] [--show] <result id | dir> ...
    python3 cblread.py --selftest

Reads the `cblat` hakuX-perf lines of a perflog build with pfifo.c's
instrument (one line per 2 s window). Per window the line carries:

  flips          FLIP_STALL methods dispatched
  n              callbacks timed (NO_OPERATION, non-zero parameter, with a kick)
  nokick         callbacks with no pending submission on record (not timed)
  shared         callbacks whose split starts at the previous callback, not
                 at their own kick (two callbacks in one submission)
  dup            callbacks dispatched while the previous one's interrupt was
                 still pending (the Android handler drops them)
  lost           submissions not recorded: the 128-entry ring was full
  rst            method dispatches whose nested counters were reset inside
                 them (the per-flip profile reset in FLIP_STALL)
  lat(...)       kick -> dispatch per callback, ms (p50/p90 in 0.25 ms bins)
  split(...)     ms summed over the window's callbacks, over NON-overlapping
                 intervals (from the later of the kick and the previous
                 callback's dispatch):
                   span    the intervals' total
                   pflip   parked: FLIP_STALL waiting for the VBLANK
                   pnop    parked: the previous callback not yet acknowledged
                   pidle   parked for anything else
                   mflip, msema, mclear, mdraw, mother
                           inside a method, by class (with its pgraph.lock wait)
                   rest    span less the eight above
                   dl, fin nested in the methods, OVERLAPPING each other:
                           the deferred surface download (cdef/surfupd) and
                           pgraph_vk_finish (every reason)
  params         the callback parameters seen, hex:count (first eight)

Per frame = the window's sums over its flips. `--show` prints one raw line
from the middle of the window.
"""
import argparse
import os
import re
import sys
from datetime import datetime
from statistics import median

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
SPLIT = ['span', 'pflip', 'pnop', 'pidle', 'mflip', 'msema', 'mclear',
         'mdraw', 'mother', 'rest', 'dl', 'fin']
PARTS = ['pflip', 'pnop', 'pidle', 'mflip', 'msema', 'mclear', 'mdraw',
         'mother', 'rest']
COUNTS = ['win', 'flips', 'n', 'nokick', 'shared', 'dup', 'lost', 'rst']


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


def parse(l):
    i = l.find('cblat ')
    if i < 0:
        return None
    s = l[i:]
    d = {}
    for k in COUNTS:
        m = re.search(r'\b' + k + r'=(\d+)', s)
        if not m:
            return None
        d[k] = int(m.group(1))
    m = re.search(r'lat\(mean=([\d.]+) p50=([\d.]+) p90=([\d.]+) max=([\d.]+)\)', s)
    if not m:
        return None
    d['lat_mean'], d['p50'], d['p90'], d['max'] = map(float, m.groups())
    m = re.search(r'split\(([^)]*)\)', s)
    if not m:
        return None
    kv = dict(x.split('=') for x in m.group(1).split())
    try:
        for k in SPLIT:
            d[k] = float(kv[k])
    except (KeyError, ValueError):
        return None
    m = re.search(r'params=(\S*) other=(\d+)', s)
    d['params'] = {}
    if m:
        for p in filter(None, m.group(1).split(',')):
            a, b = p.split(':')
            d['params'][a] = int(b)
        d['params_other'] = int(m.group(2))
    return d


def summarize(rows):
    t = {k: sum(r[k] for r in rows) for k in COUNTS + SPLIT}
    t['lines'] = len(rows)
    flips, n = t['flips'], t['n']
    t['per_flip'] = {k: (t[k] / flips if flips else None) for k in SPLIT}
    t['per_cb'] = {k: (t[k] / n if n else None) for k in SPLIT}
    t['lat_mean'] = (sum(r['lat_mean'] * r['n'] for r in rows) / n) if n else None
    busy = [r for r in rows if r['n']]
    t['p50_med'] = median(r['p50'] for r in busy) if busy else None
    t['p90_med'] = median(r['p90'] for r in busy) if busy else None
    t['max'] = max((r['max'] for r in rows), default=0.0)
    params = {}
    for r in rows:
        for a, b in r['params'].items():
            params[a] = params.get(a, 0) + b
    t['params'] = sorted(params.items(), key=lambda x: -x[1])
    parts = sum(t[k] for k in PARTS)
    t['closure'] = (parts / t['span']) if t['span'] else None
    t['rank'] = sorted(((t['per_flip'][k] or 0.0, k) for k in PARTS),
                       reverse=True)
    return t


def fmt(x, nd=2):
    return '-' if x is None else f'{x:.{nd}f}'


def report(name, t):
    print(f'== {name}: {t["lines"]} lines, {t["flips"]} flips, {t["n"]} '
          f'callbacks timed ({fmt(t["n"] / t["flips"] if t["flips"] else None)}'
          f'/flip), nokick {t["nokick"]}, shared {t["shared"]}, dup {t["dup"]}, '
          f'lost {t["lost"]}, rst {t["rst"]}')
    print(f'   kick->callback ms: mean {fmt(t["lat_mean"])}, p50 (median of '
          f'lines) {fmt(t["p50_med"])}, p90 {fmt(t["p90_med"])}, max '
          f'{fmt(t["max"])}')
    print('   split            ms/frame   ms/callback')
    for k in SPLIT:
        print(f'   {k:<8} {fmt(t["per_flip"][k]):>16} {fmt(t["per_cb"][k]):>13}')
    print(f'   closure (parts / span): {fmt(t["closure"], 3)}')
    print('   largest per frame: ' + ', '.join(
        f'{k} {fmt(v)}' for v, k in t['rank'][:3]))
    print('   params: ' + ', '.join(f'{a}:{b}' for a, b in t['params'][:8]))


def load(run, lo, hi, show):
    d = run if os.path.isdir(run) else R + run
    L = open(os.path.join(d, 'logcat.txt'), errors='replace').read().splitlines()
    t0 = None
    rows, bad, raw = [], 0, []
    for l in L:
        if len(l) < 18 or not l[:2].isdigit():
            continue
        try:
            t = ts(l)
        except ValueError:
            continue
        if t0 is None:
            t0 = t
        s = (t - t0).total_seconds()
        if 'cblat ' not in l or s < lo or s > hi:
            continue
        r = parse(l)
        if r is None:
            bad += 1
            continue
        rows.append(r)
        raw.append(l)
    if show and raw:
        print('   raw: ' + raw[len(raw) // 2])
    return rows, bad


def selftest():
    def line(sec, **kw):
        base = dict(win=2000, flips=30, n=60, nokick=0, shared=5, dup=0,
                    lost=0, rst=0, mean=20.0, p50=18.0, p90=30.0, mx=41.0,
                    span=1200.0, pflip=100.0, pnop=200.0, pidle=50.0,
                    mflip=300.0, msema=10.0, mclear=20.0, mdraw=400.0,
                    mother=90.0, rest=30.0, dl=250.0, fin=280.0,
                    params='1234:40,beef:20', other=0)
        base.update(kw)
        b = base
        return (f'09-27 10:00:{sec:06.3f}  123  456 I hakuX-perf: cblat '
                f'win={b["win"]}ms flips={b["flips"]} n={b["n"]} '
                f'nokick={b["nokick"]} shared={b["shared"]} dup={b["dup"]} '
                f'lost={b["lost"]} rst={b["rst"]} lat(mean={b["mean"]:.2f} '
                f'p50={b["p50"]:.2f} p90={b["p90"]:.2f} max={b["mx"]:.2f}) '
                f'split(span={b["span"]:.1f} pflip={b["pflip"]:.1f} '
                f'pnop={b["pnop"]:.1f} pidle={b["pidle"]:.1f} '
                f'mflip={b["mflip"]:.1f} msema={b["msema"]:.1f} '
                f'mclear={b["mclear"]:.1f} mdraw={b["mdraw"]:.1f} '
                f'mother={b["mother"]:.1f} rest={b["rest"]:.1f} '
                f'dl={b["dl"]:.1f} fin={b["fin"]:.1f}) params={b["params"]} '
                f'other={b["other"]}')

    rows = [parse(line(0)), parse(line(2, n=20, mean=50.0, flips=10,
                                       span=1300.0, pnop=600.0, mdraw=100.0,
                                       params='1234:20'))]
    assert all(rows), rows
    t = summarize(rows)
    assert t['flips'] == 40 and t['n'] == 80, t
    assert abs(t['lat_mean'] - (60 * 20 + 20 * 50) / 80) < 1e-9, t['lat_mean']
    assert abs(t['per_flip']['pnop'] - 800 / 40) < 1e-9
    assert abs(t['per_cb']['span'] - 2500 / 80) < 1e-9
    assert t['rank'][0][1] == 'pnop', t['rank']
    assert t['params'][0] == ('1234', 60), t['params']
    assert abs(t['closure'] - 1.0) < 1e-9, t['closure']
    assert parse(line(4).replace('pnop=', 'pnopx=')) is None
    assert parse(line(4).replace(' rst=0', '')) is None
    assert parse('09-27 10:00:00.000 1 2 I hakuX-perf: fifoskew win=2000ms') is None
    # Empty windows keep their counts and do not divide by zero.
    e = summarize([parse(line(6, n=0, flips=0, span=0.0))])
    assert e['per_flip']['span'] is None and e['lat_mean'] is None
    print('selftest ok')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='lo', type=float, default=0)
    ap.add_argument('--to', dest='hi', type=float, default=1e9)
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('runs', nargs='*')
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    for run in a.runs:
        rows, bad = load(run, a.lo, a.hi, a.show)
        if not rows:
            print(f'== {run}: no cblat lines in {a.lo:g}-{a.hi:g} s '
                  f'({bad} unparsed)')
            continue
        report(f'{run} {a.lo:g}-{a.hi:g} s ({bad} unparsed)', summarize(rows))
    return 0


if __name__ == '__main__':
    sys.exit(main())
