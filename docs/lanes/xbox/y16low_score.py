#!/usr/bin/env python3
"""Score the #10 low-byte run (y16low-run.md) on one captures root.

    y16low_score.py <captures root> [--goldens /home/justin/goldens/results] [--hakux]

<captures root> is a console run's `console/` (Bump_map/Test.png) or a
dispatcher result's `captures1/` (Bump_map::Test.png). Pixel counts compare
RGB outside the printed label rows 20..44. Writes nothing.

  C1  BumpMap_Y16 and BumpMap_Y8 equal their goldens
  C0  BumpMap_Y16_patchSame equals the same run's BumpMap_Y16 (rewriting each
      low byte with its own high byte is inert)
  Z   BumpMap_Y16_zero differs from BumpMap_Y16 by >= 10,000 px (the GPU saw
      the patched texels; otherwise every variant could be a stale texture)
  S   BumpMap_Y8's seam band has no single-colour rows in any quad (the band
      samples the checkerboard, so a flip there is visible)
  M   BumpMap_Y16_lo00 against BumpMap_Y8: HIGH if <= 2,000 px (the offsets
      ignore the low byte), LOW if >= 10,000 px (a low byte feeds an offset),
      else X
M is scored only when C1, C0, Z and S hold. --hakux reports the counts
without C1 (hakuX differs from the goldens by #10's own residual).
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

QUADS = [(66, 146), (66, 326), (246, 146), (246, 326)]   # DrawRectangles: top, left of the 168 px quads
LABEL = (20, 45)
HIGH, LOW = 2000, 10000


def find(root, name):
    for p in (os.path.join(root, "Bump_map", name + ".png"), os.path.join(root, "Bump_map::%s.png" % name)):
        if os.path.exists(p):
            return p
    return None


def rgb(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def px(a, b):
    d = np.abs(a - b).max(axis=2) > 0
    d[LABEL[0]:LABEL[1], :] = False
    return int(d.sum())


def striped_rows(a):
    out = []
    for top, left in QUADS:
        band = a[top:top + 168, left + 44:left + 103]
        out.append(sum(1 for r in band if len({tuple(p) for p in r.tolist()}) == 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    ap.add_argument("--hakux", action="store_true")
    a = ap.parse_args()
    names = ["BumpMap_Y16", "BumpMap_Y8", "BumpMap_Y16_patchSame", "BumpMap_Y16_zero", "BumpMap_Y16_lo00", "BumpMap_Y16_lo80"]
    missing = [n for n in names if not find(a.root, n)]
    if missing:
        print("MISSING: %s" % ", ".join(missing))
        return 2
    cap = {n: rgb(find(a.root, n)) for n in names}
    gold = lambda n: rgb(os.path.join(a.goldens, "Bump_map", n + ".png"))
    c1 = all(np.array_equal(cap[n], gold(n)) for n in ("BumpMap_Y16", "BumpMap_Y8"))
    c0 = np.array_equal(cap["BumpMap_Y16_patchSame"], cap["BumpMap_Y16"])
    z = px(cap["BumpMap_Y16_zero"], cap["BumpMap_Y16"])
    s = striped_rows(cap["BumpMap_Y8"])
    m = px(cap["BumpMap_Y16_lo00"], cap["BumpMap_Y8"])
    print("C1 controls equal their goldens: %s" % ("holds" if c1 else "FAILS"))
    print("C0 patchSame equals this run's BumpMap_Y16: %s" % ("holds" if c0 else "FAILS"))
    print("Z  zero vs BumpMap_Y16: %d px -> %s" % (z, "holds" if z >= LOW else "FAILS (the patch may not reach the GPU)"))
    print("S  Y8 seam-band single-colour rows per quad: %s -> %s" % (s, "holds" if max(s) == 0 else "FAILS"))
    for x, y in (("BumpMap_Y16", "BumpMap_Y8"), ("BumpMap_Y16_lo00", "BumpMap_Y8"), ("BumpMap_Y16_lo80", "BumpMap_Y8"),
                 ("BumpMap_Y16_lo80", "BumpMap_Y16_lo00"), ("BumpMap_Y16_lo00", "BumpMap_Y16")):
        print("   %-17s vs %-17s %6d px" % (x, y, px(cap[x], cap[y])))
    verdict = "HIGH" if m <= HIGH else ("LOW" if m >= LOW else "X")
    gates = (c1 or a.hakux) and c0 and z >= LOW and max(s) == 0
    if gates:
        print("M  lo00 vs Y8: %d px -> %s" % (m, verdict))
    else:
        print("M  not scored: a gate failed")
    return 0 if gates else 1


if __name__ == "__main__":
    sys.exit(main())
