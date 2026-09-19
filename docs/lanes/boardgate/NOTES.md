# lane.boardgate

## Why attempt 3 did not finish, and what attempt 4 did

Attempt 3 **did** finish its brief: selftest green, master merged, pushed,
`gh pr ready 124`, `harness` label on. What stopped the PR was the fold job,
not the lane. Between attempt 3's merge and the fold, PR #136 landed as
`f53f3f66c2` and split `selftest.sh` into `selftest.d/NN-*.sh` fragments, so
the 128-line block this lane had appended to `selftest.sh` conflicted with a
file that no longer held any checks at all. The fold job resolves nothing and
handed #124 back as `needs-rebase`. The resume brief for that state was
written after attempt 3 ended, so attempt 4 is the first to see it.

Attempt 4 is a **move, not a rewrite**:

- `git merge origin/master` conflicted only in `selftest.sh`. Resolution:
  master's `selftest.sh` verbatim (the fixtures, the shims, the fragment
  loader, the tally) and the 128-line block carried **byte-identical** into
  `docs/testing/jobs/selftest.d/97-board-gate.sh` behind a header in the
  other fragments' shape. Verified by extracting the block from the HEAD
  side of the conflict and `diff`-ing it against the `+` lines of
  `git diff <merge-base> HEAD -- selftest.sh`: identical, 128 lines.
- Master moved three commits (`912f58a1c1`, the #117 fold) *during* the
  merge, which made `git diff --cached origin/master` show two doc files as
  deleted. Nothing was deleted; a second `git merge origin/master` brought
  them in and the diff against master is exactly this lane's three files.
- `board.sh` did not conflict: master has not touched it since the
  merge-base.
- `.scratch/falsify.sh` and `.scratch/mutants.sh` (still uncommitted scratch)
  now extract the block from the fragment instead of `selftest.sh`. Both
  layers reproduce the tables below unchanged: 14/14 flip against
  `origin/master`'s `board.sh`, and every mutant trips its named check with
  the cap mutant tripping two.
- Full `selftest.sh` on the merged tree: **138 passed, 0 failed**, the 14 in
  the last section.

The lesson this time is the one #136 already drew: a check appended to a
shared file is a hand-back waiting to happen. New checks go in their own
fragment, and the PR body's `Files:` line has to name the fragment.

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

Re-run on the **merged** tree (attempt 3, after `origin/master` came in), which
is the only version of this measurement that describes the code being reviewed:

```
capacity: 5/11 lanes running, startable issues:
#93 #92 #91 #89 #88 #86 #85 #84 #79 #77 #65 #62 #60 #59 #53 #50 #43 #38 #34 #31 #13 #10
ready PRs with no state label:
#134 #122 #117 #115
```

Same 22 issues; the lane count and the PR list both moved, as they should on a
live fleet. #129 and #128 have since been labelled and are correctly gone;
#134 is new and correctly present. The trigger tracks state rather than
reporting a fixed list.

## Falsification, in two layers

The block is **14** checks, not the thirteen an earlier commit message and an
earlier draft of these notes both said.

### Layer 1 — against the code being replaced

`.scratch/falsify.sh` (scratch, not committed) extracts the block from the real
`selftest.sh` by its section header — so the falsification cannot drift from
what CI runs — and executes it twice against two directories of symlinks to
`jobs/`, one with this branch's `board.sh` and one with
`git show origin/master:…`. Result: **14 passed / 0 failed** on this branch,
**0 passed / 14 failed** against master. Every check flips.

**This layer is weaker than its 14/14 looks, and the weakness is worth
naming.** All 14 go red for the *same* reason: master's `board.sh` has no
`gate` argument, so it falls through to a board worktree it cannot create and
dies. That shows the checks need the new code. It does **not** show that any
individual check pins the behaviour its name claims — 14 checks that only
detected "board.sh is the old one" would produce an identical table.

### Layer 2 — one mutant per invariant

So `.scratch/mutants.sh` breaks the **new** `board.sh` one invariant at a time
and requires the named check to go red *and the other thirteen to stay green*:

| mutant | named check goes red | other checks |
|---|---|---|
| drop `needs-rebase` from `STATE` | yes | all green |
| drop the `isDraft` skip | yes | all green |
| stop sourcing `$WORK/limits.env` | yes | all green |
| `lanes < LANE_MAX` → `true` | yes | **one more**, see below |
| `SKIP_PREFIX` loses `blocked:` | yes | all green |
| `SKIP` gains `harness`/`dispatchable` | yes | all green |
| the no-gh `NOTE:` becomes a bland line | yes | all green |

The cap mutant trips two checks, and that is correct rather than sloppy: two
checks assert the cap is honoured, one at the default and one at a raised
`LANE_MAX`, so a cap that is ignored must fail both. The script refuses to
score a mutant whose `sed` matched nothing, because a mutant that changed no
bytes passes everything for free and reads exactly like a specific check.

### How the falsification is run, which is the part attempt 2 got wrong

`falsify.sh` and `mutants.sh` **never write to `docs/testing/jobs/board.sh`**.
They build a directory of symlinks to `jobs/` and swap the one file inside it.
Both scripts end by printing `git status --porcelain` for the real path, which
must be empty. Attempt 2 instead redirected `git show origin/master:…` over the
real file and ended before restoring it — see the section at the top.

## Not done / out of scope

- `jobs/roles/board.md` is untouched, as the brief instructs — its Dispatch and
  Labels bullets already say what to do once woken.
- The real tick path (`fleet.py`, `check_coverage.py`, `run-claude-job.sh`) is
  not exercised by the selftest; only the shared predicate and the positive
  half are. Running the whole tick would need a board worktree in the real
  repo and could spend a model session, which a selftest must not do.
