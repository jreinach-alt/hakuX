# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# $WORK/limits.env must reach the SPAWNED COMMAND LINE, not merely the script.
#
# MEASURED 2026-09-19. lane.sh computed `TURNS="${LANE_TURNS:-150}"` at line 40
# and sourced limits.env at line 57, so the expansion had already run by the
# time anything set LANE_TURNS: nine lanes ended at exactly 151 turns
# (--max-turns 150 plus the final turn) while limits.env had said
# LANE_TURNS=300 all morning. jobs/cloud.sh had the identical shape with
# CLOUD_TURNS. LANE_MAX hid it, because limits.env assigns THAT name directly
# over the literal above the source and so has always worked.
#
# WHY THE ASSERTION IS ON THE COMMAND LINE. A check that reads $TURNS from
# inside lane.sh passes against the broken version for free -- by then the
# source has run and LANE_TURNS really is 300; what was wrong is that the
# value handed to `claude` was captured before it. The systemd-run shim logs
# its whole argv, and `--max-turns N` in that log is the only place the two
# versions differ.
#
# 99 AND NOT 101, WHICH IS WHAT territory.toml GRANTED THIS LANE. The runner's
# loop matches `[0-9][0-9]-*.sh` and hard-exits 2 on anything else, so a
# three-digit prefix does not merely sort wrong -- it ends the whole selftest
# before a single check runs, and the selftest is CI's gate for everything
# under jobs/. Measured here by dropping a 101-probe.sh in beside this file:
# `selftest: .../101-probe.sh is not selftest.d/NN-<concern>.sh and would never
# be sourced`, exit 2, zero checks. NN is not unique (86- and 97- each appear
# twice already), so "the next free number" does not require leaving two
# digits; 99 keeps the position the grant intended and stays legal.
#
# Position is in any case irrelevant to this fragment: 97-board-gate.sh and
# 98-audit-outlet.sh write and truncate the SHARED $HAKUX_WORK/limits.env, and
# this one never touches that file. It builds its own $HAKUX_WORK, its own
# origin and its own log, and depends on no other fragment.

echo "== \$WORK/limits.env reaches the session's command line, not just the script"
LE="$T/limitsenv"
rm -rf "$LE"; mkdir -p "$LE/work/briefs" "$LE/dispatch"

# UNSET IN THE ENVIRONMENT, ALWAYS. The live mitigation on the owner's host is
# `systemctl --user set-environment LANE_TURNS=300`, and line 40 read the
# process environment -- so a run that inherited LANE_TURNS would satisfy
# these checks against the broken code too. The values below (317, 213) are
# also reachable from nowhere else: not the defaults (150, 120), not the
# host's 300, not any number in models.env.
le_run() {   # <log> <limits.env contents> [extra env] -- a real lane.sh start
    local log=$1 limits=$2; shift 2
    printf '%s\n' "$limits" > "$LE/work/limits.env"
    : > "$log"
    # Each run starts from nothing: lane.sh exits 3 on an existing worktree
    # and `worktree add -b` refuses a branch that is already there, and either
    # one would end the run BEFORE systemd-run -- an empty log, which every
    # `! grep` below would read as a pass.
    git -C "$LE/repo" worktree remove --force "$LE/work/wt/turnslane" 2>/dev/null
    rm -rf "$LE/work/wt/turnslane" "$LE/work/attempts/turnslane"
    git -C "$LE/repo" worktree prune 2>/dev/null
    git -C "$LE/repo" branch -qD lane/turnslane 2>/dev/null
    ( env -u LANE_TURNS -u CLOUD_TURNS "$@" \
        HAKUX_WORK="$LE/work" HAKUX_REPO_DIR="$LE/repo" DISPATCH_DIR="$LE/dispatch" \
        SELFTEST_GH_LOG="$log" \
        bash "$TESTING/lane.sh" start turnslane "$LE/brief.md" 9401 ) >/dev/null 2>&1
}
# CALLED IN THE PARENT SHELL, never from inside a `bash -c`: a function is not
# exported, so `[ "$(turns_on_cmdline ...)" = 317 ]` in a child shell compares
# against the empty output of a command-not-found and can never be green.
turns_on_cmdline() {   # <log> -> the N in the --max-turns N systemd-run actually spawned
    sed -n 's/.*--max-turns \([0-9][0-9]*\).*/\1/p' "$1" | head -1
}

git init -q -b master "$LE/origin"
git -C "$LE/origin" -c user.email=s@t -c user.name=s commit -q --allow-empty -m base
git clone -q "$LE/origin" "$LE/repo"
printf '# a brief for the turn-cap selftest\n' > "$LE/brief.md"

le_run "$LE/override.log" 'LANE_TURNS=317'
check "LANE_TURNS in \$WORK/limits.env reaches the lane's --max-turns" \
    test "$(turns_on_cmdline "$LE/override.log")" = 317
# Both halves. "317 is present" would also pass if the script spawned two
# sessions, and "150 is absent" would pass if it spawned none -- which is how
# a start that exits before systemd-run reads as a green override.
check "...and the 150 default is not what was spawned" \
    bash -c '! grep -q -- "--max-turns 150" "$1"' _ "$LE/override.log"

# THE DEFAULT STILL APPLIES. Without this, "always 317" and "reads the file"
# are the same green, and the grep above proves nothing about the mechanism.
le_run "$LE/default.log" ''
check "with no dial set, the compiled-in default is what is spawned" \
    test "$(turns_on_cmdline "$LE/default.log")" = 150

# PRECEDENCE, and the reason it is asserted: until the fix, the ONLY thing
# holding lanes at 300 was `systemctl --user set-environment LANE_TURNS=300`
# on the owner's host -- a runtime patch that dies with the systemd user
# session and is invisible to anyone reading the repository. The file has to
# win, or clearing that manager environment silently changes the number and
# leaving it there makes two sources of truth that agree today.
le_run "$LE/precedence.log" 'LANE_TURNS=317' LANE_TURNS=999
check "the file wins over the process environment, as it already did for LANE_MAX" \
    test "$(turns_on_cmdline "$LE/precedence.log")" = 317

# The shape, anchored on the assignment rather than on any wording near it:
# the comments above both lines quote the broken form verbatim, so an
# unanchored `grep -n 'TURNS='` matches the prose describing the bug. ^TURNS=
# cannot, and "exactly one" is what stops a second assignment drifting back up.
le_order() {   # <script> -- the sole ^TURNS= line sits below the limits.env source
    local f=$1 s t
    s=$(grep -n 'limits.env" \] && \.' "$f" | head -1 | cut -d: -f1)
    t=$(grep -c '^TURNS=' "$f")
    [ "$t" = 1 ] || return 1
    t=$(grep -n '^TURNS=' "$f" | cut -d: -f1)
    [ -n "$s" ] && [ "$t" -gt "$s" ]
}
check "lane.sh has exactly one TURNS= assignment and it is below the source" le_order "$TESTING/lane.sh"
check "cloud.sh has exactly one TURNS= assignment and it is below the source" le_order "$HERE/cloud.sh"

# ------------------------------------------------- the same dial, the audit outlet
# cloud.sh spawns through the same systemd-run, so the same log is the oracle.
# A full claim is what reaches it: `cloud.sh list` prints the cap and exits
# long before any command line exists, and the cap is LANE_MAX -- the variable
# that was never broken.
LEC="$LE/cloud"; mkdir -p "$LEC/bin"
cat > "$LEC/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        [[ "$args" == *"--label needs-remediation"* ]] || exit 0
        printf '102\tlane/blitsafe\tblit: clamp the destination rect\n'; exit 0 ;;
    "pr view")
        echo '{"body": "Lane: blitsafe            Issue: #88", "closingIssuesReferences": [{"number": 88}], "files": [{"path": "docs/lanes/blitsafe/NOTES.md"}]}'
        exit 0 ;;
    "api "*)
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && exit 0
        exit 0 ;;
esac
exit 0
EOF
chmod +x "$LEC/bin/gh"

git init -q --bare "$LEC/origin.git"
git init -q "$LEC/repo"
git -C "$LEC/repo" remote add origin "$LEC/origin.git"
git -C "$LEC/repo" config user.email t@example.invalid
git -C "$LEC/repo" config user.name t
git -C "$LEC/repo" checkout -q -b master
echo "the trunk" > "$LEC/repo/README.md"
git -C "$LEC/repo" add -A && git -C "$LEC/repo" commit -qm "fixture: master"
git -C "$LEC/repo" push -q origin master
git -C "$LEC/repo" checkout -q -b lane/blitsafe
echo "a lane's work" > "$LEC/repo/blit.txt"
git -C "$LEC/repo" add -A && git -C "$LEC/repo" commit -qm "fixture: the PR's branch"
git -C "$LEC/repo" push -q origin lane/blitsafe
git -C "$LEC/repo" checkout -q master

lec_run() {   # <log> <limits.env contents> [extra env] -- a real cloud.sh claim
    local log=$1 limits=$2; shift 2
    printf '%s\n' "$limits" > "$LEC/work/limits.env"
    : > "$log"
    git -C "$LEC/repo" worktree remove --force "$LEC/work/wt/cloud-remediate-102" 2>/dev/null
    rm -rf "$LEC/work/wt/cloud-remediate-102" "$LEC/work/attempts/cloud-remediate-102"
    git -C "$LEC/repo" worktree prune 2>/dev/null
    ( env -u LANE_TURNS -u CLOUD_TURNS "$@" \
        PATH="$LEC/bin:$PATH" HAKUX_WORK="$LEC/work" HAKUX_REPO_DIR="$LEC/repo" \
        SELFTEST_GH_LOG="$log" \
        bash "$HERE/cloud.sh" ) >/dev/null 2>&1
}
mkdir -p "$LEC/work/briefs"

lec_run "$LEC/override.log" 'CLOUD_TURNS=213'
check "CLOUD_TURNS in \$WORK/limits.env reaches the audit session's --max-turns" \
    test "$(turns_on_cmdline "$LEC/override.log")" = 213
check "...and the 120 default is not what was spawned" \
    bash -c '! grep -q -- "--max-turns 120" "$1"' _ "$LEC/override.log"
lec_run "$LEC/default.log" ''
check "with no dial set, cloud.sh spawns its compiled-in default" \
    test "$(turns_on_cmdline "$LEC/default.log")" = 120
lec_run "$LEC/precedence.log" 'CLOUD_TURNS=213' CLOUD_TURNS=999
check "the file wins over the process environment for the audit outlet too" \
    test "$(turns_on_cmdline "$LEC/precedence.log")" = 213

git -C "$LEC/repo" worktree remove --force "$LEC/work/wt/cloud-remediate-102" 2>/dev/null
git -C "$LE/repo" worktree remove --force "$LE/work/wt/turnslane" 2>/dev/null
unset LE LEC
unset -f le_run lec_run le_order turns_on_cmdline
