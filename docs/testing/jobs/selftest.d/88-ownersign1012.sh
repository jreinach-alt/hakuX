# Sourced by ../selftest.sh with the harness already built: $T, $HERE,
# $TESTING, $REPO, the shims on PATH, ok/bad/check. Not executable, no
# shebang, no exit -- `fail` is shared and is the run's verdict.
#
# owner_build.sh (#433, measured 2026-10-12): the owner's own stable-channel
# build has the same defect lane.nightlysign1012 found in the nightly --
# `git worktree add` starts the private build tree with no
# android/key.properties (gitignored), so build.gradle.kts's
# hasReleaseKeystore is false, assembleRelease signs with nothing, and the
# unsigned apk used to reach `adb install -r` and fail there (exit 6) --
# indistinguishable from a real device problem. Fixed the same way, for this
# script: key.properties is symlinked into the tree and the built apk is
# verified with apksigner before adb ever sees it.
#
# Driven directly, with no SDK, no gradle and no device: a throwaway git
# repo stands in for $REPO (android/gradlew faked to produce the one
# artifact assembleRelease produces, same shape as nightlysign1012's own
# fixture), and android/local.properties names a fixture build-tools/apksigner.
# The real devices.sh is sourced, not a stand-in: owner_build.sh used to pass
# device_env the label "nova" where it takes a serial, and exited 2 on every
# real run; a fixture device_env that took labels hid that.

echo "== owner_build.sh: key.properties brought in + apksigner verify before adb (#433)"
OS="$T/ownersign"
OWNER_BUILD="$TESTING/owner_build.sh"
rm -rf "$OS"; mkdir -p "$OS/bin"

check "owner_build.sh parses (bash -n)" bash -n "$OWNER_BUILD"

# A keystore file that actually exists, so the storeFile check below prints
# the same shape the owner's real key.properties has today (absolute,
# exists) rather than a fixture-only "missing".
STOREFILE="$OS/fixture-release.jks"; echo fake-keystore > "$STOREFILE"

os_repo() {   # <name> [withkey] -> a fresh git repo at $OS/repo-<name>, android stub
    local name=$1 withkey=${2:-}
    local d="$OS/repo-$name"
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
    echo one > "$d/README.md"
    git -C "$d" add -A
    git -C "$d" commit -q -m base
    # Written AFTER the commit, and never added: the real key.properties is
    # gitignored and untracked, so `git worktree add` never materializes it
    # in $WT on its own -- only owner_build.sh's symlink does. Committing it
    # here would check it into $WT for free and never exercise that code.
    if [ -n "$withkey" ]; then
        cat > "$d/android/key.properties" <<KEYPROPS
storeFile=$STOREFILE
storePassword=x
keyAlias=x
keyPassword=x
KEYPROPS
    fi
    printf '%s' "$d"
}

os_fakesdk() {   # <dir> <exit-code> <stdout-line> -> writes build-tools/9.9.9/apksigner, prints the sdk.dir line
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

# A fake adb: logs every call, answers Success to install so the control leg
# below can actually complete, and is the thing every refusal leg must prove
# was never asked to install.
cat > "$OS/bin/adb" <<'ADB'
#!/usr/bin/env bash
echo "adb $*" >> "${OS_ADB_LOG:?}"
case "$*" in
    *" install "*) echo Success ;;
esac
ADB
chmod +x "$OS/bin/adb"

os_run() {   # <repo> <sdkline-or-empty> <name> -> runs owner_build.sh; $? is its exit code
    local repo=$1 sdkline=$2 name=$3
    [ -n "$sdkline" ] && printf '%s\n' "$sdkline" > "$repo/android/local.properties"
    OS_ADB_LOG="$OS/$name.adb.log"; : > "$OS_ADB_LOG"
    PATH="$OS/bin:$PATH" OS_ADB_LOG="$OS_ADB_LOG" \
        DISPATCH_REPO="$repo" DISPATCH_DIR="$OS/dispatch-$name" \
        OWNER_BUILD_WT="$OS/wt-$name" \
        bash "$OWNER_BUILD" master nova >"$OS/$name.out" 2>"$OS/$name.err"
}

# ------------------------------------------- (a) key.properties present
# THE CHECK: a repo with android/key.properties gets it linked into the
# private worktree, storeFile is read and reported (never its value), and
# the build still completes once apksigner accepts it.
REPO_A=$(os_repo present 1)
SDK_A=$(os_fakesdk "$OS/sdk-present" 0 "Verifies")
os_run "$REPO_A" "$SDK_A" present
rc=$?
check "(a) key.properties present: linked into the tree" \
    bash -c '[ -L "$1/android/key.properties" ] && [ "$(readlink -f "$1/android/key.properties")" = "$(readlink -f "$2/android/key.properties")" ]' \
        _ "$OS/wt-present" "$REPO_A"
check "(a) storeFile is reported absolute and existing, never its value" \
    grep -qF "key.properties storeFile is absolute (exists)" "$OS/present.err"
check "(a) and no password or path from key.properties reaches the log" \
    bash -c '! grep -qF "$2" "$1" && ! grep -q storePassword "$1"' _ "$OS/present.err" "$STOREFILE"
check "(a) the build still completes with it linked (exit 0)" [ "$rc" = 0 ]

# ------------------------------------------- (b) apksigner rejects -> exit 7
# THE CHECK, the defect's other half: an apksigner that reports the real
# failure ("Missing META-INF/MANIFEST.MF") must stop before adb, not just
# fail at install indistinguishably from a device problem.
REPO_B=$(os_repo reject "")
SDK_B=$(os_fakesdk "$OS/sdk-reject" 1 "DOES NOT VERIFY: ERROR: Missing META-INF/MANIFEST.MF")
os_run "$REPO_B" "$SDK_B" reject
rc=$?
check "(b) apksigner rejects the apk -> refuses with the new code (exit 7)" [ "$rc" = 7 ]
check "(b) the refusal names the likely cause" grep -qF "likely cause: no key.properties" "$OS/reject.err"
check "(b) apksigner actually ran against the built apk" \
    grep -qE 'verify .*/app-release\.apk' "$OS/sdk-reject/calls.log"
check "(b) and the fake adb records no install" \
    bash -c '! grep -q install "$1"' _ "$OS/reject.adb.log"

# ------------------------------------------- (c) apksigner missing -> exit 7
# THE CHECK: no sdk.dir (or no build-tools under it) means this cannot
# confirm the apk is signed, so it refuses rather than install on faith.
REPO_C=$(os_repo missing "")
os_run "$REPO_C" "" missing
rc=$?
check "(c) no apksigner locatable -> refuses (exit 7)" [ "$rc" = 7 ]
check "(c) and says why" grep -qF "no apksigner under" "$OS/missing.err"
check "(c) and the fake adb records no install" \
    bash -c '! grep -q install "$1"' _ "$OS/missing.adb.log"

# --------------------------- (d) a signed apk installs (the control)
# A refusal is easy to get by refusing always, so a tree whose apksigner
# actually verifies must still install -- otherwise (b) and (c) above would
# be passing by always refusing, not by checking anything.
REPO_D=$(os_repo accept 1)
SDK_D=$(os_fakesdk "$OS/sdk-accept" 0 "Verifies")
os_run "$REPO_D" "$SDK_D" accept
rc=$?
check "(d) a signed apk installs (exit 0), not vacuous against (b) and (c)" [ "$rc" = 0 ]
check "(d) apksigner ran before adb" grep -qE 'verify .*/app-release\.apk' "$OS/sdk-accept/calls.log"
check "(d) and the fake adb WAS asked to install" grep -q install "$OS/accept.adb.log"
check "(d) on the Nova's serial: the label nova reaches devices.sh as ee317437" \
    grep -qE '^adb -s ee317437 install ' "$OS/accept.adb.log"
check "(d) the stamped version was printed" [ -s "$OS/accept.out" ]
