#!/usr/bin/env python3
"""The Points leg: which of the 12 points survive our AA path, now and fixed.

Screen x of each CreateLines vertex under the XDK default camera (eye z=-7,
FOV pi/4, aspect 4/3, D3D viewport 640x480, VPOFF 0.53125), truncated to 1/16
as vsh.c's roundScreenCoords does.  f = frac(x).

A 1-px Vulkan point centred at physical c covers column floor(c); the resolve
keeps column 2x+1 only.
  now   c = 2x_s          -> kept iff f in [0.5, 1)
  fixed c = 2x_s + 0.5    -> kept iff f in [0.25, 0.75)
The "now" column is checked against our Points-ls capture: a point is present
iff its golden pixel (from the plain golden) is non-background there.
"""
import math
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/cloud-286')
import decompose286 as D  # noqa: E402

L, R, T, B, ZF, ZB = -2.75, 2.75, 1.75, -1.75, 1.0, 5.0
PTS = [(L, T, ZF), (R, T, ZF), (-2, 1, ZF), (2, 0, ZB), (1.5, .5, ZB),
       (-1.5, .75, ZB), (R, .25, ZF), (1.75, 1.25, ZF), (L, 1., ZF),
       (L, -1., ZF), (L, B, ZB), (R, B, ZB)]
YS = 1 / math.tan(math.pi / 8)
XS = YS / (640 / 480)


def screen(x, y, z):
    w = z + 7.0
    sx = (XS * x / w + 1) * 320 + 0.53125
    sy = (1 - YS * y / w) * 240 + 0.53125
    return math.trunc(sx * 16) / 16, math.trunc(sy * 16) / 16


def main():
    gp = D.ld(D.GOLD + 'Points.png')
    ox = D.ld(D.OURS + 'Points-ls.png')
    bg = gp[470, 5, :3]
    print('| pt | screen x | screen y | f | golden px | ours now | model now | model fixed |')
    print('|---|---:|---:|---:|---|---|---|---|')
    agree = kept_fixed = 0
    for i, v in enumerate(PTS):
        sx, sy = screen(*v)
        f = sx - math.floor(sx)
        # find the golden point pixel near the prediction
        x0, y0 = int(sx), int(sy)
        win = gp[y0 - 2:y0 + 3, x0 - 2:x0 + 3, :3]
        hit = np.argwhere(np.abs(win - bg).max(2) > 8)
        if len(hit):
            yy, xx = hit[0] + [y0 - 2, x0 - 2]
            gpix = '(%d,%d)' % (xx, yy)
            present = bool(np.abs(ox[yy, xx, :3] - bg).max() > 8)
        else:
            gpix, present = 'none', None
        now = f >= 0.5
        fixed = 0.25 <= f < 0.75
        agree += present == now
        kept_fixed += fixed
        print('| %d | %.4f | %.4f | %.4f | %s | %s | %s | %s |'
              % (i, sx, sy, f, gpix, present, now, fixed))
    print('model-now agrees with our capture on %d/12; fixed keeps %d/12'
          % (agree, kept_fixed))


if __name__ == '__main__':
    main()
