# lane.handback — an actor for a PR a job handed back

Base: `master` @ bdeab36f75, then merged forward three times. PR #132.

## Why this lane ran three times, which is the defect measuring itself

The fix was written and green in attempt 1. Attempts 2 and 3 were the
hand-back this lane exists to fix, applied to this lane, twice:

| when | what happened | left behind |
| --- | --- | --- |
| attempt 1 | the fix: `handback.sh`, the `fold.sh` cause record, the board rule, the checks | `38513ca6c8`, `3757960021`, `12e06ad68c` |
| 07:09Z | fold: `CONFLICT in: fold.sh selftest.sh` — #131 folded under it | `needs-rebase` |
| attempt 2 | merged `1f7572a34c`, resolved both, pushed, re-applied `fold-ready` | `ab1f7e67ad` |
| 07:42Z | fold: `CONFLICT in: selftest.sh` — #136 folded under it | `needs-rebase` |
| attempt 3 (this one) | merged `f53f3f66c2`, moved the checks into `selftest.d/99-handback.sh` | this section |

**Neither resumed attempt failed.** Attempt 2 did every step of its brief —
the 07:42Z hand-back is the fold job re-deriving the same verdict against a
master that had moved once more, not a defect in what attempt 2 did. That is
the reading to avoid, and the reason to write it down: `$WORK/attempts/handback`
reads `3`, and nothing in it distinguishes three dispatches from three
failures.

Two things follow that are worth more than this lane's own history.

The attempt counter counts *dispatches*, not *failures*, and `lane.sh`
escalates the model on the fourth. This lane is at 3 of 4 with nothing wrong
in it; one more fold under it and the actor I am adding would resume it onto
the escalated model, and the one after that would refuse and open a
`decision-needed` issue about a PR that has been correct throughout. That is
`lane.sh`'s policy and I did not change it — changing it is a different
lane's brief, and it should be one: **an attempt spent re-merging is not
evidence the lane needs a bigger model.** What was available to me is the
head-sha key, which at least charges each cause once rather than once a tick.

And the conflict was always on one path. #136 split `selftest.sh` into
`selftest.d/` fragments **because of these three hand-backs** — the causes
are in `$WORK/handback/cause/` and on this PR — and that split is the actual
fix for the rate. `handback.sh` is the fix for what happens *after* a
hand-back, which is a smaller and more permanent problem: conflicts will
still occur on files that cannot be split.

## The defect, restated

`fold.sh` labels a conflicting PR `needs-rebase`, comments naming the files,
and stops — which is right; a merge resolved by a script that does not
understand the code is how a working fix was reverted on 09-12. But
`needs-rebase` was set by one job, displayed by `status.sh`, and **acted on by
none**: `roles/board.md` had no rule for it, the board only wakes on a
`fleet.py` or coverage `FAIL`, and the lane it hands the PR back to is a
`systemd-run` transient unit that exited when its session ended.

## Where it goes, and why (the brief called this a judgement call)

**`fold.sh` records the cause; a separate script, `jobs/handback.sh`, is the
actor; `lane.sh resume` does the work.** Three reasons for the split, and one
reason for the invocation point.

`fold.sh` is the only thing that knows *which files conflicted* — nothing
downstream can re-derive it without doing the merge again — so it writes
`$WORK/handback/cause/<pr>-<head>` at the conflict, four lines, no action.
`handback.sh` quotes that file when it exists and works without it, which
matters because the PRs labelled `needs-rebase` by a fold from before this
change have no cause file and still need an actor.

Everything after that is a *different kind of job*. A script that merges has no
cap, no attempt counter and no model; a job that starts model sessions has all
three, and mixing them means `fold.sh list` can start a session (it already
posts comments — see PR #127 — so that is not hypothetical). Keeping them
apart also means the cap logic lives in exactly one place: `handback.sh` starts
nothing itself, and a selftest check asserts that no line of it reaches for
`systemd-run`. The actor is `docs/testing/lane.sh resume`, which already counts
the attempt, escalates to Fable on the fourth, and refuses past
`LANE_MAX_ATTEMPTS`.

It is **invoked at the end of the fold tick** (`bash jobs/handback.sh "$mode"`,
one line, beside the existing `status.sh` call) rather than getting its own
timer, because the fold timer is the one that is live: `hakux-cloud.timer` is
disabled by the owner and the board only wakes on a FAIL. The mode is passed
through so `fold.sh list` stays read-only and resumes nobody.

## One table, so merging with lane.auditoutlet is an edit to a list

`needs-rebase` is the fourth terminal label; `needs-audit-1`, `needs-audit-2`
and `needs-remediation` are the other three, and `lane.auditoutlet` (PR #130)
is building their actor under the same `LANE_MAX`. Its PR carries only
`NOTES.md` so far — its stated decision is "`cloud.sh` stays, as the one
dispatcher, on the lane path", with the mechanism still to land — so I wrote
the pickup the way the brief asked: **one table keyed by label**, not a branch
per label.

```
#   <label>  <action>  [<label that means this one is stale>...]
HANDBACK_ROWS=(
    "needs-rebase   resume_rebase   fold-ready folded"
)
```

An action is a shell function that prints the section appended to the lane's
brief. Everything else — deriving the lane name, resuming once per cause, the
cap, the attempt counter, the refusal paths — is written once, around the
table. So `needs-remediation` is one row plus one function.

I posted this shape on #130 before writing it, and said there that if their
dispatcher lands first I will move my row into it: the table and the loop are
the thing, not where they are invoked from. I touch neither `cloud.sh` nor
`board.sh`. We overlap on `roles/board.md` and `selftest.sh`, both
append-shaped.

## The two details the brief said decide whether this works or loops

**Resume only on a new cause**, keyed on the head sha the handback was found
at, the way `fold.sh` already keys `$F/failed/$pr-$head`: `$WORK/handback/done/
<label>-<pr>-<head>`. A lane resumed twice for one head re-reads the same
`NOTES.md` and the same diff and spends one of its four attempts doing it. When
the lane pushes, the head moves, and a fresh conflict is a fresh cause.

The head-sha key alone is **not enough**, and this is the loop it does not
catch: a lane that resolves its conflict pushes (new head) and re-applies
`fold-ready`, and may well leave `needs-rebase` behind — `fold.sh`'s candidate
query filters on `fold-ready`, so nothing forces it off. New head plus the
label still set reads as a new cause, and a second session lands on work that
is already back in the pipeline. Hence the third column of the table: a PR
carrying `fold-ready` or `folded` is skipped whatever its head.

**The lane name is not the PR.** `lane/<name>` → `<name>`; anything else stops
and says so on the PR once (not once per tick — the state does not change by
itself and the reader is a person). The two live counter-examples are both
handled by name: `lane/cloud-109` matches the shape but is a cloud session's
branch with no local worktree, and `roles/cloud.md` has cloud lanes remediate
themselves; `claude/hakux-...` is an interactive session's branch with no lane
at all. Guessing either one is a `lane.sh resume` that burns an attempt against
the escalation budget of a lane that does not exist.

## Three refusals that are not the same refusal

`lane.sh` exits 75 for two very different reasons and prints a different
sentence for each. Treating them alike is how this job would either loop or
re-park the PR:

| refusal | what it means | what handback.sh does |
| --- | --- | --- |
| `LANE_MAX=` | the fleet is at its cap; `lane.sh` checks this **before** `next_attempt`, so nothing was spent | says so in the tick log and writes **no marker**, so the next tick tries again |
| `LANE_MAX_ATTEMPTS=` | the escalated attempt failed too | marker (said once), label `blocked:needs-owner`, comment quoting the refusal; `roles/board.md` opens the `decision-needed` issue |
| anything else (rc≠75) | a host fault — no worktree, no brief | marker, comment quoting rc and the output; a push to the branch makes a new cause |

A fourth case is upstream of all three: a lane whose unit is **still active** is
not stalled, and `systemd-run --unit` on a live unit fails *after* `lane.sh` has
already counted the attempt. That guard is worth one of the four attempts, not
tidiness. No marker; the next tick looks again.

## The row that came back without the label it was filtered on

Attempt 3's merge turned up a defect in attempt 1's work, and it was the
`selftest.d` split that turned it up — so it is worth recording how, not just
what.

`fold.sh` now calls `handback.sh` at the end of every tick. `selftest.d/85-fold-ci.sh`
drives the real `fold.sh` through its own `gh` shim, and that shim answers
**every** `pr list` with one fixed row (`102 lane/foldci …`), because before my
change the only `pr list` in a fold tick was the candidate query. So every
`fold_tick` in that fragment now also ran a handback tick, which took the
fixture's row at face value and **resumed `lane.foldci` and commented on #102**.
Three of that fragment's checks went red: "it is said exactly once", "a run
still in flight is not commented on", "and that too is said exactly once".

The shim's indifference to `--label` is a fixture artefact. What it exposed is
not. `handback.sh` asked `gh pr list --label needs-rebase` and then trusted
that every row it got back carried that label — a server-side filter, never
re-checked. The failure mode if that filter does not happen is not an empty
list, which would be visible and harmless; it is **resuming, by name, whichever
lane owns the first open PR on the repository, against that lane's four-attempt
escalation budget.** A `--jq` typo is the live way to get there, and the NOTES
below already flag that `--jq` as the one surface no shim exercises.

So the fix is in `handback.sh`, not in the fixture: a row that comes back for
`--label X` without `X` in its labels is refused and logged with the labels it
did carry. `85-fold-ci.sh` is another lane's file and I did not touch it.

The check for this is the one place I had to think about what a negative
proves. Written with the row labelled `harness,fold-ready`, two of its four
checks passed against a build with the guard deleted — the *stale-label* rule
refused the row first and the guard never did any work. With the row labelled
`harness` alone, all four fail on that build. Measured both ways; the numbers
are in the table below.

## Evidence

The new checks drive the real `handback.sh` and the real `lane.sh` against
shims of their own. They have to be their own: the shared `gh` shim answers
every `pr list` with `[]` and the shared `systemctl` answers every `is-active`
with `active`, which are exactly the two answers that make this job do nothing.
`$HB/bin` holds `gh` (rows from a per-label TSV, comment *bodies* kept, labels
logged), `systemctl` (`$HB/active` is the set of running units) and
`systemd-run` (logs and exits).

The fragment holds 46 checks. Measured after the `selftest.d` move, all three
runs on the same host within the hour:

| `jobs/` under test | whole suite | this fragment |
| --- | --- | --- |
| this branch | **170 passed, 0 failed** | 46 / 46 |
| `origin/master` + only `selftest.d/99-handback.sh` | 140 passed, **30 failed** | 16 / 46 |
| this branch, unfiltered-row guard deleted | — | 40 / 46 |

Every one of the 30 failures against master is in this fragment; master's own
124 checks pass under it, which is the claim that the move changed nothing but
the file the checks live in. The falsification run is a real worktree at
`origin/master` with only this fragment copied in, so the checks run against
master's `fold.sh`, master's `roles/board.md`, and no `handback.sh` at all.

**The 16 that "pass" against master pass for nothing**, and it is worth being
explicit about that rather than counting them: they are the negative halves —
"a `claude/*` head starts nothing", "at `LANE_MAX` nothing is resumed", "an
exhausted lane is not started again". A script that does not exist starts
nothing, so each of those is trivially satisfied by the defect itself. Every
one of them is paired with a positive assertion about what was *said* — the
comment naming the branch shape, the tick line naming the cap, the
`blocked:needs-owner` label — and all of those fail against master. The pairing
is the check; the negative alone is not a measurement.

### Mutants

Falsifying against master only shows the checks notice an absence. These are
plausible wrong implementations of the four decisions above, each one line:

| mutant | what tripped |
| --- | --- |
| the cap writes a marker like any other failure | "the cap leaves no marker for that head", "so the next tick, under the cap, resumes it" |
| no stale-label column — the head sha is the only key | "a PR that also carries `fold-ready` is left alone", "list says why it was left alone" |
| no is-active guard | "a lane whose unit is still active is not resumed" |
| the brief is appended and never rolled back | "a capped tick rolls its handback back out of the brief" |
| the unfiltered-row guard deleted | all four of "a row that came back WITHOUT the label…" |

Each trips the check written for it and no other, except the two
`grep -c` brief-count checks, which are cumulative and therefore trip for any
mutant that changes how many resumes happen. That is a property of counting
against a running total; the named checks are the discriminators.

A fifth mutant was not staged — it was the first draft. `lane_name` returned
the name on stdout and was called as `name=$(lane_name "$branch")`, so the
`REASON` it set on every refusing path was set inside a command-substitution
subshell and thrown away. The two "no local lane" comments went out ending at
the colon with nothing after it — the whole content of the answer missing,
the comment still posted, the tick still green. Two checks caught it: "naming
the shape it needed" and "and is told cloud lanes remediate themselves". The
function now sets `NAME` and `REASON` and returns a status.

### What has not been shown

No open PR carried `needs-rebase` while I worked (checked against the live
repository: 15 open PRs, labels `harness`, `needs-audit-1`,
`needs-remediation,verified`, and nothing else). So every claim here rests on
the selftest and on reading `lane.sh`; **no handback has been observed
end to end on the real host.** The first live one is the test that matters, and
the thing to check on it is the one path the shims cannot reproduce: that
`systemd-run --unit hakux-lane-<name>` actually starts in a worktree whose
branch is mid-conflict, and that the session reads the appended brief section
rather than only the original. `$WORK/logs/handback/tick.log` is where to look.

### What is checked by grep, and why

Three checks on `fold.sh` are `grep`s and say so: the cause file is written
inside the conflict branch, and reaching it needs a real remote, a real push
and a real conflicting merge — which this selftest cannot stage against the
live repository. The *consumption* of that file is checked behaviourally (a
cause file on disk, and the lane's brief comes out naming the conflicting
path), so the grep only pins the producer's path string, which is the one thing
the behavioural check assumes.

The `--jq` in the pickup is the other invisible surface: `gh` runs it
internally, so the shim never exercises it and a typo in it would make this job
silently find nothing — the exact failure mode it exists to fix. The last check
extracts the query out of the script and runs it through `jq` (the same program
`gh` embeds) over canned JSON, and skips with a printed note if `jq` is absent.

## One thing I found on the way, and fixed in the file I own

`gh pr edit --body-file` fails exactly the way `gh pr edit --add-label` does —
measured here updating this PR's own body:

```
$ gh pr edit 132 --repo jreinach-alt/hakuX --body-file .pr-body.md
GraphQL: Projects (classic) is being deprecated ... (repository.pullRequest.projectCards)
$ echo $?
1
```

PR #118 fixed this for labels and `gh-label.sh` documents it thoroughly, but
only for labels. `roles/board.md` tells the board to grant a blocked lane its
file by **editing the lane PR's `Files:` line** — written with `gh pr edit`
that applies nothing, exits 1, and leaves the grant looking granted while the
board's own collision view never changes. It is the same silent state-machine
loss, one field over. I added the REST form and the measurement to that bullet,
since `roles/board.md` is one of my files. I did **not** write a
`gh-body.sh` helper: no job does this today (it is a model session's action,
not a script's), and a second helper nobody calls is the kind of thing the next
lane deletes.

## For the next lane

- `selftest.sh` exports `HERE`, `HAKUX_WORK`, `DISPATCH_DIR`, `GOLDENS`,
  `GH_REPO`, `PATH`, `SELFTEST_GH_LOG` — and, from this section, `HB` and
  `HB_LOG`. It does **not** export `T`, `REPO`, `TESTING`, `pass`, `fail`. A
  negative check written as `bash -c '! grep -q x "$T/..."'` passes against
  anything, because in that child shell the path is `/...` and `grep` fails on
  a missing file. PR #127 found this the hard way; every negative check in my
  section either uses an exported variable or is a function `check` runs in the
  current shell.
- `${*##* }` does **not** give you the last argument. A substring removal on
  `$*` is applied to each positional parameter separately and then joined, so
  the shim's `systemctl is-active` handed `grep` the whole command line as an
  option, `grep` exited 2, and "is this unit running" answered "no" for every
  unit. `${!#}` is the last argument. The check caught it; `-q` would have
  hidden the error message and `rc=2` reads exactly like `rc=1`.
- The whole file takes minutes, not seconds: `arms.sh list` walks every file in
  `docs/testing/predictions/`. Do not pipe it to `tail`; the pipe buffers and
  you see nothing until it ends.
- `handback.sh` resumes **one lane per tick**, matching `fold.sh`'s one fold per
  tick: a tick can create at most one new conflict, so the rates are matched.
  If a backlog ever needs draining faster, that is a loop bound to change, not a
  cap — `LANE_MAX` is the cap and it is `lane.sh`'s.
- **A fragment's `gh` shim now sees traffic its author never sent.** Every
  fragment under `selftest.d/` that drives `fold.sh` is also, since this PR,
  driving `handback.sh`, because `fold.sh` calls it at the end of a tick. A
  shim written as "answer every `pr list` with my row" was correct when a tick
  made one such call and is a trap now. If you add a job to the tail of another
  job's tick, run the whole suite and read the *other* fragments' failures as
  yours — the three that went red here were the only evidence of a real defect
  in this PR.
- **A mutant worktree made with `git worktree add --detach . HEAD` carries the
  committed file, not your working tree.** Mine ran the handback section twice
  — once from `selftest.d/99-handback.sh` and once from the copy still inline
  in `selftest.sh` at HEAD — and the second pass inherited the first pass's
  markers and briefs, so it failed for reasons that had nothing to do with the
  mutant. Twenty-two failures, none of them the discriminator. Copy the
  working-tree files in after `worktree add`, or commit first. The tell is a
  section header appearing twice in the output; the driver's fragment loop
  prints nothing, so grep the headers, not the counts.
