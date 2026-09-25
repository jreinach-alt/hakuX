# dispatch-hardening (lane.toolsmith), 2026-09-25

Brief: dispatcher hardening, defects 0-10. PR #249.
Base: master @ 0a4e284536, which is after #206 folded.
Everything here is harness work, so there is no arm and no prediction.

All eleven defects are fixed in this PR. `jobs/selftest.sh` passes 1253 checks
with 0 failing. `ab_selftest.sh` passes 14 of 14. `preflight.sh` passes.
The new checks are in `jobs/selftest.d/51-dispatch-hardening.sh`, parts A-I,
plus four additions to `66-deliveries.sh`. Every part that has a mutant was
confirmed red against it: the mutant is built in a symlink tree, and the check
that it differs from the real file runs first.

## Defect 0: an unreadable capture read as "repaired to exact" (top priority)

What changed:

- `ab_compare.py` now has `SCORED_STATUSES`: ok, blank, label-differs and
  white-content. That is score_sweep's own `scored` set.
- A capture is VOID if any run in either arm has a status outside that set,
  or if the capture is missing from one arm. A void capture is in no class and
  in no total. It is listed by suite and cause right under the counts.
- A registered leg that lands on a void capture is neither held nor broken.
- A global `expect_counts` leg is void if ANY capture is.
- If there are void legs and no real failures, the verdict is
  `VERDICT: INCOMPLETE -- ...`. That line deliberately contains neither PASS
  nor FAIL, because arms.sh classifies a verdict by those substrings, and an
  unmeasured arm must set no label and supersede nothing.
- A real FAIL still reads FAIL, and lists the void legs below it.
- `--probe` refuses a void capture, so ab_bisect skips the step instead of
  reading median 0 as exact.
- The dispatcher's result writer now counts only scored rows in
  `runs[].captures`, `exact` and `captures_vs_goldens`. It records the rest as
  `runs[].unscored`. A run that is all unreadable therefore hits the existing
  0-captures ERROR.
- The three copies of the status set (score_sweep, ab_compare, dispatcher)
  are checked for equality by selftest part B.

**Deviation from the brief's literal wording.** The brief says "anything but
`ok`" is void. I made void mean anything outside the scorer's `scored` set.
`blank`, `white-content` and `label-differs` are all computed from both
images' pixels. A blank capture that starts to draw is exactly the movement a
fix exists to produce, so voiding it would void real must-move legs.
`unreadable`, `size` and `no-golden` write `differing = 0` because there is no
number to write, and those are the three that faked results.

Falsified on the real pair `42c014b32fab` (#224; fix
`1790327180-arms-shadeflat224-fix-820924`):

| ab_compare | better | W_param better | repaired to exact | VOID | verdict |
|---|---:|---:|---:|---:|---|
| master (`/tmp` worktree at 0a4e284536) | 64 | 52 | 52 | - | FAIL, 53 of 461 checks |
| this branch | 12 | 0 | 0 | 56 (W_param, B unreadable) | INCOMPLETE, 3 void legs |

The 12 remaining movers are the real ones. The prediction's
`expect_counts better=12` would have matched them, but that leg is void,
because 56 captures could not be counted.

## Defect 1: the sweep preemption. Deleted

I deleted it rather than fixing it:

- `preempt_sweep` never ran. `dispatcher.log` begins 09-12 11:03 and has zero
  "preempting the sweep" or "resuming the sweep" lines.
- The pid in `night19/sq_g0/pid` (2771299, written 09-12 00:25) is not a
  live process.
- Master's `sweep_queue.sh pause` with only `SWEEP_STATE` set exits with
  `BASE_ISO: set BASE_ISO to ...`. It called `adb devices` once and did
  nothing else.

The corpus sweep is `z-sweep-*` queue work now, sorted last, so nothing needs
the hook. `SWEEP_STATE`, `SWEEP_DEVICE`, `sweep_running` and the status line
went with it. `docs/orchestration.md` says so where the old rule was stated.

`sweep_queue.sh` stays as a standalone tool, and two of its bugs are fixed:

- `start` records the device in `$STATE/serial`, and every other verb reads
  it back.
- The four build inputs are demanded only by `start`.

Selftest part D checks it: with the thor listed first by adb, `pause`
force-stops on ee317437 only and needs no build inputs.

I left `sweep_queue.sh` and `make_isolation_discs.py` in `SCRIPT_DEPS`. It
does no harm, and changing the list only churns 97's closure check.

## Defect 2: unbounded adb calls in the serve path

- `adb_call <secs> <what> [--in FILE] args` is new, in devices.sh.
  dispatcher.sh and run_disc.sh already source devices.sh, and the snapshot
  already ships it.
- Deadlines: the install gets 300 s (`ADB_INSTALL_TIMEOUT`). The pref
  read/write/read-back, the title check and the force-stops get 30 s
  (`ADB_QUICK_TIMEOUT`). `adb devices` gets 30 s.
- A hang is written to `ADB_HUNG_FILE`, which is per device and cleared at
  each claim. It has to be a file because most calls sit in a pipe or a
  `$(...)`.
- `adb_error` puts the hung call into the ERROR line. The worker then leaves
  through the post-claim exit it would have taken anyway.
- `apply_env_pref` keeps its marker on a hang. Previously, when clearing, an
  unreadable prefs file dropped the marker, and a hang would have left the env
  on the device with nothing remembering it.

Falsified against master's real dispatcher.sh in a scratch worktree, using a
fake adb that never returns from `install`:

| dispatcher.sh | outcome |
|---|---|
| master | still blocked when the outer 40 s timeout fired (exit 124). adb was asked to `install -r`, there was no ERROR, and the last log line was `binary e3b0c44298fc` |
| this branch | returned in 6 s. ERROR: `install failed: adb hung -- adb install -r (no answer in 5s)` |

Selftest part C covers the same thing: C1 for install, C2 for the env-pref
calls, and a mutant that is adb_call without `timeout`.

Not covered: `soak_title.sh`'s own calls. It has always used
`timeout 120 adb`, so it is bounded, but it has no retry. The frame capture
was already bounded.

## Defect 3: WSL interop

- **The signature cannot be matched per call.** `1790325543-arms-vshconst-base`
  logged four `UtilAcceptVsock` lines in `run1.log`, although run_disc sends
  those calls' stderr to `/dev/null`. The line is written past the call's own
  redirection.
- `adb_call` therefore retries on the exit status. A failed call (not a hung
  one) is retried twice more, after 2 s and then 6 s. Every routed call is
  safe to repeat. The pref write re-reads its input file (`--in`) on each try.
- **Unverified:** whether an interop drop-out gives adb a non-zero exit. If
  it does not, the retry never fires. The backstop below does not depend on
  it.
- **Backstop:** if a run has 0 captures and `run*.log` carries the signature,
  the ERROR is `adb interop failure: ...`. The attempt is moved to
  `<id>.interop1` and the request is requeued once, with `interop_requeued`
  set. A second loss is final and says so. A startup crash takes precedence,
  because the crash is then the real cause. Selftest part F runs the whole
  disc path of serve_one with stubbed programs.
- **arms.sh:** a sha now counts as run only when two distinct refs have a
  clean result for it. So the ARM ERROR advice to "delete judged/<sha> and
  pairs/<sha>.json" works on a half-run pair. Selftest part E checks it, with
  a mutant.
- **Not done: native Linux adb with `ADB_SERVER_SOCKET=tcp:<win>:5037`.**
  The brief says to prove it on one run first. That needs the Windows adb
  server listening beyond localhost (`adb -a`, a restart of the server the
  devices hang off). That is a host-side change, and a lane may not touch a
  device directly. It is still the better fix, since it removes per-call
  interop entirely. For the owner or host.

Counted today: 12 run logs under `dispatch/results` carry the signature, from
09-13 to 09-25 (the brief had five). They include
`1790327180-arms-shadeflat224-fix-820924`, which is the #224 arm that
Defect 0 is about.

## Defect 4: score_sweep on an empty run

It returns after the counts when nothing was scored. Master's version raised
`ValueError: max() iterable argument is empty` on `--out /nonexistent`; this
one exits 0. The jobs-selftest runner has no numpy, so this was checked by
hand and has no fragment.

## Defects 5-10

- **5. Shader cache.**
  - `clear_shader_caches_on_apk_change` runs after the install. When the apk
    differs from the one this device last ran, it removes
    `files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin`
    via `run-as`. Those are the paths `MainActivity.flushShaderCaches()`
    removes.
  - It is recorded per device (`$D/.shader_cache_apk.<label>`), only after a
    successful clear.
  - `result.json` gains `shader_cache` on both the disc and soak paths.
  - I chose this over "before every run". A same-apk soak keeps its warm
    cache, so its first minute is not shader warm-up. The two arms of an A/B
    are different apks, so each arm starts cold anyway, which removes the
    coupling lane.xbox raised.
  - Selftest part H: the first run clears, the same apk keeps the cache, and
    a new apk clears again.
- **6. Logcat spec.**
  - Added `libc:F` (bionic's assert text), `DEBUG:F` (the tombstone:
    `Abort message:` plus an unwinder backtrace of every thread, which the
    hakuX handler's frame-pointer walk cannot give), `hakuX-stderr:E` and
    `hakuX-vk:I`.
  - `hakuX-stderr` is the app's pump for the process's stderr, and pgraph
    prints the offending format there before it aborts. The spec had dropped
    it all along.
  - `hakuX-vk` is one line, the app's own cache-wipe notice.
  - The hakuX crash handler logs the signal, the pc and an FP backtrace, but
    never the abort message.
  - **Unmeasured:** how loud `hakuX-stderr` is on a run that does not crash.
    The first logcat after this folds should be compared by line count with
    the one before it. If it floods, narrow it; do not drop it.
- **7. Fast crash.**
  - run_disc.sh reads the capture for `Caught signal|Fatal signal|assertion
    ... failed` in the appear loop. On a hit it reports
    `the emulator started and CRASHED ... (Ns): <line>` plus the assert line,
    and stops waiting.
  - Without a CAPTURE_LOG it says a sub-second crash cannot be ruled out.
  - The dispatcher's 0-captures ERROR quotes the crash.
  - Selftest part G, with a mutant.
- **8. Lane allowlist.**
  - The two `docs/testing/*` rules are replaced by explicit prefixes, with and
    without `./`, for request.sh, ab_run.sh, preflight.sh, ab_compare.py,
    ab_bisect.sh, diff_specimen.py, check_territory.py, check_coverage.py and
    jobs/selftest.sh. `lane_preflight.sh` does not exist.
  - Proven with a headless `claude -p` (haiku, acceptEdits,
    `--allowedTools "$(cat allowed-tools.lane)"`, run in a scratch dir with
    no project hooks) running `docs/testing/ab_run.sh --help`. Master's list
    gave `REFUSED: This command requires approval`, with one entry in
    `permission_denials`. This list gave `RAN`, with none.
  - `request.sh` has no `--help`, and its bare invocation is not harmless, so
    ab_run.sh was the harmless one.
- **9. Sweep stamp.**
  - `deliver.sh scan` writes `delivery-cache/.sweep-scanned` on every
    successful read, including an empty window, and never on exit 3.
  - check_coverage takes the newer of that stamp and the lane's own
    `scanned`.
  - `66-deliveries.sh` now ages the sweep stamp in its "nobody refreshed"
    fixture, and adds three checks: a quiet lane under a fresh sweep, an
    empty scan stamps, and a failed scan does not.
- **10. Tracker source.**
  - check_territory loads `nv2a_issues.toml` through `board_files` and
    prints its source.
  - On the live board, the stale "#13 walled by wparamclip223" note and both
    #91 notes are gone. Master's version printed them from the 09-18
    working-tree copy.

## Defect 11: a refuted-then-reverted FAIL kept its PR `regressed` forever

PR #260, decision #257 option 3.

- **The shape.** A lane whose arm refutes its candidate reverts the code.
  The branch is then docs-only, which builds master's binary, so no arm can
  supersede the FAIL. PR #252 (#224 family B) sat there. The exits were an
  override that was not an acceptance, or re-landing the docs with no
  prediction (#259).
- **The rule.** In `label_decide`, a FAIL is withdrawn when
  `git diff --name-only a_ref b_ref`, minus `docs/`, shares no file with
  `git diff --name-only origin/<tip>...<head>`.
  - A withdrawn FAIL leaves the decision entirely. It neither counts nor
    supersedes, so an older verdict on the same issue is live again.
  - `state` prints `withdrawn <prediction>` straight after `STATE=`, and a
    markdown line naming the files that are gone.
  - Things that cannot be answered keep the FAIL: an unresolvable ref, a head
    the object store lacks, or an arm whose b_ref changed no code. (An empty
    set would otherwise be withdrawn vacuously.)
  - A PASS is never withdrawn. A partial revert is not a withdrawal.
  - `state` stays offline. It reads the refs the last tick fetched:
    `origin/<branch>`, then `refs/heads/<branch>`, then `refs/remotes/pr/<n>`
    from the last PR map.
- **The label.** Beyond the brief, the judge loop moves labels only when it
  judges an arm, and a reverted branch is never judged again. Without more,
  `regressed` would stay on the PR and fold.sh reads the label. So each tick,
  for every open PR (from the PR map) with a withdrawn FAIL and nothing else
  outstanding, it takes `regressed` off once per set of withdrawn verdicts.
  It posts a `[job.arms] WITHDRAWN:` comment and keeps a marker in
  `$WORK/arms/withdrawn/`. It does not add `verified`. The verdict comment
  and the `judged/` marker are untouched.
- **Proof.** Fragment `94-arms-withdrawn.sh`, with its own git repo, work dir
  and dispatch dir:
  - (a) full revert reads `STATE=none` plus `withdrawn`.
  - (b) partial reads `regressed`.
  - (c) intact reads `regressed`.
  - (d) a PASS on a docs-only branch reads `verified`.
  - (e) on one branch with three arms, only the middle FAIL is withdrawn.
  - The tick removes the label once, on the right PR only.
  - Three mutants, run from copies inside the fragment, each red on its named
    case: no `docs/` restriction (a), any-overlap-withdraws (b), and a PASS
    withdrawn too (d).
- **Falsification.** The fragment was copied into a scratch worktree at
  `origin/master` (`d709a8d1fa`), and master's own arms.sh was never swapped.
  (a) is red there for the reason this defect exists: "a fully reverted
  refuted branch is not regressed" FAILs, because the old code says
  `regressed`. (e) and the tick's label removal are red too. (b), (c) and (d)
  are green, since the old code already gets those right. The three mutant
  anchors are absent from the old file, as expected. That run had 1372
  passes and 10 failures, all 10 in this fragment.
- **Real check.** `arms.sh state lane/shadetie224` on the host, re-run
  2026-09-25 after merging master: `STATE=none`,
  `withdrawn shadetie224-ltnormal.json`, naming
  `hw/xbox/nv2a/pgraph/glsl/vsh-ff.c` as the code that is gone.

## Defect 12: arms backpressure counted the idle tier

- **The shape.** The workers serve `queue/` in glob order, so `z-*` (the
  full-corpus sweep, one request per suite) sorts behind every arm. arms.sh
  counted every `.req`, though. A queued sweep of about 100 requests held
  `waiting` above `ARMS_QUEUE_MAX=4`, and no lane's arm was queued. The host's
  stopgap, `ARMS_QUEUE_MAX=1000`, removes backpressure entirely.
- **The fix.** `waiting` counts only the requests that are not `z-*`. The
  refusal line prints both counts: `queue has N waiting ahead of the idle
  tier, M idle-tier z-* behind it`.
- **The other readers.**
  - `status.sh` (summary and queue line) and `board-status.sh` now print the
    idle tier apart.
  - `idle-watchdog.sh` and `backlog-gate.sh` already split `z-*` out.
  - `fleet.py`'s `queue_stall` is correct as it stands. Its busy evidence
    needs a claimer running something that sorts after the waiting request,
    and nothing sorts after `z-*` except another `z-*`. An idle worker would
    claim a `z-*` itself. So a `z-*` waiting behind real work is never
    counted as a stall. It was left unchanged.
- **Defect 12b.** `queue_full_sweep.sh` now resolves `"$REF^{commit}"`, so an
  annotated tag peels to its commit instead of the tag object.
- **Proof.** Fragment `94-arms-idle-tier.sh`, with its own work dir and
  dispatch dir:
  - 100 `z-*` requests plus 1 normal request: the pair is queued.
  - 100 `z-*` requests plus 4 normal requests: refused, and the line names
    both counts. This keeps a no-backpressure fix red.
  - The mutant that counts every request refuses the pair (red).
  - Against master's arms.sh in the scratch worktree, the queueing legs are
    red.
- **After the fold,** the host deletes
  `~/.config/systemd/user/hakux-arms.service.d/zsweep-backpressure.conf`.

## Defect 13: a worker's re-snapshot rewrote the other worker's running script

- **The shape.** `snapshot_scripts` used `cp -f` into the shared `$SNAP`, which
  rewrites the file in place. bash reads a running script by byte offset. On
  2026-09-25 the Thor read the new `run_disc.sh` at the old offset, and the
  run was voided.
- **The fix.** Each file is written to `$SNAP/.<f>.tmp.$$` and then `mv`'d
  into place. The rename swaps the inode, so a running bash keeps the old
  inode. An unchanged file (`cmp -s`) is not touched at all.
  - Per-worker snapshot directories were considered and not done. The
    rename alone closes the race, and a per-worker `$SNAP` would change the
    path every re-exec and every other reader of `$D/bin` depends on.
- **Proof.** Fragment `97-dispatch-snapshot-rename.sh` is exact, not a race.
  v1 starts with `sleep 2` (8 bytes), and v2 is built so that its byte 8
  starts `echo GARBLED`.
  - With the fix, the running v1 prints `v1-done`, the snapshot holds v2,
    and no temp file is left behind.
  - The mutant (`cp -f` in place) prints `GARBLED v2-done` (red).
  - Master's dispatcher.sh in the scratch worktree fails the `v1-done` leg
    (red).
- **Selftest,** on the branch after merging master (defects 11 to 13):
  `bash docs/testing/jobs/selftest.sh` gave 1393 passed, 0 failed.

## For the next lane

- Do not match the WSL interop signature on a call's stderr; it bypasses
  the redirection. Match the run log, or fix the transport.
- A verdict line may never contain PASS or FAIL unless it means that.
  arms.sh reads it by substring.
- `score_sweep`'s `SCORED_STATUSES` has two copies, in ab_compare.py and in
  dispatcher.sh's result writer. Selftest part B fails if they drift. Change
  all three together.
- The selftest runner has no numpy, so score_sweep cannot be driven there.
