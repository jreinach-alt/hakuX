#!/usr/bin/env python3
"""Read a HAKUX_APU_VOICELOG run: the legs of predictions/nfsaudio1011-identify.json.

    voiceread.py <result id or dir> [--stale N] [--scan N]

From logcat.txt's 'apuvoice' lines (tag hakuX-audio) and the pulled
apu_monitor capture:

  V  the instrument ran: 'on' line, sec lines, capture length, drops.
  A  the VP-side stale share of the top voice by loud blocks, against the
     output-side lag-2400 share of the same run (replay_share.py's rule).
  P  VP pacing from the sec lines: frames/s, lead range, bursts, maxgap.
  M  the material for naming the mechanism: each loud voice's config, its
     fresh/stale/first blocks and SSL switches, the stale runs' lap and
     write ages, and the first N stale and scan lines verbatim.
"""
import glob
import os
import re
import sys
from collections import Counter, defaultdict

import numpy as np

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
KV = re.compile(r'(\w+)=([^\s]+)')
LAG, MIN_RUN, LOUD = 2400, 16, 200


def kv(s):
    return dict(KV.findall(s))


def num(x, default=None):
    try:
        return float(x.rstrip('%'))
    except (TypeError, ValueError):
        return default


def output_share(d):
    pcm = sorted(p for p in glob.glob(d + '/pulled/**/apu_monitor.s16le48k2ch.pcm*', recursive=True)
                 if not p.endswith('.json'))
    if not pcm:
        return None, 0.0
    x = np.concatenate([np.fromfile(p, dtype='<i2') for p in pcm]).reshape(-1, 2).astype(np.int64)
    loud = np.abs(x).max(axis=1) > LOUD
    same = np.zeros(len(x), bool)
    same[LAG:] = np.all(x[LAG:] == x[:-LAG], axis=1)
    m = (same & loud).astype(np.int8)
    e = np.diff(np.concatenate(([0], m, [0])))
    s, t = np.flatnonzero(e == 1), np.flatnonzero(e == -1)
    k = (t - s) >= MIN_RUN
    n = int((t[k] - s[k]).sum())
    return 100.0 * n / max(int(loud.sum()), 1), len(x) / 48000.0


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else float('nan')


def main():
    args = sys.argv[1:]
    nstale = nscan = 12
    if '--stale' in args:
        i = args.index('--stale'); nstale = int(args[i + 1]); del args[i:i + 2]
    if '--scan' in args:
        i = args.index('--scan'); nscan = int(args[i + 1]); del args[i:i + 2]
    for rid in args:
        d = rid if os.path.isdir(rid) else R + rid
        lines = [ln.split('apuvoice ', 1)[1].rstrip() for ln in open(d + '/logcat.txt', errors='replace')
                 if 'apuvoice ' in ln]
        kinds = Counter(ln.split(' ', 1)[0].rstrip(':') for ln in lines)
        sec = [kv(ln) for ln in lines if ln.startswith('sec ')]
        print('==', rid)
        print('V  lines by kind:', dict(kinds))

        # P: pacing
        vpf = [num(s.get('vpframes')) for s in sec if s.get('vpframes')]
        leads = [tuple(int(v) for v in s['lead'].split('..')) for s in sec if '..' in s.get('lead', '')]
        gaps = [num(s.get('maxgap')) for s in sec]
        bursts = [num(s.get('bursts')) for s in sec]
        drops = Counter()
        for s in sec:
            for i, v in enumerate(s.get('dropped', '0/0/0').split('/')):
                drops[('event', 'pio', 'scan')[i]] += int(v)
        if vpf:
            print('P  vpframes/s median %.0f (p10 %.0f, p90 %.0f; 1500 = real time); lead min %d max %d samples;'
                  ' maxgap p50 %.0f p90 %.0f us; bursts/s median %.0f' % (
                      pct(vpf, 50), pct(vpf, 10), pct(vpf, 90), min(l[0] for l in leads), max(l[1] for l in leads),
                      pct(gaps, 50), pct(gaps, 90), pct(bursts, 50)))
        print('   dropped lines, all seconds:', dict(drops))
        rs = [s.get('ring_stale', '0/0').split('/') for s in sec]
        rsn, rsd = sum(int(a) for a, b in rs), sum(int(b) for a, b in rs)
        print('   ring_stale pooled %d/%d = %.1f%%' % (rsn, rsd, 100.0 * rsn / max(rsd, 1)))

        # Per voice, pooled over the voice lines (top 3 per second).
        pool = defaultdict(Counter)
        cfg = {}
        win = defaultdict(lambda: defaultdict(Counter))
        t_sec = None
        for ln in lines:
            if ln.startswith('sec '):
                t_sec = num(kv(ln).get('t'), 0) / 1e6
            elif ln.startswith('voice '):
                v = kv(ln)
                vid = int(v['v'])
                for k in ('loud', 'fresh', 'stale', 'first', 'samples', 'sslsw', 'sslrep', 'sslempty', 'pio', 'notify'):
                    pool[vid][k] += int(v.get(k, 0))
                pool[vid]['secs'] += 1
                cfg[vid] = ln.split(' A=')[0]
                if t_sec is not None:
                    w = int(t_sec // 30) * 30
                    win[w][vid]['fresh'] += int(v.get('fresh', 0))
                    win[w][vid]['stale'] += int(v.get('stale', 0))
                    win[w][vid]['loud'] += int(v.get('loud', 0))
        top = sorted(pool, key=lambda v: -pool[v]['loud'])
        print('M  voices by loud blocks (pooled over the seconds each was in the top 3):')
        for v in top[:6]:
            p = pool[v]
            j = p['fresh'] + p['stale']
            print('   v=%-3d secs=%-4d loud=%-7d fresh=%-7d stale=%-6d first=%-6d share=%5.1f%% sslsw=%d sslrep=%d '
                  'sslempty=%d pio=%d notify=%d' % (v, p['secs'], p['loud'], p['fresh'], p['stale'], p['first'],
                                                   100.0 * p['stale'] / max(j, 1), p['sslsw'], p['sslrep'],
                                                   p['sslempty'], p['pio'], p['notify']))
            print('        last: ' + cfg[v])
        print('   per 30 s window (top voice of the run, then all top-3 voices pooled):')
        for w in sorted(win):
            tv = win[w].get(top[0], Counter()) if top else Counter()
            a = sum(c['stale'] for c in win[w].values())
            b = sum(c['stale'] + c['fresh'] for c in win[w].values())
            print('   %4d s  v%-3s %5.1f%% of %-6d   all %5.1f%% of %d' % (
                w, top[0] if top else '-', 100.0 * tv['stale'] / max(tv['stale'] + tv['fresh'], 1),
                tv['stale'] + tv['fresh'], 100.0 * a / max(b, 1), b))

        # A: agreement
        out, secs = output_share(d)
        if top and out is not None:
            p = pool[top[0]]
            vp = 100.0 * p['stale'] / max(p['stale'] + p['fresh'], 1)
            print('A  VP stale share v=%d %.1f%%, output lag-%d share %.1f%% (%.0f s captured): |diff| %.1f points'
                  % (top[0], vp, LAG, out, secs, abs(vp - out)))
        else:
            print('A  not readable: top voice %s, output share %s' % (top[:1], out))

        # Stale runs
        st = [kv(ln) for ln in lines if ln.startswith('stale ')]
        if st:
            def col(k):
                return [num(s.get(k)) for s in st if num(s.get(k), -1) >= 0]
            print('   stale runs: %d lines; blocks p50 %.0f p90 %.0f; lap p50 %.1f ms; pio_age p50 %.1f ms;'
                  ' blk_wr_age p50 %.1f ms (n %d); wr_age p50 %.1f ms' % (
                      len(st), pct(col('blocks'), 50), pct(col('blocks'), 90), pct(col('lap'), 50) / 1e3,
                      pct(col('pio_age'), 50) / 1e3, pct(col('blk_wr_age'), 50) / 1e3, len(col('blk_wr_age')),
                      pct(col('wr_age'), 50) / 1e3))
            print('   by voice:', dict(Counter(s.get('v') for s in st)))
        for kind, n in (('stale ', nstale), ('sslsw ', nstale), ('sslempty ', 4), ('cfg ', 8), ('scan ', nscan)):
            sel = [ln for ln in lines if ln.startswith(kind)]
            if sel:
                print('   first %d of %d %s lines:' % (min(n, len(sel)), len(sel), kind.strip()))
                for ln in sel[:n]:
                    print('     ' + ln[:400])


if __name__ == '__main__':
    main()
