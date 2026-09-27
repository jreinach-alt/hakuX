# lane.handbackmerged

## What was wrong

`handback.sh` had no way to wake a lane whose last PR had merged while it
kept working. lane.titleroutes (#397) merged batch 5 as #476, queued three
Thor soaks for batch 6 and ended its session with no open PR. The draft
pickups need an open draft PR, and `idle_lanes()` skipped every lane with a
MERGED PR ("merged is done, not idle"), so nothing resumed it when the soaks
finished.

## What changed

- `idle_lanes()` also emits a row marked `merged=1` for a lane with a live
  territory row, a MERGED PR on `lane/<x>` and no OPEN one. The same
  exclusions apply as for the no-PR row: standing, remote, no worktree or
  brief, `decision-needed` issue. The `decision-needed` check moved ahead of
  the merged/open check; both `continue`, so that order changes nothing for
  the no-PR row. The line `if states.get(...) & {"OPEN", "MERGED"}:` is
  unchanged, because 99-handback-idle.sh's `merged` mutant anchors on it.
- Rows marked `merged=1` become the `merged-runs` cause (action
  `resume_merged`). It calls `lane_requests_of` (no second attribution
  reader) and resumes only when nothing is in flight and `RKEY` is non-empty,
  meaning at least one finished run is newer than the last session log. The
  marker is `merged-runs-<name>-r<RKEY>`, once per result set. It is
  uncounted (the attempt counter is put back) and does not touch the strand
  or idle counters, same as `draft-strand-runs`.
- `list` says why it declined a merged lane: in flight, or no new runs
  ("done").
- The runs table moved out of `resume_strand` into `runs_text`, which
  `resume_merged` also uses. The draft brief's output is unchanged.

## Proof

`selftest.d/99-handback-merged.sh` checks cases (1)-(4) from the brief. Each
case also asserts the `list` reason line. "Not resumed" on its own would pass
on a file that never looks at merged lanes, so the reason line is what shows
the new code ran and declined for the right reason. It also has four mutants
(no merged emission, a non-result-set key, no in-flight gate, no new-run
gate), and all four go red.

Against **this branch's** `handback.sh` (all eight 99-handback-* fragments,
run through a small runner that sources the selftest prologue):

```
  ok   (1) merged PR, row live, a run finished since its session: resumed
  ok   (1)   on merged-runs
  ok   (1)   with the result in its brief
  ok   (1)   without spending an attempt
  ok   (1)   a lane with an OPEN PR beside its merged one is left to the draft pickups
  ok   (1)   and nothing is commented, there being no open PR
  ok   (2) the same runs, a tick later: not again, keyed on the result set
  ok   (3) a request of its own still queued: waiting, not resumed
  ok   (4) no run newer than its last session: done, not resumed
  ok   mutant 'nomerged' ... (red, as it must be)   [and rekey, inflight, norkey]
selftest: 269 passed, 0 failed
```

Against **origin/master's** `handback.sh` (49ca6d319d), with the same
fragment and the rest of the tree unchanged:

```
  FAIL (1) merged PR, row live, a run finished since its session: resumed
  FAIL (1)   on merged-runs
  FAIL (1)   with the result in its brief
  ok   (1)   without spending an attempt
  ok   (1)   a lane with an OPEN PR beside its merged one is left to the draft pickups
  ok   (1)   and nothing is commented, there being no open PR
  FAIL (2) the same runs, a tick later: not again, keyed on the result set
  FAIL (3) a request of its own still queued: waiting, not resumed
  FAIL (4) no run newer than its last session: done, not resumed
  FAIL mutant anchor ... no longer matches handback.sh   (x4)
```

The three sub-checks under (1) that pass on master are guards: nothing is
commented, no attempt is spent, and an OPEN+MERGED lane is left alone. They
are not the cases the brief asks for.

Full `bash docs/testing/jobs/selftest.sh` after merging origin/master
(6e4dee6a28): **2130 passed, 0 failed**. At the original base (49ca6d319d),
one check in `66-status-titles.sh` failed: `fold`, "4 folded (4 rows), 10
shown". It fails the same way with that fragment run on its own, and
master's `001b8166c0` (the titles05 fixture gets its own registry) fixes it.
It was not caused by this change.

## For the next lane

- A full selftest takes over 10 minutes. To iterate, source lines 24-99 of
  `selftest.sh` and then only the fragments you need.
- `host-tools/harness_health.py`'s `merged-unwoken` check was the interim
  mitigation. Once this is live it should be quiet, and it can be retired.
