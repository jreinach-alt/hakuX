# Sourced by ../selftest.sh with the harness already built: $T, $HERE,
# $TESTING, $REPO, the shims on PATH, ok/bad/check. Not executable, no
# shebang, no exit -- `fail` is shared and is the run's verdict.
#
# jobs/window.sh: the account's five-hour and weekly windows (§9.1). Three
# things are checked, and each one failed differently against the code this
# replaces (docs/lanes/windowbudget/NOTES.md records the falsification run):
#
#   1. the DETECTION. run-claude-job.sh's old one-line grep over the whole log
#      matched the model's own PROSE, and missed every shape that does not put
#      the phrase after `"is_error": true` on the same line.
#   2. lane.sh's EXIT MAPPING. A lane that met a closed window exited with
#      whatever the CLI returned, spent an attempt, and was escalated to a more
#      expensive model on the fourth for a reason unrelated to its work.
#   3. board.sh's RESERVE. There was none: `grep -ci reserve board.sh` was 0.
#
# 88 is free and lands before the fleet-registry (96) and board-gate (97)
# blocks, which is deliberate: this fragment must leave NO window state behind
# in the shared $HAKUX_WORK or 97's gate would read a deferral and go quiet.
# Everything below runs against its own $WB/work, and the last lines here
# assert the shared tree is untouched.
#
# Depends on no other fragment. Brings its own gh/systemctl/systemd-run shims.

echo "== window.sh: what a closed account window looks like, and what it does not"
export WB="$T/windowbudget" TESTING HERE
mkdir -p "$WB/bin" "$WB/work/logs/lane" "$WB/work/attempts" "$WB/work/window"
# Sourced into THIS shell so the detection is exercised as the jobs use it;
# `export -f` because several checks below run it inside `bash -c`, where a
# shell function that was never exported is simply not there and the check
# would pass or fail for a reason that has nothing to do with the window.
. "$HERE/window.sh" 2>/dev/null || true
export -f window_limit_hit window_limit_probe 2>/dev/null || true

# The fixtures are the shapes the CLI can end a run with. NONE of them is a
# guess about the wording: 1 and 5 are the CLI's own "usage limit reached"
# message (with the reset epoch it appends), 2 and 3 are the JSON fields a
# refusal would land in, and 4 and 6 are taken from real logs on the host.
printf '{"is_error":true,"subtype":"success","result":"Claude AI usage limit reached|1790000000"}' > "$WB/limit.json"
printf '{"is_error":true,"terminal_reason":"usage_limit","num_turns":3,"result":""}' > "$WB/terminal.json"
printf '{"is_error":true,"api_error_status":"rate_limit_error","result":"stopped"}' > "$WB/apierr.json"
printf '{"is_error":false,"subtype":"success","num_turns":40,"result":"Done. PR #144 is ready."}' > "$WB/ok.json"
printf 'Claude AI usage limit reached|1790000000\n' > "$WB/truncated.log"
# THE ONE THAT MATTERS. A capped run (is_error is true for error_max_turns)
# whose summary talks ABOUT a rate limit. This is not hypothetical: it is
# cloud-remediate-128's own result text, and a lane briefed on this very defect
# writes those words by construction.
printf '{"is_error":true,"subtype":"error_max_turns","result":"a bound for the pathological run rather than a rate limit for the normal one"}' > "$WB/prose.json"

wl() { window_limit_hit "$WB/$1"; }
# A NEGATIVE CHECK MUST FIRST PROVE THERE IS SOMETHING TO BE NEGATIVE ABOUT.
# `! window_limit_hit x` is TRUE when the function does not exist, so every
# "is not a hit" check below was green against the tree that has no window.sh
# at all -- including the one that matters most. The guard is the difference
# between "it answered no" and "nothing answered".
wl_not() { declare -F window_limit_hit >/dev/null || return 1; ! window_limit_hit "$WB/$1"; }
check "a run refused by the account's window is a hit" wl limit.json
check "so is one that names it in terminal_reason" wl terminal.json
check "so is one that names it in api_error_status" wl apierr.json
check "a log too truncated to parse still yields the CLI's own message" wl truncated.log
check "a healthy run is not a hit" wl_not ok.json
check "a missing log is not a hit (and does not error)" wl_not nosuch.json
# Asserting BOTH halves, so this cannot pass by the fixture being uninteresting:
# the replaced regex really does match this file, and window.sh really does not.
wl_prose() {
    grep -qiE '"is_error": *true.*(rate.?limit|usage limit)' "$WB/prose.json" || return 1
    wl_not prose.json
}
check "a capped run that merely MENTIONS a rate limit is not one -- the grep it replaces matched it" \
    wl_prose
wl_reset() { window_limit_hit "$WB/limit.json" && [ "${WINDOW_RESET:-}" = 1790000000 ]; }
check "the reset time the run named is kept, not re-guessed from a five-hour bound" wl_reset

echo "== lane.sh: a lane that met a closed window did not fail at its work"
# fleet-end is the unit's tail and the only place a lane's exit code is
# decided. Driven directly, with a private $HAKUX_WORK so nothing here can
# leak a usage-limit record into the fragments that follow.
lane_end() {   # <attempt count to seed> <rc> [log] -> prints "exit=<n> attempts=<n>"
    local seed=$1 rc=$2 log=${3:-} out code
    mkdir -p "$WB/work/attempts"; echo "$seed" > "$WB/work/attempts/wbtest"
    out=$( HAKUX_WORK="$WB/work" DISPATCH_DIR="$WB/work/dispatch" \
           bash "$TESTING/lane.sh" fleet-end wbtest "$rc" $log 2>&1 ); code=$?
    echo "exit=$code attempts=$(cat "$WB/work/attempts/wbtest") $out"
}
export -f lane_end
export REPO
: > "$WB/work/window/limits.tsv"
check "a lane refused by the window exits 75 (EX_TEMPFAIL), not its session's code" \
    bash -c '[[ "$(lane_end 2 1 "$WB/limit.json")" == exit=75* ]]'
check "and the attempt is REFUNDED, so three of them cannot escalate the model" \
    bash -c '[[ "$(lane_end 2 1 "$WB/limit.json")" == *"attempts=1"* ]]'
check "and it says so, rather than leaving an orange unit to be read as broken" \
    bash -c 'lane_end 2 1 "$WB/limit.json" | grep -qi "STOPPED ON THE ACCOUNT.S USAGE WINDOW"'
check "the refusal is recorded, because it is the only evidence the window closed" \
    grep -q 'lane-wbtest' "$WB/work/window/limits.tsv"
# Column 3, not "somewhere in the line": column 1 is the time of the hit and
# would match any date pattern, so a whole-line grep would be green whether
# the reset was recorded or not.
check "the reset the run named is recorded with it, in its own column" \
    bash -c 'cut -f3 "$WB/work/window/limits.tsv" | grep -qE "^20[0-9][0-9]-"'
# The other side of the mapping, which is what keeps it from being a blanket
# amnesty: a lane that really did fail still fails, and still spends its try.
check "a lane that failed at its WORK still exits its own code" \
    bash -c '[[ "$(lane_end 2 3 "$WB/ok.json")" == exit=3* ]]'
check "and keeps its attempt: the refund is for the window, not for failure" \
    bash -c '[[ "$(lane_end 2 3 "$WB/ok.json")" == *"attempts=2"* ]]'
check "a unit from the PREVIOUS version, calling fleet-end with no log, still ends cleanly" \
    bash -c '[[ "$(lane_end 2 0)" == exit=0* ]]'
check "a refund never takes the counter below zero" \
    bash -c '[[ "$(lane_end 0 1 "$WB/limit.json")" == *"attempts=0"* ]]'

# And the wiring: the unit lane.sh actually writes must hand its log to
# fleet-end and exit on fleet-end's status, or none of the above ever runs.
cat > "$WB/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$WB/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${SELFTEST_GH_LOG:?}"; exit 0
EOF
chmod +x "$WB/bin/"*
git init -q -b master "$WB/origin"
git -C "$WB/origin" -c user.email=s@t -c user.name=s commit -q --allow-empty -m base
git clone -q "$WB/origin" "$WB/repo"
printf 'a brief\n' > "$WB/work/brief.md"
( export PATH="$WB/bin:$PATH" HAKUX_WORK="$WB/work" HAKUX_REPO_DIR="$WB/repo" \
         DISPATCH_DIR="$WB/work/dispatch" SELFTEST_GH_LOG="$WB/unit.log"; : > "$WB/unit.log"
  bash "$TESTING/lane.sh" start wbunit "$WB/work/brief.md" 9601 ) > "$WB/start.txt" 2>&1
check "the unit hands its run log to fleet-end, which is what maps the exit" \
    grep -qE "fleet-end 'wbunit' \\\$rc '[^']*wbunit[^']*\.json'" "$WB/unit.log"
check "and exits on fleet-end's verdict, not on the code it already had" \
    grep -q 'fleet-end .*; exit \$?' "$WB/unit.log"

echo "== run-claude-job.sh: the mapping every other job already had, end to end"
# The real runner, against a `claude` that returns a chosen result. Cheap, and
# it is the only place the three outcomes are distinguished in one file: 75 for
# a refusal, 0 for a turn cap, the session's own code otherwise.
RJ="$WB/runner"; mkdir -p "$RJ/bin" "$RJ/work"
cat > "$RJ/bin/claude" <<'EOF'
#!/usr/bin/env bash
cat "$FAKE_RESULT"; exit 0
EOF
chmod +x "$RJ/bin/claude"
printf '{"is_error":false,"subtype":"success","num_turns":3,"duration_ms":1000,"total_cost_usd":0.5,"result":"fine"}' > "$RJ/ok.json"
printf '{"is_error":true,"subtype":"success","num_turns":1,"duration_ms":10,"total_cost_usd":0.01,"result":"Claude AI usage limit reached|1790000000"}' > "$RJ/limit.json"
# THE LIVE DEFECT IN THE FILE BEING REPLACED: a run cut at the turn cap whose
# summary talks about a rate limit. is_error is true for error_max_turns, so
# the old grep called this a closed window, exited 75, and grew the unit's
# RestartSec for a run that had done its work and must exit 0.
printf '{"is_error":true,"subtype":"error_max_turns","num_turns":70,"duration_ms":10,"total_cost_usd":1,"result":"a bound rather than a rate limit for the normal run"}' > "$RJ/maxturns.json"
echo '# brief' > "$RJ/brief.md"
rj() {   # <fixture> -> the runner's exit code
    FAKE_RESULT="$RJ/$1.json" HAKUX_WORK="$RJ/work" PATH="$RJ/bin:$PATH" \
        bash "$HERE/run-claude-job.sh" board "$REPO" "$RJ/brief.md" 5 >/dev/null 2>&1
    echo $?
}
export -f rj; export RJ
check "a healthy job run exits 0" bash -c '[ "$(rj ok)" = 0 ]'
check "a job refused by the account's window exits 75" bash -c '[ "$(rj limit)" = 75 ]'
check "and the runner records the refusal where the board's reserve reads it" \
    grep -q 'board' "$RJ/work/window/limits.tsv"
check "a run cut at the turn cap that MENTIONS a rate limit still exits 0" \
    bash -c '[ "$(rj maxturns)" = 0 ]'
check "and is still indexed as MAXTURNS, not as an error" \
    bash -c 'cut -f7 "$RJ/work/logs/board/index.tsv" | grep -q MAXTURNS'

echo "== board.sh: the reserve, which §9.1 named and no file implemented"
# The board is the only actor that starts a lane or claims an audit, so the
# reserve lives on its gate. These drive the REAL board.sh with its own
# gh/systemctl shims and its own $HAKUX_WORK, and every check asserts on the
# OUTPUT: half of them expect a deferral, and a board.sh that cannot answer at
# all also exits non-zero.
export BWD="$WB/board"; mkdir -p "$BWD/bin" "$BWD/work/logs/board" "$BWD/work/logs/lane" "$BWD/work/window"
cat > "$BWD/bin/gh" <<'EOF'
#!/usr/bin/env bash
case "$1 $2" in
    "auth status") exit 0 ;;
    "issue list")  cat "${BW_ISSUES:-/dev/null}" ;;
    "pr list")     cat "${BW_PRS:-/dev/null}" ;;
esac
exit 0
EOF
cat > "$BWD/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$BWD/bin/"*
echo '[{"number":120,"title":"a startable issue","labels":[]}]' > "$BWD/issues.json"
echo '[{"number":101,"title":"ready and unlabelled","isDraft":false,"labels":[]}]' > "$BWD/prs.json"
echo '[]' > "$BWD/none.json"
SUN=$(date -u -d '2026-09-20T15:00:00Z' +%s)    # 95% through a Mon-anchored week
WED=$(date -u -d '2026-09-16T15:00:00Z' +%s)    # 38% through the same week
# A run index the reserve can read: 90 units of spend inside that week, in the
# nine-column shape summarise_run.py writes.
printf '2026-09-16T00:00:00Z\tlane-a\tclaude-opus-5\t50\t600\t90\tok\ta.json\tdid a thing\n' \
    > "$BWD/work/logs/lane/index.tsv"
hits() { : > "$BWD/work/window/limits.tsv"; for t in "$@"; do printf '%s\tlane-x\t-\tx.json\n' "$t" >> "$BWD/work/window/limits.tsv"; done; }
bwgate() {   # <issues.json> <prs.json> <now epoch or ""> [limits.env contents]
    printf '%s\n' "${4:-}" > "$BWD/work/limits.env"
    BW_ISSUES="$BWD/$1" BW_PRS="$BWD/$2" HAKUX_NOW="${3:-}" \
        HAKUX_WORK="$BWD/work" HAKUX_REPO_DIR="$BWD/no-such-repo" PATH="$BWD/bin:$PATH" \
        bash "$HERE/board.sh" gate 2>&1
}
bw_says()  { local w=$1 p=$2; shift 2; local o; o=$(bwgate "$@"); local r=$?; [ "$r" = "$w" ] && grep -q -- "$p" <<< "$o"; }
bw_omits() { local w=$1 p=$2; shift 2; local o; o=$(bwgate "$@"); local r=$?; [ "$r" = "$w" ] && ! grep -q -- "$p" <<< "$o"; }

# 1. A measured refusal. This is the case that needs nothing declared.
hits "$(date -u -d '5 minutes ago' +%FT%TZ)"
check "a session refused minutes ago defers dispatch" \
    bw_says 1 'DEFERRING' issues.json none.json ""
check "the startable issue is not offered while the window is closed" \
    bw_omits 1 '#120' issues.json none.json ""
check "the deferral says when it resumes, so quiet is not indistinguishable from jammed" \
    bw_says 1 'Resumes 20' issues.json none.json ""
check "a deferral carries NO FAIL: it must not wake a tick to investigate itself" \
    bw_omits 1 'FAIL' issues.json none.json ""
check "the five-hour reset is treated as a bound, so this re-probes rather than sleeping it off" \
    bw_says 1 're-probes in 30 min' issues.json none.json ""
# The half that must keep working. Labelling a ready PR is not dispatch; a
# pipeline that stops labelling is a pipeline that stalls for free.
check "a ready PR with no state label still wakes the tick while dispatch is held" \
    bw_says 0 '#101' none.json prs.json ""

# 2. It lifts itself. Nothing external clears a deferral, so a stuck one would
#    be a permanent outage with a tidy explanation.
hits "$(date -u -d '2 hours ago' +%FT%TZ)"
check "the deferral lifts itself once the cooldown has passed" \
    bw_says 0 '#120' issues.json none.json ""

# 3. The weekly reserve: the last fifth of the week AND evidence, never time
#    alone -- a calendar that stops the fleet every Sunday is a throttle.
hits
check "the last fifth of the week alone does NOT defer: an unknown window must not stop the fleet" \
    bw_says 0 '#120' issues.json none.json "$SUN"
check "and it says so on the tick, so an un-armed reserve is not silent" \
    bw_says 0 'weekly reserve is NOT armed' issues.json none.json "$SUN"
check "naming what would arm it, rather than reporting an unexplained zero" \
    bw_says 0 'WEEK_SPEND_BUDGET' issues.json none.json "$SUN"
check "a declared budget 80% spent, in the last fifth, holds the reserve" \
    bw_says 1 "owner's reserve" issues.json none.json "$SUN" 'WEEK_SPEND_BUDGET=100'
check "the same spend mid-week does NOT defer: this is a reserve, not a second cap" \
    bw_says 0 '#120' issues.json none.json "$WED" 'WEEK_SPEND_BUDGET=100'
# Two refusals INSIDE the reserve's own stretch, which opens at Sat 14:24Z
# under a Monday anchor (5.6 days in). Both are hours old, so what arms here
# is the reserve and not the cooldown wearing its clothes.
hits 2026-09-19T15:00:00Z 2026-09-19T20:00:00Z
check "two refusals inside the reserve arm it with nothing declared at all" \
    bw_says 1 'refused 2 time' issues.json none.json "$SUN"
# A five-hour refusal on Tuesday and a weekly one on Sunday read identically
# from here, so Tuesday's must not be evidence about Sunday's budget.
hits 2026-09-15T09:00:00Z 2026-09-15T10:00:00Z
check "refusals from earlier in the week do not arm it: nothing here knows which window closed" \
    bw_says 0 '#120' issues.json none.json "$SUN"
check "and they are still reported, so the week's refusals are not hidden" \
    bw_says 0 '2 usage-limit hit(s) this week' issues.json none.json "$SUN"
hits 2026-09-07T09:00:00Z 2026-09-08T10:00:00Z
check "last week's refusals do not arm this week's reserve" \
    bw_says 0 '#120' issues.json none.json "$SUN"

# 4. The audit outlet is dispatch too, and it is claimed on the tick path
#    rather than the gate -- so this drives the tick far enough to reach it,
#    with a cloud.sh that only leaves a mark. Nothing actionable, so the tick
#    exits before any model session.
mkdir -p "$BWD/origin"; git init -q -b master "$BWD/origin"
mkdir -p "$BWD/origin/docs/testing/jobs"
cat > "$BWD/origin/docs/testing/jobs/cloud.sh" <<'EOF'
#!/usr/bin/env bash
touch "$CLOUD_MARK"
EOF
git -C "$BWD/origin" -c user.email=s@t -c user.name=s add -A
git -C "$BWD/origin" -c user.email=s@t -c user.name=s commit -q -m base
git clone -q "$BWD/origin" "$BWD/repo"
bwtick() {   # <now> -> runs a tick with no actionable work; $BWD/mark appears iff the outlet ran
    # The board worktree is NOT removed between ticks: git keeps the
    # registration in $BWD/repo, and a second `worktree add` on the same path
    # would fail, which board.sh reports as "cannot create" and exits before
    # reaching the outlet at all -- a green-looking check for the wrong reason.
    rm -f "$BWD/mark"
    printf '\n' > "$BWD/work/limits.env"
    BW_ISSUES="$BWD/none.json" BW_PRS="$BWD/none.json" HAKUX_NOW="${1:-}" \
        HAKUX_WORK="$BWD/work" HAKUX_REPO_DIR="$BWD/repo" CLOUD_MARK="$BWD/mark" \
        HAKUX_BOARD_REEXEC=1 PATH="$BWD/bin:$PATH" \
        bash "$HERE/board.sh" 2>&1
}
hits
bwtick "" > "$BWD/tick-open.txt" 2>&1
check "with the window open, the tick lets the audit outlet claim" \
    bash -c 'test -f "$BWD/mark"'
hits "$(date -u -d '5 minutes ago' +%FT%TZ)"
# To a FILE, not to a variable a later `bash -c` would read as empty: an
# unexported $out inside a child shell is the empty string, and every grep
# over it fails for a reason that has nothing to do with the tick.
bwtick "" > "$BWD/tick-deferred.txt" 2>&1
check "an audit is a lane session, so a closed window defers its claim too" \
    bash -c '! test -f "$BWD/mark"'
check "and the tick log says so in one line, naming the resume time" \
    bash -c 'grep -q "DEFERRING the audit outlet" "$BWD/tick-deferred.txt" && grep -q "Resumes" "$BWD/tick-deferred.txt"'
check "the deferred tick still does not report a failure" \
    bash -c '! grep -q "FAIL" "$BWD/tick-deferred.txt"'

echo "== status.sh: the page says it is deferring, or the fleet just looks jammed"
( export HAKUX_WORK="$BWD/work" HAKUX_REPO_DIR="$BWD/repo" PATH="$BWD/bin:$PATH"
  bash "$HERE/status.sh" --print ) > "$BWD/status.txt" 2>&1
check "the status page carries a window-budget section" \
    grep -q '### Window budget' "$BWD/status.txt"
check "and names the deferral, its reason and its resume time, above the empty lane table" \
    bash -c 'grep -q "dispatch DEFERRED until" "$BWD/status.txt" && grep -q "refused" "$BWD/status.txt"'
check "and says plainly that this is a budget decision and not a failure" \
    grep -q 'not a failure' "$BWD/status.txt"
hits
( export HAKUX_WORK="$BWD/work" HAKUX_REPO_DIR="$BWD/repo" PATH="$BWD/bin:$PATH"
  bash "$HERE/status.sh" --print ) > "$BWD/status2.txt" 2>&1
check "with the window open it says the fleet is dispatching, and shows the week it used" \
    bash -c 'grep -q "dispatching normally" "$BWD/status2.txt" && grep -q "week from 20" "$BWD/status2.txt"'
check "and names what cannot be observed from here, so a zero is not read as health" \
    grep -q 'cannot be queried from here' "$BWD/status2.txt"

# Nothing above may leak into the shared fixture: 97's gate runs after this
# fragment and would read a stale refusal as a live deferral.
check "this fragment left no window state in the shared \$HAKUX_WORK" \
    bash -c '! test -s "$HAKUX_WORK/window/limits.tsv"'
rm -rf "$HAKUX_WORK/window"
