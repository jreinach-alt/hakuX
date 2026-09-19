#!/usr/bin/env bash
#
# The owner's one-time host step for Phase 0. Idempotent; run it again after
# any change to the units in docs/testing/systemd or docs/testing/*.timer.
#
#   docs/testing/jobs/install-host.sh
#
# It installs the user units, enables the board timer and the dispatcher
# service, creates the work directories, and retires the orchestrator claim
# the old Stop hook keyed on. It does not start a lane and does not touch
# the devices or the holds.
set -u
REPO="${HAKUX_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
UNITS="$HOME/.config/systemd/user"
mkdir -p "$UNITS" "$WORK"/{wt,briefs,predictions,attempts,arms,fold,status,logs/board,logs/lane,logs/arms,logs/fold,logs/status,logs/cloud,dispatch/logs}
# The arms job runs predictions registered after this watermark; history
# stays history. Move it back (ISO-8601 UTC) to re-run older ones.
[ -f "$WORK/arms/since" ] || date -u +%FT%TZ > "$WORK/arms/since"

for u in "$REPO"/docs/testing/systemd/*.service "$REPO"/docs/testing/systemd/*.timer \
         "$REPO"/docs/testing/hakux-comments.service "$REPO"/docs/testing/hakux-comments.timer \
         "$REPO"/docs/testing/hakux-dx.service "$REPO"/docs/testing/hakux-dx.timer; do
    [ -f "$u" ] && cp -f "$u" "$UNITS/" && echo "installed $(basename "$u")"
done
systemctl --user daemon-reload
loginctl enable-linger "$USER" 2>/dev/null || echo "note: enable-linger needs a password; run: sudo loginctl enable-linger $USER"
systemctl --user enable --now hakux-board.timer hakux-arms.timer hakux-fold.timer hakux-status.timer hakux-cloud.timer hakux-nightly.timer hakux-comments.timer hakux-dx.timer
systemctl --user enable --now hakux-dispatcher.service

# The labels every job reads and writes; gh silently no-ops on a missing one.
bash "$REPO/docs/testing/jobs/ensure-labels.sh"

# The old backlog gate keyed on this claim; with no orchestrator session it
# must not exist.
rm -f /tmp/hakux-backlog-gate/orchestrator && echo "orchestrator claim removed"

echo
systemctl --user list-timers 'hakux-*' --no-pager
systemctl --user status hakux-dispatcher.service --no-pager | head -5
echo
echo "next: the board timer's first tick runs in 3 minutes; the status roll-up is $WORK/status/STATUS.md and the comment on the harness-status issue"
