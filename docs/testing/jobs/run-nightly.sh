#!/usr/bin/env bash
#
# Run the nightly out of the fetched trunk, never out of the owner's checkout.
#
#   run-nightly.sh            what hakux-nightly.service ExecStarts
#
# This is run-trunk.sh's argument applied to the one job that was never
# converted. hakux-nightly.service named /home/justin/hakuX -- whatever branch
# the owner last checked out there -- so on 2026-09-20 and 2026-09-21 the
# nightly built 20e4708d50, a 09-19 commit, twice, and published both under a
# current date with an APK attached. origin/master was 152 commits ahead.
#
# WHY NOT JUST `run-trunk.sh nightly`. That launcher shares ONE worktree,
# $WORK/jobs-wt, across arms/fold/status/cloud/pr-sweep/issue-sweep, and
# serialises the whole job under flock on .jobs-wt.lock. Those jobs are
# seconds of `gh` and `git`. The nightly is `./gradlew assembleRelease` --
# minutes, sometimes tens of them -- and holding that lock for the length of
# an Android build would park the fold job, the arms dispatcher and both
# sweeps behind it at 00:30 every night. Sharing the worktree is worse still:
# those jobs check out FETCH_HEAD on entry, which would move the tree under a
# running compile. So the nightly gets its own worktree and its own lock, and
# the two families never wait on each other.
#
# WHAT THIS DOES NOT GUARANTEE. Only that the tree is at the tip when the
# script STARTS. nightly_build.sh fetches and compares again itself, and
# refuses to publish anything that is not the trunk -- because this file is
# the launcher and the launcher is, by construction, the stale copy (systemd
# ExecStarts it by absolute path out of the owner's checkout, exactly as it
# does run-trunk.sh). A guarantee that lives only here is a guarantee that
# lives in the file nobody updates.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
TIP="${HAKUX_TIP:-master}"
WT="${NIGHTLY_WT:-$WORK/nightly-wt}"
LOCK="$WORK/.nightly-wt.lock"
mkdir -p "$WORK"

if [ ! -e "$WT/.git" ]; then
    git -C "$REPO" fetch -q origin "$TIP" \
        && git -C "$REPO" worktree add --quiet --detach "$WT" FETCH_HEAD \
        || { echo "run-nightly: cannot create $WT" >&2; exit 1; }
fi

# -n, not a blocking wait. Two nightlies are not worth queueing: the second
# would build the same tip half an hour later and race the first for the tag.
# -E 75 so a lock conflict is distinguishable from the job's own exit 1 --
# without it "skipped, already running" and "failed" are the same number.
flock -n -E 75 "$LOCK" bash -c '
    WT=$1; TIP=$2; REPO=$3; shift 3
    # A failed fetch is NOT fatal here. The worktree still holds the last tip
    # we had, and nightly_build.sh is the thing that decides what an
    # unreachable origin means -- it labels the release rather than silently
    # publishing as if it were current. Swallowing the night entirely at this
    # layer would turn a reachability blip into a missing nightly.
    #
    # Resolved to a sha before the checkout, not used as the name FETCH_HEAD:
    # that file lives in the COMMON git dir, so run-trunk.sh fetching for the
    # fold job in the same second would rewrite it between these two lines.
    if git -C "$REPO" fetch -q origin "$TIP" && TRUNK=$(git -C "$REPO" rev-parse FETCH_HEAD); then
        git -C "$WT" checkout -q --detach "$TRUNK" \
            || echo "run-nightly: checkout of $TRUNK failed; nightly_build.sh will see the tree is behind and refuse" >&2
    else
        echo "run-nightly: fetch of origin/$TIP failed; nightly_build.sh will label the release" >&2
    fi
    exec env NIGHTLY_TREE="$WT" NIGHTLY_TIP="$TIP" \
        bash "$WT/docs/testing/nightly_build.sh" "$@"
  ' _ "$WT" "$TIP" "$REPO" "$@"
rc=$?
# 75 is propagated, not swallowed: the unit carries SuccessExitStatus=75, the
# same convention hakux-fold.service already uses for "nothing to do".
[ "$rc" = 75 ] && echo "run-nightly: another nightly holds $LOCK; skipping this tick" >&2
exit "$rc"
