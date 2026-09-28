#!/usr/bin/env python3
"""Per-line Tx, Tot, fps and the longest phase-line gap in a soak logcat (lane.forza414b, #474).

    txline.py <logcat.txt> [--from S] [--to S] [--every N]

t = 0 is the first `soak start`. Prints every Nth hakuX-phase line in the
window (Tot, Draw, Pipe, Tx, GPU), then the H0 figures: the longest gap between
consecutive phase lines over the whole run, and how close to the end the last
one is. Also counts crash/abort/assert lines.
"""
import re
import sys

TS = re.compile(r'^\d\d-\d\d (\d\d):(\d\d):(\d\d)\.(\d\d\d) ')


def secs(line):
    m = TS.match(line)
    if not m:
        return None
    h, mi, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000.0


def f(pat, l):
    m = re.search(pat, l)
    return float(m.group(1)) if m else float('nan')


def main(argv):
    lo, hi, every, path = 0.0, 1e9, 1, None
    i = 1
    while i < len(argv):
        if argv[i] in ('--from', '--to', '--every'):
            v = float(argv[i + 1])
            if argv[i] == '--from':
                lo = v
            elif argv[i] == '--to':
                hi = v
            else:
                every = int(v)
            i += 2
        else:
            path = argv[i]
            i += 1
    if not path:
        raise SystemExit(__doc__)
    lines = open(path, errors='replace').read().splitlines()
    t0 = next((secs(l) for l in lines if 'soak start' in l), None)
    if t0 is None:
        raise SystemExit('no soak start line')
    last_t = max(secs(l) or 0 for l in lines) - t0
    phase_t = []
    bad = 0
    n = 0
    for l in lines:
        t = secs(l)
        if t is None:
            continue
        t -= t0
        if re.search(r'FATAL|SIGABRT|SIGSEGV|Assertion|assert.*failed', l):
            bad += 1
        if 'hakuX-phase' not in l or t < 0:
            continue
        phase_t.append(t)
        if lo <= t <= hi:
            if n % every == 0:
                print('t=%6.1f Tot %6.1f Draw %6.1f Pipe %6.1f Tx %6.1f GPU %6.1f' % (
                    t, f(r'Tot:([\d.]+)', l), f(r'Draw:([\d.]+)', l),
                    f(r'Pipe:([\d.]+)', l), f(r'\(Tx:([\d.]+)', l),
                    f(r'GPU:([\d.]+)', l)))
            n += 1
    gaps = [b - a for a, b in zip(phase_t, phase_t[1:])]
    print('H0: longest gap between phase lines %.1f s; last line at %.1f of %.1f s; crash/abort lines %d' % (
        max(gaps) if gaps else float('nan'), phase_t[-1] if phase_t else float('nan'), last_t, bad))


if __name__ == '__main__':
    main(sys.argv)
