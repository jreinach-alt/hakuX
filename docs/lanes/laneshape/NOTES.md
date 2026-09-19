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

**Superseded 2026-09-19 22:24Z, and the reason is worth reading.** This
section said the change unblocks `2026-09-19-gl-pad-bit-write-side.json`,
registered 16:48Z on `claude/docs-tooling-agentic-coding-u152m1` after the
watermark, and invisible to the arms job for as long as its branch was not
`lane/*`. PR #162 **merged at 22:24Z**, so that prediction is now on
`origin/master` and `arms.sh` collects it from the trunk, by the old code, on
its next tick. The queue that was closed to that lane opened by the fold
instead.

What did NOT change: the branch `claude/docs-tooling-agentic-coding-u152m1`
still exists on origin, `lane.remote` still lives there, and its next
prediction -- pushed to that branch before its next PR merges -- is
uncollectable again on master's code. The defect is the prefix, not that one
file; one folded PR does not retire it. The only thing that expired is this
lane's ready-made example, and it expired by being fixed the slow way.

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

**Items 1 and 2 have landed; only 3 is open.** Re-read at `origin/board`
wave 126 (2026-09-19T22:20Z) during the pass-1 remediation:

1. ~~Write `[lane.laneshape]`~~ **DONE.** The row exists and claims
   `docs/lanes/laneshape/NOTES.md`, `docs/testing/jobs/arms.sh`,
   `docs/testing/jobs/remote-lane.sh` and
   `docs/testing/jobs/selftest.d/98-lane-shape.sh`. The other four paths this
   PR touches (`fold.sh`, `handback.sh`, `lane.sh`, `fleet.py`) stayed with
   their holders, which is the right answer and is what the surgical diffs
   were for.
2. ~~Classify #164~~ **DONE.** `[issue.164]` is in `nv2a_issues.toml` at wave
   126 with `disposition = "defect"`, so the `coverage` gate is no longer
   failing for an unclassified row and `[lane.clrpad164]` (PR #172) holds it.
3. **Still open**, and it is the only one: add
   `remote = "claude/docs-tooling-agentic-coding-u152m1"` to `[lane.remote]`.
   That row at wave 126 carries `issues`, `files` and `note` and no `remote`.

The original text of 1 and 2 is kept below for the record.

1. Write `[lane.laneshape]` with these files (or say which to drop and this
   lane will drop them).
2. Classify **#164** in `nv2a_issues.toml` (opened 18:57Z by the owner, "GL:
   the clear half of #59's write side is unported"). It is the only thing
   failing this branch's `preflight.sh`: `coverage` FAILs on an unclassified
   row, and `nv2a_issues.toml` is a file no lane may edit, so this is
   AGENTS.md's "a lane cannot satisfy a gate it is barred from fixing"
   exactly. `--allow-tracker` does **not** clear it -- that flag licenses a
   checkout that *edits* the board (a gate this branch already passes); the
   coverage FAIL is a different step. Every other preflight gate on this
   branch is green, `territory` included.
3. Add to `[lane.remote]`:
   `remote = "claude/docs-tooling-agentic-coding-u152m1"`.
   Nothing else on the row changes. Until it lands, `fleet.py` still reports
   `remote` as a claim with no agent and `fold.sh` has nothing to exempt --
   both are the pre-change behaviour, so the marker's absence is safe, just
   not useful.

## Two things this lane got wrong, and how they were caught

**1. `arms.sh state` stopped being read-only.** The first version built the PR
map in every mode, so on a host where `gh` answers nothing the WARNING line
landed on stdout *ahead of* the `STATE=` line -- and `94-arms-label-state.sh`
reads it with `sed -n 1p`. One existing check, "verified and regressed are
never both live", went red and that is the only reason it was found; reading
the diff would not have shown it, because the defect is in a mode the diff
does not mention. `state` now skips the PR map and the fetch, which its own
header already promised. Two legs in `98-lane-shape.sh` state the invariant
from this side; verified against the intermediate commit, which makes 1 gh call
in `state` mode where the fixed one makes 0.

**2. `git add -A` committed 504 scratch files**, including a 4 MB tar of
master's `docs/testing` built for the old-code verification run. Caught by the
merge's status output. The branch was rebuilt from `origin/master` with only
the eight intended paths and force-pushed -- permitted here because no
prediction names any sha on it and no other agent is on it. **Stage by name in
a worktree that holds scratch.**

## Remediation after audit pass 1 (2026-09-19)

`docs/audits/2026-09-19-laneshape-pass1.md`: 2 HIGH, 3 MEDIUM, 4 LOW. All five
HIGH/MEDIUM are fixed here, each with a leg. Both HIGHs were the same species
of mistake and it is worth naming it before the details: **a widened reach was
shipped without widening what could go wrong with it.** H1 added named
refspecs to a fetch that previously could not fail on a name; H2 added three
guards on top of a read whose third outcome nothing had looked for.

**H1 -- one open PR with an absent head branch aborted the whole fetch.**
`git fetch` fails the entire invocation when any *named* refspec matches no
remote ref, and updates **nothing**: not the other named specs, not the
`lane/*` wildcard, not `$TIP`. One PR from a fork (`headRefName` is a branch
in the *head* repository, not on origin) or one open PR whose head branch
somebody deleted would therefore have staled every ref `collect()` walks,
master included, for as long as that PR stayed open -- every prediction
registered after that moment invisible to the queue, with one WARNING in
`$WORK/logs/arms/tick.log` and nothing else. That is a larger outage than the
one this lane was opened to fix. Three changes, and each is load-bearing:

1. **The PR heads are fetched as `refs/pull/<n>/head`**, not
   `refs/heads/<branch>`. That ref exists for an open PR from a fork, and it
   survives the head branch's deletion. The number was already in the map --
   the same `gh pr list` call carries it for `pr_for()`. It is also now the
   field that is *validated*, because it is the field that enters a refspec.
2. **The trunk and `lane/*` are fetched FIRST, in a separate invocation** that
   contains no name that can be missing. Whatever the PR fetch does, master's
   tracking ref has already advanced.
3. **A batch PR fetch that fails retries one spec at a time**, so one bad ref
   costs its own PR head and not the other seven. The ordinary tick is still
   one round trip; the N fetches happen only on a tick that has already
   failed.

The destination is `refs/remotes/pr/<n>`, a namespace of its own, and not
`refs/remotes/origin/<branch>`: a fork's head branch name is chosen by a
stranger, and a fork PR whose head is called `board` would otherwise have
overwritten `refs/remotes/origin/board` -- which is where every job reads the
board. `collect()` still labels the source with the *branch*, because
`pr_for()` keys the PR map on it.

Legs: an open PR (#778) whose head exists nowhere on the fixture origin, with
checks that `refs/remotes/origin/master` still advances to the sha pushed
during that tick, that the prediction pushed to master in that tick is
collected, that the *other* PR's head is collected too, and that the tick
names the ref it could not fetch. Plus the leg that makes those meaningful:
the consumer is asserted to be *behind* origin/master before the tick, because
against an already-current tracking ref they are green for a fetch that did
nothing.

**H2 -- `board_files.load` has three outcomes and this read reported two.**
When `git show origin/board:territory.toml` fails -- the ref not fetched, a CI
checkout, a fresh clone, a timeout -- `load()` falls back to the **in-tree**
copy and returns it *successfully*. That copy is not incidentally stale, it is
structurally stale: it reaches a tree only when a later fold carries it over,
and it was 31 waves and a day behind on the day this was written. So it is
exactly the copy guaranteed **not** to carry a `remote` marker the board has
just added -- and the old `remote_readable` could not tell it from a clean
board read. All three guards would have passed, at the same moment, in the
same unsafe direction, on a map missing the one row they exist for: `fold.sh`
deleting a live cloud lane's branch, `lane.sh` starting a second agent on it,
and `handback.sh`'s defence-in-depth (which *is* `lane.sh`) going with it.

`remote_source` now names the outcome -- `board` / `worktree` / `unreadable` --
and `remote_authoritative` is rc 0 only for the first. `fold.sh` and `lane.sh`
ask *that*, not `remote_readable`, because their question is about an
**absence**: "no row names this branch". Three details:

- **A row present in the stale copy is still true.** Only absence is unsafe,
  which is why `handback.sh` -- which reads a positive, "some row names this
  branch" -- is left asking the map directly and is still sound. The two
  guards now fail differently on purpose: one question each.
- **`HAKUX_BOARD_REF=` reads as `board`.** A host that switched the board
  branch off deliberately has made the in-tree file the board *by
  configuration*; refusing there would stop every lane for a fault that does
  not exist. The state being refused is a board ref configured and not
  fetched.
- **The refusal names its cure**, `git fetch origin board`, because a refusal
  nobody can act on is a refusal somebody deletes. `board.sh` already fetches
  it before re-execing these jobs (`board.sh:161`), so the host path is
  unaffected.

Legs: the helper's three states asserted separately (including that the
fallback still *parses*, so the states really are three); `fold.sh prune
--apply` with the board ref pointed at nothing keeps `lane/third`, which the
fold-lagged copy does not name; `lane.sh resume alpha` in the same state exits
**76** and creates no worktree. And the closing check against the real board
no longer asserts "the read succeeded" -- it asserts that `remote_source`
names one of the two live answers and that `remote_authoritative` **agrees
with that name**, which is the whole guarantee. That check is honest in CI,
where the checkout legitimately has `origin/master` and not `origin/board` and
so legitimately reads `worktree`; the old one passed there by quoting a
fold-lagged read as a live one, which is the defect itself.

**M1** -- merged `origin/master` and resolved `lane.sh` by hand; master had
moved a `. "$JOBS/window.sh"` onto the same line this branch sources
`remote-lane.sh`. Both are kept. `refuse_if_remote` is still the first
statement of `start` and of `resume`, ahead of every side effect.

**M2** -- see the section below; re-measured once, at a named tip, and the
three places now agree.

**M3** -- the `86-fold-regressed.sh` section is struck through *at its
heading*, with the commit and the CI runs that make it history.

**L1/L2** -- `p["remote"]` is now read: READY, NOT FOLDED prints `elsewhere`
for a remote lane's PR instead of `finished`, which is the one word in that
column meaning "the local unit is gone" and is wrong for a lane that never had
one. **L3** -- the REMOTE LANES comment now says a remote lane's PR *can*
still raise a FAIL through `unfolded`/`waiting`, which it should; what the
section declines is a permanent line about the lane itself. **L4** -- the
`REMOTE LANES (2)` check is renamed to describe what it asserts.

### The remediation's own falsifier

A leg added to fix a defect has to be shown failing against the code that had
the defect, and for H1 and H2 that code is **not master** -- master has no
`remote-lane.sh` and fetches no PR heads, so it cannot exhibit either bug.
The falsifier is this branch's own pre-audit tip.

Same procedure as the master measurement, `git archive 8b185a925f
docs/testing` into a scratch tree with this fragment dropped in:

> **Against `8b185a925f`, 16 of the 61 fail; 45 pass.**

All 16 are H1's and H2's, and nothing else moved -- which is the other half of
the claim, because a remediation that silently changed a fourth job would show
up here as an unexplained failure. Of the 16:

- **14 are behaviour.** The trunk fetch not being staled by an absent PR head
  and the prediction pushed to master in that tick being collected; the PR
  head landing in `refs/remotes/pr/<n>`; the tick naming the ref it could not
  fetch; the helper's `worktree` / `board` / authoritative distinction in all
  four of its configurations; `fold.sh` keeping `lane/third` and `lane.sh`
  exiting 76 on a fold-lagged read; and the closing check that
  `remote_authoritative` agrees with `remote_source` rather than with the read
  merely succeeding.
- **2 moved with the refusal text**, not with behaviour: "lane.sh refuses when
  territory.toml cannot be read at all" and fold.sh's "and says that is why"
  now grep for `board read came back`, where the old message said
  `territory.toml could not be read`. The old code did refuse in that state.
  Naming which source it got is part of the fix -- a refusal that does not say
  whether the board was stale or absent cannot be acted on -- but these two
  are text legs and counting them as new behaviour would be a curve fit.

**One self-inflicted regression, caught by the gate.** The first draft of the
`handback.sh` comment above quoted `"$LANE_SH" resume` while explaining the
depth argument, and `99-handback-draft.sh` counts that exact string to prove
there is **one** call site. The count read 2 and the check went red. A grep
anchored on a call matches the prose too; the comment now describes the call
without spelling it, and says why.

## Checks that do NOT fail against master, and why that is correct

**One number, measured once, at a named tip.** Pass 1 found three mutually
inconsistent counts here (19, 25-of-39, 25-of-41), reconciled by arithmetic
rather than by a re-run -- which matters more than a stale number usually
would, because *the count is the evidence*. It has been re-measured, at
`origin/master@11ddd94a66` (the current trunk, which is also what this branch
is merged up to):

> **`98-lane-shape.sh` contains 61 checks. Against master's code, 43 fail and
> 18 pass.**

Procedure, so it can be repeated: `git archive 11ddd94a66 docs/testing | tar
-x` into a scratch tree, copy *this branch's* fragment into that tree's
`selftest.d/`, run that tree's `selftest.sh`, and count the `ok`/`FAIL` lines
between the `== a lane is a branch...` header and the next fragment's. 43 + 18
= 61; the enumeration below is of all 18.

The rule is that each new check must fail against the code it replaces. The 18
that cannot are these, by name:

- **Must-not-move legs** (6). An ordinary folded `lane/*` branch is still
  deleted; a local lane with no unit is still a claim with no agent;
  `lane.sh resume alpha` is not refused by the remote guard and reaches its
  own "no worktree" answer; a remote lane's handed-back PR started nothing
  locally on master either, even with a worktree and a brief on this host
  (master has no local lane for a `claude/*` head). By construction these pass
  on both sides -- that is what makes them the control, and without them a
  widened exemption would look exactly like a working one.
- **The negative half of a pair** (7). "a row with no `remote` names no
  branch"; "an unreadable board is reported as unreadable"; "an unreadable
  board is not authoritative either"; "its b_ref counts as live"; "so it is
  not queued"; "it creates no worktree on the way out" (twice, in `lane.sh`'s
  two refusals). Each is paired with a positive check that does discriminate.
  Alone, every one of them is green against a tree with no `remote-lane.sh` in
  it at all -- a failed `source` leaves the function undefined,
  command-not-found returns 127, and `!` turns that into a pass. That is
  precisely why none of them stands alone.
- **The two `arms.sh state` legs** (2). They discriminate against this lane's
  own intermediate commit, not against master, because master's `state` makes
  no gh call either. Regression guard for defect 1 above.
- **The two H1 trunk legs and their control** (3). "the arms consumer is
  behind origin/master before the tick", "an open PR whose head is absent from
  origin does not stale the trunk fetch", "so a prediction pushed to master in
  that tick is still collected". Master cannot fail these because master
  fetches no PR heads at all: H1 was a defect **this branch introduced**, so
  its falsifier is this branch's own pre-remediation tip `8b185a925f`, not
  master. The first of the three is a fixture precondition and passes
  everywhere by design; it is there because without it the other two are green
  for a fetch that did nothing.

Both HIGH remediations were therefore measured against the tip that had the
defect, not only against master -- see the pre-remediation numbers in the
remediation section above. A leg whose only falsifier is a tree missing the
file it tests has been tested against very little, and saying which legs those
are is the difference between 61 checks and 61 claims.

## ~~Not mine: `86-fold-regressed.sh` is red on master~~ -- SUPERSEDED 2026-09-19, FIXED

**This section is history, not a live blocker, and nothing below it is asking
anybody for anything.** `lane.selftest86` took the defect and fixed it exactly
where this section said it lived -- one line in the fixture, recreating the
local ref `fr_reset` assumed survived the fold. It folded as `bb4b78689e`
(PR #167, 19:47Z) and master's `jobs selftest` workflow has concluded
`success` on every head since: `bb4b78689e`, `3b27da7a3e`, `f5d40ca778`,
`6675e6414b`. The last red master head was `f7be6e68cb` at 18:42Z.

The sentence at the end of this section -- "CI is the gate of record, so this
holds up every fold until someone owns it, including this PR's" -- was true
when it was written and stopped being true at 19:47Z the same day. It is
struck through in place below rather than withdrawn in a footnote, because a
withdrawal at the bottom of a long file leaves the claim at the top still
asserting itself, and a reader acting on this one would dispatch a lane at a
defect that is already fixed.

The diagnosis is kept because it is the record of what happened and it is what
`lane.selftest86` confirmed; only the tense is wrong.

---

`selftest.sh` reported 11 failures on this branch. **10 of them were
master's**, in `86-fold-regressed.sh`, and reproduced exactly when master's own
`docs/testing` is unpacked into a scratch tree and run there -- which is how
they were separated from this lane's, rather than assumed to be somebody
else's.

The diagnosis, since it is two commits and nobody has written it down:

- `a4fcced05a` (`lane.branchprune`, 01:07) added
  `prune_branch "$WT" "$branch" HEAD` at `fold.sh:603`, so a successful fold
  now deletes the lane branch -- on origin, the tracking ref, **and the local
  head**.
- `4eb641e777` (08:03) is the fold of PR #145, `lane.foldregress`, which added
  `86-fold-regressed.sh`. Its fixture's `fr_reset` re-pushes with
  `git push -f origin master lane/foldreg` after every tick. That branch no
  longer exists locally once a tick has folded, so `fr_reset` fails with
  `src refspec lane/foldreg does not match any` and every later check in the
  fragment runs against a fixture that was never reset.
- `a4fcced05a` is an ancestor of `4eb641e777`, so the fragment was written
  against a `fold.sh` that pruned nothing and went red on its first run on
  master. Master's `jobs selftest` workflow has been failing since that
  commit.

The fix is one line in the fixture (recreate the local branch in `fr_reset`,
e.g. `git branch -f lane/foldreg <sha>` before the push), not in `fold.sh` --
the prune is doing exactly what it was written to do. `fold.sh` is
`[lane.branchprune]`'s and `86-fold-regressed.sh` is `[lane.foldregress]`'s,
so this is reported here, not fixed here. ~~**CI is the gate of record, so
this holds up every fold until someone owns it, including this PR's.**~~
**No longer true as of 19:47Z on 2026-09-19: `bb4b78689e` fixed it, in the
fixture, in that one line. See the heading.**

The 11th failure was this lane's and is fixed; see above.

## What the next lane should not repeat

- Do not try to fix this by renaming the branch. `fold.sh:141`'s prune path
  targets `lane/*`; renaming would put a cloud container's tracking branch in
  the delete path, and GitHub cannot retarget a PR's head so #162 would have to
  be closed and reopened.
- Do not add a second `branch` field beside `remote`. Two fields that can
  disagree is a mechanism; the value *is* the branch.
- Do not make `LANE_MAX` count remote lanes by adding a tally. See above.
