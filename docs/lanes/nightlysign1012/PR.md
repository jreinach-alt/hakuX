# nightlysign1012: the nightly refuses to publish an unsigned or unnamed apk (#433, 0.5)

State: ready

Lane: nightlysign1012          Issue: #433 umbrella
Base: master @ c6e0a63852
Files: docs/testing/nightly_build.sh, docs/testing/jobs/run-nightly.sh, docs/testing/jobs/selftest.d/86-nightly-notes.sh, docs/testing/jobs/selftest.d/87-nightly-trunk.sh, docs/testing/jobs/selftest.d/88-nightly-sign.sh
Prediction: none (a build/publish fix, not a measured arm)
Needs device: no    Needs NDK: no

Every nightly apk from 2026-10-03 through 2026-10-12 failed `apksigner
verify` ("Missing META-INF/MANIFEST.MF") and was named with an empty version
(`hakuX--nightly-<day>-<sha>.apk`). Two separate causes, one fix each:

- `jobs/run-nightly.sh` builds in a private worktree that `git worktree add`
  starts with neither `android/key.properties` nor `local.properties` (both
  gitignored), so `build.gradle.kts`'s `hasReleaseKeystore` is false and the
  release signs with nothing. It now symlinks both in from the owner's own
  checkout when present and not already there, the same way
  `owner_build.sh` already carries `local.properties` into its own private
  worktree.
- `nightly_build.sh` named the apk from a `versionName = "..."` literal that
  no longer exists in `build.gradle.kts` (it is `stampedVersionName()` now,
  via `version_stamp.sh`). It now reads `version_stamp.sh`'s `BASE_VERSION`
  instead, and refuses to publish (exit 10) rather than publish an empty
  name if that is unreadable.
- `nightly_build.sh` now runs `apksigner verify` on the built apk, located
  through `local.properties`' `sdk.dir` (same as Gradle itself; newest
  `build-tools` version wins), and refuses to publish (exit 11) if the tool
  can't be found or the apk doesn't verify. This runs after the existing
  "nothing player-facing" publish-skip (exit 9) and before `gh release
  create`, so an apk nobody can install never reaches a release.

Both new exit codes are in the header's exit-code table alongside the
existing ones.

Tested: `bash -n` on every file touched. A new fragment,
`selftest.d/88-nightly-sign.sh`, drives both gates directly (no SDK, no
gradle, no device) over five fixtures — no `version_stamp.sh` (exit 10), the
real `BASE_VERSION` naming the apk and still publishing, no apksigner on the
fake `sdk.dir` (exit 11), apksigner rejecting the apk the way the real
nightlies' did (exit 11, the defect itself), and apksigner accepting it (the
control, so the refusals above aren't just refusing always). All 17 checks
pass. `selftest.d/86-nightly-notes.sh`'s own build-mode fixture needed a stub
`version_stamp.sh` so the new version read doesn't mask its exit-9 check;
with that, its full file passes (69 checks).

`selftest.d/87-nightly-trunk.sh`'s own build-mode "at the tip" fixture also
needed a stub `docs/testing/version_stamp.sh` (committed to its `$SEED`, so
`$BEHIND` and `$CURRENT` both carry it) and, on `$CURRENT` alone, a fake
`sdk.dir`/apksigner that verifies, the same shape `88-nightly-sign.sh`
already stubs. With both, its full file passes.

Release note: none.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
