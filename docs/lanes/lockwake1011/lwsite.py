#!/usr/bin/env python3
"""The guest's pfifo.lock wait by site, cold start 1 against the warm countdown (#433, lane.lockwake1011).

    lwsite.py <result dir> [...] [--window -2,1.5]

A plain run with HAKUX_FRAMETRACE=1 and `--pull 'frametrace_*'`, on a build with lockwake1011's columns.
Frames come from ftpair.load (docs/lanes/reportasync1010): cold = `mark gameplay`, warm = go2 .. go12, both
over [mark+LO, mark+HI] (default -2,1.5, the countdown); post = go2 .. go12, +1.5 .. +12 s. A start whose route
input failed or hung is left out (raread.bad_starts).

Per frame, ms unless marked:
  lockw            the frame's lock_wait_ns (the column census.py and ftbuckets read)
  sum of sites     lw_kick + lw_put + lw_get + lw_ref + lw_oth; must equal lockw to rounding
  <site> ms        lw_<site>: KICK = pfifo_post_kick() (the posted DMA_PUT's wake), PUT = a DMA_PUT store
                   that was not posted, GET, REF, OTH = the locked branch of user_write by register
  <site> n, n>=10us   ln_<site>, lb_<site>: acquisitions, and those that waited 10 us or more
  us per wait      lw_<site> / ln_<site>
  parked           lw_parked: the waits that ended with the PFIFO thread in pfifo_park()
  vhp_<holder>     what the PFIFO thread was in while the vCPU waited for pfifo.lock (profile.h's holder
                   split): run = in no recorded wait (its own work, or parked: the park is no frametrace
                   wait), gpu = fence or download wait, rnd = submit or render-thread wait, idle, wait, unk
  lockw in frames  the share of the window's lockw that falls in frames whose lockw is >= 1, >= 4 ms

The hakuX-perf `lockw` line (60 flips, logcat) is read as a cross-check, over mark -4 .. +3.5 s for the
cold start (one line per ~2 s) and the window for warm.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'reportasync1010'))
sys.path.insert(0, os.path.join(HERE, '..', 'nfs30plan1010'))
import ftpair  # noqa: E402
import raread  # noqa: E402

SITES = ['kick', 'put', 'get', 'ref', 'oth']
HOLDERS = ['run', 'gpu', 'rnd', 'idle', 'wait', 'unk']
PERF = re.compile(r'hakuX-perf\(\s*\d+\): lockw f=(\d+) n=(\d+) lw=([\d.]+) (.*) parked=([\d.]+)')
SITE_F = re.compile(r'(\w+)=([\d.]+)/([\d.]+)/([\d.]+)')


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float('nan')


def col(fr, k, scale=1000.0):
    return mean([(r.get(k) or 0) / scale for r in fr]) if fr and k in fr[0] else float('nan')


def read_perf(d):
    out = []
    with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
        for ln in f:
            m = raread.TS.match(ln)
            q = PERF.search(ln) if m else None
            if not q:
                continue
            v = {'lw': float(q.group(3)), 'parked': float(q.group(5)), 'n': int(q.group(2))}
            for s, ms, n, nb in SITE_F.findall(q.group(4)):
                v[s] = (float(ms), float(n), float(nb))
            out.append((raread.secs(m), v))
    return out


def account(fr):
    a = {'n': len(fr), 'lockw': col(fr, 'lockw')}
    a['sum'] = mean([sum((r.get('lw_' + s) or 0) for s in SITES) / 1000.0 for r in fr]) if fr else float('nan')
    for s in SITES:
        a['lw_' + s] = col(fr, 'lw_' + s)
        a['ln_' + s] = col(fr, 'ln_' + s, 1.0)
        a['lb_' + s] = col(fr, 'lb_' + s, 1.0)
        tot_ns = sum(r.get('lw_' + s) or 0 for r in fr)
        tot_n = sum(r.get('ln_' + s) or 0 for r in fr)
        a['us_' + s] = tot_ns / tot_n if tot_n else float('nan')
    a['parked'] = col(fr, 'lw_parked')
    for h in HOLDERS:
        a['vhp_' + h] = col(fr, 'vhp_' + h)
    tot = sum(r.get('lockw') or 0 for r in fr)
    for cut in (1, 4):
        a[f'in{cut}'] = (100.0 * sum(r['lockw'] for r in fr if (r.get('lockw') or 0) >= cut * 1000) / tot
                         if tot else float('nan'))
    return a


def report(d, lo, hi):
    name = os.path.basename(d.rstrip('/'))
    ft = ftpair.load(d)
    if not ft:
        print(f"\n=== {name}: no frametrace or no marks")
        return None
    print(f"\n=== {name}: {ft['marks']} marks, csv {ft['csv']}, dropped {sorted(ft['bad']) or 'none'}")
    if 'lw_kick' not in (ft['cold'] or ft['warm'] or [{}])[0]:
        print("  (no lw_* columns: not a lockwake1011 build)")
        return None
    acc = {w: account(ft[w]) for w in ('cold', 'warm', 'post')}
    cols = ('cold', 'warm', 'post')
    print(f"  {'per frame':34s} " + ' '.join(f'{c:>8s}' for c in cols))

    def row(label, k, fmt='{:8.2f}'):
        print(f"  {label:34s} " + ' '.join(fmt.format(acc[c][k]) for c in cols))

    row('frames', 'n', '{:8d}')
    row('lockw ms', 'lockw')
    row('sum of sites ms', 'sum')
    for s in SITES:
        row(f'{s} ms', 'lw_' + s)
        row(f'{s} waits (n)', 'ln_' + s)
        row(f'{s} waits >= 10 us', 'lb_' + s)
        row(f'{s} us per wait', 'us_' + s, '{:8.1f}')
    row('parked ms (ended with PFIFO parked)', 'parked')
    for h in HOLDERS:
        row(f'vhp_{h} ms (PFIFO in, while waited)', 'vhp_' + h)
    row('% of lockw in frames >= 1 ms', 'in1', '{:8.0f}')
    row('% of lockw in frames >= 4 ms', 'in4', '{:8.0f}')

    perf = read_perf(d)
    marks, _, _, _ = raread.read(d)
    good = raread.valid(marks, raread.bad_starts(d))
    for which, (plo, phi) in (('cold', (-4.0, 3.5)), ('warm', (lo, hi))):
        ls = raread.sel(perf, good, plo, phi, which)
        if not ls:
            print(f"  perf lockw {which}: no lines")
            continue
        lw = mean([v['lw'] for _, v in ls])
        sites = ' '.join(f"{s}={mean([v[s][0] for _, v in ls if s in v]):.2f}/"
                         f"{mean([v[s][1] for _, v in ls if s in v]):.1f}" for s in SITES)
        print(f"  perf lockw {which} ({len(ls)} lines): lw={lw:.2f} {sites} "
              f"parked={mean([v['parked'] for _, v in ls]):.2f}")
    return acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--window', default='-2,1.5')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))
    if (lo, hi) != (-2.0, 1.5):
        ftpair.WINDOWS[:2] = [('cold', 'cold', lo, hi), ('warm', 'warm', lo, hi)]
    for d in a.dirs:
        report(d, lo, hi)
    return 0


if __name__ == '__main__':
    sys.exit(main())
