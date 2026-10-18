# Building the Android app

_Last updated 2026-10-17, for version 0.5.2._

This folder is the Android app: a Gradle and CMake project that builds the
xemu core as native libraries, wrapped in a Kotlin app with setup, settings
and the game library. The [main README](../README.md) describes what the app
does. This page covers building it.

## Toolchain

- Android SDK 36 and Build Tools 36.1.0
- NDK 29.0.14206865
- CMake 3.30.3
- JDK 21. JDK 25 does not work.
- **meson.** The native build uses it to compile glib. Without it the build
  fails late, with `meson not found in PATH; required to build glib for
  Android`.
- **ninja on your `PATH`.** meson needs it. The SDK ships one at
  `$ANDROID_SDK_ROOT/cmake/3.30.3/bin/ninja`, but Gradle hands it only to
  CMake. Without it on `PATH` the build fails with
  `Could not detect Ninja v1.8.2 or newer`.

The ISO-to-XISO converter builds from `android/third_party/extract-xiso` with
the same toolchain. Leave it out with `-DXEMU_ENABLE_XISO_CONVERTER=OFF`.

## Build

From this folder:

```bash
./gradlew assembleDebug      # installs as "hakuX (test builds)"
./gradlew assembleRelease    # installs as "hakuX CE"
```

A release build has to be signed with the same key every time, or it cannot
update an existing install. [RELEASING.md](RELEASING.md) explains signing.

## SDL2

CMake fetches SDL2 (`release-2.32.10` by default). To build against your own
checkout:

```bash
./gradlew assembleDebug -Pandroid.experimental.cmake.arguments=-DSDL2_LOCAL_DIR=/path/to/SDL
```
