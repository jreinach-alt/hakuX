#!/usr/bin/env bash
# Render the 16:24 fixture with the pre-change renderer and with this tree's.
#
#   both.sh <scratch dir>     -> <scratch>/out-old/, <scratch>/out-new/
set -u
mkdir -p "$1"; S=$(cd "$1" && pwd)
F=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TOP=$(git -C "$F" rev-parse --show-toplevel)
mkdir -p "$S"
bash "$F/old_renderer.sh" "$S/old"
FIXTURE_REPO="$TOP" bash "$F/run_fixture.sh" "$S/old/docs/testing/jobs" "$S/out-old"; echo "old renderer rc=$?"
FIXTURE_REPO="$TOP" bash "$F/run_fixture.sh" "$TOP/docs/testing/jobs" "$S/out-new"; echo "new renderer rc=$?"
for o in out-old out-new; do
    echo "== $o stderr:"; head -5 "$S/$o/stderr.txt"
    [ -s "$S/$o/work/status/status_html.err" ] && { echo "== $o status_html.err:"; tail -5 "$S/$o/work/status/status_html.err"; }
done
