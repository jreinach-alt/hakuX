# lane.armsscope: arms.sh scopes a PR's verdicts to that PR

Brief: `briefs/armsscope.md` (hostops, 2026-09-26, from lane.remote's report on #274).
PR #409. Harness only; no hw/ file, so no arm.

## The defect

`build_label_index()` keys every pair on the branch in its `source`, and
`label_decide()` counts every judged pair on that branch. A branch name outlives
its PR. lane.remote reuses `claude/docs-tooling-agentic-coding-u152m1` for every
PR, so PR #389 got the #60 PASS and the four 09-20 GL FAILs of PRs that had
already folded. The withdrawal pass then posted those verdicts on #389 as its own.

## The rule chosen

A pair is **not this PR's** when its prediction file is **on the trunk** and the
branch's diff against the trunk (`git diff --no-renames --name-only
origin/master...<head>`) **does not touch it**. Such a pair is dropped before
withdrawal, supersession and counting. So it neither labels the PR nor is listed
`withdrawn`.

Why this rule and not the brief's two alternatives:

- **"In the PR's diff" alone** (brief option 2, strict). This drops a verdict
  whose prediction the lane deleted from its own branch, so `git rm` on a FAILed
  registration would clear a live `regressed`. Supersession exists to close
  exactly that exit. The selftest has a mutant for it (`deleter` case).
- **Merge base / registered_utc against the first commit past master** (brief
  option 1). Dates on commits change under a rebase or cherry-pick, and a lane
  that rebased after its arm was queued would silently lose its verdicts,
  FAILs included. The fixed fact is simpler: `collect()` reads the trunk
  first, so a pair sourced from a branch was *not* on the trunk when it was
  queued. If its prediction is on the trunk now, a fold put it there.
- A PR that **edits** a folded prediction has it in its diff, so it counts
  (the `edited` case). Single-use `lane/<x>` branches are unchanged, because
  their predictions are not on the trunk until they fold.
- Anything git cannot answer (no base, no head, a failed diff or ls-tree)
  keeps every pair, which is the old behaviour. That matches the withdrawal
  rule next to it.

Cost: one `git diff` (already there for withdrawal, and now also run when the
branch has only PASSes) plus one `git ls-tree` of `docs/testing/predictions/`
per decision. Both only run when the branch has a judged verdict. There is no
per-row git call, so nothing is quadratic.

## Residual, not fixed here

- A reused branch whose **earlier PR closed without folding** leaves its
  predictions off the trunk, so they still count toward the next PR on that
  name. Handling it needs the "not in the diff" test, and that reopens the
  deletion exit above. It never happened. lane.remote's PRs fold.
- `withdrawn_refs_for()` prefers `refs/remotes/origin/<branch>` over
  `refs/remotes/pr/<n>`. The tick fetches the former only for `lane/*`, so a
  non-lane branch's origin ref is whatever the last manual fetch left. In the
  replay it was newer than `pr/389` (07a47ebd vs 9df6b13c). Resolution order
  is outside this brief.
- The judge loop still *posts* a verdict comment on whatever PR has the
  branch at judge time. That is usually the PR that queued it. Only the label
  decision is scoped here.

## #389 replay, read-only

`.scratch/replay.sh` points a scratch `$HAKUX_WORK` at the live
`arms/pairs` and `arms/judged` through symlinks, uses a copy of
`arms/log/prs.tsv` and the live object store, and runs `arms.sh state
claude/docs-tooling-agentic-coding-u152m1`. The scratch dir takes the only
write (label-index.tsv). Nothing was posted.

Before (master's arms.sh, 2026-09-26T17:33:25Z, head 07a47ebd6b, pr/389
9df6b13c57, master 504aeee4d4):

```
STATE=verified
withdrawn 2026-09-20-gl-x1a7-read-side.json
withdrawn 2026-09-20-gl-stale-surface-blit.json
withdrawn 2026-09-20-gl-x1a7-download.json
withdrawn 2026-09-20-gl-stale-surface-blit-opengl.json
**PR label: `verified`** -- every one of the 1 judged verdict(s) on `claude/docs-tooling-agentic-coding-u152m1` that still counts is a PASS.

| verdict | prediction | issue | counts? |
|---|---|---|---|
| PASS | `2026-09-20-gl-texture-cache-vulkan-inert.json` | #60 | yes |

- `2026-09-20-gl-x1a7-read-side.json` FAILED, and is **withdrawn**: ... (four such lines)
```

After (this branch, 2026-09-26T17:34:25Z, same refs):

```
STATE=none
```

All five predictions are on master, and #389's diff touches none of them.

## Proof

`selftest.d/94-arms-verdict-scope.sh` builds the history in its own repo: an
earlier PR on `claude/reuse` whose PASS and FAIL predictions (and the FAIL's
code) folded, then a new PR on the same name. Cases: no own verdict gives
`none` (it was `verified` + `withdrawn` before), the PR's own PASS and FAIL
label it, a folded prediction the PR edits counts, a single-use lane is
unchanged, and a deleted own prediction keeps its FAIL. A tick posts nothing
on the reused PR. Three mutants (no scoping, diff-only, trunk-only) each go
red on their named case.

## Do not repeat

- The Bash tool here rejects `$VAR` expansions in some command lines. Put
  replay and selftest drivers in `.scratch/*.sh` files.
- The full selftest takes more than 10 minutes on this box. Detach it and
  poll its log.
