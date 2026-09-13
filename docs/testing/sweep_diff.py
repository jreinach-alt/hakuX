#!/usr/bin/env python3
"""Diff two scoreboard columns, and REFUSE to attribute a mover without a repeat.

    sweep_diff.py <column-A> <column-B> [--dispatch DIR] [--scoreboard DIR]

Why this exists, and it is not to save typing
---------------------------------------------

The corpus sweep runs ONE run per suite. So a diff of two sweep columns is one
run before against one run after, and on any suite with a nondeterministic
failure that difference is indistinguishable from noise.

On 2026-09-13 the orchestrator diffed two columns by hand, found three
previously-exact `Stencil` captures at 40,000/30,000/30,000 px, filed it as a
regression (#75), named a suspect commit and spawned a lane to bisect it.
Thirteen runs later: `0026f00534` alone spans 0 to 180,000 px on one binary,
and the column called clean reaches 140,000 px on two of the three captures the
regression was attributed to. There was no regression. #39 had predicted
exactly this in writing the previous day -- "a change measured by one run
before and one after can show a difference it did not cause" -- and recommended
a two-run disagreement guard that was never built. This is it.

What it does that a hand-rolled diff does not
---------------------------------------------

For every suite that has movers, it pools every SAME-REF REPEAT on disk --
completed runs of that suite at one ref, on one disc, from one APK. Then:

  * fewer than MIN_RUNS repeats -> UNATTRIBUTABLE. The tool prints the exact
    `request.sh` line that would settle it and exits non-zero.
  * enough repeats -> report the pooled band and label each mover INSIDE or
    OUTSIDE it. Only an OUTSIDE mover is a candidate regression, and even that
    is reported as a candidate because the band is a lower bound.

THE RUN COUNT IS NOT DECORATION, and the first version of this file got it
wrong in the exact way it was written to prevent. It took the largest repeat
group and called its min/max "the spread". For `Stencil` that was two runs at
one ref which both happened to read 0, so it reported the spread as [0, 0] and
declared the three movers candidate regressions -- reproducing #75's false
conclusion from inside the guard. At that suite's measured 7-in-13 failure
rate, two clean runs in a row happen about a fifth of the time. A spread from
a handful of runs is a LOWER BOUND on the spread, never the spread. Pooling
across refs and requiring MIN_RUNS is what turns it into an answer: the same
three movers now read INSIDE [0, 40000] over 6 runs.

The exit code is the point. A report that says "here are the movers, mind the
noise" is what the hand-rolled version already did, and it did not stop
anybody: the warning was there to be read and the conclusion was drawn anyway.
A gate that exits 1 until the repeat exists cannot be read past.

It also compares `scorer_rev` between the columns, because two columns scored
by different `score_sweep.py` revisions disagree about which captures are VOID
with no pixel differing -- and that is not hypothetical either: the sweep ran
100 suites over five hours with a scorer fix landing mid-run, so one column was
internally inconsistent until it was re-scored.
"""
import argparse
import collections
import csv
import glob
import json
import os
import sys

# Below this many repeat runs, a suite's variance is not bounded and no mover
# in it may be attributed. Five is not a statistical derivation -- it is the
# smallest number at which a suite failing half its runs is unlikely (~3%) to
# look clean throughout, and the case that motivated this file needed thirteen
# to settle. It is deliberately a floor on CONFIDENCE, not on effort.
MIN_RUNS = 5

SCOREBOARD = "/home/justin/hakux-work/scoreboard"
DISPATCH = "/home/justin/hakux-work/dispatch"


def load_column(d):
    """{(suite, test): structural} plus the set of scorer revisions seen."""
    rows, scorers, refs = {}, set(), set()
    for f in sorted(glob.glob(os.path.join(d, "*.tsv"))):
        for r in csv.DictReader(open(f), delimiter="\t"):
            if not r.get("suite"):
                continue
            try:
                diff = int(r.get("differing") or 0)
                ob1 = int(r.get("off_by_one") or 0)
            except ValueError:
                continue
            rows[(r["suite"], r["test"])] = diff - ob1
    prov = os.path.join(d, "PROVENANCE.json")
    if os.path.exists(prov):
        try:
            p = json.load(open(prov))
            for entry in p.get("refs") or []:
                refs.add(entry.get("ref", ""))
        except Exception:
            pass
    # scorer_rev lives in the dispatch result, not in the TSV, so collect it
    # from the result dirs the column was built from.
    for f in sorted(glob.glob(os.path.join(d, "*.tsv"))):
        rdir = os.path.join(DISPATCH, "results", os.path.basename(f)[:-4])
        meta = os.path.join(rdir, "result.json")
        if os.path.exists(meta):
            try:
                scorers.add(json.load(open(meta)).get("scorer_rev") or "")
            except Exception:
                pass
    return rows, scorers, refs


def repeats_for(suite, dispatch=DISPATCH):
    """Completed runs of one suite, grouped by (ref, disc_id, apk_sha).

    A REPEAT is two entries sharing that key. Grouping on the disc as well as
    the ref matters: the same suite built from a different base ISO is a
    different disc, and two such runs are not a repeat of each other -- which
    is exactly the mistake `disc_id` was introduced to stop.
    """
    groups = collections.defaultdict(list)
    for rdir in glob.glob(os.path.join(dispatch, "results", "*")):
        req = os.path.join(rdir, "request.json")
        res = os.path.join(rdir, "result.json")
        if not (os.path.exists(req) and os.path.exists(res)):
            continue
        try:
            q = json.load(open(req))
            m = json.load(open(res))
        except Exception:
            continue
        if suite.replace("_", " ") not in [s.replace("_", " ")
                                           for s in (q.get("suites") or [])]:
            continue
        # Only completion-proven runs. A truncated run leaves the previous
        # image in place and reads as a pass, so counting it as a repeat would
        # manufacture agreement.
        cv = m.get("captures_vs_goldens") or {}
        proof = all(not c.get("partial") for c in cv.values()) if cv else False
        if not proof:
            continue
        key = (m.get("ref") or q.get("ref") or "", m.get("disc_id") or "",
               m.get("apk_sha") or "")
        tsv = os.path.join(rdir, "scores1.tsv")
        if os.path.exists(tsv):
            groups[key].append(tsv)
    return {k: v for k, v in groups.items() if len(v) > 1}


def spread_from(tsvs):
    """Per-capture min/max structural across repeats of one ref."""
    vals = collections.defaultdict(list)
    for t in tsvs:
        for r in csv.DictReader(open(t), delimiter="\t"):
            if not r.get("suite"):
                continue
            try:
                vals[(r["suite"], r["test"])].append(
                    int(r.get("differing") or 0) - int(r.get("off_by_one") or 0))
            except ValueError:
                pass
    return {k: (min(v), max(v)) for k, v in vals.items() if len(v) > 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("column_a")
    ap.add_argument("column_b")
    ap.add_argument("--scoreboard", default=SCOREBOARD)
    ap.add_argument("--dispatch", default=DISPATCH)
    a = ap.parse_args()

    da = os.path.join(a.scoreboard, a.column_a)
    db = os.path.join(a.scoreboard, a.column_b)
    for d in (da, db):
        if not os.path.isdir(d):
            sys.exit("no such column: %s" % d)

    A, sa, ra = load_column(da)
    B, sb, rb = load_column(db)
    both = set(A) & set(B)
    print("columns %s -> %s" % (a.column_a, a.column_b))
    print("  %d captures in both; %d only in A, %d only in B"
          % (len(both), len(set(A) - set(B)), len(set(B) - set(A))))

    if sa and sb and sa != sb:
        print("\nWARNING: the columns were scored by different score_sweep.py "
              "revisions (A %s, B %s). They disagree about which captures are "
              "VOID with no pixel differing, so a status count is not "
              "comparable across them. Re-score one before reading one."
              % (sorted(sa), sorted(sb)))
    for label, s in (("A", sa), ("B", sb)):
        if len(s) > 1:
            print("\nWARNING: column %s is INTERNALLY mixed -- its suites were "
                  "scored by %d different scorer revisions %s. The sweep runs "
                  "for hours, so a scorer change lands mid-column."
                  % (label, len(s), sorted(s)))

    movers = [(k, A[k], B[k]) for k in sorted(both) if A[k] != B[k]]
    if not movers:
        print("\nno movers. Nothing to attribute.")
        return 0
    print("\n%d capture(s) moved:" % len(movers))

    by_suite = collections.defaultdict(list)
    for k, x, y in movers:
        by_suite[k[0]].append((k[1], x, y))

    unattributable, outside = [], []
    for suite in sorted(by_suite):
        reps = repeats_for(suite, a.dispatch)
        print("\n  %s" % suite)
        if not reps:
            print("    NO SAME-REF REPEAT ON DISK. Every mover below is "
                  "UNATTRIBUTABLE: one run before against one run after cannot "
                  "separate a change from this suite's own variance.")
            for test, x, y in by_suite[suite]:
                print("      %-44s %9d -> %9d" % (test, x, y))
                unattributable.append((suite, test))
            print("    settle it with:  docs/testing/request.sh --who "
                  "sweep-repeat --purpose 'noise floor for %s' --suites '%s' "
                  "--runs %d --no-expect 'noise floor'"
                  % (suite, suite.replace("_", " "), MIN_RUNS))
            continue
        # POOL EVERY REPEAT GROUP, and count the runs behind the answer.
        #
        # The first version of this took the group with the most runs and
        # called its min/max "the spread". It then reproduced, exactly, the
        # error it was written to prevent: for `Stencil` it found two runs at
        # one ref that both happened to read 0, reported the spread as [0, 0],
        # and declared the movers candidate regressions. At that suite's
        # measured 7-in-13 failure rate, two clean runs in a row happen about
        # a fifth of the time.
        #
        # A spread from a handful of runs is a LOWER BOUND on the spread, never
        # the spread -- the same rule as a within-ref floor, which this
        # campaign has already paid for twice. So: pool across refs, because a
        # suite that varies at ANY ref is a suite whose single runs cannot be
        # differenced; and refuse to call anything a regression until enough
        # runs stand behind the band.
        nruns = sum(len(v) for v in reps.values())
        sp = {}
        for tsvs in reps.values():
            for k, (lo, hi) in spread_from(tsvs).items():
                if k in sp:
                    sp[k] = (min(sp[k][0], lo), max(sp[k][1], hi))
                else:
                    sp[k] = (lo, hi)
        varies = sum(1 for lo, hi in sp.values() if lo != hi)
        print("    %d repeat run(s) across %d ref/disc group(s); %d of %d "
              "repeated captures vary between runs"
              % (nruns, len(reps), varies, len(sp)))
        if nruns < MIN_RUNS:
            print("    TOO FEW REPEATS to bound this suite's variance. %d runs "
                  "give a LOWER BOUND on the spread, not the spread, and a "
                  "quiet pair proves nothing: at a 7-in-13 per-run failure "
                  "rate two clean runs happen ~20%% of the time. Every mover "
                  "below is UNATTRIBUTABLE." % nruns)
            for test, x, y in by_suite[suite]:
                print("      %-44s %9d -> %9d" % (test, x, y))
                unattributable.append((suite, test))
            print("    settle it with:  docs/testing/request.sh --who "
                  "sweep-repeat --purpose 'noise floor for %s' --suites '%s' "
                  "--runs %d --no-expect 'noise floor'"
                  % (suite, suite.replace("_", " "), MIN_RUNS))
            continue
        if varies:
            print("    THIS SUITE IS NONDETERMINISTIC -- %d captures vary "
                  "between runs of one binary on one disc. A mover here is "
                  "attributable only if it leaves the pooled band." % varies)
        for test, x, y in by_suite[suite]:
            band = sp.get((suite, test))
            if band is None:
                print("      %-44s %9d -> %9d   NOT repeated -- no band for "
                      "this capture, so unattributable" % (test, x, y))
                unattributable.append((suite, test))
            elif band[0] <= y <= band[1] and band[0] <= x <= band[1]:
                print("      %-44s %9d -> %9d   INSIDE the pooled band "
                      "[%d, %d] over %d runs -- not a regression"
                      % (test, x, y, band[0], band[1], nruns))
            else:
                print("      %-44s %9d -> %9d   outside the pooled band "
                      "[%d, %d] over %d runs -- CANDIDATE regression, and the "
                      "band is a lower bound so more runs can retire it"
                      % (test, x, y, band[0], band[1], nruns))
                outside.append((suite, test))

    print("\n%s" % ("-" * 70))
    if unattributable:
        print("REFUSING to attribute %d mover(s): no same-ref repeat exists "
              "for their suite, so a difference between two single runs cannot "
              "be told from that suite's own variance. Queue the runs named "
              "above first." % len(unattributable))
        return 1
    if outside:
        print("%d mover(s) sit OUTSIDE their suite's measured spread and are "
              "candidate regressions." % len(outside))
        return 0
    print("every mover sits INSIDE its suite's measured run-to-run spread. "
          "There is nothing here to attribute to a commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
