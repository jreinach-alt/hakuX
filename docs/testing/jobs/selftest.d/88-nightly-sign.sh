# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check, and the live prediction's
# fixtures. Not executable, no shebang, no exit -- `fail` is shared and is
# the run's verdict.
#
# nightly_build.sh (#433, measured 2026-10-12): two defects in the same
# build-and-publish step, both covered here with stubs -- no SDK, no gradle,
# no device.
#
#   1. Every nightly apk from 2026-10-03 through 2026-10-12 failed `apksigner
#      verify` ("Missing META-INF/MANIFEST.MF"): the private worktree
#      jobs/run-nightly.sh builds in has no android/key.properties, so
#      build.gradle.kts signs the release with nothing. An apk nobody can
#      install must never be published.
#   2. The same nightlies were named with an empty version
#      (`hakuX--nightly-<day>-<sha>.apk`): versionName stopped being a
#      literal in build.gradle.kts (it is stampedVersionName(), computed by
#      version_stamp.sh) but nightly_build.sh kept grepping the old literal.
#
# Neither defect is reachable through `notes` mode -- both live after the
# gradle build -- so every fixture below runs BUILD mode, over a tiny stub
# tree of nightly_build.sh's own shape (android/gradlew replaced with a
# script that fakes assembleRelease's one output, same as
# 86-nightly-notes.sh's FIX5 and 87-nightly-trunk.sh's SEED).

echo "== nightly_build.sh: the version and the signing gate (#433)"
NS="$T/nightlysign"
NIGHTLY="$TESTING/nightly_build.sh"
rm -rf "$NS"; mkdir -p "$NS"

OLD_NS=$(date -d '3 days ago' -Iseconds)
NOW_NS=$(date -d '2 hours ago' -Iseconds)

ns_commit() {   # <repo> <subject> <date> <path...>
    local d=$1 subject=$2 when=$3; shift 3
    local p
    for p in "$@"; do mkdir -p "$d/$(dirname "$p")"; echo "$subject" >> "$d/$p"; done
    git -C "$d" add -A
    GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" git -C "$d" commit -q -m "$subject"
}

# <name> <base-version|""> -> a fresh repo at $NS/<name>, pushed to its own
# origin and AT the tip (so the trunk gate above this never refuses), with
# ONE player-facing emulator change dated two hours ago so the window is
# never empty -- an empty window would exit 9 before ever reaching the
# version or signing checks this file is about. $2 empty omits
# docs/testing/version_stamp.sh entirely, for the no-version fixture.
ns_tree() {
    local name=$1 base=$2
    local d="$NS/$name"
    rm -rf "$d"; mkdir -p "$d/android/app"
    git -c init.defaultBranch=master init -q "$d"
    git -C "$d" config user.email s@t; git -C "$d" config user.name s
    cat > "$d/android/gradlew" <<'GRADLEW'
#!/usr/bin/env bash
# selftest stub: produce the one artifact the real assembleRelease produces.
mkdir -p app/build/outputs/apk/release
echo "fake apk for $*" > app/build/outputs/apk/release/app-release.apk
GRADLEW
    chmod +x "$d/android/gradlew"
    if [ -n "$base" ]; then
        mkdir -p "$d/docs/testing"
        printf 'BASE_VERSION="%s"\n' "$base" > "$d/docs/testing/version_stamp.sh"
    fi
    ns_commit "$d" "base: the android stub" "$OLD_NS" README.md
    ns_commit "$d" "hw/xbox/nv2a: a player-facing change, so the window is never empty" \
        "$NOW_NS" hw/xbox/nv2a/sign.c
    git -c init.defaultBranch=master init -q --bare "$d.git"
    git -C "$d" remote add origin "$d.git"
    git -C "$d" push -q origin master
    printf '%s' "$d"
}

ns_fakesdk() {   # <dir> <exit-code> <stdout-line> -> writes build-tools/9.9.9/apksigner, prints the sdk.dir line
    local sdk=$1 rc=$2 line=$3
    mkdir -p "$sdk/build-tools/9.9.9"
    cat > "$sdk/build-tools/9.9.9/apksigner" <<APKSIGNER
#!/usr/bin/env bash
echo "\$*" >> "$sdk/calls.log"
echo "$line"
exit $rc
APKSIGNER
    chmod +x "$sdk/build-tools/9.9.9/apksigner"
    printf 'sdk.dir=%s\n' "$sdk"
}

# --------------------------------------------------- 1. no version -> exit 10
# THE CHECK: version_stamp.sh missing entirely (the shape of a tree old
# enough to predate it, or one where the file was deleted by accident) must
# refuse rather than publish `hakuX--nightly-<day>-<sha>.apk`.
NOVER=$(ns_tree novar "")
GH_NOVER="$NS/gh-nover.log"; : > "$GH_NOVER"
NIGHTLY_TREE="$NOVER" NIGHTLY_TIP=master NIGHTLY_OUT="$NS/out-nover" \
    SELFTEST_GH_LOG="$GH_NOVER" bash "$NIGHTLY" >"$NS/nover-build.log" 2>&1
rc=$?
check "THE CHECK: no version_stamp.sh -> refuses (exit 10), not an empty name" [ "$rc" = 10 ]
check "  and says why" grep -qF "no version found" "$NS/nover-build.log"
check "  nothing with an empty version segment reached disk" \
    bash -c '! find "$1" -name "hakuX--nightly-*.apk" 2>/dev/null | grep -q .' _ "$NS/out-nover"
check "  and nothing was published" bash -c '! grep -q "release create" "$1"' _ "$GH_NOVER"

# ---------------------------------------- 2. the real base version is used
# THE CHECK: version_stamp.sh's BASE_VERSION names the apk, not the literal
# `versionName = "..."` build.gradle.kts no longer has (and this fixture's
# android/app/build.gradle.kts does not even exist, so a read of the old
# line would find nothing).
VEROK=$(ns_tree verok "9.9.9-selftest")
SDKLINE=$(ns_fakesdk "$NS/sdk-verok" 0 "")
echo "$SDKLINE" > "$VEROK/android/local.properties"
GH_VEROK="$NS/gh-verok.log"; : > "$GH_VEROK"
NIGHTLY_TREE="$VEROK" NIGHTLY_TIP=master NIGHTLY_OUT="$NS/out-verok" \
    SELFTEST_GH_LOG="$GH_VEROK" bash "$NIGHTLY" >"$NS/verok-build.log" 2>&1
rc=$?
check "THE CHECK: BASE_VERSION names the apk, and the build still publishes (exit 0)" [ "$rc" = 0 ]
check "  the apk carries 9.9.9-selftest, not an empty or stale version" \
    bash -c '[ -n "$(find "$1" -name "hakuX-9.9.9-selftest-nightly-*.apk")" ]' _ "$NS/out-verok"

# ------------------------------------- 3. no apksigner found -> exit 11
# THE CHECK: no sdk.dir (or no build-tools under it) means this cannot
# confirm the apk is signed, so it refuses rather than publish on faith.
NOSDK=$(ns_tree nosdk "9.9.9-selftest")
GH_NOSDK="$NS/gh-nosdk.log"; : > "$GH_NOSDK"
NIGHTLY_TREE="$NOSDK" NIGHTLY_TIP=master NIGHTLY_OUT="$NS/out-nosdk" \
    SELFTEST_GH_LOG="$GH_NOSDK" bash "$NIGHTLY" >"$NS/nosdk-build.log" 2>&1
rc=$?
check "THE CHECK: no apksigner locatable -> refuses (exit 11)" [ "$rc" = 11 ]
check "  and says why" grep -qF "no apksigner under" "$NS/nosdk-build.log"
check "  the apk was still built (on disk if anyone wants it) -- just not published" \
    bash -c '[ -n "$(find "$1" -name "*.apk" 2>/dev/null)" ]' _ "$NS/out-nosdk"
check "  and gh was never asked to create a release" bash -c '! grep -q "release create" "$1"' _ "$GH_NOSDK"

# --------------------------- 4. THE DEFECT: apksigner rejects -> exit 11
# THE CHECK, the defect itself: an apksigner that reports the real nightlies'
# failure ("Missing META-INF/MANIFEST.MF") must stop the publish, not just
# log it -- this is #433's second half, and the one that let ten straight
# nights of an uninstallable apk reach `gh release create`.
UNSIGNED=$(ns_tree unsigned "9.9.9-selftest")
SDKLINE=$(ns_fakesdk "$NS/sdk-unsigned" 1 "DOES NOT VERIFY: ERROR: Missing META-INF/MANIFEST.MF")
echo "$SDKLINE" > "$UNSIGNED/android/local.properties"
GH_UNSIGNED="$NS/gh-unsigned.log"; : > "$GH_UNSIGNED"
NIGHTLY_TREE="$UNSIGNED" NIGHTLY_TIP=master NIGHTLY_OUT="$NS/out-unsigned" \
    SELFTEST_GH_LOG="$GH_UNSIGNED" bash "$NIGHTLY" >"$NS/unsigned-build.log" 2>&1
rc=$?
check "THE CHECK: an apk apksigner rejects is never published (exit 11)" [ "$rc" = 11 ]
check "  the refusal and apksigner's own reason both reach the log" \
    bash -c 'find "$1" -name "*.log" | xargs grep -l "PUBLISH REFUSED" | xargs grep -qF "Missing META-INF/MANIFEST.MF"' \
        _ "$NS/out-unsigned"
check "  apksigner was actually run, against the built apk" \
    bash -c 'grep -q "verify .*/out-unsigned/" "$1/calls.log"' _ "$NS/sdk-unsigned"
check "  and gh was never asked to create a release" bash -c '! grep -q "release create" "$1"' _ "$GH_UNSIGNED"

# ------------------------------- 5. a signed apk publishes (the control)
# A refusal is easy to get by refusing always, so a tree whose apksigner
# actually verifies must still publish -- otherwise checks 3 and 4 above
# would be passing by always refusing, not by checking anything.
SIGNED=$(ns_tree signed "9.9.9-selftest")
SDKLINE=$(ns_fakesdk "$NS/sdk-signed" 0 "Verifies")
echo "$SDKLINE" > "$SIGNED/android/local.properties"
GH_SIGNED="$NS/gh-signed.log"; : > "$GH_SIGNED"
NIGHTLY_TREE="$SIGNED" NIGHTLY_TIP=master NIGHTLY_OUT="$NS/out-signed" \
    SELFTEST_GH_LOG="$GH_SIGNED" bash "$NIGHTLY" >"$NS/signed-build.log" 2>&1
rc=$?
check "a signed apk publishes (exit 0), not vacuous against checks 3 and 4" [ "$rc" = 0 ]
check "  apksigner ran against the published apk before gh did" \
    bash -c 'grep -q "verify .*/out-signed/" "$1/calls.log"' _ "$NS/sdk-signed"
check "  and gh WAS asked to create a release" grep -q "release create" "$GH_SIGNED"
