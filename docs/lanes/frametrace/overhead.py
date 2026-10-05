#!/usr/bin/env python3
"""Overhead pair (NOTES section 2): instrument on (B) against off (A).

    overhead.py <B result dir> <A result dir> [--delay 20]
    overhead.py --duty <result dir> [--delay 20]    (HAKUX_FRAMETRACE_DUTY)

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


T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36,
       8: 2.31, 9: 2.26, 10: 2.23, 12: 2.18, 15: 2.13, 20: 2.09, 30: 2.04}


def t95(df):
    k = max(x for x in T95 if x <= max(df, 1))
    return T95[k]


def duty(d, delay):
    """One run, HAKUX_FRAMETRACE_DUTY: the rule in NOTES section 5.

    Each 2-s hakuX-perf gfps line and hakuX-pace interval covers (t-2, t];
    [idlehalt] covers (t - span, t]. A window counts for the phase it lies
    wholly in; one that straddles a switch, or holds a route frame capture
    (route-frames/HHMMSS-*.png, +-1 s), is dropped. Phase k (even on, odd
    off) is scored by its mean fps (pace frames / s), mean gfps and mean
    vCPU run share; each on phase k with both neighbours k-1, k+1 present
    gives one paired difference against their mean.
    """
    import glob
    import os
    t0 = mark(d)
    if t0 is None:
        print('VOID: no mark gameplay')
        return
    t0 += delay
    sw = []                                 # (wall, k, on)
    gf, pace, idle = [], [], []
    for l in open(d + '/logcat.txt', errors='replace'):
        t = secs(l)
        if t is None:
            continue
        m = re.search(r'\[hakuX-ft1\] duty=(on|off) k=(\d+)', l)
        if m:
            sw.append((t, int(m[2]), m[1] == 'on'))
            continue
        m = re.search(r'hakuX-perf.*gfps=(\d+)', l)
        if m:
            gf.append((t - 2.0, t, int(m[1])))
        m = re.search(r'hakuX-pace.*f=(\d+).*ms=([\d.]+)', l)
        if m:
            pace.append((t - float(m[2]) / 1000.0, t, int(m[1])))
        m = re.search(r'\[idlehalt\].*span_us=(\d+) run_us=(\d+)', l)
        if m:
            idle.append((t - int(m[1]) / 1e6, t, int(m[2]) / int(m[1])))
    if not sw:
        print('VOID: no duty switch lines')
        return
    caps = []
    for p in glob.glob(os.path.join(d, 'route-frames', '*.png')):
        b = os.path.basename(p)[:6]
        if b.isdigit():
            caps.append(int(b[:2]) * 3600 + int(b[2:4]) * 60 + int(b[4:6]))
    # phase boundaries: before the first switch the instrument was on, k=0
    bounds = [(-1e9, 0, True)] + sw

    def phase(a, b):
        if a < t0:
            return None
        for i, (ts, k, on) in enumerate(bounds):
            te = bounds[i + 1][0] if i + 1 < len(bounds) else 1e9
            if ts <= a and b <= te:
                if any(a - 1 <= c <= b + 1 for c in caps):
                    return None
                return k
        return None

    ph = {}
    prev_f = None
    for a, b, f in pace:
        if prev_f is not None:
            k = phase(a, b)
            if k is not None:
                ph.setdefault(k, {'fps': [], 'gfps': [], 'run': []})
                ph[k]['fps'].append((f - prev_f) / (b - a))
        prev_f = f
    for a, b, g in gf:
        k = phase(a, b)
        if k is not None:
            ph.setdefault(k, {'fps': [], 'gfps': [], 'run': []})['gfps'].append(g)
    for a, b, r in idle:
        k = phase(a, b)
        if k is not None:
            ph.setdefault(k, {'fps': [], 'gfps': [], 'run': []})['run'].append(r)
    m_ = {k: {q: statistics.mean(v[q]) if v[q] else None for q in v}
          for k, v in ph.items()}
    print('phases scored: %d (on %d, off %d); switches %d; frame captures %d'
          % (len(m_), sum(1 for k in m_ if k % 2 == 0),
             sum(1 for k in m_ if k % 2), len(sw), len(caps)))
    for q, name in (('fps', 'O2 fps (pace)'), ('gfps', 'O2 gfps'),
                    ('run', 'O3 vCPU run share')):
        diffs, base = [], []
        for k in sorted(m_):
            if k % 2 or (k - 1) not in m_ or (k + 1) not in m_:
                continue
            on = m_[k][q]
            nb = [m_[k - 1][q], m_[k + 1][q]]
            if on is None or None in nb:
                continue
            off = statistics.mean(nb)
            diffs.append(on - off)
            base.append(off)
        if len(diffs) < 2:
            print('%s: %d pairs, not enough' % (name, len(diffs)))
            continue
        md = statistics.mean(diffs)
        hw = t95(len(diffs) - 1) * statistics.stdev(diffs) / len(diffs) ** 0.5
        b = statistics.mean(base)
        print('%s: %d pairs, on - off = %+.3f (95%% %+.3f .. %+.3f) on a base '
              'of %.3f: %+.2f%% (%+.2f%% .. %+.2f%%)' % (
                  name, len(diffs), md, md - hw, md + hw, b, 100 * md / b,
                  100 * (md - hw) / b, 100 * (md + hw) / b))
    # O3 per frame: run share / fps, per phase class
    for cls, sel in (('on', 0), ('off', 1)):
        ks = [k for k in m_ if k % 2 == sel and m_[k]['run'] and m_[k]['fps']]
        if ks:
            print('vCPU run us/frame, %s phases: %.0f' % (cls, statistics.mean(
                m_[k]['run'] * 1e6 / m_[k]['fps'] for k in ks)))


def main():
    if '--duty' in sys.argv:
        a = [x for x in sys.argv[1:] if not x.startswith('--')]
        delay = 20.0
        if '--delay' in sys.argv:
            delay = float(sys.argv[sys.argv.index('--delay') + 1])
            a = [x for x in a if x != sys.argv[sys.argv.index('--delay') + 1]]
        duty(a[0], delay)
        return
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
