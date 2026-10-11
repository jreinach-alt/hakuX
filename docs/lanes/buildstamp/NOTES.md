# buildstamp (#433): every build says which commit it is

## 1. What was built

- **`docs/testing/version_stamp.sh`** (new). The one place the version string
  is computed: `<base>-<MMDD>-<shortsha>[-<variant>][-dirty]` of the commit
  at `HEAD` in the tree it is pointed at. MMDD and the sha are read from
  that commit (`git log -1 --format=%cd --date=format:%m%d`), not from the
  day the script happens to run, so the same commit built on two different
  days prints the same stamp. `-dirty` is the one part that is NOT about the
  commit: tracked modifications only (matches `nightly_build.sh`'s own
  dirty check), so an untracked scratch file does not trip it.
- **`android/app/build.gradle.kts`**: `versionName` now calls
  `stampedVersionName()`, which shells out to `version_stamp.sh` against
  `rootProject.projectDir.parentFile` (the repo root) with `perflog` when
  `-Pperflog=true` is set. This runs **in whatever tree Gradle is invoked
  from** -- the dispatcher's detached `BUILD_TREE`, `owner_build.sh`'s own
  worktree, or a lane's checkout -- so it names the commit actually being
  built, not whatever the host's own checkout happens to be on. Base version
  stays `0.4.1` (dropped the old static `-j1` suffix, superseded by this).
- Debug app label: `"hakuX (debug)"` -> `"hakuX (test builds)"`
  (`com.jreinach.hakux.debug`, the one the dispatcher reinstalls every run).
- **The stamp shows on screen**: `activity_game_library.xml` gets a small,
  muted `TextView` pinned to the bottom-end corner; `GameLibraryActivity`
  sets it from `packageManager.getPackageInfo(packageName, 0).versionName`
  at `onCreate`. This is the screen a player actually lands on after setup
  (`LauncherActivity` itself has no UI -- it only routes), and reading the
  *installed* package's version rather than a build-time constant means the
  label is right even if two variants' Gradle configs ever disagreed.
- **`docs/testing/owner_build.sh`** (new): `owner_build.sh <ref|master>
  [--env-default KEY=VAL]... <nova|thor>`. Builds the **release** variant
  (`com.jreinach.hakux`, "hakuX") in its own private detached worktree
  (`$DISPATCH_DIR/owner-build-tree`, lock-protected) -- never the shared
  checkout `dispatcher.sh` reads from, and never its build tree -- then
  `adb install -r`s it and prints the stamped version. Refuses **at once**
  (exit 3), not queued, when `dispatch/running/*.owner` already names the
  target device: this is not a dispatch request, so there is no slot to
  wait in.
  - `--env-default KEY=VAL` writes the same `env_vars` pref the dispatcher
    writes for a request's `env`, via `run-as`. **That mechanism needs a
    debuggable package**, and the release build is deliberately not
    debuggable -- it is the stable channel, not a diagnostic one -- so on
    these unrooted handhelds (Nova/Thor; no `adb root` anywhere in this
    harness) it reports the `run-as` failure plainly and leaves the apk
    installed, rather than silently doing nothing. Implemented as asked,
    but genuinely untested beyond "it fails loudly as expected" -- see
    section 3.
- **Dispatcher guard** (`docs/testing/dispatcher.sh`): a new
  `guard_not_release_apk` runs right after the build, before the device is
  even checked for presence. It opens the apk as a zip, reads
  `AndroidManifest.xml`'s string pool (UTF-16LE/UTF-8) and refuses only on
  an **exact** `com.jreinach.hakux` match (no following `.`/word char) --
  `.debug`/`.debug2` pass, and a file it cannot open (the empty placeholder
  the existing fakes use for `build_ref`) is not refused, so this adds
  nothing to what those tests already cover. This is defense in depth: today
  `_build_ref_locked` only ever runs `assembleDebug`, so there is no live
  path from the dispatcher to a release apk at all -- the guard is there so
  a future change to that function can't quietly reopen one.
- **`docs/testing/jobs/selftest.d/86-build-stamp.sh`** (new): the stamp
  format over a fixture git repo (clean/perflog/dirty/dirty+perflog/
  untracked-only/non-git-tree), plus the guard both as a unit (five apk
  fixtures: release/`.debug`/`.debug2`/a same-prefix lookalike id/empty) and
  end-to-end through `serve_one` itself (REAL refuses before
  `device_present`; a MUTANT with the guard's `if` block sed-deleted lets
  the same request reach the device-presence check and get requeued
  instead) -- the real/mutant pair is built on a symlinked copy of
  `docs/testing`, the same shape `51-dispatch-hardening.sh`'s `dhmut` uses,
  because `dispatcher.sh` sources `devices.sh` by its own `$HERE` and a bare
  copied file breaks that before `serve_one` is ever reached. Ran standalone
  and through the real harness (`SELFTEST_ONLY=86-build-stamp.sh`): 15
  checks, 0 failures, ~37s.

## 2. The nightly's exit 4 -- diagnosed, not "fixed"

The brief's framing ("exit 4 NOPERMISSION... it fast-forwards ~/hakuX") is
a reasonable guess from the code, but it is not what is actually happening.
I read `/home/justin/hakux-work/nightly/systemd.log` and the per-day logs
(outside this worktree, via Read; **Bash here is sandboxed to the worktree
and cannot touch them or any host service** -- confirmed by trying):

- `~/.config/systemd/user/hakux-nightly.service` IS stale: it still carries
  the `nightlytrunk`-era `ExecStartPre` stopgap (`WorkingDirectory=
  /home/justin/hakuX`, fetch+ff-only-or-stash the shared checkout, then
  `ExecStart` calls `nightly_build.sh` directly, never `run-nightly.sh`'s
  private worktree). Its own comment says **"REMOVE WHEN lane.nightlytrunk
  FOLDS"** -- that fold landed 2026-09-21 (visible in the log's own
  diffstat for that night), and the host unit was never reinstalled. That
  stopgap has no `dispatch/running/` check at all, so it is exactly the
  "fast-forward with a run in flight" hazard AGENTS.md warns about -- but it
  has not actually failed on any of the fast-forwards logged (every
  "Updating.../Fast-forward" since 09-21 succeeded), so it is a live latent
  risk, not today's symptom.
- **The actual, 100%-reproducing cause of exit 4, every night since
  2026-09-30**, is in `2026-10-0{1,2}.log`:
  ```
  error checking for existing release: HTTP 403 (.../releases/tags/nightly-2026-10-02)
  HTTP 403: Sorry. Your account was suspended (.../releases/tags/nightly-2026-10-02)
  ```
  This is the GitHub suspension this lane's own ADDENDUM already names
  ("every `gh` call and every GitHub URL returns 403... since about 21:00
  PDT" on 09-29). The build itself succeeds every night (`BUILD SUCCESSFUL`,
  apk copied to `$OUT`); only `gh release create` and the `gh release
  upload --clobber` fallback fail, both with the same 403, because the
  account is suspended -- not because of anything in this repo's code.

**I did not touch `gh`, auth, or the publish step**: the offline ADDENDUM is
explicit -- "Do not try to repair auth or reach GitHub by any other route" --
and chasing an external suspension with a code change would be exactly that.
`nightly_build.sh` already logs the real `gh` error text into its per-day
log (the `>>"$LOG" 2>&1` redirect already in place), so there is nothing to
fix there either -- the cause has been fully legible in the log the whole
time, just not in the terser `systemd.log` summary line.

**What is left, for the owner or lane.local, not this lane:**
- Reinstall the systemd units from this repo's `docs/testing/systemd/` (the
  checked-in `hakux-nightly.service` already has no `ExecStartPre` and no
  `WorkingDirectory` -- it is correct; only the host's installed copy is
  stale) once the account is reinstated, to close the latent
  fast-forward-with-a-run-in-flight hazard. This is a host action
  (`docs/testing/jobs/install-host.sh`, `systemctl --user daemon-reload`),
  outside this lane's sandbox (confirmed: every Bash call outside this
  worktree is blocked) and outside its territory.
- The nightly's GitHub release publish resumes on its own once the account
  is reinstated; nothing here needs to change for that.

## 3. Device verification

Territory note: `docs/testing/dispatcher.sh` had **zero** rows in
`territory.toml` for `buildstamp` before this lane (grep came back empty) --
not drift, just never granted. Named in OUTBOX.md per the brief's own
instruction ("name the file in OUTBOX first; lane.local requests rows").

[Fill in after the Nova hold: both apps' installed version, screenshots,
Settings -> App info confirmation.]

## 4. What I did not build

- `--env-default`'s actual device-side effect is unverified on real
  hardware (no root on Nova/Thor to confirm one way or the other beyond
  "run-as fails as expected against a non-debuggable package" from reading
  the code path dispatcher.sh already uses for the debug pref write).
- No change to `nightly_build.sh`'s gh-failure messaging: already correct
  (see section 2) -- a change here would be solving a problem that doesn't
  exist in this file.

## 5. Next (P x win, per the owner's ranking rule)

| Candidate | P | win | cost |
|---|---|---|---|
| Reinstall `hakux-nightly.service`/`.timer` from repo once GitHub is back | ~1.0 (the stale file is confirmed, the fix is "copy the file + daemon-reload") | removes a real, if so-far-silent, fast-forward-during-a-dispatch-run hazard on the shared checkout | minutes, host-side, not this lane |
| Give `--env-default` a non-debuggable delivery path (e.g. a world-readable file the native layer polls, or an `am start --es` extra `MainActivity` reads at launch) | ~0.3 (no evidence yet it's ever been asked for against the release channel; may not be worth the app-side change) | unblocks one bracketed sub-feature of `owner_build.sh` | an app-code change + a device round-trip to confirm; out of this lane's "no emulator code" / $15 budget |
| Device verification (both apps' Apps->App info + on-screen label) | ~1.0 (the build/UI are both done and selftested; only the install step remains) | closes the brief's "Device" item at the only risk point (actually seeing it on screen) | one Nova hold, ~10 min |

Device verification is the only one of these inside this lane's scope and
budget; the systemd reinstall and the env-default delivery path are both
named above for whoever picks them up next, not attempted here.
