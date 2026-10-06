State: waiting

Lane: harnessfix1006            Issue: #433
Base: master @ bf85412b88ec157360428a475794b0da996e956d
Files: docs/testing/jobs/device_build.py, docs/testing/jobs/hold.sh, docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/99-build-gate.sh, docs/lanes/harnessfix1006/NOTES.md, docs/lanes/harnessfix1006/OUTBOX.md, docs/lanes/harnessfix1006/PR.md, docs/lanes/harnessfix1006/selftest-pass.txt, docs/lanes/harnessfix1006/selftest-mutant-nogate.txt
Prediction: none: no arm (a harness change, no pixels, no device run in this PR)
Needs device: yes (one 60 s Nova smoke, after the grant)    Needs NDK: no

The Nova's runs are on a known build, and a test build no longer stays on it.

- `docs/testing/jobs/device_build.py` (new) reads the device's newest result.json and says whether it is master (ref master, env `[]`). A result with no `env` key is not master. `check` gates; `restore` queues one 60 s master request after a run off master.
- `docs/testing/jobs/hold.sh`: `take` and `wait` refuse a non-release Nova (exit 4) and name the build. The Thor is not gated.
- `docs/testing/dispatcher.sh`: `queue_master_restore` runs after both result writers, before DONE. It never fails the run.
- `docs/testing/jobs/selftest.d/99-build-gate.sh` (new): 27 legs, all green; with the gate removed the real legs go red (see the two .txt logs).

The soak and disc result writers already record ref, apk_sha, env and device_label, so the dispatcher side of item (e) needed no new field. What is not done, and needs the owner of those files: `titles/pathfind.py` records no ref, apk_sha or env (it never calls request.sh); `titles/drive.py:1051` writes `mark gameplay` on the classifier's own call, so a window that is not live play gets the label. Both are named in OUTBOX.md. The lanewaker keepalive check is not verified from this worktree. The 60 s Nova smoke has not been run.

The Files grant is requested in OUTBOX.md.
