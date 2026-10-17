#!/usr/bin/env python3
"""Per meter window after mark cinematic: each named voice's volume register
(apumix bins, 1/64 dB per step; the MON_VP gain is the max over its bins),
its frames active (n of 7500), its metered level (apumeter top=), and level
minus register gain = the content's own RMS over the window.

usage: mixregs.py <result dir> [voices, default 65,85,86,87,88]
"""
import re
import sys

d = sys.argv[1]
voices = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else '65,85,86,87,88').split(',')]
mark = None
mix = {}     # w -> v -> (n, st, gain dB, bins)
meter = {}   # w -> (3d, 2d, top{})
TS = re.compile(r'^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+)')
wt = {}
for line in open(d + '/logcat.txt', errors='replace'):
    m = TS.match(line)
    t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None
    if 'hakuX-route' in line and 'mark cinematic' in line and mark is None:
        mark = t
    m = re.search(r'apumix w=(\d+) v=(\d+) n=(\d+) st=(\d+) mp=(\d+) bins=(\S+)', line)
    if m:
        w, v = int(m.group(1)), int(m.group(2))
        bins = {}
        for x in m.group(6).split(','):
            b, vol = x.split(':')
            bins[int(b)] = int(vol)
        live = [vol for vol in bins.values() if vol < 0xFFF]
        g = -min(live) / 64.0 if live else -200.0
        mix.setdefault(w, {})[v] = (int(m.group(3)), int(m.group(4)), g,
                                    ','.join('%d:%d' % kv for kv in bins.items() if kv[1] < 0xFFF))
        wt[w] = t
        continue
    m = re.search(r'apumeter w=(\d+) 3d=(\S+) 2d=(\S+) top=(\S*)', line)
    if m:
        top = {}
        for x in m.group(4).split(','):
            if ':' in x:
                v, lv = x.split(':')
                top[int(v)] = float(lv)
        meter[int(m.group(1))] = (float(m.group(2)), float(m.group(3)), top)
        wt.setdefault(int(m.group(1)), t)

print('mark', mark)
hdr = '| t-mark | w | 3d | 2d | ' + ' | '.join('v%d n/gain/lvl/content' % v for v in voices) + ' |'
print(hdr)
print('|' + '---|' * (4 + len(voices)))
for w in sorted(set(mix) | set(meter)):
    t = wt.get(w)
    if mark is None or t is None or t < mark:
        continue
    d3, d2, top = meter.get(w, (None, None, {}))
    cells = []
    for v in voices:
        n, st, g, bins = mix.get(w, {}).get(v, (0, 0, None, ''))
        lv = top.get(v)
        if g is None:
            cells.append('-' if lv is None else 'lvl %.1f' % lv)
            continue
        cells.append('%d/%.1f/%s/%s%s' % (n, g, '%.1f' % lv if lv is not None else '.',
                                          '%.1f' % (lv - g) if lv is not None else '.',
                                          ' st' if st else ''))
    print('| %.0f | %d | %s | %s | %s |' % (t - mark, w, d3, d2, ' | '.join(cells)))

# speech while it runs: its window level scaled to its active frames, against
# the music voices' summed window level (they run the whole window)
import math
import statistics
SP, MUS = 65, (85, 86, 87, 88)
rows = []
for w in sorted(meter):
    t = wt.get(w)
    if mark is None or t is None or t < mark:
        continue
    top = meter[w][2]
    n = mix.get(w, {}).get(SP, (0,))[0]
    if SP not in top or n <= 0:
        continue
    sa = top[SP] + 10 * math.log10(7500.0 / n)
    e = sum(10 ** (top[v] / 10) for v in MUS if v in top)
    m = 10 * math.log10(e) if e > 0 else -200.0
    rows.append((t - mark, w, n, top[SP], sa, m, sa - m))
print('\n| t-mark | w | n | S win | S running | M | S running - M |')
print('|---|---|---|---|---|---|---|')
for r in rows:
    print('| %.0f | %d | %d | %.1f | %.1f | %.1f | %.1f |' % r)
for lab, sel in (('t-mark < 130', [r for r in rows if r[0] < 130]),
                 ('t-mark >= 130', [r for r in rows if r[0] >= 130])):
    if sel:
        print('%s: %d windows, median S running - M %.1f dB (min %.1f, max %.1f)' %
              (lab, len(sel), statistics.median(r[6] for r in sel),
               min(r[6] for r in sel), max(r[6] for r in sel)))
first = {}
for w in sorted(mix):
    for v in voices:
        if v in mix[w] and v not in first:
            first[v] = mix[w][v][3]
print('\nbins at first sight:', '; '.join('v%d %s' % kv for kv in sorted(first.items())))
