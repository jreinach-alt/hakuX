# lane.laneshape -- a lane is a branch with an open PR, not a branch named `lane/*`

Brief: `briefs/laneshape.md`. Issue: none (harness defect, dispatched directly).
PR #163.

## What was wrong

Four jobs tested `lane/*` when what they meant was "a branch a lane owns". The
one real lane that does not use the prefix -- `lane.remote`, a cloud session on
`claude/docs-tooling-agentic-coding-u152m1`, PR #162 -- was invisible or
second-class to all four. The prefix is a proxy, and it failed on exactly the
lane it was not written for.

## The decision the brief left open: PRs, not territory rows

The brief let `arms.sh` collect from "every branch with an open PR" **or**
"every branch named by a territory row". It collects from **master, every
branch with an open PR, and (still) every `lane/*` branch**.

Why not territory rows. A territory row does not name a branch. Measured
against `origin/board` at wave 122: the only keys any `[lane.*]` row carries
are `files`, `issues`, `note` and `standing`. "Every branch a row names" would
therefore have meant adding a branch field to every row and keeping it in step
by hand -- and a row whose field was never written would be silently
uncollectable in exactly the way the `lane/*` glob already is. That is the same
defect with a new spelling.

An open PR *is* the branch, machine-read, and it is the same fact this job
needs anyway: a verdict has to be posted somewhere, and for anything but the
trunk that somewhere is the PR. One `gh pr list`, two uses -- the collect set
and `pr_for()`.

The `lane/*` glob is **kept alongside** it rather than replaced. A lane that
pushes a prediction before opening its PR would otherwise become uncollectable
the moment this landed. The change only ever adds branches.

## The marker, and why its value is the branch

`remote` on a territory lane row. The brief specified `remote = true`; what
shipped accepts both spellings, and the one on `[lane.remote]` is the string:

```toml
[lane.remote]
remote = "claude/docs-tooling-agentic-coding-u152m1"
```

`remote = true` means the conventional `lane/<row name>` and is accepted
everywhere.

**A boolean alone cannot do items 3 and 4 of the brief.** Two of the consumers
are handed a *branch* and have to find the lane: `handback.sh` gets a PR's head
ref, `fleet.py` gets `headRefName`. `remote = true` on `[lane.remote]` answers
"is lane.remote elsewhere?" and cannot answer "whose branch is
`claude/docs-tooling-agentic-coding-u152m1`?". The brief's own text concedes
this -- "count PRs for any branch a territory row names" -- so the row has to
name one. Making the branch the marker's *value* keeps that to one field
instead of a `remote` plus a `branch` that can disagree with each other, and
the two facts are not separable anyway: a lane is remote precisely because it
lives on a branch this host does not drive.

### Where it is consulted

The brief's budget was three places. It is four, and the fourth is the one the
brief itself named as the hazard:

| where | what it does |
|---|---|
| `fleet.py` | counts its PR; never lists it under LANE CLAIMED WITH NO RUNNING AGENT; prints it under REMOTE LANES |
| `handback.sh` | hands back by comment naming its routine, never by `lane.sh resume` |
| `fold.sh` | never prunes its branch, even if it is someday named `lane/*` |
| `lane.sh` | **refuses to start or resume it** |

`lane.sh` is the hazard the brief singled out and is not really a fourth
consumer of the marker so much as the thing the marker exists to stop. One
function, `refuse_if_remote`, called from both `start` and `resume`: `start` is
the same accident by the other door (`lane.sh start remote <brief>` makes
`$WORK/wt/remote` and pushes to the same branch), and guarding one entry point
and not the other would be a gate with a hole in it.

`arms.sh` consults the marker **not at all** -- it reads the PR list, which is
why the marker did not have to exist for the arms half to work.

### One reader, four callers

`docs/testing/jobs/remote-lane.sh` is sourced by `fold.sh`, `handback.sh` and
`lane.sh`; `fleet.py` has the same rule in `remote_lanes()`. The board is read
through `board_files.py`, so it is `origin/board` and not a lane worktree's
fold-lagged copy. `HAKUX_TERRITORY` points it at one file instead -- that is
the selftest's seam, and it is a path rather than a mode flag so it cannot be
switched on by accident.

**A read failure is not "no remote lanes", and each caller fails in its own
direction** -- they are not the same direction:

- `lane.sh` **refuses**. "I cannot tell whether another agent holds this
  branch" must not be answered by starting one. Costs a dispatch; the other way
  costs a session's work.
- `fold.sh` **keeps the ref**. An un-pruned branch costs a few bytes.
- `fleet.py` reports as before.

A helper that returned an empty map on failure would have made all three
silently take the "no remote lanes" branch. That is this project's own recorded
mistake -- a guard that passes by early-returning on a missing precondition --
and it is why `remote_map` has a return code and `remote_readable` exists.

## What must stay true, and the leg that proves each

- **Nothing changes for a local lane.** `98-lane-shape.sh` checks that a local
  lane with no unit is *still* reported as a claim with no agent, that
  `lane.sh resume alpha` reaches its own "no worktree" answer untouched, and
  that an ordinary folded `lane/*` branch is *still* deleted. Those three are
  the must-not-move legs; without them the exemption could have widened and
  nothing would have noticed.
- **`LANE_MAX` still counts local units only.** A remote lane does not count
  against it. That is a small inaccuracy and it is left alone deliberately:
  unifying the two would mean inventing a second count, and "one number is not
  one count" is already a recorded lesson here. If it ever matters, the fix is
  to make `LANE_MAX` count *sessions*, not to add a remote tally beside it.
- **`fold.sh` still prunes `lane/*` and nothing else.** The remote test is an
  extra `return 1` after the existing `lane/?*` case, so it can only ever
  refuse.
- **The arms watermark still fences history.** The fixture puts a
  pre-watermark registration on the newly-visible branch; it is counted as
  history and not queued.

## What this unblocks, concretely

`2026-09-19-gl-pad-bit-write-side.json`, registered 16:48Z on
`claude/docs-tooling-agentic-coding-u152m1`, after the watermark. One pair, not
a backlog: everything else on that branch predates the watermark. The arms job
picks it up on its first tick after this folds **and** after the `remote` row
lands -- though in fact the arms half does not need the row at all, only the
open PR, so the queue opens the moment this merges.

## Two sessions on one branch, which this change cannot prevent

Already survived once today: two routines fired in the same minute and put two
sessions on `claude/docs-tooling-agentic-coding-u152m1`. The host session
disabled the duplicate by hand. Nothing here stops that -- the collision is
between two cloud routines and neither of them asks this host anything. **Do
not create a second routine on that branch.** The guard added here only stops
the *local* half of the same accident (`lane.sh` starting a third agent on it),
which is the half this host controls.

## The territory situation, which is a board item and not a lane's to fix

`territory.toml` on `origin/board` at wave 122 has **no `[lane.laneshape]` row
at all**, and every file this brief names is claimed by another row:

| file | claimed by |
|---|---|
| `docs/testing/jobs/arms.sh` | `[lane.armlabel]` (no open PR) |
| `docs/testing/jobs/fold.sh` | `[lane.branchprune]` (no open PR) |
| `docs/testing/jobs/handback.sh` | `[lane.draftstrand]` (PR #153, draft) |
| `docs/testing/lane.sh` | `[lane.windowbudget]` (PR #155, ready) |
| `docs/testing/fleet.py` | `[lane.toolsmith]` (standing) |

A brief that lists a file as "yours" is not the claim; the row is. This lane
could not write the row either -- a lane must never edit `territory.toml`.
The board request is below and on the PR. The diffs here are deliberately
surgical for that reason: one sourced helper, one `if` in `prune_branch`, one
early arm in `lane_name`, one guard function in `lane.sh`, and `arms.sh`'s
collect/`pr_for` pair. Two of the five holders have no open PR at all, so the
live overlap is with `draftstrand` (handback.sh) and `windowbudget` (lane.sh).

### The board-request channel does not work from a lane worktree

AGENTS.md says a lane asks the board by dropping
`$DISPATCH_DIR/board-requests/<lane>.md`. A lane session cannot write that
path: the sandbox permits its own worktree and nothing else, and `cp` into
`/home/justin/hakux-work/dispatch/board-requests/` is refused outright. So the
documented channel is a channel no lane can use, the same shape
`[lane.remotechannel]` is fixing for the delivery channel a cloud session
cannot open. This request is therefore in `NOTES.md` and in a PR comment, which
the board does read. Not filed as an issue -- a harness defect gets a briefed
lane, not a tracker row.

## Board request

1. Write `[lane.laneshape]` with these files (or say which to drop and this
   lane will drop them).
2. Add to `[lane.remote]`:
   `remote = "claude/docs-tooling-agentic-coding-u152m1"`.
   Nothing else on the row changes. Until it lands, `fleet.py` still reports
   `remote` as a claim with no agent and `fold.sh` has nothing to exempt --
   both are the pre-change behaviour, so the marker's absence is safe, just
   not useful.

## What the next lane should not repeat

- Do not try to fix this by renaming the branch. `fold.sh:141`'s prune path
  targets `lane/*`; renaming would put a cloud container's tracking branch in
  the delete path, and GitHub cannot retarget a PR's head so #162 would have to
  be closed and reopened.
- Do not add a second `branch` field beside `remote`. Two fields that can
  disagree is a mechanism; the value *is* the branch.
- Do not make `LANE_MAX` count remote lanes by adding a tally. See above.
