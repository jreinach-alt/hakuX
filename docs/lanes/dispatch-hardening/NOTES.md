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

## Defect 23: a lane whose device run finished was not woken

- **The shape.** A lane ends its session while its soak waits on a device,
  which is correct. `handback.sh` resumed a waiting draft only on a judged arm
  (`draft-strand-arm`) or on the two-hour quiet clock. So a lane whose soak
  finished at minute ten sat on its own result for up to two hours. At
  23:45Z on 2026-09-25 the Nova had 23 lane requests waiting, including
  perfarch's nine soaks.
- **The fix.** It adds a third strand cause, `draft-strand-runs`.
  - `lane_requests_of` makes one read of `queue/`, `running/` and `results/`.
    It replaces `inflight_of`, so the in-flight gate and the finished set
    cannot attribute a request differently.
  - A request belongs to a lane by these rules, first match wins: its `lane`
    field; an expect_sha registered in `arms/pairs` (that pair's branch); a
    purpose saying ` from lane/<b>:`; then its requester, or the owner field
    of its id when there is no requester. A leading `lane.` or `arms-` is
    stripped, and the owner is the lane it equals or the LONGEST known lane
    it starts with plus `-`. Known lanes are the `$WORK/wt` dirs and the
    branches in the pairs.
  - A finished run is new when its DONE/ERROR marker is newer than the mtime
    of the lane's newest `$WORK/logs/lane/<name>.<stamp>.json`. That is the
    end of its last session, because `claude -p` writes that file on exit.
    With no session log, nothing counts as new.
  - An arm's own result (expect_sha registered) is left out. The verdict is
    the arm cause's news, and resuming on the raw run would come ahead of it.
  - The cause fires only when none of the lane's requests is queued or
    running. It is keyed on the hash of the finished set, so a push is not a
    new cause and a second soak finishing is. It skips the quiet clock, so it
    fires on the first tick after the run finishes.
  - A judged verdict that is still news goes first. The runs cause takes a
    quiet row, or an arm row whose verdict was already actioned.
  - The brief addendum is a table of request, state and result dir.
  - It neither counts toward `DRAFT_STRAND_MAX` nor spends an attempt. It can
    recur only after a new session ended and new device work finished, and
    that is progress, not a loop. If it were counted, a lane that ran four
    soaks would be labelled `blocked:needs-owner` for waiting on them.
  - **A side effect, on purpose.** The in-flight gate that held a draft off
    the quiet clock used to see only the lane's arms. It now sees any of the
    lane's requests. On the host at 00:05Z it held #264 (vtxarr262), #308
    (perfarch), #309 (tcgchurn) and #317 (fmv303) while their soaks are
    queued. Each will be woken when those finish, instead of being told
    "still queued".
- **Proof.** Fragment `99-handback-runs.sh` has three lanes, ours in the
  middle: `selftestrq`, `selftestrs`, and `selftestrs-x`, whose name has ours
  as a prefix.
  - (0) A run that finished before the session ended resumes nothing.
  - (a) One request is still queued: no resume. `list` names the request.
  - (b) Every request has finished: one resume inside the quiet clock, on
    `draft-strand-runs`. The brief lists the ERROR row with its result dir
    and the `lane`-field request. It does not list the old run or the
    neighbour's run. The comment names the runs. The strand count and the
    attempt counter are unchanged.
  - (c) The next tick, and a push after it: no second resume.
  - (d) An arm's result is left to the arm cause.
  - Each of four mutants is red: first prefix instead of longest; no session
    anchor; ignore requests in flight; count an arm's result as a run.
  - **Falsification:** master's `handback.sh` was put in a scratch copy of
    `docs/testing` (the real file was never swapped). It failed (b) and every
    leg under it, because it never resumes on a finished run, plus (a)'s
    named-request line, 11 FAIL in all.
- **Not done: the live instance.** The brief asks for a lane resumed within
  one tick of its run finishing. That can only be observed after this folds
  and the handback timer runs the new file. The host's first
  `draft-strand-runs` line in `$WORK/logs/handback/tick.log` is that
  instance.

- **The live instance, found 2026-09-26.** `#317` (fmv303) was resumed on
  `draft-strand-runs` at 20:28:38 PDT on 2026-09-25. Its last run,
  `1790389079-fmv303-1248256`, wrote DONE at 19:55:38 PDT, before #333
  folded (20:10:27 PDT). The 20:12 and 20:22 ticks still logged the old
  "only quiet" line. So this shows the cause firing on real data, on the
  first tick observed to run the new code. It cannot show the one-tick
  latency, because the fix was not deployed when the run finished.

## Defect 25: a lane waiting on its own background task was stranded

- **The shape, read from `logs/handback/tick.log`.** titlerun (#307),
  sweepcover (#298) and blankrule297 (#335) were all drafts. Each was
  resumed ONCE on `draft-strand-quiet`: #298 at 17:20 PDT, #307 at 17:30 and
  #335 at 20:12. Each session ended again "waiting for my background task",
  without pushing. The quiet marker is `draft-strand-quiet-<pr>-<head>`, so
  with the head unmoved, the cause at that head was spent for good. The
  quiet clock also restarts on any PR activity (`updatedAt`): #307's went
  from 4017 s to 119 s at 15:15 on someone else's comment.
- **(a) The rule, in `roles/lane.md` item 5.** Never end a session waiting on
  your own background task. Run it in the foreground in chunks, or detach it
  with `setsid nohup` and poll it. A `waiting:` comment names something
  outside the session. It also says what `handback.sh` now does.
- **(b) The idle cause, in `handback.sh`.**
  - `draft-strand-idle` takes a row only the quiet clock holds. It is keyed
    on the lane's LAST SESSION END (the stamp of its newest
    `logs/lane/<name>.<stamp>.json`), not on the head, so a session that ends
    again is a new cause.
  - It fires when nothing of the lane's is queued or running, CI on the head
    is settled (not PENDING), the session ended `IDLE_GRACE_SECS` (2400)
    ago, and the lane did not say it was waiting. The grace is longer than
    one arms tick (30 min), so a prediction just pushed and not yet queued
    is not "nothing".
  - "Said it was waiting" means either of two things: the session's `result`
    text contains `[lane.<name>] waiting:` or `blocked:`, or the lane's
    newest `[lane.<name>]` comment on the PR is one, newer than this job's
    last `Resumed` comment.
  - It spends neither an attempt nor `DRAFT_STRAND_MAX`, because a busy lane
    ends many sessions on one PR. Its own bound is `IDLE_MAX=3` idle resumes
    at one head (`$H/idle/<name>-<head>`). After that the quiet clock and the
    strand cap take over.
  - `idle-no-pr` covers the other half of the status page's "idle, no
    work". The pickup is board lanes (read through `board_files`, or
    `HAKUX_TERRITORY`) that have a worktree and a brief and no open or merged
    PR on `lane/<name>`. It skips standing and remote lanes, `xbox`, and any
    lane whose issue has `decision-needed`, which is how `status.sh` decides.
    It has no PR to comment on, so the tick log is its record. A running unit
    is skipped silently.
  - The brief addendum (`idle_text`) carries the host's
    `host-tools/bg-addendum.md` guidance, so the repo does not depend on a
    host file.
- **Proof.** The fragment is `99-handback-idle.sh`, with 26 checks.
  - Draft legs: (0) inside the grace, no resume. (a) Resumed on the idle
    cause, with the brief text and the comment, and the strand count and
    attempts unchanged. (b) Same session, no resume. (c) A new session end
    at the SAME head is a new cause (blankrule297's shape). (d) The session
    said waiting, honoured. (e) The PR's newest word is waiting, honoured.
    (f) A request is queued, no resume. (g) CI is PENDING, no resume. (h)
    CI is RED, resumed. (i) A fourth idle session at one head, stopped by
    IDLE_MAX. (j) A new head resets that bound.
  - No-PR legs, with four board lanes: merged, no PR (ours), standing, and
    the draft lane. Only ours is resumed, with no comment. The same session
    is not resumed twice. A `decision-needed` issue holds it, and so does a
    running unit.
  - Five mutants, each red: key on the head (fails c); no grace (fails 0);
    ignore the session's waiting (fails d); no IDLE_MAX (fails i); treat a
    merged PR as absent (the merged lane is resumed).
  - **Falsification:** `origin/master`'s `handback.sh` was run in a scratch
    copy (`.lanework/quick.py old:jobs/handback.sh=origin/master`). It failed
    (a) with its brief and comment lines, (c), (h), (j) and all three no-PR
    resume lines, plus the five mutant anchors: 15 FAIL, for the reason this
    exists.
  - `99-handback-runs.sh` holds the idle cause off
    (`IDLE_GRACE_SECS=999999`). Its leg (0) lane ended a session an hour ago
    with nothing in flight, which is now correctly idle, and that leg asks
    only whether an old run is news.
- **Live read, 22:18 PDT 2026-09-25, `handback.sh list` on the host.**
  #335 (blankrule297) and #354 (statuspage) classify as
  `draft-strand-idle`. Both units were running again at that moment, so
  neither would have been acted on. The no-PR pickup read
  `origin/board` and emitted no row. That is correct: every non-standing
  board lane has an open or merged PR (checked lane by lane).

## Defect 22: blocked on a lent file

The queue priority field, `request.sh --priority`, and the hold `yield` file
all live in `dispatcher.sh` / `request.sh`. Both are lent to lane.titlerun
until #307 folds, and #307 was still open at 00:05Z on 2026-09-26. It was not
started here.

## Defect 15: the pull was holed, not truncated

**The brief's premise was wrong, and so was part A's comment.** Both said
the pull truncated the PNGs. Measured on the two affected results
(`1790327180-arms-shadeflat224-fix`, `1790357477-arms-wparamclip223-base`):

| | shadeflat224-fix | wparamclip223-base | every other run of both pairs |
|---|---|---|---|
| bad PNGs | 56, all W_param | 51, all W_param | 0 |
| size of each bad PNG | 16384 (one FATX cluster), header intact, no IEND | same | n/a |
| `UtilAcceptVsock` lines in run1.log | 3 | 3 | 0 |
| guest wall time (logcat) | 02:17:10 to 02:19:48, "QEMU cleanup complete" | 10:31:31 to 10:34:43, same | normal |
| progress log | "Testing completed normally" | same | same |
| `ran Ns` | 49 | 66 | 141 to 182 |

- **`ran Ns` counts poll iterations, not seconds.** Retried `adb ps` calls
  stretch each iteration. The guests ran their full time and exited cleanly,
  so the run was not cut short.
- **The image is qcow2** (`QFI\xfb`). A truncated qcow2 cannot produce these
  files: `extract_results.Qcow2._read_at` raises "short read" on any cluster
  past the end.
- **What fits is a hole.** A 4 KB write missing from the host's copy zeroes
  part of the FAT. A zero entry ends the chain, so each file behind it stops
  after its first cluster, while the size is right and the pull exits 0. A
  size check or an IEND check on the image cannot see that. A checksum can.
- **Across all 201 results since epoch 1790000000:** unreadable rows occur in
  2 runs, both with the interop signature. 18 other runs had the signature
  and no damage.

**Fix.**
- `run_disc.sh` takes the device's `md5sum` of `hdd.img` once, after the
  guest has exited. It pulls, compares, and pulls again on a mismatch, up to
  `PULL_TRIES` (default 3). If no pull matches, it exits 1 without extracting.
- `extract_results.py` names files whose chain ended before the size their
  directory entry records. It says so on its summary line: `; N SHORT: ...
  (first: <name>)`.
- A device that gives no md5 leaves SHORT as the only check, so SHORT files
  force a re-pull there. SHORT files from a pull that matches the md5 are
  blamed on the device's own image and are not re-pulled.
- Every run now logs `pull: md5 matches the device's image` or
  `pull: NOT VERIFIED`.

**Unverified on hardware:** that toybox `md5sum` answers on both handhelds. If
it does not, the run log says NOT VERIFIED on every run, and SHORT still
triggers the re-pull.

**Proof: `58-pull-verify.sh`, 14 checks.**
- The fixture is a real qcow2 holding a real FATX volume. The holed image is
  the same bytes with the FAT page holding entries 0..1023 zeroed.
- The real extractor gives 16384 bytes and `1 SHORT ... (first: t.png)` on
  the holed image, and 40000 bytes with no SHORT on the good one.
- Five run_disc cases, each asserted on rc, pull count, PNG size and output
  words:

  | case | device image | pulls return | md5 | expected |
  |---|---|---|---|---|
  | (a) | good | hole, good, hole | yes | 2 pulls; the good one, in the middle, is extracted |
  | (b) | good | hole x3 | yes | exit 1; nothing extracted |
  | (c) | good | hole, good | no | SHORT forces a second pull |
  | (d) | hole | hole | yes | 1 pull; SHORT, blamed on the device |
  | (e) | good | good | yes | 1 pull; clean |

- **Three mutants, each red on its case:** the md5 never compared (b); SHORT
  never re-pulls (c); the extractor does not measure the chain (d).
- **Falsification:** `origin/master`'s `run_disc.sh` and `extract_results.py`
  in a scratch copy. Case (a) gives `rc=0 pulls=1 png=16384`: the old code
  scores the one-cluster PNG, the same shape as both live arms.

Defect 19 (soak liveness) moved to lane.titlerun, so no shared adb wrapper
was added here.

## Defect 26: concurrent preflights read each other's reports

The fold refused PR #367 twice with `psh_differ report FAILED / produced no
report`, on a sha that passes alone. preflight.sh wrote every log to a fixed
`/tmp/preflight-*` path (8 files, 22 references). A second run's
`>/tmp/preflight-differ.log` truncates the report the first has written and
not yet read.

**Fix.** One `mktemp -d` per run (`$TMPDIR/preflight.XXXXXX`) holds every
log. A pass removes it; a failure keeps it and prints `this run's logs:
<dir>`, so the path in `full output:` still exists when someone reads it.

**Proof, `selftest.d/97-preflight-tmp.sh`:** two stub trees around the real
preflight.sh, every gate stubbed to pass. The order is forced with sync files,
not sleeps: A's psh-differ writes `TOTAL A`, and only then does B start; B's
redirect opens its report before A reads its own.

| run | this branch | mutant (one fixed dir) | master @ 2dc2b5c49a |
|---|---|---|---|
| A | ok, `TOTAL A`, passed | `produced no report`, FAILED | `produced no report`, FAILED |
| B | ok, `TOTAL B`, passed | ok | ok |

The master row is master's own preflight.sh with `/tmp/preflight-` renamed
to a private directory, so the falsification cannot clobber a real fold on
this host. It is otherwise byte-identical. It shows #367's refusal word for
word.

**The rest of the brief's list is not this class.** In `run_disc.sh`,
`sweep_queue.sh`, `soak_title.sh` and `run_one_disc.sh`, the only `/tmp`
path is the device lease, `/tmp/hakux-device-lease`, which is shared on
purpose: it is how the Stop hook sees a device in use. In `run_perf.sh`,
`swap_driver.sh` and `profile_guest.sh`, the hits are `/data/local/tmp/...`
on the device, one per `adb -s` serial, used under that device's lease.
`pgraph_capture_run.sh`'s `/tmp/pgraph-run` is an `OUTDIR` default for a
hand-run tool. None of these is two host processes sharing one path by
accident, so nothing else was changed.

## For the next lane

- Do not match the WSL interop signature on a call's stderr; it bypasses
  the redirection. Match the run log, or fix the transport.
- A verdict line may never contain PASS or FAIL unless it means that.
  arms.sh reads it by substring.
- `score_sweep`'s `SCORED_STATUSES` has two copies, in ab_compare.py and in
  dispatcher.sh's result writer. Selftest part B fails if they drift. Change
  all three together.
- The selftest runner has no numpy, so score_sweep cannot be driven there.
