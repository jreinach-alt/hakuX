#!/usr/bin/env python3
"""Pair EV and BV frames by seconds after `mark cinematic` (index.tsv and logcat share the device clock)
and write side-by-side sheets (EV left, BV right) for pairs within --tol seconds.

usage: evbv_pairs.py <EV dir> <BV dir> <out dir> [--tol 3]
"""
import argparse
import os
import re

from PIL import Image


def secs(hms):
    h, m, s = hms.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def frames(d):
    with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
        mark = None
        for line in f:
            if 'mark cinematic' in line:
                mark = secs(line.split()[1])
                break
    out = []
    with open(os.path.join(d, 'frames', 'index.tsv')) as f:
        for line in f:
            p = line.split()
            if len(p) >= 2 and re.match(r'\d+:\d+:\d+', p[1]):
                out.append((secs(p[1]) - mark, os.path.join(d, 'frames', p[0])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ev')
    ap.add_argument('bv')
    ap.add_argument('out')
    ap.add_argument('--tol', type=float, default=3.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ev, bv = frames(a.ev), frames(a.bv)
    print('EV t-mark:', ' '.join('%.0f' % t for t, _ in ev))
    print('BV t-mark:', ' '.join('%.0f' % t for t, _ in bv))
    for t, p in ev:
        best = min(bv, key=lambda x: abs(x[0] - t))
        if abs(best[0] - t) > a.tol:
            continue
        l, r = Image.open(p).convert('RGB'), Image.open(best[1]).convert('RGB')
        w = 640
        l = l.resize((w, int(l.height * w / l.width)))
        r = r.resize((w, int(r.height * w / r.width)))
        sheet = Image.new('RGB', (2 * w + 8, max(l.height, r.height)), (255, 0, 255))
        sheet.paste(l, (0, 0))
        sheet.paste(r, (w + 8, 0))
        name = os.path.join(a.out, 'pair_ev%+04.0f_bv%+04.0f.png' % (t, best[0]))
        sheet.save(name)
        print('%s  EV %s @ %.1f  BV %s @ %.1f' % (name, os.path.basename(p), t, os.path.basename(best[1]), best[0]))


if __name__ == '__main__':
    main()
