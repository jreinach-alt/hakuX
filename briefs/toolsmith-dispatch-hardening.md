# Dispatcher hardening: two serve-path defects found on PR #206

Lane: toolsmith (standing). No tracker issue: this is a harness defect, so it gets a brief only.
Found by: lane.xbox while remediating PR #206. See "Found on the way, NOT fixed here, and routed" in
`docs/lanes/dispatch-script-deps/NOTES.md`.
Base: origin/master **after PR #206 folds**. #206 rewrites dispatcher.sh's
snapshot/`SCRIPT_DEPS` and fleet.py's `queue_stall`. Starting from a pre-#206
master is a guaranteed conflict.
Files: docs/testing/dispatcher.sh, docs/testing/sweep_queue.sh, one new
`docs/testing/jobs/selftest.d/NN-<concern>.sh` (two digits, unused; the runner
globs `[0-9][0-9]-*.sh`), docs/lanes/dispatch-hardening/NOTES.md.
Needs device: no. Needs NDK: no. Prediction: none, because this is harness work with no arm.

## Defect 1: the legacy sweep preemption cannot work

- `sweep_queue.sh` demands `BASE_ISO`, `GOLDENS`, `RESULTS` and
  `BASELINE_APK` with `${VAR:?}` at top level, before its `pause` case.
  `preempt_sweep` in dispatcher.sh passes only `SWEEP_STATE`, so `pause` exits
  before it pauses anything.
- It passes no `SERIAL`, so `pause` would force-stop the app on the FIRST adb
  device, not the sweep's.
- Either worker calls it, but only `SWEEP_DEVICE`'s worker resumes.
- It is dormant. The runner's pid (`$SWEEP_STATE/pid`, default
  `/home/justin/hakux-work/night19/sq_g0`, a 09-12 state dir) has been dead
  since 09-12, and "preempting the sweep" has never appeared in
  `dispatch/logs/dispatcher.log`.

Fix it or delete it, and say which in the PR and why. Prefer deleting the
preempt/resume path if nothing has used it since 09-12. A code path that has
never run is not a feature, and it holds a force-stop aimed at whichever
device happens to be first.

## Defect 2: unbounded adb calls in the serve path

- `adb install -r`, the run-as pref reads and writes, and `am force-stop` in
  dispatcher.sh have no timeout. On 09-14 the Thor sat in
  `1789389229-lane.blit38-4028618` from 06:29 until 09-18 09:23. It stopped
  between run 2 and run 3 and was later ABORTED, so the queue waited four days
  behind one hung call. run_disc.sh's per-call deadline (since 09-10) does not
  cover these calls.
- Bound each call (`timeout <s> adb ...`) with a deadline sized to the
  operation: an apk install is not a pref read. On expiry, log the call that
  hung, mark the result `ERROR` naming it, and return the worker to its claim
  loop through the existing post-claim exits.
- The host has a backstop in the meantime, not a fix:
  `/home/justin/hakux-work/host-tools/dispatch_jamcheck.sh` (host-only). It
  detects a run with no lease, result or build activity for 30 min and
  restarts the service when nothing else is in flight.

## Defect 3 (added 2026-09-25 02:15 PDT): WSL interop adb failures void runs

The host's `adb` is the Windows `adb.exe` reached through WSL interop
(`/usr/local/bin/adb -> /mnt/c/platform-tools/adb.exe`). Interop sometimes
fails with `<3>WSL (...) ERROR: UtilAcceptVsock:271: accept4 failed 110`.

- Five run logs carry it: `1790325543-arms-vshconst-{base,fix}`,
  `1790321693-arms-wbuf31fix-base`, `1790317302-xbox-wbuf31-dryrun`, and a
  09-13 one. Most of those runs survived it.
- `1790325543-arms-vshconst-base-650341` did not. It logged four such errors,
  "ran 39s", "pull failed or timed out", and an empty logcat, so its pair came
  back as ARM ERROR and one device run was lost.

What to do:

- Recognise the signature, and retry the adb call with backoff before treating
  it as device loss.
- If a run still produces 0 captures and the signature appears in its log,
  record `ERROR: adb interop failure` rather than a silent zero, and requeue
  it once.

**Recurrence, 2026-09-25 02:15-02:30:** `1790327181-arms-vshconst-fix-821066`
"ran 130s", then "pull failed or timed out" after three of the same errors.
Its logcat shows a normal run, and the captures were lost in the pull. That is
the second arm lost in about 40 minutes.

**The fix to evaluate first:** stop spawning `adb.exe` through interop for
every call. A native Linux `adb` client with
`ADB_SERVER_SOCKET=tcp:<windows-host>:5037` talks to the Windows adb server
over TCP, so no per-call interop is involved. The owner's USB setup stays on
Windows. Prove it on one run before switching the dispatcher.

**Related arms.sh gap:** a HALF-run pair cannot be re-queued. `already_ran()`
counts a sha as run if either half's result is DONE (the `RAN` set). The ARM
ERROR comment's advice ("delete judged/<sha> and pairs/<sha>.json to have the
job queue it again") therefore does nothing when one half survived, as with
vshconst above. Either count a sha as run only when both halves ran, or make
the comment tell the lane to re-run with `ab_run.sh`.

## Defect 4 (minor): score_sweep.py crashes on an empty run

`score_sweep.py:399` does `max(len(k) for k in suites)`, which raises
`ValueError: max() iterable argument is empty` when a run has no captures (the
same lost run). Guard it. An empty run already prints its own explanation just
above.

## Falsify before claiming

- Defect 2: a selftest fragment with a fake `adb` that never returns. On the
  OLD code the serve path must block, so run it against the old file in a
  scratch worktree and confirm it goes red for that reason, not an ImportError
  or a missing variable. On the new code it must return within the deadline
  and record ERROR. Assert on the output words, not only the exit code.
- Defect 1: if you fix it, a fragment drives `preempt_sweep` with a fake sweep
  state and a fake adb, and shows `pause` reaching the named SERIAL only. If
  you delete it, show that no caller is left and that selftest stays green.

## Done when

The PR has the lane body (its `Files:` line equal to
`git diff --stat origin/master...HEAD`), `jobs/selftest.sh` is green,
`preflight.sh` passes, NOTES are written, and the PR is marked ready.
