#!/usr/bin/env python3
"""Classify the W buffering depth-quad residual (#266) against the goldens.

    python3 docs/lanes/wbufdepth24/classify.py RESULT_DIR [RUN]
            [--goldens /home/justin/goldens/results] [--geom FloorQuad,...]

For every Floor/Wall/Roof quad capture pair (colour + `_ZB`) it reports:

  colour  diff    px differing in the colour capture (any channel)
          miss    px where the capture shows the clear colour 0x251135 and the
                  golden does not -- the quad was not drawn there
          miss@S  of those, px where the golden's depth word is saturated
                  (0xFFFFFF, 0xFFFF for Z16) -- mechanism A's footprint
          extra   px drawn in the capture where the golden shows the clear

  depth   wdiff   px whose decoded depth WORD differs (the scorer counts
                  channels, and a +2 that carries out of the low byte reads
                  as a 254 channel step -- words are the honest unit)
          dmode   the most common (ours - gold) word delta, and its count
          sat     px the golden holds at the saturated word

`_ZB` encoding, read off the golden labels (`Z=0xFFE9AD` at (159,160) is
RGBA (0xE9, 0xAD, 0, 0xFF)): Z24S8 -> word = A<<16 | R<<8 | G. Z16 is read
as R<<8 | G, which is only good for equality; see `gsat` below.
"""
import argparse
import collections
import os
import sys

import numpy as np
from PIL import Image

BG = np.array([0x25, 0x11, 0x35])


def load(p):
    return np.asarray(Image.open(p).convert("RGBA")).astype(np.int64)


def word(img, bits):
    if bits == 24:
        return (img[..., 3] << 16) | (img[..., 0] << 8) | img[..., 1]
    return (img[..., 0] << 8) | img[..., 1]


def bits_of(test):
    return 24 if "24" in test.split("_")[0] else 16


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("result")
    ap.add_argument("run", nargs="?", default="1")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    ap.add_argument("--geom", default="FloorQuad,WallQuad,RoofQuad")
    ap.add_argument("--fmt", default="")
    a = ap.parse_args()
    cap = os.path.join(a.result, "captures" + a.run)
    gold = os.path.join(a.goldens, "W_buffering")
    geoms = a.geom.split(",")
    fmts = a.fmt.split(",") if a.fmt else None
    tests = sorted(f[:-4] for f in os.listdir(gold)
                   if f.endswith(".png") and not f.endswith("_ZB.png")
                   and f.split("_")[1] in geoms
                   and (fmts is None or f.split("_")[0] in fmts))
    print("%-34s %7s %7s %7s %6s | %7s %8s %7s %7s" % (
        "test", "diff", "miss", "miss@S", "extra", "wdiff", "dmode", "n", "sat"))
    tot = collections.Counter()
    for t in tests:
        cp = os.path.join(cap, "W_buffering::%s.png" % t)
        zp = os.path.join(cap, "W_buffering::%s_ZB.png" % t)
        if not os.path.exists(cp) or not os.path.exists(zp):
            print("%-34s  (no capture)" % t)
            continue
        bits = bits_of(t)
        sat = 0xFFFFFF if bits == 24 else 0xFFFF
        g, c = load(os.path.join(gold, t + ".png")), load(cp)
        gz = word(load(os.path.join(gold, t + "_ZB.png")), bits)
        cz = word(load(zp), bits)
        diff = (np.abs(g[..., :3] - c[..., :3]).max(2) > 0)
        gbg = (g[..., :3] == BG).all(2)
        cbg = (c[..., :3] == BG).all(2)
        miss = cbg & ~gbg
        extra = gbg & ~cbg
        # Z16 `_ZB` is not a plain 16-bit word in these bytes (every pixel
        # of a saturated Z16 golden reads 0xFFFE here), so take the golden's
        # own ceiling as "saturated" rather than a decoded 0xFFFF.
        gsat = gz == (sat if bits == 24 else gz.max())
        wd = cz - gz
        wdiff = wd != 0
        mode, n = (collections.Counter(wd[wdiff].tolist()).most_common(1)
                   or [(0, 0)])[0]
        row = dict(diff=int(diff.sum()), miss=int(miss.sum()),
                   missS=int((miss & gsat).sum()), extra=int(extra.sum()),
                   wdiff=int(wdiff.sum()), sat=int(gsat.sum()))
        tot.update(row)
        print("%-34s %7d %7d %7d %6d | %7d %8d %7d %7d" % (
            t, row["diff"], row["miss"], row["missS"], row["extra"],
            row["wdiff"], mode, n, row["sat"]))
    print("%-34s %7d %7d %7d %6d | %7d %8s %7s %7d" % (
        "TOTAL", tot["diff"], tot["miss"], tot["missS"], tot["extra"],
        tot["wdiff"], "", "", tot["sat"]))


if __name__ == "__main__":
    sys.exit(main())
