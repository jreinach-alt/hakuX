"""Score vertex-depth models on DBFF z24 FZn goldens only (training set)."""
import itertools
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from dbff import render, zeta_word, GOLD  # noqa: E402

NAMES = ["z24_Cn_FZn_Mffffff_ZB", "z24_Cy_FZn_Mffffff_ZB"]
gold = {n: zeta_word(os.path.join(GOLD, n + ".png")) for n in NAMES}


def score(m):
    ex = ab = tot = 0
    for n in NAMES:
        cutoff = int(n.split("_M")[1].split("_")[0], 16)
        z = render(m, cutoff)
        d = gold[n] - z
        drawn = z != cutoff
        ex += int((d[drawn] == 0).sum())
        ab += int(np.abs(d[drawn]).sum())
        tot += int(drawn.sum())
    return ex, ab, tot


if __name__ == "__main__":
    res = []
    for mul, add, fin in itertools.product(['rne', 'rtz'], ['rne', 'rtz'], ['rne', 'rtz', 'exact']):
        cands = [dict(div='div')] + [dict(div='rcp', rcp=r, rbits=b)
                                     for r in ('rne', 'rtz', 'exact') for b in (22, 23, 24, 25)]
        for c in cands:
            m = dict(mul=mul, add=add, fin=fin, **c)
            ex, ab, tot = score(m)
            res.append((ex, ab, tot, m))
    res.sort(key=lambda r: (-r[0], r[1]))
    for ex, ab, tot, m in res[:25]:
        print("%7d/%d  sum|d|=%7d  %s" % (ex, tot, ab, m))
    print('...')
    for ex, ab, tot, m in res[-3:]:
        print("%7d/%d  sum|d|=%7d  %s" % (ex, tot, ab, m))
