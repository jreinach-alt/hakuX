# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# #433 lane.sparsewt1017: every lane worktree used to be a full checkout, and
# docs/lanes/pathfind/runs/ (held-run evidence, 54 GB across 28 trees) was
# 1.9 GB of each one, for a subtree no lane ever reads -- git already stores
# it. lane.sh's start command now builds BOTH its worktree forms (the fresh
# `-b branch FETCH_HEAD` form and the resume-after-crash `-B branch
# origin/branch` form) through one helper, lane_worktree_add(), that excludes
# that path via `git sparse-checkout set --no-cone`, unless the lane is named
# pathfind (whose tree IS the live harness tree) or its brief carries a
# $WORK/briefs/<name>.fullcheckout opt-out marker.
#
# 99 because it depends on the harness only (git and the real lane.sh), and
# touches no other fragment's state: its own throwaway origin and $WORK, and
# lane names ("sparselane", "sparselane2", "pathfind") no territory row
# anywhere names, so refuse_if_remote always falls through, the same
# reasoning 99-lane-path.sh and 99-lane-model-file.sh give for their own
# fixtures.

echo "== lane.sh: a new worktree is sparse, excluding docs/lanes/pathfind/runs/"
LW="$T/lanesparse"; rm -rf "$LW"; mkdir -p "$LW/work/briefs" "$LW/dispatch"

# A BARE origin, not a plain checked-out one: the resume-form leg below
# pushes a freshly-made lane branch to it, and a non-bare origin would refuse
# that push the moment the branch collided with its own checked-out HEAD (the
# same reason 98-lane-shape.sh's arms/prune fixtures use --bare).
git init -q -b master --bare "$LW/origin.git"
git clone -q "$LW/origin.git" "$LW/seed" 2>/dev/null
mkdir -p "$LW/seed/docs/lanes/pathfind/runs"
printf 'held run evidence, not needed by a lane\n' > "$LW/seed/docs/lanes/pathfind/runs/sample.bin"
printf 'an ordinary tracked file\n' > "$LW/seed/README-scratch.md"
git -C "$LW/seed" add -A
git -C "$LW/seed" -c user.email=s@t -c user.name=s commit -q -m seed
git -C "$LW/seed" push -q origin master
git clone -q "$LW/origin.git" "$LW/repo" 2>/dev/null
printf '# a brief for the sparse-worktree selftest\n' > "$LW/brief.md"

RUNS_REL=docs/lanes/pathfind/runs/sample.bin

lw_fresh() {   # <name>
    git -C "$LW/repo" worktree remove --force "$LW/work/wt/$1" 2>/dev/null
    rm -rf "$LW/work/wt/$1" "$LW/work/attempts/$1" "$LW/work/briefs/$1."*
    git -C "$LW/repo" worktree prune 2>/dev/null
    git -C "$LW/repo" branch -qD "lane/$1" 2>/dev/null
}
lw_start() {   # <lane.sh> <name> <log> -> sets LW_RC
    local lsh=$1 nm=$2 log=$3
    : > "$log"
    ( env HAKUX_WORK="$LW/work" HAKUX_REPO_DIR="$LW/repo" DISPATCH_DIR="$LW/dispatch" \
          SELFTEST_GH_LOG="$log" \
          bash "$lsh" start "$nm" "$LW/brief.md" 9401 ) >"$log" 2>&1
    LW_RC=$?
}
# <label> <wt path> <branch> -- the four things every scenario below checks:
# the excluded path is absent, the rest of the tree is there, nothing else is
# touched (clean status), and HEAD is the lane's own branch (not detached,
# not master).
lw_check() {   # <label> <wt path> <branch>
    local label=$1 wt=$2 br=$3
    check "$label: docs/lanes/pathfind/runs/ is excluded from the checkout" \
        [ ! -e "$wt/$RUNS_REL" ]
    check "$label: the rest of the tree is still there" [ -f "$wt/README-scratch.md" ]
    check "$label: git status is clean (no partial/missing-index artifacts)" \
        bash -c '[ -z "$(git -C "$1" status --short)" ]' _ "$wt"
    check "$label: the worktree is on the lane's own branch" \
        bash -c '[ "$(git -C "$1" branch --show-current)" = "$2" ]' _ "$wt" "$br"
}

# ------------------------------------------------------- the fresh-branch form
lw_fresh sparselane
lw_start "$TESTING/lane.sh" sparselane "$LW/fresh.log"
check "fresh start (-b branch FETCH_HEAD) reaches systemd-run (not an early exit)" \
    grep -q -- '--setenv=HAKUX_ROLE=lane' "$LW/fresh.log"
lw_check "fresh form" "$LW/work/wt/sparselane" lane/sparselane

# --------------------------------------------- the resume-after-crash form
# Simulate what a real lane does once started: push its branch to origin.
# Then drop the worktree (as `lane.sh rm` or a crash would) and start the
# SAME name again -- refs/remotes/origin/lane/sparselane now exists, so
# lane.sh takes the OTHER branch, `-B branch origin/branch`.
git -C "$LW/work/wt/sparselane" push -q origin lane/sparselane
git -C "$LW/repo" worktree remove --force "$LW/work/wt/sparselane"
rm -rf "$LW/work/wt/sparselane" "$LW/work/attempts/sparselane" "$LW/work/briefs/sparselane."*
git -C "$LW/repo" worktree prune 2>/dev/null
lw_start "$TESTING/lane.sh" sparselane "$LW/resumeform.log"
check "resume-form start (-B branch origin/branch) reaches systemd-run too" \
    grep -q -- '--setenv=HAKUX_ROLE=lane' "$LW/resumeform.log"
check "resume-form start says it resumed from origin" \
    grep -q '^resumed lane/sparselane from origin' "$LW/resumeform.log"
lw_check "resume form" "$LW/work/wt/sparselane" lane/sparselane
lw_fresh sparselane

# ------------------------------------------------------------- the exemptions
# lane.pathfind: its tree IS the live harness tree, so it is exempt --
# docs/lanes/pathfind/runs/ must actually be checked out.
lw_fresh pathfind
lw_start "$TESTING/lane.sh" pathfind "$LW/pathfind.log"
check "lane.pathfind: start reaches systemd-run" \
    grep -q -- '--setenv=HAKUX_ROLE=lane' "$LW/pathfind.log"
check "lane.pathfind: its own docs/lanes/pathfind/runs/ IS checked out, not excluded" \
    [ -f "$LW/work/wt/pathfind/$RUNS_REL" ]
lw_fresh pathfind

# $WORK/briefs/<name>.fullcheckout: an explicit opt-out for any other lane.
lw_fresh sparselane2
mkdir -p "$LW/work/briefs"; : > "$LW/work/briefs/sparselane2.fullcheckout"
lw_start "$TESTING/lane.sh" sparselane2 "$LW/optout.log"
check "the .fullcheckout opt-out: start reaches systemd-run" \
    grep -q -- '--setenv=HAKUX_ROLE=lane' "$LW/optout.log"
check "the .fullcheckout opt-out: docs/lanes/pathfind/runs/ IS checked out" \
    [ -f "$LW/work/wt/sparselane2/$RUNS_REL" ]
lw_fresh sparselane2
rm -f "$LW/work/briefs/sparselane2.fullcheckout"

# ------------------------------- the shared repo config is never touched
# sparse-checkout writes core.sparseCheckout into the per-WORKTREE config
# (extensions.worktreeConfig = true), never the shared one every worktree of
# $REPO shares -- a write there would turn every OTHER worktree sparse too.
check "the shared repo's config never gains core.sparseCheckout" \
    bash -c '! git -C "$1" config --get core.sparseCheckout >/dev/null 2>&1' _ "$LW/repo"

# ------------------------------------------------------------------ structural
# A value re-derived in a second place is a value that drifts the next time
# only one copy is edited (99-lane-path.sh's lp_one makes the same argument
# for LANE_PATH). One function, one exclusion pattern.
lw_one() { [ "$(grep -c -- "$2" "$1")" = 1 ]; }
check "lane.sh has exactly one lane_worktree_add() definition" \
    lw_one "$TESTING/lane.sh" '^lane_worktree_add() {'
check "lane.sh has exactly one docs/lanes/pathfind/runs/ exclusion pattern" \
    lw_one "$TESTING/lane.sh" '!/docs/lanes/pathfind/runs/'
check "the only raw \`git worktree add\` calls left are lane_worktree_add's own two forms (start's call sites now go through it)" \
    [ "$(grep -c 'git -C "\$REPO" worktree add' "$TESTING/lane.sh")" = 2 ]

# ------------------------------------------------------------------ mutant
# THE FALSIFIER: if the exemption's condition is widened to "always", the
# exclusion stops applying to anything, and this leg must go red to prove the
# checks above are not merely checking that lane.sh ran at all.
m="$TESTING/.selftest-mutlane-sparsealways.sh"
cp "$TESTING/lane.sh" "$m"
sed -i 's/if \[ "\$name" = pathfind \] || \[ -e "\$WORK\/briefs\/\$name.fullcheckout" \]; then/if true; then/' "$m"
check "mutant sparsealways: the sed applied" bash -c '! cmp -s "$1" "$2"' _ "$m" "$TESTING/lane.sh"
lw_fresh sparselane3
lw_start "$m" sparselane3 "$LW/mutant.log"
check "mutant sparsealways: start still reaches systemd-run (not refusing for an unrelated reason)" \
    grep -q -- '--setenv=HAKUX_ROLE=lane' "$LW/mutant.log"
if [ -f "$LW/work/wt/sparselane3/$RUNS_REL" ]; then
    ok "mutant sparsealways: docs/lanes/pathfind/runs/ IS checked out again, and this leg is red"
else
    bad "mutant sparsealways: the exclusion still held even with the condition forced to \`if true\`"
fi
lw_fresh sparselane3
rm -f "$m"

rm -rf "$LW"
unset -f lw_fresh lw_start lw_check lw_one
unset LW_RC RUNS_REL
