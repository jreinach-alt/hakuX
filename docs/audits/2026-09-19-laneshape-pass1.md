# Audit pass 1 — PR #163, `lane/laneshape`: a lane is a branch with an open PR, not a branch named `lane/*`

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #163, branch `lane/laneshape`, tip **`8b185a925f`**, five commits
over its stated base **`732b97e2df`**. `origin/master` is **21 commits** ahead
of this tip.
**Date** 2026-09-19. **Records** `2026-09-19-laneshape-pass1.{md,json}`.

**2 HIGH. 3 MEDIUM. 4 LOW.**

The diff is 8 files, +978/−21: one new helper (`jobs/remote-lane.sh`), one new
selftest fragment (`selftest.d/98-lane-shape.sh`, 41 checks), edits to
`arms.sh`, `fleet.py`, `fold.sh`, `handback.sh`, `lane.sh`, and
`docs/lanes/laneshape/NOTES.md`. No emulator code, no prediction, no device.

CI on this head is **green** (`Android`, `Desktop build`, `jobs selftest`, all
`success` at 20:42Z on `8b185a925f`). `mergeStateStatus` is **DIRTY**.

## What I checked and found correct, so remediation does not re-derive it

* **The premise is real and verified against the live repo.** `gh pr list
  --state open` returns eight PRs today; exactly one of them, #162, has a head
  (`claude/docs-tooling-agentic-coding-u152m1`) that no `lane/*` glob matches,
  and `git ls-remote --heads origin` confirms that branch exists. Master's
  `arms.sh` walked `refs/remotes/origin/lane/*` and nothing else, so that
  branch's predictions were genuinely uncollectable. The lane did not invent
  its bug.
* **`prune_branch`'s new refusal cannot widen the delete set.** It is placed
  after the `lane/?*` case and can only `return 1`; both live call sites
  (`fold.sh:232`, `:603`) discard the rc, and `:212` exits with it, which is
  that mode's documented contract. An un-pruned ref is the safe direction and
  the diff takes it.
* **The three shell callers avoid the `local x=$(...)` rc-masking trap.**
  `handback.sh`'s `local rl; rl=$(remote_lane_of "$1")` and `lane.sh`'s
  `local b` / `b=$(remote_branch_of "$1")` are split correctly. None of the
  four scripts sets `-e`, so a non-zero `remote_lane_of` cannot abort a tick.
* **The `remote_map` cache is not the no-op it looks like.** `remote_lane_of`
  and friends run `remote_map` in a pipeline subshell, so they cannot populate
  it — but `remote_readable` does not, and both `fold.sh` and `lane.sh` call
  `remote_readable` first. One `python3` + `board_files` per process, not per
  branch.
* **`arms.sh state` really is off the network path now.** The `mode = state`
  arms skip the PR map (`:122`), the fetch and the tips build (`:149`), and the
  `state` block exits at `:586` before `collect` is ever called at `:646`;
  `build_label_index`/`label_decide` read `$A/pairs` and `$A/judged` only. The
  regression guard added for the lane's own defect 1 is real.
* **`live_ancestor` was widened in step with `tips`.** It iterates the same
  `$tips` string (`:277`), so a `b_ref` on a newly visible PR head is not
  refused as stale — a gap that would have made the arms half inert.
* **`lane.sh rm` is not a second deletion door.** It removes the worktree only;
  no branch is deleted, and a remote lane has no local worktree. The exemption
  in `fold.sh` is the only place that needed one.
* **`handback.sh`'s missing `remote_readable` check is covered by depth**, as
  its comment claims: the resume goes through `bash "$LANE_SH" resume "$name"`
  (`handback.sh:241`), and `lane.sh`'s `refuse_if_remote` exits 76 on an
  unreadable board. (H2 below defeats both at once, which is the point of H2.)
* **`Files:`, notes path and readiness are right.** The body's eight paths are
  exactly `git diff --stat origin/master...HEAD`; `NOTES.md` is at
  `docs/lanes/laneshape/NOTES.md`, not the branch root; the PR is not a draft;
  `Prediction: none: analysis-only` is the correct answer for a harness change.
* **41 checks is 41 checks.** `grep -c 'check "'` on the fragment returns 41,
  and the fixtures are real bare origins for the arms and prune halves, with
  named must-not-move legs (`lane/ordinary` still deleted, `alpha` still a
  claim with no agent, `resume alpha` still reaching "no worktree"). The
  fragment's structure is the good kind. See M2 for what is wrong about the
  number that certifies it.

---

## HIGH

### H1 — one open PR whose head branch is absent from `origin` aborts the whole `arms.sh` fetch, silently staling every ref `collect()` walks, master included

`docs/testing/jobs/arms.sh:150-158`.

The new fetch builds one `git fetch` invocation that carries a *named*,
non-wildcard refspec per open PR head: `+refs/heads/$b:refs/remotes/origin/$b`.
`git fetch` fails the whole invocation when any named refspec matches no remote
ref, and **updates nothing at all** — not the other named specs, not the
`lane/*` wildcard, and not `$TIP`. Verified here against a scratch bare origin:

```
$ git fetch -q origin master '+refs/heads/lane/*:...' '+refs/heads/gone:...'
fatal: couldn't find remote ref refs/heads/gone
rc=128
consumer origin/master before: 67f05659ca
consumer origin/master after:  67f05659ca     # origin advanced; this did not
```

The old code could not fail this way: `$TIP` always exists and a wildcard that
matches nothing is not an error.

`headRefName` is the branch name in the *head repository*, which for a fork PR
is not a branch on `origin` at all — and this repository is public by the PR
body's own argument about CI. A head branch deleted while its PR stays open
does the same thing, and GitHub leaves such PRs open indefinitely. The `lane/*`
and `$TIP` filters at `:153` and `:163` remove the self-inflicted cases; they
do not remove these.

**Failure scenario.** Someone opens a PR from a fork, or deletes the head
branch of an open PR. From the next tick on, `arms.sh` logs
`WARNING: fetch failed; working from what the object store has` and collects
from whatever refs it already had. Every prediction pushed after that moment —
on master, on every `lane/*` branch, on the remote lane — is invisible to the
queue, for as long as that PR stays open. The device pipeline stops taking new
work and nothing says so outside `$WORK/logs/arms/tick.log`. That is a
strictly larger outage than the one this PR was opened to fix, and it needs a
person to notice it.

It does not fire today: the one non-`lane/*` head, #162's, exists on origin.
That is the whole reason it is worth fixing now rather than at 03:00 on the day
it does.

**Remediation.** Any of: fetch the PR heads as `+refs/pull/<n>/head:...`
(always present, and the only form that works for a fork at all — the map
already carries the number); or intersect the branch list with one
`git ls-remote --heads origin` per tick; or issue the PR-head fetch as a
*second*, separate, non-fatal `git fetch` so a bad name cannot take master's
refs down with it. Whichever is chosen, add a fragment leg with an open PR
whose head does not exist on the fixture origin, and assert master's tracking
ref still advanced.

### H2 — a board read that silently falls back to the fold-lagged in-tree `territory.toml` is reported as a successful read, and defeats all three callers in the same unsafe direction

`docs/testing/jobs/remote-lane.sh:37-40, 66-82`.

The header states the design's central safety property:

> THE BOARD IS READ THROUGH board_files.py, so this sees origin/board and not a
> lane worktree's fold-lagged copy
>
> A READ FAILURE IS NOT "NO REMOTE LANES". […] lane.sh REFUSES to start,
> fold.sh KEEPS the ref, fleet.py reports the lane as it did before. A helper
> that returned an empty map on failure would have made all three silently take
> the "no remote lanes" branch.

`board_files.load` has a third outcome that `remote_map` folds into the first.
`_from_ref` returns `None` whenever `git show origin/board:territory.toml`
fails — the ref not fetched, a clone or CI checkout without it, a timeout — and
`load` then reads `os.path.join(HERE, name)`, the **in-tree** copy, and records
that in `_src`. `remote_map` never calls `board_files.source()`, so this path
exits 0 with a map built from the wrong file, and `remote_readable` returns
true.

The in-tree copy is not incidentally stale, it is *structurally* stale:

```
origin/board:territory.toml                 wave = 125   2026-09-19T21:00:00Z
origin/master:docs/testing/territory.toml   wave =  94   2026-09-18T22:25:00Z
```

31 waves and a day behind, today. The `remote` marker this PR asks the board to
add (body, board request 3) will live on `origin/board` and reach the in-tree
copy only when some later fold copies it — so the fallback copy is exactly the
one guaranteed *not* to carry the new marker.

**Failure scenario.** The board adds `remote = true` to a row whose lane lives
on `lane/<name>` — the case `fold.sh`'s new exemption exists for, in its own
words "the exemption for the day one is, which is exactly when nobody will be
thinking about it". A fold tick runs from a checkout without `origin/board`
(`board.sh` re-execs `arms.sh`/`fold.sh` from a fetched master worktree; a
fresh clone has `origin/master` and not `origin/board`). `remote_readable`
returns 0 from the wave-94 copy, `is_remote_branch` returns false, and
`prune_branch` deletes the branch of a live cloud lane on origin, its tracking
ref and the local head — the outcome the exemption's own comment calls "not the
recoverable kind of mistake". In the same state `lane.sh`'s `refuse_if_remote`
also passes and starts a second agent on that branch, and `handback.sh`'s
defence-in-depth (which is `lane.sh`) goes with it. Three guards, one
common-mode failure, in the direction the header promises is impossible.

**Remediation.** Make the stale-copy state visible to the helper and pick a
direction for it. `board_files.source("territory.toml")` already answers the
question; have the python block emit it and let `remote_map` distinguish
`read from origin/board` / `read from the working tree` / `unreadable`, with
the callers treating the middle one as they treat the third (refuse, keep,
report-as-before) or at minimum saying so in the refusal text. Add a fragment
leg: a fixture whose `origin/board` read fails and whose working-tree
`territory.toml` carries no `remote` row, asserting `fold.sh` still does not
prune and `lane.sh` still refuses.

---

## MEDIUM

### M1 — the branch conflicts with current master in `docs/testing/lane.sh`, so this head cannot fold

`docs/testing/lane.sh`. `gh pr view 163 --json mergeStateStatus` returns
`DIRTY`, and `git merge-tree --write-tree --name-only HEAD origin/master`
reports `CONFLICT (content): Merge conflict in docs/testing/lane.sh`
(`fold.sh` and `handback.sh` auto-merge).

**Failure scenario.** The PR reaches `fold-ready` and `fold.sh` cannot produce
a merge commit; the PR sits until `handback.sh` labels it `needs-rebase` and
something resumes the lane — one full extra cycle, after two audit passes have
already been spent. Worse for this particular file: master has moved `lane.sh`
underneath the one gate this PR adds to it, so `refuse_if_remote`'s placement
relative to master's current `start`/`resume` bodies has not been verified by
anything, and the conflict resolution is where that would be checked.

**Remediation.** `git merge origin/master`, resolve `lane.sh` by hand, re-run
`selftest.sh` (the 98 fragment exercises both call sites), push. Commit the
resolution before running any long gate.

### M2 — three mutually inconsistent counts of how many checks fail against master, and the one in the PR body was reconciled by arithmetic rather than by measuring

`docs/testing/jobs/selftest.d/98-lane-shape.sh:22`,
`docs/lanes/laneshape/NOTES.md:220`, PR body.

The fragment contains 41 `check` calls — verified, and it has contained exactly
41 in every one of the four commits on this branch. The three places that
record the falsification measurement say:

| where | claim | adds to |
|---|---|---|
| fragment `:22` | "Measured 2026-09-19 against master@841a38736c: **19** of these fail" | — |
| `NOTES.md:220` | "**25** of the **39** do. The other **14**" | 39 |
| PR body | "**25** of the **41** fail against master's code. The other **16**" | 41 |

`841a38736c` is a real commit on master (10:50 PDT, fold of #160), so the
fragment's figure is a stated measurement, not a placeholder. 19 ≠ 25, and the
body's "16" is `41 − 25` — the denominator was corrected to the true check
count while the numerator was carried across unchanged, which is the shape of
an arithmetic reconciliation rather than a re-run.

This matters more here than a stale number usually would, because the count
*is* the evidence. Forty-one new checks are trustworthy only in proportion to
how many of them were shown to fail against the code they replace; NOTES then
spends a section enumerating the 14 that could not discriminate and why. With
the totals disagreeing, at most one of the three accounts can be true and the
per-check taxonomy underneath it cannot be reconciled to the file either.

**Failure scenario.** Pass 2 sets out to verify "each new check fails against
the code it replaces", unpacks master's `docs/testing`, runs the fragment, and
gets some number. It matches none of 19, 25, or 25-of-39, and pass 2 cannot
tell whether a check silently became a tautology against the new code, whether
the enumeration of non-discriminating legs is wrong, or whether it is only
reading a stale note — so it either passes the PR on a claim it could not
check, or hands back for a re-measurement that should have been done once.

**Remediation.** Re-run the unpack-master procedure against this tip once,
write the resulting number in all three places, and make the NOTES enumeration
sum to 41. If the 19 and the 25 came from different tips of this branch, say
which tip each was measured at.

### M3 — the "86-fold-regressed.sh is red on master and holds up every fold, including this PR's" section is superseded and still reads as current

`docs/lanes/laneshape/NOTES.md:242-274`, and the same claim in the PR body.

The section states "`selftest.sh` reports 11 failures on this branch. 10 of
them are master's" and concludes "**CI is the gate of record, so this holds up
every fold until someone owns it, including this PR's.**" The `jobs selftest`
workflow run on this very head (`8b185a925f`, 2026-09-19T20:42:34Z) concluded
`success`; the previous head `e18b3e47ef` was `failure`. Whatever landed in the
21 commits this branch merged from master resolved it, and the merge commit is
on this branch.

The diagnosis itself (two commits, `a4fcced05a` then `4eb641e777`, and the
`fr_reset` refspec) is good work and worth keeping as the record of what
happened. What is wrong is the tense, and it is asserted at the top of the
section and in the body's headline, which is where anyone reads it.

**Failure scenario.** The board reads a still-open PR saying the trunk's
selftest is red and every fold is blocked on an unowned fixture, and dispatches
a lane at a defect that is already fixed — or pass 2 treats a red `jobs
selftest` as expected on this branch and lets a real regression through. The
project's own rule is that a withdrawal appended at the bottom of a long notes
file leaves the claim at the top still asserting itself; here there is not even
a withdrawal.

**Remediation.** Mark the section superseded in place, at its heading, naming
the head and the run that is green. Keep the two-commit diagnosis. Remove the
"holds up every fold, including this PR's" sentence from the PR body, or
restate it in the past tense with the date it stopped being true.

---

## LOW

### L1 — `p["remote"]` is written and never read
`docs/testing/fleet.py:237, 240`. Every PR row gets a `remote` boolean; nothing
in the file consults it (the REMOTE LANES section iterates the `remote` map
directly, and `pr_of` is keyed by lane). Either use it where the distinction
matters — see L2 — or drop it, since a field nothing reads is a field nothing
keeps true.

### L2 — READY, NOT FOLDED prints `finished` for a remote lane's PR
`docs/testing/fleet.py:607-610` prints `"unit up" if p["lane"] in units else
"finished"`. A remote lane never has a `hakux-lane-*` unit, which is the whole
premise of the change, so its ready PR always reads `finished` — the one word
in that column that means "the local unit is gone". The REMOTE LANES section
above corrects it for a reader who gets that far. `p["remote"]` is exactly the
field that would let this print `elsewhere`.

### L3 — a remote lane's PR now sets FAIL through `unfolded`/`waiting`, which the new section's comment says it does not
`docs/testing/fleet.py:588` reasons "No FAIL: there is no action a board tick
could take from here". True of the REMOTE LANES section; not true of the
change as a whole, because `lane_prs` now admits those PRs and `unfolded`
(`:386`) and `waiting` (`:399`) both raise `FAIL` lines at `:694` and `:714`,
and `board.sh` starts a session on any `^FAIL`. This is almost certainly the
intent — a remote lane's ready PR *should* enter the audit pipeline — but the
comment as written would tell a later reader the opposite. One clause.

### L4 — a fragment check's label does not describe its assertion
`docs/testing/jobs/selftest.d/98-lane-shape.sh:186`: "fleet.py counts an open
PR on a branch a territory row names" asserts `REMOTE LANES (2)`, which is the
count of remote *rows*, one of which deliberately has no PR. The next check is
the one that asserts the PR. Rename, so a failure names the right thing.

---

## What pass 2 has to verify

Each of these is a scenario that must no longer be reachable, not a commit
that must exist:

1. **H1** — with an open PR whose head branch does not exist on the fixture
   origin, an `arms.sh` tick still advances `refs/remotes/origin/master` and
   still collects a prediction pushed to master in that tick.
2. **H2** — with `origin/board` unreadable and a working-tree `territory.toml`
   carrying no `remote` row for it, `fold.sh --apply` does not delete the
   marked branch and `lane.sh resume` still exits 76.
3. **M1** — `gh pr view 163 --json mergeStateStatus` is not `DIRTY`, and
   `selftest.sh` still passes after the resolution.
4. **M2** — one number, measured at a named tip, in all three places, summing
   to 41.
5. **M3** — the superseded claim is corrected at its heading and in the body.
