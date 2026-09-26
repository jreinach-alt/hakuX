#!/usr/bin/env python3
"""Did the Line_width derivation ever pin a TIE, and on which axis?

The #13 extent rule is low-open on BOTH axes: a pixel is lit iff its centre is
in (c - E/2, c + E/2].  That choice only bites on a cut whose band edge lands
EXACTLY on a pixel centre (a tie).  Front_face's line-mode goldens break a
y-tie the other way (edge at integer y=430 lights row 429, not 430) while
breaking x-ties the rule's way (x=138 lights column 138).  If the Line_width
cuts contain y-axis ties, the rule was pinned there and Front_face contradicts
it; if they contain none, the rule's y-axis tie direction was never measured.

Reuses line_extent_phase.py's own cuts, snap and predict, unchanged.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
import line_extent_phase as lep  # noqa: E402

G = os.path.expanduser("~/goldens/results")


def main():
    for lo, hi in ((0, 5.0), (6.0, 48.0), (0, 63.875)):
        rows = lep.cuts(G, lo, hi)
        T = lep.tabulate(rows)
        E, xm, ln, p, q, oa, ob = T
        c = p + q * (ln + 0.5)
        # band edges relative to pixel centres on the minor axis
        lo_e, hi_e = c - E / 2 - 0.5, c + E / 2 - 0.5
        tie_lo = np.abs(lo_e - np.round(lo_e)) < 1e-6
        tie_hi = np.abs(hi_e - np.round(hi_e)) < 1e-6
        tie = tie_lo | tie_hi
        print("widths %s-%s: %d cuts" % (lo, hi, len(rows)))
        for name, m in (("x-major (minor=y)", xm), ("y-major (minor=x)", ~xm)):
            for rule in ("low_open", "high_open"):
                ok = lep.exact(T, rule=rule)
                print("  %-18s ties %5d of %6d   %-9s exact on ties %5d  (all cuts %6d)"
                      % (name, (tie & m).sum(), m.sum(), rule,
                         (ok & tie & m).sum(), (ok & m).sum()))


if __name__ == "__main__":
    main()
