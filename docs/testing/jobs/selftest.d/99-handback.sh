# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# handback.sh: the actor for a PR a job handed back.
# Written as an append to selftest.sh (#132, lane/handback); carried here
# unchanged when that PR's third hand-back met this split. The hand-back this
# fragment's subject fixes is the same one that parked #132 three times, and
# the split is what stops the fourth.
#
# 99 because it sat last on the branch and nothing below it reads its state.
#
# Builds its own shims under $HB/bin -- it has to: the shared gh shim answers
# every `pr list` with "[]" and the shared systemctl answers every `is-active`
# with "active", which are exactly the two answers that make this job do
# nothing. Depends on no other fragment.

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

# AN IMPOSSIBLE ROW: one that came back for `--label needs-rebase` and does not
# carry it. `gh` filters server-side and this job never re-checked it, so the
# failure mode is not an empty list -- it is resuming, by name, whichever lane
# owns the first open PR on the repository, against ITS attempt budget. Not
# hypothetical: fold.sh now calls this job at the end of every tick, and the
# fold-ci fragment's own gh shim answers every `pr list` with one fixed row, so
# before this guard three of its checks went red because each fold tick resumed
# lane.foldci and commented on #102. A row like this means the filter did not
# happen; nothing about it can be trusted, including which lane it names.
#
# The row carries `harness` and NOTHING ELSE on purpose. Written with a stale
# label in it -- `fold-ready`, the obvious thing to reach for -- the two
# negative checks below pass against a build with NO guard at all, because the
# stale rule refuses the row first and the guard is never what did the work.
# Measured: with `harness,fold-ready` the un-guarded mutant failed two of these
# four; with `harness` it fails all four. The branch is a lane that really does
# have a worktree here, so an un-guarded build resumes it for real.
hb_reset; hb_row 204 lane/selftesthb ffffffffffffffffffffffffffffffffffffffff "harness"
out=$(hb list); hb >/dev/null
check "a row that came back WITHOUT the label it was filtered on resumes nobody" \
    bash -c '! grep -q systemd-run "$HB_LOG"'
check "  and it is refused as an unfiltered row, not silently as a stale label" \
    grep -q "the filter did not happen" <<< "$out"
check "  naming the labels it did come back with, so the broken filter is diagnosable" \
    grep -q "labels=harness" <<< "$out"
check "  and it comments on nothing: an unfiltered row names no PR worth telling" \
    bash -c '[ ! -s "$HB/comments.log" ]'

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
