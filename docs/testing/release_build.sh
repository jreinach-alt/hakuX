#!/usr/bin/env bash
#
# Build and verify a VERSIONED RELEASE APK (#433).
#
#   docs/testing/release_build.sh <version>
#     version   the release version, e.g. 0.5.0 or 0.5.0-rc1
#
# WHY A SEPARATE STEP. Debug Capture (the pause menu's "Debug Capture"
# button, gated on the "debug_tools" preference) is on by default in every
# build this repo normally produces -- nightlies (nightly_build.sh), owner
# builds (owner_build.sh) and the dispatcher's working builds are all plain
# `assembleRelease`/`assembleDebug`, so the owner's standing order (#433) is
# that contributors keep seeing it there. A versioned release is the one
# build that ships to players outside this project, and that is the one
# place Debug Capture should default off -- Settings > Debug Tools still
# turns it back on for anyone who wants it, contributors included.
#
# Build TYPE can't tell a nightly from a versioned release (both are
# assembleRelease) and versionName can't either (it's always
# <base>-<MMDD>-<sha> unless something overrides it -- version_stamp.sh).
# So this is the one caller that passes -PversionedRelease=<version> to
# Gradle, which is what actually switches the default (android/app/
# build.gradle.kts) and pins versionName to exactly <version>.
#
# REFUSES before building unless:
#   - the tree is clean (a release must be exactly its tagged commit, not
#     that commit plus whatever happens to be sitting in the working copy)
#   - HEAD is exactly v<version>^{commit} (so <version> names a real,
#     reviewed tag rather than whatever the checkout happens to be on)
#
#   - for a plain X.Y.Z, docs/releases/v<version>.md exists and links
#     docs/gpu-driver.md (every release note names the tested GPU driver)
#
# and REFUSES after building unless the APK is signed and its own aapt2 dump agrees
# that versionName is exactly <version> and bool/debug_tools_default is
# exactly "false" -- so a defect in the Gradle wiring is caught here, against
# the actual artifact, rather than discovered after it ships.
#
# Prints the APK's path on stdout as its last line; everything else is
# status, on stderr.
set -u

usage() { echo "usage: ${0##*/} <version>" >&2; exit 2; }
[ "$#" -eq 1 ] || usage
VERSION="$1"
VERSION_RE='^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?$'
[[ "$VERSION" =~ $VERSION_RE ]] || {
    echo "${0##*/}: '$VERSION' doesn't look like a version (want X.Y.Z or X.Y.Z-suffix)" >&2
    exit 2
}

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

# A versioned release is exactly its tagged commit's tree -- not that commit
# plus an uncommitted edit nobody reviewed. Tracked and untracked both count:
# unlike version_stamp.sh's "-dirty" (which only flags tracked changes,
# because it is naming a commit that may have scratch files sitting beside
# it), a release step has no business publishing an untracked file either.
DIRTY=$(git -C "$REPO" status --porcelain | wc -l)
if [ "$DIRTY" -gt 0 ]; then
    echo "${0##*/}: refusing -- $REPO has $DIRTY uncommitted change(s); a versioned release is built from a clean, tagged commit" >&2
    exit 1
fi

TAG="v$VERSION"
TAG_SHA=$(git -C "$REPO" rev-parse -q --verify "$TAG^{commit}") || {
    echo "${0##*/}: refusing -- no tag '$TAG' in $REPO" >&2
    exit 1
}
HEAD_SHA=$(git -C "$REPO" rev-parse HEAD)
if [ "$HEAD_SHA" != "$TAG_SHA" ]; then
    echo "${0##*/}: refusing -- HEAD ($HEAD_SHA) is not $TAG ($TAG_SHA); check out the tag first" >&2
    exit 1
fi

# Every final release note links the GPU driver page (owner, 2026-10-17): the
# one driver hakuX is tested with. A -rc or other suffixed build has no note
# of its own, so only a plain X.Y.Z is held to it.
if [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    NOTE="$REPO/docs/releases/v$VERSION.md"
    if [ ! -f "$NOTE" ]; then
        echo "${0##*/}: refusing -- no release note at docs/releases/v$VERSION.md" >&2
        exit 10
    fi
    if ! grep -q 'docs/gpu-driver\.md' "$NOTE"; then
        echo "${0##*/}: refusing -- docs/releases/v$VERSION.md does not link docs/gpu-driver.md (every release note names the tested GPU driver)" >&2
        exit 10
    fi
fi

echo "${0##*/}: building $VERSION from $TAG ($HEAD_SHA) ..." >&2
if ! ( cd "$REPO/android" && ./gradlew --no-daemon assembleRelease "-PversionedRelease=$VERSION" ); then
    echo "${0##*/}: build failed" >&2
    exit 3
fi

APK=$(find "$REPO/android/app/build/outputs/apk/release" -name '*.apk' | head -1)
[ -n "$APK" ] || { echo "${0##*/}: build succeeded but produced no apk" >&2; exit 4; }
# Gradle signs a release only when android/key.properties names a keystore
# (android/app/build.gradle.kts); without one it writes app-release-unsigned.apk,
# which Android refuses to install.
case "$APK" in
    *-unsigned.apk)
        echo "${0##*/}: refusing -- $APK is unsigned (android/key.properties has no release keystore here); Android will not install it" >&2
        exit 8 ;;
esac

SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}"
AAPT2="$SDK_ROOT/build-tools/36.1.0/aapt2"
if [ ! -x "$AAPT2" ]; then
    AAPT2="$SDK_ROOT/build-tools/36.1.0/aapt"
fi
[ -x "$AAPT2" ] || {
    echo "${0##*/}: refusing -- no aapt2 or aapt under $SDK_ROOT/build-tools/36.1.0 (set ANDROID_SDK_ROOT); $APK was built but not verified" >&2
    exit 5
}

# #433: re-sign with the rotated key, v3-only + lineage, but ONLY once
# ~/keystores/hakux-rotation.lineage exists and key.properties names that
# keystore -- otherwise this is a no-op and $APK is exactly what Gradle
# produced, same as before the rotation.
APKSIGNER="$SDK_ROOT/build-tools/36.1.0/apksigner"
[ -x "$APKSIGNER" ] || APKSIGNER=$(find "$SDK_ROOT/build-tools" -maxdepth 2 -name apksigner -type f 2>/dev/null | sort -V | tail -1)
if [ -n "$APKSIGNER" ]; then
    # shellcheck source=sign_lineage.sh
    . "$HERE/sign_lineage.sh"
    resign_with_rotation "$APK" "$REPO/android/key.properties" "$APKSIGNER" || {
        echo "${0##*/}: refusing -- the rotated re-sign of $APK did not check out; nothing published" >&2
        exit 9
    }
    if [ "$ROTATION_APPLIED" = 1 ] && ! lineage_lists_both_certs "$APK" "$APKSIGNER"; then
        echo "${0##*/}: refusing -- $APK was re-signed but its lineage does not list both certs" >&2
        exit 9
    fi
fi

# `aapt2 dump badging` prints versionName='...' on its "package:" line.
GOT_VERSION=$("$AAPT2" dump badging "$APK" 2>/dev/null | sed -nE "s/.*versionName='([^']*)'.*/\1/p" | head -1)
if [ "$GOT_VERSION" != "$VERSION" ]; then
    echo "${0##*/}: refusing -- $APK reports versionName '$GOT_VERSION', expected '$VERSION'" >&2
    exit 6
fi

# `aapt2 dump resources` prints "resource <id> bool/<name>" then its value(s)
# on the following indented line(s), e.g. "      () true". The first value
# line after the matching resource line is the default configuration's.
GOT_DEFAULT=$("$AAPT2" dump resources "$APK" 2>/dev/null | awk '
    /[[:space:]]bool\/debug_tools_default$/ { want = 1; next }
    want && NF { print $NF; exit }
')
if [ "$GOT_DEFAULT" != "false" ]; then
    echo "${0##*/}: refusing -- $APK reports bool/debug_tools_default='$GOT_DEFAULT', expected 'false' (Debug Capture must default off in a versioned release)" >&2
    exit 7
fi

echo "${0##*/}: verified -- versionName=$VERSION debug_tools_default=false" >&2
echo "$APK"
