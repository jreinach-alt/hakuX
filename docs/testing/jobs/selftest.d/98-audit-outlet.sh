# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# The audit outlet: one dispatch path, one cap, and no terminal label.
#
# Written against selftest.sh as an append (#130, lane/auditoutlet) and carried
# here unchanged when that lane met the split. 98 because it was the last block
# appended; it depends on no other fragment and builds its own gh shim on its
# own PATH ($AOPATH), leaving the shared one untouched.

echo "== the audit outlet: one dispatch path, one cap, and no terminal label"
# MEASURED 2026-09-19. Pass 1 on PR #102 worked -- an audit file, a review
# reading 0 HIGH / 2 MEDIUM / 5 LOW, the label needs-remediation -- and nothing
# could ever pick it up. cloud.sh filtered the remediate pickup on the head
# prefix lane/cloud- and #102's head is lane/blitsafe, a LOCAL lane; the rule
# in roles/board.md could only run on a board tick, and a tick only starts when
# fleet.py or the coverage gate says FAIL, neither of which counts an
# unremediated audit; and hakux-cloud.timer is disabled. needs-audit-1 and
# needs-remediation were terminal states.
AO="$T/ao"; mkdir -p "$AO/bin"
cat > "$AO/bin/gh" <<'EOF'
#!/usr/bin/env bash
# A gh that answers with ONE open PR: #102, head lane/blitsafe -- a LOCAL
# lane's branch, which is exactly the case the prefix filter could not see.
# The filter itself lives in the --jq expression, which a shim does not run,
# so the one property under test is emulated directly: a query that restricts
# the head branch to lane/cloud- cannot match #102.
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        [[ "$args" == *'startswith("lane/cloud-")'* ]] && exit 0
        [[ "$args" == *"--label ${AO_LABEL:-needs-remediation}"* ]] || exit 0
        printf '102\t%s\tblit: clamp the destination rect\n' "${AO_HEAD:-lane/blitsafe}"
        exit 0 ;;
    "api "*)
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${AO_LABELS:-}; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$AO/bin/gh"; AOPATH="$AO/bin:$PATH"

: > "$SELFTEST_GH_LOG"
aout=$(PATH="$AOPATH" bash "$HERE/cloud.sh" list 2>&1)
check "a needs-remediation PR on a LOCAL lane's branch is claimable" \
    grep -q "would claim remediate #102 (lane/blitsafe)" <<< "$aout"
check "the pickup query does not filter on the head branch at all" \
    bash -c '! grep -q "headRefName | startswith" "$HERE/cloud.sh"'
check "the pickup skips a PR already escalated to the owner" \
    grep -q 'blocked:needs-owner' "$HERE/cloud.sh"

# THE CAP IS ONE NUMBER. An audit session costs what a lane session costs, so
# it is capped by LANE_MAX and by nothing else -- and the default is read out
# of lane.sh, because a repeated default is a second cap that drifts the first
# time one of the two is edited.
lmax=$(sed -n 's/^LANE_MAX=\([0-9][0-9]*\).*/\1/p' "$TESTING/lane.sh" | head -1)
check "the cap it reports is the number lane.sh defaults to, not one of its own" \
    grep -q "cap: LANE_MAX=${lmax:-UNREADABLE} " <<< "$aout"
echo 'LANE_MAX=9' > "$HAKUX_WORK/limits.env"
aout2=$(PATH="$AOPATH" bash "$HERE/cloud.sh" list 2>&1); rm -f "$HAKUX_WORK/limits.env"
check "\$WORK/limits.env overrides it, exactly as it does for lane.sh" \
    grep -q "cap: LANE_MAX=9 " <<< "$aout2"
check "the cap counts the unit glob lane.sh counts" \
    grep -q "list-units 'hakux-lane-\*' --state=active,activating" "$HERE/cloud.sh"
check "the session's unit is a hakux-lane-* unit, so lane.sh's own count sees it" \
    grep -q 'unit="hakux-lane-\$name"' "$HERE/cloud.sh"
check "no second cap: CLOUD_MAX is gone" bash -c '! grep -q CLOUD_MAX "$HERE/cloud.sh"'

# THE TRIGGER. hakux-cloud.timer is disabled and stays disabled; the timer that
# starts lanes starts this too, and it must run BEFORE the board's own early
# exit, because a fleet with nothing actionable is exactly when an audit is
# waiting.
check "board.sh dispatches the audit outlet" \
    grep -q 'bash "\$JOBS/cloud.sh"' "$HERE/board.sh"
# Anchor on the say() CALL, not the words: the first draft of this check
# matched a comment three lines above the dispatch that happened to contain
# "nothing actionable", so the exit appeared to come first and the check
# failed against the file that was correct.
check "it does so before the 'nothing actionable' exit, which is the tick an audit needs" bash -c '
    c=$(grep -n "bash \"\$JOBS/cloud.sh\"" "$HERE/board.sh" | head -1 | cut -d: -f1)
    n=$(grep -n "say \"nothing actionable\"" "$HERE/board.sh" | head -1 | cut -d: -f1)
    [ -n "$c" ] && [ -n "$n" ] && [ "$c" -lt "$n" ]'

# CLEARING THE STATE LABEL IS PART OF THE JOB. A label that is never cleared
# makes the same PR eligible forever, and the session meant to clear it is the
# one thing here that can forget; so the unit's tail checks, and the answer
# differs by whether the session left a next state behind.
: > "$SELFTEST_GH_LOG"
PATH="$AOPATH" AO_LABELS="needs-audit-1 needs-remediation claimed:cloud" \
    bash "$HERE/cloud.sh" finish audit1 102 >/dev/null 2>&1
check "finish drops the claim" \
    grep -q 'api -X DELETE repos/example/hakux/issues/102/labels/claimed%3Acloud' "$SELFTEST_GH_LOG"
check "finish clears needs-audit-1 once the session has set a successor state" \
    grep -q 'api -X DELETE repos/example/hakux/issues/102/labels/needs-audit-1' "$SELFTEST_GH_LOG"
: > "$SELFTEST_GH_LOG"
PATH="$AOPATH" AO_LABELS="needs-audit-1 claimed:cloud" \
    bash "$HERE/cloud.sh" finish audit1 102 >/dev/null 2>&1
check "a session that set NO successor does not get needs-audit-1 cleared (the next tick retries it)" \
    bash -c '! grep -q "labels/needs-audit-1" "$SELFTEST_GH_LOG"'
check "and the PR is told, rather than the unit ending silently" \
    grep -q '^pr comment 102' "$SELFTEST_GH_LOG"

# ...AND THAT RETRY IS BOUNDED. Leaving the label is what makes a retry
# possible; the attempt counter is what stops it being endless. The refusal
# runs before any git or worktree work, so it is cheap and testable.
amax=$(sed -n 's/^LANE_MAX_ATTEMPTS=\([0-9][0-9]*\).*/\1/p' "$HERE/models.env" | head -1)
: > "$SELFTEST_GH_LOG"; echo "${amax:-4}" > "$HAKUX_WORK/attempts/cloud-remediate-102"
PATH="$AOPATH" bash "$HERE/cloud.sh" >/dev/null 2>&1
check "a PR whose sessions keep ending unfinished goes to the owner, not to a fifth session" \
    grep -q 'labels\[\]=blocked:needs-owner' "$SELFTEST_GH_LOG"
check "and no session is started for it" bash -c '! grep -q "^systemd-run" "$SELFTEST_GH_LOG"'
rm -f "$HAKUX_WORK/attempts/cloud-remediate-102"
