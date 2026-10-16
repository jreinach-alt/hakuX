#!/usr/bin/env python3
"""Surface-download finishes per frame against frame time, per 60-frame
window of a perflog logcat (NV2A_PERF_LOG build).

Pairs each hakuX-stall `Finish:N(... sdM ... presP flipF ...)` line with the
nearest hakuX-perf `gfps= G:` line and hakuX-phase line, and fits frame time
G (ms) on downloads per frame by least squares. A slope near the measured
per-finish cost, with the intercept near the frame time of a window with no
downloads, says the frame time is the downloads'; a flat slope says it is
not. Usage:

    dlrate.py LOGCAT [--from HH:MM:SS] [--to HH:MM:SS] [--min-gfps N]
"""
import argparse
import re
import sys
from datetime import datetime

TS = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d)\s')
STALL = re.compile(r'hakuX-stall\(\d+\): RPBreaks:\d+ Finish:(\d+)\(.*?'
                   r'sd(\d+) .*?pres(\d+) flip(\d+) ')
PERF = re.compile(r'gfps=(\d+) G:([\d.]+)')
PHASE = re.compile(r'Draw:([\d.]+) .*Fin:([\d.]+)\(Sub:([\d.]+) Fen:([\d.]+)\)'
                   r'.*Tot:([\d.]+) GPU:([\d.]+)\(R:([\d.]+) X:([\d.]+)')


def ts(line):
    m = TS.match(line)
    if not m:
        return None
    return datetime.strptime('2026-' + m.group(1),
                             '%Y-%m-%d %H:%M:%S.%f').timestamp()


def nearest(seq, t, tol=1.5):
    best = min(seq, key=lambda x: abs(x[0] - t)) if seq else None
    return best[1] if best and abs(best[0] - t) <= tol else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--from', dest='t_from')
    ap.add_argument('--to', dest='t_to')
    ap.add_argument('--min-gfps', type=int, default=1)
    ap.add_argument('--min-sd', type=float, default=0.0,
                    help='only windows with at least this many downloads a frame')
    ap.add_argument('--fit-only', action='store_true')
    a = ap.parse_args()

    stall, perf, phase = [], [], []
    with open(a.log, errors='replace') as f:
        for line in f:
            t = ts(line)
            if t is None:
                continue
            m = STALL.search(line)
            if m:
                frames = int(m.group(3)) + int(m.group(4))
                if frames:
                    stall.append((t, (int(m.group(2)) / frames,
                                      int(m.group(1)) / frames)))
                continue
            m = PERF.search(line)
            if m and 'hakuX-perf' in line:
                perf.append((t, (int(m.group(1)), float(m.group(2)))))
                continue
            m = PHASE.search(line)
            if m and 'hakuX-phase' in line:
                phase.append((t, tuple(float(x) for x in m.groups())))

    def clock(s):
        if not s or not stall:
            return None
        d = datetime.fromtimestamp(stall[0][0]).strftime('%Y-%m-%d ')
        return datetime.strptime(d + s, '%Y-%m-%d %H:%M:%S').timestamp()

    t0, t1 = clock(a.t_from), clock(a.t_to)
    rows = []
    for t, (sd, fin_n) in stall:
        if t0 and t < t0 or t1 and t > t1:
            continue
        p = nearest(perf, t)
        h = nearest(phase, t)
        if not p or not h or p[0] < a.min_gfps or sd < a.min_sd:
            continue
        rows.append((t, sd, fin_n, p[0], p[1]) + h)

    if not a.fit_only:
        print('%8s %6s %6s %5s %6s %6s %6s %6s %6s %6s %5s %5s'
              % ('t', 'sd/fr', 'fin/fr', 'gfps', 'G', 'Draw', 'Fin', 'Sub',
                 'Tot', 'GPU', 'R', 'X'))
    for (t, sd, fn, gf, g, dr, fi, su, fe, to, gp, r, x) in (
            [] if a.fit_only else rows):
        print('%8s %6.1f %6.1f %5d %6.1f %6.1f %6.1f %6.1f %6.1f %6.1f %5.1f %5.1f'
              % (datetime.fromtimestamp(t).strftime('%H:%M:%S'), sd, fn, gf,
                 g, dr, fi, su, to, gp, r, x))
    n = len(rows)
    if n < 3:
        print('%d windows: too few to fit' % n)
        return 0

    def fit(xs, ys):
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        syy = sum((y - my) ** 2 for y in ys)
        if not sxx or not syy:
            return float('nan'), float('nan'), float('nan')
        b = sxy / sxx
        return b, my - b * mx, sxy / (sxx * syy) ** 0.5

    xs = [r[1] for r in rows]
    for name, idx in (('G', 4), ('Fin', 6), ('Draw', 5), ('GPU', 10)):
        b, c, rr = fit(xs, [r[idx] for r in rows])
        print('%-4s = %.3f ms x sd/frame + %.1f ms   r=%.2f  (n=%d, sd/frame %.1f-%.1f)'
              % (name, b, c, rr, n, min(xs), max(xs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
