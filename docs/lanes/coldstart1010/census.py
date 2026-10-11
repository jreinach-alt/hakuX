#!/usr/bin/env python3
"""Cold start 1 against the warm countdown, every instrument on one page (#433, lane.coldstart1010).

    census.py <result dir> [...] [--window -2,1.5]

A perflog run with HAKUX_FRAMETRACE=1 HAKUX_PROBE_WAITS=1 and `--pull 'frametrace_*'`. Cold = `mark
gameplay`, warm = go2 .. go12, both over [mark+LO, mark+HI] (default -2,1.5, the countdown; raread.py's
windows); a start whose route input failed or hung is left out (raread.bad_starts).

  frametrace  the PFIFO thread's schedstat row per frame (reportasync1010 ftpair.account): P = p_run +
              p_rq + p_blk; p_blk = pidle + p_c_rep (waits inside process_pending_reports, pfifo.lock
              held) + other hooked waits + unhooked. GPU busy and render passes (`rp`) per frame. The guest
              line is ftbuckets.line: work, v_blk, lockw (the DMA_PUT store's wait for pfifo.lock).
  phase       hakuX-phase samples (per-flip EMAs, ~8 frames each) printed in the window, mean: the split of
              p_run (Draw = recording, Fin = finishes with Sub and Fen, Surf, Tex, Shd), Idle, Tot, and
              G - Tot (the PFIFO time no phase timer covers)
  shd413      pipeline creates per frame and ms inside them (60-flip deltas / 60)
  rpbrk       render-pass breaks per frame by cause (fin fb qry clr nd srf; 60-flip counts / 60)
  work        xemu-work's last-frame snapshot (1/s): RP, S2T, PGen, SGen, TexU, Clr
  cpu         hakuX-cpu Pull Lk (the puller's lock ms) and Lw, per frame
  probe1010   rotations, blocking rotations and ms blocked per frame (lines printed in the window,
              widened to -4,+3.5 for the cold start: one line per 60 flips)
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'reportasync1010'))
sys.path.insert(0, os.path.join(HERE, '..', 'nfs30plan1010'))
sys.path.insert(0, os.path.join(HERE, '..', 'drawrec1010'))
import ftbuckets  # noqa: E402
import ftpair  # noqa: E402
import phaseread  # noqa: E402
import proberead  # noqa: E402
import raread  # noqa: E402

TS = phaseread.TS
RPBRK = re.compile(r'hakuX-rpbrk\(\s*\d+\): RP:(\d+)\(fin(\d+) fb(\d+) qry(\d+) clr(\d+) nd(\d+) srf(\d+)\)')
WORK = re.compile(r'xemu-work\(\s*\d+\): (.*)$')
SHD = re.compile(r'\[shd413\] f=\d+ .*?dpc_ms=([\d.]+) dpn=(\d+)')
WFIELDS = ('BE', 'RP', 'PGen', 'SGen', 'TexU', 'Clr')

PHASE_SHOW = ['Draw', 'Vtx', 'Syn', 'Prw', 'Pipe', 'Desc', 'Setup', 'Cmd', 'Fin', 'Sub', 'Fen', 'Surf', 'Tex',
              'Shd', 'Flip', 'Idle', 'Fr', 'St', 'Tot', 'GPU', 'RP']


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float('nan')


def read_extra(d):
    rpbrk, work, shd, lk = [], [], [], []
    with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
        for ln in f:
            m = TS.match(ln)
            if not m:
                continue
            t = phaseread.secs(m)
            q = RPBRK.search(ln)
            if q:
                rpbrk.append((t, [int(x) for x in q.groups()]))
                continue
            q = SHD.search(ln)
            if q:
                shd.append((t, float(q.group(1)), int(q.group(2))))
                continue
            q = phaseread.CPU.search(ln)
            if q:
                lk.append((t, float(q.group(3))))
                continue
            q = WORK.search(ln)
            if q:
                v = {}
                for k, x in re.findall(r'(\w+):(\d+)', q.group(1)):
                    v.setdefault(k, int(x))
                s2t = re.search(r'S2T:(\d+)/(\d+)', q.group(1))
                v['S2T'] = int(s2t.group(1)) if s2t else None
                work.append((t, v))
    return rpbrk, work, shd, lk


def window(evs, marks, lo, hi, which):
    return raread.sel(evs, marks, lo, hi, which)


def report(d, lo, hi):
    name = os.path.basename(d.rstrip('/'))
    marks, _, _, _ = raread.read(d)
    bad = raread.bad_starts(d)
    good = raread.valid(marks, bad)
    print(f"\n=== {name}: {len(marks)} marks, {len(good)} valid"
          + ''.join(f'; dropped {k} ({v})' for k, v in bad.items()))
    ev, _ = phaseread.read(os.path.join(d, 'logcat.txt'))
    rpbrk, work, shd, lk = read_extra(d)
    _, prows = proberead.read_probe(d)
    ft = ftpair.load(d)
    acc = {}
    for which in ('cold', 'warm'):
        ph = window(ev['phase'], good, lo, hi, which)
        perf = window(ev['perf'], good, lo, hi, which)
        cpu = window(ev['cpu'], good, lo, hi, which)
        pace = window(ev['pace'], good, lo, hi, which)
        a = {'n_phase': len(ph)}
        for k in PHASE_SHOW:
            a[k] = mean([p[1].get(k) for p in ph])
        a['G'] = mean([p[2] for p in perf])
        a['pace'] = mean([p[3] / 60 for p in pace])
        a['Lk'] = mean([x[1] / 60 for x in window(lk, good, lo, hi, which)])
        a['Pull'] = mean([c[2] / 60 for c in cpu])
        a['Lw'] = mean([c[4] / 60 for c in cpu])
        rb = window(rpbrk, good, lo, hi, which)
        for i, k in enumerate(('rp', 'fin', 'fb', 'qry', 'clr', 'nd', 'srf')):
            a['brk_' + k] = mean([r[1][i] / 60 for r in rb])
        a['n_brk'] = len(rb)
        wk = window(work, good, lo, hi, which)
        for k in WFIELDS + ('S2T',):
            a['w_' + k] = mean([w[1].get(k) for w in wk])
        a['n_work'] = len(wk)
        sh = window(shd, good, lo, hi, which)
        a['pc_ms'] = mean([s[1] / 60 for s in sh])
        a['pc_n'] = mean([s[2] / 60 for s in sh])
        plo, phi = (-4.0, 3.5) if which == 'cold' else (lo, hi)
        pr = [r for _, r in window([(r['t'], r) for r in prows], good, plo, phi, which)]
        a['probe'] = proberead.probe_stats(pr)
        a['ft'] = ftpair.account(ft[which]) if ft else None
        a['ft_frames'] = ft[which] if ft else []
        acc[which] = a
    c, w = acc['cold'], acc['warm']

    def row(label, k, fmtw='{:8.2f}'):
        x, y = c.get(k), w.get(k)
        fx = fmtw.format(x) if isinstance(x, float) else f'{x!s:>8}'
        fy = fmtw.format(y) if isinstance(y, float) else f'{y!s:>8}'
        print(f"  {label:44s} {fx} {fy}")

    print(f"  {'':44s} {'cold':>8s} {'warm':>8s}")
    print(" frametrace, PFIFO thread, ms per frame")
    if c['ft'] and w['ft']:
        for k in ftpair.ROWS:
            print(f"  {k:44s} {c['ft'][k]:8.2f} {w['ft'][k]:8.2f}")
        rp = lambda fr: mean([r.get('rp') for r in fr])  # noqa: E731
        print(f"  {'render passes per frame (rp)':44s} {rp(c['ft_frames']):8.1f} {rp(w['ft_frames']):8.1f}")
        print(f"  {'frames':44s} {c['ft']['n']:8d} {w['ft']['n']:8d}")
        print(" frametrace, guest")
        print(ftbuckets.line('cold', c['ft_frames']))
        print(ftbuckets.line('warm', w['ft_frames']))
    else:
        print("  (no frametrace)")
    print(f" phase (hakuX-phase EMA samples: cold {c['n_phase']}, warm {w['n_phase']}), ms per frame")
    for k in PHASE_SHOW:
        row(k, k)
    row('G (hakuX-perf EMA period)', 'G')
    row('pace ms/frame (60-flip spans)', 'pace')
    print(f"  {'G - Tot (untimed)':44s} {c['G'] - c['Tot']:8.2f} {w['G'] - w['Tot']:8.2f}")
    row('cpu Pull ms/frame', 'Pull')
    row('cpu Pull Lk ms/frame', 'Lk')
    row('cpu Lw ms/frame', 'Lw')
    print(f" shd413 per frame")
    row('pipeline creates', 'pc_n')
    row('ms inside pipeline creates', 'pc_ms')
    print(f" rpbrk per frame (lines: cold {c['n_brk']}, warm {w['n_brk']})")
    for k in ('rp', 'fin', 'fb', 'qry', 'clr', 'nd', 'srf'):
        row('breaks ' + k, 'brk_' + k, '{:8.1f}')
    print(f" xemu-work, last-frame snapshot (lines: cold {c['n_work']}, warm {w['n_work']})")
    for k in WFIELDS + ('S2T',):
        row(k, 'w_' + k, '{:8.1f}')
    print(" [probe1010] per frame (cold lines printed mark-4 .. +3.5 s)")
    for k in ('frames', 'rot', 'blk', 'rot_ms', 'mid', 'mid_ms', 'flip', 'flip_ms', 'draws'):
        x = c['probe'][k] if c['probe'] else float('nan')
        y = w['probe'][k] if w['probe'] else float('nan')
        print(f"  {k:44s} {x:8.2f} {y:8.2f}")
    for which in ('cold', 'warm'):
        p = acc[which]['probe']
        if p:
            print(f"  nd {which}: " + ' '.join(f"{k}={n:.2f}/{ms:.2f}" for k, (n, ms) in sorted(p['nd'].items())))
    return acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--window', default='-2,1.5')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))
    for d in a.dirs:
        report(d, lo, hi)
    return 0


if __name__ == '__main__':
    sys.exit(main())
