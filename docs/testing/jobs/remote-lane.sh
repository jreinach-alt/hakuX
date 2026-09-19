#!/usr/bin/env bash
#
# WHICH BRANCHES BELONG TO A LANE THIS HOST CANNOT DRIVE.
#
# Sourced, not run:
#
#   . "$(dirname "${BASH_SOURCE[0]}")/remote-lane.sh"
#   remote_map                     # <branch>\t<lane> per line; rc 1 if unreadable
#   remote_lane_of   <branch>      # prints the lane name, or nothing
#   remote_branch_of <lane>        # prints the branch, or nothing
#   is_remote_branch <branch>      # rc 0 when some row names it
#   remote_readable                # rc 0 when the board could be read at all
#
# WHY IT EXISTS. Four jobs tested `lane/*` when what they meant was "a branch a
# lane owns", and the prefix is a proxy that fails on the one real lane that
# does not use it: `lane.remote` is a cloud session on
# `claude/docs-tooling-agentic-coding-u152m1`. It had been contributing for
# days while arms.sh could not see its predictions at all, fleet.py reported it
# as a claim with no agent, and handback.sh called it "whoever owns this
# branch". None of that is about the prefix; it is about nothing recording that
# a lane can live somewhere else.
#
# THE MARKER IS ONE FIELD ON THE TERRITORY ROW, and territory.toml already is
# the list of lanes that every job reads:
#
#   [lane.remote]
#   remote = "claude/docs-tooling-agentic-coding-u152m1"
#
# `remote = true` is accepted too and means the conventional `lane/<row name>`.
# WHY THE VALUE IS THE BRANCH AND NOT JUST `true`: two of the four consumers
# are handed a BRANCH and have to find the lane (handback.sh gets a PR's head;
# fleet.py gets `headRefName`), and a boolean cannot answer that. The two facts
# are not separable anyway -- a lane is remote precisely because it lives on a
# branch this host does not drive -- so making the branch the marker's value
# keeps it one field rather than a `remote` plus a `branch` that can disagree.
#
# THE BOARD IS READ THROUGH board_files.py, so this sees origin/board and not a
# lane worktree's fold-lagged copy (ORCHESTRATION-DESIGN.md §5). HAKUX_TERRITORY
# points it at one file instead; that is the seam the selftest uses, and it is
# an explicit path rather than a mode flag so there is no way to enable it by
# accident.
#
# A READ FAILURE IS NOT "NO REMOTE LANES". Every caller distinguishes them and
# each one fails in its own safe direction, because they are not the same
# direction: lane.sh REFUSES to start (two agents on one branch is the
# expensive accident), fold.sh KEEPS the ref (an un-pruned branch costs
# nothing), fleet.py reports the lane as it did before. A helper that returned
# an empty map on failure would have made all three silently take the "no
# remote lanes" branch, which is this project's own recorded mistake: a guard
# that passes by early-returning on a missing precondition.

_REMOTE_MAP=""; _REMOTE_MAP_RC=""
remote_map() {   # -> "<branch>\t<lane>" per line on stdout; rc 1 if the board could not be read
    if [ -z "$_REMOTE_MAP_RC" ]; then
        local testing
        testing="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
        _REMOTE_MAP=$(python3 - "$testing" <<'PY' 2>/dev/null
import os, sys, tomllib
testing = sys.argv[1]
path = os.environ.get("HAKUX_TERRITORY")
if path:
    with open(path, "rb") as fh:
        t = tomllib.load(fh)
else:
    sys.path.insert(0, testing)
    import board_files
    t = board_files.load("territory.toml")
for lane, meta in sorted((t.get("lane") or {}).items()):
    r = meta.get("remote")
    if not r:
        continue
    # A string IS the branch; `true` means the conventional one. Anything
    # else (a number, a list) is a row nobody can act on -- say nothing
    # rather than guess a branch name to refuse pushes to.
    if r is True:
        print("lane/%s\t%s" % (lane, lane))
    elif isinstance(r, str) and r.strip():
        print("%s\t%s" % (r.strip(), lane))
PY
) && _REMOTE_MAP_RC=0 || { _REMOTE_MAP_RC=1; _REMOTE_MAP=""; }
    fi
    [ -n "$_REMOTE_MAP" ] && printf '%s\n' "$_REMOTE_MAP"
    return "$_REMOTE_MAP_RC"
}

remote_readable() { remote_map >/dev/null; }

remote_lane_of() {   # <branch> -> the lane name, or nothing
    [ -n "${1:-}" ] || return 1
    remote_map | awk -F'\t' -v b="$1" '$1 == b { print $2; found = 1; exit } END { exit !found }'
}

remote_branch_of() {   # <lane> -> the branch, or nothing
    [ -n "${1:-}" ] || return 1
    remote_map | awk -F'\t' -v l="$1" '$2 == l { print $1; found = 1; exit } END { exit !found }'
}

is_remote_branch() { remote_lane_of "${1:-}" >/dev/null; }
