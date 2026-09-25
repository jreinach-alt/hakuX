#!/usr/bin/env python3
"""ClipF at clip_left 300, clip_top 8: predict it, then score it (#31, flatTop).

    python3 docs/lanes/xbox/score_clipf300.py --predict \\
        --goldens /home/justin/goldens/results --goldens <run>/console-run/console ...
    python3 docs/lanes/xbox/score_clipf300.py \\
        --goldens <this run>/console-run/console --goldens /home/justin/goldens/results ...

Uses wbuf_anchor_recover.py unchanged.  It adds the one new capture to the
tool's PRIMS exactly as the tool defines the clip_left 150 variants (the
floor quad, its ZS0 baseline the unclipped FloorQuad), and adds it to
`_QUADS` as well.  `_QUADS` is computed from PRIMS at import, so a capture
added afterwards would read `second_of_quad` False on its second triangle,
which is wrong for a quad.

--predict prints what every rival says about the new capture BEFORE it
exists.  That covers master's `sel` rule, the four literals the fix lane
names as interchangeable, and each four-literal fit the tool's own
--selectors search finds over the anchors silicon has already given.  Only
geometry is read for the new capture.  The fits come from the anchors in
the --goldens roots, so pass every earlier silicon run.

Without --predict it runs the tool's main() with --selectors over the roots
given, so the new capture's recovered anchor is scored with everything else.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "testing"))
import wbuf_anchor_recover as w  # noqa: E402

CAP, CL, CT = "ClipF-300-008", 300, 8
NAMED = ("flat_top", "span_starts_at_clip", "B_quad_covered_at_c",
         "second_of_quad")

w.PRIMS[CAP] = (w.FLOOR, CL, CT, "FloorQuad")
w._QUADS.add(CAP)


def predict(argv):
    import numpy as np

    got = {}
    real = w._selectors

    def keep(rows):
        got["fit4"] = real(rows)
        return got["fit4"]

    w._selectors = keep
    rc = w.main(["--selectors"] + argv)
    w._selectors = real
    if rc or "fit4" not in got:
        print("the tool did not reach --selectors (rc %r)" % rc, file=sys.stderr)
        return 2
    fit4 = got["fit4"]

    print()
    print("=" * 78)
    print("PREDICTION for %s (clip_left %d, clip_top %d), from geometry only"
          % (CAP, CL, CT))
    print("=" * 78)
    clip = (float(CL), float(CT), float(w.W), float(w.H))
    for ti in (0, 1):
        tri = w.FLOOR[ti]
        ft = w.features(tri, CL, CT, ti == 1)
        px = int(w.coverage(np, tri, CL, CT).sum())
        if ft is None:
            print("t%d: the clip leaves nothing (%d px)" % (ti, px))
            continue
        r, c, f = ft
        ax = w.dominant_axis(tri)
        a = c if ax == "x" else r
        quad, grid = 2 * (a // 2), 4 * (a // 4) + 2
        sel, cut = w.anchor(tri, clip, "sel")
        sel_a = sel[0] if ax == "x" else sel[1]
        g = sum((f[x[0]] == x[1]) or ((f[y[0]] == y[1]) and (
            f[p[0]] == p[1] or f[q[0]] == q[1])) for x, y, p, q in fit4)
        print("t%d: %d px, axis %s, first covered row %d, anchor column %d, cut %s"
              % (ti, px, ax, r, c, cut))
        print("    quad snap -> %d   4-grid -> %d   %s"
              % (quad, grid, "INFORMATIVE" if quad != grid else
                 "not informative (both rules agree)"))
        print("    master's sel rule -> %d (%s)"
              % (sel_a, "grid" if sel_a == grid and quad != grid else
                 "quad" if sel_a == quad and quad != grid else "either"))
        print("    named literals: %s" % ", ".join(
            "%s=%s" % (k, f[k]) for k in NAMED))
        print("    four-literal fits: %d vote grid, %d vote quad, of %d"
              % (g, len(fit4) - g, len(fit4)))
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--predict" in args:
        args.remove("--predict")
        sys.exit(predict(args))
    sys.exit(w.main(["--selectors"] + args))
