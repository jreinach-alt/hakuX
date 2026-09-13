#!/usr/bin/env python3
"""Score the same disc twice and report which captures disagree.

    sweep_agreement.py RUN_A RUN_B [RUN_C ...] [--tsv out.tsv] [--goldens DIR]

Exists because of #39, which is a draw whose result is intermittently lost --
same disc, same binary, run to run. The corpus sweep is one run per suite, so
it cannot tell a lost draw from a regression, and on 2026-09-13 it did not:
#75 was filed as a live 100,652 px regression in ``Stencil`` with a suspect
commit and a planned four-build bisect, and it was this defect. Thirteen runs
put every ref's own spread at 0 to over 100,000 px, so the reported delta sat
entirely inside one column's noise. A whole lane spent on a coin landing the
other way up.

The remedy was written down on #39 the day before and not built:

    score every capture from two runs and flag disagreements, which costs one
    extra disc run and makes every future number trustworthy whether or not
    this is ever fixed.

This is that. It answers one question -- *which captures on this disc are
allowed to carry a number today* -- and nothing else. It does not score
against goldens unless you ask it to, it does not judge better or worse, and
it has no opinion about any change.

WHAT IT REPORTS

Per capture, across the runs given:

  AGREE       every run produced byte-identical pixels. Byte equality, not
              score equality: three runs of one binary on the desktop GL disc
              gave ``Surface_pitch::Swizzle`` a differing-pixel count of
              15,360 every time and were still not the same picture. A guard
              that compared scores would have passed them
  DISAGREE    the runs differ; the capture cannot carry a number from a
              single run, and the spread is reported so the band is known
  ABSENT      the capture is missing from at least one run, which is a
              disagreement of the strongest kind -- a test that did not run
              scores nothing, and averaging it with runs where it did is how
              a half-run suite reads as an improvement

With ``--goldens`` it also prints each run's differing-pixel count against the
hardware golden, so a DISAGREE row shows the band in the units every other
tool on this lane speaks. Without it the check is pure byte equality, which
needs no goldens and is the cheaper gate.

EXIT STATUS

0 if every capture agrees, 1 if any disagrees or is absent, 2 if the runs are
not comparable (no captures, or no capture in common). So it can stand in
front of a sweep: if it exits non-zero, the sweep's numbers are conditional
and the disagreeing captures must be excluded or re-run, not averaged.

WHAT IT DELIBERATELY DOES NOT DO

It does not decide how many runs are enough. Two runs catch a defect that
fires half the time about half the time; the desktop GL disc needed five to
see ``Surface_pitch::Swizzle`` vary once. Agreement over two runs is evidence
that a capture is stable, not proof, and the header of any TSV it writes says
so rather than letting the number travel without it.
"""
import argparse
import hashlib
import os
import sys


def load_dir(path):
    """Map capture name -> file path, accepting a directory of PNGs or a
    directory holding exactly one such directory (the shape the run scripts
    and the sweep extractor each produce)."""
    if not os.path.isdir(path):
        sys.exit("not a directory: %s" % path)
    pngs = [f for f in os.listdir(path) if f.endswith(".png")]
    if pngs:
        return {f: os.path.join(path, f) for f in pngs}
    subs = [os.path.join(path, d) for d in sorted(os.listdir(path))
            if os.path.isdir(os.path.join(path, d))]
    found = {}
    for s in subs:
        for f in os.listdir(s):
            if f.endswith(".png"):
                found[f] = os.path.join(s, f)
    return found


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def golden_for(goldens, name):
    stem = name[:-4]
    if "::" in stem:
        suite, test = stem.split("::", 1)
    else:
        return None
    p = os.path.join(goldens, suite, test + ".png")
    return p if os.path.exists(p) else None


def differing(a_path, g_path):
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None
    import numpy as np
    from PIL import Image
    a = np.array(Image.open(a_path).convert("RGB"), dtype=np.int16)
    g = np.array(Image.open(g_path).convert("RGB"), dtype=np.int16)
    if a.shape != g.shape:
        return -1
    return int((a != g).any(axis=2).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+",
                    help="two or more capture directories of the SAME disc")
    ap.add_argument("--goldens",
                    help="also report each run's differing-pixel count, so a "
                         "DISAGREE row shows its band in pixels")
    ap.add_argument("--tsv", help="write the per-capture table here")
    ap.add_argument("--quiet", action="store_true",
                    help="print only the disagreements and the summary")
    args = ap.parse_args()

    if len(args.runs) < 2:
        sys.exit("need at least two runs; one run cannot disagree with itself")

    maps = [load_dir(r) for r in args.runs]
    for r, m in zip(args.runs, maps):
        if not m:
            print("no captures in %s" % r, file=sys.stderr)
            return 2
    names = sorted(set().union(*[set(m) for m in maps]))
    common = set(maps[0])
    for m in maps[1:]:
        common &= set(m)
    if not common:
        print("no capture is present in every run; these are not the same "
              "disc", file=sys.stderr)
        return 2

    rows = []
    for n in names:
        present = [n in m for m in maps]
        if not all(present):
            rows.append((n, "ABSENT", [], "missing from %d of %d runs"
                         % (present.count(False), len(maps))))
            continue
        hashes = [sha(m[n]) for m in maps]
        agree = len(set(hashes)) == 1
        px = []
        if args.goldens:
            g = golden_for(args.goldens, n)
            if g:
                px = [differing(m[n], g) for m in maps]
        note = ""
        if not agree and px and None not in px:
            if min(px) == max(px):
                # The case a score-based guard cannot see, and the reason
                # this one compares bytes: the capture differs between runs
                # while its differing-pixel count does not move at all.
                note = "SAME SCORE, different pixels (%d every run)" % px[0]
            else:
                note = "band %d..%d (spread %d)" % (min(px), max(px),
                                                    max(px) - min(px))
        elif not agree:
            note = "pixels differ"
        rows.append((n, "AGREE" if agree else "DISAGREE", px, note))

    bad = [r for r in rows if r[1] != "AGREE"]
    for n, verdict, px, note in rows:
        if args.quiet and verdict == "AGREE":
            continue
        pxs = ("  " + " ".join(str(v) for v in px)) if px else ""
        print("%-9s %-58s %s%s" % (verdict, n[:-4], note, pxs))

    print()
    print("%d captures over %d runs: %d agree, %d disagree, %d absent"
          % (len(rows), len(maps),
             sum(1 for r in rows if r[1] == "AGREE"),
             sum(1 for r in rows if r[1] == "DISAGREE"),
             sum(1 for r in rows if r[1] == "ABSENT")))
    if bad:
        print("Those %d cannot carry a number from a single run of this disc."
              % len(bad))
    else:
        print("Every capture agreed over %d runs. That is evidence of "
              "stability, not proof: a defect that fires half the time is "
              "missed by two runs about a quarter of the time." % len(maps))

    if args.tsv:
        with open(args.tsv, "w", encoding="utf-8") as fh:
            fh.write("# agreement over %d runs of the same disc; AGREE means "
                     "byte-identical, not correct\n" % len(maps))
            fh.write("# agreement over N runs is evidence of stability, not "
                     "proof -- see #39\n")
            fh.write("capture\tverdict\tnote\t%s\n"
                     % "\t".join("run%d_px" % (i + 1) for i in range(len(maps))))
            for n, verdict, px, note in rows:
                fh.write("%s\t%s\t%s\t%s\n"
                         % (n[:-4], verdict, note,
                            "\t".join(str(v) for v in px) if px else ""))
        print("wrote %s" % args.tsv)

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
