#!/usr/bin/env python3
"""Join the ~2 s instrument lines of one run against offset from the mark.

usage: joinread.py <result-copy> [bucket_s]
Per bucket: pace fps (60 flips / window ms), guest idle share from [rr425w]
(idle_us / (idle_us + busy_us)), vCPU thread cpu ms per 2 s from [tlb68]
cpu=, renderer idle Ri from the gfps line, vbl rate from 'vbl n=', and the
[idlehalt] run_us share.
"""
import re, sys, os


def t(s):
    h, mi, se = s.split(':')
    return int(h) * 3600 + int(mi) * 60 + float(se)


d = sys.argv[1]
bucket = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
runlog = open(os.path.join(d, 'run.log'), errors='replace').read()
mark = t(re.search(r'ROUTE (\d+:\d+:\d+\.\d+) mark gameplay', runlog).group(1))
TS = re.compile(r'^\d+-\d+ (\d+:\d+:\d+\.\d+) ')
series = {k: [] for k in ('fps', 'gidle', 'tcpu', 'Ri', 'vblhz', 'run', 'G', 'rdctex', 'rdcv')}
for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
    m = TS.match(line)
    if not m:
        continue
    off = t(m.group(1)) - mark
    if off < -60:
        continue
    if 'hakuX-pace' in line:
        ms = float(re.search(r' ms=([\d.]+)', line).group(1))
        series['fps'].append((off, 60000.0 / ms))
    elif '[rr425w]' in line:
        mm = re.search(r'idle_us=(\d+) busy_us=(\d+)', line)
        i, b = int(mm.group(1)), int(mm.group(2))
        if i + b:
            series['gidle'].append((off, 100.0 * i / (i + b)))
    elif '[rr425]' in line:
        mm = re.search(r' dt=(\d+) .* x=(\d+) .*gapus=(\d+) tbus=(\d+)', line)
        if mm:
            dt = int(mm.group(1)) * 1000.0
            series.setdefault('tb%', []).append((off, 100.0 * int(mm.group(4)) / dt))
            series.setdefault('gap%', []).append((off, 100.0 * int(mm.group(3)) / dt))
            series.setdefault('out%', []).append((off, 100.0 - 100.0 * (int(mm.group(3)) + int(mm.group(4))) / dt))
            series.setdefault('x', []).append((off, int(mm.group(2))))
    elif '[tlb68]' in line:
        mm = re.search(r' dt=(\d+) cpu=(\d+)', line)
        series['tcpu'].append((off, 100.0 * int(mm.group(2)) / max(1, int(mm.group(1)))))
    elif 'gfps=' in line:
        mm = re.search(r'G:([\d.]+).*Ri:([\d.]+) Tq:([\d.]+)', line)
        series['G'].append((off, float(mm.group(1))))
        series['Ri'].append((off, float(mm.group(2))))
        series.setdefault('Tq', []).append((off, float(mm.group(3))))
    elif 'I/hakuX-perf' in line and ': vbl n=' in line:
        mm = re.search(r'rate=([\d.]+)Hz', line)
        if mm:
            series['vblhz'].append((off, float(mm.group(1))))
    elif ': vblphase n=' in line:
        mm = re.search(r'nodef\(n=(\d+) mean=(\d+) max=(\d+)\) def\(n=(\d+) mean=(\d+) max=(\d+)\).* clamp=(\d+)', line)
        if mm:
            g = [int(x) for x in mm.groups()]
            series.setdefault('ndmean', []).append((off, g[1] / 1e6))
            series.setdefault('ndmax', []).append((off, g[2] / 1e6))
            series.setdefault('defn', []).append((off, g[3]))
            series.setdefault('defmean', []).append((off, g[4] / 1e6))
            series.setdefault('clamp', []).append((off, g[6]))
    elif 'hakuX-pages' in line and ' inval ev=' in line:
        mm = re.search(r' ev=(\d+) .* cg=(\d+) xx=\d+ ins=(\d+)', line)
        if mm:
            series.setdefault('ev', []).append((off, int(mm.group(1))))
            series.setdefault('cg', []).append((off, int(mm.group(2))))
    elif '[idlehalt]' in line:
        mm = re.search(r'span_us=(\d+) run_us=(\d+)', line)
        if mm and int(mm.group(1)):
            series['run'].append((off, 100.0 * int(mm.group(2)) / int(mm.group(1))))
    elif '[rdc]' in line:
        mm = re.search(r' dt=(\d+) .*vtx=(\d+)/(\d+)/(\d+)/(\d+) .*tex=(\d+)/(\d+)/(\d+)/(\d+)', line)
        if mm:
            series['rdctex'].append((off, int(mm.group(8))))
            series['rdcv'].append((off, int(mm.group(4))))

if '-v' in sys.argv:
    for k in ('fps', 'gidle'):
        pass


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float('nan')


cols = ['fps', 'gidle', 'tcpu', 'tb%', 'gap%', 'out%', 'x', 'cg', 'ndmax', 'clamp']
for c in cols:
    series.setdefault(c, [])
print('bucket ' + ' '.join('%8s' % c for c in cols) + '   (medians; gidle/tcpu/run in %)')
lo = -60
while lo < 600:
    row = []
    for c in cols:
        xs = [v for (o, v) in series[c] if lo <= o < lo + bucket]
        row.append(med(xs))
    if any(x == x for x in row):
        print('%5d  ' % lo + ' '.join('%8.1f' % x for x in row))
    lo += bucket
