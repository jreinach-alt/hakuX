# lane.cloudtail -- the cloud unit's tail was not guaranteed

Brief: `$WORK/briefs/cloudtail.md`. Harness defect, no tracker issue. PR #175.

## Why attempt 1 did not finish (written at the start of attempt 2)

It ran out of turns with the work done and **uncommitted**. The fixes below
were all in the worktree; what was pushed as `06c8d6efa5` was an earlier
state of them, and CI went red on that head with three failures in this
lane's own fragment:

| CI failure on `06c8d6efa5` | already repaired in the worktree, never committed |
|---|---|
| `b: the PR is told the session ended without a next state` | `tl_comments()` counted every `COMMENT 141`, and `cloud.sh` comments at **claim** as well as in `finish`; it now counts the notice's own words, and `tl_claim` truncates the log |
| `an unreadable label list is retried three times, not read as 'no claim'` | the count is **four** reads, not three -- the retry loop's three plus `label_rm`'s own; three alone is equally consistent with retrying and then giving up |
| `and finish goes on anyway: ...` | replaced: with the labels endpoint down, `label_rm` cannot issue the `DELETE` at all, so the observable property is the tick-log line saying which path it took, not a `DELETE` that cannot happen |

So attempt 1 was not wrong about the fix; it was wrong about when to commit.
The lesson is the ordinary one and it is already in the contract: **commit
before any long step**, and a self-test run is a long step. Nothing here was
re-derived in attempt 2 -- the diff was committed, `origin/master` merged, and
the suite re-run.

One thing attempt 2 did find and did not cause: `selftest.d/60-status.sh`
(`[lane.statusfresh]`'s, not mine) wrote a **hardcoded** `2026-09-19T01:10Z`
row into a table `status.sh` filters to the last 24h, so it went red on every
branch at 2026-09-20T01:26Z. `origin/master` had already fixed it (relative
stamps) 42 commits ahead of this branch. Merging master is what clears it
here; there was nothing in this lane to fix.

## Territory: `cloud.sh` is held by a LIVE lane, not a stale one

The brief expected `[lane.cloudterritory]` to hold `docs/testing/jobs/cloud.sh`
and to be stale. Neither is true any more. The board retired that row at wave
126 and **granted `docs/testing/jobs/cloud.sh` outright to `[lane.turncap]`**,
whose **PR #171 is OPEN**. I have not edited `territory.toml` and have not
claimed the file.

#171's `cloud.sh` diff is confined to the header — it moves
`TURNS="${CLOUD_TURNS:-120}"` down below the `limits.env` source. Mine touches
the header comment block, `finish`, the dispatch block and the `systemd-run`
invocation. **The changed lines are disjoint**; the header comment and #171's
hunk share context lines, so a fold conflict is possible but mechanical. This
wants a fold order, not a re-dispatch.

**Resolved, and not by a prediction about it.** #171 MERGED at
2026-09-20T02:37:54Z, and attempt 2 merged `origin/master` (42 commits) into
this branch at `73f8d3afbb`: **clean, no conflict in `cloud.sh` or anywhere
else.** `TURNS="${CLOUD_TURNS:-120}"` now sits at `cloud.sh:89` below the
`limits.env` source, from turncap's commit, with my header comment above it.
So the fold-order request above is discharged — it was right, and the order it
asked for is the order that happened. Written down rather than deleted because
the next lane to touch `cloud.sh` will face the same question, and "the two
hunks were genuinely disjoint" is the part worth having evidence for.

Since #171 is merged, `[lane.turncap]`'s hold on `docs/testing/jobs/cloud.sh`
is now the *stale* row the brief expected to find under a different name. That
is the board's to retire (`roles/lane.md:79`); I have not touched
`territory.toml` and am not claiming the file on the way past.

`docs/testing/jobs/selftest.d/**` went to `[free]` in the same wave, and no
open PR uses the `72-` prefix.

## The two defects, and what each fix actually rests on

**1. The tail.** It was the last command of the unit's `bash -c` string. A `;`
chain runs its tail only if that shell reaches it, so the tail was absent for
a kill, a manager restart, a dead shell — and for a command-not-found earlier
in the chain, which is what actually happened. Now
`--property=ExecStopPost="/bin/bash $SJOBS/cloud.sh finish $kind $num"`.
`ExecStopPost=` is systemd's own mechanism for exactly this: it runs after the
main process terminates, whatever terminated it, including a failure to start.

**2. The path.** `$JOBS` is `$WORK/board-wt/docs/testing/jobs`, and `board.sh`
re-checkouts that worktree on *every tick* (`board.sh:185`). Now the scripts
the unit names are copied at claim time to `$WORK/units/<unit>/{jobs,lane.sh}`.

I chose the snapshot over the two alternatives the brief listed, and the
reason is not only immutability:

- `$REPO` (the owner's checkout) is *also* mutable — it is whatever branch the
  owner last checked out, which `board.sh:188-204` already has its own scar
  about. Swapping one moving directory for another is not a fix.
- A copy installed once under `$WORK` cannot move, but drifts from the trunk
  silently. Same class of bug, longer fuse.
- A snapshot **pins the tail to the version that made the claim**. The shape
  of a claim — which labels, which territory row, which attempt file — is
  defined by the script that wrote it, so the script that reverses it must be
  that same one. A tail read from a `$JOBS` that merely moved *forward* is not
  just a live path; it is a different program undoing this program's work.
  That is the argument `board.sh:188-204` makes for its own re-exec, pointed
  the other way: the board wants the *newest* trunk because it is starting
  work; a tail wants the *same* revision because it is finishing some.

Cost: ~664K per live unit, swept on the next claim for every unit that is no
longer active. The sweep deliberately spares an **active** unit's snapshot:
its tail executes from it, and bash reads a script lazily by byte offset, so
deleting one under a live unit corrupts the program mid-file rather than
tidying a directory.

## Was `finish` idempotent? Four steps of five.

The brief asked me to say which. It runs twice in practice — `ExecStopPost`
fires on stop, and the owner runs it by hand when a claim has been stranded,
which is how #141 and #148 were repaired at 2026-09-19T23:21Z.

| step | idempotent before? | why |
|---|---|---|
| `label_rm claimed:cloud` | yes | `gh-label.sh` probes the labels first and skips what is absent |
| `territory_row rm` | yes | exits 3 on a row that is not there; the caller treats that as success |
| `label_rm <state>` | yes | same probe |
| `rm -f $WORK/attempts/...` | yes | `rm -f` |
| **`gh pr comment`** | **no** | posted the "ended without setting a next state" notice again, every time |

And the fifth is the branch a hand-repaired claim *lands in*, because its
`claimed:cloud` is already gone, so the successor test is not what saves it.

**The key is the claim label, not a marker file.** `claimed:cloud` is the one
piece of state that says "a claim is live right now", it is server-side where
every actor sees it, and the next claim re-applies it — so a genuine *second*
claim of the same PR gets a live `finish` again. A `kind+num` marker under
`$WORK` could not tell the second run of one claim from the first run of the
next, and re-claiming is the whole retry policy.

Only the comment is gated on it. The four self-cancelling steps still run
unconditionally, which is what covers the case where `label_add` failed at
claim time and there was never a label to key on.

## Also fixed, same family, one line

`systemd-run` failing was the one path `ExecStopPost` can never cover — there
is no unit to stop. It used to drop the territory row and **leave
`claimed:cloud` on a PR no session was ever started for**: permanently
invisible, exactly like the stranded tail, by a different route. It now drops
the claim too and gives the attempt back. The *state* label stays, because the
PR still needs what it was claimed for.

## One comment corrected where it is read

`gh-label.sh`'s closing comment justified its CLI mode by naming the caller
this change removes: "cloud.sh builds an 'unclaim' command as a STRING for the
session's systemd unit". That premise is now false, and the next reader who
greps for the caller finds none — and the CLI is what `roles/cloud.md` and
every lane brief tell a *session* to run, because `gh pr edit` is GraphQL and
applies nothing here. Comment-only; the file is claimed by no row and named by
no open PR.

## What I could not execute, and what happens if I am wrong about it

**No real systemd unit was ever started.** CI (`ubuntu-latest`) has no user
manager, and this sandbox refused `systemctl` outright. So
`selftest.d/72-cloud-tail.sh` emulates systemd in exactly one property and
says so at the line that implements it: `ExecStopPost=` runs after the main
process ends, ignoring how it ended. Everything else in the fragment is real —
`cloud.sh`, `gh-label.sh`, git, the board branch, the territory row, the
worktree, the snapshot copy, and the `kill -9`.

Two things guard the gap:

- The stub **refuses a relative first word** in `ExecStopPost`, because
  systemd does not fall back to `$PATH` for an `Exec*` command — it refuses to
  load the unit. That is the single most likely way this fix could be inert on
  the host and green here, so it is refused in the stub *and* pinned on the
  script's text.
- If this systemd rejects `-p ExecStopPost=` for some other reason,
  `systemd-run` exits non-zero, `cloud.sh` takes its failure branch, says
  `systemd-run failed for <unit>` in the tick log, **drops the claim and
  returns the attempt**. A wrong guess here is loud and self-reverting, not a
  new silent strand. That branch is itself checked.

**What no version of this can recover**: while the labels endpoint is down,
nothing removes the label. `gh-label.sh`'s `label_rm` reads the current labels
first and returns 1 without attempting the `DELETE` (a `DELETE` on an absent
label is a 404, and swallowing that would swallow every other failure). So the
retry-then-continue path is not "the claim comes off anyway" — it is that
`finish` does not mistake an unreadable list for a finished claim, takes the
long path, and leaves a later `finish` able to work. The check asserts four
reads, not three: the retry loop's three plus `label_rm`'s own, because a
count of three alone is equally consistent with retrying and giving up.

## The mutants

Two defects, so two mutants reverting exactly one each, plus a third reverting
both — which is the file as it stood on 2026-09-19. One at a time is what
shows they are independent:

| mutant | world | result |
|---|---|---|
| `both` (today's file) | worktree moves mid-session | claim stranded, state label stranded, territory row stranded, PR invisible to every future tick |
| `path` (ExecStopPost kept, `$SJOBS` → `$JOBS`) | worktree moves mid-session | claim stranded — ExecStopPost cannot save a tail that names a path which is gone |
| `tail` (snapshot kept, tail back in-band) | `kill -9` mid-session | claim stranded — no `;` runs after SIGKILL |
| — (fixed) | either world | claim released, state label handled, row removed, PR claimable again |

Each substitution is **asserted to match exactly once** and the builder refuses
otherwise. A mutant whose edit silently failed to apply is the fixed file under
another name, and it passes the check it was built to fail, for free and
forever.

Two fixture traps worth not repeating:

- `cloud.sh` comments on the PR **at claim** as well as in `finish`, so a count
  of "comments on #141" counts the wrong thing. The shim logs the body and the
  count matches the notice's own words.
- The kill must land on the unit's own `bash -c`, not on a subshell wrapping
  it — hence `exec` — or the very shell whose trailing `; finish` is under test
  survives and runs it. And `claude` blocks on a file the harness releases
  *after* setting a kill flag, rather than on a fixed sleep: a sleeping orphan
  labels the PR seconds into the *next* scenario, which reads like a defect.

## Result

`bash docs/testing/jobs/selftest.sh`: 37 new checks, all green, whole file
green. `preflight.sh --allow-tracker`: passed, territory gate included.
