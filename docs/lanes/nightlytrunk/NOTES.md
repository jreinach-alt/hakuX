# lane.nightlytrunk -- the nightly built the owner's checkout, not the trunk

Brief only, no tracker issue. Base: `master @ bda6c52d9c`. PR #209.

## Why attempt 1 did not finish

The work was done, pushed and green; the session ended with the PR still a
**draft**, which is the one state nothing else in the harness can act on --
`board.sh`, `fleet.py` and `fold.sh` all skip drafts. It would have sat there
indefinitely.

The cause was sitting in the worktree as an untracked `.ci-poll.sh` (removed
now): a 40-round `gh pr view` loop on #209's check rollup, `sleep 45` between
rounds -- i.e. a hand-rolled sleep, worth 30 minutes of turns. Attempt 1
pushed `b651d2b2e0`, started waiting for CI on it, and ran out of turns inside
that loop -- so it never reached `gh pr ready`, and it never wrote the
`[lane.nightlytrunk] waiting:` comment that would have told a reader what it
was waiting for. From the outside those two failures are indistinguishable
from a lane that gave up mid-change.

Two things a lane should take from it:

- **Waiting is a finished session, but only if you say so.** CI on a fresh
  head is ~10 minutes and a lane cannot sleep through it. Post the
  `waiting:` comment, write it here, stop. `jobs/handback.sh` is the actor for
  that state and a resume for a wait costs no attempt -- that is exactly how
  this attempt was started.
- **Polling is what consumes the turns you need to finish.** The budget spent
  on 40 rounds of `gh pr view` is the budget that should have gone on the four
  remaining definition-of-done items, none of which needed CI's answer.
  Nothing in items 1-4 depends on the rollup, so all four could have been
  finished *before* the push that started the wait.

Nothing about the change itself was in question: CI was green on
`b651d2b2e0`, `mergeStateStatus` is `CLEAN`, and `preflight.sh` passes on that
head with no `--allow-tracker`. Attempt 2 added no code -- it wrote this
section and marked the PR ready.

## What was wrong

`nightly-2026-09-20` and `nightly-2026-09-21` were both built from
`20e4708d50`, a commit from the evening of 09-19. `origin/master` was 152
commits ahead of it; 89 commits landed on 09-20 alone. Both releases were
published under a current date, with an APK attached, saying **"No commits in
the last day"**.

Two independent causes stacked, and each alone was enough:

1. `hakux-nightly.service` ExecStarted `/home/justin/hakuX/docs/testing/nightly_build.sh`
   with `WorkingDirectory=/home/justin/hakuX` -- the owner's checkout, moved
   only when a person pulls it. Its last movement was a manual `pull --ff-only`
   at 2026-09-19T20:10:55-0700; nothing touched it for the 34 hours after.
2. `nightly_build.sh` asked that checkout what it was (`rev-parse HEAD`) and
   never fetched or compared. `grep -cE 'git fetch|origin/master' nightly_build.sh`
   was 0.

So fixing only the unit would leave a script that trusts whatever tree it is
handed, and fixing only the script would leave it running a stale *copy of
itself*. Both had to move.

## What was built

**`docs/testing/jobs/run-nightly.sh`** (new). The nightly's own detached
worktree at `$WORK/nightly-wt`, its own lock at `$WORK/.nightly-wt.lock`,
fetch + `checkout --detach <resolved sha>` on entry, then exec
`$WT/docs/testing/nightly_build.sh` with `NIGHTLY_TREE`/`NIGHTLY_TIP` set.

**`docs/testing/nightly_build.sh`**. Fetches `origin/$TIP` itself, every run,
and classifies three answers rather than two:

| state | what it does |
|---|---|
| at the tip | publishes; notes say "the tip of `origin/master`" |
| behind | **refuses**, exit 5, before `./gradlew` and before `gh` |
| origin unreachable | publishes with a banner naming the last successful fetch |

Both `git log` calls now name `HEAD` explicitly, so the commit range and the
binary are answers about the same ref. The flat sentence "No commits in the
last day." is now reachable only when origin answered *and* the tree is its
tip; otherwise it is qualified and points at the banner. `TREE` defaults to
the script's own repository rather than a hardcoded path, so under the
launcher it resolves to the fetched trunk. The dirty-tree warning is
unchanged. A second gate right before `gh release create` refuses if `HEAD`
moved during the build, because `$SHA` labels the tag, the title, the APK
filename and the notes and all four are read before `./gradlew` starts.

**`docs/testing/systemd/hakux-nightly.service`**. ExecStart is the launcher;
`WorkingDirectory` is gone (it *was* the defect); `SuccessExitStatus=75` for a
lock conflict, matching `hakux-fold.service`. The owner must re-run
`install-host.sh` (or at least `daemon-reload`) for the unit change to take.

**`docs/systemd/hakux-nightly.{service,timer}`, deleted.** Found while
grepping for other references, and it is the half of this defect that no care
inside `nightly_build.sh` can reach. There were *two* copies of the nightly
unit, both installing into the same `~/.config/systemd/user/`, so whichever
was copied last won. They had already drifted (`AccuracySec=1min` vs `30s`, no
`Unit=` in the old one), and the old one still carried
`WorkingDirectory=/home/justin/hakuX` with
`ExecStart=.../nightly_build.sh` -- and `docs/systemd/README.md` gave the `cp`
command for it. That is a documented procedure for reinstating this bug after
it is fixed, which is worse than the bug: it fires months later, when nobody
is looking at the nightly. Deleted rather than fixed, because two copies of a
unit are what produced the drift in the first place; the README keeps its
prose (linger, `Persistent=true`, WSL) and points at `install-host.sh`.

Worth recording: **`docs/ORCHESTRATION-DESIGN.md:496` already specified this**
-- "`nightly_build.sh` from a worktree of `origin/master`, not from the
owner's checkout" -- and §7.3 lists `nightly_build.sh` and `dx_pass.sh` as the
two that still reference the shared tree. The design was right and was never
implemented for the nightly; §7.3's other name is the dx pass, below.

## Why its own worktree and not `run-trunk.sh`

`run-trunk.sh` shares one worktree across arms/fold/status/cloud/both sweeps
and holds `flock .jobs-wt.lock` for the whole job. Those jobs are seconds of
`gh` and `git`; the nightly is `./gradlew assembleRelease`. Converting it
naively would park fold, arms, status and both sweeps behind an Android build
at 00:30 every night -- and worse, those jobs `checkout FETCH_HEAD` on entry,
which would move the tree under a running compile. The two families now share
an object store and nothing else.

The other option the brief offered -- fetch and compare in place, never
checking out -- was rejected as the *only* mechanism because it can never
publish on a night the owner has a feature branch checked out: it would refuse
every night until a person intervened, which is a missing nightly, which is
what everyone was trying to avoid. It is kept as the **backstop** instead
(that is exactly what the `behind` arm is), because the launcher is by
construction the stale copy: systemd ExecStarts it by absolute path out of
`/home/justin/hakuX`, exactly as it does `run-trunk.sh`. A guarantee living
only in the launcher lives in the file nobody updates.

## The mutant

`docs/testing/jobs/selftest.d/87-nightly-trunk.sh`, 34 checks, all green.
Full selftest on the final head: 1102 passed, 0 failed.

A bare origin, a clone at its tip, and a clone **pinned five commits behind
it**. The behind tree's commits are backdated three days and the trunk's five
are two hours old, so with a one-day window the behind tree's own log is
empty -- that reproduces the exact sentence the two bad releases printed,
which a same-day fixture cannot. A committed `android/gradlew` stub makes the
publish path runnable here instead of only at 00:30 on the owner's box, so
the check that the *release title* carries the trunk's sha is a real check.

The falsification runs `nightly_build.sh`'s replaced lines 66-80 verbatim over
the same behind tree and requires both central predicates to FAIL: the old
code prints ``built from `<stale>` on `master` `` as fact and prints "No
commits in the last day." while the trunk has five.

The last four checks are about the unit rather than the script: no `.service`
anywhere under `docs/` may ExecStart `nightly_build.sh`, exactly one
`hakux-nightly.service` is shipped, and it pins no `WorkingDirectory`. That
predicate is parameterised on a directory and run against a mutant holding the
deleted unit verbatim, because a check green only on the fixed tree cannot
tell "no bad unit" from "found no units".

It also drives the two arms of the deliberate asymmetry in the gate: a tree
both ahead of and behind the trunk refuses (behind is tested first), while a
tree purely ahead of it publishes with the old `unpushed` label, because it
contains every trunk commit and so nothing a reader is owed is missing from
it. That rests entirely on the order of an `elif`, and a documented gate is
not an enforced gate.

### What the next lane should not repeat

- `GIT_AUTHOR_DATE="3 days ago"` is rejected by git on the CI runner and the
  commit silently lands at the wall clock, collapsing a windowed fixture
  without a word. Use `date -d ... -Iseconds`.
- `git init --bare` without `-c init.defaultBranch=master` gets
  `HEAD -> refs/heads/main`, so every clone of it checks out **nothing** --
  and every negative grep in the fragment then passes against an empty file.
  Both of these are why the fragment asserts its own premise ("really five
  commits behind") before anything else; without that assert the whole file
  was green while the fixture was empty, which I saw happen.
- One predicate in that file is a negation (`! grep`), and it leads with
  `[ -s "$1" ]` for the same reason.

## The other two units out of the owner's checkout

**`hakux-dx` should move; it has the same defect, and the design doc already
says so** (§7.3 names `dx_pass.sh` alongside `nightly_build.sh`). `dx_pass.sh` reads
`$TREE/docs/testing/papercuts.toml` and `git log --since='24 hours ago'` from
the owner's checkout. On 09-20 and 09-21 it was reading the same 34-hour-old
tree, so its harvest saw zero of the day's commit messages and "no new paper
cuts today" was indistinguishable from "nobody pulled". It publishes no
artifact, so nothing is mislabelled -- but the `dx-pass.due` marker the
orchestrator dispatches from is derived from a window it cannot see, which is
the nightly's bug minus the APK.

It is **not** in this PR. `run-trunk.sh` execs `$WT/docs/testing/jobs/$job.sh`
and `dx_pass.sh` lives one directory up, so converting it needs a change to
`run-trunk.sh`'s path handling (a file six other units depend on) plus its own
pinned-behind mutant. That is its own lane, not a rider on this one. It is a
good fit for the shared worktree -- seconds of `git log`, no build, no lock
contention -- so it should be `run-trunk.sh`, not a second private worktree.

**`hakux-comments` is a weaker case and should move for a different reason.**
`comment_sweep.sh` reads no git history and no tracked file: it uses `$SELF`
only to locate `jobs/deliver.sh`, and everything it reasons about comes from
`GET /repos/{o}/{r}/issues/comments?since=`. So it cannot be stale *about the
repository* the way the nightly and the dx pass can. What it can be stale
about is itself -- it and `deliver.sh` run at whatever version the owner last
pulled, which is `run-trunk.sh`'s original argument and still worth fixing,
just not urgent. Same launcher, same lane as dx.
