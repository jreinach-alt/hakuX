# hakuX Android build

This directory is the Android port: a Gradle/CMake project that builds the
xemu/QEMU core as native libraries and wraps them in a Kotlin app (SDL2 for
the native entry point, SAF-based file pickers for BIOS/HDD/game images, and
the setup, settings and game-library screens). See the top-level
[`README.md`](../README.md) for what the app does; this file covers building
it.

## Toolchain expectations
- Android SDK 36
- Build Tools 36.1.0
- NDK r29+ (configured to 29.0.14206865 in Gradle)
- CMake 3.30.3
- JDK 21 (**not** 25 — the build targets Java 21 and will not configure on 25)
- **meson** — the native build compiles glib with it. Without meson the build
  fails late inside CMake with `meson not found in PATH; required to build glib
  for Android`, not at configure time.
- **ninja on `PATH`** — meson needs it. One ships with the SDK at
  `$ANDROID_SDK_ROOT/cmake/3.30.3/bin/ninja`, but Gradle passes it to CMake via
  `-DCMAKE_MAKE_PROGRAM` only, so meson cannot see it. Add that directory to
  `PATH` or the build fails with `Could not detect Ninja v1.8.2 or newer`.

Both of the last two are installed explicitly by `.github/workflows/android.yml`.
A clean checkout does not build from the list above alone.

The ISO→XISO converter (`-DXEMU_ENABLE_XISO_CONVERTER=ON`, the default) builds
`extract-xiso` from `android/third_party/extract-xiso`; it needs no toolchain
beyond the one above. Build without it with
`-DXEMU_ENABLE_XISO_CONVERTER=OFF`.

## Build
From this directory:

```
./gradlew assembleDebug
```

`./gradlew assembleRelease` builds the release variant; see
[`RELEASING.md`](RELEASING.md) for signing it so it can upgrade in place
instead of costing users their saves.

## SDL2
SDL2 is fetched via CMake (default `release-2.32.10`). Mainline xemu moved to
SDL3 upstream; this port stays on SDL2. To use a local checkout instead of the
fetched one:

```
./gradlew assembleDebug -Pandroid.experimental.cmake.arguments=-DSDL2_LOCAL_DIR=/path/to/SDL
```
