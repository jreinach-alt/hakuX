# release052b: versionCode 10, the driver link, and two known-issue lines for 0.5.2 (#433)

State: ready

Lane: release052b            Issue: #433
Base: master @ 2be43a56f6 (drivernotice1017's fold)
Files: android/app/build.gradle.kts, KNOWN_ISSUES.md, docs/gpu-driver.md, docs/releases/v0.5.2.md, docs/lanes/release052b/
Prediction: none: metadata and docs
Needs device: no    Needs NDK: no
Selftest: none -- no file under docs/testing/ or tools/ changes

Release note (none): version bookkeeping only.

0.5.0 and 0.5.1 both shipped as versionCode 9, so 0.5.2 needs a higher one to install as an update:
`android/app/build.gradle.kts` goes 9 to 10. That line is the only change to the file; it is APK metadata, and
offline_fold.py now treats a versionCode-only diff of that one file as non-code (any other changed line in it is
still code and still needs a device run).

Docs: `docs/gpu-driver.md` links the driver's page (MrPurple666/purple-turnip) in "Installing it";
`KNOWN_ISSUES.md` drops "aimed at 0.5.2" from #938 and #939, which 0.5.2 does not fix;
`docs/releases/v0.5.2.md` says 0.5.2 installs over 0.5.1 as an ordinary update.
