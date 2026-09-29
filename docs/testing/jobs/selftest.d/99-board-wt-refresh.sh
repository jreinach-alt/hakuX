# Sourced by ../selftest.sh with the harness already built: $T, $HERE,
# $TESTING, ok/bad/check. Not executable, no shebang, no exit -- `fail` is
# shared and is the run's verdict.
#
# THE BOARD'S TRUNK TREE LANDS ON THE TRUNK, OR THE TICK STOPS. board.sh
# refreshed $WORK/board-wt with `fetch && checkout --detach FETCH_HEAD`; a dirty
# tree makes that checkout refuse, and nothing read the refusal. On 2026-09-29
# the tree held 39 uncommitted paths from an old WIP commit and every tick ran
# a stale fleet.py. `board.sh refresh-wt <tree>` is the refresh alone. Checked:
#   - a dirty tree (a modified, a deleted and an untracked path) ends at
#     FETCH_HEAD, clean, with the nested .boardtree left alone;
#   - a NOTE naming the dirt is printed AND in the tick log;
#   - nothing is lost: a stash with the auto-cleared message holds the edit;
#   - a clean tree is refreshed without a NOTE or a stash;
#   - a checkout that still fails, and a fetch that fails, ABORT with rc 1.
#
# Builds its own origin, clone and worktrees under $BW; depends on no other
# fragment.

echo "== board trunk tree: a dirty tree is stashed, said, and still lands on the trunk"
BW="$T/boardwt"; mkdir -p "$BW/jobs"
cp "$HERE/board.sh" "$HERE/localtime.sh" "$HERE/window.sh" "$BW/jobs/"
git init -q --bare -b master "$BW/origin.git"
git clone -q "$BW/origin.git" "$BW/repo" 2>/dev/null
git -C "$BW/repo" config user.email t@t; git -C "$BW/repo" config user.name t
printf 'old\n' > "$BW/repo/fleet.py"; printf 'keep\n' > "$BW/repo/gone.txt"
git -C "$BW/repo" add -A && git -C "$BW/repo" commit -q -m A && git -C "$BW/repo" push -q origin master
git -C "$BW/repo" worktree add -q --detach "$BW/wt" master
git -C "$BW/wt" worktree add -q -b board "$BW/wt/.boardtree" master   # nested, as board.sh makes it
# The trunk moves on; the tree is dirtied as the stale WIP did.
printf 'new\n' > "$BW/repo/fleet.py"
git -C "$BW/repo" commit -q -am B && git -C "$BW/repo" push -q origin master
tipsha=$(git -C "$BW/repo" rev-parse HEAD)
printf 'stale wip\n' > "$BW/wt/fleet.py"; rm "$BW/wt/gone.txt"; printf 'x\n' > "$BW/wt/stray.txt"

bwrun() { HAKUX_WORK="$BW/work" HAKUX_REPO_DIR="$BW/repo" HAKUX_TIP="${BW_TIP:-master}" \
          bash "$BW/jobs/board.sh" refresh-wt "$BW/wt" 2>&1; echo "rc=$?"; }
out=$(bwrun)
check "refresh-wt: a dirty tree still refreshes (rc 0)" grep -qx 'rc=0' <<< "$out"
check "...and lands at origin's tip" test "$(git -C "$BW/wt" rev-parse HEAD)" = "$tipsha"
check "...with the trunk's content, not the stale edit" grep -qx 'new' "$BW/wt/fleet.py"
check "...clean apart from .boardtree" test -z "$(git -C "$BW/wt" status --porcelain -- . ':(exclude).boardtree')"
check "...and .boardtree is left in place" test -e "$BW/wt/.boardtree/.git"
check "...and a NOTE names the dirty tree" grep -q "NOTE: $BW/wt had 3 uncommitted path(s)" <<< "$out"
check "...the NOTE is in the tick log too" grep -q "NOTE: $BW/wt had 3 uncommitted" "$BW/work/logs/board/tick.log"
check "...and the NOTE says where it went" grep -q 'Stashing as "board.sh: auto-cleared dirty' <<< "$out"
st=$(git -C "$BW/wt" stash list --format='%H %gs' | grep "auto-cleared dirty $BW/wt" | head -1 | cut -d' ' -f1)
check "nothing lost: the stash is listed" test -n "$st"
check "...and holds the stale edit" grep -qx 'stale wip' <(git -C "$BW/wt" show "$st:fleet.py")
check "...and the untracked path" grep -qx 'x' <(git -C "$BW/wt" show "$st^3:stray.txt")

# A clean tree: refreshed, silent, no second stash.
nst=$(git -C "$BW/wt" stash list | wc -l)
printf 'newer\n' > "$BW/repo/fleet.py"
git -C "$BW/repo" commit -q -am C && git -C "$BW/repo" push -q origin master
out=$(bwrun)
check "refresh-wt: a clean tree refreshes (rc 0)" grep -qx 'rc=0' <<< "$out"
check "...to the new tip" test "$(git -C "$BW/wt" rev-parse HEAD)" = "$(git -C "$BW/repo" rev-parse HEAD)"
check "...without a NOTE" bash -c '! grep -q NOTE <<< "$1"' _ "$out"
check "...or a stash" test "$(git -C "$BW/wt" stash list | wc -l)" = "$nst"

# A checkout that fails with the dirt gone is not a dirty-tree problem: ABORT.
printf 'newest\n' > "$BW/repo/fleet.py"
git -C "$BW/repo" commit -q -am D && git -C "$BW/repo" push -q origin master
lock="$(git -C "$BW/wt" rev-parse --absolute-git-dir)/index.lock"; : > "$lock"
out=$(bwrun)
rm -f "$lock"
check "refresh-wt: a checkout that still fails exits 1" grep -qx 'rc=1' <<< "$out"
check "...and says ABORT, naming the wrong base" grep -q 'ABORT: checkout of origin/master failed' <<< "$out"
out=$(BW_TIP=no-such-branch bwrun)
check "refresh-wt: a failed fetch exits 1" grep -qx 'rc=1' <<< "$out"
check "...and says ABORT" grep -q 'ABORT: cannot fetch origin/no-such-branch' <<< "$out"

echo "== board session tree: a dirty or stale .boardtree lands on origin/board, or the tick stops"
# .boardtree ($BW/wt/.boardtree) was made above (line 29), nested in $BW/wt,
# checked out on branch `board` off master's first commit (A). It was never
# pushed anywhere; push it now so origin has a `board` ref refresh-bt can
# fetch, exactly as a real session's first tick creates $BT from `board` or
# `origin/board` (board.sh:526-529).
BT="$BW/wt/.boardtree"
git -C "$BT" push -q origin board
# A second clone plays "another session pushing to origin/board" so $BT's
# own history never gets ahead of origin by anything this test does not
# construct on purpose.
git clone -q "$BW/origin.git" "$BW/board-writer" 2>/dev/null
git -C "$BW/board-writer" checkout -q board
git -C "$BW/board-writer" config user.email t@t; git -C "$BW/board-writer" config user.name t

bwbtrun() { HAKUX_WORK="$BW/work" HAKUX_REPO_DIR="$BW/repo" HAKUX_TIP=master \
            bash "$BW/jobs/board.sh" refresh-bt "$BT" 2>&1; echo "rc=$?"; }

# Case 1: a clean $BT, origin/board has moved on -> lands at the new tip,
# nothing stashed. refs/stash is shared across every worktree of one
# repository -- $BT is a worktree of the same repo as $BW/wt above, which
# already holds stashes from the refresh-wt cases -- so "nothing stashed"
# is checked as no CHANGE in the count, not a count of zero.
nst0=$(git -C "$BT" stash list | wc -l)
printf 'one\n' > "$BW/board-writer/boardfile.txt"
git -C "$BW/board-writer" add -A && git -C "$BW/board-writer" commit -q -m "board A" && git -C "$BW/board-writer" push -q origin board
tip1=$(git -C "$BW/board-writer" rev-parse HEAD)
out=$(bwbtrun)
check "refresh-bt: a clean tree refreshes (rc 0)" grep -qx 'rc=0' <<< "$out"
check "...to origin/board's tip" test "$(git -C "$BT" rev-parse HEAD)" = "$tip1"
check "...without a NOTE" bash -c '! grep -q NOTE <<< "$1"' _ "$out"
check "...or a stash" test "$(git -C "$BT" stash list | wc -l)" = "$nst0"

# Case 2: origin/board moves again, and $BT is dirtied (a modified tracked
# path and an untracked one) -> the tick proceeds, the dirt is stashed
# (verified via `git stash list`, not just rc), $BT ends at the new tip, and
# the dirty content is recoverable from the stash.
printf 'two\n' > "$BW/board-writer/boardfile.txt"
printf 'keep\n' > "$BW/board-writer/gone2.txt"
git -C "$BW/board-writer" add -A && git -C "$BW/board-writer" commit -q -m "board B" && git -C "$BW/board-writer" push -q origin board
tip2=$(git -C "$BW/board-writer" rev-parse HEAD)
printf 'dirty edit\n' > "$BT/boardfile.txt"
printf 'stray\n' > "$BT/stray-bt.txt"
out=$(bwbtrun)
check "refresh-bt: a dirty tree still refreshes (rc 0)" grep -qx 'rc=0' <<< "$out"
check "...and lands at origin/board's new tip" test "$(git -C "$BT" rev-parse HEAD)" = "$tip2"
check "...clean afterward" test -z "$(git -C "$BT" status --porcelain)"
check "...and a NOTE names the dirty tree" grep -q "NOTE: $BT had 2 uncommitted path(s)" <<< "$out"
check "...the NOTE is in the tick log too" grep -q "NOTE: $BT had 2 uncommitted" "$BW/work/logs/board/tick.log"
bst=$(git -C "$BT" stash list --format='%H %gs' | grep "auto-cleared dirty $BT " | head -1 | cut -d' ' -f1)
check "nothing lost: the stash is listed" test -n "$bst"
check "...and holds the dirty edit" grep -qx 'dirty edit' <(git -C "$BT" show "$bst:boardfile.txt")
check "...and the untracked path" grep -qx 'stray' <(git -C "$BT" show "$bst^3:stray-bt.txt")

# Case 3: $BT and origin/board each hold a commit the other lacks (true
# divergence, as if a push failed after a local commit while another
# session pushed too) -> refresh_bt must not guess how to reconcile it:
# `merge --ff-only` refuses cleanly here, unlike the merely-ahead case (a
# local commit alone, with origin unmoved, IS a fast-forward -- ff-only
# would just no-op past it, not abort). Verify: abort, keep the local
# commit, never force-push or rewrite origin.
printf 'three\n' > "$BW/board-writer/boardfile.txt"
git -C "$BW/board-writer" add -A && git -C "$BW/board-writer" commit -q -m "board C" && git -C "$BW/board-writer" push -q origin board
tip3=$(git -C "$BW/board-writer" rev-parse HEAD)
printf 'local only\n' > "$BT/localwip.txt"
git -C "$BT" add -A && git -C "$BT" commit -q -m "local wip, never pushed"
localsha=$(git -C "$BT" rev-parse HEAD)
out=$(bwbtrun)
check "refresh-bt: a diverged tree aborts (rc 1)" grep -qx 'rc=1' <<< "$out"
check "...and says ABORT, naming it unforwardable" grep -q 'ABORT:.*not fast-forwardable' <<< "$out"
check "...the local commit is not lost" test "$(git -C "$BT" rev-parse HEAD)" = "$localsha"
check "...origin/board is untouched" test "$(git -C "$BW/origin.git" rev-parse board)" = "$tip3"

# A fetch that fails also aborts, same as refresh-wt.
mv "$BW/origin.git" "$BW/origin.git.away"
out=$(bwbtrun)
mv "$BW/origin.git.away" "$BW/origin.git"
check "refresh-bt: a fetch that fails exits 1" grep -qx 'rc=1' <<< "$out"
check "...and says ABORT" grep -q 'ABORT: cannot fetch origin/board' <<< "$out"

# THE MUTANT: reverting the fast-forward to a no-op is exactly the old
# create-once-never-refresh bug (board.sh made $BT once and never touched it
# again). It must fail case 2 above -- a dirty, stale $BT that a tick still
# has to land on origin/board's tip.
bt_scenario() {   # <jobs-dir> -> stdout lines "clean ok|FAIL", "dirty ok|FAIL"
    local jobs="$1" root
    root=$(mktemp -d "$T/bt-mutant.XXXXXX")
    git init -q --bare -b master "$root/origin.git"
    git clone -q "$root/origin.git" "$root/seed" 2>/dev/null
    git -C "$root/seed" config user.email t@t; git -C "$root/seed" config user.name t
    printf 'x\n' > "$root/seed/f.txt"
    git -C "$root/seed" add -A && git -C "$root/seed" commit -q -m seed
    git -C "$root/seed" branch -q board
    git -C "$root/seed" push -q origin master board
    git clone -q "$root/origin.git" "$root/bt" 2>/dev/null
    git -C "$root/bt" checkout -q board
    git -C "$root/bt" config user.email t@t; git -C "$root/bt" config user.name t
    git -C "$root/seed" checkout -q board

    printf 'y\n' > "$root/seed/f.txt"
    git -C "$root/seed" commit -q -am board1 && git -C "$root/seed" push -q origin board
    tip1=$(git -C "$root/seed" rev-parse board)
    HAKUX_WORK="$root/work" bash "$jobs/board.sh" refresh-bt "$root/bt" >/dev/null 2>&1
    if [ "$(git -C "$root/bt" rev-parse HEAD)" = "$tip1" ]; then echo "clean ok"; else echo "clean FAIL"; fi

    printf 'z\n' > "$root/seed/f.txt"
    git -C "$root/seed" commit -q -am board2 && git -C "$root/seed" push -q origin board
    tip2=$(git -C "$root/seed" rev-parse board)
    printf 'dirty\n' > "$root/bt/f.txt"
    HAKUX_WORK="$root/work" bash "$jobs/board.sh" refresh-bt "$root/bt" >/dev/null 2>&1
    if [ "$(git -C "$root/bt" rev-parse HEAD)" = "$tip2" ] && [ -z "$(git -C "$root/bt" status --porcelain)" ]
        then echo "dirty ok"; else echo "dirty FAIL"; fi
    rm -rf "$root"
}
real_out=$(bt_scenario "$BW/jobs")
check "refresh-bt: real code, clean case" grep -qx 'clean ok' <<< "$real_out"
check "refresh-bt: real code, dirty case" grep -qx 'dirty ok' <<< "$real_out"

MBT="$T/bt-mutant-jobs"; rm -rf "$MBT"; mkdir -p "$MBT"
cp "$BW/jobs/board.sh" "$BW/jobs/localtime.sh" "$BW/jobs/window.sh" "$MBT/"
python3 -c '
import re, sys
p, pat, rep = sys.argv[1:4]
s = open(p).read(); t, n = re.subn(pat, rep, s, flags=re.S)
if n != 1: sys.exit("mutant pattern matched %d times in board.sh" % n)
open(p, "w").write(t)' "$MBT/board.sh" \
    'git -C "\$wt" merge -q --ff-only FETCH_HEAD \\\n        \|\| \{ say "ABORT: \$wt.s board branch has a commit origin/board does not \(not fast-forwardable\); not force-landing over session work"; return 1; \}' \
    'true  # mutant: fast-forward reverted to a no-op' \
    || bad "refresh-bt mutant: its anchor no longer matches board.sh"
mut_out=$(bt_scenario "$MBT")
check "mutant: fast-forward reverted to a no-op -> dirty/stale case goes red" bash -c '! grep -qx "dirty ok" <<< "$1"' _ "$mut_out"
