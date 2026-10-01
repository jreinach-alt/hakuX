#!/usr/bin/env python3
"""The numbers behind this lane's hand-read Forza soak legs (#414).

    judge.py [--end N] <result dir> [<result dir> ...]

One block per soak: what each registered leg of forzadecay414-bisect.json,
-master.json and -fix-forza.json reads from that run's logcat. It prints
quantities, not verdicts: which arm a run is, and so which legs apply to it,
is the reader's to say.

t = 0 is the `soak start` line, as in docs/lanes/forza414/timeline.py, whose
30-s rows supply fps and G. `race` rows are t = 180..330, which is
180 <= t < 360; `early` is rows t = 150..210 (150 <= t < 240) and `late`
rows t = 270..330. --end N (default 360) moves the window's end: race rows
run to N - 30, `late` is the last three of them, `invalid= last` is read at
or before N, and `all` rows t = 150..N - 30 print with their min / median
(forzadecay414-fix-forza3.json reads a 420-s run with --end 420).

  G, fps      timeline.py's columns, per row
  w311        [watch311] lines after t = 150, and invalid= max / last at or
              before t = 360 / median over the early rows
  faf         txw faf calls/flip over the race rows: median and max
  scan        txw scan ms/flip and calls/flip on the first and last race line
              (first txw line at or after t = 150 with >= 500 scan calls/flip;
              last such line at or before `soak end`, or the log's end)
  range       [sdcall] range= completion ms per frame on the lines nearest
              those two: a download the scan triggers and waits on, inside
              the scan's time. walk = scan - range is what is left for the
              list walk itself.
"""
import os
import re
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TIMELINE = os.path.join(HERE, '..', 'forza414', 'timeline.py')
TS = re.compile(r'^\d\d-\d\d (\d\d):(\d\d):(\d\d)\.(\d\d\d) ')
W311 = re.compile(r'\[watch311\] live=(\d+).*invalid=(\d+)')
TXW = re.compile(r'txw\[f(\d+) ([\d.]+)s .*? scan([\d.]+)/([\d.]+) '
                 r'faf([\d.]+)/([\d.]+)')
SDC = re.compile(r'\[sdcall\] frames=(\d+)(.*)')
RANGE = re.compile(r'range=fin(\d+)/fence\d+/pre\d+/dl(\d+)/([\d.]+)ms')


def secs(line):
    m = TS.match(line)
    if not m:
        return None
    h, mi, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000.0


def rows(logcat):
    out = subprocess.run([sys.executable, TIMELINE, logcat],
                         capture_output=True, text=True).stdout
    table = {}
    for line in out.splitlines()[2:]:
        c = [x.strip() for x in line.strip('|').split('|')]
        if len(c) < 3:
            continue

        def num(x):
            return None if x == '-' else float(x)
        table[int(float(c[0]))] = (num(c[1]), num(c[2]))
    return table


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x, spec='%.2f'):
    return '-' if x is None else spec % x


def judge(d, end=360):
    logcat = os.path.join(d, 'logcat.txt')
    t0 = tend = None
    w311, txw, sdc = [], [], []
    last_t = None
    for line in open(logcat, errors='replace'):
        t = secs(line)
        if t is None:
            continue
        if t0 is None:
            if 'soak start' in line:
                t0 = t
            continue
        t -= t0
        last_t = t
        if 'soak end' in line:
            tend = t
        m = W311.search(line)
        if m:
            w311.append((t, int(m.group(2))))
            continue
        m = TXW.search(line)
        if m:
            txw.append((t, float(m.group(3)), float(m.group(4)),
                        float(m.group(6))))
            continue
        m = SDC.search(line)
        if m:
            r = RANGE.search(m.group(2))
            ms = float(r.group(3)) / int(m.group(1)) if r else 0.0
            sdc.append((t, ms))

    tl = rows(logcat)
    print('== %s' % os.path.basename(d.rstrip('/')))
    print('   log: soak end t=%s, last line t=%s' %
          (fmt(tend, '%.1f'), fmt(last_t, '%.1f')))
    race = list(range(180, end, 30))
    lrows = race[-3:]
    print('   G   rows 180-%d: %s' % (race[-1],
          ' '.join(fmt(tl.get(t, (None, None))[1], '%.1f') for t in race)))
    print('   fps rows 150-%d: %s' % (race[-1],
          ' '.join(fmt(tl.get(t, (None, None))[0], '%.0f')
                   for t in [150] + race)))
    early = mean([tl.get(t, (None, None))[0] for t in (150, 180, 210)])
    have_late = all(tl.get(t, (None, None))[0] is not None for t in lrows)
    late = mean([tl[t][0] for t in lrows]) if have_late else None
    print('   fps early (150-210) %s, late (%d-%d) %s, late/early %s' %
          (fmt(early), lrows[0], lrows[-1], fmt(late),
           fmt(late / early if late is not None and early else None)))
    every = [tl.get(t, (None, None))[0] for t in [150] + race]
    if all(v is not None for v in every):
        med = statistics.median(every)
        print('   fps all rows 150-%d: min %.0f median %.1f min/median %.2f' %
              (race[-1], min(every), med, min(every) / med if med else 0))
    else:
        print('   fps all rows 150-%d: a row is missing' % race[-1])

    after = [v for t, v in w311 if t > 150]
    upto = [v for t, v in w311 if t <= end]
    mid = [v for t, v in w311 if 150 <= t < 240]
    print('   w311: %d lines after t=150; invalid max %s, last (t<=%d) %s, '
          'median t=150-240 %s' %
          (len(after), max(v for _, v in w311) if w311 else '-', end,
           upto[-1] if upto else '-',
           fmt(statistics.median(mid) if mid else None, '%.0f')))

    faf = [f for t, _, _, f in txw if 180 <= t < end]
    print('   faf calls/flip t=180-%d: n=%d median %s max %s' %
          (end, len(faf), fmt(statistics.median(faf) if faf else None),
           fmt(max(faf) if faf else None)))

    stop = tend if tend is not None else last_t
    lines = [x for x in txw if x[0] >= 150 and x[0] <= stop and x[2] >= 500]
    for name, x in (('first', lines[0] if lines else None),
                    ('last', lines[-1] if lines else None)):
        if x is None:
            print('   scan %s race line: none' % name)
            continue
        near = min(sdc, key=lambda s: abs(s[0] - x[0])) if sdc else None
        rng = near[1] if near else None
        print('   scan %s race line t=%.1f: %.2f ms/flip over %.1f calls/flip;'
              ' range completion %s ms/frame (sdcall t=%s); walk %s' %
              (name, x[0], x[1], x[2], fmt(rng),
               fmt(near[0] if near else None, '%.1f'),
               fmt(x[1] - rng if rng is not None else None)))
    scans = [x[1] for x in lines]
    if scans:
        print('   scan ms/flip over the race: min %.2f median %.2f max %.2f '
              '(n=%d)' % (min(scans), statistics.median(scans), max(scans),
                          len(scans)))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args, end = sys.argv[1:], 360
    if args[:1] == ['--end']:
        end, args = int(args[1]), args[2:]
    for d in args:
        judge(d, end)
