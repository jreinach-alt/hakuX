## #433 -- 2026-10-02 18:55 PDT

**Territory request (lane.local: please add a row).** `territory.toml` has zero rows for `buildstamp`
today (checked by grep; not drift, just never granted). Requesting exactly the brief's own list, which
is what this PR's `Files:` line touches:
- `android/app/build.gradle.kts`
- `android/app/src/main/res/layout/activity_game_library.xml`
- `android/app/src/main/java/com/rfandango/haku_x/GameLibraryActivity.kt`
- `docs/testing/version_stamp.sh` (new)
- `docs/testing/owner_build.sh` (new)
- `docs/testing/dispatcher.sh` -- named explicitly per the brief ("the dispatcher's install step (name
  the file in OUTBOX first; lane.local requests rows)"). The change is additive: a new
  `guard_not_release_apk` function and one call site right before the `adb install -r` in `serve_one`,
  refusing to install an apk whose compiled manifest reports the bare release package id. Covered by
  a new selftest fragment; reran `50-arms-requeue.sh`+`51-dispatch-hardening.sh` and
  `99-battery-admit.sh` afterwards to check for a regression.
- `docs/testing/jobs/selftest.d/86-build-stamp.sh` (new)
- `docs/testing/nightly_build.sh` -- read only this session, no change (see below); listing it since
  the brief named it.
- `docs/lanes/buildstamp/**`

**The nightly's exit 4, diagnosed (not fixed).** Read `~/hakux-work/nightly/systemd.log` and the
per-day logs. Two separate things are true:
1. The installed `~/.config/systemd/user/hakux-nightly.service` is stale -- it still has the
   `lane.nightlytrunk`-era `ExecStartPre` stopgap (fast-forwards `~/hakuX`, the dispatcher's shared
   checkout, with no `dispatch/running/` check at all) that its own comment says to remove once that
   lane's fold landed. That fold landed 2026-09-21; the host unit was never reinstalled. Every
   fast-forward it has actually run since then succeeded, so this is a real but so-far-silent hazard,
   not today's symptom.
2. **The actual cause, every night since 2026-09-30:** `gh release create`/`gh release upload` both
   fail with `HTTP 403: Sorry. Your account was suspended` -- the same GitHub suspension this lane's
   own offline ADDENDUM already names. The Gradle build itself succeeds every night; only the GitHub
   publish step fails.

Per the ADDENDUM's own instruction ("do not try to repair auth or reach GitHub by any other route") I
did not touch `gh`, credentials, or `nightly_build.sh`'s publish step -- which already logs the real
`gh` error text (`>>"$LOG" 2>&1` was already in place), so there was nothing to fix there either.

**What's left, for someone with host/systemd access (not this lane -- confirmed Bash here is sandboxed
to the worktree and cannot reach `~/.config/systemd/user/` or run `systemctl`):** reinstall
`hakux-nightly.service`/`.timer` from this repo's `docs/testing/systemd/` (already correct there) once
GitHub is reinstated, to close the stale-`ExecStartPre` hazard. Ranked against the device-verification
step actually inside this lane's scope/budget in `docs/lanes/buildstamp/NOTES.md` section 5.
