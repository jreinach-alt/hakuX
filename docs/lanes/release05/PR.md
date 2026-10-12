# release05: version 0.5.0 and a classifier route for the Ghoulies release soak (#433, 0.5)

State: ready

Lane: release05          Issue: none (#433 umbrella)
Base: master @ 1f317671b7
Files: android/app/build.gradle.kts, docs/testing/version_stamp.sh, docs/testing/jobs/selftest.d/86-build-stamp.sh,
docs/testing/titles/routes/ghoulies.classifier.route, docs/lanes/release05/PR.md
Prediction: none (no emulator change)
Needs device: no (the release soak runs on the tagged fold)    Needs NDK: no

The 0.5 targets are met: 175 titles measured (target 145) and 50 Playable
(target 50). This change prepares the candidate.

- Version 0.5.0. `version_stamp.sh` now stamps builds `0.5.0-<MMDD>-<sha>`,
  `versionCode` goes from 8 to 9, and the build's fallback name (no git) is
  `0.5.0-unknown`. The build-stamp selftest expects the new base.
- `ghoulies.classifier.route`: Grabbed by the Ghoulies opened by the
  classifier (`drive generic 480 mark`) on the kept profile, followed by
  `ghoulies.route`'s play loop. This is the route for the release gate:
  median gfps >= 25 over 90-240 s of play on the candidate APK.

Checks: `SELFTEST_ONLY=86-build-stamp selftest.sh` passes (10 of 10);
`route.sh --check` passes; `titlestate.py resolve-route --route
ghoulies.classifier --title-id 4D530053` resolves to state `returning` with
no refusal.

Release note: none

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
