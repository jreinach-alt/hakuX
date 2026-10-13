#!/usr/bin/env bash
#
# Build the RELEASE variant from a ref and install it on a device, for the
# owner's own stable playtest channel: com.jreinach.hakux, "hakuX" (#433).
#
#   owner_build.sh <ref|master> [--env-default KEY=VAL]... <nova|thor>
#
# This is not a dispatch request: there is no queue to wait in, so it
# REFUSES at once -- it does not retry or queue -- while the target device
# has a run in flight (a file under dispatch's running/ naming it). It builds
# in its own private detached worktree, never the shared checkout dispatcher.sh
# reads from ($DISPATCH_TREE / ~/hakuX) and never the dispatcher's own build
# tree, so this can never contend with, or be mistaken for, a dispatch build.
#
# Prints the stamped version (docs/testing/version_stamp.sh) it installed.
#
# --env-default writes docs/testing/dispatcher.sh's `env_vars` pref via
# run-as, the same mechanism the dispatcher uses for a request's `env`. THAT
# MECHANISM NEEDS A DEBUGGABLE PACKAGE, and the release build is deliberately
# not debuggable (it is the owner's stable channel, not a diagnostic one) --
# so on an unrooted device this reports the run-as failure and leaves the
# apk installed rather than silently doing nothing.
#
# Exit codes:
#   1   cannot resolve the ref, or the build worktree could not be created or
#       checked out
#   2   bad usage, or the device label is unknown
#   3   the device has a dispatch run in flight; refused, not queued
#   4   `./gradlew assembleRelease` failed
#   5   the build produced no apk
#   6   `adb install` failed
#   7   the apk does not verify (apksigner), or apksigner could not be
#       located; never installed
#
# android/key.properties is gitignored, same as local.properties, so
# `git worktree add` starts $WT without it -- and with no key.properties,
# build.gradle.kts's hasReleaseKeystore is false and the release build type
# signs with nothing, which is why this used to reach exit 6 (adb install
# failed) rather than ever installing (#433). Brought in below by symlink,
# not copy, so the private worktree never holds a second copy of the signing
# secret -- the same fix jobs/run-nightly.sh carries for the nightly, for the
# same reason. And because an apk nobody can install must never reach
# `adb install -r`, the built apk is verified with apksigner first; exit 7
# covers both "apksigner is missing" and "apksigner rejects it".
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Overridable only so a selftest fragment can stand in a fixture device_env
# (device_env takes a serial, not a label, and this repo's real devices.sh
# has none named "nova"/"thor" to drive a selftest with no device at all);
# the default is today's own devices.sh, unchanged.
. "${OWNER_BUILD_DEVICES_SH:-$HERE/devices.sh}"

REPO="${DISPATCH_REPO:-${DISPATCH_TREE:-/home/justin/hakuX}}"
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
WT="${OWNER_BUILD_WT:-$D/owner-build-tree}"
LOCK="$D/.owner-build.lock"
export JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}"
export PATH="/home/justin/Android/Sdk/cmake/3.30.3/bin:$PATH"
ADB_INSTALL_TIMEOUT="${ADB_INSTALL_TIMEOUT:-300}"
ADB_QUICK_TIMEOUT="${ADB_QUICK_TIMEOUT:-30}"
PKG="com.jreinach.hakux"

usage() {
    echo "usage: ${0##*/} <ref|master> [--env-default KEY=VAL]... <nova|thor>" >&2
    exit 2
}

[ "$#" -ge 2 ] || usage
REF="$1"; shift
ENV_DEFAULTS=()
while [ "$#" -gt 1 ]; do
    case "$1" in
        --env-default)
            [ "$#" -ge 2 ] || usage
            ENV_DEFAULTS+=("$2"); shift 2 ;;
        *) usage ;;
    esac
done
LABEL="$1"
case "$LABEL" in
    nova|thor) ;;
    *) usage ;;
esac
device_env "$LABEL" || { echo "${0##*/}: unknown device $LABEL" >&2; exit 2; }

# Refuse, don't queue: a run in dispatch/running/ owns the device until it
# ends, and this script has no slot to wait in behind it.
mkdir -p "$D/running"
busy=$(grep -lx "$LABEL" "$D"/running/*.owner 2>/dev/null | head -1)
if [ -n "$busy" ]; then
    echo "${0##*/}: $LABEL has a dispatch run in flight ($(basename "${busy%.owner}")); try again once it finishes" >&2
    exit 3
fi

# Resolve the ref in $REPO, before the build and before the lock: a half
# finished build of the wrong sha is worse than failing early.
SHA=$(git -C "$REPO" rev-parse --short "$REF" 2>/dev/null) || {
    git -C "$REPO" fetch -q origin 2>/dev/null
    SHA=$(git -C "$REPO" rev-parse --short "$REF" 2>/dev/null)
}
[ -n "${SHA:-}" ] || { echo "${0##*/}: cannot resolve ref '$REF' in $REPO" >&2; exit 1; }

exec 9>"$LOCK"
flock 9

if [ ! -e "$WT/.git" ]; then
    mkdir -p "$(dirname "$WT")"
    git -C "$REPO" worktree add --quiet --detach "$WT" "$SHA" || {
        echo "${0##*/}: cannot create build worktree at $WT" >&2; exit 1; }
else
    git -C "$WT" checkout --quiet --detach "$SHA" || {
        echo "${0##*/}: checkout of $SHA in $WT failed" >&2; exit 1; }
fi
# local.properties is gitignored and required (see dispatcher.sh's build_ref).
if [ ! -f "$WT/android/local.properties" ] && [ -f "$REPO/android/local.properties" ]; then
    cp "$REPO/android/local.properties" "$WT/android/local.properties"
fi
# android/key.properties is gitignored too (see the header). Symlinked, not
# copied, so $WT never holds a second copy of the signing secret. Checked
# every run, not just on first creation, so a worktree made before this fix
# still gets one -- [ ! -e ... ] first so a real file (or an existing
# symlink) already there is never replaced.
if [ -f "$REPO/android/key.properties" ] && [ ! -e "$WT/android/key.properties" ]; then
    ln -s "$REPO/android/key.properties" "$WT/android/key.properties"
fi
# A relative storeFile would resolve against $WT/android/app (where
# build.gradle.kts's bare file() call runs), not against $REPO where the
# real key.properties lives -- so the symlink alone would not be enough.
# Only the KEY is read, and only its shape is printed: never the value, and
# never storePassword/keyPassword.
if [ -f "$WT/android/key.properties" ]; then
    STORE_FILE=$(sed -n 's/^storeFile=//p' "$WT/android/key.properties" | tail -1)
    if [ -n "${STORE_FILE:-}" ]; then
        case "$STORE_FILE" in
            /*) STORE_KIND=absolute; STORE_TARGET="$STORE_FILE" ;;
            *)  STORE_KIND=relative; STORE_TARGET="$WT/android/app/$STORE_FILE" ;;
        esac
        STORE_EXIST=missing; [ -f "$STORE_TARGET" ] && STORE_EXIST=exists
        if [ "$STORE_KIND" = relative ] && [ "$STORE_EXIST" = missing ]; then
            # Resolve the same relative path against the owner's own
            # checkout's app module -- not a worktree, so it is where the
            # keystore has always actually lived -- and symlink it into the
            # same relative place under $WT so build.gradle.kts's file()
            # call finds it there too.
            REAL_STORE="$REPO/android/app/$STORE_FILE"
            if [ -f "$REAL_STORE" ] && [ ! -e "$STORE_TARGET" ]; then
                mkdir -p "$(dirname "$STORE_TARGET")"
                ln -s "$REAL_STORE" "$STORE_TARGET"
                STORE_EXIST=exists
            fi
        fi
        echo "${0##*/}: key.properties storeFile is $STORE_KIND ($STORE_EXIST)" >&2
    fi
fi

echo "${0##*/}: building release $SHA ..." >&2
BUILD_LOG="$D/logs/owner-build-$SHA.log"; mkdir -p "$D/logs"
if ! (cd "$WT/android" && ./gradlew assembleRelease) >"$BUILD_LOG" 2>&1; then
    echo "${0##*/}: build failed -- see $BUILD_LOG" >&2
    exit 4
fi
APK=$(find "$WT/android/app/build/outputs/apk/release" -name '*.apk' | head -1)
[ -n "$APK" ] || { echo "${0##*/}: build succeeded but produced no apk" >&2; exit 5; }

VER=$(bash "$HERE/version_stamp.sh" "$WT")

# An apk nobody can install must never reach `adb install -r` (#433: a
# missing key.properties used to get this far silently and only fail at
# install, exit 6, indistinguishable from a real device problem). apksigner
# lives under the SDK's build-tools, resolved from local.properties' sdk.dir
# -- the same file JAVA_HOME/the cmake PATH above stand in for -- rather
# than a hardcoded build-tools version, newest installed wins.
SDK_DIR=$(sed -n 's/^sdk\.dir=//p' "$WT/android/local.properties" 2>/dev/null | tail -1)
APKSIGNER=""
[ -n "$SDK_DIR" ] && APKSIGNER=$(find "$SDK_DIR/build-tools" -maxdepth 2 -name apksigner -type f 2>/dev/null | sort -V | tail -1)
if [ -z "$APKSIGNER" ]; then
    echo "${0##*/}: no apksigner under ${SDK_DIR:-<no sdk.dir>}/build-tools; cannot confirm $APK is signed (likely cause: no key.properties)" >&2
    exit 7
fi
if ! "$APKSIGNER" verify "$APK" >>"$BUILD_LOG" 2>&1; then
    echo "${0##*/}: $APK does not verify (apksigner) -- an unsigned apk is never installed (likely cause: no key.properties)" >&2
    exit 7
fi
echo "${0##*/}: verified: $APK is signed" >&2

echo "${0##*/}: installing $PKG ($VER) on $LABEL ($SERIAL)" >&2
timeout -k 5 "$ADB_INSTALL_TIMEOUT" adb -s "$SERIAL" install -r "$APK" 2>&1 | grep -q Success || {
    echo "${0##*/}: adb install failed on $LABEL ($SERIAL)" >&2
    exit 6
}

if [ "${#ENV_DEFAULTS[@]}" -gt 0 ]; then
    env_body=$(printf '%s\n' "${ENV_DEFAULTS[@]}")
    timeout -k 5 "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell am force-stop "$PKG" >/dev/null 2>&1
    tmp="$D/.owner-build-prefs.${LABEL}.xml"
    timeout -k 5 "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell "run-as $PKG cat shared_prefs/x1box_prefs.xml" \
        2>/dev/null | tr -d '\r' > "$tmp"
    if [ ! -s "$tmp" ]; then
        echo "${0##*/}: WARNING: could not set --env-default ($env_body): run-as $PKG failed." \
             "The release build is deliberately not debuggable, so this needs a rooted device;" \
             "$APK is installed without these env defaults." >&2
    else
        python3 - "$tmp" "$env_body" <<'PY'
import re, sys
path, body = sys.argv[1], sys.argv[2]
want = [l for l in body.splitlines() if l]
xml = open(path, encoding="utf-8").read()
m = re.search(r'name="env_vars"[^>]*>([^<]*)</string>', xml)
new_entry = '<string name="env_vars">%s</string>' % "\n".join(want).replace("&", "&amp;")
if m:
    xml = xml[:m.start()] + new_entry + xml[m.end():]
else:
    xml = xml.replace("</map>", new_entry + "</map>")
open(path, "w", encoding="utf-8").write(xml)
PY
        timeout -k 5 "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell "run-as $PKG mkdir -p shared_prefs" >/dev/null 2>&1
        timeout -k 5 "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell "run-as $PKG sh -c 'cat > shared_prefs/x1box_prefs.xml'" \
            < "$tmp" >/dev/null 2>&1
        rm -f "$tmp"
        echo "${0##*/}: set env defaults: $env_body" >&2
    fi
fi

echo "$VER"
