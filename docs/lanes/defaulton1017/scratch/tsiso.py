#!/usr/bin/env python3
"""Judge the TS isolation rows (NOTES, "Triggered, TS isolation") as written: does the route reach the match?

For each result dir: env, the switch lines (s2tcvt, rearly, fldcw chain, fist round), crash and route end;
the shots s13..s19 against fps1015's off run (0-1792170186, which reached the match) as a mean absolute
difference on 64x48 grey; and tsread's play windows with each signature (on: cvt 0 and s2tc >= 600; off:
cvt >= 600). REACHES = at least 30 play windows and two thirds of them carrying the signature for the row's
S2T state (on unless HAKUX_S2T_CVT=0); otherwise DROPS, with the shots to say where the route stopped.
The S2T state rule is ed2b1d3333's (S2T on by default). fps1015's runs, on a binary where it was off by
default, read DROPS for their off arm here; their signature counts are printed for reading by hand.
usage: tsiso.py <result dir> [...]"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'fps1015'))
import tsread  # noqa: E402

R = '/home/justin/hakux-work/dispatch/results'
MASTER = os.path.join(R, '0-1792170186-fps1015-2314810')
LINES = ('[s2tcvt] on', '[s2tcvt] off', '[rearly1018] early=', '[fldcw1018] chain=', 'perfarch fist round=')


def shots(d):
    out = {}
    for f in sorted(os.listdir(os.path.join(d, 'route-frames'))):
        lab = f.split('-', 1)[1].split('-')[0]
        out.setdefault(lab, os.path.join(d, 'route-frames', f))
    return out


def small(p):
    return list(Image.open(p).convert('L').resize((64, 48)).getdata())


def mad(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


ms = shots(MASTER)
for arg in sys.argv[1:]:
    d = arg if arg.startswith('/') else os.path.join(R, arg)
    import json
    req = json.load(open(os.path.join(d, 'request.json')))
    env = req.get('env') or []
    s2t_on = 'HAKUX_S2T_CVT=0' not in env
    lc = open(os.path.join(d, 'logcat.txt'), errors='replace').read() if os.path.exists(
        os.path.join(d, 'logcat.txt')) else ''
    seen = []
    for key in LINES:
        i = lc.find(key)
        if i >= 0:
            seen.append(lc[i:lc.find('\n', i)].strip())
    crash = lc.count('hakuX-crash') + lc.count('Fatal signal')
    rl = open(os.path.join(d, 'run.log'), errors='replace').read() if os.path.exists(
        os.path.join(d, 'run.log')) else ''
    print('== %s  env %s' % (os.path.basename(d), ' '.join(env)))
    for s in seen:
        print('   ' + s)
    end = any(ln.startswith('ROUTE ') and ln.rstrip().endswith(' end') for ln in rl.splitlines())
    print('   crash %d  route end %s' % (crash, end))
    sh = shots(d)
    row = []
    for n in range(13, 20):
        k = 's%02d' % n
        row.append('%s %s' % (k, '%.0f' % mad(small(sh[k]), small(ms[k])) if k in sh and k in ms else '-'))
    print('   shots against master off: ' + '  '.join(row))
    t = tsread.read_run(d)
    if 'error' in t:
        print('   tsread: %s  -> DROPS (no play span)' % t['error'])
        continue
    play = [w for w in t['windows'] if w['span'] == 'play']
    on = sum(1 for w in play if tsread.signature('on', w))
    off = sum(1 for w in play if tsread.signature('off', w))
    want = on if s2t_on else off
    ok = len(play) >= 30 and want * 3 >= 2 * len(play)
    gf = sorted(w['gfps'] for w in play)
    print('   play windows %d: on-signature %d, off-signature %d (wanted %s); play median gfps %s  -> %s' % (
        len(play), on, off, 'on' if s2t_on else 'off', gf[len(gf) // 2] if gf else '-',
        'REACHES' if ok else 'DROPS'))
