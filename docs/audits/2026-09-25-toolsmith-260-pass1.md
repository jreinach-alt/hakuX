# Audit pass 1: PR #260 (lane/toolsmith) -- arms.sh withdrawn FAILs, idle-tier backpressure, snapshot by rename

Auditor: job.cloud, 2026-09-25. Diff read: `gh pr diff 260` at head
`8655834510` (10 files, +589 / -20). The file is named `-260-` because
`2026-09-25-toolsmith-pass1.md` already holds PR #229's audit. This follows the
`-249-` precedent.

**Result: 1 MEDIUM, 3 LOW, 0 HIGH -> `needs-remediation`.**

## MEDIUM

### M1. Renaming a file that holds the refuted code withdraws the FAIL, and the PR can then fold

`arms.sh` `label_decide` -> `names()` runs `git diff --name-only`, which is
porcelain `git diff`, so rename detection is on by default (`diff.renames`).
The branch set `base...head` then lists only a renamed file's **new** path. The
arm's code set `a_ref..b_ref` lists the **old** path. They do not intersect, so
`withdrawn()` reports the FAIL as gone even though every refuted line is still
on the branch.

**Failure scenario, reproduced** with git 2.43.0 in a scratch repo
(`/tmp/rn260.sh`, the same `git diff` invocations arms.sh makes):

```
arm code set (a..b):                          src/a.c
branch set, as arms.sh runs it (base...head): src/a2.c
branch set with --no-renames:                 src/a.c  src/a2.c
```

Here the lane's candidate edits `src/a.c`, its arm FAILs, and the lane
then `git mv`s the file, for example as part of a refactor, while keeping the
refuted change. On the next tick `state` prints `withdrawn <prediction>` and
`STATE=none`. The new tick loop removes `regressed` and posts
`[job.arms] WITHDRAWN`, and `fold.sh` (which gates only on the
`regressed` label, lines 697-805) folds a measured regression onto master.
This is the exact outcome the `regressed` gate exists to stop.

The blast radius is bounded: it needs a rename or move of the refuted file,
and the WITHDRAWN comment names the file as gone, which a reader can
catch. So this is MEDIUM, not HIGH.

**Remedy.** Pass `--no-renames` to both diffs in `names()`. A rename then
shows as delete-old plus add-new, and the old path stays in the branch set.
Add a fragment case (f) to `94-arms-withdrawn.sh`: `git mv` of a refuted file
with its content intact must stay `regressed`. Add a mutant that drops
`--no-renames` and must be red on (f).

## LOW

### L1. A withdrawal that leaves live PASS verdicts gives the PR neither label

When the recomputed state is `verified` (the (e) shape: a withdrawn FAIL next
to live PASSes), the tick removes `regressed` but does not add `verified`. The
judge loop took `verified` off when it judged the FAIL (`label_add regressed
&& label_rm verified`). So `arms.sh state` says `verified` and the PR carries
nothing. `fold.sh` does not require `verified`, so this has no fold effect.
It is only a label that disagrees with `state`. The comment "`verified` is not
added: a withdrawal is the absence of a measurement" is right for `STATE=none`,
but not when live PASSes remain.

### L2. The "code that is gone" line can name files the lane never touched

`code = git diff a_ref b_ref` is two-dot. When `a_ref` is not an ancestor of
`b_ref` (the lane merged a newer master before registering), the set includes
master's own changes between `a_ref` and that merge. Those files are never in
the branch's three-dot diff, so they are listed as "code that is gone" in the
WITHDRAWN comment and in `state`. In this direction it never causes a false
withdrawal: an extra file can only keep a FAIL alive if the branch still
touches it. It is misleading prose. `git diff a_ref...b_ref` (merge-base)
would restrict it to the lane's own change.

### L3. The idle-tier fragment never runs the zero-non-z queue

`waiting=$(ls ... | grep -vc ...)` makes grep exit 1 when it selects nothing.
arms.sh has `set -u` and no `set -e` (line 55), so `waiting` is `0` and the tick
continues. I checked that, and it is fine today. `94-arms-idle-tier.sh` tests
1 and 4 normal requests but never 0 (for example 100 `z-*` only). If `set -e`
is ever added, the empty queue, which is the most common state, would abort
the tick, and no fragment would catch it. Adding a 0-normal leg costs one line.

## Checked, no finding

- **Withdrawal rule, other directions.** An unresolvable ref, a missing head,
  an unrelated history, or an empty code set all give `names()` -> `None` or
  empty -> the FAIL is kept. A partial revert is kept (`code & have`). A PASS
  is never withdrawn (the `cls != "FAIL"` guard). A branch name in `a_ref`
  or `b_ref` does not resolve in `$REPO`, so the FAIL is kept.
- **Head and base refs.** `withdrawn_refs_for` reads `origin/<b>`, then
  `refs/heads/<b>`, then `refs/remotes/pr/<n>`. The PR map is keyed on
  `headRefName`, and `collect` writes the same name into `source` (line 241),
  so fork PRs are found. `state` stays offline, as its header promises.
- **Tick label removal.** `label_rm` returns 0 when the label is absent
  (gh-label.sh:49), so a PR with no `regressed` is not retried every tick.
  The marker is keyed on the PR and the withdrawn set. A new withdrawn FAIL
  gives a new marker, and a new live FAIL leaves the state `regressed`, which
  is skipped.
- **Judge comment.** `sed '1d; /^withdrawn /d'` strips the machine lines
  from the posted decision.
- **Defect 12.** `grep -vc '/z-[^/]*$'` matches only basenames that start with
  `z-`. `status.sh` and `board-status.sh` only display the count.
- **Defect 12b.** `rev-parse --short --verify "$REF^{commit}"` peels an
  annotated tag. The resolved-message comparison is unchanged.
- **Defect 13.** `cmp -s` skips unchanged files. `cp` to
  `.$f.tmp.$$` then `mv -f` is an atomic same-directory rename. When it
  fails, the temp file is removed. Two workers are two PIDs, so their temp
  names cannot collide. The fragment is deterministic (8-byte offset) and its
  mutant is shown red.
- **Fragments.** Each builds its own repo, work dir and dispatch dir, and
  cleans up. Mutants run from copies. (e) puts the withdrawn arm in the
  middle of three.

## For remediation

Fix M1 (`--no-renames`, case (f), and a mutant). L1-L3 are optional.
