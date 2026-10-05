#!/usr/bin/env python3
"""Overhead pair (NOTES section 2): instrument on (B) against off (A).

    overhead.py <B result dir> <A result dir> [--delay 20]

Scored window: run.log's `mark gameplay` + --delay s to the end of the log.
O2: median gfps of the 2-s hakuX-perf lines in the window, with A's IQR.
O3: [idlehalt] run_us per guest frame (frames from hakuX-pace f= deltas).
O1 (B only): mean ins (builder us/frame) from [hakuX-ft1] ins=, plus the
writer's wcpu_us / frames.
"""
import re
import statistics
import sys

TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')


def secs(l):
    m = TS.match(l)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None


def mark(d):
    for l in open(d + '/run.log', errors='replace'):
        m = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', l)
        if m:
            return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    return None


def read(d, delay):
    t0 = mark(d)
    if t0 is None:
        return None
    t0 += delay
    gf, pace, idle, ft1 = [], [], [], []
    for l in open(d + '/logcat.txt', errors='replace'):
        t = secs(l)
        if t is None or t < t0:
            continue
        m = re.search(r'hakuX-perf.*gfps=(\d+)', l)
        if m:
            gf.append(int(m[1]))
        m = re.search(r'hakuX-pace.*f=(\d+)', l)
        if m:
            pace.append((t, int(m[1])))
        m = re.search(r'\[idlehalt\].*span_us=(\d+) run_us=(\d+)', l)
        if m:
            idle.append((t, int(m[1]), int(m[2])))
        if '[hakuX-ft1]' in l:
            kv = dict(re.findall(r'(\w+)=([-\d.]+)(?=\s|$)', l))
            ft1.append(kv)
    # run_us per frame: total run_us over the window / frames over it
    frames = pace[-1][1] - pace[0][1] if len(pace) > 1 else 0
    span = pace[-1][0] - pace[0][0] if len(pace) > 1 else 0
    run = sum(r for t, s, r in idle if pace and pace[0][0] <= t <= pace[-1][0])
    sp = sum(s for t, s, r in idle if pace and pace[0][0] <= t <= pace[-1][0])
    out = dict(n=len(gf), gfps=statistics.median(gf) if gf else None,
               q=statistics.quantiles(gf, n=4) if len(gf) > 3 else None,
               mean=statistics.mean(gf) if gf else None,
               fps=frames / span if span else None,
               run_pf=run / frames if frames else None,
               run_share=run / sp if sp else None)
    if ft1:
        n = sum(float(k.get('n', 0)) for k in ft1)
        ins = sum(float(k.get('ins', 0)) * float(k.get('n', 0)) for k in ft1)
        w = sum(float(k.get('wcpu_us', 0)) for k in ft1)
        out.update(ins=ins / n if n else None, wcpu=w / n if n else None,
                   insmax=max(float(k.get('insmax', 0)) for k in ft1))
    return out


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    delay = 20.0
    if '--delay' in sys.argv:
        delay = float(sys.argv[sys.argv.index('--delay') + 1])
        a = [x for x in a if x != sys.argv[sys.argv.index('--delay') + 1]]
    b, aa = read(a[0], delay), read(a[1], delay)
    for name, r in (('B (on)', b), ('A (off)', aa)):
        print(name, {k: (round(v, 3) if isinstance(v, float) else v)
                     for k, v in r.items()})
    print('O2 gfps median B-A: %+.1f (%.1f%% of A); A IQR %s' % (
        b['gfps'] - aa['gfps'], 100.0 * (b['gfps'] - aa['gfps']) / aa['gfps'],
        aa['q']))
    print('O2 fps (pace frames / s) B %.2f A %.2f (%+.1f%%)' % (
        b['fps'], aa['fps'], 100.0 * (b['fps'] - aa['fps']) / aa['fps']))
    print('O3 vCPU run_us/frame B %.0f A %.0f (%+.1f%%); run share B %.3f A %.3f'
          % (b['run_pf'], aa['run_pf'],
             100.0 * (b['run_pf'] - aa['run_pf']) / aa['run_pf'],
             b['run_share'], aa['run_share']))
    if 'ins' in b:
        print('O1 ins %.1f us/frame (max %.0f) + writer %.1f us/frame = %.1f'
              % (b['ins'], b['insmax'], b['wcpu'], b['ins'] + b['wcpu']))


if __name__ == '__main__':
    main()
