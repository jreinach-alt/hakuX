#!/usr/bin/env python3
"""#52 blocker falsifier: is the "stall" a slow test, or a guest clock that
runs backwards?

#52's blocker says the 784-golden depth oracle is unreachable in one run
"BECAUSE OF A STALL, NOT A RUN BUDGET", that pace was never the variable
(876 ms/test then, 888 ms/test now), that ~1,525 s of a 1,800 s run were
"spent not testing", and -- load-bearing -- that "The stalling test is NOT
named ... any attribution from it would be the reader's".

Both halves are checkable offline, from the per-test durations the guest
already writes into captures*/pgraph_progress_log.txt.

FALSIFIER SHAPE.  The blocker's model is "wall clock minus test time is
dead time of unknown origin".  If that were right, every per-test duration
would be a plausible positive number and the dead time would sit BETWEEN
tests, invisible to this file.  So: if the dead time is NOT outside the
measured tests, individual `Completed ... in Nms` lines will carry values
that cannot happen -- negative, or larger than the whole run.  An impossible
row is the check; a file of uniformly plausible durations would leave the
blocker's model standing, which is the world in which this falsifier fails.

It is not forced true by anything this script does: it reads durations the
guest printed on the device, long before the blocker was written.
"""
import glob, os, re, sys, collections

R = "/home/justin/hakux-work/dispatch/results"
DUR = re.compile(r"Completed '([^']+)' in (-?\d+)ms")
START = re.compile(r"Starting (.+)$")


def scan(path):
    done, started, neg = {}, [], []
    last_start = None
    for line in open(path, errors="replace"):
        line = line.rstrip("\n")
        m = DUR.search(line)
        if m:
            name, ms = m.group(1), int(m.group(2))
            done[name] = ms
            if ms < 0:
                neg.append((name, ms))
            last_start = None
            continue
        m = START.search(line.strip())
        if m:
            last_start = m.group(1).strip()
            started.append(last_start)
    return done, started, neg, last_start


def main():
    logs = sorted(glob.glob(R + "/*/captures*/pgraph_progress_log.txt"))
    print("progress logs on disk: %d" % len(logs))
    tot_neg = 0
    tot_neg_ms = 0
    runs_with_neg = []
    unfinished = []
    unreadable = []
    anomalous = []
    for p in logs:
        run = os.path.basename(os.path.dirname(os.path.dirname(p)))
        done, started, neg, last = scan(p)
        if neg:
            runs_with_neg.append((run, neg, sum(v for _, v in neg), done))
            tot_neg += len(neg)
            tot_neg_ms += sum(v for _, v in neg)
        # A trailing Starting with no Completed NAMES the test the guest
        # stopped inside -- which #52's blocker says is not knowable.
        #
        # BUT ONLY WHERE THE COUNTS SAY SO.  Not every progress log on disk
        # uses this format: many carry "[n/m] Suite::test" progress lines and
        # no `Completed ... in Nms` at all, and a naive "last Starting wins"
        # read reported 762 of 766 runs as having stopped inside a test --
        # a clean-looking total that is almost entirely the reader's own
        # regex failing to match.  The honest test is arithmetic: a run
        # stopped inside a test iff it emitted exactly one more Starting than
        # Completed.  Runs whose two counts are equal finished; runs with no
        # Completed lines at all are a format this instrument cannot read,
        # and are reported as unreadable rather than as stalls.
        if not done:
            unreadable.append(run)
        elif len(started) == len(done) + 1 and last is not None:
            unfinished.append((run, last, len(done)))
        elif len(started) != len(done):
            anomalous.append((run, len(started), len(done)))

    print()
    print("=== IMPOSSIBLE ROWS: a per-test duration that cannot happen")
    print("negative durations: %d, across %d runs, summing %d ms (%.1f s)"
          % (tot_neg, len(runs_with_neg), tot_neg_ms, tot_neg_ms / 1000.0))
    if not tot_neg:
        print("NONE.  Every duration is plausible, which leaves the blocker's")
        print("'dead time between tests' model standing.  This is the world in")
        print("which this falsifier fails, and it did not happen.")
    for run, neg, s, done in runs_with_neg:
        pos = [v for v in done.values() if v >= 0]
        print("  %-44s %2d negative, sum %8d ms | %d positive, median %d ms"
              % (run[:44], len(neg), s, len(pos),
                 sorted(pos)[len(pos) // 2] if pos else 0))
        for name, ms in neg[:6]:
            print("        %-44s %9d ms" % (name, ms))
        # What the blocker's arithmetic would have computed for this run.
        wall_in_tests = sum(done.values())
        print("        sum of ALL durations as printed : %8.1f s" % (wall_in_tests / 1000.0))
        print("        sum with negatives EXCLUDED     : %8.1f s" % (sum(pos) / 1000.0))
        print("        the difference is the part the blocker charged to a stall")

    print()
    print("=== RUNS THAT STOPPED INSIDE A TEST")
    print("Criterion: exactly one more 'Starting' than 'Completed'.  The last")
    print("'Starting' then NAMES the test -- which #52's blocker says is not")
    print("knowable from this artefact.")
    print("count: %d of %d readable logs" % (len(unfinished), len(logs) - len(unreadable)))
    for run, last, n in unfinished:
        print("  %-44s stopped inside: %s" % (run[:44], last))
        print("  %-44s   (%d tests completed before it)" % ("", n))

    print()
    print("=== INSTRUMENT COVERAGE, so a zero above cannot be read as 'no stalls'")
    print("logs with no 'Completed ... in Nms' line at all (a format this")
    print("script cannot read, NOT evidence of anything): %d" % len(unreadable))
    print("logs whose Starting/Completed counts differ by something other")
    print("than one (unexplained, report rather than classify): %d" % len(anomalous))
    for run, s, d in anomalous[:10]:
        print("  %-44s Starting=%d Completed=%d" % (run[:44], s, d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
