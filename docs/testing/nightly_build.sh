#!/usr/bin/env bash
#
# Nightly build and publish. 00:30 America/Los_Angeles.
#
# A build needs no device, so this never contends with the dispatcher's queue.
# It deliberately does NOT run tests: a nightly that grabbed the Nova at half
# past midnight would collide with an overnight sweep, and running belongs to
# the dispatcher.
#
# It reports either way. A silent failure is worse than no nightly at all,
# because a missing release looks like a day with no work.
set -u

REPO="${NIGHTLY_REPO:-jreinach-alt/hakuX}"
TREE="${NIGHTLY_TREE:-/home/justin/hakuX}"
OUT="${NIGHTLY_OUT:-/home/justin/hakux-work/nightly}"
export JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}"
export PATH="/home/justin/Android/Sdk/cmake/3.30.3/bin:$PATH"

mkdir -p "$OUT"
DAY=$(date +%Y-%m-%d)
LOG="$OUT/$DAY.log"
say() { echo "$(date '+%H:%M:%S') $*" | tee -a "$LOG"; }

cd "$TREE" || { echo "no tree at $TREE"; exit 1; }
BRANCH=$(git rev-parse --abbrev-ref HEAD)
SHA=$(git rev-parse --short HEAD)
say "nightly $DAY  branch=$BRANCH  head=$SHA"

# Reproducibility: say plainly whether this sha exists on the remote. A
# release built from an unpushed HEAD cannot be rebuilt by anyone else, so it
# is labelled rather than quietly published as if it could.
UNPUSHED=$(git log --oneline "origin/$BRANCH..HEAD" 2>/dev/null | wc -l)
if [ "$UNPUSHED" -gt 0 ]; then
    say "WARNING: $UNPUSHED commit(s) not on origin; the release will say so"
    PROV="built from **unpushed** \`$SHA\` on \`$BRANCH\` ($UNPUSHED commits ahead of origin)"
else
    PROV="built from \`$SHA\` on \`$BRANCH\`"
fi

DIRTY=$(git status --porcelain | grep -v '^??' | wc -l)
[ "$DIRTY" -gt 0 ] && say "WARNING: $DIRTY tracked file(s) modified; build is not the commit"

# The day's work, for the notes. Subjects only -- bodies are long here.
SINCE=$(date -d 'yesterday 00:30' -Iseconds 2>/dev/null || date -v-1d -Iseconds)
TOTAL=$(git log --since="$SINCE" --oneline | wc -l)
mapfile -t SUBJECTS < <(git log --since="$SINCE" --format='- %s' | head -40)
say "$TOTAL commit(s) since $SINCE, listing ${#SUBJECTS[@]}"

say "building release"
if ! (cd android && ./gradlew assembleRelease) >>"$LOG" 2>&1; then
    say "BUILD FAILED -- see $LOG"
    exit 2
fi

APK=$(find android/app/build/outputs/apk/release -name '*.apk' | head -1)
[ -n "$APK" ] || { say "no APK produced"; exit 3; }
VER=$(grep -oP 'versionName = "\K[^"]+' android/app/build.gradle.kts | head -1)
NAME="hakuX-${VER}-nightly-${DAY}-${SHA}.apk"
cp "$APK" "$OUT/$NAME"
say "built $NAME ($(du -h "$OUT/$NAME" | cut -f1)), sha256 $(sha256sum "$OUT/$NAME" | cut -c1-16)"

TAG="nightly-$DAY"
BODY="$OUT/$DAY.notes.md"
{
    echo "Automated nightly. $PROV."
    echo
    [ "$DIRTY" -gt 0 ] && echo "> Built with $DIRTY modified tracked file(s): the binary is not exactly this commit."
    echo
    if [ "${#SUBJECTS[@]}" -gt 0 ]; then
        echo "### The day's work"; echo
        printf '%s\n' "${SUBJECTS[@]}"
        [ "$TOTAL" -gt "${#SUBJECTS[@]}" ] && { echo; echo "_…and $((TOTAL - ${#SUBJECTS[@]})) more commits._"; }
    else
        echo "No commits in the last day."
    fi
    echo
    echo "Installs alongside an official hakuX build and upgrades a previous fork build in place."
    echo "Launching from ES-DE needs the two files in \`docs/es-de/\`."
} > "$BODY"

if gh release create "$TAG" "$OUT/$NAME" --repo "$REPO" --prerelease \
        --title "hakuX nightly $DAY ($SHA)" --notes-file "$BODY" >>"$LOG" 2>&1; then
    say "published $TAG"
else
    say "release create failed; retrying as an upload to an existing tag"
    gh release upload "$TAG" "$OUT/$NAME" --repo "$REPO" --clobber >>"$LOG" 2>&1 \
        && say "uploaded to existing $TAG" || { say "PUBLISH FAILED"; exit 4; }
fi
say "done"
