#!/usr/bin/env bash
# Render the fixture with a given jobs dir and print every check's verdict.
#
#   proof.sh <jobs dir holding status.sh> <out dir>
#
# NOTES.md's "Proof" runs it twice: master's jobs dir (every check FAILs) and
# this branch's (every check PASSes).
set -u
HERE_P=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE_P/../../../.." && pwd)
bash "$HERE_P/render.sh" "$1" "$2" "$REPO" > /dev/null 2>&1
echo "render exit $?"
for c in glance order bar chart json copied; do
    python3 "$HERE_P/assert_measured.py" "$2" "$c"
done
