#!/usr/bin/env python3
"""Per-run extras beside decompose.py (lane.fps20786), all per guest frame.

    extras.py <result dir> [--mark HH:MM:SS]

From the always-on lines after the mark: the VBLANK histogram (hakuX-pace
v1..v4), the render thread's dirty-tracking walks ([rdc] site=calls/us/...),
the vCPU's pgraph.lock waits by register ([lock474] rN=reg:n:ms), the flip
wait ([lock474] flip_op_ms), and, when the build has NV2A_PERF_LOG, the
hakuX-phase / hakuX-cpu / xemu-gpu medians.
"""
import argparse, os, re, statistics
from collections import Counter, defaultdict

ap = argparse.ArgumentParser()
ap.add_argument('dir')
ap.add_argument('--mark')
a = ap.parse_args()
TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


runlog = open(os.path.join(a.dir, 'run.log'), errors='replace').read()
mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', runlog)
if a.mark:
    mk = re.match(r'(\d+):(\d+):([\d.]+)', a.mark)
mark = secs(*mk.groups())
vb = Counter()
frames = 0
rdc = defaultdict(float)
rdc_f = 0
lk = defaultdict(float)
lk_flips = 0
flip_op = 0.0
phase = defaultdict(list)
for line in open(os.path.join(a.dir, 'logcat.txt'), errors='replace'):
    m = TS.match(line)
    if not m or secs(*m.groups()) < mark:
        continue
    if 'hakuX-pace' in line:
        for k in range(5):
            vb[k] += int(re.search(r' v%d=(\d+)' % k, line).group(1))
    elif '[rdc]' in line:
        f = int(re.search(r' f=(\d+)', line).group(1))
        rdc_f += f
        for site, n, us, pg, h in re.findall(r' (vtx|nv2a|tex|vga|code)=(\d+)/(\d+)/(\d+)/(\d+)', line):
            rdc[site + '_us'] += int(us)
            rdc[site + '_n'] += int(n)
        rdc['rdous'] += int(re.search(r'rdous=(\d+)', line).group(1))
    elif '[lock474]' in line:
        fl = int(re.search(r'flips=(\d+)', line).group(1))
        lk_flips += fl
        flip_op += float(re.search(r'flip_op_ms=([\d.]+)', line).group(1))
        for reg, n, ms in re.findall(r' r\d=(0x[0-9a-f]+):(\d+):([\d.]+)', line):
            lk[reg] += float(ms)
    elif 'hakuX-phase' in line or 'hakuX-cpu' in line or 'xemu-gpu' in line or 'xemu-vsync' in line:
        tag = 'phase' if 'hakuX-phase' in line else 'cpu' if 'hakuX-cpu' in line else 'gpu' if 'xemu-gpu' in line else 'vsync'
        for k, v in re.findall(r'([A-Za-z_]+):([\d.]+)', line.split('):', 1)[-1]):
            phase[tag + '.' + k].append(float(v))
n = sum(vb.values())
print('== %s' % os.path.basename(a.dir.rstrip('/')))
print('VBLANKs per flip: ' + ' '.join('v%d=%.2f' % (k, vb[k] / max(1, n)) for k in range(5)) + '  (n=%d)' % n)
if rdc_f:
    print('render-thread dirty walks, ms/frame: ' + ' '.join(
        '%s=%.2f' % (s, rdc[s + '_us'] / 1000 / rdc_f) for s in ('vtx', 'nv2a', 'tex', 'vga', 'code')) +
        '  vtx walks/frame=%.0f' % (rdc['vtx_n'] / rdc_f))
if lk_flips:
    print('vCPU pgraph.lock wait, ms/frame by reg: ' + ' '.join(
        '%s=%.2f' % (r, ms / lk_flips) for r, ms in sorted(lk.items(), key=lambda x: -x[1])[:5]) +
        '  flip_op=%.2f' % (flip_op / lk_flips))
for k in sorted(phase):
    print('  %-22s median %.2f' % (k, statistics.median(phase[k])))
