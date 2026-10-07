State: ready

Lane: harnessfix1006            Issue: #433
Base: master @ 6cef37f426 (merged into the branch; origin/master moved further since, see NOTES.md)
Files: docs/testing/jobs/device_build.py, docs/testing/jobs/hold.sh, docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/99-build-gate.sh, docs/lanes/harnessfix1006/NOTES.md, docs/lanes/harnessfix1006/OUTBOX.md, docs/lanes/harnessfix1006/PR.md, docs/lanes/harnessfix1006/selftest-pass.txt, docs/lanes/harnessfix1006/selftest-mutant-nogate.txt, docs/lanes/harnessfix1006/selftest-merged.txt
Prediction: none: no arm (a harness change, no pixels, no device run in this PR)
Needs device: no (the one 60 s Nova smoke this PR needed has run; see below)    Needs NDK: no
Release note (none): a test-harness/dispatcher change; no player-visible effect.

The Nova's runs are on a known build, and a test build no longer stays on it.

- `docs/testing/jobs/device_build.py` reads the device's newest result.json and says whether it is master (ref master/origin/master, `MASTER_SHA`, or -- new in attempt 3 -- a resolved sha that `git merge-base --is-ancestor` finds reachable from `origin/master`) with env `[]`. A result with no `env` key is not master. `check` gates; `restore` queues one 60 s master request after a run off master.
- `docs/testing/jobs/hold.sh`: `take` and `wait` refuse a non-release Nova (exit 4) and name the build. The Thor is not gated.
- `docs/testing/dispatcher.sh`: `queue_master_restore` runs after both result writers, before DONE, now passing `DISPATCH_REPO` so the ancestry check works from the snapshot a worker re-execs into. It never fails the run.
- `docs/testing/dispatcher.sh` also ends a `dispatch.restore` request in `serve_one`, after its build, install and env reset. Before this, the restore had no title and no suites, so the disc path refused it (`NO SUITES`) and the device kept the test build. Its result is `kind: "restore"`, and `device_build.py check` reads it.
- `docs/testing/jobs/selftest.d/99-build-gate.sh`: 34 legs (30 from attempt 2, plus new leg (k) and its mutant), all green when sourced directly with the real selftest context; `selftest.sh`'s own end-to-end run is blocked in this session by an unrelated sandbox restriction on its shared setup's `git fetch`, not by this change -- see NOTES.md.

**Found and fixed in attempt 3:** the gate's own release check never actually matched a real run. `request.sh` resolves every `--ref` to a concrete sha before a request reaches the dispatcher (deliberate, queue-time resolution), so no real request ever carries the literal string `"master"` that `build_of()` matched -- only the gate's own internal restore did. Reading the Nova's live result with `device_build.py check nova` (the exact command named as the readiness confirmation) returned "non-release" on a Nova that was actually clean, which is how this was caught. Unfixed, `dispatcher.sh`'s `queue_master_restore` would also have queued a 60 s restore after every ordinary run, not only a test build. Fixed by the ancestry check above; both live results from this lane's own device activity (the smoke and hostops's restore) now read correctly. Full account in NOTES.md.

The soak and disc result writers already record ref, apk_sha, env and device_label, so the dispatcher side of item (e) needed no new field beyond the fix above. What is not done, and needs the owner of those files: `titles/pathfind.py` records no ref, apk_sha or env (it never calls request.sh); `titles/drive.py:1051` writes `mark gameplay` on the classifier's own call, so a window that is not live play gets the label. Both are named in OUTBOX.md. The lanewaker keepalive check is not verified from this worktree (also OUTBOX.md).

The 60 s Nova smoke queued at `55e66e43ae` ran (`1-1791349581-lane.harnessfix1006-4034827`, DONE 22:13 PDT); the master restore that followed (queued by hostops by hand, not yet this lane's own dispatcher, since the branch is unfolded) also ran (`1-1791350958-hostops-restore-nova-50958`, DONE 22:40 PDT). Both read as expected once the fix above is applied. `queue_master_restore`'s own dispatch is not proven on a device under this branch's dispatcher; the fold will exercise it for real.

The Files grant is in (OUTBOX.md section 1, granted on origin/board 10-06 ~13:49 PDT).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
