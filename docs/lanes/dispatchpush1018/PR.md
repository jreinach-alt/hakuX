# dispatcher: fix the staged-disc push's /mnt/d path so adb.exe can open it

State: ready

Lane: dispatchpush1018            Issue: #433
Base: master @ 1b3b3db8f4
Files: docs/lanes/dispatchpush1018/**, docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/99-dev-push-wslpath.sh, docs/testing/jobs/selftest.d/99-hdd-split.sh, docs/testing/jobs/selftest.d/85-savestate.sh, docs/testing/jobs/selftest.d/98-dispatch-doctor.sh
Prediction: none: harness defect, no device-facing behavior change to predict
Needs device: no (already proved against the Nova in NOTES.md section 1; nothing further needed)    Needs NDK: no

`dev_push` (docs/testing/dispatcher.sh) handed Windows `adb.exe` a host path unchanged. Any
source under `/mnt/d` -- every staged-disc push since the fast staging path landed -- failed
with "cannot stat", because `adb.exe` cannot open a `/mnt/...` path; it needs either a Windows
drive path or a `\\wsl.localhost\...` UNC path. `dev_push` now resolves its source through
`wslpath -w` before pushing, which produces a form `adb.exe` can open for both a `/mnt/d` source
and a `/home` source (the latter already worked by resolving against the WSL UNC share, and
still does after this change).

Confirmed against the real Nova (docs/lanes/dispatchpush1018/NOTES.md section 1): a small
scratch file pushed with the unconverted path reproduces the exact dispatcher.log failure; the
same file through `wslpath -w` pushes and its on-device sha256 matches. Both the `/mnt/d` form
and a `/home`-style source were checked. The device copy was removed immediately after; nothing
near the 25 GB free floor was touched; no app data or install state was touched.

`docs/testing/jobs/selftest.d/99-dev-push-wslpath.sh` fails on the pre-fix line: its fake `adb`
stubs only the device transport (there is no real device in CI), not `wslpath`, which runs for
real and must resolve a `/mnt/d/...` source and a `/home/...` source each to a form the fake
`push` accepts; an unconverted `/mnt/...` or bare `/home/...` argument fails the fragment. This
is a different gap than the existing `99-iso-roots.sh`, which never calls `push` at all (NOTES.md
section 0.2).

A second fault turned up in three pre-existing fixtures, not the real device: `99-hdd-split.sh`,
`85-savestate.sh` and `98-dispatch-doctor.sh` each fake `push` by `cp`-ing the source argument
directly, which `dev_push`'s fix broke since that argument is now a Windows-form path. Each is
fixed with the same one-line `wslpath -u` round-trip, confirmed by the stash A/B technique
(clean at baseline, broken only with the fix, clean again after) before and after
(docs/lanes/dispatchpush1018/NOTES.md section 3.1). All four push-stubbing fragments pass
together: 178 passed, 0 failed.

**Deploy**: the host dispatcher runs a separate copy of this file, snapshotted into
`/home/justin/hakux-work/dispatch/bin/dispatcher.sh` whenever the dispatcher service restarts
from the fast-forwarded tree at `/home/justin/hakuX`. After this PR folds to master, that happens
through `host-tools/dispatcher_update_window.sh` (brings `/home/justin/hakuX` to
`origin/master` and restarts `hakux-dispatcher.service`), not by hand-editing
`dispatch/bin/dispatcher.sh`. This lane did not run that script and queued no Nova request
beyond the one scratch-file push above.

Release note (other): none -- a harness/dispatcher fix, not an emulator behavior change.

Selftest: 99-dev-push-wslpath

🤖 Generated with [Claude Code](https://claude.com/claude-code)
