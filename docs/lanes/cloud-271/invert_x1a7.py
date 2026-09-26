#!/usr/bin/env python3
"""Read X1A7's rule off the DstAlpha goldens by inversion, not by fitting.

    invert_x1a7.py [--goldens DIR]

derive_x1a7.py (lane x1a7271) enumerates candidate stages and keeps the ones
that fit.  This script assumes none of them.  Per swatch it reads two flat
golden halves and inverts them:

  bottom RGB = the blend result 255*f with dfactor ZERO, so it IS the 8-bit
               factor the blend unit used: Ad (DstAlpha) or 255-Ad (1-DstAlpha).
  top alpha  = s*s/255 + 255 - s (SRC_ALPHA over an opaque grey framebuffer),
               where s is the byte the texture unit returned for the stored
               swatch alpha.  Alpha alone is two-valued in s; the top RGB,
               linear in s over the 0x55 grey, picks the branch.  Where
               8-bit rounding leaves several s, all are listed.

It then prints, per background byte bg the test drew with blend off:
  Ad        the blend unit's read of the stored background alpha, next to
            bit-replicating bg>>1 (identity would read 0x80 as 128, not 129)
  s, s>>7   the sampled candidates and their top bit, next to X (Z=0, O=1)
  want      (X<<7)|(round8(0x22*f)>>1), the rule's sampled byte
so each claim is a column that holds on every row or visibly does not.
"""
import argparse
import os

import numpy as np
from PIL import Image

BGS = (0x00, 0x40, 0x80, 0xFF)
CAPTURES = ('DstAlpha_XA_Z1A7RGB8', 'DstAlpha_XA_O1A7RGB8',
            '1-DstAlpha_XA_Z1A7RGB8', '1-DstAlpha_XA_O1A7RGB8')
MARGIN, TOP, SP, RP, S = 32, 92, 144, 160, 128


def flat(img, y, x):
    v = np.unique(img[y:y + S // 2, x:x + S].reshape(-1, 4), axis=0)
    assert len(v) == 1, 'half not flat'
    return tuple(int(c) for c in v[0])


def rnd(x):
    return int(np.floor(x + 0.5))


def invert_top(top, rgb8):
    """Every s whose composite reproduces the top half in RGB and alpha.

    Alpha alone is quadratic in s and two-valued; the RGB composite over the
    0x55 grey is linear in s and picks the branch.
    """
    return [s for s in range(256)
            if rnd(s * s / 255 + 255 * (255 - s) / 255) == top[3]
            and rnd(rgb8 * s / 255 + 0x55 * (255 - s) / 255) == top[0]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--goldens', default=os.path.expanduser('~/goldens/results'))
    a = ap.parse_args()
    bad = unique = 0
    print(f"{'capture':26} {'bg':>4} {'Ad':>4} {'rep(bg>>1)':>10} "
          f"{'s candidates':>14} {'s>>7':>4} X {'want':>5} {'0x22*f/2':>8}")
    for name in CAPTURES:
        g = np.asarray(Image.open(os.path.join(
            a.goldens, 'Blend_surface', name + '.png')).convert('RGBA')).astype(int)
        x_bit = 1 if '_O1A7' in name else 0
        one_minus = name.startswith('1-')
        for i in range(8):
            l, t = MARGIN + SP * (i % 4), TOP + RP * (i // 4)
            top, bot = flat(g, t, l), flat(g, t + S // 2, l)
            bg = BGS[i % 4]
            fac = bot[0]
            ad = 255 - fac if one_minus else fac
            v = bg >> 1
            rep = (v << 1) | (v >> 6)
            ss = invert_top(top, fac)
            half_sw = 0x22 * fac / 255 / 2
            want = (x_bit << 7) | (rnd(0x22 * fac / 255) >> 1)
            ok = (ad == rep and ss and all(s >> 7 == x_bit for s in ss)
                  and want in ss)
            bad += not ok
            unique += len(ss) == 1
            print(f"{name:26} {bg:#04x} {ad:4} {rep:10} {str(ss):>14} "
                  f"{','.join(sorted({str(s >> 7) for s in ss})):>4} {x_bit} "
                  f"{want:5} {half_sw:8.2f}"
                  f"{'' if ok else '   <-- breaks a claim'}")
    print(f'\n{bad} of 32 swatches break "Ad == replicate(bg>>1)", '
          f'"every candidate s has s>>7 == X" or "(X<<7)|(round8(0x22f)>>1) '
          f'is a candidate"; s is pinned uniquely on {unique} of 32')


if __name__ == '__main__':
    main()
