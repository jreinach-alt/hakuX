# lane.boardgate

## Why attempt 2 did not finish, and what it left behind

Attempt 2 did essentially all of the work and then ended **inside the
falsification run**, one command short of the restore. Attempt 3 found:

- `docs/testing/jobs/board.sh` in the working tree **byte-identical to
  `origin/master`** (md5 `7d2566df…`). The `git show origin/master:… > …` half
  of the falsification had run; the `git checkout HEAD -- …` half had not. The
  fix survived only because it was already committed as `dda25c4596`, with an
  identical copy at `.scratch/mine-board.sh`. Had the session ended a few
  commands earlier, the tree would have looked like a finished lane and
  contained none of the change.
- `selftest.sh`'s 127-line block **uncommitted**, so the branch carried the fix
  with no test of it.
- PR #124 still a **draft**, which is the one thing that makes a finished lane
  invisible: the fold job only considers non-draft PRs, and the board job that
  would resume the lane is the very job this lane is fixing.

**The lesson worth keeping: a falsification run leaves the tree holding the
code you are replacing, and that is indistinguishable from never having done
the work.** Do the swap and the restore in one command, or commit first and
falsify from a scratch copy — `.scratch/` already had both files side by side,
so nothing needed the real path to be overwritten at all. Verify with
`git status` immediately after, not at the end of the session.

## The defect

`docs/testing/jobs/board.sh`'s gate had two inputs and both are error reports:
`fleet.py`'s `FAIL` lines (a lane stuck, reported-not-folded, waiting) and
`check_coverage.py` (the tracker disagreeing with GitHub). Neither can say
*"there is capacity and there is work"*, so a **healthy** board dispatched
nothing — and this job is the only actor permitted to label an issue
`dispatchable` or call `lane.sh start` (design §4). Six consecutive ticks
(03:25–05:10Z) logged `nothing actionable` with 29 issues open, 0 lanes running
against `LANE_MAX=4`, and both handhelds attached and idle.

## What I built

Two positive triggers in a `positive_gate()` beside the two negative ones, and
one shared predicate `nothing_actionable()` that the tick and the new
`board.sh gate` subcommand both use.

- **capacity** — `lanes_running < LANE_MAX` and at least one open issue is
  startable: no `lane:` label, no `claimed:cloud`, and none of `blocked:*`,
  `decision-needed`, `upstream`, `unmodellable`, `xbox-hardware`,
  `harness-status`. `dispatchable` is deliberately **not** required; requiring
  it would be as circular as the gate it sits beside, since only this job may
  apply it.
- **labels** — a PR that is out of draft and carries none of `needs-audit-1`,
  `needs-audit-2`, `needs-remediation`, `fold-ready`, `folded`, `needs-rebase`.

Both feed new sections of the brief the job already writes, so the model knows
which of the four gates woke it.

## Things the next lane should not have to re-derive

- **`python3 - <<'PY'` spends stdin on the script.** My first version piped
  `gh --json` output into `board_filter` and read `sys.stdin`; the heredoc won,
  the filter saw the *script* as its input, and every case returned nothing.
  The gate read exactly like "no work" — the defect it was written to fix,
  reproduced inside the fix. It only showed up because the scratch driver
  asserted on the *content* of the output, not just on the exit status. The
  JSON now arrives as `argv[2]`.
- **Assert on output, never on the exit status alone.** Half of these cases
  expect "no trigger", and `origin/master`'s `board.sh` — which has no `gate`
  argument at all — also exits non-zero (it falls through to its worktree
  setup and dies). An exit-code-only check passes against the file being
  replaced. Every check in the new block greps the output.
- **`HAKUX_REPO_DIR` is pinned to a nonexistent directory** in the selftest's
  `bgate()`. That pins the claim that the gate needs no tree, *and* it is what
  makes the falsification run safe: the old `board.sh` cannot fetch, so it
  cannot reach `run-claude-job.sh` and spend a model session.
- **`needs-rebase` counts as a state label.** The lane owns that fix. If it
  didn't count, a PR waiting on its own lane would wake the board every twenty
  minutes forever — this defect with its sign flipped.
- **The gate fails quiet, not loud.** No `gh`, no network → no trigger, plus a
  one-line `NOTE:` so six quiet ticks are never unexplained again. A gh outage
  that woke a model tick every twenty minutes would cost more than the idleness.
- **Do not edit `selftest.sh` while a run is in progress.** bash reads the
  script lazily by byte offset; inserting a block shifts every later offset
  under the running process. Four lanes were running `selftest.sh`
  concurrently tonight and a full run took minutes, which makes the
  temptation real.

## The gate against live GitHub state, 2026-09-19T23:2xZ

`board.sh gate` run against the real repo (three read-only `gh` calls):

```
capacity: 10/11 lanes running, startable issues:
#93 #92 #91 #89 #88 #86 #85 #84 #79 #77 #65 #62 #60 #59 #53 #50 #43 #38 #34 #31 #13 #10
ready PRs with no state label:
#129 #128 #122 #117 #115
```

22 startable issues and 5 ready PRs the board owes a label, at an instant when
the old gate would have logged `nothing actionable` if `fleet.py` and
`check_coverage.py` were clean. The five PRs that *are* drafts right now (#130,
#127, #126, #124, #123) are all correctly absent — and #128 flipped to ready
between two `gh` calls a minute apart, so the `isDraft` filter is confirmed on
live data and not only on fixtures.

**`LANE_MAX` is 11 on the host, not the 4 the brief states.** The brief's figure
was already stale; the code reads `$WORK/limits.env`, so this needs no change,
but anyone reasoning from "4" should re-read the file.

## Falsification against the code being replaced

`.scratch/drive.sh` (scratch, not committed) ran the six gate cases against
`git show origin/master:docs/testing/jobs/board.sh`. Every case printed
`cannot create .../board-wt` and `rc=1`: no `#120`, no `0/2 lanes running`, no
`no positive trigger`. All thirteen new checks go red.

## Not done / out of scope

- `jobs/roles/board.md` is untouched, as the brief instructs — its Dispatch and
  Labels bullets already say what to do once woken.
- The real tick path (`fleet.py`, `check_coverage.py`, `run-claude-job.sh`) is
  not exercised by the selftest; only the shared predicate and the positive
  half are. Running the whole tick would need a board worktree in the real
  repo and could spend a model session, which a selftest must not do.
