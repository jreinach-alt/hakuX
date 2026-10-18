# holdcap1018: an owner-play hold starts a host logcat capture

State: ready

Lane: holdcap1018            Issue: #433
Base: master @ 7e00c7cf73 (merged in, see NOTES.md)
Files: docs/testing/jobs/hold.sh, docs/testing/jobs/selftest.d/99-ownerplay-capture.sh, docs/lanes/holdcap1018/**
Prediction: none: no arm
Needs device: no    Needs NDK: no
Selftest: 99-ownerplay-capture.sh
Release note (other): none -- harness/testing-only change, no emulator code touched.

`hold.sh take` for a tag starting `owner-play` now starts a host `adb logcat`
capture (a transient user systemd unit, `hakux-ownerplay-capture-<label>`,
using the dispatcher's own `LOGCAT_SPEC`) so an owner playthrough is never
lost to the device's ~2-3 minute logcat ring again (10-17 Halo survived by
luck; 10-18 Fable's first 30 s did not). `who`/`wait-idle`/`release` gain the
matching capture-aware behaviour:

- `take` for an owner-play tag reuses an already-running capture for that
  label (reporting its path and age) or starts one; if the capture cannot be
  started it prints `NO CAPTURE: <reason>`, exits 6, and rolls the hold back
  -- no orphaned hold.
- `who` prints the capture line, or `NO CAPTURE RUNNING` if the process died.
- `wait-idle` ANDs the capture check onto the existing idle gate: idle with a
  dead capture now exits 5 instead of 0.
- `release` stops the capture (and prints its file + byte size) only once the
  release itself succeeded; a refused release (wrong tag) leaves the capture
  running untouched.
- A non-owner-play tag takes the unchanged path throughout; `99-hold-take.sh`
  needed no edit (none of its tags start `owner-play`), so its existing legs
  are the regression check for that, for free.

Detection of "already running" is by a pidfile this lane writes plus
`/proc/<pid>/cmdline`, never `systemctl is-active` -- the harness's own
global shim answers "active" unconditionally regardless of unit name, and a
real systemd can answer confidently wrong after a crash too.

`docs/testing/jobs/selftest.d/99-ownerplay-capture.sh` (new) covers every
point in the brief with its own local `adb`/`systemd-run` shims (the global
ones are inert for exercising a real capture process), including a mutant
that must turn red.

Full `docs/testing/jobs/selftest.sh` run twice (sharded 0/4..3/4, each
detached and polled to completion): 3718 passed, 1 failed, both times,
150/150 fragments. The one failure both times is pre-existing and unrelated:
`66-status-titles.sh`'s "check --pages" leg (a README.md/home_page.py
formatting check with no connection to `hold.sh` or captures) -- the exact
fragment and failure the brief's own precedent (lane.snaptargets1018) names.
Branch was merged up to `origin/master` (55 commits, none touching
`hold.sh`/`selftest.sh`/`selftest.d/`/the CI workflow) before either run.
Details and the per-shard table are in NOTES.md.
