#!/usr/bin/env bash
# Android debug build of this worktree, perflog variant (what the run uses).
# Detach it and poll the log for GRADLE_EXIT=:
#   setsid nohup docs/lanes/flushstall787/build.sh > docs/lanes/flushstall787/.build.log 2>&1 < /dev/null &
set -u
export JAVA_HOME=$HOME/toolchains/jdk21
export ANDROID_SDK_ROOT=$HOME/Android/Sdk
export PATH="$JAVA_HOME/bin:$ANDROID_SDK_ROOT/cmake/3.30.3/bin:$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/../../../android" || exit 2
git -C .. status --short | grep -v '^??' && { echo "DIRTY TREE"; echo GRADLE_EXIT=99; exit 99; }
echo "building $(git rev-parse --short HEAD)"
./gradlew --no-daemon assembleDebug -Pperflog=true
echo "GRADLE_EXIT=$?"
