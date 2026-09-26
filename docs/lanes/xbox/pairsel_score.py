#!/usr/bin/env python3
"""Score the #38 mechanism-2 selector run (pairsel-run.md) on one captures root.

    pairsel_score.py <captures root>

<captures root> is a console run's `console/` (Suite/Test.png) or a dispatcher
result's `captures1/` (Suite::Test.png). Writes nothing.

Every PairSel test is Alpha func's AlphaFuncAlways_Disabled with its three
gradient bands W px wide and centred, submitted by SET_VERTEX4F or
SET_VERTEX3F. A band is read with the tracker's own instrument,
docs/testing/pair_fill_blocks_38.pair_stats (E - O over pair_census_38's
qualifying mask, framebuffer parity) and xparity (x-step parity skew), on the
red band (rows 168-210, clear of Alpha func's text) and the blue band (rows
216-274), 2 px inside the band's ends:

  paired     E - O > 0.5 on both bands
  unpaired   |E - O| < 0.1 on both bands
  otherwise  unreadable

Legs:
  K1  PairSel_W512_V4F is pixel-identical to Alpha func's
      AlphaFuncAlways_Disabled from the same root over rows 168-372 (the
      suite reproduces the known positive's draw).
  P   PairSel_W512_V4F is paired (the positive reproduces).
  N   PairSel_W128_V3F is unpaired (the narrow 3F negative reproduces).
  S   reported, the question: W512_V3F and W128_V4F against four rivals --
      width alone (paired, unpaired), SET_VERTEX4F alone (unpaired, paired),
      both (unpaired, unpaired), either (paired, paired).
  T   reported: every width in both registers, for a threshold.
Exit 0 only if K1, P and N hold and S names one rival with both cells read.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
from pair_fill_blocks_38 import pair_stats, xparity  # noqa: E402
from pair_y_group_38 import skew  # noqa: E402

SUITE = "Pair_selector"
BANDS = {"red": (168, 211), "blue": (216, 275)}
WIDTHS = (512, 384, 256, 128)


def path(root, suite, test):
    for p in (os.path.join(root, suite, test + ".png"), os.path.join(root, suite + "::" + test + ".png")):
        if os.path.exists(p):
            return p
    return None


def read(p, width):
    left = (640 - width) // 2
    x0, x1 = left + 2, left + width - 2
    out = {}
    for band, (y0, y1) in BANDS.items():
        ne, no, E, O = pair_stats(p, x0, x1, y0, y1)
        e, o = xparity(p, x0, x1, y0, y1)
        out[band] = (None if E is None else E - O, skew(e, o), ne, no)
    gaps = [v[0] for v in out.values()]
    if any(g is None for g in gaps):
        verdict = "unreadable"
    elif all(g > 0.5 for g in gaps):
        verdict = "paired"
    elif all(abs(g) < 0.1 for g in gaps):
        verdict = "unpaired"
    else:
        verdict = "unreadable"
    return verdict, out


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    res = {}
    for w in WIDTHS:
        for reg in ("V4F", "V3F"):
            test = "PairSel_W%d_%s" % (w, reg)
            p = path(root, SUITE, test)
            if p is None:
                print("MISSING %s -- the run is void" % test)
                return 2
            v, out = read(p, w)
            res[(w, reg)] = v
            print("%-18s %-10s %s" % (test, v, "  ".join(
                "%s E-O %s skew %.3f" % (b, "%+.4f" % g if g is not None else "n/a", s) for b, (g, s, _, _) in out.items())))

    ref = path(root, "Alpha_func", "AlphaFuncAlways_Disabled")
    k1 = False
    if ref is None:
        print("K1 no Alpha func capture in this root -- FAILS")
    else:
        a = np.asarray(Image.open(ref).convert("RGBA")).astype(int)[168:373]
        b = np.asarray(Image.open(path(root, SUITE, "PairSel_W512_V4F")).convert("RGBA")).astype(int)[168:373]
        diff = int((a != b).any(axis=2).sum())
        k1 = diff == 0
        print("K1 PairSel_W512_V4F equals Alpha func's capture over rows 168-372: %s" % (
            "holds" if k1 else "FAILS, %d px differ" % diff))
    p_ok = res[(512, "V4F")] == "paired"
    n_ok = res[(128, "V3F")] == "unpaired"
    print("P  W512_V4F paired: %s" % ("holds" if p_ok else "FAILS (%s)" % res[(512, "V4F")]))
    print("N  W128_V3F unpaired: %s" % ("holds" if n_ok else "FAILS (%s)" % res[(128, "V3F")]))

    rivals = {("paired", "unpaired"): "width alone",
              ("unpaired", "paired"): "SET_VERTEX4F alone",
              ("unpaired", "unpaired"): "width AND SET_VERTEX4F",
              ("paired", "paired"): "width OR SET_VERTEX4F"}
    cells = (res[(512, "V3F")], res[(128, "V4F")])
    s = rivals.get(cells)
    print("S  W512_V3F %s, W128_V4F %s -> selector: %s" % (cells[0], cells[1], s or "NONE (a cell is unreadable)"))
    for reg in ("V4F", "V3F"):
        print("T  %s: %s" % (reg, ", ".join("%d px %s" % (w, res[(w, reg)]) for w in WIDTHS)))
    ok = k1 and p_ok and n_ok and s is not None
    print("VERDICT: %s" % ("every leg holds; the selector is " + s if ok else "a leg failed or the selector is unread"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
