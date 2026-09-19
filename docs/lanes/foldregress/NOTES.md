# lane.foldregress — `regressed` was a rule in a role file; it is a gate now

## What was wrong

2026-09-19T10:56:52Z, PR #102 folded as `3d072c6ea6` carrying `regressed`.
Its failing prediction is `issue88-vk-same-offset-colour-wins.json`
(b_ref `67dc7724ee`): `VERDICT: FAIL -- 2 of 13 checks violated`, with
`Color_zeta_overlap Swap 165,447 -> 304,750 (+139,303)`. That b_ref is an
ancestor of `origin/master` now.

```
$ grep -c regressed docs/testing/jobs/fold.sh
0
```

The rule lived in `jobs/roles/board.md` — *"a `regressed` PR is not
fold-ready"* — which is prose, read by whichever model session decides to set
`fold-ready`. The label had been set twenty minutes before the fold precisely
to stop it, and stopped nothing, because nothing read it. **A rule that lives
only in a role file is advice, and the job it advises is a script.** (That is
the same shape as `documented-gate-is-not-enforced-gate`: `board.md` also
still described this as the board's rule while `fold.sh` had never had it.)

## What it does now

`fold.sh` reads `labels` off the candidate `gh pr list` — the one call it
already makes — and refuses to fold a PR carrying `regressed` unless the
owner has accepted the regression with a `regression-accepted:<issue>` label.
Blocked is not the same as handed back:

- `fold-ready` is **kept**. Nothing is removed, no `$F/failed/<pr>-<head>`
  marker is written, and the head is retried every tick, so the fold resumes
  the moment the regression clears and nobody has to re-apply anything.
- It is said on the PR **once per head and per state**, on `ci_report`'s
  ledger discipline: `REGRESSED`, and separately `ACCEPT-MALFORMED` if an
  override that names no issue turns up later. A boolean there would have
  moved the silence one state over — an owner who adds a malformed label has
  acted and must be answered.
- The override is only read on a PR that is actually `regressed`. A stray
  `regression-accepted:91` on a PR with no verdict folds it silently, rather
  than announcing a regression the PR has no record of.
- `fold.sh list` reports it and posts nothing. (Note that `list` is not
  read-only in general — the CI path comments from it and always has; see
  `docs/lanes/foldci/NOTES.md`. This gate does not add to that.)

Costs: no extra `gh` call at all. For a blocked PR it is one call *fewer*,
because the gate sits before `ci_green`'s `gh pr view`.

## What this lane deliberately did NOT decide

**What `regressed` means.** Today it is the last verdict judged, which is how
#102 briefly read `verified` with a live FAIL; #144 (lane.armlabel) replaces
that with supersession by issue number. That is the right place for it: this
gate reads the label, `arms.sh` decides the label. A second opinion here —
re-reading `$WORK/arms/pairs/`, deciding which FAIL is still live — would be
a second state machine over one word, and the two would disagree on the day
it mattered. It also would not work: a cloud lane's fold has no host disk.

The two lanes do not touch the same file (#144 is `arms.sh` +
`selftest.d/94-*`; this is `fold.sh` + `selftest.d/86-*`) and land in either
order.

## Why the override is an owner-set label, and not a comment or a file

`regression-accepted:<issue>` on the PR. The alternatives, and why not:

| | why not |
|---|---|
| a magic comment (`[owner] accept #91`) | it costs a per-PR `gh pr comment list` for every candidate — the gate's whole cheapness is that labels ride the candidate list — and *anything* can post a comment with any prefix, so it is unauthenticated by construction |
| a file in the PR's diff (`docs/testing/accepted/*.toml`) | the lane can edit its own diff, so the actor being overridden would set the override. It also puts a decision about one fold permanently on master |
| a `decision-needed` issue the board closes | the board is a model session; "the board judged the owner meant yes" is exactly the layer this defect came from |
| no override at all | #91 exists to hold `Color_zeta_overlap/Swap 165,447 -> 304,750` under #88's colour-wins policy. That trade is deliberate, so a gate with no way through makes every deliberate trade permanently unfoldable, and the pressure then goes into removing `regressed` by hand — which clears the label without clearing the regression |

A label is the only one of these that (a) is already in the candidate list,
(b) has an actor GitHub records, and (c) a lane has no reason to be able to
set. The **issue number is required** and is not decoration: the issue is
where the trade is argued, and an override with no issue is an assertion with
no argument — a year later the label is all there is left to read. A bare
`regression-accepted` is refused out loud, with the spelling.

**What enforces "owner-only" is that nothing else sets it.** Not an actor
check: the jobs authenticate with the owner's own `gh` token, so
`labeled`-event actors cannot tell an owner from a job on this host, and a
gate that pretended otherwise would be a check that cannot fail.
`ensure-labels.sh` therefore creates no member of the family (deliberately —
it is the one label in that file no job sets, and the note says so), the
selftest asserts no job calls `label_add` with one, and `roles/board.md` tells
the board it is not theirs. **The remaining hole**, for whoever picks it up:
`gh-label.sh` would take `label_add <pr> regression-accepted:91` from a lane
if a lane decided to run it. Refusing that family inside `gh-label.sh` is one
`case` arm and would close it mechanically; that file is not this lane's, so
it is written down here rather than edited.

## For the next lane

- **The candidate row now has six fields:** number, branch, head, isDraft,
  labels, title. Title stays **last** because `read` gives the last variable
  everything after its tab, so free text in any earlier position lands inside
  a field a gate keys on. Two fixture shims (`85-fold-ci.sh`,
  `91-fold-transient.sh`) emit that row and were updated; a shim still
  emitting five fields does not error, it silently feeds the title into the
  labels gate.
- **PR #137 (lane.branchprune) also edits `fold.sh`.** Unavoidable — both
  briefs name the file. This diff is two functions, a report and a nine-line
  block in the candidate loop, all in one place, to keep that merge cheap.
- **`92-arms-skip-told.sh`'s "a second tick does not tell it again" flakes
  under load, and it is not this lane's.** On the attempt-2 merge run it was
  the single red in `358 passed, 1 failed`; an immediate rerun of the *same
  tree* gave `359 passed, 0 failed`, and pristine `origin/master`
  (`415dcc6997`) in a scratch worktree gave `313 passed, 0 failed`. So it is
  neither my diff nor a master regression — 313 + this lane's 46 = 359 either
  way. The box was at load ~18 on 8 cores with a dozen lanes running
  selftests at once. Worth knowing because the check is a **negative**
  (`! grep -qE "^(pr|issue) comment"` over the whole shim log, not over this
  sha's comment): anything that posts for any other reason on the second tick
  reds it, so it is sensitive to state no other check pins. Rerun before
  debugging it, and do not conclude from one red that the merge broke arms.
- Do not run `fold.sh` or `fold.sh list` against the real host to try
  something out: the tick ends by calling `handback.sh` and `status.sh`, and
  `status.sh` rewrites the live status issue. The fixture is the way.

## Why attempt 1 did not finish

The work was done and CI was green on `f310e308c0`; the session ended with
PR #145 still in **draft**, waiting on a CI result that had already landed.
Nothing else was outstanding. A draft is invisible to every actor here —
`board.sh` skips drafts, `fleet.py`'s READY-NOT-FOLDED counts only
non-drafts, `fold.sh` folds only non-drafts, `handback.sh` does not look at
them — so "green in draft" and "never started" are the same state from
outside, and it cost a whole resume. The fix is the last line of the role
file, not a judgement call: **mark ready when green and current.** Waiting
for CI is not a reason to stay draft; the fold gates on `fold-ready` and the
check rollup, both of which re-evaluate after the fact.

Attempt 2 merged `origin/master` (25 commits, clean — `selftest.d/` was
already this branch's base, so no fragment had to move), re-ran the
selftest, and marked it ready. `lane.armlabel` (#144) landed in that merge
as `selftest.d/94-arms-label-state.sh`; as predicted above the two lanes
share no file, and this gate still reads the label that lane now computes.

## Verification

- `bash docs/testing/jobs/selftest.sh` → **314 passed, 0 failed**;
  `preflight.sh --allow-tracker` passes on the branch.
- After the attempt-2 merge of `origin/master`: **359 passed, 0 failed**
  (the one red seen first was the `92-arms-skip-told.sh` flake above).
- The new fragment run against the pre-change `fold.sh`,
  `ensure-labels.sh` and `roles/board.md` (a copy in a scratch tree, never
  the real path): **30 of its 46 checks FAIL**. The 16 that pass are the
  must-not-move legs — a PR with no verdict still folds, a `verified` PR
  folds, `list` writes nothing — which is what they are for.
- Two mutants of the *new* gate, because a check that cannot fail is not a
  check:

  | mutant | what failed |
  |---|---|
  | `has_label` matching a substring instead of a whole label | exactly one check: `unregressed` folding |
  | the override regex not requiring `[0-9]+` | exactly the seven malformed-override checks |

- One trap found in my own fixture, which is worth repeating: the first gh
  shim answered `api .../labels` with the label csv on **one line**, so
  `label_rm`'s `grep -Fxq` matched nothing, no DELETE was ever issued for a
  multi-label PR, and *"fold-ready is kept"* was a check that could not fail.
  The positive control passed anyway because it used a single-label PR — the
  control did not exercise the path the negative depended on.
