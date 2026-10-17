# Contributing

_Last updated 2026-10-16, for version 0.5.1._

hakuX is an original Xbox emulator for Android. Its lineage is xemu, then
X1 BOX (izzy2lost), then hakuX (rfandango), then this project, hakuX CE. This
page covers building it, testing games and sending pull requests.

## Building for Android

You need:

- Android SDK 36, Build Tools 36.1.0, NDK 29.0.14206865 and CMake 3.30.3
- JDK 21, a full JDK with `bin/javac` (JDK 25 does not work)
- `meson`, and `ninja` on your `PATH`. The SDK's
  `cmake/3.30.3/bin/ninja` works.

```bash
export JAVA_HOME=/path/to/jdk21
export ANDROID_SDK_ROOT=$HOME/Android/Sdk
export PATH="$JAVA_HOME/bin:$ANDROID_SDK_ROOT/cmake/3.30.3/bin:$PATH"
cd android
./gradlew assembleDebug
```

The APK is `android/app/build/outputs/apk/debug/app-debug.apk`. It installs
as **hakuX (test builds)** with its own settings, hard disk image and saves,
next to any release install. [android/README.md](android/README.md) has the
details.

## Building for desktop (Linux)

Dependencies on Debian or Ubuntu:

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

From the repository root:

```bash
./configure --target-list=i386-softmmu --extra-cflags=-DXBOX=1
make -j"$(nproc)"
```

The binary is `build/qemu-system-i386`.

## Testing games

1. Install a build, then add your games folder from the library.
2. Play. Check [Known issues](KNOWN_ISSUES.md) and the
   [issue tracker](https://github.com/jreinach-alt/hakuX/issues) for what you
   find.
3. If it is new, file it with the **Title / Compatibility Report** form.
   [Reporting a bug](docs/reporting-bugs.md) lists what to include.

## Pull requests

1. Fork the repository and branch from `master`.
2. One change per pull request. Put an unrelated cleanup in its own PR.
3. Say what you tested and on which device. No hosted CI runs on pull
   requests, so your description is the record that the change was tried.
4. The [pull request template](.github/pull_request_template.md) is the
   checklist.
5. Contributions are under the project's licence, GPL-2.0. See
   [LICENSE](LICENSE), [COPYING](COPYING) and [COPYING.LIB](COPYING.LIB). No
   sign-off line is needed.
