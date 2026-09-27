#!/usr/bin/env bash
# Render the LIVE page from a lane, without touching the host's status dir:
# status.sh --print into <out dir>, the board read from this worktree's
# fetched origin/board, the plug meter taken from the host's cache (so this
# render never polls the plug).
#
#   live_print.sh <out dir>
set -u
F=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TOP=$(git -C "$F" rev-parse --show-toplevel)
mkdir -p "$1"; O=$(cd "$1" && pwd)
git -C "$TOP" fetch -q origin board master 2>/dev/null
W=${HAKUX_WORK:-/home/justin/hakux-work}
[ -f "$W/status/console-meter" ] && cat "$W/status/console-meter" > "$O/console-meter"   # fresh mtime: no plug read
STATUS_OUT_DIR="$O" HAKUX_REPO_DIR="$TOP" timeout 500 bash "$TOP/docs/testing/jobs/status.sh" --print > "$O/print.txt" 2> "$O/err.txt"
echo "status.sh --print rc=$?"
tail -3 "$O/err.txt" "$O/lanes.err" 2>/dev/null
