#!/usr/bin/env bash
# Extract the pre-change renderer (docs/testing at the lane's base) into <dir>,
# so run_fixture.sh can render the same fixture with it.
#
#   old_renderer.sh <dir> [base sha]      -> <dir>/docs/testing/jobs/status.sh
set -eu
dir=$1; base=${2:-916c246260}
rm -rf "$dir"; mkdir -p "$dir"
git -C "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)" archive "$base" docs/testing/jobs docs/testing/affinity.py | tar -x -C "$dir"
