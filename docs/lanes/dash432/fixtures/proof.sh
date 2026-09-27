#!/usr/bin/env bash
# Render the fixture with both renderers, assert the objective on each, and
# (when CHROME names a headless browser) shoot both at phone width.
#
#   proof.sh <scratch dir>
set -u
F=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$1"; S=$(cd "$1" && pwd)
bash "$F/both.sh" "$S" | grep 'rc='
for o in old new; do
    echo "== the $o renderer"
    python3 "$F/assert_objective.py" "$S/out-$o"
    [ -n "${CHROME:-}" ] && bash "$F/shoot.sh" "$S/out-$o/index.html" "$S/shots/$o-1624.png" 400 "${SHOT_H:-2600}" > /dev/null
done
exit 0
