#!/usr/bin/env python3
"""#50 blocker falsifier: how unstable is the FULL 1,673-capture disc,
run to run, using the runs already on disk?

#50's blocker says the cheapest honest measurement is "5 runs on the FULL
1,673-capture disc, ~28 min each", and that the run-to-run rate for
1-srcRGB_SADD_0 rests on n=3 observations of ONE capture.

But three full-disc runs ALREADY EXIST at one ref and one disc_id, and the
population that matters is not one capture observed three times -- it is
1,673 captures observed three times, i.e. 1,673 independent Bernoulli trials
of "does this capture's value depend on the run?".  That is a ~1,600x larger
sample for the same zero device minutes.

FALSIFIER SHAPE.  If run-to-run instability on the full disc were confined to
the handful of captures #50 names, then comparing the three runs pairwise
would show differing-pixel disagreement on ~those captures and nothing else.
A large unstable set refutes "the movers are a known short list"; a set of
exactly zero would refute the race on the full disc outright.  Neither
outcome is forced by the comparison: the instrument reads three files it did
not produce.

CONTROL.  apk_sha and disc_id are asserted equal across the three runs and
the script refuses to summarise if they are not -- a comparison across
binaries or across disc compositions measures the build or the composition,
which is exactly the pooling error #50's own blocker withdrew a rate for.
"""
import csv, os, sys, itertools, collections

RESULTS = "/home/justin/hakux-work/dispatch/results"
RUNS = ["1789318910-blendstack-A-63953",
        "1789318915-blendstack-B-64031",
        "1789326864-blendstack-thor2-889257"]

def load(d):
    p = os.path.join(RESULTS, d, "scores1.tsv")
    rows = {}
    meta = set()
    with open(p) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            rows[(r["suite"], r["test"])] = r
            meta.add((r["apk_sha"], r["disc_id"]))
    return rows, meta

def main():
    data, metas = {}, set()
    for d in RUNS:
        rows, meta = load(d)
        data[d] = rows
        metas |= meta
    print("runs: %d, captures each: %s" % (len(RUNS), [len(data[d]) for d in RUNS]))
    print("distinct (apk_sha, disc_id): %d -> %s" % (len(metas), sorted(metas)))
    if len(metas) != 1:
        print("VOID: the three runs are not one binary on one disc composition.")
        print("Pooling them would measure the build or the disc, which is the")
        print("error #50's blocker already withdrew a rate for.")
        return 2

    keys = set(data[RUNS[0]])
    for d in RUNS[1:]:
        keys &= set(data[d])
    print("captures common to all three: %d" % len(keys))

    # A capture is UNSTABLE if its differing-pixel count is not identical in
    # all three runs.  Report the count and the spread, not a mean: a mean
    # hides an 87,381-px defect behind "0.00" (AGENTS.md).
    unstable = []
    for k in sorted(keys):
        vals = [int(data[d][k]["differing"]) for d in RUNS]
        if len(set(vals)) > 1:
            unstable.append((k, vals, max(vals) - min(vals)))

    print()
    print("=== UNSTABLE CAPTURES (differing-px not identical across all 3 runs)")
    print("count: %d of %d  (%.2f%%)" % (len(unstable), len(keys),
                                         100.0 * len(unstable) / max(1, len(keys))))
    if not unstable:
        print("NOTE: zero unstable captures would REFUTE a live race on this disc.")
    unstable.sort(key=lambda t: -t[2])
    for (k, vals, spread) in unstable[:40]:
        print("  %-14s %-34s %s  spread=%d" % (k[0], k[1], vals, spread))
    if len(unstable) > 40:
        print("  ... %d more" % (len(unstable) - 40))

    # Per-suite, because #50 is a Blend_tests issue and a suite-wide rate is
    # what "no fix may be judged on single runs" actually needs.
    bysuite = collections.Counter(k[0] for k, _, _ in unstable)
    tot = collections.Counter(k[0] for k in keys)
    print()
    print("=== BY SUITE")
    for s in sorted(tot):
        print("  %-24s %4d / %4d unstable" % (s, bysuite.get(s, 0), tot[s]))

    # How much of the spread is the whole story?  A capture that moves by 1 px
    # and one that moves by 22,272 are different claims.
    print()
    print("=== SPREAD DISTRIBUTION")
    buckets = collections.Counter()
    for _, _, sp in unstable:
        if sp == 0: b = "0"
        elif sp < 10: b = "1-9"
        elif sp < 100: b = "10-99"
        elif sp < 1000: b = "100-999"
        elif sp < 10000: b = "1k-10k"
        else: b = ">10k"
        buckets[b] += 1
    for b in ["1-9", "10-99", "100-999", "1k-10k", ">10k"]:
        if buckets.get(b):
            print("  %-10s %d" % (b, buckets[b]))

    # The capture #50's blocker quotes by name, so the new number can be
    # checked against the old one rather than replacing it silently.
    print()
    print("=== THE CAPTURE #50 QUOTES")
    for k in sorted(keys):
        if "srcRGB_SADD_0" in k[1] or "dstA_SUB_1" in k[1]:
            print("  %-14s %-34s %s" % (k[0], k[1],
                                        [int(data[d][k]["differing"]) for d in RUNS]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
