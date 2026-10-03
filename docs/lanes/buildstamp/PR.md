# buildstamp: every build says which commit it is, and the owner's release channel is never touched by a lane run

State: draft

Lane: buildstamp             Issue: #433 (0.5: 50 Playable)
Base: master @ 9550493846
Files: android/app/build.gradle.kts, android/app/src/main/res/layout/activity_game_library.xml,
       android/app/src/main/java/com/rfandango/haku_x/GameLibraryActivity.kt,
       docs/testing/version_stamp.sh (new), docs/testing/owner_build.sh (new),
       docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/86-build-stamp.sh (new),
       docs/lanes/buildstamp/PR.md, docs/lanes/buildstamp/NOTES.md, docs/lanes/buildstamp/OUTBOX.md
Prediction: none: harness/tooling, no emulator-behavior arm
Needs device: yes (one Nova hold, install-and-screenshot both apps) -- not yet done this session
Needs NDK: no
Release note (none): instrumentation/tooling only; no player-visible emulator behavior changed.

**versionName is now `<base>-<MMDD>-<shortsha>[-perflog][-dirty]`** of the commit actually being
built, computed once in `docs/testing/version_stamp.sh` and called from `build.gradle.kts` via a
small `ProcessBuilder` shellout (`stampedVersionName()`), run against the repo root `./gradlew` is
invoked from -- so a dispatcher build (its own detached `BUILD_TREE`) or `owner_build.sh`'s build
(its own detached worktree) stamps the ref it was actually asked to build, never the host's own
checkout. The stamp shows on screen: a small, muted corner label on `GameLibraryActivity` (the first
screen a player actually lands on), read back from the installed package's own `versionName` rather
than a compile-time constant.

The debug app (`com.jreinach.hakux.debug`, reinstalled by the dispatcher on every run) is relabelled
`"hakuX (test builds)"` so it plainly reads as the harness's app, not the owner's.

**`docs/testing/owner_build.sh <ref|master> [--env-default KEY=VAL]... <nova|thor>`** (new) builds the
release variant and installs it on request, in its own private worktree, refusing at once (not
queueing) if the target device has a dispatch run in flight. `--env-default` is implemented against
the same `run-as`-based pref write the dispatcher already uses for a request's `env` -- which needs a
debuggable package, so against the release build on these unrooted handhelds it reports that plainly
rather than silently no-op'ing (see NOTES.md section 4 for what that means for this one sub-feature).

**`docs/testing/dispatcher.sh` gets a new `guard_not_release_apk`**, checked right after the build and
before the device is even asked for, refusing to `adb install` anything whose compiled manifest
reports the bare release id `com.jreinach.hakux` (checked via the apk's own `AndroidManifest.xml`
string pool, not by filename). `_build_ref_locked` only ever builds the `debug` variant today, so there
is no live path from the dispatcher to the release apk -- this is defense in depth against that
changing later, not a fix for something observed.

**Selftest** (`docs/testing/jobs/selftest.d/86-build-stamp.sh`, new): the stamp's format over a
fixture repo (clean / `-perflog` / `-dirty` / both / untracked-only-is-not-dirty / non-git-tree
refusal), the guard as a unit over five apk fixtures (release / `.debug` / `.debug2` / a same-prefix
lookalike id / an empty placeholder apk, which must NOT be refused -- existing fakes for `build_ref`
use one), and the guard end-to-end through `serve_one` itself with a real/mutant pair (mutant: the
guard's own `if` block sed-deleted) built on a symlinked copy of `docs/testing` (the same shape
`51-dispatch-hardening.sh`'s `dhmut` uses). 15 checks, ran standalone and through
`SELFTEST_ONLY=86-build-stamp.sh bash docs/testing/jobs/selftest.sh`: 0 failures, ~37s. Also reran
`50-arms-requeue.sh 51-dispatch-hardening.sh` (the chain that exercises `dispatcher.sh` most directly)
and `99-battery-admit.sh` after editing `dispatcher.sh`, to check for a regression from the new guard
-- results in NOTES.md.

**The nightly's exit 4 is diagnosed, not changed.** I read the host's nightly logs (outside this
worktree; Bash here is sandboxed to it, confirmed). The brief's guess (a stale `ExecStartPre`
fast-forwarding `~/hakuX`) is real but not the cause: that stopgap predates `lane.nightlytrunk`'s fold
(2026-09-21) and was never removed from the *installed* systemd unit, but every fast-forward it has
run has succeeded. The actual, 100%-reproducing cause since 2026-09-30 is `HTTP 403: Sorry. Your
account was suspended` from `gh release create`/`upload` -- the same GitHub suspension this lane's own
offline ADDENDUM names. Per that ADDENDUM ("do not try to repair auth or reach GitHub by any other
route") I did not touch `gh`, auth, or `nightly_build.sh`'s publish step, which already logs the real
cause. Full detail and a ranked next-steps table in NOTES.md section 2/5. Reinstalling the host's
systemd units (closing the stale-`ExecStartPre` hazard) is a host action outside this lane's sandbox
and territory; named there for whoever owns that next.

**Territory note:** `docs/testing/dispatcher.sh` (and this lane generally) had zero rows in
`territory.toml` before this PR -- not drift, this lane was simply never granted any. Named in
OUTBOX.md per the brief's own instruction.

**Still open, this session:** the Nova device verification (install both apps, confirm the version in
Apps -> hakuX -> App info and on screen, screenshot both for the owner) has not run yet.
