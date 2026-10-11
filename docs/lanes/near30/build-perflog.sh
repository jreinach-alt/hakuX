#!/usr/bin/env bash
# lane.near30: the perflog debug APK of this worktree's emulator code (master + docs).
# Written to build-perflog.log; the last line is GRADLE_EXIT=<rc>.
here=$(cd "$(dirname "$0")" && pwd)
# meson lives in ~/.local/bin on this host; without it CMake fails at configure (dispatcher.sh build_ref)
export PATH="$HOME/.local/bin:$HOME/Android/Sdk/cmake/3.30.3/bin:$PATH"
cd "$here/../../../android" || exit 1
./gradlew assembleDebug -Pperflog=true > "$here/build-perflog.log" 2>&1
rc=$?
mkdir -p "$here/../../../scratch" && cp app/build/outputs/apk/debug/app-debug.apk "$here/../../../scratch/app-debug-perflog.apk" 2>/dev/null
echo "GRADLE_EXIT=$rc" >> "$here/build-perflog.log"
