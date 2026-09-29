#!/usr/bin/env bash
#
# WHICH BRANCHES BELONG TO A LANE THIS HOST CANNOT DRIVE.
#
# Sourced, not run:
#
#   . "$(dirname "${BASH_SOURCE[0]}")/remote-lane.sh"
#   remote_map                     # <branch>\t<lane> per line; rc 0 board, 2 working tree, 1 unreadable
#   remote_lane_of   <branch>      # prints the lane name, or nothing; <branch> may be suffixed
#   remote_lanes_of  < heads       # "<head>\t<lane>" for each head on stdin a remote lane owns
#   remote_branch_of <lane>        # prints the branch, or nothing (the row's own, unsuffixed)
#   is_remote_branch <branch>      # rc 0 when some remote lane owns it
#   remote_source                  # prints board | worktree | unreadable
#   remote_authoritative           # rc 0 ONLY when the map came from the board
#   remote_readable                # rc 0 when SOMETHING parsed -- see the warning below
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
# AND A REMOTE LANE OPENS EACH PR ON A SUFFIXED BRANCH, `<remote>-<suffix>`,
# exactly as a local lane's second PR goes on `lane/<name>-<suffix>`. Audit
# files are named by branch, so a lane that reuses one name collides with its
# own earlier audits; #578's pair did, and both passes said to stop. Asking
# only "is this head the row's value?" filed every such PR under nobody, and
# fold.sh's index-conflict repair would have pushed a merge onto a branch that
# a session elsewhere pushes to.
# So a head is a remote lane's when it EQUALS the row's value or, failing that,
# STARTS WITH `<value>-`, and the longest match wins -- branch_lane() in
# fleet.py, stated for remote rows. The longest match is taken over EVERY
# row's branch, local ones included (`lane/<row name>`): a `remote = true`
# row `foo` must not claim `lane/foo-bar` from a local lane called `foo-bar`,
# since that is the other lane's own branch or its suffixed one. fleet.py's
# remote_lane_of() is the same rule, and 98-lane-shape.sh runs one table of
# heads through both.
#
# THE BOARD IS READ THROUGH board_files.py, so this sees origin/board and not a
# lane worktree's fold-lagged copy (ORCHESTRATION-DESIGN.md §5). HAKUX_TERRITORY
# points it at one file instead; that is the seam the selftest uses, and it is
# an explicit path rather than a mode flag so there is no way to enable it by
# accident.
#
# ...EXCEPT THAT board_files.load HAS A THIRD OUTCOME, AND THE FIRST VERSION OF
# THIS FILE REPORTED IT AS THE FIRST. When `git show origin/board:territory.toml`
# fails -- the ref not fetched, a CI checkout or a fresh clone that has only
# origin/master, a timeout -- load() falls back to the IN-TREE copy and returns
# it successfully. That copy is not incidentally stale, it is STRUCTURALLY
# stale: it reaches the tree only when some later fold copies it, so on
# 2026-09-19 it was 31 waves and a day behind, and it is exactly the copy
# guaranteed NOT to carry a `remote` marker the board has just written. Read
# through the old `remote_readable`, that state was indistinguishable from a
# clean board read -- so all three guards below would have passed on a map
# missing the one row they exist for, in the same direction, at the same time.
#
# So there are THREE outcomes, `remote_source` names them, and a caller
# deciding a SAFETY question must ask `remote_authoritative`, never
# `remote_readable`:
#
#   board       from origin/board (or a path given explicitly by
#               HAKUX_TERRITORY, or a host that has deliberately switched the
#               board ref off with HAKUX_BOARD_REF= -- in both of those the
#               file named IS the board, by configuration and not by accident)
#   worktree    the ref was configured and could not be read, so this is the
#               fold-lagged in-tree copy. The rows in it are still TRUE -- the
#               unsafe direction is only ABSENCE, a marker the board has since
#               added -- so the map is still worth having. It just cannot
#               settle "this branch belongs to nobody".
#   unreadable  nothing parsed.
#
# `remote_readable` answers only "did something parse" and remains for a
# caller that merely reports; it is not a permission.
#
# A READ FAILURE IS NOT "NO REMOTE LANES". Every caller distinguishes them and
# each one fails in its own safe direction, because they are not the same
# direction: lane.sh REFUSES to start (two agents on one branch is the
# expensive accident), fold.sh KEEPS the ref (an un-pruned branch costs
# nothing), fleet.py reports the lane as it did before. A helper that returned
# an empty map on failure would have made all three silently take the "no
# remote lanes" branch, which is this project's own recorded mistake: a guard
# that passes by early-returning on a missing precondition.
#
# A `worktree` READ IS CURABLE, AND THE REFUSALS SAY SO: `git fetch origin
# board` in the checkout the job runs from. That is why the safe direction is
# affordable here -- the cost of being wrong is one fetch, and the cost of the
# other direction is a deleted cloud branch or a second agent on one.

_REMOTE_MAP=""; _REMOTE_MAP_RC=""; _REMOTE_SRC=""; _REMOTE_LOCAL=""
remote_map() {   # -> "<branch>\t<lane>" per line on stdout; rc 0 board, 2 working tree, 1 unreadable
    if [ -z "$_REMOTE_MAP_RC" ]; then
        local testing out
        testing="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
        # LINE ONE IS `src=<where>`, and it is not optional: a map with no
        # source line is a map from a reader that does not know where it read,
        # which is the state this whole file exists to make impossible. The
        # shell below treats a missing or unrecognised source as unreadable.
        out=$(python3 - "$testing" <<'PY' 2>/dev/null
import os, sys, tomllib
testing = sys.argv[1]
path = os.environ.get("HAKUX_TERRITORY")
if path:
    # An explicitly named file IS the board for this process. Nothing fell
    # back to it; somebody pointed here on purpose.
    with open(path, "rb") as fh:
        t = tomllib.load(fh)
    src = "board"
else:
    sys.path.insert(0, testing)
    import board_files
    t = board_files.load("territory.toml")
    if board_files.source("territory.toml") != "working tree":
        src = "board"
    elif not board_files.REF:
        # The board ref is switched OFF by configuration (HAKUX_BOARD_REF=),
        # so the in-tree file is not a fallback, it is the board. A host that
        # has made that choice must not have every lane refused at it.
        src = "board"
    else:
        # The ref was configured and could not be read. This copy reaches the
        # tree only via a fold, so it is exactly the one that will be missing
        # a marker the board has just written.
        src = "worktree"
print("src=%s" % src)
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
# Every LOCAL row's branch too, with a third field, for remote_lane_of's
# longest match alone. remote_map does not print these: its callers asked for
# remote lanes and get exactly those.
for lane, meta in sorted((t.get("lane") or {}).items()):
    if not meta.get("remote"):
        print("lane/%s\t%s\tlocal" % (lane, lane))
PY
)      && case "$(printf '%s\n' "$out" | head -1)" in
               src=board)    _REMOTE_SRC=board;    _REMOTE_MAP_RC=0 ;;
               src=worktree) _REMOTE_SRC=worktree; _REMOTE_MAP_RC=2 ;;
               *)            _REMOTE_SRC=unreadable; _REMOTE_MAP_RC=1 ;;
           esac \
        || { _REMOTE_SRC=unreadable; _REMOTE_MAP_RC=1; }
        if [ "$_REMOTE_MAP_RC" = 1 ]; then
            _REMOTE_MAP=""; _REMOTE_LOCAL=""
        else
            _REMOTE_MAP=$(printf '%s\n' "$out" | tail -n +2 | awk -F'\t' 'NF == 2')
            _REMOTE_LOCAL=$(printf '%s\n' "$out" | tail -n +2 | awk -F'\t' 'NF == 3 && $3 == "local"')
        fi
    fi
    [ -n "$_REMOTE_MAP" ] && printf '%s\n' "$_REMOTE_MAP"
    return "$_REMOTE_MAP_RC"
}

remote_source() {   # -> board | worktree | unreadable
    remote_map >/dev/null
    printf '%s' "$_REMOTE_SRC"
}

# THE PREDICATE A GUARD ASKS. rc 0 only when the map came from the board, so a
# fold-lagged in-tree copy cannot answer "no row names this branch".
remote_authoritative() { remote_map >/dev/null; [ "$_REMOTE_MAP_RC" = 0 ]; }

# NOT A PERMISSION. rc 0 when anything parsed, including the stale copy. Use it
# to report, never to decide whether a branch is safe to delete or to start on.
remote_readable() { remote_map >/dev/null; [ "$_REMOTE_MAP_RC" != 1 ]; }

# THE SUFFIX RULE (see the header), ONCE, for both functions below. The bases
# come in through the environment -- remote rows "<branch>\t<lane>" first,
# then local rows with a third field -- and the heads on stdin, one per line.
# It prints "<head>\t<lane>" for each head a REMOTE lane owns. Remote rows are
# listed first and the match is strict, so where a remote and a local row
# somehow name the same branch the answer is the remote lane: the direction in
# which every caller refuses to act.
_REMOTE_RULE='
BEGIN {
    k = split(ENVIRON["_REMOTE_BASES"], line, "\n")
    for (j = 1; j <= k; j++) {
        m = split(line[j], f, "\t")
        if (m >= 2 && f[1] != "") { n++; B[n] = f[1]; L[n] = f[2]; R[n] = (m == 2) }
    }
}
$0 == "" { next }
{
    h = $0; own = 0; bl = 0
    for (i = 1; i <= n; i++) if (B[i] == h) { own = i; break }
    if (!own) for (i = 1; i <= n; i++)
        if (index(h, B[i] "-") == 1 && length(B[i]) > bl) { bl = length(B[i]); own = i }
    if (own && R[own]) print h "\t" L[own]
}'
_remote_owner() {   # heads on stdin -> "<head>\t<lane>"; remote_map must have run in this shell
    _REMOTE_BASES=$(printf '%s\n%s' "$_REMOTE_MAP" "$_REMOTE_LOCAL") awk "$_REMOTE_RULE"
}

# Both in a SUBSHELL, so the read stays out of the caller's cache, as it did
# when this was `remote_map | awk`. A caller that has already read the map
# (every gate asks remote_authoritative first) hands its cache down and pays
# for no second read.
remote_lane_of() {   # <branch> -> the lane name, or nothing
    [ -n "${1:-}" ] || return 1
    ( remote_map >/dev/null; printf '%s\n' "$1" | _remote_owner ) \
        | awk -F'\t' 'NR == 1 { print $2; found = 1 } END { exit !found }'
}

# THE SAME RULE FOR MANY HEADS, ON ONE BOARD READ. The sweeps ask about every
# open PR's head at once; remote_lane_of per head would be a read per head.
remote_lanes_of() {   # heads on stdin -> "<head>\t<lane>" for each head a remote lane owns
    ( remote_map >/dev/null; _remote_owner )
}

remote_branch_of() {   # <lane> -> the branch, or nothing
    [ -n "${1:-}" ] || return 1
    remote_map | awk -F'\t' -v l="$1" '$2 == l { print $1; found = 1; exit } END { exit !found }'
}

is_remote_branch() { remote_lane_of "${1:-}" >/dev/null; }
