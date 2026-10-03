#!/usr/bin/env python3
"""Judge the mechanism legs of docs/testing/predictions/bf2push656-bf2-soak.json.
Written and committed before any run.

    push656_read.py --a <dir> [<dir> ...] --b <dir> [<dir> ...] [--from S]

GPU ms is judged by docs/lanes/bf2stall433/armread.py, unmodified. This
reads what the uniform overlay did, per arm, over heavy windows (BE >= 1800,
armread's convention): every ubosz[...] and ubopush[...] line (60 flips each)
is joined to the nearest hakuX-pace row within 2 s that carries BE, as
bf2ubosize433's ubosz_read.py does.

  binds/draw  ubosz's UBO set binds / (60 x BE). Both arms print ubosz.
  P0          B printed `[push656] ... uniform overlay on`, and ubopush lines.
  rebind      B: binds / (up + push), the uploads A would have made and
              rebound. The brief's target is <= 0.41 (R16 of bf2ubosize433).
  why         B: set/binding/psh/row/full, the share of uploads per reason.
"""
import argparse, os, re, statistics

ap = argparse.ArgumentParser()
ap.add_argument('--a', nargs='+', required=True)
ap.add_argument('--b', nargs='+', required=True)
ap.add_argument('--from', dest='lo', type=float, default=-45.0)
args = ap.parse_args()

HEAVY = 1800
JOIN = 2.0
TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')
UBOSZ = re.compile(r'ubosz\[n(\d+) .* bind(\d+)/(\d+)\]')
PUSH = re.compile(r'ubopush\[up (\d+) push (\d+) \(n1 (\d+) n2-4 (\d+) '
                  r'n5-8 (\d+) n9-12 (\d+)\) why ([\d/]+) bind (\d+) '
                  r'skip (\d+) pc (\d+)\]')


def num(rx, s):
    m = re.search(rx, s)
    return float(m.group(1)) if m else None


def read_run(d):
    runlog = open(os.path.join(d, 'run.log'), errors='replace').read()
    mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', runlog)
    info = {'dir': os.path.basename(d.rstrip('/')), 'rows': [], 'w': [],
            'on': None, 'void': None}
    if not mk:
        info['void'] = 'no mark gameplay'
        return info
    mark = int(mk.group(1)) * 3600 + int(mk.group(2)) * 60 + float(mk.group(3))
    cur = None
    pend = {}
    for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
        if '[push656]' in line:
            info['on'] = line.split('[push656]', 1)[1].strip()
        m = TS.match(line)
        if not m:
            continue
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) - mark
        u = UBOSZ.search(line)
        if u:
            pend = {'t': t, 'up_all': int(u.group(1)), 'bind': int(u.group(2))}
            info['w'].append(pend)
            continue
        p = PUSH.search(line)
        if p and pend and abs(t - pend['t']) < 0.5:
            g = [int(x) for x in p.groups()[:6]]
            pend.update(up=g[0], push=g[1], n=g[2:6],
                        why=[int(x) for x in p.group(7).split('/')],
                        obind=int(p.group(8)), skip=int(p.group(9)),
                        pc=int(p.group(10)))
            continue
        if 'hakuX-pace' in line:
            cur = {'t': t}
            info['rows'].append(cur)
        elif cur is not None and abs(t - cur['t']) < 0.3 and 'xemu-work' in line:
            cur['BE'] = num(r'BE:(\d+)', line)
    rows = [r for r in info['rows'] if r.get('BE') is not None]
    for w in info['w']:
        near = min(rows, key=lambda r: abs(r['t'] - w['t']), default=None)
        if near is not None and abs(near['t'] - w['t']) <= JOIN:
            w['BE'] = near['BE']
    info['w'] = [w for w in info['w'] if w['t'] >= args.lo and 'BE' in w]
    return info


def report(name, runs):
    print('== %s' % name)
    heavy = []
    for r in runs:
        h = [w for w in r['w'] if w['BE'] >= HEAVY]
        print('  %s: %s; %d windows, %d heavy; P0 line: %s' % (
            r['dir'], r['void'] or 'ok', len(r['w']), len(h), r['on']))
        heavy += h
    if not heavy:
        print('  no heavy windows: BELOW RESOLUTION')
        return None
    draws = sum(60 * w['BE'] for w in heavy)
    binds = sum(w['bind'] for w in heavy)
    out = {'heavy': len(heavy), 'bpd': binds / draws}
    print('  heavy windows %d, draws ~%d, UBO binds %d -> binds/draw %.3f' % (
        len(heavy), draws, binds, out['bpd']))
    pw = [w for w in heavy if 'up' in w]
    if pw:
        up = sum(w['up'] for w in pw)
        push = sum(w['push'] for w in pw)
        ob = sum(w['obind'] for w in pw)
        skip = sum(w['skip'] for w in pw)
        why = [sum(w['why'][i] for w in pw) for i in range(5)]
        n = [sum(w['n'][i] for w in pw) for i in range(4)]
        out['rebind'] = ob / max(1, up + push)
        print('  ubopush windows %d: uploads %d, pushed %d (push share %.3f)' %
              (len(pw), up, push, push / max(1, up + push)))
        print('  rebind = binds / (up + push) = %d / %d = %.3f   (target <= 0.41)'
              % (ob, up + push, out['rebind']))
        print('  binds skipped as repeats %d; overlay pushes %d' % (
            skip, sum(w['pc'] for w in pw)))
        print('  overlay size n1/n2-4/n5-8/n9-12: %s' % '/'.join(map(str, n)))
        print('  upload reasons set/binding/psh/row/full: %s  (shares %s)' % (
            '/'.join(map(str, why)),
            '/'.join('%.2f' % (x / max(1, up)) for x in why)))
    return out


A = report('A', [read_run(d) for d in args.a])
B = report('B', [read_run(d) for d in args.b])
if A and B:
    print('binds/draw B/A = %.3f / %.3f = %.3f' % (
        B['bpd'], A['bpd'], B['bpd'] / A['bpd'] if A['bpd'] else float('nan')))
