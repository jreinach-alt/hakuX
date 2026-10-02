# snapdrive: the dispatcher's script snapshot carries the screen-aware driver (#433)

State: draft

Lane: snapdrive            Issue: #433
Base: master @ b71f92a12a
Files: docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/97-dispatch-deploy.sh, docs/testing/jobs/selftest.d/97-dispatch-snapshot-rename.sh, docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh, docs/testing/request.sh, docs/lanes/snapdrive/NOTES.md, docs/lanes/snapdrive/OUTBOX.md, docs/lanes/snapdrive/PR.md
Prediction: none: no arm. Harness deploy only (which scripts the dispatcher snapshots), not emulator pixels or speed.
Needs device: no    Needs NDK: no

Work in progress.

Release note (none): test harness only -- no emulator code changes.
