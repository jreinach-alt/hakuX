#!/usr/bin/env python3
"""Judge the HAKUX_S2T_CVT soak A/B on Mortal Kombat: Shaolin Monks (#986)
against docs/testing/predictions/fps1015-mksm.json.

    s2tread.py [--windows] RESULT_DIR [RESULT_DIR ...]

Each RESULT_DIR is one perflog soak of route fps1015-mksm. Its arm is read
from request.json: `on` when its env carries HAKUX_S2T_CVT=1, else `off`.

Windows. A perflog build prints one block per 60 guest frames: hakuX-stall
`Finish:N(... sdS ... presP flipF ...)` and `txr[... dlD/..K ... s2tcC ...]
txdl[... cvtV ...]`, then hakuX-perf `gfps= G:`, hakuX-pace `ms=` (the
window's length) and hakuX-phase `Draw: Fin: GPU:`. One window per `gfps`
line; the other lines are paired to it by timestamp.

Spans. The route's inputs are blind and timed, so its shots fall at the same
offsets from route start in every run. run.log gives each `ROUTE ... shot`
and `mark gameplay` on the host clock; the offset from `ROUTE ... start` is
added to the logcat's first `surface_scale=` line plus LEAD (1.42 s: the
gap between the two on 10-09, before the host clock began stepping), so
spans are on the logcat clock. Cutscene span: shot s13 to shot s24 (the
Goro's Lair opening, 3 surface downloads a frame in the baseline). Gameplay
span: `mark gameplay` to the last window. A window counts in a span only if
it lies wholly inside it.

Legs (the prediction file states them; this script computes them):
  V  each run: >= 15 cutscene windows, two thirds of them carrying the arm's
     signature (off: cvt >= 60 a window; on: cvt 0 and s2tc >= 60), and >= 8
     gameplay windows; on runs log `[s2tcvt] on` and `[s2tcvt] first`, off
     runs neither. A run failing V is VOID, not a refutation.
  R  cutscene, pooled windows: on median sd a frame <= 0.1 and median cvt 0;
     off median sd a frame >= 2.5.
  P  cutscene median G, on - off, in [-22, -6] ms.
  F  cutscene median gfps, on - off, >= +5.
  N  gameplay median gfps, on >= off - 3.
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys
from datetime import datetime

LEAD = 1.42
TS = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d)\s')
FINISH = re.compile(r'hakuX-stall\(\d+\): RPBreaks:\d+ Finish:(\d+)\(.*?sd(\d+) .*?'
                    r'pres(\d+) flip(\d+) ')
TXR = re.compile(r'txr\[ct\d+ bt\d+/\d+ dl(\d+)/\d+K .*?s2tc(\d+) .*?\] '
                 r'txdl\[.*?cvt(\d+) ')
PERF = re.compile(r'hakuX-perf\(\d+\): gfps=(\d+) G:([\d.]+)')
PACE = re.compile(r'hakuX-pace\(\d+\): .*? ms=([\d.]+)')
PHASE = re.compile(r'hakuX-phase\(\d+\): .*Draw:([\d.]+) .*Fin:([\d.]+)\(Sub:([\d.]+) '
                   r'Fen:([\d.]+)\).*Tot:([\d.]+) GPU:([\d.]+)')
ROUTE = re.compile(r'^ROUTE (\d\d):(\d\d):(\d\d\.\d+) (start|shot (\S+)|mark gameplay)')


def dev_time(line):
    m = TS.match(line)
    if not m:
        return None
    return datetime.strptime('2026-' + m.group(1), '%Y-%m-%d %H:%M:%S.%f').timestamp()


def nearest(seq, t, tol):
    best = min(seq, key=lambda x: abs(x[0] - t)) if seq else None
    return best[1] if best and abs(best[0] - t) <= tol else None


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
            t = dev_time(line)
            if t is None:
                continue
            if anchor is None and 'surface_scale=' in line:
                anchor = t
            if '[s2tcvt] on' in line:
                on_lines += 1
            elif '[s2tcvt] first' in line:
                first_lines.append(line.split('[s2tcvt] ', 1)[1].strip())
            m = FINISH.search(line)
            if m:
                frames = int(m.group(3)) + int(m.group(4))
                fin.append((t, int(m.group(2)) / frames if frames else None))
                continue
            m = TXR.search(line)
            if m:
                txr.append((t, tuple(int(x) for x in m.groups())))
                continue
            m = PERF.search(line)
            if m:
                perf.append((t, (int(m.group(1)), float(m.group(2)))))
                continue
            m = PACE.search(line)
            if m:
                pace.append((t, float(m.group(1))))
                continue
            m = PHASE.search(line)
            if m:
                phase.append((t, tuple(float(x) for x in m.groups())))

    shots, start, mark = {}, None, None
    prev = None
    with open(runs[0], errors='replace') as f:
        for line in f:
            m = ROUTE.match(line)
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
    if anchor is None or start is None or 's13' not in shots or 's24' not in shots or mark is None:
        out['error'] = ('no anchor' if anchor is None else 'route did not reach s13/s24/mark gameplay')
        return out

    def to_dev(h):
        return anchor + LEAD + (h - start)

    c_lo, c_hi, g_lo = to_dev(shots['s13']), to_dev(shots['s24']), to_dev(mark)
    windows = []
    for t, (gfps, g) in perf:
        ms = nearest(pace, t, 0.3)
        sd = nearest(fin, t, 0.6)
        tx = nearest(txr, t, 0.6)
        ph = nearest(phase, t, 0.3)
        if ms is None or tx is None:
            continue
        w = {'t': t, 't0': t - ms / 1000.0, 'gfps': gfps, 'G': g, 'sd': sd,
             'dl': tx[0], 's2tc': tx[1], 'cvt': tx[2],
             'Draw': ph[0] if ph else None, 'Fin': ph[1] if ph else None,
             'GPU': ph[5] if ph else None}
        w['span'] = ('cut' if w['t0'] >= c_lo and t <= c_hi else
                     'play' if w['t0'] >= g_lo else '')
        windows.append(w)
    out.update(windows=windows, cut=(c_lo, c_hi), play=g_lo)
    return out


def med(ws, key):
    xs = [w[key] for w in ws if w[key] is not None]
    return statistics.median(xs) if xs else None


def signature(arm, w):
    return w['cvt'] >= 60 if arm == 'off' else (w['cvt'] == 0 and w['s2tc'] >= 60)


def fmt(x, nd=1):
    return '-' if x is None else ('%.*f' % (nd, x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--windows', action='store_true', help='print every window')
    a = ap.parse_args()

    runs = [read_run(d) for d in a.dirs]
    void = []
    print('%-48s %-3s %4s %4s %4s %6s %5s %5s %6s %6s %5s %5s %5s  %s'
          % ('run', 'arm', 'cut', 'sig', 'play', 'sd/fr', 'cvt', 's2tc', 'G', 'gfps', 'Fin', 'GPU',
             'pgfps', 'markers'))
    for r in runs:
        name = os.path.basename(r['dir'].rstrip('/'))
        if 'error' in r:
            print('%-48s %-3s VOID: %s' % (name, r['arm'], r['error']))
            void.append(name)
            continue
        cut = [w for w in r['windows'] if w['span'] == 'cut']
        play = [w for w in r['windows'] if w['span'] == 'play']
        sig = sum(1 for w in cut if signature(r['arm'], w))
        markers = 'on%d first%d' % (r['on_lines'], len(r['first']))
        r.update(cutw=cut, playw=play)
        print('%-48s %-3s %4d %4d %4d %6s %5s %5s %6s %6s %5s %5s %5s  %s'
              % (name, r['arm'], len(cut), sig, len(play), fmt(med(cut, 'sd'), 2),
                 fmt(med(cut, 'cvt'), 0), fmt(med(cut, 's2tc'), 0), fmt(med(cut, 'G')),
                 fmt(med(cut, 'gfps')), fmt(med(cut, 'Fin')), fmt(med(cut, 'GPU')),
                 fmt(med(play, 'gfps')), markers))
        reasons = []
        if len(cut) < 15:
            reasons.append('%d cutscene windows < 15' % len(cut))
        elif sig * 3 < len(cut) * 2:
            reasons.append('%d of %d cutscene windows carry the %s signature' % (sig, len(cut), r['arm']))
        if len(play) < 8:
            reasons.append('%d gameplay windows < 8' % len(play))
        if r['arm'] == 'on' and (r['on_lines'] == 0 or not r['first']):
            reasons.append('on run without [s2tcvt] on/first')
        if r['arm'] == 'off' and (r['on_lines'] or r['first']):
            reasons.append('off run logs [s2tcvt]')
        if reasons:
            print('    VOID (V): ' + '; '.join(reasons))
            void.append(name)
        if a.windows:
            for w in r['windows']:
                print('    %s-%s %-4s gfps %2d G %5.1f sd/fr %s dl %3d s2tc %3d cvt %3d Draw %s Fin %s GPU %s'
                      % (datetime.fromtimestamp(w['t0']).strftime('%H:%M:%S'),
                         datetime.fromtimestamp(w['t']).strftime('%H:%M:%S'), w['span'], w['gfps'],
                         w['G'], fmt(w['sd'], 2), w['dl'], w['s2tc'], w['cvt'], fmt(w['Draw']),
                         fmt(w['Fin']), fmt(w['GPU'])))

    ok = [r for r in runs if os.path.basename(r['dir'].rstrip('/')) not in void]
    arms = {k: [r for r in ok if r['arm'] == k] for k in ('on', 'off')}
    if not arms['on'] or not arms['off']:
        print('VERDICT: VOID -- need at least one valid run per arm (on %d, off %d)'
              % (len(arms['on']), len(arms['off'])))
        return 2
    pool = {k: ([w for r in v for w in r['cutw']], [w for r in v for w in r['playw']])
            for k, v in arms.items()}
    on_c, on_p = pool['on']
    off_c, off_p = pool['off']
    legs = []
    r_ok = (med(on_c, 'sd') is not None and med(on_c, 'sd') <= 0.1 and med(on_c, 'cvt') == 0
            and med(off_c, 'sd') is not None and med(off_c, 'sd') >= 2.5)
    legs.append(('R', r_ok, 'cutscene sd/frame on %s off %s; cvt on %s'
                 % (fmt(med(on_c, 'sd'), 2), fmt(med(off_c, 'sd'), 2), fmt(med(on_c, 'cvt'), 0))))
    dg = med(on_c, 'G') - med(off_c, 'G')
    legs.append(('P', -22 <= dg <= -6, 'cutscene median G on %.1f off %.1f: %+.1f ms (predicted -10, [-22, -6])'
                 % (med(on_c, 'G'), med(off_c, 'G'), dg)))
    df = med(on_c, 'gfps') - med(off_c, 'gfps')
    legs.append(('F', df >= 5, 'cutscene median gfps on %.1f off %.1f: %+.1f (predicted +8, >= +5)'
                 % (med(on_c, 'gfps'), med(off_c, 'gfps'), df)))
    dn = med(on_p, 'gfps') - med(off_p, 'gfps')
    legs.append(('N', dn >= -3, 'gameplay median gfps on %.1f off %.1f: %+.1f (>= -3)'
                 % (med(on_p, 'gfps'), med(off_p, 'gfps'), dn)))
    print('reported, not judged: cutscene median Fin on %s off %s ms; GPU on %s off %s ms; Draw on %s off %s ms'
          % (fmt(med(on_c, 'Fin')), fmt(med(off_c, 'Fin')), fmt(med(on_c, 'GPU')), fmt(med(off_c, 'GPU')),
             fmt(med(on_c, 'Draw')), fmt(med(off_c, 'Draw'))))
    for name, passed, text in legs:
        print('%s %s  %s' % (name, 'PASS' if passed else 'FAIL', text))
    if all(p for _, p, _ in legs):
        print('VERDICT: PASS')
        return 0
    failed = [n for n, p, _ in legs if not p]
    if 'R' not in failed and ('P' in failed or 'F' in failed):
        print('VERDICT: REFUTED -- the downloads are gone but the frame did not follow: '
              'another wait or the GPU takes their place')
    elif 'R' in failed:
        print('VERDICT: REFUTED -- the switch did not remove the cutscene downloads')
    else:
        print('VERDICT: REFUTED (%s)' % ', '.join(failed))
    return 1


if __name__ == '__main__':
    sys.exit(main())
