#!/usr/bin/env python3
"""Judge the bf2stall433 BF2 soak pair (docs/testing/predictions/
bf2stall433-bf2-soak.json). Written and committed before any run.

    armread.py --a <dir> [<dir> ...] --b <dir> [<dir> ...] [--from S] [--to S]

Rows are collapse433's (modecmp.py): one per 60-flip window, where a perflog
build prints hakuX-pace (window fps), hakuX-phase (GPU ms per frame and its
render/transfer split) and xemu-work (BE draws and RP passes of the last
frame) at the same instant. S is seconds after the run's `mark gameplay`.
Rows are pooled per arm and compared within BE bins, because the blind route
sets the view and the view sets the draw count.
"""
import argparse, os, re, statistics

ap = argparse.ArgumentParser()
ap.add_argument('--a', nargs='+', required=True)
ap.add_argument('--b', nargs='+', required=True)
ap.add_argument('--from', dest='lo', type=float, default=-45.0)
ap.add_argument('--to', dest='hi', type=float, default=1e9)
args = ap.parse_args()

BINS = [0, 600, 1200, 1800, 2400, 99999]
HEAVY = 1800
TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')


def num(rx, s):
    m = re.search(rx, s)
    return float(m.group(1)) if m else None


def read_run(d):
    runlog = open(os.path.join(d, 'run.log'), errors='replace').read()
    mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', runlog)
    info = {'dir': os.path.basename(d.rstrip('/')), 'rows': [], 'mirror': [],
            'mirror_on': None, 'void': None}
    if not mk:
        info['void'] = 'no mark gameplay'
        return info
    mark = int(mk.group(1)) * 3600 + int(mk.group(2)) * 60 + float(mk.group(3))
    cur = None
    for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
        if '[vtxmirror]' in line:
            if '[vtxmirror] on' in line or '[vtxmirror] off' in line:
                info['mirror_on'] = line.split('[vtxmirror]', 1)[1].strip()
            else:
                kb = num(r' kb=(\d+)', line)
                if kb is not None:
                    info['mirror'].append(kb)
        m = TS.match(line)
        if not m:
            continue
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) - mark
        if 'hakuX-pace' in line:
            ms = num(r' ms=([\d.]+)', line)
            cur = {'t': t, 'fps': 60000.0 / ms if ms else None}
            info['rows'].append(cur)
        elif cur is not None and abs(t - cur['t']) < 0.3:
            if 'hakuX-phase' in line:
                cur['GPU'] = num(r'GPU:([\d.]+)', line)
                cur['X'] = num(r'GPU:[\d.]+\(R:[\d.]+ X:([\d.]+)', line)
                cur['Fen'] = num(r'Fen:([\d.]+)', line)
                cur['Tot'] = num(r'\| Tot:([\d.]+)', line)
            elif 'xemu-work' in line:
                cur['BE'] = num(r'BE:(\d+)', line)
                cur['RP'] = num(r' RP:(\d+)', line)
    info['rows'] = [r for r in info['rows']
                    if args.lo <= r['t'] <= args.hi and r.get('BE') is not None
                    and r.get('GPU') is not None and r.get('fps') is not None]
    if len(info['rows']) < 15:
        info['void'] = 'only %d rows in the window' % len(info['rows'])
    return info


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else float('nan')


def share(rows):
    return sum(1 for r in rows if r['fps'] >= 29.5) / len(rows) if rows else float('nan')


def fit(rows):
    xs = [r['BE'] for r in rows]
    ys = [r['GPU'] for r in rows]
    if len(xs) < 3:
        return float('nan'), float('nan')
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if not sxx:
        return float('nan'), float('nan')
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return a, my - a * mx


arms = {}
for name, dirs in (('A', args.a), ('B', args.b)):
    runs = [read_run(d) for d in dirs]
    for r in runs:
        print('%s %s: %s rows=%d mirror=%s%s' % (
            name, r['dir'], 'VOID (' + r['void'] + ')' if r['void'] else 'ok',
            len(r['rows']), r['mirror_on'] or '-',
            ' kb/120fl med=%.0f n=%d' % (med(r['mirror'][2:] or r['mirror']),
                                         len(r['mirror'])) if r['mirror'] else ''))
    arms[name] = [row for r in runs if not r['void'] for row in r['rows']]
    arms[name + 'runs'] = runs

print()
print('%-11s | %-34s | %-34s' % ('BE bin', 'A: n fps GPU X Fen >=29.5',
                                  'B: n fps GPU X Fen >=29.5'))
for lo, hi in zip(BINS, BINS[1:]):
    cells = []
    for name in 'AB':
        rs = [r for r in arms[name] if lo <= r['BE'] < hi]
        cells.append('%3d %5.1f %5.1f %4.1f %5.1f %4.2f' % (
            len(rs), med([r['fps'] for r in rs]), med([r['GPU'] for r in rs]),
            med([r['X'] for r in rs]), med([r['Fen'] for r in rs]), share(rs))
            if rs else '  0')
    print('%5d-%-5d | %-34s | %-34s' % (lo, hi, cells[0], cells[1]))

heavy = {n: [r for r in arms[n] if r['BE'] >= HEAVY] for n in 'AB'}
light = {n: [r for r in arms[n] if r['BE'] < 1200] for n in 'AB'}
slope = {n: fit(arms[n]) for n in 'AB'}
print()
for n in 'AB':
    print('%s: all n=%d fps>=29.5 %.3f | heavy n=%d GPU %.1f fps %.1f >=29.5 %.2f | '
          'light GPU %.1f | X %.2f | fit GPU = %.4f*BE + %.1f' % (
              n, len(arms[n]), share(arms[n]), len(heavy[n]),
              med([r['GPU'] for r in heavy[n]]), med([r['fps'] for r in heavy[n]]),
              share(heavy[n]), med([r['GPU'] for r in light[n]]),
              med([r['X'] for r in arms[n]]), slope[n][0], slope[n][1]))

# Legs, exactly as registered.
print()
b_on = [r['mirror_on'] for r in arms['Bruns'] if not r['void']]
p0 = all(s and s.startswith('on') and 'cached=1 coherent=1' in s for s in b_on) and b_on
print('P0 premise (B logs [vtxmirror] on, host cached=1 coherent=1): %s'
      % ('PASS' if p0 else 'FAIL -> the mirror removes no snoop; read P1 as INERT'))
if len(heavy['A']) < 8 or len(heavy['B']) < 8:
    print('P5 resolution: BELOW RESOLUTION (heavy rows A=%d B=%d, need >= 8 each)'
          % (len(heavy['A']), len(heavy['B'])))
else:
    ga, gb = med([r['GPU'] for r in heavy['A']]), med([r['GPU'] for r in heavy['B']])
    q = gb / ga
    print('P1 heavy-view GPU ms (BE >= %d): B/A = %.1f/%.1f = %.3f -> %s' % (
        HEAVY, gb, ga, q,
        'PASS' if q <= 0.80 else 'PARTIAL' if q <= 0.95 else 'FAIL (V refuted as the cause)'))
    sa, sb = slope['A'][0], slope['B'][0]
    print('P2 GPU per draw (fit slope): B/A = %.4f/%.4f -> %s' % (
        sb, sa, 'PASS' if sb <= 0.75 * sa else 'FAIL'))
    fa, fb = med([r['fps'] for r in heavy['A']]), med([r['fps'] for r in heavy['B']])
    print('P3 heavy-view fps: B %.1f vs A %.1f; >=29.5 share B %.2f vs A %.2f -> %s' % (
        fb, fa, share(heavy['B']), share(heavy['A']),
        'PASS' if fb >= fa + 2.0 or share(heavy['B']) > share(heavy['A']) + 0.15 else 'FAIL'))
print('P3b all-window >=29.5 share: B %.3f vs A %.3f -> %s' % (
    share(arms['B']), share(arms['A']),
    'PASS' if share(arms['B']) >= share(arms['A']) - 0.05 else 'FAIL (regression)'))
la, lb = med([r['GPU'] for r in light['A']]), med([r['GPU'] for r in light['B']])
xa, xb = med([r['X'] for r in arms['A']]), med([r['X'] for r in arms['B']])
print('P4 cost: light-view GPU B %.1f vs A %.1f (limit A*1.05+0.5); transfer X B %.2f '
      'vs A %.2f (limit A+0.5) -> %s' % (
          lb, la, xb, xa,
          'PASS' if lb <= la * 1.05 + 0.5 and xb <= xa + 0.5 else 'FAIL'))
