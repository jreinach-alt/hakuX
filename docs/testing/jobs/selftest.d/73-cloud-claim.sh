# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# cloud.sh: a claim that never started a session spends no attempt, and a
# folded session's leftover local lane/cloud-<n> does not block the next claim.
#
# 73 because it belongs with 70- to 72- (the same script). It uses issue #271,
# the issue of the incident, and is FENCED: its own $HAKUX_WORK, its own repo
# and origin, its own gh/systemctl/systemd-run/git shims on its own PATH. It
# never touches this repository, the shared $HAKUX_WORK or $SELFTEST_GH_LOG.
#
# $CC_JOBS picks the jobs/ tree under test (default: this one), so the same
# legs can be run once against an older cloud.sh staged elsewhere, which is how
# each of them was shown to fail before the fix (docs/lanes/cloudclaim/NOTES.md).

echo "== cloud.sh: an unstarted claim spends no attempt; a folded lane/cloud-N is cleared"
# MEASURED 2026-09-26 07:44 PDT. Three ticks for issue #271 each printed
# `fatal: a branch named 'lane/cloud-271' already exists` and exited 5, and
# each raised $WORK/attempts/cloud-issue-271 by one, 1 -> 4, so the next
# `cloud.sh list` said `would REFUSE issue #271: 4 attempts` after ONE real
# session. The branch was a9f64b930c, a folded session's, an ancestor of
# origin/master: nothing on it could be lost.
CC="$T/cloudclaim"; CC_JOBS="${CC_JOBS:-$HERE}"
rm -rf "$CC"; mkdir -p "$CC/bin" "$CC/work"
CC_LOG="$CC/log"; : > "$CC_LOG"; export CC_LOG

# gh: ONE claimable unit, issue #271 labelled `cloud`. The PR queues are empty.
cat > "$CC/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "${CC_LOG:?}"
case "$1 $2" in
    "issue list") [[ "$*" == *"--label cloud"* ]] && printf '271\t\tcloud: the incident issue\n'; exit 0 ;;
    *) exit 0 ;;
esac
EOF
# systemd-run: recorded, not run. A line in the log IS "the session started".
cat > "$CC/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${CC_LOG:?}"; exit 0
EOF
# systemctl: nothing is active, so the cap is never what stops the claim.
cat > "$CC/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in *is-active*) exit 3 ;; *) exit 0 ;; esac
EOF
# git: the real one, except that `worktree add` fails when $CC_FAIL_WT is set.
# That is leg (a)'s forced failure, and it is independent of the branch state
# legs (b)-(e) arrange, so (a) tests the counter and nothing else.
realgit=$(command -v git)
cat > "$CC/bin/git" <<EOF
#!/usr/bin/env bash
if [ -n "\${CC_FAIL_WT:-}" ]; then
    for a in "\$@"; do [ "\$a" = worktree ] && w=1; [ "\${w:-}" = 1 ] && [ "\$a" = add ] && { echo "fatal: forced by the selftest" >&2; exit 128; }; done
fi
exec "$realgit" "\$@"
EOF
chmod +x "$CC/bin/"*
CCPATH="$CC/bin:$PATH"

# A real origin: master (two commits, so there is an ancestor to be stale at)
# and the orphan board branch the territory row is pushed to.
cc_fixture() {
    rm -rf "$CC/origin.git" "$CC/repo" "$CC/work"; mkdir -p "$CC/work"
    : > "$CC_LOG"
    git init -q --bare "$CC/origin.git"
    git init -q "$CC/repo"
    git -C "$CC/repo" remote add origin "$CC/origin.git"
    git -C "$CC/repo" config user.email t@example.invalid
    git -C "$CC/repo" config user.name t
    git -C "$CC/repo" checkout -q -b master
    echo one > "$CC/repo/README.md"; git -C "$CC/repo" add -A && git -C "$CC/repo" commit -qm "fixture: master 1"
    git -C "$CC/repo" branch lane/cloud-271-at-folded     # where the folded session's branch will point
    echo two > "$CC/repo/README.md"; git -C "$CC/repo" commit -qam "fixture: master 2"
    git -C "$CC/repo" push -q origin master
    git -C "$CC/repo" checkout -q --orphan board
    git -C "$CC/repo" rm -rq --cached . >/dev/null 2>&1; rm -f "$CC/repo/README.md"
    printf 'wave = 7\nupdated_utc = "2026-09-26T00:00:00Z"\n\n[free]\nfiles = []\n' > "$CC/repo/territory.toml"
    git -C "$CC/repo" add -A && git -C "$CC/repo" commit -qm "fixture: the board"
    git -C "$CC/repo" push -q origin board
    git -C "$CC/repo" checkout -q master
    git -C "$CC/repo" fetch -q origin
}
cc_claim() {   # [env assignments...] -- one tick, fenced
    env PATH="$CCPATH" HAKUX_WORK="$CC/work" HAKUX_REPO_DIR="$CC/repo" GH_REPO=example/hakux "$@" \
        bash "$CC_JOBS/cloud.sh" >> "$CC_LOG" 2>&1
}
cc_att()      { [ "$(cat "$CC/work/attempts/cloud-issue-271" 2>/dev/null || echo ABSENT)" = "$1" ]; }
cc_started()  { grep -q '^systemd-run .*hakux-lane-cloud-issue-271' "$CC_LOG"; }
cc_idle()     { ! cc_started; }
cc_branch_at(){ [ "$(git -C "$CC/repo" rev-parse -q --verify refs/heads/lane/cloud-271)" = "$1" ]; }
cc_said()     { grep -qF -- "$1" "$CC_LOG"; }
cc_seed()     {   # the one real session; and where this fixture's folded branch points
    mkdir -p "$CC/work/attempts"; echo 1 > "$CC/work/attempts/cloud-issue-271"
    folded=$(git -C "$CC/repo" rev-parse lane/cloud-271-at-folded); }

# ======================= a: a forced worktree failure spends no attempt
cc_fixture; cc_seed
cc_claim CC_FAIL_WT=1
check "a: the claim fails at worktree add, so no session starts" cc_idle
check "a: and the attempts file is unchanged (1, the one real session)" cc_att 1
cc_claim CC_FAIL_WT=1; cc_claim CC_FAIL_WT=1
check "a: three such ticks, as on #271, still leave it at 1 -- not 4" cc_att 1
cc_fixture
cc_claim CC_FAIL_WT=1
check "a: with no attempts file before, there is none after" cc_att ABSENT

# ======================= b: a folded session's local branch is cleared
cc_fixture; cc_seed
git -C "$CC/repo" branch lane/cloud-271 "$folded"
cc_claim
check "b: the stale lane/cloud-271 (an ancestor of origin/master) is deleted and the session starts" cc_started
check "b: it is recreated at origin/master, not left at the folded sha" \
    cc_branch_at "$(git -C "$CC/repo" rev-parse origin/master)"
check "b: the deletion is logged, with the sha" cc_said "deleting local lane/cloud-271 at ${folded:0:7}"
check "b: and the attempt it spent is counted (1 -> 2), because a session ran" cc_att 2

# ======================= c: a branch with a commit NOT on the tip is kept
cc_fixture; cc_seed
git -C "$CC/repo" checkout -q -b lane/cloud-271 lane/cloud-271-at-folded
echo unpushed > "$CC/repo/work.txt"; git -C "$CC/repo" add -A && git -C "$CC/repo" commit -qm "unpushed work"
git -C "$CC/repo" checkout -q master
unpushed=$(git -C "$CC/repo" rev-parse lane/cloud-271)
cc_claim
check "c: a lane/cloud-271 holding a commit not on origin/master is kept" cc_branch_at "$unpushed"
check "c: the claim is refused, so no session starts" cc_idle
check "c: and the refusal says why" cc_said "holds 1 commit(s) not on origin/master, which may be unpushed work"
check "c: the refused claim spends no attempt" cc_att 1

# ======================= d: an ancestor that origin still has is kept
cc_fixture; cc_seed
git -C "$CC/repo" branch lane/cloud-271 lane/cloud-271-at-folded
git -C "$CC/repo" push -q origin lane/cloud-271
git -C "$CC/repo" update-ref -d refs/remotes/origin/lane/cloud-271   # the host has not fetched it
cc_claim
check "d: an ancestor that is still on origin is not deleted" cc_branch_at "$folded"
check "d: and the refusal says origin has it" cc_said "origin has it too"
check "d: no attempt spent" cc_att 1

# ======================= e: an ancestor checked out in a worktree is kept
cc_fixture; cc_seed
git -C "$CC/repo" worktree add -q -b lane/cloud-271 "$CC/other-wt" lane/cloud-271-at-folded 2>/dev/null
cc_claim
check "e: an ancestor checked out in another worktree is not deleted" cc_branch_at "$folded"
check "e: and the refusal says it is checked out" cc_said "it is checked out in a worktree"
check "e: no attempt spent" cc_att 1
git -C "$CC/repo" worktree remove --force "$CC/other-wt" 2>/dev/null
unset CC_JOBS
