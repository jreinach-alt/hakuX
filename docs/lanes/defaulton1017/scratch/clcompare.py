#!/usr/bin/env python3
"""CLF against CLC (Conker, no route, frames every 5 s): each run's frames on its own launch clock
(`surface_scale=` in logcat, the device clock frames/index.tsv is on), paired by nearest offset, with a mean
absolute difference on 64x48 grey; the `[fldcw1018] n=` lines and the pace frame count on the same clock; and
one contact sheet of both runs' frames, offset-aligned (out path outside the repo).
usage: clcompare.py <CLF dir> <CLC dir> <sheet.png>"""
import os
import re
import sys

from PIL import Image, ImageDraw

R = '/home/justin/hakux-work/dispatch/results'
T = re.compile(r'^\d\d-\d\d (\d\d):(\d\d):(\d\d(?:\.\d+)?) ')


def sec(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def read(d):
    p = d if d.startswith('/') else os.path.join(R, d)
    anchor, fl, pace = None, [], []
    for line in open(os.path.join(p, 'logcat.txt'), errors='replace'):
        m = T.match(line)
        if not m:
            continue
        t = sec(*m.groups())
        if anchor is None and 'surface_scale=' in line:
            anchor = t
        if '[fldcw1018] n=' in line:
            fl.append((t, line.split('[fldcw1018] ', 1)[1].strip()))
        mp = re.search(r'hakuX-pace\(\s*\d+\): f=(\d+)', line)
        if mp:
            pace.append((t, int(mp.group(1))))
    frames = []
    for row in open(os.path.join(p, 'frames', 'index.tsv')):
        f, hms = row.split()
        frames.append((sec(*hms.split(':')) - anchor, os.path.join(p, 'frames', f)))
    return dict(name=os.path.basename(p), anchor=anchor, frames=frames,
                fl=[(t - anchor, s) for t, s in fl], pace=[(t - anchor, n) for t, n in pace])


def small(f):
    return list(Image.open(f).convert('L').resize((64, 48)).getdata())


def mad(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


a, b, out = read(sys.argv[1]), read(sys.argv[2]), sys.argv[3]
for r in (a, b):
    print('%s: %d frames, %.0f..%.0f s after launch' % (r['name'], len(r['frames']), r['frames'][0][0],
                                                      r['frames'][-1][0]))
    for t, s in r['fl']:
        print('   +%.0f s  %s' % (t, s))
    for mark in (60, 120, 180, 240, 290):
        n = [f for t, f in r['pace'] if t <= mark]
        print('   pace frames by +%d s: %s' % (mark, n[-1] if n else '-'))
print('\npaired by offset (CLF frame, CLC frame nearest in time): MAD')
pairs = []
for ta, fa in a['frames']:
    tb, fb = min(b['frames'], key=lambda x: abs(x[0] - ta))
    pairs.append((ta, fa, tb, fb, mad(small(fa), small(fb))))
    print('  +%5.0f %s  +%5.0f %s  %5.1f' % (ta, os.path.basename(fa), tb, os.path.basename(fb), pairs[-1][4]))

W, H, COLS = 160, 120, 10
rows = (len(pairs) + COLS - 1) // COLS
img = Image.new('RGB', (W * COLS, rows * (2 * H + 14)), 'black')
dr = ImageDraw.Draw(img)
for i, (ta, fa, tb, fb, m) in enumerate(pairs):
    x, y = (i % COLS) * W, (i // COLS) * (2 * H + 14)
    img.paste(Image.open(fa).convert('RGB').resize((W, H)), (x, y))
    img.paste(Image.open(fb).convert('RGB').resize((W, H)), (x, y + H))
    dr.text((x + 2, y + 2 * H), '+%.0f/%.0f %.0f' % (ta, tb, m), fill='yellow')
img.save(out)
print(out, img.size, '(top of each pair CLF, bottom CLC)')
