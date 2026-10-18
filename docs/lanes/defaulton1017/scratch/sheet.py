#!/usr/bin/env python3
"""Contact sheet of route shots: one row per result dir, one column per shot label, 320x240 each.
usage: sheet.py <out.png> <first label> <last label> <result dir> [<result dir> ...]
Labels are the sNN prefix (s13 .. s17) or a route's unpadded dN (d1 .. d20); the out path should be outside
the repo."""
import os
import sys

from PIL import Image, ImageDraw

R = '/home/justin/hakux-work/dispatch/results'
out, pre, lo, hi = sys.argv[1], sys.argv[2][0], int(sys.argv[2][1:]), int(sys.argv[3][1:])
dirs = sys.argv[4:]


def is_shot(f, n):
    # route shots are HHMMSS-sNN-what.png, or HHMMSS-dN.png on routes that number without padding
    lab = f.split('-', 1)[1].rsplit('.', 1)[0]
    return lab.startswith('%s%02d-' % (pre, n)) or lab == '%s%d' % (pre, n)

W, H = 320, 240
cols = list(range(lo, hi + 1))
img = Image.new('RGB', (W * len(cols), (H + 16) * len(dirs)), 'black')
dr = ImageDraw.Draw(img)
for r, d in enumerate(dirs):
    p = d if d.startswith('/') else os.path.join(R, d)
    fs = sorted(os.listdir(os.path.join(p, 'route-frames')))
    for c, n in enumerate(cols):
        hit = [f for f in fs if is_shot(f, n)]
        y = r * (H + 16)
        dr.text((c * W + 4, y + 2), '%s %s%02d' % (os.path.basename(d)[-20:], pre, n), fill='white')
        if hit:
            img.paste(Image.open(os.path.join(p, 'route-frames', hit[0])).convert('RGB').resize((W, H)),
                      (c * W, y + 16))
img.save(out)
print(out, img.size)
