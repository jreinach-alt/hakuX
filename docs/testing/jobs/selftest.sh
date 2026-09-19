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

echo "== handback.sh: the actor for a PR a job handed back"
# `needs-rebase` was set by fold.sh, shown by status.sh and acted on by nothing,
# so a complete, audited, green PR was parked the moment master moved under it.
# These drive the REAL handback.sh and the REAL lane.sh against shims of their
# own: the shared gh shim answers every `pr list` with "[]" and every
# `systemctl is-active` with "active", which are exactly the two answers that
# make this job do nothing.
HB="$T/handback"; mkdir -p "$HB/bin" "$HAKUX_WORK/wt" "$HAKUX_WORK/briefs"
cat > "$HB/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${HB_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        # The rows this tick should see, one file per label, TSV as the --jq emits.
        [[ "$args" =~ --label\ ([A-Za-z0-9:_-]+) ]] && { f="$HB/prs.${BASH_REMATCH[1]}.tsv"; [ -f "$f" ] && cat "$f"; }
        exit 0 ;;
    "pr comment")
        # keep the body, not just the fact of it: these checks read what it said
        b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$HB/comments.log"; b=""; }; [ "$a" = --body-file ] && b=1; done
        echo "--- end comment" >> "$HB/comments.log"; exit 0 ;;
    "api "*|"api -X"*)
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${HB_LABELS:-}; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HB/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
# $HB/active holds one unit name per line; everything else is inactive.
# ${!#} is the last argument -- the unit. NOT ${*##* }: on $* a substring
# removal applies to each positional parameter separately and the join puts
# the whole command line back, which grep then reads as an option.
case "$*" in
    *is-active*) u="${!#}"; grep -qxF -- "$u" "$HB/active" 2>/dev/null ;;
    *list-units*) cat "$HB/active" 2>/dev/null; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HB/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${HB_LOG:?}"; exit 0
EOF
chmod +x "$HB/bin/"*
export HB HB_LOG="$HB/gh.log"; : > "$HB_LOG"; : > "$HB/comments.log"; : > "$HB/active"
hb() { ( export PATH="$HB/bin:$PATH"; bash "$HERE/handback.sh" "$@" 2>&1 ); }
hb_said()   { grep -qF -- "$1" "$HB/comments.log"; }
hb_ran()    { grep -q "systemd-run.*hakux-lane-$1" "$HB_LOG"; }
hb_runs()   { [ "$(grep -c "systemd-run.*hakux-lane-$1" "$HB_LOG")" -eq "$2" ]; }
hb_reset()  { : > "$HB_LOG"; : > "$HB/comments.log"; }
hb_row()    { printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "${4:-needs-rebase}" > "$HB/prs.needs-rebase.tsv"; }

check "handback.sh exists at all" [ -f "$HERE/handback.sh" ]
out=$(hb list)
check "list says so when nothing is handed back" grep -q "nothing handed back" <<< "$out"
check "and names the label it looked for" grep -q "needs-rebase" <<< "$out"

# A real local lane: a worktree directory and a brief, which is all lane.sh
# resume requires. Its unit is not running.
mkdir -p "$HAKUX_WORK/wt/selftesthb"; echo "# the original brief" > "$HAKUX_WORK/briefs/selftesthb.md"
HEAD1=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
hb_row 201 lane/selftesthb "$HEAD1"
out=$(hb list)
check "list names the lane it would resume" grep -q "WOULD RESUME lane.selftesthb" <<< "$out"
check "list starts no session" bash -c '! grep -q systemd-run "$HB_LOG"'

hb_reset; hb >/dev/null
check "a handed-back PR resumes its lane" hb_ran selftesthb
check "the resume is announced on the PR" hb_said "[job.handback] Resumed \`lane.selftesthb\`"
check "the handback is appended to the lane's own brief" grep -q "no longer merges into" "$HAKUX_WORK/briefs/selftesthb.md"
check "the brief says merge, and says why not rebase" grep -q "un-ancestors any registered" "$HAKUX_WORK/briefs/selftesthb.md"
check "the brief tells the lane to re-apply fold-ready" grep -q "gh-label.sh add 201 fold-ready" "$HAKUX_WORK/briefs/selftesthb.md"
check "the original brief is still there under it" grep -q "the original brief" "$HAKUX_WORK/briefs/selftesthb.md"

# RESUME ONLY ON A NEW CAUSE. A lane resumed twice for one head has been given
# nothing new to read; it re-opens the same NOTES.md and the same diff, and
# spends one of the four attempts the escalation policy allows doing it.
hb_reset; hb >/dev/null
check "the same head does not resume the lane a second time" bash -c '! grep -q systemd-run "$HB_LOG"'
check "and says nothing on the PR the second time" bash -c '[ ! -s "$HB/comments.log" ]'
out=$(hb list)
check "list explains the skip by naming the head" grep -q "already actioned at aaaaaaaaaa" <<< "$out"

# ...but a head that moved IS new information: the lane pushed, and the merge
# conflicts somewhere else.
HEAD2=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
printf 'label=needs-rebase\nbranch=lane/selftesthb\nhead=%s\nfiles=docs/testing/jobs/selftest.sh\n' "$HEAD2" \
    > "$HAKUX_WORK/handback/cause/201-$HEAD2"
hb_reset; hb_row 201 lane/selftesthb "$HEAD2"; hb >/dev/null
check "a new head resumes the lane again" hb_ran selftesthb
check "fold.sh's recorded cause reaches the lane's brief" grep -q "conflicting in: docs/testing/jobs/selftest.sh" "$HAKUX_WORK/briefs/selftesthb.md"

# A lane that resolved its conflict re-applies fold-ready. Its head has moved,
# so the cause looks new -- and resuming it now would put a second session on
# work that is already back in the pipeline. This is the loop this job must not
# become, and the head-sha key alone does not stop it.
hb_reset; hb_row 201 lane/selftesthb cccccccccccccccccccccccccccccccccccccccc "needs-rebase,fold-ready"
out=$(hb list); hb >/dev/null
check "a PR that also carries fold-ready is left alone" bash -c '! grep -q systemd-run "$HB_LOG"'
check "list says why it was left alone" grep -q "already moved on" <<< "$out"

# THE LANE NAME IS NOT THE PR. Both of these are live head branches on this
# repository, and neither has a local worktree to resume.
hb_reset; hb_row 202 claude/hakux-orchestration-design-e663m8 dddddddddddddddddddddddddddddddddddddddd
hb >/dev/null
check "a claude/* head starts nothing" bash -c '! grep -q systemd-run "$HB_LOG"'
check "and the PR is told there is no local lane" hb_said "no local lane can act on it"
check "naming the shape it needed" hb_said 'is not a `lane/<name>` branch'
hb_reset; hb >/dev/null
check "a PR with no lane is told once, not once a tick" bash -c '[ ! -s "$HB/comments.log" ]'

hb_reset; hb_row 203 lane/cloud-109 eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
hb >/dev/null
check "a lane/cloud-* head starts no local lane" bash -c '! grep -q systemd-run "$HB_LOG"'
check "and is told cloud lanes remediate themselves" hb_said "cloud lanes remediate themselves"

# A lane whose unit is still running is not stalled. systemd-run on a live unit
# fails AFTER lane.sh has counted the attempt, so this guard is one of the four
# attempts, not a tidiness.
hb_reset; echo "hakux-lane-selftesthb" > "$HB/active"
hb_row 201 lane/selftesthb ffffffffffffffffffffffffffffffffffffffff
hb >/dev/null
check "a lane whose unit is still active is not resumed" bash -c '! grep -q systemd-run "$HB_LOG"'
: > "$HB/active"

# THE FLEET CAP IS NOT A FAILURE, AND MUST NOT BE REMEMBERED AS ONE. lane.sh
# checks LANE_MAX before it counts the attempt, so nothing was spent and the
# cause is still unactioned -- writing the marker here would park the PR exactly
# the way `needs-rebase` already did.
hb_reset; printf 'hakux-lane-other1\nhakux-lane-other2\n' > "$HB/active"
HEAD3=1111111111111111111111111111111111111111
hb_row 201 lane/selftesthb "$HEAD3"
out=$(hb)
check "at LANE_MAX nothing is resumed" bash -c '! grep -q systemd-run "$HB_LOG"'
check "and the tick says the cap is why" grep -q "fleet at cap" <<< "$out"
check "the cap leaves no marker for that head" [ ! -f "$HAKUX_WORK/handback/done/needs-rebase-201-$HEAD3" ]
# ...and it leaves no half-handback in the brief either. The section goes in
# before the resume, because that file is what the session is handed; a tick
# that appends and then does not resume appends again next tick.
check "a capped tick rolls its handback back out of the brief" \
    [ "$(grep -c 'no longer merges into' "$HAKUX_WORK/briefs/selftesthb.md")" -eq 2 ]
: > "$HB/active"; hb_reset; hb >/dev/null
check "so the next tick, under the cap, resumes it" hb_ran selftesthb
check "and the brief gains exactly one more handback" \
    [ "$(grep -c 'no longer merges into' "$HAKUX_WORK/briefs/selftesthb.md")" -eq 3 ]

# THE END OF THE LINE STAYS REACHABLE. lane.sh refuses past LANE_MAX_ATTEMPTS;
# the board opens the decision-needed issue. A job that swallowed that refusal
# would park the PR silently for the fourth time.
hb_reset; echo 9 > "$HAKUX_WORK/attempts/selftesthb"
hb_row 201 lane/selftesthb 2222222222222222222222222222222222222222
hb >/dev/null
check "an exhausted lane is not started again" bash -c '! grep -q systemd-run "$HB_LOG"'
check "the exhausted PR is labelled blocked:needs-owner" grep -q 'api -X POST repos/example/hakux/issues/201/labels.*blocked:needs-owner' "$HB_LOG"
check "and the comment hands it to the board's decision-needed path" hb_said "decision-needed"
check "quoting lane.sh's own refusal, so the count is visible" hb_said "LANE_MAX_ATTEMPTS"
rm -f "$HAKUX_WORK/attempts/selftesthb"

# The pickup is a TABLE of labels, not a branch per label: needs-remediation
# and the two audit labels join it as a row (lane.auditoutlet, PR #130).
check "the pickup is one table of labels" grep -q '^HANDBACK_ROWS=(' "$HERE/handback.sh"
check "handback.sh starts no session itself; lane.sh does" \
    bash -c '! grep -qE "^[^#]*systemd-run" "$HERE/handback.sh"'

# fold.sh's half: it records the cause and resolves nothing. A real conflict
# needs a real remote and a real push, so this pins the two lines that connect
# the jobs; the consumption of the cause file is checked behaviourally above.
check "fold.sh records the conflicting files where handback.sh reads them" \
    grep -q 'handback/cause/\$pr-\$head' "$HERE/fold.sh"
check "fold.sh calls the actor at the end of its tick" \
    grep -q 'jobs/handback.sh" "\$mode"' "$HERE/fold.sh"
check "fold.sh still resolves no conflict itself" \
    bash -c '! grep -qE "checkout --(ours|theirs)|merge -X|-s (ours|recursive)" "$HERE/fold.sh"'
check "roles/board.md tells the board handback.sh owns needs-rebase" \
    grep -q 'needs-rebase` is not yours' "$HERE/roles/board.md"

# The --jq the shim bypasses. gh runs it internally, so a typo in it is invisible
# to every check above; jq is the same program gh embeds.
if command -v jq >/dev/null 2>&1; then
    q=$(sed -n "s/.*--jq '\(sort_by(\.number).*\)' .*/\1/p" "$HERE/handback.sh" | head -1)
    got=$(printf '%s' '[{"number":9,"headRefName":"lane/x","headRefOid":"ab","labels":[{"name":"needs-rebase"},{"name":"folded"}]}]' \
          | jq -r "$q" 2>&1)
    check "the pickup query yields number/branch/head/labels" [ "$got" = "$(printf '9\tlane/x\tab\tneeds-rebase,folded')" ]
else
    echo "  note: jq not on PATH; the pickup query was not exercised"
fi

echo
echo "selftest: $pass passed, $fail failed (fake host in $T)"
[ "$fail" -eq 0 ]
