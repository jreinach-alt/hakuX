#!/usr/bin/env python3
"""Score the radial-fog priming run against PR #179's prediction.

    fogprime_score.py <captures root> [--goldens /home/justin/goldens/results]

<captures root> holds `Fog_radial_priming/` and `Fog_gen/` (a console run's
layout) or flat `Suite::Test.png` files (a dispatcher result's captures1/).

The quantity (prediction section 2) is the 8-bit fog factor over each VS
capture's drawn region: the blue channel where red + blue == 255 and green == 0.
Gates are the prediction's own: V0 A0 in 29.63..35.20; V1 the FF captures
bit-identical outside the label band (A3 excepted); V2 each VS region is
exactly 181,016 px of one colour; V3 the six FogGen_VS-*-radial reproduce
their goldens. Writes nothing.

The model line is printed only when V0 and V2 hold. The console run of
2026-09-25 failed V2, and this file's first version still printed S=True from
each mixture's commonest colour; that line is not a result.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

VS = ["A0far_VS", "A1mid_VS", "A2near_VS", "A3farLabel_VS", "A4pad_VS", "A4radial_VS"]
FF = ["A0far_FF", "A1mid_FF", "A2near_FF", "A4near_FF"]  # V1 set; A3farLabel_FF moves its label on purpose
RADIAL = ["FogGen_VS-%s-radial" % m for m in ("exp", "exp2", "exp2_abs", "exp_abs", "linear", "linear_abs")]
REGION_PX = 181016
WINDOWS = {  # prediction section 2: (S, S-first, H)
    "A0far_VS": ((30.25, 32.11), (249.48, 252.21), (29.63, 35.20)),
    "A1mid_VS": ((100.64, 101.85), (99.98, 101.33), (29.63, 35.20)),
    "A2near_VS": ((223.95, 226.92), (222.32, 225.36), (29.63, 35.20)),
    "A3farLabel_VS": ((30.25, 32.11), (249.48, 252.21), (29.63, 35.20)),
    "A4radial_VS": ((223.95, 226.92), (222.32, 225.36), (29.63, 35.20)),
}
LABEL_BAND_ROW0 = (20, 45)  # pbkit text row 0: y = 25 .. 40


def find(root, suite_dir, name):
    for p in (os.path.join(root, suite_dir, name + ".png"),
              os.path.join(root, "%s::%s.png" % (suite_dir, name))):
        if os.path.exists(p):
            return p
    return None


def rgb(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.int32)


def fog_factor(p):
    a = rgb(p)
    m = (a[..., 0] + a[..., 2] == 255) & (a[..., 1] == 0)
    vals, counts = np.unique(a[..., 2][m], return_counts=True)
    return int(m.sum()), dict(zip(vals.tolist(), counts.tolist()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    a = ap.parse_args()
    f8 = {}
    print("VS captures: drawn px, colours (f8: px)")
    v2 = True
    for n in VS:
        p = find(a.root, "Fog_radial_priming", n)
        if not p:
            print("  %-15s MISSING" % n)
            v2 = False
            continue
        px, vals = fog_factor(p)
        top = sorted(vals.items(), key=lambda kv: -kv[1])[:4]
        f8[n] = top[0][0] if top else None
        single = px == REGION_PX and len(vals) == 1
        v2 = v2 and single
        print("  %-15s %7d px, %d colour(s): %s%s" % (n, px, len(vals), top, "" if single else "   <- V2 FAILS"))
    a0 = f8.get("A0far_VS")
    v0 = a0 is not None and 29.63 <= a0 <= 35.20
    print("V0 (A0 in 29.63..35.20): %s (A0 f8 = %s)" % ("holds" if v0 else "FAILS -- session void", a0))
    # V1
    imgs = {n: find(a.root, "Fog_radial_priming", n) for n in FF}
    v1 = all(imgs.values())
    if v1:
        ref = rgb(imgs[FF[0]])
        keep = np.ones(ref.shape[:2], bool)
        keep[LABEL_BAND_ROW0[0]:LABEL_BAND_ROW0[1], :] = False
        for n in FF[1:]:
            d = int((np.abs(rgb(imgs[n]) - ref).max(axis=2) > 0)[keep].sum())
            print("  V1 %s vs %s outside the label band: %d px differ" % (n, FF[0], d))
            v1 = v1 and d == 0
    print("V1 (FF captures identical outside the label): %s" % ("holds" if v1 else "FAILS"))
    print("V2 (each VS region one colour, %d px): %s" % (REGION_PX, "holds" if v2 else "FAILS"))
    v3 = True
    for n in RADIAL:
        p = find(a.root, "Fog_gen", n)
        g = os.path.join(a.goldens, "Fog_gen", n + ".png")
        same = bool(p) and os.path.exists(g) and open(p, "rb").read() == open(g, "rb").read()
        if not same and p and os.path.exists(g):
            d = int((np.abs(rgb(p) - rgb(g)).max(axis=2) > 0).sum())
            print("  V3 %s differs from its golden by %d px" % (n, d))
        v3 = v3 and same
    print("V3 (six radial captures = goldens): %s" % ("holds" if v3 else "does not hold (see above)"))
    # Models (section 3)
    def inside(n, w):
        return n in f8 and f8[n] is not None and w[0] <= f8[n] <= w[1]
    s = all(inside(n, WINDOWS[n][0]) for n in ("A0far_VS", "A1mid_VS", "A2near_VS")) and \
        f8.get("A3farLabel_VS") == f8.get("A0far_VS") and f8.get("A4radial_VS") == f8.get("A2near_VS")
    sf = all(inside(n, WINDOWS[n][1]) for n in ("A0far_VS", "A1mid_VS", "A2near_VS")) and \
        f8.get("A3farLabel_VS") == f8.get("A0far_VS")
    t = len({f8.get(n) for n in ("A0far_VS", "A1mid_VS", "A2near_VS", "A4radial_VS")}) == 1 and \
        f8.get("A3farLabel_VS") != f8.get("A0far_VS")
    h = all(inside(n, WINDOWS[n][2]) for n in WINDOWS) and v1 and v2
    print("f8 (commonest colour): " + ", ".join("%s=%s" % (n, f8.get(n)) for n in VS))
    # Section 6: V0 voids the session; V2 voids the single-value reading every
    # model row in section 3 is written in. Neither prints a model verdict:
    # the commonest colour of a mixture is not "the" f8 (found by mutation test).
    if not v0:
        print("models: not scored -- V0 fails, the session is void")
    elif not v2:
        print("models: not scored -- V2 fails, which voids the single-value reading (section 6)")
    else:
        print("models confirmed: S=%s S-first=%s T=%s H=%s%s" % (s, sf, t, h, "" if (s or sf or t or h) else "  -> X (report the values)"))
    return 0 if (v0 and v1 and v2) else 1


if __name__ == "__main__":
    sys.exit(main())
