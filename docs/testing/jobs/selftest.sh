#!/usr/bin/env bash
#
# The jobs' self-test: run the real job scripts against a fake host.
#
#   docs/testing/jobs/selftest.sh          # exits non-zero on any failure
#
# WHY. The jobs run only on the owner's host -- systemd, gh, adb, the
# dispatch directory, the goldens tree -- and the session that writes them
# cannot execute any of it. On 2026-09-19 that put the owner in a loop:
# merge, run, paste the error, wait for the fix, merge again. Three of the
# four defects that day (a watermark seeded at install time, an arithmetic
# error on a "?" field, an empty --runs handed to request.sh) fall out of
# one run of this file. So: nothing under jobs/ is pushed until this passes,
# and the check is in CI (.github/workflows/jobs-selftest.yml) as well.
#
# WHAT IS REAL AND WHAT IS FAKED. Real: git, python3, request.sh's whole
# queue path (its gates, its JSON writer), arms.sh, fold.sh, cloud.sh,
# status.sh. Faked, as shims on PATH under $T/bin: gh (canned answers, every
# call logged), systemctl, systemd-run, adb. The goldens tree is generated
# from the prediction under test, so request.sh's every-key-must-bind gate
# runs for real.
set -u
export HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; TESTING="$(dirname "$HERE")"; REPO="$(cd "$TESTING/../.." && pwd)"
T="${SELFTEST_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/hakux-selftest.XXXXXX")}"
export HAKUX_WORK="$T/work" HAKUX_REPO_DIR="$REPO" DISPATCH_DIR="$T/work/dispatch" GOLDENS="$T/goldens" GH_REPO="example/hakux"
export HOME="${HOME:-$T}"
mkdir -p "$T/bin" "$HAKUX_WORK"/{arms,logs/arms,logs/lane,logs/board,logs/fold,logs/cloud,status,briefs,attempts} "$DISPATCH_DIR"/{queue,running,results,expect} "$GOLDENS"
pass=0; fail=0
ok()   { echo "  ok   $*"; pass=$((pass+1)); }
bad()  { echo "  FAIL $*"; fail=$((fail+1)); }
check() { local msg=$1; shift; if "$@" >/dev/null 2>&1; then ok "$msg"; else bad "$msg"; fi; }

# ------------------------------------------------------------------ shims
cat > "$T/bin/gh" <<'EOF'
#!/usr/bin/env bash
# gh shim: log every call, answer the shapes the jobs ask for.
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "auth status") exit 0 ;;
    "pr list")
        if [[ "$args" == *"--head lane/selftest"* ]]; then
            [[ "$args" == *".[0].number"* ]] && { echo 102; exit 0; }
            echo "#102 draft"; exit 0
        fi
        [[ "$args" == *"--jq"* ]] && exit 0
        echo "[]"; exit 0 ;;
    "pr view") echo GREEN; exit 0 ;;
    "issue list") [[ "$args" == *"harness-status"* ]] && echo 107; exit 0 ;;
    "issue create") echo "https://github.com/example/hakux/issues/107"; exit 0 ;;
    "api "*|"api -X"*)
        [[ "$args" == *"--jq .id"* ]] && { echo 5; exit 0; }
        # the labels currently on an issue/PR, for label_rm's "is it there" probe
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${SELFTEST_LABELS:-}; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$T/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) echo active ;;
    *show*ActiveEnterTimestamp*) date ;;
    *) exit 0 ;;
esac
EOF
cat > "$T/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${SELFTEST_GH_LOG:?}"; exit 0
EOF
cat > "$T/bin/adb" <<'EOF'
#!/usr/bin/env bash
printf 'List of devices attached\nbdc158a5\tdevice\nee317437\tdevice\n'
EOF
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH" SELFTEST_GH_LOG="$T/gh.log"; : > "$SELFTEST_GH_LOG"

# ------------------------------------------------------- the prediction
# A registration naming two real, live refs of this repository: the trunk's
# tip and its parent. It has NO runs_per_arm and NO disc, which is the shape
# that broke the first real tick.
git -C "$REPO" fetch -q origin master 2>/dev/null || true
B=$(git -C "$REPO" rev-parse --short origin/master 2>/dev/null || git -C "$REPO" rev-parse --short HEAD)
A=$(git -C "$REPO" rev-parse --short "$B~1")
EXP="$DISPATCH_DIR/expect/selftest-live.json"
python3 - "$EXP" "$A" "$B" <<'PY'
import json, sys, datetime
p, a, b = sys.argv[1:]
json.dump({"registered_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "who": "lane.selftest", "issue": "1", "prediction": "selftest: the fix arm moves TestA to 0",
           "a_ref": a, "b_ref": b,
           "expect": {"Blend_surface/TestA": 0}, "must_not_move": ["Color_mask_blend/*"],
           "must_not_regress": [], "expect_counts": {}}, open(p, "w"), indent=2)
PY
mkdir -p "$GOLDENS/Blend_surface" "$GOLDENS/Color_mask_blend"
: > "$GOLDENS/Blend_surface/TestA.png"; : > "$GOLDENS/Color_mask_blend/Sample.png"
date -u -d '1 minute ago' '+%FT%TZ' > "$HAKUX_WORK/arms/since"   # fences every committed prediction; only ours is live
# Make our registration look like it came from a lane branch, so the verdict/refusal path targets a PR.
mkdir -p "$HAKUX_WORK/arms"

# --------------------------------------------------------------- the checks
# Every check lives in its own file under selftest.d/, sourced here in sorted
# order with everything above already built: $T, $HERE, $REPO, the shims on
# PATH, ok/bad/check, the live prediction and its goldens.
#
# WHY IT IS NOT ONE FILE. This is the gate every change under jobs/ must pass,
# so a lane that fixes something here also adds the check that proves it: on
# 2026-09-19 nine harness lanes ran and all nine appended to this file. The
# fold job folds one PR per tick and each fold moves master, so the conflict
# rate on this one path was not high, it was ~100% -- two of the first three
# folds attempted were handed back on selftest.sh alone, each costing a full
# lane.sh resume to re-land work that was already finished and green. A
# fragment is separately ownable; two lanes adding checks now touch two paths.
#
# ADDING A CHECK: write, or edit, selftest.d/NN-<concern>.sh.
#   - NN is exactly two digits. A three-digit prefix would sort before every
#     two-digit one, so the loop below refuses a name that is not NN-*.sh
#     rather than silently never sourcing it.
#   - The number fixes the order, and order matters: fragments 10..50 drive
#     arms.sh over one shared dispatcher queue in sequence, and 60 reads what
#     they left. Each fragment's header says what it depends on.
#   - Fragments are sourced, not executed: no shebang, no exit. `pass`, `fail`
#     and the fixtures are shared state, so a failing check in a fragment
#     fails the whole run, which is the point.
frags=()
while IFS= read -r f; do                         # LC_ALL=C: the runner's
    [ -e "$f" ] || continue                      # collation is not this box's
    case "${f##*/}" in
        [0-9][0-9]-*.sh) frags+=("$f") ;;
        *.md|*~)         ;;                      # a README, an editor backup
        *) echo "selftest: $f is not selftest.d/NN-<concern>.sh and would never be sourced" >&2
           exit 2 ;;
    esac
done < <(printf '%s\n' "$HERE/selftest.d/"* | LC_ALL=C sort)
[ "${#frags[@]}" -gt 0 ] || {
    echo "selftest: no fragments under $HERE/selftest.d -- nothing would be checked" >&2
    exit 2
}
for f in "${frags[@]}"; do
    . "$f"
done

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

echo
echo "selftest: $pass passed, $fail failed (fake host in $T)"
[ "$fail" -eq 0 ]
