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

Self-test: `docs/testing/jobs/selftest.d/88-ownersign1012.sh`, driven
directly with `SELFTEST_ONLY`, no real device/gradle/SDK/network -- a
throwaway git repo stands in for `$REPO` (gradlew stubbed to produce the one
artifact assembleRelease produces; key.properties written AFTER the repo's
commit so it stays untracked, same as the real gitignored file), a fake
apksigner on a fixture `build-tools/9.9.9/`, and a fake adb that logs every
call. `OWNER_BUILD_DEVICES_SH` is one added override, defaulting to today's
own devices.sh unchanged -- needed only because the real devices.sh keys
`device_env` on an ADB serial and has no row for the labels "nova"/"thor"
this script takes on its command line, so a selftest with no device at all
needs its own stand-in; that mismatch is pre-existing, out of scope for this
lane, and is not touched here. Four cases: (a) key.properties present ->
linked into the tree, storeFile reported absolute/exists, build completes;
(b) apksigner rejects -> refuses with exit 7, names the cause, fake adb
never asked to install; (c) apksigner missing -> refuses with exit 7, fake
adb never asked to install; (d) apksigner accepts -> exit 0 and the fake adb
WAS asked to install (the control, proving (b) and (c) aren't passing by
refusing unconditionally). `bash -n` was run on both touched scripts.
Result: `selftest: 16 passed, 0 failed, PARTIAL: 1 of 139 fragments`.

Found but out of scope (not fixed, not edited): docs/testing/devices.sh's
`device_env` matches only literal ADB serials, never the "nova"/"thor"
labels owner_build.sh passes it -- `device_env nova` prints
"unknown device nova -- add it to devices.sh rather than guessing" and
returns 2. This is a real pre-existing gap but devices.sh is not in this
lane's file list, so it is reported here rather than touched.

Release note (none): harness only.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
