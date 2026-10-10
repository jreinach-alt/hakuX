#!/usr/bin/env python3
"""Frametrace per-thread account for route windows (#433, lane.nfs30plan1010).

    ftwin.py <result dir> [...] [--window LO,HI] [--heavy 60] [--cols a,b,c] [--all-cols]

Reads <dir>/pulled/frametrace_*.csv (the one whose frames overlap the run's
marks) and <dir>/logcat.txt. Frame wall time comes from the `[hakuX-ft1] n=
rt_ms= t_ms=` anchors (rt_ms is epoch ms, t_ms the trace's monotonic ms;
the CSV's t_ns is the same monotonic clock). Marks are `hakuX-route: mark
gameplay|goN` in logcat (device local time; the offset to epoch is taken
from the first anchor, rounded to the hour).

For every frame whose END time lies in [mark+LO, mark+HI] (default -2,1.5,
the countdown) it pools the per-frame columns and prints, in ms per frame:
the period P, the pacemaker classes (`cls`), the critical path (`crit`), and
the three thread rows:

  v  guest vCPU : v_run (on CPU, incl. the guest's idle spin), gidle (of
                  which, the guest idle loop), v_rq (runnable, not scheduled),
                  v_blk (blocked) and the blocked time by site v_<site>
  p  PFIFO      : p_run, p_rq, p_blk, pidle (waiting for a kick) and p_<site>
  r  render     : r_run, r_rq, r_blk and r_<site>
  m  main loop  : m_run, m_rq, m_blk (profile.h HAKUX_FT_MAIN, registered in
                  system/cpus.c:448; the submit worker is NOT a row: its waits
                  land in o_*, as do the render thread's when its row is absent)
  o  other threads' Vulkan waits o_<site>
  gpu           : GPU busy (timestamps), rp render passes, mhz GPU clock
sites: bql pfl pgl halt idle fence submit rthr dl oth (profile.h hakux_ft_w_name).

`--heavy MS` adds the same table over the window's frames with P >= MS.
Everything is a mean over the selected frames unless marked p50/p95.
"""
import argparse
import csv
import glob
import os
import re
import statistics
import sys

TS = re.compile(r'^(\d+)-(\d+) (\d+):(\d+):([\d.]+) ')
MARK = re.compile(r'hakuX-route.*mark (gameplay|go\d+)')
ANCH = re.compile(r'\[hakuX-ft1\] n=\d+ rt_ms=(\d+) t_ms=([\d.]+)')

MS_COLS = ['P', 'crit', 'v_run', 'gidle', 'v_rq', 'v_blk', 'v_bql', 'v_pfl', 'v_pgl', 'v_halt', 'v_idle', 'v_fence',
           'v_submit', 'v_rthr', 'v_dl', 'v_oth', 'lockw', 'p_run', 'p_rq', 'p_blk', 'pidle', 'p_bql', 'p_pfl',
           'p_pgl', 'p_idle', 'p_fence', 'p_submit', 'p_rthr', 'p_dl', 'p_oth', 'r_run', 'r_rq', 'r_blk', 'r_fence',
           'r_submit', 'r_rthr', 'r_oth', 'm_run', 'm_rq', 'm_blk', 'o_fence', 'o_submit', 'o_oth', 'gpu', 'slack']
CNT_COLS = ['vb', 'np', 'rp', 'mhz', 'ins', 'mmio', 'nmmio', 'have']
GROUPS = [
    ('frame', ['P', 'crit', 'gpu', 'slack']),
    ('vCPU', ['v_run', 'gidle', 'v_rq', 'v_blk', 'v_bql', 'v_pfl', 'v_pgl', 'v_halt', 'v_fence', 'v_submit', 'v_rthr', 'v_dl', 'v_oth']),
    ('PFIFO', ['p_run', 'p_rq', 'p_blk', 'pidle', 'p_bql', 'p_pgl', 'p_fence', 'p_submit', 'p_rthr', 'p_dl', 'p_oth', 'lockw']),
    ('render', ['r_run', 'r_rq', 'r_blk', 'r_fence', 'r_submit', 'r_rthr', 'r_oth']),
    ('main loop', ['m_run', 'm_rq', 'm_blk']),
    ('other waits', ['o_fence', 'o_submit', 'o_oth']),
]


def secs(m):
    return int(m.group(3)) * 3600 + int(m.group(4)) * 60 + float(m.group(5))


def read_log(path):
    marks, anchors = [], []
    with open(path, errors='replace') as f:
        for ln in f:
            m = TS.match(ln)
            if not m:
                continue
            t = secs(m)
            k = MARK.search(ln)
            if k:
                marks.append((t, k.group(1)))
                continue
            a = ANCH.search(ln)
            if a:
                anchors.append((t, int(a.group(1)), float(a.group(2))))
    return marks, anchors


def read_csv(path):
    rows = []
    with open(path, errors='replace') as f:
        for r in csv.DictReader(f):
            try:
                rows.append({k: (v if k == 'cls' else (int(v) if v not in ('', None) else None)) for k, v in r.items()})
            except ValueError:
                continue
    return rows


def pick_csv(d, anchors):
    """The CSV whose t_ns range covers the anchors' t_ms."""
    best, bestn = None, -1
    for p in sorted(glob.glob(os.path.join(d, 'pulled', 'frametrace_*.csv'))):
        rows = read_csv(p)
        if not rows:
            continue
        lo, hi = rows[0]['t_ns'] / 1e6, rows[-1]['t_ns'] / 1e6
        n = sum(1 for _, _, tm in anchors if lo <= tm <= hi)
        if n > bestn:
            best, bestn, bestrows = p, n, rows
    return best, bestrows


def wall_of(rows, anchors):
    """Attach device-local wall secs to each frame's end (t_ns)."""
    # offset monotonic ms -> epoch ms, from the anchors (median)
    offs = statistics.median([rt - tm for _, rt, tm in anchors])
    # epoch secs -> device local secs-of-day: from the first anchor's logcat time
    t0, rt0, _ = anchors[0]
    ep0 = rt0 / 1000.0
    tz = round((t0 - ep0 % 86400) / 3600.0) * 3600
    for r in rows:
        ep = (r['t_ns'] / 1e6 + offs) / 1000.0
        r['wall'] = (ep % 86400) + tz
    return tz


def mean(xs):
    return sum(xs) / len(xs) if xs else float('nan')


def table(name, fr, show_all):
    if not fr:
        print(f"  {name}: no frames")
        return
    n = len(fr)
    P = [r['P'] / 1000.0 for r in fr]
    cls = {}
    for r in fr:
        cls[r['cls']] = cls.get(r['cls'], 0) + 1
    late = sum(1 for r in fr if r['late'])
    print(f"  {name}: {n} frames, P mean {mean(P):.1f} p50 {statistics.median(P):.1f} p95 {sorted(P)[int(0.95 * (n - 1))]:.1f} ms, "
          f"late {100 * late / n:.0f}%, cls " + ' '.join(f"{k}:{100 * v / n:.0f}%" for k, v in sorted(cls.items(), key=lambda x: -x[1])))
    for g, cols in GROUPS:
        parts = []
        for c in cols:
            vals = [r[c] for r in fr if r.get(c) is not None]
            if not vals:
                continue
            m = mean(vals) / 1000.0
            if m >= 0.05 or c in ('P', 'crit', 'gpu', 'v_run', 'p_run', 'r_run', 'm_run'):
                parts.append(f"{c}={m:.1f}")
        print(f"    {g:14s} " + ' '.join(parts))
    parts = []
    for c in CNT_COLS:
        vals = [r[c] for r in fr if r.get(c) is not None]
        if vals:
            parts.append(f"{c}={mean(vals):.1f}")
    print(f"    {'counts':14s} " + ' '.join(parts))
    if show_all:
        keys = [k for k in fr[0].keys() if k not in ('cls', 'wall')]
        print('    all: ' + ' '.join(f"{k}={mean([r[k] for r in fr if r.get(k) is not None]) / 1000.0:.2f}" for k in keys))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--window', default='-2,1.5')
    ap.add_argument('--heavy', type=float, default=0.0, help='also table frames with P >= this many ms')
    ap.add_argument('--all-cols', action='store_true')
    ap.add_argument('--per-mark', action='store_true')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))
    print(f"window: frame end in mark{lo:+.1f} .. mark{hi:+.1f} s; ms per frame (means)")
    pooled = []
    for d in a.dirs:
        marks, anchors = read_log(os.path.join(d, 'logcat.txt'))
        if not anchors or not marks:
            print(f"{d}: anchors {len(anchors)} marks {len(marks)}")
            continue
        path, rows = pick_csv(d, anchors)
        wall_of(rows, anchors)
        sel = []
        for mt, name in marks:
            fr = [r for r in rows if mt + lo <= r['wall'] <= mt + hi]
            if a.per_mark:
                table(name, fr, False)
            sel += fr
        print(f"{os.path.basename(d)} ({os.path.basename(path)}, {len(rows)} frames, {len(marks)} marks)")
        table('all in window', sel, a.all_cols)
        if a.heavy:
            table(f'P >= {a.heavy:.0f} ms', [r for r in sel if r['P'] >= a.heavy * 1000], a.all_cols)
        pooled += sel
    if len(a.dirs) > 1:
        print('POOLED')
        table('all in window', pooled, a.all_cols)
        if a.heavy:
            table(f'P >= {a.heavy:.0f} ms', [r for r in pooled if r['P'] >= a.heavy * 1000], a.all_cols)


if __name__ == '__main__':
    sys.exit(main())
