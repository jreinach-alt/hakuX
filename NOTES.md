# lane.boardgate

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
