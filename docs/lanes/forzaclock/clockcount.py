#!/usr/bin/env python3
"""Race-clock advance against flips and VBLANKs between route screenshots.

usage: clockcount.py <result dir> <race clock at each 'shot play', in order...>

The race clock is read off the HUD of each `*-play.png` by eye (RACE mm:ss.sss,
entered as seconds). Flips and VBLANKs come from the `hakuX-pace` lines
(`f=` is the cumulative flip count, `vb=` the VBLANKs in that window) and are
interpolated linearly to each screenshot's `shot play` time in run.log.

If the game steps a fixed 1/30 s per rendered frame, drace*30 == dflips.
If it steps by elapsed VBLANKs, drace*60 == dvbl. If it reads a real-time
timer, drace == dwall.
"""
import bisect
import re
import sys


def ts(s):
    h, m, x = s.split(':')
    return int(h) * 3600 + int(m) * 60 + float(x)


def main():
    d = sys.argv[1].rstrip('/')
    clocks = [float(x) for x in sys.argv[2:]]
    shots = [l.split()[1] for l in open(d + '/run.log', errors='replace')
             if 'shot play' in l]
    if len(shots) != len(clocks):
        sys.exit('have %d play shots, %d clocks' % (len(shots), len(clocks)))
    T, F, V = [], [], []
    cv = 0
    for l in open(d + '/logcat.txt', errors='replace'):
        if 'hakuX-pace' not in l:
            continue
        m = re.search(r'f=(\d+) .*vb=(\d+) ', l)
        cv += int(m.group(2))
        T.append(ts(l[6:18]))
        F.append(int(m.group(1)))
        V.append(cv)

    def at(t, A):
        i = bisect.bisect_left(T, t)
        if i == 0 or i >= len(T):
            return None, None
        a = (t - T[i - 1]) / (T[i] - T[i - 1])
        return A[i - 1] + a * (A[i] - A[i - 1]), T[i] - T[i - 1]

    print('interval                   dwall  drace race/wall  dflips drace*30 '
          'r30/fl   dvbl drace*60  pace-window s')
    tot = [0.0] * 4
    for (t0, c0), (t1, c1) in zip(zip(shots, clocks), zip(shots[1:], clocks[1:])):
        f0, s0 = at(ts(t0), F)
        f1, s1 = at(ts(t1), F)
        v0, _ = at(ts(t0), V)
        v1, _ = at(ts(t1), V)
        if f0 is None or f1 is None:
            print('%s-%s  (no pace line on both sides; skipped)' % (t0, t1))
            continue
        dw = ts(t1) - ts(t0)
        dr = c1 - c0
        df = f1 - f0
        dv = v1 - v0
        tot = [tot[0] + dw, tot[1] + dr, tot[2] + df, tot[3] + dv]
        print('%s-%s %6.2f %6.3f %7.1f%% %7.1f %8.1f %6.3f %6.0f %8.1f  %.1f/%.1f'
              % (t0, t1, dw, dr, 100 * dr / dw, df, dr * 30, dr * 30 / df,
                 dv, dr * 60, s0, s1))
    dw, dr, df, dv = tot
    print('TOTAL %37.2f %6.3f %7.1f%% %7.1f %8.1f %6.3f %6.0f %8.1f'
          % (dw, dr, 100 * dr / dw, df, dr * 30, dr * 30 / df, dv, dr * 60))
    # Quantization: every reading is k/30 s to display rounding (1 ms).
    for c in clocks:
        k = round(c * 30)
        print('  %8.3f = %5d/30 %+.4f' % (c, k, c - k / 30.0))


if __name__ == '__main__':
    main()
