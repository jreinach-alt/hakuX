#!/usr/bin/env python3
"""Signed histogram of ours - golden over the |d| <= 2 wash pixels, per channel.

A symmetric +-1 wash is a rounding floor; a one-signed wash is a bias with a
mechanism.  usage: wash_sign.py <capture.png> <golden.png> [...pairs]
"""
import sys

import numpy as np
from PIL import Image


def main():
    args = sys.argv[1:]
    for cap, gold in zip(args[0::2], args[1::2]):
        a = np.asarray(Image.open(cap).convert('RGB')).astype(int)
        b = np.asarray(Image.open(gold).convert('RGB')).astype(int)
        d = a - b
        wash = (np.abs(d).max(2) <= 2) & (np.abs(d).max(2) > 0)
        print(cap.rsplit('::', 1)[-1], 'wash px', int(wash.sum()))
        for ch, name in enumerate('RGB'):
            v = d[..., ch][wash]
            h = {k: int((v == k).sum()) for k in (-2, -1, 0, 1, 2)}
            print('  %s %s' % (name, h))


if __name__ == '__main__':
    main()
