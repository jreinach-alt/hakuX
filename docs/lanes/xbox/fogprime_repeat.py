#!/usr/bin/env python3
"""Score the fogprime repeat against the first run (fogprime-repeat-run.md).

    fogprime_repeat.py <run 1 root> <run 2 root> [--goldens DIR] [--hakux]

Roots are laid out as fogprime_score.py accepts: a console `console/`
directory or a dispatcher `captures1/`. --hakux scores the emulator legs
(E4, E5) instead of the silicon ones (R1-R4). Writes nothing.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fogprime_slots as S  # noqa: E402

FF = ["A0far_FF", "A1mid_FF", "A2near_FF", "A3farLabel_FF", "A4near_FF"]
VS = ["A0far_VS", "A1mid_VS", "A2near_VS", "A3farLabel_VS", "A4pad_VS", "A4radial_VS"]
EDGE = {"A0far_VS": 0.85, "A3farLabel_VS": 0.85}  # the 31/32 rounding edge; others 0.99
R4 = [("A0far_VS", "A3farLabel_VS", 3), ("A2near_VS", "A4pad_VS", 3), ("A4pad_VS", "A4radial_VS", 2)]
RADIAL = ["FogGen_VS-%s-radial" % m for m in S.G.MODES]


def pixels(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def same(a, b):
    return a is not None and b is not None and np.array_equal(pixels(a), pixels(b))


def patterns(root, name):
    p = S.find(root, "Fog_radial_priming", name)
    if not p:
        return None
    f = S.factor_image(p)
    return [S.corner_pattern(f, i) for i in range(374)]


def best_shift(pa, pb):
    """(s, fraction) with pb[i + s] == pa[i]; None if pa is uniform."""
    if pa is None or pb is None or len(set(pa)) == 1:
        return None
    fr = [sum(1 for i in range(368) if pa[i] == pb[i + s]) / 368.0 for s in range(6)]
    s = max(range(6), key=lambda k: fr[k])
    return s, fr[s]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run1")
    ap.add_argument("run2")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    ap.add_argument("--hakux", action="store_true")
    a = ap.parse_args()
    ok = {}

    gdir = os.path.join(a.goldens, "Fog_gen")
    names = sorted(f[:-4] for f in os.listdir(gdir) if f.endswith(".png"))
    ident, bad = 0, []
    for n in names:
        p, g = S.find(a.run2, "Fog_gen", n), os.path.join(gdir, n + ".png")
        if same(p, g):
            ident += 1
        else:
            bad.append((n, "missing" if p is None else int((np.abs(pixels(p) - pixels(g)).max(axis=2) > 0).sum())))
    radial_ok = all(n not in dict(bad) for n in RADIAL)
    print("Fog gen against the goldens: %d of %d identical; the six VS radial %s"
          % (ident, len(names), "all identical" if radial_ok else "NOT all identical"))
    for n, d in bad[:12]:
        print("   %-34s %s" % (n, d if d == "missing" else "%d px" % d))
    if a.hakux:
        ok["E4 six VS radial = goldens"] = radial_ok
        e5 = True
        for n in FF + VS:
            s1, s2 = S.find(a.run1, "Fog_radial_priming", n), S.find(a.run2, "Fog_radial_priming", n)
            e = same(s1, s2)
            e5 = e5 and e
            print("   E5 %-14s run 1 vs run 2: %s" % (n, "identical" if e else "DIFFERS"))
        ok["E5 priming captures = run 1"] = e5
    else:
        ok["R1 all Fog gen = goldens"] = ident == len(names) and not bad
        r2 = True
        for n in FF:
            e = same(S.find(a.run1, "Fog_radial_priming", n), S.find(a.run2, "Fog_radial_priming", n))
            r2 = r2 and e
            print("   R2 %-14s run 1 vs run 2: %s" % (n, "identical" if e else "DIFFERS"))
        ok["R2 FF captures = run 1"] = r2
        r3 = True
        for n in VS:
            bs = best_shift(patterns(a.run1, n), patterns(a.run2, n))
            need = EDGE.get(n, 0.99)
            good = bs is not None and bs[1] >= need
            r3 = r3 and good
            print("   R3 %-14s run 1 -> run 2: %s (needs >= %.2f)%s" % (
                n, "no shift readable" if bs is None else "s=%d on %.3f of quads" % bs, need,
                "" if good else "  <- FAILS"))
        ok["R3 values reproduce up to a shift"] = r3
        r4 = True
        for x, y, want in R4:
            bs = best_shift(patterns(a.run2, x), patterns(a.run2, y))
            need = min(EDGE.get(x, 0.99), EDGE.get(y, 0.99))
            good = bs is not None and bs[0] == want and bs[1] >= need
            r4 = r4 and good
            print("   R4 %-13s -> %-13s %s, run 1 had %d%s" % (
                x, y, "no shift readable" if bs is None else "s=%d on %.3f" % bs, want, "" if good else "  <- FAILS"))
        ok["R4 relative phases = run 1's"] = r4
    for k, v in ok.items():
        print("%-36s %s" % (k, "holds" if v else "FAILS"))
    return 0 if all(ok.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
