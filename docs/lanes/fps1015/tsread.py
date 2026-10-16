#!/usr/bin/env python3
"""Judge the HAKUX_S2T_CVT soak A/B on Top Spin (#992) against
docs/testing/predictions/fps1015-topspin.json.

    tsread.py [--windows] RESULT_DIR [RESULT_DIR ...]

Each RESULT_DIR is one perflog soak of route fps1015-topspin. Its arm is read
from request.json: `on` when its env carries HAKUX_S2T_CVT=1, else `off`.
The log lines, their pairing into 60-frame windows and the host-to-logcat
clock are s2tread.py's (#986); only the spans and the legs differ.

Spans. Intro: shot s20 to shot s23, the stadium fly-over behind the
"PRESS START" banner (58 surface downloads a frame and 18-23 fps in
lane.async794's control, 1791135713). It waits for the route's START at s23,
so it lasts the same wall time at any speed. Play: `mark gameplay` to the
last window, a live exhibition match (24-37 downloads a frame, 37 fps). A
window counts in a span only if it lies wholly inside it.

Legs (the prediction file states them; this script computes them):
  V  each run: >= 10 intro windows and >= 30 play windows; two thirds of the
     play windows carry the arm's signature (off: cvt >= 600 a window; on:
     cvt 0 and s2tc >= 600); on runs log `[s2tcvt] on`, off runs neither
     `on` nor `first`. A run failing V is VOID, not a refutation. An on run's
     `first` is reported, not required: MKSM's on2 (1792168743) lost it from
     its logcat while its counters carried the decode in every window.
  R  play, pooled windows: on median sd a frame <= 1 and median cvt 0; off
     median sd a frame >= 15.
  P  play median G, on - off, in [-13, -4] ms.
  F  play median gfps, on - off, >= +6.
  I  intro median G, on - off, <= -10 ms.

Reported, not judged: Fin, GPU, Draw, and the GPU's time outside render
passes (X, where the decode's copies and compute run) per span and arm.
"""
import argparse
import glob
import json
import os
import statistics
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s2tread as S  # noqa: E402

SIG = 600


def read_run(d):
    req = json.load(open(os.path.join(d, 'request.json')))
    env = req.get('env') or []
    arm = 'on' if 'HAKUX_S2T_CVT=1' in env else 'off'
    logs = sorted(glob.glob(os.path.join(d, 'logcat*.txt')))
    runs = sorted(glob.glob(os.path.join(d, 'run*.log')))
    if not logs or not runs:
        return {'dir': d, 'arm': arm, 'error': 'no logcat or run.log'}

    anchor, on_lines, first_lines = None, 0, []
    fin, txr, perf, pace, phase = [], [], [], [], []
    with open(logs[0], errors='replace') as f:
        for line in f:
            t = S.dev_time(line)
            if t is None:
                continue
            if anchor is None and 'surface_scale=' in line:
                anchor = t
            if '[s2tcvt] on' in line:
                on_lines += 1
            elif '[s2tcvt] first' in line:
                first_lines.append(line.split('[s2tcvt] ', 1)[1].strip())
            m = S.FINISH.search(line)
            if m:
                frames = int(m.group(3)) + int(m.group(4))
                fin.append((t, int(m.group(2)) / frames if frames else None))
                continue
            m = S.TXR.search(line)
            if m:
                txr.append((t, tuple(int(x) for x in m.groups())))
                continue
            m = S.PERF.search(line)
            if m:
                perf.append((t, (int(m.group(1)), float(m.group(2)))))
                continue
            m = S.PACE.search(line)
            if m:
                pace.append((t, float(m.group(1))))
                continue
            m = S.PHASE.search(line)
            if m:
                phase.append((t, tuple(None if x is None else float(x) for x in m.groups())))

    shots, start, mark, prev = {}, None, None, None
    with open(runs[0], errors='replace') as f:
        for line in f:
            m = S.ROUTE.match(line)
            if not m:
                continue
            h = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            if prev is not None and h < prev - 43200:
                h += 86400
            prev = h
            if m.group(4) == 'start':
                start = h
            elif m.group(4) == 'mark gameplay':
                mark = h
            elif m.group(5):
                shots.setdefault(m.group(5).split('-')[0], h)
    out = {'dir': d, 'arm': arm, 'env': env, 'on_lines': on_lines, 'first': first_lines}
    if anchor is None or start is None or 's20' not in shots or 's23' not in shots or mark is None:
        out['error'] = ('no anchor' if anchor is None else 'route did not reach s20/s23/mark gameplay')
        return out

    def to_dev(h):
        return anchor + S.LEAD + (h - start)

    i_lo, i_hi, g_lo = to_dev(shots['s20']), to_dev(shots['s23']), to_dev(mark)
    windows = []
    for t, (gfps, g) in perf:
        ms = S.nearest(pace, t, 0.3)
        sd = S.nearest(fin, t, 0.6)
        tx = S.nearest(txr, t, 0.6)
        ph = S.nearest(phase, t, 0.3)
        if ms is None or tx is None:
            continue
        w = {'t': t, 't0': t - ms / 1000.0, 'gfps': gfps, 'G': g, 'sd': sd,
             'dl': tx[0], 's2tc': tx[1], 'cvt': tx[2],
             'Draw': ph[0] if ph else None, 'Fin': ph[1] if ph else None,
             'GPU': ph[5] if ph else None, 'X': ph[6] if ph else None}
        w['span'] = ('intro' if w['t0'] >= i_lo and t <= i_hi else
                     'play' if w['t0'] >= g_lo else '')
        windows.append(w)
    out.update(windows=windows)
    return out


def signature(arm, w):
    return w['cvt'] >= SIG if arm == 'off' else (w['cvt'] == 0 and w['s2tc'] >= SIG)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--windows', action='store_true', help='print every window')
    a = ap.parse_args()
    med, fmt = S.med, S.fmt

    runs = [read_run(d) for d in a.dirs]
    void = []
    print('%-44s %-3s %5s %4s %4s %6s %5s %6s %6s %5s %5s %5s %6s %6s  %s'
          % ('run', 'arm', 'intro', 'play', 'sig', 'sd/fr', 'cvt', 'G', 'gfps', 'Fin', 'GPU', 'X',
             'iG', 'igfps', 'markers'))
    for r in runs:
        name = os.path.basename(r['dir'].rstrip('/'))
        if 'error' in r:
            print('%-44s %-3s VOID: %s' % (name, r['arm'], r['error']))
            void.append(name)
            continue
        intro = [w for w in r['windows'] if w['span'] == 'intro']
        play = [w for w in r['windows'] if w['span'] == 'play']
        sig = sum(1 for w in play if signature(r['arm'], w))
        markers = 'on%d first%d' % (r['on_lines'], len(r['first']))
        r.update(introw=intro, playw=play)
        print('%-44s %-3s %5d %4d %4d %6s %5s %6s %6s %5s %5s %5s %6s %6s  %s'
              % (name, r['arm'], len(intro), len(play), sig, fmt(med(play, 'sd'), 2),
                 fmt(med(play, 'cvt'), 0), fmt(med(play, 'G')), fmt(med(play, 'gfps')),
                 fmt(med(play, 'Fin')), fmt(med(play, 'GPU')), fmt(med(play, 'X')),
                 fmt(med(intro, 'G')), fmt(med(intro, 'gfps')), markers))
        reasons = []
        if len(intro) < 10:
            reasons.append('%d intro windows < 10' % len(intro))
        if len(play) < 30:
            reasons.append('%d play windows < 30' % len(play))
        elif sig * 3 < len(play) * 2:
            reasons.append('%d of %d play windows carry the %s signature' % (sig, len(play), r['arm']))
        if r['arm'] == 'on' and r['on_lines'] == 0:
            reasons.append('on run without [s2tcvt] on')
        if r['arm'] == 'off' and (r['on_lines'] or r['first']):
            reasons.append('off run logs [s2tcvt]')
        if reasons:
            print('    VOID (V): ' + '; '.join(reasons))
            void.append(name)
        if a.windows:
            for w in r['windows']:
                print('    %s-%s %-5s gfps %2d G %5.1f sd/fr %s dl %4d s2tc %4d cvt %4d Draw %s Fin %s GPU %s X %s'
                      % (datetime.fromtimestamp(w['t0']).strftime('%H:%M:%S'),
                         datetime.fromtimestamp(w['t']).strftime('%H:%M:%S'), w['span'], w['gfps'],
                         w['G'], fmt(w['sd'], 2), w['dl'], w['s2tc'], w['cvt'], fmt(w['Draw']),
                         fmt(w['Fin']), fmt(w['GPU']), fmt(w['X'])))

    ok = [r for r in runs if os.path.basename(r['dir'].rstrip('/')) not in void]
    arms = {k: [r for r in ok if r['arm'] == k] for k in ('on', 'off')}
    if not arms['on'] or not arms['off']:
        print('VERDICT: VOID -- need at least one valid run per arm (on %d, off %d)'
              % (len(arms['on']), len(arms['off'])))
        return 2
    pool = {k: ([w for r in v for w in r['introw']], [w for r in v for w in r['playw']])
            for k, v in arms.items()}
    on_i, on_p = pool['on']
    off_i, off_p = pool['off']
    legs = []
    r_ok = (med(on_p, 'sd') is not None and med(on_p, 'sd') <= 1 and med(on_p, 'cvt') == 0
            and med(off_p, 'sd') is not None and med(off_p, 'sd') >= 15)
    legs.append(('R', r_ok, 'play sd/frame on %s off %s; cvt on %s'
                 % (fmt(med(on_p, 'sd'), 2), fmt(med(off_p, 'sd'), 2), fmt(med(on_p, 'cvt'), 0))))
    dg = med(on_p, 'G') - med(off_p, 'G')
    legs.append(('P', -13 <= dg <= -4, 'play median G on %.1f off %.1f: %+.1f ms (predicted -8, [-13, -4])'
                 % (med(on_p, 'G'), med(off_p, 'G'), dg)))
    df = med(on_p, 'gfps') - med(off_p, 'gfps')
    legs.append(('F', df >= 6, 'play median gfps on %.1f off %.1f: %+.1f (predicted +12, >= +6)'
                 % (med(on_p, 'gfps'), med(off_p, 'gfps'), df)))
    di = med(on_i, 'G') - med(off_i, 'G')
    legs.append(('I', di <= -10, 'intro median G on %.1f off %.1f: %+.1f ms (predicted -20, <= -10)'
                 % (med(on_i, 'G'), med(off_i, 'G'), di)))
    for span, on_w, off_w in (('play', on_p, off_p), ('intro', on_i, off_i)):
        print('reported, not judged: %s median ms on/off: Fin %s/%s GPU %s/%s X %s/%s Draw %s/%s'
              % (span, fmt(med(on_w, 'Fin')), fmt(med(off_w, 'Fin')), fmt(med(on_w, 'GPU')),
                 fmt(med(off_w, 'GPU')), fmt(med(on_w, 'X')), fmt(med(off_w, 'X')),
                 fmt(med(on_w, 'Draw')), fmt(med(off_w, 'Draw'))))
    for name, passed, text in legs:
        print('%s %s  %s' % (name, 'PASS' if passed else 'FAIL', text))
    if all(p for _, p, _ in legs):
        print('VERDICT: PASS')
        return 0
    failed = [n for n, p, _ in legs if not p]
    if 'R' in failed:
        print('VERDICT: REFUTED -- the switch did not remove the match-play downloads')
    elif failed == ['P'] and dg < -13:
        print('VERDICT: REFUTED as registered -- the frame gained more than the predicted bound (%+.1f ms < -13)'
              % dg)
    elif 'P' in failed or 'F' in failed or 'I' in failed:
        print('VERDICT: REFUTED (%s) -- the downloads are gone but the frame did not follow as predicted: '
              'read GPU and X for the decode\'s own cost' % ', '.join(failed))
    return 1


if __name__ == '__main__':
    sys.exit(main())
