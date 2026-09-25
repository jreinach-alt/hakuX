# arms.sh: a FAIL whose registered code is gone from the branch is `withdrawn`, not `regressed`

Lane: toolsmith (standing)            Issue: none (harness defect; decision #257 option 3)
Base: origin/master (PR #249, defects 0-10 of the dispatch-hardening brief, is folded as 93e356b9fd)
Files: docs/testing/jobs/arms.sh, one new `docs/testing/jobs/selftest.d/NN-arms-withdrawn.sh`
(two digits; the runner sorts `[0-9][0-9]-*.sh` by full name), docs/lanes/dispatch-hardening/NOTES.md
Needs device: no. Needs NDK: no. Prediction: none. This is harness work; the proof is the
fragment, the mutants and a falsification run against the old arms.sh.

## The defect (defect 11 of `briefs/toolsmith-dispatch-hardening.md`)

`arms.sh` recomputes a PR's `regressed` label from the newest verdict on disk.

A lane whose arm **refutes** its candidate reverts the code, which is the
correct outcome. That leaves a docs-only branch. A docs-only head builds
master's binary, so no arm can ever supersede the FAIL, and the PR stays
`regressed` forever.

- It happened on PR #252 (#224 family B). The only exits were an owner override
  that "records an acceptance that is not one" (#257, option 1) or re-landing
  the docs from a fresh branch with no prediction (option 2). The host did the
  second, as PR #259.
- #246 (#223) had the same shape, but it registered nothing, so it escaped.

## The job

A FAIL verdict is **withdrawn** when the branch head no longer touches any
file that the arm's b_ref changed against its a_ref.

1. Compute the arm's code files: `git diff --name-only <a_ref> <b_ref>`,
   restricted to paths outside `docs/`.
2. Compare them with `git diff --name-only origin/<tip>...<head>` for the PR.
3. If none of the arm's code files is still in the PR's diff, the verdict is
   withdrawn:
   - it does not make the PR `regressed`;
   - `arms.sh state` prints `withdrawn <prediction>`, so the record stays
     visible;
   - the verdict comment is untouched.

A PASS is never withdrawn by this rule. A FAIL whose code is still partly in
the diff stays `regressed`: a partial revert is not a withdrawal.

## Proof

- **The fragment,** with git fixtures, no shared state, and output words
  asserted, not only exit codes:
  - (a) a refuted-then-fully-reverted branch reads `withdrawn`, not
    `regressed`;
  - (b) a partly-reverted branch stays `regressed`;
  - (c) a branch whose FAIL code is intact stays `regressed`;
  - (d) a PASS on a branch with no code change stays whatever it was.

  Three candidate diffs where one must be chosen, so the right one sits in the
  middle.
- **Mutants, each red:**
  - drop the `docs/` restriction, so NOTES keep a FAIL alive;
  - treat any overlap as withdrawal, so (b) goes wrong.
- **A falsification run** against the real old arms.sh in a scratch worktree
  at `origin/master`. Never swap the file in place, and stage by name. (a) must
  be red for the reason this brief exists: the old code says `regressed`.
- **One real check:** run `arms.sh state lane/shadetie224` on the host. #252's
  branch still exists on origin, closed unmerged, and it must read `withdrawn`.
- `bash docs/testing/jobs/selftest.sh`: all green, with the totals in the PR
  body.

## Done when

- The fragment, mutants and falsification behave as stated.
- NOTES record it under "Defect 11".
- The PR carries the lane template with its `Files:` line.
- Preflight passes, and the PR is marked ready. It touches the verdict path, so
  it gets `needs-audit-1`, like #249.

## Defect 12 (added 2026-09-25 11:15 PDT, owner's ask): arms backpressure ignores queue priority

The owner wants the device queue to put urgent work ahead of long runs. The
dispatcher already does this: it serves `queue/` in ASCII order, `0-*` first,
then epoch-named requests, then the `z-*` idle-priority full-corpus sweep
(`queue_full_sweep.sh`), yielding between suites. **`arms.sh` does not.** Its
backpressure counts every queued request, `waiting=$(ls "$D"/queue/*.req | wc -l)`
(arms.sh:657), so a queued ~100-suite `z-*` sweep keeps `waiting` at or above
`ARMS_QUEUE_MAX` (4). The arms job then never queues another lane's arm, and the
most urgent work starves behind the least.

The host has a stopgap in place: a systemd drop-in sets `ARMS_QUEUE_MAX=1000`
(`~/.config/systemd/user/hakux-arms.service.d/zsweep-backpressure.conf`). That
removes backpressure entirely, so it is not the fix.

**Fix:** count only requests that sort ahead of the idle tier (not `z-*`), and
print both counts in the "queue has N waiting" line. Audit every other
queue-depth reader for the same mistake, such as `fleet.py`'s queue-stall check
and `status.sh`. A `z-*` request waiting for hours is the design, not a stall.

**Proof:** a fragment with a fake queue of 100 `z-*` requests plus 1 normal
request, in which the arms job still queues a pair. Show the mutant (count
everything) refusing it, and the old arms.sh refusing it too. After it folds,
the host deletes the drop-in; say so in the PR body.
everything) refusing it, and the old arms.sh refusing it too. After it folds,
the host deletes the drop-in; say so in the PR body.

**Defect 12b (same area, one line):** `queue_full_sweep.sh v0.4.0-j1` resolved the annotated tag to its **tag object** (`df3978f7b9`), not its commit (`aeb4a096b6`), and wrote that into all 100 requests' `ref`. The build would still peel it, but every result row and "hw commits behind tip" then names a sha that is not a commit. Resolve `"$ref^{commit}"`. The host withdrew those requests to `queue/withdrawn/` and re-queued them by commit on 2026-09-25.

## Defect 13 (added 2026-09-25 11:40 PDT; found by lane.xbox): a worker's re-exec corrupts the other device's run in flight

`snapshot_scripts` copies the scripts into the shared `$SNAP` with `cp -f` (dispatcher.sh:118), **in place**, and bash reads a running script lazily, by byte offset.
- **What happened:** at 11:11:16 the Nova worker saw its scripts change on disk (the host had fast-forwarded the checkout) and re-execed. That rewrote `$SNAP/run_disc.sh` under the Thor, which was mid-way through it. The Thor's bash then read the new file at the old offset (`line 137: cess: command not found`). The run reported "the emulator never started" with 0 captures, and lane.xbox's `1790359588-xbox-full6743-dry1` was voided.
- **It recurs** at every fold that touches a SCRIPT_DEPS file, and it looks like a device failure. Details: https://github.com/jreinach-alt/hakuX/pull/238#issuecomment-5837670338

**Fix:** write each snapshot file to a temp path in the same directory and `mv` it into place. A rename swaps the inode, so a bash process already reading the old file keeps its inode. Consider per-worker snapshot directories too, so one worker's re-exec never touches the scripts another worker runs.

**Proof:** a fragment where one process sources a long script from `$SNAP` while `snapshot_scripts` rewrites it with different content. It is red with `cp -f` (a garbled line or a parse error) and green with temp plus `mv`, with the mutant shown.

## Defects 14-17 (added 2026-09-25 13:10 PDT; from the host's tests-that-never-run inventory)

- **14. An env pref nobody requested runs on every request.**
  - **What happened:** the Nova's `x1box_prefs.xml` held `env_vars = VK_LAYER_ENABLES=VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT` from at least 02:09 PDT, with no dispatcher marker. Khronos sync validation ran on every Nova request, including the release sweep's Nova suites and every arm. Master's W buffering aborted twice with `std::bad_alloc` inside `libVkLayer_khronos_validation.so` (from `pgraph_vk_clear_surface`).
  - **Why nothing caught it:** `dispatcher.sh`'s rule of touching nothing without a marker is right for a human's setting, but that rule made the problem invisible. The host cleared it by hand under a hold.
  - **Fix:** on every request, read the device's `env_vars` (one run-as read, already cheap) and record it in `result.json` as `device_env`. When it is non-empty and the request asked for none, log `WARNING: unrequested device env: …` into `run1.log`, and let `ab_compare`/`scoreboard` treat an arm whose two halves differ in `device_env` as not comparable.
- **15. WSL-interop pulls truncate PNGs.**
  - **What happened:** W_param had 56 and 51 unreadable captures in two arms today (UtilAcceptVsock), and dry3 shows the same. PR #249 voids the arm, but the pull itself is not fixed.
  - **Fix:** after a pull, verify each PNG ends in `IEND` and matches the device-side size, and re-pull what does not, up to twice, before scoring.
- **16. The `blank` heuristic gives false positives** (`score_sweep.py:229-230`). 13 of the 15 `blank` rows are near-exact against goldens that are themselves at least 99% one colour (#297).
  - **Fix:** do not tag `blank` when the golden itself is at least 99% one colour; score the row normally.
- **17. One golden root.** `dispatcher.sh:46/:1039` scores against a single golden root, and `jobs/arms.sh:353-374` drops suites with no golden directory. So the 16 tests added at 6743b6a, 11 of which now have console references at `~/hakux-work/hardware/runs/2026-09-25-refs6743/console-run/console/`, can never be scored (#293).
  - **Fix:** accept an ordered list of golden roots. For each suite the first root that has the test wins, and `result.json` records which root scored each row. lane.sweepcover owns `queue_full_sweep.sh`'s `--base-iso` side, so coordinate through #293.

Order: 14 first, because it silently changes every measurement. Then 15, 17 and 16.
