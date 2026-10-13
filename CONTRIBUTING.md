# Contributing to hakuX

hakuX is an original Xbox emulator for Android
(`xemu -> izzy2lost/xemu (X1 BOX) -> rfandango/hakuX -> this fork`). This
page covers building, testing titles, and submitting pull requests.

## Building

### Desktop (Linux)

Dependencies (Debian/Ubuntu):

```bash
sudo apt-get install -y ninja-build ccache python3-venv pkg-config \
  libglib2.0-dev libpixman-1-dev \
  libsdl2-dev libepoxy-dev libgtk-3-dev \
  libvulkan-dev mesa-vulkan-drivers \
  libslirp-dev libpcap-dev libssl-dev libgmp-dev \
  libpng-dev libsamplerate0-dev libasound2-dev libpulse-dev \
  libcap-ng-dev libattr1-dev libdrm-dev libpcre2-dev \
  nlohmann-json3-dev libcurl4-openssl-dev
```

Then, from the repository root:

```bash
./configure --target-list=i386-softmmu --extra-cflags=-DXBOX=1
make -j"$(nproc)"
```

The resulting binary is `build/qemu-system-i386`.

### Android

Toolchain (see [`android/README.md`](android/README.md) for the full list):

- Android SDK 36, Build Tools 36.1.0, NDK 29.0.14206865, CMake 3.30.3
- JDK 21 (not 25 -- check for `bin/javac`, a plain `java` binary is not enough)
- **meson** and **ninja on `PATH`** -- the native build compiles glib with
  meson, and meson needs ninja, which Gradle does not put on `PATH` for it.
  `$ANDROID_SDK_ROOT/cmake/3.30.3/bin` has a `ninja` that works.
- Nothing else: the ISO -> XISO converter builds from
  `android/third_party/extract-xiso` with the same toolchain.

```bash
export JAVA_HOME=/path/to/jdk21          # must contain bin/javac
export ANDROID_SDK_ROOT=$HOME/Android/Sdk
export PATH="$JAVA_HOME/bin:$ANDROID_SDK_ROOT/cmake/3.30.3/bin:$PATH"
cd android
./gradlew assembleDebug
```

The APK lands at `android/app/build/outputs/apk/debug/app-debug.apk`. It
installs as `com.jreinach.hakux.debug` ("hakuX (test builds)"), alongside a
release install rather than replacing it -- separate settings, HDD image
and saves.

## Testing titles

1. Build and install the debug APK (above), or `./gradlew installDebug`.
2. Add games: grant a games folder through the in-app library (this needs
   real UI interaction; it's a Storage Access Framework grant).
3. Play, and if something is worth reporting, use the **Title /
   Compatibility Report** issue form. A useful report has what's in
   [`docs/reporting-bugs.md`](docs/reporting-bugs.md) -- device, hakuX
   version, what you saw, and a logcat or Debug Capture if it's a rendering
   problem.
4. Check [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) and the
   [issue tracker](https://github.com/jreinach-alt/hakuX/issues) first --
   someone may have already filed what you found.

## Submitting PRs

1. Fork the repository and branch from `master`.
2. Keep one logical change per PR -- a fix and an unrelated refactor belong
   in separate PRs, even if you touched both while working.
3. Describe what you tested and on which device (or, for a desktop-only
   change, which platform) in the PR description. Hosted CI does not
   currently run against this repository, so this description is the only
   record that the change was actually exercised -- state it plainly rather
   than leaving it implied.
4. Use [`.github/pull_request_template.md`](.github/pull_request_template.md)
   (it's filled in for you when you open a PR) as the checklist.
5. Contributions are under the project's license, GPL-2.0 -- see
   [`COPYING`](COPYING), [`COPYING.LIB`](COPYING.LIB) and
   [`LICENSE`](LICENSE). No sign-off line is required.
