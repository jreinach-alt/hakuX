# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# cloud.sh: the unit's tail must run however the unit ends, and must not read
# its scripts out of a directory another job moves.
#
# 72 because it belongs with 70- and 71- (the same script) and must run before
# 98-audit-outlet.sh, which drives the same script against PR #102. It uses PR
# #141 -- the number of the unit that was actually stranded -- so it shares no
# attempt counter, no worktree and no label state with either neighbour.
# Depends on no other fragment: its own git remote, its own repo, its own
# gh/systemd-run/systemctl/claude shims, its own PATH. It never touches this
# repository, the shared gh shim or $SELFTEST_GH_LOG.
#
# WHAT IS REAL AND WHAT IS EMULATED. Real: cloud.sh, gh-label.sh, git, the
# board branch, the territory row, the worktree, the snapshot copy, and the
# kill. Emulated: systemd, in ONE property and deliberately no more --
# `ExecStopPost=` runs after the main process terminates, whatever terminated
# it. tl_run_unit() below is that emulation and says so at the line that
# implements it. A real unit cannot be started here: CI has no user manager at
# all, and the session that wrote this file could not reach the host's.

echo "== cloud.sh: the unit's tail runs however the unit ends, from a path nothing moves"
# MEASURED 2026-09-19. cloud.sh built its unit as one `bash -c` string ending
# `...; python3 "$JOBS/summarise_run.py" ...; bash "$JOBS/cloud.sh" finish ...`
# and $JOBS was $WORK/board-wt/docs/testing/jobs -- the board's worktree, which
# board.sh re-checkouts on every tick. That worktree spent ~100 minutes
# detached on the orphan `board` branch, which has no docs/ at all.
# cloud-audit2-141 and cloud-remediate-148 both ran to completion, both
# SUCCEEDED, both set their successor label -- and both tails died on
# `python3: can't open file '.../board-wt/docs/testing/jobs/summarise_run.py'`,
# taking the `finish` after them down with them. `claimed:cloud` was never
# removed; pr_by_label excludes a claimed PR; both were invisible to the outlet
# for six and a half hours, until a person looked.
TL="$T/cloudtail"; TL_UNITS="$TL/units"; TL_LOG="$TL/log"; TL_LABELS="$TL/labels"
TL_ACTIVE="$TL/active"; TL_HOLD="$TL/hold"; TL_KILLED="$TL/killed"; TL_STARTED="$TL/started"
rm -rf "$TL"; mkdir -p "$TL/bin" "$TL_UNITS"
export TL_UNITS TL_LOG TL_LABELS TL_ACTIVE TL_HOLD TL_KILLED TL_STARTED
: > "$TL_LOG"; : > "$TL_LABELS"; : > "$TL_ACTIVE"

# ------------------------------------------------------------------- the shims
#
# gh, WITH STATE. The property under test is "the claim is released", which is
# a change to the labels a PR carries -- so the shim keeps them in a file that
# POST appends to and DELETE removes from, and the checks read that file. A
# shim answering from a variable the check itself set would be the check
# writing down its own answer; here `finish` has to really remove the label.
#
# `pr list` reads that same file, including pr_by_label's own skip of a PR
# carrying claimed:cloud -- the filter lives in a --jq expression the shim does
# not run, and it is the exact mechanism that made #141 invisible, so it is
# emulated rather than assumed.
cat > "$TL/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "${TL_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        lbl=$(sed -n 's/.*--label \([^ ]*\).*/\1/p' <<< "$args")
        [ -n "$lbl" ] || exit 0
        grep -qFx "$lbl" "${TL_LABELS:?}" || exit 0
        grep -qFx "claimed:cloud" "$TL_LABELS" && exit 0
        grep -qFx "blocked:needs-owner" "$TL_LABELS" && exit 0
        printf '141\tlane/auditme\taudit: the pass-2 verification of #141\n'; exit 0 ;;
    "pr view")
        printf '{"body": "Lane: auditme", "closingIssuesReferences": [], "files": []}\n'; exit 0 ;;
    # The BODY is logged, not just the number: cloud.sh comments on this PR at
    # claim too, so a count of "comments on #141" counts the wrong thing.
    "pr comment") echo "COMMENT $3 ${*: -1}" >> "$TL_LOG"; exit 0 ;;
    "api "*)
        if [[ "$args" == *"-X POST"* && "$args" == *"/labels"* ]]; then
            for a in "$@"; do [[ "$a" == labels\[\]=* ]] && echo "${a#labels[]=}" >> "${TL_LABELS:?}"; done
            exit 0
        fi
        if [[ "$args" == *"-X DELETE"* && "$args" == *"/labels/"* ]]; then
            l=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.unquote(sys.argv[1].rsplit("/",1)[1]))' "${*: -1}")
            grep -vFx -- "$l" "${TL_LABELS:?}" > "$TL_LABELS.n"; mv "$TL_LABELS.n" "$TL_LABELS"
            exit 0
        fi
        [[ "$args" == *"/labels"* ]] && { cat "${TL_LABELS:?}"; exit 0; }
        exit 0 ;;
esac
exit 0
EOF

# systemd-run: RECORDED, NOT RUN -- which is what the real one does too, since
# it returns as soon as the unit is queued. tl_run_unit() below starts it, so
# that the world can change BETWEEN the dispatch and the session. That gap is
# the entire incident: the board tick that moved the worktree ran while the
# session was already 22 minutes into its work.
cat > "$TL/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${TL_LOG:?}"
u=""; wd="."; sp=""; ev=()
while [ $# -gt 0 ]; do
    case "$1" in
        --unit) shift; u=$1 ;;
        --unit=*) u=${1#--unit=} ;;
        --setenv=*) ev+=("${1#--setenv=}") ;;
        --working-directory=*) wd=${1#--working-directory=} ;;
        --property=ExecStopPost=*) sp=${1#--property=ExecStopPost=} ;;
        -p) shift; [[ "$1" == ExecStopPost=* ]] && sp=${1#ExecStopPost=} ;;
        --*) ;;
        *) break ;;
    esac
    shift
done
[ -n "$u" ] || { echo "systemd-run: no --unit" >&2; exit 1; }
# systemd will not LOAD a unit whose Exec* command does not begin with an
# ABSOLUTE PATH; it does not fall back to $PATH the way a shell does. A stub
# that quietly accepted `bash /some/script` would certify a unit the real
# manager refuses outright -- the fix would then be inert on the host in the
# loudest way possible, and green here. So the stub refuses it too.
if [ -n "$sp" ] && [[ "${sp%% *}" != /* ]]; then
    echo "REFUSED ExecStopPost is not an absolute path: $sp" >> "$TL_LOG"; exit 1
fi
mkdir -p "${TL_UNITS:?}"
printf '%s' "$wd" > "$TL_UNITS/$u.wd"
printf '%s' "$sp" > "$TL_UNITS/$u.stop"
: > "$TL_UNITS/$u.env"; [ "${#ev[@]}" -gt 0 ] && printf '%s\0' "${ev[@]}" > "$TL_UNITS/$u.env"
printf '%s\0' "$@" > "$TL_UNITS/$u.exec"
exit 0
EOF

# systemctl: a unit is active iff $TL_ACTIVE names it. The snapshot sweep asks
# exactly this, and a shim answering "active" to everything (the shared one
# does) would make the sweep a no-op and its check vacuous.
cat > "$TL/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) grep -qFx "${*: -1}" "${TL_ACTIVE:-/nonexistent}" 2>/dev/null ;;
    *) exit 0 ;;
esac
EOF

# claude: a session that SUCCEEDS and sets its successor label, because that is
# what #141's and #148's did. A tail that only had to fire for a session which
# FAILED would be a far smaller claim than the one being made here.
#
# It blocks on $TL_HOLD when the scenario is a kill, and refuses to label after
# one. The alternative -- a fixed sleep -- leaves an orphan that labels the PR
# seconds into the NEXT scenario, which is a flake that reads like a defect.
cat > "$TL/bin/claude" <<'EOF'
#!/usr/bin/env bash
: > "${TL_STARTED:?}"
n=0; while [ -e "${TL_HOLD:?}" ] && [ "$n" -lt 400 ]; do sleep 0.05; n=$((n+1)); done
[ -e "${TL_KILLED:?}" ] && exit 143
gh api -X POST "repos/$GH_REPO/issues/141/labels" -f "labels[]=needs-remediation" >/dev/null 2>&1
printf '{"type":"result","subtype":"success","num_turns":91,"total_cost_usd":1.5}\n'
EOF
chmod +x "$TL/bin/"*
TLPATH="$TL/bin:$PATH"

# ---------------------------------------------------------------- the fixture
# A real origin with master, the PR's branch, and the orphan board branch the
# territory row goes to -- so the row this unit writes at claim, and the row
# its tail removes, are both real pushes to a real branch.
tl_fixture() {
    rm -rf "$TL/origin.git" "$TL/repo"
    git init -q --bare "$TL/origin.git"
    git init -q "$TL/repo"
    git -C "$TL/repo" remote add origin "$TL/origin.git"
    git -C "$TL/repo" config user.email t@example.invalid
    git -C "$TL/repo" config user.name t
    git -C "$TL/repo" checkout -q -b master
    echo "the trunk" > "$TL/repo/README.md"
    git -C "$TL/repo" add -A && git -C "$TL/repo" commit -qm "fixture: master"
    git -C "$TL/repo" push -q origin master
    git -C "$TL/repo" checkout -q -b lane/auditme
    echo "a lane's work" > "$TL/repo/work.txt"
    git -C "$TL/repo" add -A && git -C "$TL/repo" commit -qm "fixture: the PR's branch"
    git -C "$TL/repo" push -q origin lane/auditme
    git -C "$TL/repo" checkout -q --orphan board
    git -C "$TL/repo" rm -rq --cached . >/dev/null 2>&1
    rm -f "$TL/repo/README.md" "$TL/repo/work.txt"
    printf '# a fixture board\nwave = 7\nupdated_utc = "2026-09-19T00:00:00Z"\n\n[free]\nfiles = []\n' \
        > "$TL/repo/territory.toml"
    git -C "$TL/repo" add -A && git -C "$TL/repo" commit -qm "fixture: the board"
    git -C "$TL/repo" push -q origin board
    git -C "$TL/repo" checkout -q master
}
# NEGATIONS AS FUNCTIONS, NOT AS `bash -c '! ...'`. A `!` over a helper inside
# a child shell is green against anything, because the helper is not defined
# there -- `check` calls these in THIS shell, where they mean what they say.
tl_row()       { git -C "$TL/origin.git" show "board:territory.toml" 2>/dev/null | grep -q '^\[lane.cloud-audit2-141\]'; }
tl_norow()     { ! tl_row; }
tl_has()       { grep -qFx "$1" "$TL_LABELS"; }
tl_hasnt()     { ! grep -qFx "$1" "$TL_LABELS"; }
# The unfinished-session notice specifically -- the one comment `finish` posts,
# and the only step of it that does not cancel itself on a second run.
tl_comments()  { [ "$(grep -c '^COMMENT 141 .*without setting a next state' "$TL_LOG")" = "$1" ]; }
tl_claimable() { env PATH="$TLPATH" HAKUX_REPO_DIR="$TL/repo" bash "$HERE/cloud.sh" list 2>&1 | grep -q "would claim .* #141"; }
tl_invisible() { ! tl_claimable; }

# ---------------------------------------------------------------- the mutants
#
# TWO DEFECTS, SO TWO MUTANTS, each reverting exactly one of them -- and a
# third reverting both, which is the file as it stood on 2026-09-19. Reverting
# one at a time is what shows they are independent: neither fix on its own
# releases the claim in the world the other one covers.
#
# EVERY SUBSTITUTION IS ASSERTED TO MATCH ONCE. A mutant whose edit silently
# failed to apply is the fixed file under another name, and it passes the check
# it was built to fail -- for free, invisibly, and forever after.
tl_mutate() {   # <tail|path|both> <file>
    python3 - "$2" "$1" <<'PY'
import sys
path, mode = sys.argv[1:3]
t = open(path, encoding="utf-8").read()


def sub1(a, b):
    global t
    n = t.count(a)
    if n != 1:
        raise SystemExit("mutant %s: %r appears %d times, not once -- refusing to "
                         "build a mutant that does not mutate" % (mode, a[:60], n))
    t = t.replace(a, b)


if mode in ("tail", "both"):
    # The tail back where it was: the last command of the bash -c string.
    sub1('    --property=ExecStopPost="/bin/bash $SJOBS/cloud.sh finish $kind $num" \\\n', '')
    sub1('; exit \\$rc" \\\n',
         '; bash \'$SJOBS/cloud.sh\' finish $kind $num >/dev/null 2>&1; exit \\$rc" \\\n')
if mode in ("path", "both"):
    # The unit reading its scripts out of the board's mutable worktree again.
    sub1('SJOBS="$SNAP/jobs"', 'SJOBS="$JOBS"')
open(path, "w", encoding="utf-8").write(t)
PY
}

# THE BOARD'S WORKTREE, the mutable directory at the centre of all this.
# cloud.sh is run FROM here, so its own $JOBS resolves here -- exactly as on
# the host, where board.sh dispatches out of $WORK/board-wt.
tl_stage() {   # <none|tail|path|both>
    rm -rf "$TL/board-wt"
    mkdir -p "$TL/board-wt/docs/testing"
    cp -a "$HERE" "$TL/board-wt/docs/testing/jobs"
    cp -a "$TESTING/lane.sh" "$TL/board-wt/docs/testing/lane.sh"
    [ "$1" = none ] || tl_mutate "$1" "$TL/board-wt/docs/testing/jobs/cloud.sh"
}
tl_board_tick() { rm -rf "$TL/board-wt/docs"; }   # what board.sh:185 does, every tick

# ------------------------------------------------------------- the unit itself
tl_run_unit() {   # <unit> <run|kill>
    local u=$1 md=${2:-run} wd sp rc=0 p n; local -a ev=() ex=()
    [ -f "$TL_UNITS/$u.exec" ] || return 127
    wd=$(cat "$TL_UNITS/$u.wd"); sp=$(cat "$TL_UNITS/$u.stop")
    mapfile -d '' -t ev < "$TL_UNITS/$u.env"
    mapfile -d '' -t ex < "$TL_UNITS/$u.exec"
    rm -f "$TL_KILLED" "$TL_STARTED" "$TL_HOLD"
    if [ "$md" = kill ]; then
        : > "$TL_HOLD"
        # `exec`, so $p is the unit's own `bash -c` and not a subshell wrapping
        # it: killing the wrapper would leave the very shell whose trailing
        # `; finish` is under test alive to run it.
        ( cd "$wd" && exec env PATH="$TLPATH" "${ev[@]}" "${ex[@]}" ) >/dev/null 2>&1 &
        p=$!
        n=0; while [ ! -e "$TL_STARTED" ] && [ "$n" -lt 400 ]; do sleep 0.05; n=$((n+1)); done
        : > "$TL_KILLED"                 # set BEFORE the hold is released
        kill -9 "$p" 2>/dev/null; wait "$p" 2>/dev/null; rc=$?
        rm -f "$TL_HOLD"                 # the session's orphan now exits without labelling
    else
        ( cd "$wd" && env PATH="$TLPATH" "${ev[@]}" "${ex[@]}" ) >/dev/null 2>&1; rc=$?
    fi
    # THE ONE PROPERTY OF systemd EMULATED HERE, and the only one this fix
    # rests on. systemd.service(5) on ExecStopPost=: "Additional commands that
    # are executed after the service is stopped ... also run if the service
    # failed to start", and they run when the main process was killed by a
    # signal too. So: after the main process ends, unconditionally, ignoring
    # $rc. Nothing else below this line is systemd.
    #
    # `env -i` because A UNIT'S ENVIRONMENT IS ITS OWN: systemd gives an Exec*
    # line the unit's Environment= and the manager's, NOT the environment of
    # whatever invoked systemd-run. Inheriting here would hide a --setenv
    # cloud.sh forgot to pass -- and the tail removes a territory row from
    # $HAKUX_REPO_DIR, so without that one it would quietly go looking in the
    # owner's real checkout. TL_* are this fixture's own wiring; they stand in
    # for the host, and are not part of the unit's configuration.
    [ -n "$sp" ] || return "$rc"
    ( cd "$wd" 2>/dev/null || cd /
      env -i PATH="$TLPATH" HOME="$HOME" TL_LOG="$TL_LOG" TL_LABELS="$TL_LABELS" \
             TL_UNITS="$TL_UNITS" TL_ACTIVE="$TL_ACTIVE" "${ev[@]}" $sp
    ) >> "$TL_LOG" 2>&1
    return "$rc"
}

tl_claim() {   # a real dispatch, out of the staged board worktree
    rm -f "$HAKUX_WORK/attempts/cloud-audit2-141"
    rm -rf "$HAKUX_WORK/units" "$TL_UNITS"; mkdir -p "$TL_UNITS"
    git -C "$TL/repo" worktree remove --force "$HAKUX_WORK/wt/cloud-audit2-141" 2>/dev/null
    rm -rf "$HAKUX_WORK/wt/cloud-audit2-141"
    printf 'needs-audit-2\n' > "$TL_LABELS"; : > "$TL_LOG"
    env PATH="$TLPATH" HAKUX_REPO_DIR="$TL/repo" \
        bash "$TL/board-wt/docs/testing/jobs/cloud.sh" >> "$TL_LOG" 2>&1
}
tl_cleanup() {
    git -C "$TL/repo" worktree remove --force "$HAKUX_WORK/wt/cloud-audit2-141" 2>/dev/null
    rm -rf "$HAKUX_WORK/wt/cloud-audit2-141" "$HAKUX_WORK/units"
    rm -f "$HAKUX_WORK/attempts/cloud-audit2-141"
}

# ================================================================== the claim
tl_fixture; tl_stage none
tl_claim
check "the outlet claims #141 and labels it claimed:cloud" tl_has claimed:cloud
check "and writes its territory row before the unit starts" tl_row
check "while claimed, the PR is invisible to the outlet -- which is the six-hour failure" tl_invisible
check "the unit is queued" test -f "$TL_UNITS/hakux-lane-cloud-audit2-141.exec"
check "its tail is an ExecStopPost=, not the last command of the bash -c string" \
    test -s "$TL_UNITS/hakux-lane-cloud-audit2-141.stop"
check "and nothing calls finish inside the unit's command string, so it fires once" bash -c '
    tr "\0" "\n" < "$1" | grep -q "cloud.sh. finish" && exit 1; exit 0' _ \
    "$TL_UNITS/hakux-lane-cloud-audit2-141.exec"
# THE SECOND FIX, checked as a path property before it is checked as behaviour:
# no part of the unit -- not the summariser, not the role file, not the
# allowlist, not the tail -- may name the board's worktree.
check "no part of the unit names the board worktree; all of it is the snapshot" bash -c '
    { tr "\0" "\n" < "$1"; cat "$2"; } | grep -q "board-wt" && exit 1
    grep -qx "/bin/bash $3/units/cloud-audit2-141/jobs/cloud.sh finish audit2 141" "$2"' _ \
    "$TL_UNITS/hakux-lane-cloud-audit2-141.exec" "$TL_UNITS/hakux-lane-cloud-audit2-141.stop" "$HAKUX_WORK"
check "the snapshot is a real copy, with the layout its own cloud.sh derives \$T from" bash -c '
    [ -f "$1/units/cloud-audit2-141/jobs/summarise_run.py" ] &&
    [ ! -L "$1/units/cloud-audit2-141/jobs" ] &&
    [ -f "$1/units/cloud-audit2-141/lane.sh" ]' _ "$HAKUX_WORK"

# ====================================== a: the chain dies before it reaches the tail
#
# THE INCIDENT, REPRODUCED. A board tick moves its worktree while the session
# runs; the session then SUCCEEDS and sets needs-remediation; and the unit's
# command string reaches a summariser that is no longer there.
tl_board_tick
tl_run_unit hakux-lane-cloud-audit2-141 run
check "a: the session set its successor label, exactly as #141's did" tl_has needs-remediation
check "a: the claim is released even though the worktree moved under the unit" tl_hasnt claimed:cloud
check "a: and the state label it was claimed under is cleared" tl_hasnt needs-audit-2
check "a: the territory row does not outlive the unit" tl_norow
check "a: so the outlet can see the PR again, in its next state" tl_claimable
tl_cleanup

# ---- the same world, against the file as it stood on 2026-09-19: RED.
# Without this the check above proves nothing. A claim released under a mutant
# that removes the mechanism is a claim released by something else.
tl_fixture; tl_stage both
tl_claim
tl_board_tick
tl_run_unit hakux-lane-cloud-audit2-141 run
check "a-MUTANT(both): with the in-band tail and \$JOBS restored, the claim is stranded" tl_has claimed:cloud
check "a-MUTANT(both): needs-audit-2 stays too, so the outlet cannot even retry it" tl_has needs-audit-2
check "a-MUTANT(both): the territory row is left behind, a lane with no agent" tl_row
check "a-MUTANT(both): and the PR is invisible to every future tick -- the six hours" tl_invisible
tl_cleanup

# ---- and each fix alone is load-bearing: reverting either one strands it.
tl_fixture; tl_stage path
tl_claim
tl_board_tick
tl_run_unit hakux-lane-cloud-audit2-141 run
check "a-MUTANT(path): ExecStopPost cannot save a tail that names the moved worktree" tl_has claimed:cloud
tl_cleanup

# ====================================== b: the unit is killed mid-session
#
# THE CASE AN IN-BAND TAIL CAN NEVER COVER. No `;` runs after SIGKILL, so this
# is not a matter of ordering the chain better -- it is why the tail has to be
# a property of the unit. The worktree is left alone here: the only thing
# wrong is that the session did not get to finish.
tl_fixture; tl_stage none
tl_claim
tl_run_unit hakux-lane-cloud-audit2-141 kill
check "b: a killed unit still releases its claim" tl_hasnt claimed:cloud
check "b: it set no successor, so needs-audit-2 STAYS and the next tick retries it" tl_has needs-audit-2
check "b: the PR is told the session ended without a next state" tl_comments 1
check "b: the row goes with the claim" tl_norow
check "b: and the PR is claimable again" tl_claimable
tl_cleanup

tl_fixture; tl_stage tail
tl_claim
tl_run_unit hakux-lane-cloud-audit2-141 kill
check "b-MUTANT(tail): an in-band tail dies with the shell that would have run it" tl_has claimed:cloud
tl_cleanup

# ====================================== c: finish twice is a no-op, not a double-apply
#
# IT DOES RUN TWICE. ExecStopPost fires on stop, and the owner also runs
# `cloud.sh finish` by hand when a claim has been stranded -- which is how #141
# and #148 were repaired at 2026-09-19T23:21Z. Four of finish's five steps
# already no-opped on a second run: label_rm probes the labels first,
# territory_row exits 3 on a row that is absent, `rm -f` is `rm -f`, say() is a
# log line. The fifth -- the "ended without setting a next state" comment --
# did not, and that is exactly the branch a hand-repaired claim lands in,
# because its claim label is already gone.
tl_fixture
printf 'needs-audit-2\nclaimed:cloud\n' > "$TL_LABELS"; : > "$TL_LOG"
env PATH="$TLPATH" HAKUX_REPO_DIR="$TL/repo" bash "$HERE/cloud.sh" finish audit2 141 >/dev/null 2>&1
check "c: the first finish drops the claim" tl_hasnt claimed:cloud
check "c: and leaves needs-audit-2, because the session set no successor" tl_has needs-audit-2
check "c: and says so on the PR, once" tl_comments 1
env PATH="$TLPATH" HAKUX_REPO_DIR="$TL/repo" bash "$HERE/cloud.sh" finish audit2 141 >/dev/null 2>&1
check "c: the second finish posts no second comment" tl_comments 1
check "c: and changes no label" bash -c '[ "$(cat "$1")" = "needs-audit-2" ]' _ "$TL_LABELS"
# ...and it is the CLAIM that gates it, not a marker file. A kind+num marker
# under $WORK could not tell the second run of one claim from the first run of
# the next, and a PR does get claimed again -- that is the whole retry policy.
printf 'needs-audit-2\nclaimed:cloud\n' > "$TL_LABELS"
env PATH="$TLPATH" HAKUX_REPO_DIR="$TL/repo" bash "$HERE/cloud.sh" finish audit2 141 >/dev/null 2>&1
check "c: a PR claimed a second time gets a live finish, not a suppressed one" tl_comments 2

# AN UNREADABLE LABEL LIST IS NOT AN ABSENT CLAIM. The guard keys on
# claimed:cloud, so an API failure at exactly this moment must not be read as
# "already finished" -- that would rebuild the stranded claim out of the fix's
# own guard, which is the worst place to put it. It retries three times and
# then goes on regardless; every step it then takes no-ops if there is nothing
# to undo, so going on is free and stopping is permanent.
#
# WHAT THIS CANNOT RECOVER, stated rather than implied: while the labels
# endpoint is down, NOTHING can remove the label. gh-label.sh's label_rm reads
# the current labels first and returns 1 without attempting the DELETE (a
# DELETE on an absent label is a 404, and swallowing that would swallow every
# other failure with it). So the property under test here is not "the claim
# comes off anyway" -- it is that finish takes the long path and the rest of
# the unclaim still happens, which is what leaves a later finish able to work.
cp "$TL/bin/gh" "$TL/bin/gh.real"
cat > "$TL/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "${TL_LOG:?}"
[[ "$*" == *"/labels"* && "$*" != *"-X"* ]] && exit 1     # the read fails, every time
[[ "$1 $2" == "pr comment" ]] && { echo "COMMENT $3 ${*: -1}" >> "$TL_LOG"; exit 0; }
exit 0
EOF
chmod +x "$TL/bin/gh"
: > "$TL_LOG"; : > "$HAKUX_WORK/logs/cloud/tick.log"
env PATH="$TLPATH" HAKUX_REPO_DIR="$TL/repo" bash "$HERE/cloud.sh" finish audit2 141 >/dev/null 2>&1
# Four reads, not three: the retry loop's three, and then label_rm's own. The
# fourth is the evidence that the early "already finished" exit was NOT taken
# -- a count of three alone is equally consistent with retrying and giving up.
check "an unreadable label list is retried three times, and then finish goes on anyway" bash -c '
    [ "$(grep -c "^gh api repos/example/hakux/issues/141/labels " "$1")" = 4 ]' _ "$TL_LOG"
check "and it says which of the two it is doing, rather than exiting 0 quietly" \
    grep -q "could not read #141's labels in 3 tries" "$HAKUX_WORK/logs/cloud/tick.log"
mv "$TL/bin/gh.real" "$TL/bin/gh"

# ============================================ the snapshot sweep spares a live one
# A unit's tail EXECUTES from its own snapshot, and bash reads a script lazily
# by byte offset -- so removing one under a running unit does not tidy a
# directory, it corrupts the program the tail is halfway through.
mkdir -p "$HAKUX_WORK/units/cloud-audit2-999/jobs" "$HAKUX_WORK/units/cloud-audit2-998/jobs"
printf 'hakux-lane-cloud-audit2-999\n' > "$TL_ACTIVE"
tl_stage none
rm -f "$HAKUX_WORK/attempts/cloud-audit2-141"
printf 'needs-audit-2\n' > "$TL_LABELS"
env PATH="$TLPATH" HAKUX_REPO_DIR="$TL/repo" \
    bash "$TL/board-wt/docs/testing/jobs/cloud.sh" >> "$TL_LOG" 2>&1
check "a snapshot whose unit is still running survives the sweep" \
    test -d "$HAKUX_WORK/units/cloud-audit2-999/jobs"
check "a snapshot whose unit is gone is swept" \
    bash -c '[ ! -e "$1/units/cloud-audit2-998" ]' _ "$HAKUX_WORK"
tl_cleanup
: > "$TL_ACTIVE"

# ==================================================== the unit systemd would refuse
# A relative first word in an Exec* command is not a $PATH lookup, it is a unit
# that will not load at all. Pinned on the script's text as well as on the
# stub's refusal, because it is the one failure mode that stays invisible until
# the host tries it.
check "the ExecStopPost command begins with an absolute path" \
    grep -q 'property=ExecStopPost="/bin/bash \$SJOBS/cloud.sh finish \$kind \$num"' "$HERE/cloud.sh"
check "the tail's environment is set on the unit, so ExecStopPost inherits it" bash -c '
    grep -q -- "--setenv=HAKUX_REPO_DIR=" "$1" && grep -q -- "--setenv=HAKUX_WORK=" "$1"' _ "$HERE/cloud.sh"
# NO SESSION, NO CLAIM. systemd-run failing is the one path ExecStopPost cannot
# cover -- there is no unit to stop -- and it used to drop the territory row
# only, leaving claimed:cloud on a PR that no session was ever started for.
#
# Anchored on the failure branch's own extent -- from the say() to the `}`
# that closes it -- rather than on a fixed line count, which a comment added
# inside the branch would silently push the claim removal out of.
check "a dispatch that never starts drops the claim as well as the row" bash -c '
    s=$(grep -n "say \"systemd-run failed" "$1" | cut -d: -f1)
    [ -n "$s" ] || exit 1
    e=$(awk -v s="$s" "NR>s && /^    \}$/ {print NR; exit}" "$1")
    [ -n "$e" ] || exit 1
    b=$(sed -n "${s},${e}p" "$1")
    grep -q "label_rm \"\$num\" claimed:cloud" <<< "$b" &&
    grep -q "territory_row rm" <<< "$b"' _ "$HERE/cloud.sh"

rm -rf "$TL/board-wt"
