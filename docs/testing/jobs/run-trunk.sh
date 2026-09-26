#!/usr/bin/env bash
#
# Run a job out of the fetched trunk, never out of the owner's checkout.
#
#   run-trunk.sh <job>        e.g. run-trunk.sh arms
#
# The systemd units name /home/justin/hakuX, which is whatever branch the
# owner last checked out there; the first evening it sat 8 commits behind
# master and three ticks ran stale code. So every unit runs THIS launcher,
# which keeps a private detached worktree of origin/master in
# $WORK/jobs-wt and execs the job from it. The board job has its own
# worktree (board-wt) because a model session works inside it; the script
# jobs share this one, and they only read from it.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
TIP="${HAKUX_TIP:-master}"
WT="$WORK/jobs-wt"
job="${1:?job name}"
mkdir -p "$WORK/logs/$job"
if [ ! -e "$WT/.git" ]; then
    git -C "$REPO" fetch -q origin "$TIP" && git -C "$REPO" worktree add --quiet --detach "$WT" FETCH_HEAD \
        || { echo "run-trunk: cannot create $WT; running the owner's checkout copy" >&2; exec bash "$REPO/docs/testing/jobs/$job.sh" "${@:2}"; }
fi
# Serialised: two timers can fire in the same minute, and a checkout under
# a running job is the failure the private worktree exists to prevent.
exec flock "$WT/../.jobs-wt.lock" bash -c '
    git -C "$1" fetch -q origin "$2" && git -C "$1" checkout -q --detach FETCH_HEAD
    exec bash "$1/docs/testing/jobs/$3.sh" "${@:4}"' _ "$WT" "$TIP" "$job" "${@:2}"
