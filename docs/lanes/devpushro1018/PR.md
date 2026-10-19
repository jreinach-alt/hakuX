# dispatcher: dev_push gets a read-only mode for the Nova's SD-card disc pushes

State: ready

Lane: devpushro1018               Issue: #433
Base: master @ e34f8ffa77
Files: docs/lanes/devpushro1018/**, docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/99-dev-push-ro-disc.sh
Prediction: none: harness defect, no device-facing behavior change to predict
Needs device: no    Needs NDK: no

`dev_push` (dispatcher.sh) pushes a file, checks its sha, then unconditionally runs
`dev_make_660` and requires the device copy read back mode 660 -- a rule written for
`titles.qcow2`, a disk inside the app's internal x1box directory that xemu opens
read-write (dispatcher.sh:801-812, "THE DISK MUST BE MODE 660"). `DEVICE_ISO_ROOT`
(the Nova's SD card) has its file modes synthesized by the mount: `chmod 660` is a
no-op there and the mode always reads back 770. xemu opens a disc read-only, so 770
is fine for a disc -- but `dev_push` refused it anyway, failing every staged-disc
push to the Nova with "mode 770 after chmod 660; the app could not open it
read-write" (found by lane.mkdawhite1018, docs/lanes/mkdawhite1018/NOTES.md section
7.1, tracing request `1792345978-mkdawhite1018-1601447`).

`dev_push` now takes an optional third argument `ro`, which skips `dev_make_660`
and the final mode check (the sha check still runs). `ensure_title_staged`'s one
disc-push call site (the function behind both the dispatcher's own staging and the
dispatch doctor's `fix push-iso` retry) passes `ro`. The other two callers --
`titles.qcow2` and the hdd-guard push -- are unchanged and still require 660.

New selftest fragment `99-dev-push-ro-disc.sh`: a fake `adb` whose `chmod` is a
no-op and whose `stat` always answers 770, standing in for the SD card's mount.
A disc push with `ro` succeeds under it; a titles-disk-style push without `ro`
still fails the same way it does today, before the rename. Ran alone (2 passed),
together with every other fragment that already exercises `dev_push`/
`dev_make_660` (`99-dev-push-wslpath`, `99-hdd-split`, `85-savestate`,
`98-dispatch-doctor`, `99-iso-roots`: 188 passed, 0 failed), and against the full
`selftest.d` suite: 3732 passed, 1 failed. The one failure
(`66-status-titles.sh`'s `check --pages` check, README.md's Playable line not
matching the numberless form `home_page.py` rewrites) is pre-existing and out of
this lane's scope -- this lane's diff touches only `dispatcher.sh` and two new
files, nothing on that check's path, and the failure reproduces alone with no
other fragment involved. Left it and the fragment untouched per the brief.

**Deploy**: the host dispatcher runs its own snapshotted copy at
`/home/justin/hakux-work/dispatch/bin/dispatcher.sh`, refreshed by
`host-tools/dispatcher_update_window.sh` after this folds (brings
`/home/justin/hakuX` to `origin/master` and restarts `hakux-dispatcher.service`).
This lane did not run that script and did not hand-edit the live copy -- hostops
owns the update window once the fold lands.

**What this unblocks**: lane.mkdawhite1018's request
`1792345978-mkdawhite1018-1601447` (Mortal Kombat: Deadly Alliance, route
`mkda-arcade`) is the one this fixes for. This lane did not re-queue it and did
not touch the Nova -- that is mkdawhite1018's own request to resume once this PR
folds and the dispatcher is updated. Every other disc staged to the Nova was
blocked the same way, not only this title.

Release note (other): none -- a harness/dispatcher fix, not an emulator behavior
change.

Selftest: 99-dev-push-ro-disc

🤖 Generated with [Claude Code](https://claude.com/claude-code)
