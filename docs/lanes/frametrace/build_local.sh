#!/usr/bin/env bash
# Build this worktree's APK as the dispatcher does (assembleDebug), with the
# toolchain AGENTS.md names. Run detached; the last line is GRADLE_EXIT=<rc>.
export JAVA_HOME="$HOME/toolchains/jdk21"
export ANDROID_SDK_ROOT="$HOME/Android/Sdk"
export PATH="$JAVA_HOME/bin:$ANDROID_SDK_ROOT/cmake/3.30.3/bin:$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/../../../android" || exit 9
./gradlew --no-daemon assembleDebug
echo "GRADLE_EXIT=$?"
