# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# fold.sh: a folded lane branch is deleted, and nothing else is.
#
# Builds its own bare "origin" and clone under $T/prune, plus a worktree. No
# shared state, so the NN only has to sort after the other fold fragments.

echo "== fold.sh: a folded lane branch is deleted, and nothing else is"
# Nothing ever removed a lane ref. arms.sh's collect() walks
# refs/remotes/origin/lane/* every tick and its fetch refspec does not prune,
# so the tick's cost grew with the number of lanes the project had EVER run:
# 25 refs on 2026-09-19, 8 of them folded days earlier. The fold is the moment
# that has just proved every commit is on the trunk, so that is where the
# delete belongs. What has to be pinned is that it deletes exactly the right
# three refs and refuses everything else -- a delete that reaches one ref too
# far un-arms a registered b_ref silently. A scratch bare "origin" makes all
# of it real: no shim can refuse a push or hold a branch in a worktree.
PD="$T/prune"; rm -rf "$PD"; mkdir -p "$PD"
pg() { git -C "$PD/repo" -c user.email=s@t -c user.name=s "$@"; }
git -c init.defaultBranch=master init -q --bare "$PD/origin.git"
git -c init.defaultBranch=master clone -q "$PD/origin.git" "$PD/repo" 2>/dev/null
echo base > "$PD/repo/f"; pg add -A; pg commit -q -m base; pg push -q origin master
# lane/gone: folded -- its commit reached master through a --no-ff merge, the
# shape a real fold leaves, so every commit keeps its sha and is an ancestor.
pg checkout -q -b lane/gone; echo g > "$PD/repo/g"; pg add -A; pg commit -q -m lane
pg push -q origin lane/gone
pg checkout -q master; pg merge -q --no-ff --no-edit lane/gone; pg push -q origin master
# lane/live: a commit that is NOT on master -- a lane that pushed after the
# fold's fetch looks exactly like this, and deleting it destroys work.
pg checkout -q -b lane/live master; echo l > "$PD/repo/l"; pg add -A; pg commit -q -m live
pg push -q origin lane/live; pg checkout -q master
# board: fully merged, so the ancestry test would PASS on it. Only the name
# saves it, which is the point of testing with this one rather than a fiction.
pg push -q origin master:refs/heads/board
MSHA=$(pg rev-parse master)

( export HAKUX_REPO_DIR="$PD/repo"; bash "$HERE/fold.sh" prune ) > "$PD/dry.log" 2>&1
check "prune's dry run names the folded lane branch" grep -q "would prune lane/gone" "$PD/dry.log"
check "prune's dry run keeps the one with commits not on master" grep -q "^keep  *lane/live" "$PD/dry.log"
check "prune's dry run counts what it saw" grep -q "total lane refs: 2, fully merged into master: 1" "$PD/dry.log"
check "prune's dry run deletes NOTHING" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/lane/gone

( export HAKUX_REPO_DIR="$PD/repo"; bash "$HERE/fold.sh" prune --apply ) > "$PD/apply.log" 2>&1
check "prune --apply deletes the folded lane ref on origin" \
    bash -c '! git -C "$1/origin.git" rev-parse -q --verify refs/heads/lane/gone >/dev/null' _ "$PD"
check "  and the tracking ref, which is the one arms.sh actually walks" \
    bash -c '! git -C "$1/repo" rev-parse -q --verify refs/remotes/origin/lane/gone >/dev/null' _ "$PD"
check "  and the local head, which no worktree holds" \
    bash -c '! git -C "$1/repo" rev-parse -q --verify refs/heads/lane/gone >/dev/null' _ "$PD"
check "  and the merge commit it reached master by is still there" \
    bash -c 'git -C "$1/origin.git" merge-base --is-ancestor "$2" refs/heads/master' _ "$PD" "$MSHA"
check "prune --apply leaves a lane ref whose commits are not on master" \
    git -C "$PD/origin.git" rev-parse -q --verify refs/heads/lane/live
check "  and leaves its tracking ref bound" git -C "$PD/repo" rev-parse -q --verify refs/remotes/origin/lane/live
check "prune --apply never touches a non-lane branch, however merged" \
    git -C "$PD/origin.git" rev-parse -q --verify refs/heads/board
check "prune --apply never touches the trunk" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/master

# The name guard, against the two refs that would pass every other test.
pg fetch -q origin '+refs/heads/board:refs/remotes/origin/board'
for bad in master board claude/hakux-orchestration-design-e663m8; do
    bash "$HERE/fold.sh" prune-branch "$PD/repo" "$bad" "$MSHA" > "$PD/bad.log" 2>&1; rc=$?
    check "prune-branch REFUSES '$bad'" [ "$rc" != 0 ]
    # An exit code alone is a coarse discriminator: a script that died before
    # reaching the guard exits non-zero too. Assert on the sentence.
    check "  and says which rule refused it" grep -q "only lane/\* refs are ever deleted" "$PD/bad.log"
done
check "  and master is still on origin afterwards" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/master
check "  and board is too" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/board

# The ancestry guard, which is what keeps a registered b_ref bound.
bash "$HERE/fold.sh" prune-branch "$PD/repo" lane/live "$MSHA" > "$PD/live.log" 2>&1; rc=$?
check "prune-branch REFUSES a lane ref whose commits are not on the proof commit" [ "$rc" != 0 ]
check "  and says it kept the ref, naming the sha it judged" grep -q "is NOT fully merged into .*ref KEPT" "$PD/live.log"
check "  and lane/live survives on origin" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/lane/live

# A worktree holding the branch is not the edge case: on 2026-09-19 all eight
# already-merged lane branches had one. git refuses `branch -d` there, and
# that refusal is the wanted answer -- the remote ref and the tracking ref
# (the ones that cost a tick anything) still go.
pg checkout -q -b lane/held master; pg push -q origin lane/held; pg checkout -q master
git -C "$PD/repo" worktree add -q "$PD/heldwt" lane/held 2>/dev/null
bash "$HERE/fold.sh" prune-branch "$PD/repo" lane/held "$MSHA" > "$PD/held.log" 2>&1
check "a worktree-held branch still loses its ref on origin" \
    bash -c '! git -C "$1/origin.git" rev-parse -q --verify refs/heads/lane/held >/dev/null' _ "$PD"
check "  and its tracking ref" \
    bash -c '! git -C "$1/repo" rev-parse -q --verify refs/remotes/origin/lane/held >/dev/null' _ "$PD"
check "  but the local head the worktree holds is KEPT, not forced" \
    git -C "$PD/repo" rev-parse -q --verify refs/heads/lane/held
check "  and the log says so rather than passing over it" grep -q "local refs/heads/lane/held KEPT" "$PD/held.log"
check "  and names the command that removes the worktree" grep -q "lane.sh rm held" "$PD/held.log"
check "  and the worktree is left with a HEAD that resolves" git -C "$PD/heldwt" rev-parse --verify HEAD
# Run it again: the ref is gone from origin now. ls-remote --exit-code says 2
# for "no such ref" and something else for "could not ask", and those must not
# be confused -- a network failure that read as "already gone" would drop a
# tracking ref that is still bound to a live branch.
bash "$HERE/fold.sh" prune-branch "$PD/repo" lane/held "$MSHA" > "$PD/again.log" 2>&1; rc=$?
check "prune-branch is idempotent: a second run on a gone ref succeeds" [ "$rc" = 0 ]
check "  and says the ref was already gone rather than claiming a delete" \
    bash -c 'grep -q "origin has no such ref" "$1" && ! grep -q "deleted origin" "$1"' _ "$PD/again.log"
# The other half of that, and the half with teeth: an origin that cannot be
# reached at all must NOT read as "already gone". ls-remote --exit-code says 2
# for no-matching-ref and 128 for a fatal, and a `-ne 0` that lumps them
# together drops a tracking ref still bound to a live branch -- on a bad
# network, for every lane at once. lane/unreach is an ancestor of master, so
# only the unreachable-origin path can save it.
pg checkout -q -b lane/unreach master; pg push -q origin lane/unreach; pg checkout -q master
git -C "$PD/repo" remote set-url origin "$PD/no-such-remote.git"
bash "$HERE/fold.sh" prune-branch "$PD/repo" lane/unreach "$MSHA" > "$PD/unreach.log" 2>&1; rc=$?
git -C "$PD/repo" remote set-url origin "$PD/origin.git"
check "prune-branch REFUSES when it cannot reach origin at all" [ "$rc" != 0 ]
check "  and does NOT report it as already gone" \
    bash -c 'grep -q "cannot reach origin" "$1" && ! grep -q "no such ref" "$1"' _ "$PD/unreach.log"
check "  and KEEPS the tracking ref, which is still bound to a live branch" \
    git -C "$PD/repo" rev-parse -q --verify refs/remotes/origin/lane/unreach
check "  and leaves the branch on origin" git -C "$PD/origin.git" rev-parse -q --verify refs/heads/lane/unreach

# Where the delete sits in the fold path. A branch deleted on a fold whose
# push failed is work destroyed, so the call must come AFTER that push -- a
# line-number test, not a search for a word that could be in a comment.
pushln=$(grep -n 'push -q origin "HEAD:$TIP"' "$HERE/fold.sh" | head -1 | cut -d: -f1)
pruneln=$(grep -n '^ *prune_branch "$WT" "$branch" HEAD$' "$HERE/fold.sh" | head -1 | cut -d: -f1)
check "the fold path prunes the branch it just folded" bash -c '[ -n "${1:-}" ]' _ "$pruneln"
check "  and only after the push to the trunk succeeded" \
    bash -c '[ -n "${1:-}" ] && [ -n "${2:-}" ] && [ "$2" -gt "$1" ]' _ "$pushln" "$pruneln"
check "no job script forces a branch deletion or a push" \
    bash -c '! grep -nE "branch +-D|push [^|#]*--force" "$1"/*.sh' _ "$HERE"
