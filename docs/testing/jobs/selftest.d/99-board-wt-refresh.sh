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
