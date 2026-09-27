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
CC_LABELS="$CC/labels"; CC_ACTIVE="$CC/active"; export CC_LABELS CC_ACTIVE

# gh: ONE claimable unit, issue #271 labelled `cloud`. The PR queues are empty.
cat > "$CC/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "${CC_LOG:?}"
case "$1 $2" in
    "issue list") [[ "$*" == *"--label cloud"* ]] && printf '271\t\tcloud: the incident issue\n'; exit 0 ;;
    # Labels BY NUMBER, with state: POST appends, DELETE removes, GET reads
    # $CC_LABELS. `issue list` above does NOT read it -- that is the lagging
    # search index of the #420 incident, which still lists a claimed number.
    "api "*)
        f="${CC_LABELS:?}"; touch "$f"
        if [[ "$*" == *"-X POST"* ]]; then
            for a in "$@"; do [[ "$a" == labels\[\]=* ]] && echo "${a#labels[]=}" >> "$f"; done
        elif [[ "$*" == *"-X DELETE"* ]]; then
            l=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.unquote(sys.argv[1].rsplit("/",1)[1]))' "${*: -1}")
            grep -vFx -- "$l" "$f" > "$f.n"; mv "$f.n" "$f"
        else cat "$f"; fi
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
# systemd-run: recorded, not run. A line in the log IS "the session started".
# $CC_FAIL_RUN makes it fail as the real one does: `exists` is the #420
# collision -- another tick started the unit between this tick's check and its
# systemd-run, so the unit becomes active and the call is refused; `fail` is a
# unit that never started at all.
cat > "$CC/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
u=""; for a in "$@"; do [ "${p:-}" = --unit ] && u=$a; p=$a; done
case "${CC_FAIL_RUN:-}" in
    exists) echo "$u.service" >> "${CC_ACTIVE:?}"
            echo "Failed to start transient service unit: Unit $u.service was already loaded or has a fragment file." >&2; exit 1 ;;
    fail)   echo "Failed to start transient service unit: forced by the selftest" >&2; exit 1 ;;
esac
echo "systemd-run $*" >> "${CC_LOG:?}"; exit 0
EOF
# systemctl: a unit is active iff $CC_ACTIVE names it, for `is-active <unit>`
# and for `list-units <glob>` alike (the glob matched as systemd matches it).
# Empty by default, so the cap is never what stops the claim.
cat > "$CC/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
f="${CC_ACTIVE:-/nonexistent}"
case "$*" in
    *is-active*) u="${*: -1}"; grep -qFx -- "$u" "$f" 2>/dev/null || grep -qFx -- "$u.service" "$f" 2>/dev/null || exit 3 ;;
    *list-units*)
        pat=""; for a in "$@"; do case "$a" in -*|--user|list-units) ;; *) pat=$a ;; esac; done
        [ -n "$pat" ] || exit 0
        while read -r u; do [ -n "$u" ] && [[ "$u" == $pat ]] && echo "$u loaded active running a unit"; done < "$f" 2>/dev/null
        exit 0 ;;
    *) exit 0 ;;
esac
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
    : > "$CC_LOG"; : > "$CC_LABELS"; : > "$CC_ACTIVE"
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

# ====== f-h: a running unit's claim is never taken twice, and never undone
# MEASURED 2026-09-26 15:03-15:04 PDT. cloud.sh claimed audit2 #420 and started
# hakux-lane-cloud-audit2-420; the next call, seconds later, listed #420 again
# (the search-backed `gh pr list --label` lagged claimed:cloud), re-added the
# row, and when systemd-run refused the existing unit its no-session rollback
# removed the RUNNING session's row and claimed:cloud.
cc_row()      { git -C "$CC/origin.git" show board:territory.toml 2>/dev/null | grep -qFx '[lane.cloud-issue-271]'; }
cc_norow()    { ! cc_row; }
cc_label()    { grep -qFx -- "$1" "$CC_LABELS"; }
cc_nolabel()  { ! cc_label "$1"; }
cc_labels_are(){ [ "$(sort "$CC_LABELS" | tr '\n' ' ')" = "$1" ]; }
cc_board()    { git -C "$CC/origin.git" rev-parse board; }

# f: an active unit for the chosen number refuses the claim before anything is
# written. FAILS in the world where the candidate list is trusted as it comes
# from the search index: #271 is listed, so the old code claims it -- a
# systemd-run line, a claimed:cloud label, a board commit.
for u in hakux-lane-cloud-issue-271 hakux-lane-cloud-remediate-271; do
    cc_fixture; cc_seed; echo "$u.service" > "$CC_ACTIVE"; b0=$(cc_board)
    cc_claim
    check "f: with $u active, no session is started for #271" cc_idle
    check "f: with $u active, no label is added" cc_labels_are ""
    check "f: with $u active, the board is not written" test "$(cc_board)" = "$b0"
    check "f: with $u active, no attempt is spent" cc_att 1
    check "f: and the refusal names the unit" cc_said "skip issue #271: unit $u.service is running"
done
# f2: no unit, but the label read BY NUMBER says it is claimed; the lagging
# list still offers it. FAILS in the world where only the list's labels count.
cc_fixture; cc_seed; echo claimed:cloud > "$CC_LABELS"; b0=$(cc_board)
cc_claim
check "f2: claimed:cloud read by number refuses a number the list still offers" cc_idle
check "f2: and the board is not written" test "$(cc_board)" = "$b0"
check "f2: and the refusal says the list lagged" cc_said "skip issue #271: it carries claimed:cloud (read by number; the list lagged)"

# g: the race that still gets past f -- the unit becomes active between the
# check and systemd-run, which is refused. The row and label are the running
# session's and stay. FAILS in the world where every systemd-run failure is
# rolled back: the old code removes the row and claimed:cloud, as on #420.
cc_fixture; cc_seed
cc_claim CC_FAIL_RUN=exists
check "g: the collision starts no second session" cc_idle
check "g: the running session's territory row is still on the board" cc_row
check "g: its claimed:cloud and lane: labels are still on the issue" cc_labels_are "claimed:cloud lane:cloud-271 "
check "g: its snapshot is kept (its ExecStopPost executes from it)" test -d "$CC/work/units/cloud-issue-271"
check "g: this tick spends no attempt" cc_att 1
check "g: and the log calls it a collision, not a failed start" cc_said "this is a collision, not a failed start"

# h: systemd-run fails and no unit is running -- the claim is dropped, as it
# was before this change. FAILS in the world where the fix over-reaches and
# treats any failure as a collision, which strands a claim with no session.
cc_fixture; cc_seed
cc_claim CC_FAIL_RUN=fail
check "h: no session" cc_idle
check "h: the row is removed" cc_norow
check "h: claimed:cloud and lane:cloud-271 are removed" cc_labels_are ""
check "h: the snapshot is removed" test ! -e "$CC/work/units/cloud-issue-271"
check "h: no attempt spent" cc_att 1
check "h: and the log says the claim was dropped" cc_said "dropping the claim so the next tick can pick #271 up again"
unset CC_JOBS
