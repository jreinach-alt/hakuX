# lane.handback — an actor for a PR a job handed back

Base: `master` @ bdeab36f75. PR #132.

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

## Evidence

The new checks drive the real `handback.sh` and the real `lane.sh` against
shims of their own. They have to be their own: the shared `gh` shim answers
every `pr list` with `[]` and the shared `systemctl` answers every `is-active`
with `active`, which are exactly the two answers that make this job do nothing.
`$HB/bin` holds `gh` (rows from a per-label TSV, comment *bodies* kept, labels
logged), `systemctl` (`$HB/active` is the set of running units) and
`systemd-run` (logs and exits).

| `jobs/` under test | result |
| --- | --- |
| this branch | **42 passed, 0 failed** |
| `origin/master`, with only `selftest.sh` replaced by this branch's | 14 passed, **28 failed** |

The falsification run is a real worktree at `origin/master` with this branch's
`selftest.sh` copied in, so the checks run against master's `fold.sh`, master's
`roles/board.md`, and no `handback.sh` at all.

**The 14 that "pass" against master pass for nothing**, and it is worth being
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
