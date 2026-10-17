# lane worktrees are created sparse, without docs/lanes/pathfind/runs (#433)

State: ready

Lane: sparsewt1017            Issue: #433
Base: master @ 8d260f39fc319c50c7b40af85d2a00440f680ecd
Files: docs/testing/lane.sh, docs/testing/jobs/selftest.d/99-lane-sparse-worktree.sh, docs/lanes/sparsewt1017/NOTES.md, docs/lanes/sparsewt1017/PR.md
Prediction: none: no arm
Needs device: no    Needs NDK: no
Release note (performance): none

Every lane worktree was a full checkout, and `docs/lanes/pathfind/runs/`
(held-run evidence, 54 GB across 28 trees) was ~1.9 GB of each one, for a
subtree no lane ever reads. `docs/testing/lane.sh`'s `start` command now
builds both of its `git worktree add` forms (the fresh `-b branch
FETCH_HEAD` form and the resume-after-crash `-B branch origin/branch` form)
through one new helper, `lane_worktree_add()`: `--no-checkout` first, then
`git sparse-checkout set --no-cone '/*' '!/docs/lanes/pathfind/runs/'`, then
`git checkout <branch>` to populate -- so the ~2 GB is never written and
deleted again.

Two exemptions, both inside the helper: a lane named `pathfind` (its
worktree IS the live harness tree and reads its own `runs/`) gets a plain
full checkout, and so does any lane whose brief carries an explicit
`$WORK/briefs/<name>.fullcheckout` marker.

Verified on scratch fixtures (see NOTES.md for the numbers): both
worktree-add forms produce a clean `git status`, the correct branch, and an
excluded `docs/lanes/pathfind/runs/`; the shared repo config never gains
`core.sparseCheckout` (it lands in each worktree's own `config.worktree`,
since the repo already carries `extensions.worktreeConfig = true`); the real
repo (`/home/justin/hakuX`) is untouched by any of this lane's testing.

New selftest fragment `docs/testing/jobs/selftest.d/99-lane-sparse-worktree.sh`
(22 checks) proves the mechanism against a real throwaway origin -- both
worktree-add forms, both exemptions, the config isolation, and a falsifying
mutant (the exemption condition forced to `if true`) that turns the
exclusion checks red, so the passing checks aren't just "lane.sh ran".
Ran it standalone (22/22 green) plus every other `lane.sh`-touching
fragment in `selftest.d` (`98-lane-shape.sh` 92/92, `99-lane-path.sh` 32/32,
`99-lane-model-file.sh`, `99-lane-no-background.sh`,
`99-cloud-lane-branch.sh`, `99-handback-lane-line.sh`, all green) -- the
full 147-fragment suite does not finish inside this tool's 10-minute command
limit, so it was not run end to end; `63-status-lanes.sh` (which never
references `lane.sh`) has 4 pre-existing failures unrelated to this change.
`bash -n docs/testing/lane.sh` passes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
