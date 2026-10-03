#!/usr/bin/env bash
#
# The one place the app's versionName string is computed, so the Gradle
# build, owner_build.sh and this file's own selftest fixture all agree on it.
#
#   version_stamp.sh [TREE] [VARIANT]
#     TREE     a git worktree checked out at the commit being built.
#              Defaults to "." -- NEVER to this script's own location, because
#              the dispatcher's build runs this against a PRIVATE detached
#              worktree (BUILD_TREE) and must stamp THAT commit, not whatever
#              lives in the shared checkout this copy was snapshotted from.
#     VARIANT  "perflog" for a `-Pperflog=true` diagnostic build, or empty.
#
# Prints <base>-<MMDD>-<shortsha>[-<variant>][-dirty] on stdout, e.g.
#   0.4.1-1002-59a4b42
#   0.4.1-1002-59a4b42-perflog
#   0.4.1-1002-59a4b42-dirty
#
# MMDD and the sha are both read from the commit at HEAD, not from the day
# the build happens to run: the point of the stamp is "which commit is this",
# so the same commit built on two different days must print the same string.
# "-dirty" is the one piece that is NOT about the commit -- it says the
# checkout no longer matches it, same test `nightly_build.sh` runs before it
# will publish (tracked modifications only; an untracked file is not "dirty").
set -u

BASE_VERSION="0.4.1"

TREE="${1:-.}"
VARIANT="${2:-}"

cd "$TREE" 2>/dev/null || { echo "version_stamp.sh: no tree at $TREE" >&2; exit 1; }
SHA=$(git rev-parse --short HEAD 2>/dev/null) || {
    echo "version_stamp.sh: $TREE is not a git checkout" >&2; exit 1; }
MMDD=$(git log -1 --format=%cd --date=format:%m%d HEAD 2>/dev/null)
[ -n "$MMDD" ] || MMDD="0000"

VER="$BASE_VERSION-$MMDD-$SHA"
case "$VARIANT" in
    ""|none) ;;
    *) VER="$VER-$VARIANT" ;;
esac

DIRTY=$(git status --porcelain | grep -v '^??' | wc -l)
[ "$DIRTY" -gt 0 ] && VER="$VER-dirty"

echo "$VER"
