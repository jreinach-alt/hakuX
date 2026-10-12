# debugcap1012: Debug Capture is off by default in versioned releases (#433, 0.5)

State: draft

Lane: debugcap1012          Issue: none (#433 umbrella)
Base: master @ 1ed3ac8f39
Files: android/app/build.gradle.kts, android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt, android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt, android/app/src/main/res/values/strings.xml, docs/testing/release_build.sh, docs/testing/release_build_selftest.sh, docs/releases/README.md, docs/lanes/debugcap1012/PR.md
Prediction: none (UI default only; no emulator change)
Needs device: no    Needs NDK: yes

## Design

The pause menu's "Debug Capture" button is gated on the `debug_tools`
SharedPreferences boolean (PauseMenuOverlay.kt / MainActivity.kt /
SettingsActivity.kt), which previously defaulted to `false` everywhere. The
owner wants it ON by default in dailies and working builds (so contributors
keep seeing it) and OFF by default in a versioned release, with Settings >
Debug Tools still able to flip it either way.

Build TYPE can't carry that distinction: nightlies (`nightly_build.sh`),
owner builds (`owner_build.sh`) and the dispatcher's working builds are all
plain `assembleRelease`/`assembleDebug`, and versionName is always the
`<base>-<MMDD>-<sha>` stamp (`version_stamp.sh`) unless something overrides
it. So this adds one new, explicit signal:

- **`android/app/build.gradle.kts`**: a Gradle property `-PversionedRelease=
  <X.Y.Z[-suffix]>`. When set, it's validated against
  `^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?$` (the build fails with a clear
  message otherwise), `versionName` becomes exactly that string instead of
  the stamp, and a new `resValue("bool", "debug_tools_default", ...)` is
  `false`. Unset (every existing build path), `debug_tools_default` is
  `true` and `versionName` is unchanged. The resource is the checkable
  marker: it ships in the APK, so it can be read back with `aapt2` instead
  of trusting that the Gradle property took effect.
- **`MainActivity.kt` / `SettingsActivity.kt`**: both now read
  `prefs.getBoolean("debug_tools", resources.getBoolean(R.bool.debug_tools_default))`
  instead of a literal `false`. A value the user has actually stored (via
  the Settings switch, which is unchanged) always wins over the default, so
  a contributor can still turn Debug Capture on in a release build.
- **`docs/testing/release_build.sh <version>`**: the new, only normal
  caller of `-PversionedRelease`. Refuses before building unless the tree
  is clean and `HEAD` is exactly `v<version>^{commit}`; after building,
  refuses unless the produced APK's own `aapt2 dump badging`/`dump
  resources` agree that `versionName == <version>` and
  `bool/debug_tools_default == false`. Prints the APK path on success.
- **`docs/testing/release_build_selftest.sh`**: fixtures for every refusal
  (bad version string, dirty tree, no such tag, HEAD not at the tag, wrong
  versionName in the built APK, wrong `debug_tools_default` in the built
  APK, a real Gradle failure) plus the one path that must reach the build,
  all against a throwaway git repo with stub `gradlew`/`aapt2` -- no SDK,
  no network, sub-second. `bash docs/testing/release_build_selftest.sh`.
- **`docs/releases/README.md`**: five-line pointer to `release_build.sh` as
  how a versioned release is built, for anyone landing in the directory.

Also folded in, same lane: the About screen's source/license/disclaimer/
privacy links (`android/app/src/main/res/values/strings.xml`) pointed at
the upstream Android port's repo rather than this fork's. They now point at
`https://github.com/jreinach-alt/hakuX` (and its `LICENSE`/`COPYING`/
`PRIVACY.md`, the last written by another lane); `library_about_url_fork`
(xemu-project/xemu) is unchanged. No other `res/values-*/strings.xml` in
this project carries these keys, so there was nothing else to update.

## The two builds

Built twice in a fresh worktree (`/home/justin/hakux-work/wt/debugcap1012`),
unsigned (no keystore present), and read back with `aapt2` from
`$ANDROID_SDK_ROOT/build-tools/36.1.0`:

Plain `assembleRelease` (7m 20s, cold native build):
```
versionName='0.5.0-1012-1ed3ac8f39-dirty'
bool/debug_tools_default: () true
```

`assembleRelease -PversionedRelease=0.5.0` (1m 1s, resource/package tasks
only -- no native rebuild, since nothing native-facing changed):
```
versionName='0.5.0'
bool/debug_tools_default: () false
library_about_url_source:     "https://github.com/jreinach-alt/hakuX"
library_about_url_license:    "https://github.com/jreinach-alt/hakuX/blob/master/LICENSE"
library_about_url_disclaimer: "https://github.com/jreinach-alt/hakuX/blob/master/COPYING"
library_about_url_privacy:    "https://github.com/jreinach-alt/hakuX/blob/master/PRIVACY.md"
library_about_url_fork:       "https://github.com/xemu-project/xemu"
```

Diffing the two APKs' `aapt2 dump resources`/`dump badging` output shows
exactly the two expected lines changed (`bool/debug_tools_default` and
`versionName`), confirming the property actually drives the generated
resource rather than the build silently reusing a cached value. Settings >
Debug Tools (`switch_debug_tools`) is present and unchanged in both builds.

Release note: The pause menu's Debug Capture is off by default in release builds (Settings > Debug Tools turns it on), and About links to this project's source and license.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
