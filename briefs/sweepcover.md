# The full-corpus sweep: score what it can, void what it cannot read, and stop leaving 40% of the goldens out

Lane: sweepcover            Issues: #291 #292 #293 #294 #295 #296 (coverage), plus two scorer defects below
Base: origin/master
Files: docs/testing/scoreboard.py, docs/testing/collect_sweep.sh, docs/testing/queue_full_sweep.sh,
docs/testing/jobs/selftest.d/88-sweep-cover.sh, docs/lanes/sweepcover/**
Needs device: only to prove the new legs (small runs). Needs NDK: no. Prediction: none. This is
harness work.

## Why, and what is urgent

Two full-corpus sweeps are running now at idle priority: `z-a-now-2b04d4d422` (current master)
and `z-b-v040j1` (the v0.4.0-j1 release). They are the evidence for the owner's score table and
for the 0.5 release. **Their columns are collected by `collect_sweep.sh` and summarised by
`scoreboard.py`, and neither reads the status column.** An `unreadable` row has `differing = 0`, so
it would count as an **exact** capture in the new column. That is the same false win toolsmith's
defect 0 removed from arm verdicts (PR #249). WSL-interop pulls are still truncating PNGs (56 and
51 unreadable W_param captures in two arms today), so this will happen on the sweep.

## The job, in order

1. **URGENT, first PR: honour the status column.**
   - In `scoreboard.py` (104-136) and `collect_sweep.sh` (48-73), a row whose status is not `ok`
     is **void**: not exact, not counted in structural px. It is listed per category as its own
     count ("n void"), so a column says how much of it was unmeasured.
   - `label-differs` counts as scored content (the console calibration on this disc had 0 such
     rows in 3,379 captures). `blank` and `white-content` also count as scored content.
     `unreadable` / missing / `size` / `no-golden` are void.
   - Fix `CATEGORIES`: remove the phantom `Fog_multiple_vertices`, and add Fog planar vsh and
     Surface as vertex array.
   - Get it folded before the "now" column is collected. The sweep will not finish before this
     evening.
2. **`queue_full_sweep.sh`:**
   - Resolve the ref as `"$ref^{commit}"`. A tag resolved to its tag object on 2026-09-25 (toolsmith
     defect 12b moves here; the file is yours).
   - Add optional legs, each a separate label so the column says which disc produced it:
     - `--with-depth-2025`: the v2025-03-14 disc for Depth_buffer's 640 retired goldens (#291);
     - `--with-blend-interactive`: the interactive disc for Blend TestDetailed (#292);
     - `--with-rtloop`: RenderTextureLoop as its own `--only-tests` leg (#294).
   - A `--base-iso` option, so a sweep can run the 6743b6a disc (#293). The dispatcher's
     single-golden-root limit (`dispatcher.sh:46/:1039`) and `arms.sh:353-374` are lane.toolsmith's.
     Say in NOTES exactly what they need, and do not edit them.
3. **Unscoreable goldens** (#295, 20 of them) and the **interactive-only suites** (#296, Clipping
   precision 48, PVIDEO 23): a list the scorer reads, taken out of coverage denominators and
   reported as "unscoreable" or "not captured by design". This ends the permanent PARTIAL COVERAGE
   warnings that lanes now read as healthy.

## Proof

- **`selftest.d/88-sweep-cover.sh`,** built on fixture score files with `ok`, `unreadable`,
  `blank`, `label-differs` and `size` rows:
  - the column's exact count excludes the void rows;
  - its void count equals them;
  - its structural px excludes them.
- **Mutants:** count `unreadable` as exact (red); drop the void count (red).
- **A falsification run** against the old `scoreboard.py` and `collect_sweep.sh` in a scratch
  worktree at `origin/master`. The old code must count the unreadable rows as exact. Stage by name.
- `bash docs/testing/jobs/selftest.sh`: all green, with the totals in the PR body.

## Do not

- **Touch `score_sweep.py`, `dispatcher.sh` or `arms.sh`** (lane.toolsmith's), or `AGENTS.md`'s
  label-differs line. Propose the wording in NOTES; the host edits AGENTS.md.
- **Re-run or re-queue the running sweeps.**
- **Trigger CI as a self-check.**

## Done when

- The status-column PR is folded, ideally before the "now" sweep finishes.
- The legs and unscoreable list are in a second PR.
- NOTES record what toolsmith needs for #293.
