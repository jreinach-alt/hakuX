#!/usr/bin/env bash
#
# board-push-gate.sh [--rev <commit>] <boardtree>
#
# Would this board pass the board gates? Runs check_territory.py and
# check_coverage.py, from a scratch worktree of origin/master, against the two
# board files from <boardtree> -- its working tree, or with --rev the files as
# committed at <commit> (which is what a pre-push hook is asked about: the
# commit being pushed, not whatever is on disk beside it).
#
# Exit 0 only if both checkers exit 0. Otherwise print every FAIL line with
# the rows under it, and exit 1.
#
# WHY IT EXISTS. The board job's model session edits the two files in
# .boardtree and pushes `board` itself, and nothing checked the push. On
# 2026-09-26 it pushed a board that failed these very checkers twice: blockers
# naming retired lanes (check_territory), and at 14:31Z dispatch_state="done"
# on five OPEN issues, #31 #223 #262 #266 #287 (check_coverage). A red
# origin/board is red preflight for EVERY lane, because every lane reads the
# board from there, and no lane may edit it. One bad tick jams the harness.
# board.sh installs this as .boardtree's pre-push hook (install-hook below),
# so the refusal does not depend on the session reading its role file right.
#
# FAILS CLOSED. A missing file, an unresolvable base, a checker that crashes
# -- every one of them refuses. The ONE fail-open is check_coverage.py's own:
# with no gh or no network it prints `coverage NOT CHECKED` and exits 0, on
# purpose, so a blip cannot make the repository unpushable. This gate keeps
# that and says so in a NOTE line rather than printing `ok` over it.
#
# NO SIDE EFFECTS on the boardtree: the scratch worktree is detached, lives in
# $TMPDIR, and is removed (and pruned) on the way out.
set -u
rev=""
if [ "${1:-}" = "--rev" ]; then rev="${2:-}"; shift 2 || true; fi
BT="${1:-}"
say() { echo "board-push-gate: $*"; }
refuse() { say "REFUSED: $*"; exit 1; }

[ -n "$BT" ] || refuse "usage: board-push-gate.sh [--rev <commit>] <boardtree>"
git -C "$BT" rev-parse --git-dir >/dev/null 2>&1 || refuse "$BT is not a git tree"
BASE="${HAKUX_GATE_BASE:-origin/master}"
base_sha=$(git -C "$BT" rev-parse --verify -q "$BASE^{commit}") \
    || refuse "cannot resolve $BASE, so there is no checker to run (failing closed)"

tmp=$(mktemp -d "${TMPDIR:-/tmp}/board-push-gate.XXXXXX") || refuse "no scratch dir"
S="$tmp/wt"
cleanup() {
    git -C "$BT" worktree remove --force "$S" >/dev/null 2>&1
    rm -rf "$tmp"
    git -C "$BT" worktree prune >/dev/null 2>&1
}
trap cleanup EXIT
# --no-checkout, then only docs/testing: the checkers need their directory and
# a git repository around it (check_territory walks territory.toml's history),
# not 15,000 files of emulator.
git -C "$BT" worktree add -q --detach --no-checkout "$S" "$base_sha" >/dev/null 2>&1 \
    || refuse "cannot add a scratch worktree of $BASE (failing closed)"
git -C "$S" checkout -q "$base_sha" -- docs/testing 2>/dev/null \
    || refuse "cannot check out docs/testing from $BASE (failing closed)"
[ -f "$S/docs/testing/check_territory.py" ] && [ -f "$S/docs/testing/check_coverage.py" ] \
    || refuse "$BASE carries no check_territory.py / check_coverage.py (failing closed)"

for f in territory.toml nv2a_issues.toml; do
    if [ -n "$rev" ]; then
        git -C "$BT" show "$rev:$f" > "$S/docs/testing/$f" 2>/dev/null \
            || refuse "$rev has no $f (failing closed)"
    else
        cp "$BT/$f" "$S/docs/testing/$f" 2>/dev/null \
            || refuse "$BT has no $f (failing closed)"
    fi
done
what="${rev:+$(git -C "$BT" rev-parse --short "$rev" 2>/dev/null || echo "$rev") in }$BT"

# The board must be read from the files just copied, never from origin/board
# (HAKUX_BOARD_REF empty), and the scratch tree IS the tip, so
# check_coverage's stale-checkout banner cannot ride along on every line.
run() {
    (cd "$S/docs/testing" && env HAKUX_BOARD_REF= HAKUX_TIP="$base_sha" \
        timeout "${BOARD_GATE_TIMEOUT:-120}" python3 "$1" 2>&1)
}
red=0
for c in check_territory.py check_coverage.py; do
    out=$(run "$c"); rc=$?
    if [ "$rc" = 0 ]; then
        if grep -q '^coverage NOT CHECKED' <<< "$out"; then
            say "NOTE: $c could not reach GitHub and FAILED OPEN, as it does everywhere; the tracker's agreement with GitHub was NOT checked for $what"
        else
            say "ok: $c"
        fi
        continue
    fi
    red=1
    if grep -q '^FAIL' <<< "$out"; then
        # Each FAIL line and the rows indented under it, which is what the
        # session repairs from: a FAIL line and the lines under it up to the
        # first blank one. The explanatory paragraph after that is dropped.
        say "$c exited $rc:"
        awk '/^FAIL/ {p = 1; print; next} /^$/ {p = 0} p' <<< "$out" | head -60
    else
        say "$c exited $rc WITHOUT a FAIL line (a crash, or a timeout); failing closed. Its last lines:"
        tail -15 <<< "$out" | sed 's/^/  /'
    fi
done
[ "$red" = 0 ] && { say "PASS: $what passes check_territory and check_coverage against $BASE"; exit 0; }
refuse "$what fails the board gates above. Repair the named rows, re-run this gate, then push. Do not retry blind."
