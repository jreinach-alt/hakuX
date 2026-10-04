#!/usr/bin/env python3
"""badgood.py <result-copy> lo hi [fpsbar]
For every always-on 2 s line in [lo, hi) s after the mark, label it by the
hakuX-pace window covering its timestamp (bad: fps < bar), then print the
median of every numeric key=value field, bad vs good, sorted by ratio.
"""
import re, sys, os, bisect, statistics

d, lo, hi = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
bar = float(sys.argv[4]) if len(sys.argv) > 4 else 28.5


def t(s):
    h, mi, se = s.split(':')
    return int(h) * 3600 + int(mi) * 60 + float(se)


runlog = open(os.path.join(d, 'run.log'), errors='replace').read()
mark = t(re.search(r'ROUTE (\d+:\d+:\d+\.\d+) mark gameplay', runlog).group(1))
TS = re.compile(r'^\d+-\d+ (\d+:\d+:\d+\.\d+) ')
KV = re.compile(r'(?<![\w/])([A-Za-z_][\w%]*)=(-?[\d.]+)(?![\d.]*[/:x])')
TAG = re.compile(r'(\[[a-z0-9]+\]|gfps=|vblphase|vbl n=|fifoskew|inval ev=|slow stores)')
pace = []  # (end_off, start_off, fps)
lines = []
for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
    m = TS.match(line)
    if not m:
        continue
    off = t(m.group(1)) - mark
    if 'hakuX-pace' in line:
        ms = float(re.search(r' ms=([\d.]+)', line).group(1))
        pace.append((off, off - ms / 1000.0, 60000.0 / ms))
        continue
    if off < lo - 30 or off > hi + 30:
        continue
    if 'hakuX-phase' in line or 'hakuX-cpu' in line or 'xemu-gpu' in line or 'xemu-work' in line:
        tag = 'phase' if 'hakuX-phase' in line else 'cpu' if 'hakuX-cpu' in line else 'gpu' if 'xemu-gpu' in line else 'work'
        lines.append((off, tag, line))
        continue
    tm = TAG.search(line)
    if tm and 'surf92' not in line:
        lines.append((off, tm.group(1), line))
ends = [p[0] for p in pace]
vals = {}
for off, tag, line in lines:
    if not (lo <= off < hi):
        continue
    i = bisect.bisect_left(ends, off)
    if i >= len(pace):
        continue
    bad = pace[i][2] < bar
    body = line.split('): ', 1)[-1]
    pairs = KV.findall(body)
    if tag in ('phase', 'cpu', 'gpu', 'work'):
        pairs = re.findall(r'([A-Za-z]+):(-?[\d.]+)', body)
    only = os.environ.get('ONLY')
    if only and not re.search(only, tag):
        continue
    for k, v in pairs:
        try:
            x = float(v)
        except ValueError:
            continue
        vals.setdefault((tag, k), ([], []))[0 if bad else 1].append(x)
rows = []
for (tag, k), (b, g) in vals.items():
    if len(b) < 3 or len(g) < 3:
        continue
    mb, mg = statistics.median(b), statistics.median(g)
    r = (mb + 1e-9) / (mg + 1e-9) if mg else float('inf') if mb else 1.0
    rows.append((r, tag, k, mb, mg, len(b), len(g)))
rows.sort(key=lambda x: -abs(__import__('math').log(max(1e-6, x[0]) if x[0] != float('inf') else 1e6)))
for r, tag, k, mb, mg, nb, ng in rows[:int(os.environ.get('N', '60'))]:
    print('%-12s %-14s bad=%12.1f good=%12.1f ratio=%7.2f (n %d/%d)' % (tag, k, mb, mg, r, nb, ng))
