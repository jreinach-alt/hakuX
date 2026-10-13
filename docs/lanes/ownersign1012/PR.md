# ownersign1012: owner builds are signed again, and refuse an unsigned apk (#433, 0.5)

State: ready

Lane: ownersign1012          Issue: none (harness defect, dispatched directly)
Base: master @ 7ce93f5353
Files: docs/testing/owner_build.sh, docs/testing/jobs/selftest.d/88-ownersign1012.sh, docs/lanes/ownersign1012/PR.md
Prediction: none (harness)
Needs device: no    Needs NDK: no

owner_build.sh builds the RELEASE android variant in a private detached
`git worktree` and installs it as com.jreinach.hakux, the owner's stable
channel. `android/key.properties` is gitignored, so the worktree started
without it, `build.gradle.kts`'s `hasReleaseKeystore` stayed false,
`assembleRelease` signed with nothing, and the unsigned apk reached
`adb install -r` and failed there (exit 6) -- indistinguishable from a real
device problem. lane.nightlysign1012 found and fixed the identical defect in
the nightly build; this carries the same two-part fix into owner_build.sh:

1. `android/key.properties` is symlinked (never copied) from `$REPO` into
   the private worktree whenever the source exists and nothing is already
   there, same as jobs/run-nightly.sh does for the nightly. storeFile's
   shape is then read and reported -- "absolute (exists)" or
   "relative (missing)", etc. -- never its value, and never
   storePassword/keyPassword. A relative storeFile resolves against
   `android/app` (where build.gradle.kts's bare `file()` call runs, not
   against the worktree root), so that case gets its own symlink into
   `android/app/<path>` from the matching path under `$REPO/android/app`.
   Against the real repo today: storeFile is absolute, and exists.

2. The built apk is run through `apksigner verify` before `adb install`
   ever sees it. apksigner is located via `local.properties`' `sdk.dir`,
   newest `build-tools/*` first, matching nightlysign1012's approach. If
   apksigner can't be located, or it rejects the apk, the script refuses
   with a new exit code (7) and a one-line reason naming the likely cause
   ("no key.properties") -- `adb install` is never reached either way. The
   header's exit-code list documents 7 alongside the existing 1-6.

3. The device lookup. owner_build.sh passed `device_env` the label it takes
   on its command line ("nova"), but `device_env` in devices.sh keys on an
   ADB serial and answers "unknown device nova", so the script exited 2
   before building anything on either device. It now maps nova to ee317437
   and thor to bdc158a5 before the call; devices.sh is unchanged.

Self-test: `docs/testing/jobs/selftest.d/88-ownersign1012.sh`, driven with
`SELFTEST_ONLY`, with no real device, gradle, SDK or network. A throwaway git
repo stands in for `$REPO`: gradlew is stubbed to produce the one artifact
assembleRelease produces, and key.properties is written after the repo's
commit so it stays untracked, like the real gitignored file. A fake apksigner
sits on a fixture `build-tools/9.9.9/`, and a fake adb logs every call. The
real devices.sh is sourced, so the device lookup is under test too. Cases:

- (a) key.properties present: linked into the tree, storeFile reported as
  absolute and existing, and the build completes;
- (b) apksigner rejects: exit 7, the cause named, and adb never asked to
  install;
- (c) apksigner missing: exit 7, and adb never asked to install;
- (d) apksigner accepts: exit 0, and adb asked to install on `-s ee317437`
  for the label `nova`. This is the control for (b) and (c).

Result: `selftest: 17 passed, 0 failed, PARTIAL: 1 of 139 fragments`. With
the previous label-passing lookup put back, the same fragment reports 4
passed and 13 failed, with a failure in every case: each run exits 2 before
building.

Release note (none): harness only.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
