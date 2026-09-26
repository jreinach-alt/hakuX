#!/usr/bin/env bash
# The falsification run: the release fragment against the OLD tools, in a
# scratch worktree at the ref given (default origin/master). Nothing in this
# tree is swapped. Also prints what each old tool actually said, so a red
# can be read as "the old code has no such rule" and not as a path or import
# error.
#
#   falsify-release.sh [ref]
set -u
LANE="$(cd "$(dirname "$0")" && pwd)"
REF="${1:-origin/master}"
W="$LANE/.scratch-old"
git -C "$LANE" worktree add -q --detach "$W" "$REF" || exit 2
trap 'git -C "$LANE" worktree remove --force "$W"' EXIT
echo "old tools at $(git -C "$W" log --oneline -1)"
bash "$LANE/run-release.sh" "$W/docs/testing" | tail -25
D="$W/docs/testing"
printf 'wave = 1000000\n[lane.done]\nfiles = ["hw/a.c"]\nreleased = ["hw/a.c"]\n[lane.next]\nfiles = ["hw/a.c"]\n' > "$D/territory.toml"
echo "-- old check_territory.py on a released overlap:"
( cd "$D" && HAKUX_BOARD_REF= python3 check_territory.py 2>&1 | grep -v '^NOTE'; echo "exit=${PIPESTATUS[0]}" )
echo "-- old board.sh: has a released mode?"
# Grep, never run: an old board.sh ignores the argument and runs a whole tick
# (it did, once, from this script -- see NOTES.md).
grep -c '"${1:-}" = "released"' "$D/jobs/board.sh"
echo "-- old fleet.py has no release or fold-watch section:"
grep -c 'RELEASED AT READY\|FOLD-READY, NOT FOLDING' "$D/fleet.py"
