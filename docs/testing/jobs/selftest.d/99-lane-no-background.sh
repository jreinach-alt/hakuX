# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# #433 (2026-10-10): a lane is a headless `claude -p` session; its turn
# ending kills the systemd unit's cgroup, and anything still running dies
# with it, with no notification ever arriving. LANE_SESSION_FOOTER already
# says so in every lane's prompt, in prose three lanes (surfgpudefault1009,
# restoreleak1009, meterfit1010 attempt 1) ignored anyway. jobs/hooks/
# lane-no-background.py is a PreToolUse hook that refuses the call itself;
# jobs/lane-settings.json is what lane.sh now hands every lane session via
# --settings so the hook actually loads.
#
# The hook also covers the Agent tool: a live check (docs/lanes/
# lanenobg1010/NOTES.md) showed Agent is reachable and backgrounds by
# default even though "Agent" is not in jobs/allowed-tools.lane, so the
# allowlist alone does not close this -- only the hook does.
#
# Fixtures only, per the brief: this fragment pipes canned PreToolUse JSON at
# the real hook script and reads its exit code and stderr, and greps the
# real lane.sh for the --settings wiring. It starts no systemd-run shim and
# no lane worktree -- that oracle belongs to 99-lane-path.sh and
# 99-lane-model-file.sh, which already prove lane.sh's command line reaches
# systemd-run at all; this fragment's job is the hook's own behaviour and
# that lane.sh's two call sites both carry the new flag.
#
# 99 because it depends on the harness only (the real jobs/hooks and
# lane.sh), and touches no other fragment's state.

HOOK="$HERE/hooks/lane-no-background.py"

echo "== lane-no-background.py: refuses Bash(run_in_background=true), passes everything else"

LNB="$T/lanenobg"; rm -rf "$LNB"; mkdir -p "$LNB"

lnb_run() {   # <hook-script> <json> -> sets LNB_RC, writes stderr to $LNB/err
    local script=$1 json=$2
    printf '%s' "$json" | python3 "$script" >"$LNB/out" 2>"$LNB/err"
    LNB_RC=$?
}
lnb_rc_is() { [ "$LNB_RC" = "$1" ]; }

lnb_run "$HOOK" '{"tool_name":"Bash","tool_input":{"command":"sleep 300","run_in_background":true}}'
check "Bash with run_in_background:true is refused (exit 2)" lnb_rc_is 2
check "  ...and the refusal names the foreground replacement" grep -qi 'foreground' "$LNB/err"
check "  ...and the refusal names the detached+poll replacement" grep -qi 'nohup\|detached' "$LNB/err"
check "  ...and the refusal says never to end a turn with a job still running" \
    grep -qi 'never end a turn' "$LNB/err"

lnb_run "$HOOK" '{"tool_name":"Bash","tool_input":{"command":"ls","run_in_background":false}}'
check "Bash with run_in_background:false passes (exit 0)" lnb_rc_is 0
check "  ...and writes nothing to stderr" bash -c '[ ! -s "$1" ]' _ "$LNB/err"

lnb_run "$HOOK" '{"tool_name":"Bash","tool_input":{"command":"ls"}}'
check "Bash with no run_in_background key at all passes (exit 0)" lnb_rc_is 0

lnb_run "$HOOK" '{"tool_name":"Read","tool_input":{"file_path":"/tmp/x","run_in_background":true}}'
check "a non-Bash, non-Agent tool passes regardless of its tool_input (exit 0)" lnb_rc_is 0

echo "== lane-no-background.py: refuses Agent unless run_in_background is explicitly false"

lnb_run "$HOOK" '{"tool_name":"Agent","tool_input":{"description":"x","prompt":"y"}}'
check "Agent with no run_in_background key is refused (defaults to background, exit 2)" lnb_rc_is 2
check "  ...and the refusal names the run_in_background:false replacement" grep -qi 'run_in_background: *false' "$LNB/err"
check "  ...and the refusal says never to end a turn with a subagent still running" \
    grep -qi 'never end a turn' "$LNB/err"

lnb_run "$HOOK" '{"tool_name":"Agent","tool_input":{"description":"x","prompt":"y","run_in_background":true}}'
check "Agent with run_in_background:true is refused (exit 2)" lnb_rc_is 2

lnb_run "$HOOK" '{"tool_name":"Agent","tool_input":{"description":"x","prompt":"y","run_in_background":false}}'
check "Agent with run_in_background:false passes (exit 0)" lnb_rc_is 0

# ------------------------------------------------------------------ mutant
# Drop the run_in_background check (invert it so it never distinguishes
# true from anything else, and the hook never refuses) on a COPY of the
# hook, left beside the real one, not a copy of the whole jobs/ tree -- the
# hook has no sibling files to resolve, so there is nothing a full-tree copy
# would protect here, but the convention (99-lane-model-file.sh, 99-lane-
# path.sh) is one mutated file beside the real tree regardless.
lnb_mutant() {   # <name> <sed-expr> -> path to a mutated hook, living beside the real one
    local f="$HERE/hooks/.selftest-mutlnb-$1.py"
    cp "$HOOK" "$f"
    sed -i "$2" "$f"
    echo "$f"
}
lnb_differs() { ! cmp -s "$1" "$HOOK"; }

m=$(lnb_mutant norbgcheck 's/tool_input.get("run_in_background") is not True:/tool_input.get("run_in_background") is not True or True:/')
check "mutant norbgcheck: the sed applied" lnb_differs "$m"
lnb_run "$m" '{"tool_name":"Bash","tool_input":{"command":"sleep 300","run_in_background":true}}'
if lnb_rc_is 2; then
    bad "mutant norbgcheck: run_in_background:true is still refused"
else
    ok "mutant norbgcheck: run_in_background:true is no longer refused, and the first case is red"
fi
rm -f "$m"

m=$(lnb_mutant noagentcheck 's/tool_input.get("run_in_background") is False:/tool_input.get("run_in_background") is not False:/')
check "mutant noagentcheck: the sed applied" lnb_differs "$m"
lnb_run "$m" '{"tool_name":"Agent","tool_input":{"description":"x","prompt":"y"}}'
if lnb_rc_is 2; then
    bad "mutant noagentcheck: Agent with no run_in_background key is still refused"
else
    ok "mutant noagentcheck: Agent with no run_in_background key is no longer refused, and that case is red"
fi
rm -f "$m"

unset -f lnb_run lnb_rc_is lnb_mutant lnb_differs
rm -rf "$LNB"

# ---------------------------------------------- lane.sh: --settings wiring
echo "== lane.sh: start and resume both hand the lane the hook via --settings"

lnb_block() { awk "/^  $2\\)/,/^  $3\\)/" "$1"; }   # <file> <start-arm> <next-arm>
lnb_has_settings() { lnb_block "$1" "$2" "$3" | grep -qF -- "--settings '\$JOBS/lane-settings.json'"; }

check "lane.sh's start block passes --settings '\$JOBS/lane-settings.json'" \
    lnb_has_settings "$TESTING/lane.sh" start stop
check "lane.sh's resume block passes --settings '\$JOBS/lane-settings.json' too" \
    lnb_has_settings "$TESTING/lane.sh" resume rm

check "jobs/lane-settings.json exists" [ -f "$HERE/lane-settings.json" ]
check "jobs/lane-settings.json parses as JSON" python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$HERE/lane-settings.json"
check "jobs/lane-settings.json's only top-level key is hooks" \
    python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if list(d.keys())==['hooks'] else 1)" "$HERE/lane-settings.json"
check "jobs/lane-settings.json's only hook event is PreToolUse" \
    python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if list(d['hooks'].keys())==['PreToolUse'] else 1)" "$HERE/lane-settings.json"
check "jobs/lane-settings.json's PreToolUse covers both Bash and Agent" \
    python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if {e['matcher'] for e in d['hooks']['PreToolUse']}=={'Bash','Agent'} else 1)" "$HERE/lane-settings.json"

unset -f lnb_block lnb_has_settings
unset LNB HOOK
