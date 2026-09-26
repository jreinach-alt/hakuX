#!/usr/bin/env python3
"""#53: price candidate ring-phase rules against the Specular goldens.

    ring53_price.py [--root /home/justin/goldens/results]

Reads every lit ControlFlags_VS quad whose code the ring can be seen in:
rows 1 and 3 (diffuse, 4 quads each) and row 2's SEPARATE_SPECULAR quad d09
(the separate specular output, green channel). Each quad's corner code is
matched to a window start of the slot word predicted from ControlFlags_FF
(cf53_slots.py, which this imports). Then, per rule, it counts the quads whose
predicted window start equals the measured one.

The rules, and what each was fitted on:
  own     hakuX today: every vertex lit by its own normal (the FF code).
  cont0   ring; start = VP vertices since the last FF write, mod 6. Zero
          free parameters beyond litprime L0 (which it fits by construction).
  clears  ring; each pb_fill (5 method writes) moves the start by -1, plus a
          constant C = 2 fitted on litprime L0. Its fill weight was chosen
          among the odd weights by Specular row 1, so Specular row 1 is
          TRAINING for this rule, not held out.
  oracle  the measured starts (the ceiling of any ring rule).

Litprime (PR #355): L0 starts 0 at 0 VP vertices after 38 fills; L1 starts
3 after 35 fills. Those two are quoted, not re-read (the captures are on the
host under hardware/runs/2026-09-25-litprime/).

Writes nothing.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "xbox"))
import cf53_slots as cf  # noqa: E402

# pb_fill calls pb_draw_text_screen issues for ControlFlags_FF's labels
# (textfills.py): the name plus the six pb_printat labels.
FF_TEXT_FILLS = 127 + 72 + 65 + 97 + 65 + 97 + 72
CHECKER_VERTS = 4        # DrawCheckerboardUnproject, under the VP, unlit
ROW2_TOP = 285.0


def spec_code(root, suite):
    ff, vs = cf.load(root, suite, "ControlFlags_FF"), cf.load(root, suite, "ControlFlags_VS")
    f = np.array(cf.corner_values(ff[..., 1:], cf.LEFTS[1], ROW2_TOP))
    v = cf.corner_values(vs[..., 1:], cf.LEFTS[1], ROW2_TOP)
    thr = 0.5 * (f.min() + f.max())
    hl = lambda vals: "".join("H" if x > thr else "L" for x in vals)
    return hl(f), hl(v)


def rules(d):
    n = CHECKER_VERTS + 4 * d
    return {
        "cont0": n % 6,
        "clears": (-FF_TEXT_FILLS + 2 + n) % 6,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/home/justin/goldens/results")
    a = ap.parse_args()
    total = {}
    for suite in ("Specular", "Specular_back"):
        thr, word, rows, steps, ok = cf.analyse(a.root, suite)
        windows = {p: "".join(word[(p + k) % 6] for k in range(4)) for p in range(6)}
        own = {v: k for k, v in windows.items()}
        ff_spec, vs_spec = spec_code(a.root, suite)
        quads = [(d, code, p, "diffuse") for d, code, p in rows]
        quads.append((9, vs_spec, own.get(vs_spec), "specular"))
        # FF lights every quad alike, diffuse and specular with the same code
        # (HLLH in Specular, LHHL in Specular_back): d09's is taken as it.
        ff_quad = ff_spec
        print("== %s: slot word %s; FF code of every quad %s" % (suite, word, ff_quad))
        print("   %-4s %-8s %-5s %-6s %-6s %-6s %-6s" % ("draw", "output", "code", "meas", "own", "cont0", "clears"))
        for d, code, p, out in sorted(quads):
            r = rules(d)
            marks = {
                "own": code == ff_quad,
                "cont0": r["cont0"] == p,
                "clears": r["clears"] == p,
            }
            for k, v in marks.items():
                total.setdefault((suite, k), 0)
                total[(suite, k)] += int(v)
            print("   d%02d  %-8s %-5s %-6s %-6s %-6s %-6s" % (
                d, out, code, p, "Y" if marks["own"] else ".",
                "%d%s" % (r["cont0"], "Y" if marks["cont0"] else "."),
                "%d%s" % (r["clears"], "Y" if marks["clears"] else ".")))
        # the offsets of each row relative to row 3's continuous frame
        p12 = [p for d, _, p, o in quads if d == 12][0]
        rel = {}
        for d, _, p, o in quads:
            if d in (4, 9):
                rel[d] = (p - (p12 + 4 * (d - 12))) % 6
        print("   relative to row 3's frame: d04 %+d, d09 %+d (mod 6)" % (rel[4], rel[9]))
    print("== quads right, of 9 per suite:")
    for (suite, k), v in sorted(total.items()):
        print("   %-14s %-6s %d" % (suite, k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
