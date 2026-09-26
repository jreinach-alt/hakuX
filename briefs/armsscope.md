# lane.armsscope -- arms.sh must scope a PR's verdicts to that PR, not to its branch name

Lane: armsscope
Issue: none (harness defect; host-created 2026-09-26 10:40 PDT by hostops, from lane.remote's report on #274)
Base: origin/master (merge origin/master first; never rebase)
Files: docs/testing/jobs/arms.sh, docs/testing/jobs/selftest.d/94-arms-verdict-scope.sh, docs/lanes/armsscope/NOTES.md

## Why (evidence)
arms.sh builds `LABEL_INDEX` (`$A/log/label-index.tsv`, build_label_index()) with the BRANCH as the key. Every
pair whose `source` is `<branch>:<prediction>` counts toward the label of whatever PR currently has that head
branch. A branch that is reused across PRs therefore inherits the verdicts of long-folded work.

The observed case is lane.remote's report on #274 (comment at 2026-09-26T17:27:30Z). Branch
`claude/docs-tooling-agentic-coding-u152m1` is fixed and reused for every lane.remote PR.
- arms.sh's withdrawal comment 5846388108 on PR #389 counted `2026-09-20-gl-texture-cache-vulkan-inert.json` (#60,
  a_ref 01047cf3, b_ref da9e02a2) as #389's PASS ("PR label: verified").
- The same comment withdrew four 09-20 GL FAILs that belong to earlier PRs: x1a7-read-side, stale-surface-blit,
  x1a7-download and stale-surface-blit-opengl.
- Nothing is wrong on #389 today, because the withdrawal path applies no label. But a judged arm on this branch would
  count the stale PASS. And if a later PR on the branch touches gl/texture.c, gl/surface.c, gl/shaders.c or
  glsl/psh.{c,h}, those FAILs come back and read as `regressed`.
The same hazard applies to any lane/<x> branch name that is reused after its PR folds (fold.sh prunes most of them,
but not remote lanes).

## Build
1. Scope each pair to the PR it belongs to. Key it by the PR's merge base, keeping a pair only if its a_ref/b_ref
   (or its registered_utc) is not older than the PR's first commit past origin/master. Alternatively, key it by the
   prediction files present in the PR's own diff (`git diff --name-only origin/master...<head>`). Choose one, say
   why in NOTES, and keep the one-pass cost (the header comment above build_label_index: the tick is ~11 s, no
   quadratic walks).
2. A verdict whose prediction file is not in the PR's diff against origin/master must not count toward that PR's
   label, and must not be listed as withdrawn on it. The prediction was folded with an earlier PR, so it has
   nothing to do with this one.
3. Keep every existing behaviour for single-use lane/<x> branches: their predictions are in their diff.

## Proof
- `selftest.d/94-arms-verdict-scope.sh` has a fixture branch carrying a folded prediction from an earlier PR (with
  a PASS pair and a FAIL pair) and a new PR on the same branch name with its own prediction. Assert on the output
  words:
  - the old PASS does not label the new PR;
  - the old FAIL is neither counted nor listed `withdrawn`;
  - the new PR's own verdict still labels it;
  - a single-use lane branch labels exactly as before.
- Replay the real case read-only: run the label decision for PR #389 against the live `$A` (arms dir) with your
  change. It must no longer list the #60 PASS or the four 09-20 FAILs. Record the before and after output in NOTES.
  Never post to a PR from this lane.
- `bash docs/testing/jobs/selftest.sh` green, preflight green.

## Do not
- Edit board files (territory.toml, nv2a_issues.toml).
- Change how verdicts are judged (ab_compare, the leg rules), only which PR they count toward.
- Touch any other job script. arms.sh is lent to you from [lane.toolsmith] and returns there on fold.

## Done when
The scoping change and selftest have landed, NOTES records the #389 replay before and after, and the PR is ready
(merge master first). This touches no hw/ file, so no arm is needed: say that in the PR body.
