#!/usr/bin/env bash
# board_filter against the REAL tracker (origin/board via board_files), with a
# gh-shaped list of real issue numbers, then with board_files unreachable.
set -u
JOBS="$(cd "$(dirname "$0")/../../testing/jobs" && pwd)"
eval "$(sed -n '/^board_filter() {/,/^}/p' "$JOBS/board.sh")"
J='[{"number":10,"title":"t10","labels":[]},{"number":13,"title":"t13","labels":[]},
{"number":77,"title":"t77","labels":[]},{"number":266,"title":"t266","labels":[]},
{"number":224,"title":"t224","labels":[]},{"number":31,"title":"t31","labels":[]},
{"number":4,"title":"t4","labels":[]},{"number":99999,"title":"none","labels":[]}]'
echo "== real tracker"
SELF="$JOBS"; board_filter issues "$J"
echo "== board_files unreachable"
SELF=/nonexistent/jobs; board_filter issues "$J"
