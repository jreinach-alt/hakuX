# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# cloud.sh: a PR is not claimed while its own lane session is still running on
# its head branch.
#
# FENCED like 73-: its own $HAKUX_WORK, its own gh and systemctl shims on its
# own PATH, and a real git worktree at $HAKUX_WORK/wt/<lane>. `cloud.sh list`
# is the oracle; it claims nothing and starts nothing.
#
# $CL_JOBS picks the jobs/ tree under test (default: this one), so the legs can
# be run against a cloud.sh with the lane check reverted, which is how they
# were shown to fail before the fix (docs/lanes/cloudlaneguard/NOTES.md).

echo "== cloud.sh: a PR whose lane is still running on its head is not claimed"
# MEASURED 2026-09-27. PR #523 (lane/thermal507-power) was claimed for audit1
# at 01:24Z and for remediate at 01:34Z while hakux-lane-thermal507 was active
# in $WORK/wt/thermal507 on that branch. Two sessions committed to it minutes
# apart (fe5940a6e2, 20502ec594). unit_busy only looked at hakux-lane-cloud-*.
CL="$T/cloudlane"; CL_JOBS="${CL_JOBS:-$HERE}"
rm -rf "$CL"; mkdir -p "$CL/bin" "$CL/work/wt"
CL_ACTIVE="$CL/active"; export CL_ACTIVE

# gh: ONE claimable unit, needs-audit-1 PR #523. The REST head read answers
# $CL_HEAD (the PR's real head by default), or fails when $CL_API_FAIL is set.
# The list row carries a head too, so the fail-closed leg proves the REST
# failure alone holds the PR.
cat > "$CL/bin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"
case "$1 $2" in
    "pr list")
        [[ "$args" == *"--label needs-audit-1"* ]] || exit 0
        printf '523\tlane/thermal507-power\tthermal507: the power read\n'; exit 0 ;;
    "issue list") exit 0 ;;
    "api "*)
        [[ "$args" == *"/labels"* ]] && exit 0
        if [[ "$args" == *"/pulls/523"* ]]; then
            [ -n "${CL_API_FAIL:-}" ] && { echo "HTTP 502" >&2; exit 1; }
            echo "${CL_HEAD:-lane/thermal507-power}"
        fi
        exit 0 ;;
esac
exit 0
EOF
# systemctl: a unit is active iff $CL_ACTIVE names it; list-units matches its
# glob as systemd does, with or without the .service suffix.
cat > "$CL/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
f="${CL_ACTIVE:?}"
case "$*" in
    *is-active*) u="${*: -1}"; grep -qFx -- "$u.service" "$f" 2>/dev/null || exit 3 ;;
    *list-units*)
        pat=""; for a in "$@"; do case "$a" in -*|--user|list-units) ;; *) pat=$a ;; esac; done
        [ -n "$pat" ] || exit 0
        while read -r u; do
            [ -n "$u" ] || continue
            if [[ "$u" == $pat ]] || [[ "${u%.service}" == $pat ]]; then echo "$u loaded active running a unit"; fi
        done < "$f"
        exit 0 ;;
esac
exit 0
EOF
chmod +x "$CL/bin/"*
CLPATH="$CL/bin:$PATH"

# A repo with the PR's branch and another, and the lane's worktree at
# $WORK/wt/thermal507 -- where lane.sh puts hakux-lane-thermal507's tree.
git init -q "$CL/repo"
git -C "$CL/repo" config user.email t@example.invalid
git -C "$CL/repo" config user.name t
git -C "$CL/repo" checkout -q -b master
echo one > "$CL/repo/README.md"; git -C "$CL/repo" add -A && git -C "$CL/repo" commit -qm "fixture: master"
git -C "$CL/repo" branch lane/thermal507-power
git -C "$CL/repo" branch lane/thermal507-other
git -C "$CL/repo" worktree add -q "$CL/work/wt/thermal507" lane/thermal507-power 2>/dev/null

cl_list() {   # [env assignments...] -> cloud.sh list's output, fenced
    env PATH="$CLPATH" HAKUX_WORK="$CL/work" HAKUX_REPO_DIR="$CL/repo" GH_REPO=example/hakux "$@" \
        bash "$CL_JOBS/cloud.sh" list 2>&1
}
cl_held()      { grep -qF "skip audit1 #523: its lane hakux-lane-thermal507 is still running on lane/thermal507-power" <<< "$cl_out"; }
cl_claimable() { grep -q "would claim audit1 #523" <<< "$cl_out"; }
cl_unclaimed() { ! cl_claimable; }

# a: the lane unit is active and its worktree is on the PR's head -> held.
# FAILS in the world where only hakux-lane-cloud-* units are asked (the #523
# claims): the old held_why says nothing and list says "would claim".
echo hakux-lane-thermal507.service > "$CL_ACTIVE"
cl_out=$(cl_list)
check "a: with hakux-lane-thermal507 active on lane/thermal507-power, #523 is not claimable" cl_unclaimed
check "a: and list names the lane and the branch" cl_held

# b: the same worktree, the unit inactive -> claimable. FAILS in the world
# where a worktree on the branch is enough, which would hold every PR whose
# lane ended with its tree left behind (every one, until a fold prunes it).
: > "$CL_ACTIVE"
cl_out=$(cl_list)
check "b: with the lane unit inactive, #523 is claimable" cl_claimable

# c: the unit active, its worktree on a different branch -> claimable. FAILS
# in the world where any running lane of that name holds the PR.
echo hakux-lane-thermal507.service > "$CL_ACTIVE"
git -C "$CL/work/wt/thermal507" checkout -q lane/thermal507-other
cl_out=$(cl_list)
check "c: with the lane unit active on another branch, #523 is claimable" cl_claimable
git -C "$CL/work/wt/thermal507" checkout -q lane/thermal507-power

# d: a cloud-* unit whose name has a worktree on the branch is not "its lane":
# the cloud session's own claims are unit_busy's, keyed by number. Here no
# cloud unit for #523 runs, so the PR stays claimable.
mv "$CL/work/wt/thermal507" "$CL/work/wt/cloud-audit1-999" 2>/dev/null
git -C "$CL/repo" worktree repair "$CL/work/wt/cloud-audit1-999" >/dev/null 2>&1
echo hakux-lane-cloud-audit1-999.service > "$CL_ACTIVE"
cl_out=$(cl_list)
check "d: a cloud-* unit on the branch is not taken for the PR's lane" cl_claimable
mv "$CL/work/wt/cloud-audit1-999" "$CL/work/wt/thermal507"
git -C "$CL/repo" worktree repair "$CL/work/wt/thermal507" >/dev/null 2>&1

# e: FAIL CLOSED. The head read by number fails; the PR is held even with no
# lane running, as a failed label read holds it.
: > "$CL_ACTIVE"
cl_out=$(cl_list CL_API_FAIL=1)
check "e: a head that cannot be read by number holds the PR" cl_unclaimed
check "e: and list says why" grep -qF "skip audit1 #523: its head branch could not be read by number" <<< "$cl_out"

echo "== cloud.sh: an issue outside the board's focus is not offered"
# MEASURED 2026-09-27 20:07 PDT. With BOARD_FOCUS_LABEL=fps-focus in
# limits.env, `cloud.sh list` said "would claim issue #527" (labels
# accuracy,needs-triage,cloud): board.sh drops a non-focus issue and this
# outlet did not. This gh shim offers no PR, so the issue pickup is reached,
# and answers `issue list` with $CL_ISSUES, rows as issue_cloud's --jq writes
# them (num, two tabs, title, a unit separator, the labels).
cat > "$CL/bin/gh" <<'EOF'
#!/usr/bin/env bash
case "$1 $2" in
    "issue list") [[ "$*" == *"--label cloud"* ]] && printf '%b' "${CL_ISSUES:-}"; exit 0 ;;
esac
exit 0
EOF
chmod +x "$CL/bin/gh"
: > "$CL_ACTIVE"
cl_527='527\t\taccuracy: a non-focus issue\x1faccuracy,needs-triage,cloud\n'
cl_530='530\t\tfps: a focus issue\x1fcloud,fps-focus\n'
cl_no527()   { ! grep -q "would claim issue #527" <<< "$cl_out"; }
cl_skip527() { grep -qFx "skip issue #527: not in the fps-focus focus (BOARD_FOCUS_LABEL=fps-focus)" <<< "$cl_out"; }

# f: the focus in limits.env (where board.sh reads it), a non-focus issue and
# a focus one -> the focus one is offered and the other named as dropped.
# FAILS in the world before the filter: #527 is older, so list says
# "would claim issue #527".
echo "BOARD_FOCUS_LABEL=fps-focus" > "$CL/work/limits.env"
cl_out=$(cl_list CL_ISSUES="$cl_527$cl_530")
check "f: with the fps-focus focus, non-focus #527 is not offered" cl_no527
check "f: and list names the drop in one line" cl_skip527
check "f: and the focus issue #530 is offered" grep -q "would claim issue #530" <<< "$cl_out"

# g: the focus, and only the non-focus issue open -> nothing is claimed.
cl_out=$(cl_list CL_ISSUES="$cl_527")
check "g: with only non-focus #527 open, nothing is claimed" grep -qx "nothing to claim" <<< "$cl_out"

# h: no focus set -> #527 is offered as before. FAILS in the world where the
# filter drops every issue whatever the focus.
rm -f "$CL/work/limits.env"
cl_out=$(cl_list CL_ISSUES="$cl_527$cl_530")
check "h: with no focus set, #527 is offered" grep -q "would claim issue #527" <<< "$cl_out"
unset CL_JOBS cl_out cl_527 cl_530
