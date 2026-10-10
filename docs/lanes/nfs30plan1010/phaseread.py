#!/usr/bin/env python3
"""PFIFO-thread phase account per route window (#433, lane.nfs30plan1010).

    phaseread.py <result dir> [...] [--window LO,HI] [--label countdown] [--raw]

Reads logcat.txt of a perflog run. Every 60 guest flips the build prints, at one
timestamp (profile.c:794-812):

  hakuX-perf  gfps= G:MS(min-max) ... Tq=        G = flip-to-flip ms, EMA alpha 0.2 PER FLIP
  hakuX-pace  f=F v0..v4 vb= max= ms=MS         MS = wall ms over the 60 flips (exact)
  hakuX-phase Surf Tex [TxH] Shd Draw [...] Fin(Sub Fen) Flip Idle(Fr St) | Tot GPU(R X ...)
                                                 each field EMA alpha 0.2 PER FLIP
                                                 (snapshot_phase_timing, profile.c:66-74, called
                                                 from the flip hook at :418)
  hakuX-cpu   CPU: ... Push:ms [Pull:ms(Lk Mth Fst)] ... Lw:ms
  xemu-gpu    GPU: Tot Rnd Xfr RP
and once a second:
  xemu-work   BE:N ...                            N = draws (begin/end pairs) in the last frame
and once per 60 frames, on hakuX-stall:
  txw[f60 ...s bt<ms>/<n> res ct<ms>/<n> sdl<ms>/<n> scan<ms>/<n> ...]   ms per frame, count per frame
  RPBreaks:.. Finish:N(vtx sc sd buf fb pres flip flu stl stlDef stlBat) ...
and on hakuX:
  [sdcall] frames=60 range=fin/fence/pre/dl/<ms> ...

Because the phase fields and G are per-flip EMAs, a printed line is a sample of
the ~8 frames before the print, not a mean over the 60-flip window; the pace
`ms=` IS the 60-flip mean. So this reader selects lines by PRINT TIME inside
[mark+LO, mark+HI] for each `hakuX-route: mark gameplay|goN` and treats each
phase line as one sample of the frames at that moment, with G as the matched
period. Default window -2,1.5: the countdown proper (the restart's OK is at
mark-2.1, GO at mark+1.5). Output per run and pooled: samples, G, draws/frame
(BE lines in the window), every phase, the texture-path costs, finish counts,
and `outside` = G - Tot, the PFIFO-thread time no phase timer covers.
"""
import argparse
import os
import re
import sys

TS = re.compile(r'^(\d+)-(\d+) (\d+):(\d+):([\d.]+) ')
PERF = re.compile(r'hakuX-perf\(\s*\d+\): gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\)')
PACE = re.compile(r'hakuX-pace\(\s*\d+\): f=(\d+) .*v4=(\d+) .* ms=([\d.]+)')
PHASE = re.compile(r'hakuX-phase\(\s*\d+\): (.*) ms$')
CPU = re.compile(r'hakuX-cpu\(\s*\d+\): .*Push:([\d.]+)ms \[Pull:([\d.]+)\(Lk:([\d.]+) Mth:([\d.]+) Fst:([\d.]+)\)\].*Lw:([\d.]+)')
WORK = re.compile(r'xemu-work\(\s*\d+\): BE:(\d+) ')
TXW = re.compile(r'txw\[f(\d+) [\d.]+s bt([\d.]+)/(\d+) res([\d.]+) ct([\d.]+)/([\d.]+) sdl([\d.]+)/([\d.]+) scan([\d.]+)/([\d.]+)')
STALL = re.compile(r'Finish:(\d+)\(vtx(\d+) sc(\d+) sd(\d+) buf(\d+) fb(\d+) pres(\d+) flip(\d+) flu(\d+) stl(\d+) stlDef(\d+)')
SDCALL = re.compile(r'\[sdcall\] frames=(\d+) range=fin(\d+)/fence(\d+)/pre(\d+)/dl(\d+)/([\d.]+)ms')
MARK = re.compile(r'hakuX-route.*mark (gameplay|go\d+)')
FIELD = re.compile(r'([A-Za-z]+):(-?[\d.]+)')

SHOW = ['Surf', 'Tex', 'Shd', 'Draw', 'Syn', 'Pipe', 'Sh', 'Desc', 'Setup', 'Mfp', 'Fin', 'Sub', 'Fen', 'Flip',
        'Idle', 'Fr', 'St', 'Tot', 'GPU', 'R', 'X']


def secs(m):
    return int(m.group(3)) * 3600 + int(m.group(4)) * 60 + float(m.group(5))


def parse_phase(s):
    vals = {}
    for fm in FIELD.finditer(s):
        k = fm.group(1)
        if k not in vals:          # Pipe(Tx ..) comes after Tex/TxH; keep the first of each name
            vals[k] = float(fm.group(2))
    return vals


def read(path):
    ev = {'perf': [], 'phase': [], 'cpu': [], 'work': [], 'txw': [], 'stall': [], 'sdcall': [], 'pace': []}
    marks = []
    with open(path, errors='replace') as f:
        for ln in f:
            m = TS.match(ln)
            if not m:
                continue
            t = secs(m)
            if 'hakuX-route' in ln:
                k = MARK.search(ln)
                if k:
                    marks.append((t, k.group(1)))
                continue
            q = PERF.search(ln)
            if q:
                ev['perf'].append((t, int(q.group(1)), float(q.group(2)), float(q.group(3)), float(q.group(4))))
                continue
            q = PACE.search(ln)
            if q:
                ev['pace'].append((t, int(q.group(1)), int(q.group(2)), float(q.group(3))))
                continue
            q = PHASE.search(ln)
            if q:
                ev['phase'].append((t, parse_phase(q.group(1))))
                continue
            q = CPU.search(ln)
            if q:
                ev['cpu'].append((t, float(q.group(1)), float(q.group(2)), float(q.group(4)), float(q.group(6))))
                continue
            q = WORK.search(ln)
            if q:
                ev['work'].append((t, int(q.group(1))))
                continue
            q = TXW.search(ln)
            if q:
                ev['txw'].append((t, float(q.group(2)), float(q.group(5)), float(q.group(7)), float(q.group(8)),
                                  float(q.group(9)), float(q.group(10))))
                continue
            q = STALL.search(ln)
            if q:
                ev['stall'].append((t, int(q.group(4)), int(q.group(8)), int(q.group(10)), int(q.group(1))))
                continue
            q = SDCALL.search(ln)
            if q:
                ev['sdcall'].append((t, int(q.group(1)), int(q.group(2)), int(q.group(5)), float(q.group(6))))
    return ev, marks


def inwin(seq, lo, hi):
    return [e for e in seq if lo <= e[0] <= hi]


def mean(xs):
    return sum(xs) / len(xs) if xs else float('nan')


def collect(ev, marks, lo, hi):
    """One sample dict per phase line inside a window; plus window-level BE/txw/stall/sdcall.

    On a plain (non-perflog) build there is no phase line, so the window's `hakuX-perf G:` lines are
    kept as samples of their own ('plain': True) and the report prints G and pace only."""
    samples, be, txw, stall, sdc, pace = [], [], [], [], [], []
    for mt, name in marks:
        w0, w1 = mt + lo, mt + hi
        if not ev['phase']:
            for p in inwin(ev['perf'], w0, w1):
                samples.append({'mark': name, 't': p[0], 'plain': True, 'G': p[2], 'gfps': p[1]})
        for t, ph in inwin(ev['phase'], w0, w1):
            perf = [p for p in ev['perf'] if abs(p[0] - t) < 0.05]
            cpu = [c for c in ev['cpu'] if abs(c[0] - t) < 0.05]
            s = {'mark': name, 't': t, 'ph': ph,
                 'G': perf[0][2] if perf else float('nan'),
                 'gfps': perf[0][1] if perf else float('nan'),
                 'push': cpu[0][1] / 60 if cpu else float('nan'),
                 'pull': cpu[0][2] / 60 if cpu else float('nan'),
                 'lw': cpu[0][4] / 60 if cpu else float('nan')}
            samples.append(s)
        be += [e[1] for e in inwin(ev['work'], w0, w1)]
        txw += inwin(ev['txw'], w0, w1)
        stall += inwin(ev['stall'], w0, w1)
        sdc += inwin(ev['sdcall'], w0, w1)
        pace += inwin(ev['pace'], w0, w1)
    return samples, be, txw, stall, sdc, pace


def report(name, samples, be, txw, stall, sdc, pace):
    if not samples and not pace:
        print(f"{name}: no phase, perf or pace lines in the window")
        return
    if not samples or samples[0].get('plain'):
        # plain build: G (per-flip EMA at print time) and the exact 60-flip pace spans only
        G = mean([s['G'] for s in samples])
        print(f"{name}: PLAIN build, {len(samples)} perf samples, G {G:.1f} ms ({1000 / G:.1f} fps; gfps line "
              f"{mean([s['gfps'] for s in samples]):.1f}), pace windows {len(pace)}: "
              f"{mean([p[3] / 60 for p in pace]):.1f} ms/frame, v4 {mean([p[2] for p in pace]):.0f}/60"
              + (f", draws/frame {mean(be):.0f} (BE n={len(be)})" if be else ''))
        return
    n = len(samples)
    G = mean([s['G'] for s in samples])
    ph = {k: mean([s['ph'].get(k, 0.0) for s in samples]) for k in SHOW}
    print(f"{name}: {n} phase samples, G {G:.1f} ms ({1000 / G:.1f} fps; gfps line {mean([s['gfps'] for s in samples]):.1f}), "
          f"draws/frame {mean(be):.0f} (BE n={len(be)}), pace windows {len(pace)}: "
          f"{mean([p[3] / 60 for p in pace]):.1f} ms/frame, v4 {mean([p[2] for p in pace]):.0f}/60")
    print('  ' + ' '.join(f"{k}={ph[k]:.1f}" for k in SHOW))
    print(f"  Push {mean([s['push'] for s in samples]):.2f} Pull {mean([s['pull'] for s in samples]):.2f} "
          f"Lw {mean([s['lw'] for s in samples]):.2f} ms/frame (60-flip figures / 60)")
    print(f"  outside phases (G - Tot): {G - ph['Tot']:.1f} ms; Tot/G = {ph['Tot'] / G:.2f}; GPU/G = {ph['GPU'] / G:.2f}; "
          f"Draw per draw {1000 * ph['Draw'] / mean(be):.1f} us" if be else '')
    if txw:
        print(f"  txw ms/frame: bind {mean([x[1] for x in txw]):.1f} create_texture {mean([x[2] for x in txw]):.1f} "
              f"sync-dl {mean([x[3] for x in txw]):.1f} ({mean([x[4] for x in txw]):.2f}/frame) "
              f"range-scan {mean([x[5] for x in txw]):.1f} ({mean([x[6] for x in txw]):.0f} scans/frame)  n={len(txw)}")
    if stall:
        print(f"  finishes per 60 frames: sd {mean([x[1] for x in stall]):.0f} flip {mean([x[2] for x in stall]):.0f} "
              f"stl {mean([x[3] for x in stall]):.0f} total {mean([x[4] for x in stall]):.0f}  n={len(stall)}")
    if sdc:
        print(f"  [sdcall] range scan: fin {mean([x[2] / x[1] for x in sdc]):.2f}/frame dl {mean([x[3] / x[1] for x in sdc]):.1f}/frame "
              f"{mean([x[4] / x[1] for x in sdc]):.1f} ms/frame  n={len(sdc)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--window', default='-2,1.5')
    ap.add_argument('--label', default='')
    ap.add_argument('--raw', action='store_true', help='print each phase sample')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))
    print(f"window: print time in mark{lo:+.1f} .. mark{hi:+.1f} s {a.label}  (phase fields and G are per-flip EMAs: samples of ~8 frames)")
    pooled = [[], [], [], [], [], []]
    for d in a.dirs:
        ev, marks = read(os.path.join(d, 'logcat.txt'))
        got = collect(ev, marks, lo, hi)
        if a.raw:
            for s in got[0]:
                print(f"  {s['mark']:9s} G={s['G']:5.1f} " + ' '.join(f"{k}={s['ph'].get(k, 0):.1f}" for k in SHOW))
        report(os.path.basename(d), *got)
        for i in range(6):
            pooled[i] += got[i]
    if len(a.dirs) > 1:
        report('POOLED', *pooled)


if __name__ == '__main__':
    sys.exit(main())
