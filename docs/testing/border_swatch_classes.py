#!/usr/bin/env python3
"""Split #44's stale swatches into the classes a skew bound can and cannot reach.

    border_swatch_origin.py --json RESULTDIR > nf.json
    border_swatch_classes.py nf.json [nf2.json ...]
    border_swatch_classes.py --a A.json --b B.json

Reads `border_swatch_origin.py --json` and reports nothing that tool does not
already compute. It exists because `stale_px` is a SUM over swatches that fail
for structurally different reasons, and #44 is now being worked by two lanes
with two mechanisms -- a pushbuffer skew (this lane, #44's own conclusion) and
a decoded-length hash gate that declines to re-upload at all (the texture
lane, `blind=2` measured directly). A single total cannot be used to judge
either, and AGENTS.md records the trap in as many words: a class count is a
count of pixels a mechanism TOUCHES, not of pixels it is solely responsible
for, and subtracting one from a differing total assumes an additivity the
residual classes do not have.

THREE CLASSES, and the field that separates them is `cut`:

  TORN        a finite `cut` with `prefix_ok` -- the stale set is a row-major
              PREFIX of the successor's write, so the read landed in the
              middle of it. Unambiguously a read while a write is in flight;
              nothing else produces a frontier at an arbitrary offset, and the
              offset differs every run. A skew bound must zero these.

  COMPLETE    no `cut`, and the successor explains every wrong pixel. The
              successor's write had FINISHED when the read happened, so there
              is no frontier -- a skew of one whole iteration rather than a
              partial one. Still a skew, and the argument is directional: a
              texture that was never re-uploaded holds content from an EARLIER
              upload, so it cannot show the SUCCESSOR's surface, which is
              written after the draw that is missing it. A missed re-upload
              therefore does not reach this class; a skew bound should.

  NO-SUCCESSOR `successor == 0` while pixels are still wrong. The successor
              model explains none of it. On the ten-run floor this is pass-2
              4x8 -- the LAST swatch of the test, which has no successor at
              all -- so no "reads its successor" story can produce it, and a
              bound on the guest's run-ahead within the test cannot be
              expected to. It is what remains to be explained.

`border_swatch_origin.py` reports `unexplained_px = 0` for the whole floor,
and that is right on its own terms: every wrong pixel is matched by SOME
candidate surface. It is not the same statement as "the immediate successor
explains 100% of wrong pixels", which is the headline on #44. Split this way
the second claim reads 11,916 of 12,596 -- 94.6% -- with the 680-pixel
remainder in the class that has no successor to be explained by.
"""
import argparse
import json
import sys


def classify(sw):
    cut = sw.get("cut")
    if isinstance(cut, int):
        return "torn"
    if sw.get("successor", 0) == 0 and sw.get("wrong", 0) > 0:
        return "no-successor"
    if sw.get("successor", 0) == sw.get("wrong", 0):
        return "complete"
    return "partial-successor"


CLASSES = ("torn", "complete", "partial-successor", "no-successor")


def load(path):
    d = json.load(open(path))
    return d if isinstance(d, list) else d.get("runs", [])


def runkey(r):
    tail = r["run"].rsplit("captures", 1)
    try:
        return int(tail[1])
    except (IndexError, ValueError):
        return 0


def summarise(label, runs):
    px = {c: 0 for c in CLASSES}
    n = {c: 0 for c in CLASSES}
    per_run = []
    for r in sorted(runs, key=runkey):
        rpx = {c: 0 for c in CLASSES}
        for sw in r.get("swatches", []):
            c = classify(sw)
            px[c] += sw["wrong"]
            n[c] += 1
            rpx[c] += sw["wrong"]
        per_run.append((r["run"].rsplit("/", 1)[-1], r.get("stale_px", 0),
                        r.get("races_lost", 0), rpx))

    total = sum(px.values())
    print("%s -- %d runs, %d wrong px in %d swatches"
          % (label, len(per_run), total, sum(n.values())))
    print("  %-18s %6s %8s %7s" % ("class", "swatch", "px", "share"))
    for c in CLASSES:
        if n[c] or px[c]:
            print("  %-18s %6d %8d %6.1f%%"
                  % (c, n[c], px[c], 100.0 * px[c] / total if total else 0))
    print("  %-18s %6s %8s" % ("-- per run --", "stale", "lost"))
    for name, stale, lost, rpx in per_run:
        detail = " ".join("%s=%d" % (c, rpx[c]) for c in CLASSES if rpx[c])
        print("  %-18s %6d %8d   %s" % (name, stale, lost, detail))
    print()
    return px, n, len(per_run), per_run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--a", action="append")
    ap.add_argument("--b", action="append")
    args = ap.parse_args()

    if args.a and args.b:
        pa, na, ra, rowsa = summarise("A", [r for p in args.a for r in load(p)])
        pb, nb, rb, rowsb = summarise("B", [r for p in args.b for r in load(p)])
        print("%-18s %10s %10s   %s" % ("class", "A px", "B px", "verdict"))
        for c in CLASSES:
            if not (pa[c] or pb[c]):
                continue
            if c in ("torn", "complete"):
                v = "CLOSED" if pb[c] == 0 else "STILL OPEN"
            else:
                v = "not this bound's to close"
            print("%-18s %10d %10d   %s" % (c, pa[c], pb[c], v))
        za = sum(1 for _, s, _, _ in rowsa if s == 0)
        zb = sum(1 for _, s, _, _ in rowsb if s == 0)
        print("\nruns with stale_px == 0:  A %d of %d, B %d of %d"
              % (za, ra, zb, rb))
        # The bar #44 set, and the narrower thing this split can actually say.
        print("S1 as registered (stale_px == 0 on every run of B): %s"
              % ("HOLDS" if zb == rb else "FAILS"))
        print("mechanism-level (torn + complete both zero in B):   %s"
              % ("HOLDS" if pb["torn"] == 0 and pb["complete"] == 0
                 else "FAILS"))
        return 0

    if not args.paths:
        ap.error("give one or more --json outputs, or --a and --b")
    for p in args.paths:
        summarise(p, load(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
