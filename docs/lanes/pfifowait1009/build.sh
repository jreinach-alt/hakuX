#!/bin/bash
# Debug APK of this worktree's HEAD, copied to apk/<sha>.apk. Run detached;
# the last line of the log is GRADLE_EXIT=<rc>.
cd "$(dirname "$0")/../../../android" || exit 1
export JAVA_HOME=/home/justin/toolchains/jdk21
# meson (glib's configure) needs ninja; the SDK's cmake carries one.
export PATH="$HOME/.local/bin:/home/justin/Android/Sdk/cmake/3.30.3/bin:$PATH"
sha=$(git rev-parse --short HEAD)
./gradlew assembleDebug
rc=$?
if [ "$rc" -eq 0 ]; then
  mkdir -p ../docs/lanes/pfifowait1009/apk
  cp app/build/outputs/apk/debug/app-debug.apk "../docs/lanes/pfifowait1009/apk/$sha.apk"
fi
echo "GRADLE_EXIT=$rc"
