#!/usr/bin/env python3
"""Judge docs/testing/predictions/bf2ubosize433-bf2-ubosz.json. Written and
committed before any run.

    ubosz_read.py <result dir> [<result dir> ...] [--from S] [--to S]

Rows are bf2stall433's (armread.py): one per 60-flip window, where a perflog
build prints hakuX-pace (window fps), hakuX-phase (GPU ms) and xemu-work (BE,
the draws of the last frame) at the same instant. S is seconds after the run's
`mark gameplay`. Each `ubosz[...]` line (vk/shaders.c, every 60 flip finishes,
on hakuX-stall) is joined to the nearest row within 2 s, and the
`ubosz-top[...]` line after it to the same row. Heavy views are rows with
BE >= 1800, as in armread.py.
"""
import argparse, os, re, statistics

ap = argparse.ArgumentParser()
ap.add_argument('dirs', nargs='+')
ap.add_argument('--from', dest='lo', type=float, default=-45.0)
ap.add_argument('--to', dest='hi', type=float, default=1e9)
args = ap.parse_args()

HEAVY = 1800
JOIN = 2.0
BINS = ['0', '1', '2', '3-4', '5-8', '9-16', '17-32', '33-64', '65-128', '129+']
BIN_HI = [0, 1, 2, 4, 8, 16, 32, 64, 128, 10 ** 9]
TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')
UB = re.compile(r'ubosz\[n(\d+) d(\d+) q(\d+) sw(\d+) lay ([\d/]+) sum(\d+) '
                r'c ([\d/]+) sum(\d+) span ([\d/]+) pk8 (\d+) pk16 (\d+) '
                r'bind(\d+)/(\d+)\]')
TOP = re.compile(r'ubosz-top\[c([^|]*)\| u([^\]]*)\]')


def num(rx, s):
    m = re.search(rx, s)
    return float(m.group(1)) if m else None


def hist(s):
    return [int(x) for x in s.split('/')]


def read_run(d):
    runlog = open(os.path.join(d, 'run.log'), errors='replace').read()
    mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', runlog)
    info = {'dir': os.path.basename(d.rstrip('/')), 'rows': [], 'ub': [],
            'void': None}
    if not mk:
        info['void'] = 'no mark gameplay'
        return info
    mark = int(mk.group(1)) * 3600 + int(mk.group(2)) * 60 + float(mk.group(3))
    cur, last_ub = None, None
    for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
        m = TS.match(line)
        if not m:
            continue
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) - mark
        u = UB.search(line)
        if u:
            g = u.groups()
            last_ub = {'t': t, 'n': int(g[0]), 'd': int(g[1]), 'q': int(g[2]),
                       'sw': int(g[3]), 'lay': hist(g[4]), 'lay_sum': int(g[5]),
                       'c': hist(g[6]), 'c_sum': int(g[7]), 'span': hist(g[8]),
                       'pk8': int(g[9]), 'pk16': int(g[10]),
                       'bind': int(g[11]), 'bind_same': int(g[12]),
                       'rows': {}, 'names': {}}
            info['ub'].append(last_ub)
            continue
        tp = TOP.search(line)
        if tp and last_ub is not None and abs(t - last_ub['t']) < 0.5:
            for kv in tp.group(1).split():
                k, v = kv.split(':')
                last_ub['rows'][int(k)] = int(v)
            for kv in tp.group(2).split():
                k, v = kv.rsplit(':', 1)
                last_ub['names'][k] = int(v)
            continue
        if 'hakuX-pace' in line:
            ms = num(r' ms=([\d.]+)', line)
            cur = {'t': t, 'fps': 60000.0 / ms if ms else None}
            info['rows'].append(cur)
        elif cur is not None and abs(t - cur['t']) < 0.3:
            if 'hakuX-phase' in line:
                cur['GPU'] = num(r'GPU:([\d.]+)', line)
            elif 'xemu-work' in line:
                cur['BE'] = num(r'BE:(\d+)', line)
    rows = [r for r in info['rows'] if r.get('BE') is not None]
    for ub in info['ub']:
        near = min(rows, key=lambda r: abs(r['t'] - ub['t']), default=None)
        if near is not None and abs(near['t'] - ub['t']) <= JOIN:
            ub['BE'] = near['BE']
            ub['GPU'] = near.get('GPU')
            ub['fps'] = near.get('fps')
            ub['dt'] = ub['t'] - near['t']
    info['ub'] = [u for u in info['ub'] if args.lo <= u['t'] <= args.hi]
    if len(info['ub']) < 15:
        info['void'] = 'only %d ubosz windows from %.0f s' % (len(info['ub']), args.lo)
    return info


def pool(ws):
    p = {'w': len(ws)}
    for k in ('n', 'd', 'q', 'sw', 'lay_sum', 'c_sum', 'pk8', 'pk16', 'bind',
              'bind_same'):
        p[k] = sum(w[k] for w in ws)
    for k in ('lay', 'c', 'span'):
        p[k] = [sum(w[k][i] for w in ws) for i in range(len(BINS))]
    p['draws'] = sum(60 * w['BE'] for w in ws if w.get('BE'))
    rows, names = {}, {}
    for w in ws:
        for k, v in w['rows'].items():
            rows[k] = rows.get(k, 0) + v
        for k, v in w['names'].items():
            names[k] = names.get(k, 0) + v
    p['rows'], p['names'] = rows, names
    return p


def frac(h, upto):
    tot = sum(h)
    return sum(h[:upto + 1]) / tot if tot else float('nan')


def median_bin(h):
    tot, acc = sum(h), 0
    for i, v in enumerate(h):
        acc += v
        if tot and acc * 2 >= tot:
            return BINS[i]
    return '-'


def report(name, p):
    sb = sum(p['lay'])
    print('%s: windows %d, uploads %d (d %d, q %d), binding switches %d (%.2f), '
          'same-binding %d' % (name, p['w'], p['n'], p['d'], p['q'], p['sw'],
                               p['sw'] / p['n'] if p['n'] else float('nan'), sb))
    if p['draws']:
        print('   uploads per draw %.2f, UBO binds per draw %.2f (repeat binds %d)'
              % (p['n'] / p['draws'], p['bind'] / p['draws'], p['bind_same']))
    for k, label in (('lay', 'layout chunks changed, same binding'),
                     ('c', 'constant rows changed, every upload'),
                     ('span', 'constant-row span, uploads with a change')):
        h = p[k]
        tot = sum(h)
        print('   %-42s %s' % (label, ' '.join(
            '%s:%.1f%%' % (b, 100.0 * v / tot) for b, v in zip(BINS, h) if v)
            if tot else '-'))
        if tot:
            print('   %-42s <=8 %.3f  <=16 %.3f  median bin %s  mean %.1f' % (
                '', frac(h, 4), frac(h, 5), median_bin(h),
                (p['lay_sum'] if k == 'lay' else p['c_sum']) / tot
                if k != 'span' else float('nan')))
    if p['n']:
        print('   push policy, uploads still rebinding (pk + switches) / uploads: '
              '8 vec4 %.3f, 16 vec4 %.3f' % ((p['pk8'] + p['sw']) / p['n'],
                                            (p['pk16'] + p['sw']) / p['n']))
    top = sorted(p['rows'].items(), key=lambda kv: -kv[1])[:12]
    print('   rows changed most (from each window\'s top 8):',
          ' '.join('c%d:%d' % kv for kv in top) or '-')
    tn = sorted(p['names'].items(), key=lambda kv: -kv[1])[:8]
    print('   uniforms changed most (chunks):', ' '.join('%s:%d' % kv for kv in tn) or '-')


runs = [read_run(d) for d in args.dirs]
for r in runs:
    joined = sum(1 for u in r['ub'] if 'BE' in u)
    dts = [abs(u['dt']) for u in r['ub'] if 'dt' in u]
    print('%s: %s ubosz windows=%d joined=%d max|dt|=%.2f s' % (
        r['dir'], 'VOID (' + r['void'] + ')' if r['void'] else 'ok',
        len(r['ub']), joined, max(dts) if dts else float('nan')))
ws = [u for r in runs if not r['void'] for u in r['ub'] if 'BE' in u]
heavy = [u for u in ws if u['BE'] >= HEAVY]
light = [u for u in ws if u['BE'] < 1200]
print()
report('heavy (BE >= %d)' % HEAVY, pool(heavy))
print()
report('light (BE < 1200)', pool(light))
print()
report('all joined windows', pool(ws))

# Legs, exactly as registered.
print()
ph = pool(heavy)
if not runs or all(r['void'] for r in runs):
    print('M0 instrument: VOID (%s)' % '; '.join(r['void'] or 'ok' for r in runs))
elif len(heavy) < 6 or not ph['n']:
    print('M0 instrument: BELOW RESOLUTION (heavy windows %d, uploads %d; need >= 6 '
          'and > 0)' % (len(heavy), ph['n']))
else:
    sb = sum(ph['lay'])
    f16 = frac(ph['lay'], 5)
    f8 = frac(ph['lay'], 4)
    r16 = (ph['pk16'] + ph['sw']) / ph['n']
    swf = ph['sw'] / ph['n']
    z = ph['lay'][0] / sb if sb else float('nan')
    mb = median_bin(ph['lay'])
    print('M0 instrument: PASS (heavy windows %d, uploads %d, same-binding %d)'
          % (len(heavy), ph['n'], sb))
    print('F8 = %.3f  F16 = %.3f  R16 = %.3f  switch share = %.3f  identical '
          'uploads Z = %.3f  median bin %s' % (f8, f16, r16, swf, z, mb))
    if f16 >= 0.50 and r16 <= 0.50:
        v = 'PUSH: most heavy-view uploads change <= 16 vec4, and a 16-vec4 push ' \
            'policy keeps the UBO bind off most of them -> successor brief'
    elif f16 >= 0.50:
        v = 'PUSH-SWITCH-BOUND: the changes fit, but binding switches (%.2f of ' \
            'uploads) still force a rebind -> the successor needs one uniform ' \
            'block shared across shaders' % swf
    elif BINS.index(mb) >= BINS.index('33-64'):
        v = 'LARGE: most same-binding uploads change > 32 vec4 -> push constants ' \
            'do not help as stated; the lever is batching draws that share constants'
    else:
        v = 'MIXED: report both numbers'
    print('VERDICT:', v)
    if z >= 0.30:
        print('NOTE Z: %.2f of same-binding uploads are byte-identical to the one '
              'before (registered note leg)' % z)
