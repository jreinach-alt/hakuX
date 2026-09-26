#!/usr/bin/env python3
"""Split the real ten-run single-binary measurement into two five-run arms.

    ab_selftest_slice.py OUTDIR        writes OUTDIR/armA and OUTDIR/armB

This is the noise-floor fixture for ab_selftest.sh, and it is not synthetic
data: dispatch result ``1789255594-exp54-stst-correct`` is ten runs of one
unchanged APK (5ae2667e0f30) over ``Texture border``, requested precisely
because that suite was suspected of nondeterminism. Slicing it in half gives
two arms that differ by nothing except which runs went into them, so every
delta between them is device noise by construction -- which is the only
honest way to test that the band logic suppresses a flake without also
suppressing a real change.

What it measures, for the record: 17 of the 18 captures have band 0 across all
ten runs, and ``2D_BorderTex_SZ`` alone gives 0, 0, 0, 0, 0, 146, 181, 1847,
2352, 2430, 5640 -- five runs bit-exact and five not, on one binary.
"""
import json
import os
import shutil
import sys

SRC = os.environ.get(
    "AB_SELFTEST_SRC",
    "/home/justin/hakux-work/dispatch/results/"
    "1789255594-exp54-stst-correct-3660183")
HALVES = {"armA": [1, 2, 3, 4, 5], "armB": [6, 7, 8, 9, 10]}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = sys.argv[1]
    meta_path = os.path.join(SRC, "result.json")
    if not os.path.exists(meta_path):
        sys.exit("the ten-run fixture is not on disk: %s" % SRC)
    meta = json.load(open(meta_path))
    have = {r["tsv"] for r in meta.get("runs", [])}
    for name, runs in HALVES.items():
        wanted = ["scores%d.tsv" % r for r in runs]
        missing = [w for w in wanted if w not in have]
        if missing:
            sys.exit("%s is missing from the fixture: %s"
                     % (SRC, ", ".join(missing)))
        d = os.path.join(out, name)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        m = dict(meta, runs=[])
        for i, r in enumerate(runs, 1):
            shutil.copy(os.path.join(SRC, "scores%d.tsv" % r),
                        os.path.join(d, "scores%d.tsv" % i))
            old = next(x for x in meta["runs"]
                       if x["tsv"] == "scores%d.tsv" % r)
            m["runs"].append(dict(old, tsv="scores%d.tsv" % i))
        json.dump(m, open(os.path.join(d, "result.json"), "w"), indent=2)
        # ab_compare.py requires the DONE marker: a directory without one is a
        # run that never finished, whose TSV is whatever had been written when
        # it stopped.
        open(os.path.join(d, "DONE"), "w").close()
        print("%s  runs %s  px %s" % (
            d, " ".join(str(r) for r in runs),
            " ".join(str(r["px"]) for r in m["runs"])))


if __name__ == "__main__":
    main()
