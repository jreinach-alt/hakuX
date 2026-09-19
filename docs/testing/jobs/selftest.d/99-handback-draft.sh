# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# handback.sh's second cause: a DRAFT PR whose lane has exited.
#
# 99, beside 99-handback.sh, because it is the same job and neither ordering
# matters -- this fragment builds its own shims under $HD/bin and its own
# fake lane, and reads nothing another fragment left. It does not reuse
# 99-handback.sh's $HB fixtures on purpose: they are a fixture for the label
# pickup, and a check that shares state with the checks it is next to cannot
# say which of them broke.
#
# THE DEFECT. Every actor filters drafts out -- board.sh skips isDraft,
# fleet.py counts only non-draft lane PRs, fold.sh refuses to fold one -- and
# while the lane is running that is right. Nothing joined isDraft (GitHub) to
# unit liveness (systemd), so on 2026-09-19 five finished, CI-green lane PRs
# (#137, #141, #145, #146, #148) sat in draft with no lane running and no
# actor that could ever touch them. Three of them had not failed: they ended
# WAITING, on a ten-minute CI run or a ninety-minute arm.

echo "== handback.sh: a draft PR whose lane has exited"
HD="$T/handback-draft"; mkdir -p "$HD/bin" "$HAKUX_WORK/wt" "$HAKUX_WORK/briefs"
cat > "$HD/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${HD_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        # Two pickups, two files. The draft pickup is the one that names
        # isDraft in its --json; the label pickup is the one with --label.
        if [[ "$args" == *isDraft* ]]; then
            [ -f "$HD/drafts.tsv" ] && cat "$HD/drafts.tsv"
        elif [[ "$args" =~ --label\ ([A-Za-z0-9:_-]+) ]]; then
            f="$HD/prs.${BASH_REMATCH[1]}.tsv"; [ -f "$f" ] && cat "$f"
        fi
        exit 0 ;;
    "pr comment")
        b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$HD/comments.log"; b=""; }; [ "$a" = --body-file ] && b=1; done
        echo "--- end comment" >> "$HD/comments.log"; exit 0 ;;
    "api "*|"api -X"*)
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${HD_LABELS:-}; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HD/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
# $HD/active holds one unit name per line; everything else is inactive.
case "$*" in
    *is-active*) u="${!#}"; grep -qxF -- "$u" "$HD/active" 2>/dev/null ;;
    *list-units*) cat "$HD/active" 2>/dev/null; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HD/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${HD_LOG:?}"; exit 0
EOF
chmod +x "$HD/bin/"*
export HD HD_LOG="$HD/gh.log"; : > "$HD_LOG"; : > "$HD/comments.log"; : > "$HD/active"
hd()       { ( export PATH="$HD/bin:$PATH"; bash "$HERE/handback.sh" "$@" 2>&1 ); }
hd_said()  { grep -qF -- "$1" "$HD/comments.log"; }
hd_ran()   { grep -q "systemd-run.*hakux-lane-$1" "$HD_LOG"; }
hd_reset() { : > "$HD_LOG"; : > "$HD/comments.log"; }
# Negatives run as FUNCTIONS, never `bash -c '! grep ... "$var"'`: a child
# shell sees only exported variables, so such a check is green against
# anything the moment the variable it reads is lane-local ($got, below, is).
hd_quiet()   { [ ! -s "$HD/comments.log" ]; }
hd_no_run()  { ! grep -q systemd-run "$HD_LOG"; }
hd_unsaid()  { ! grep -qF -- "$1" "$HD/comments.log"; }
hd_notin()   { ! grep -q "$1" <<< "$got"; }
hd_in()      { grep -q "$1" <<< "$got"; }
# <pr> <branch> <head> <labels> <isDraft> <ci> <quiet-secs>: one row exactly as
# the --jq emits it -- state BEFORE labels, because tab is IFS whitespace and an
# empty field in the middle of a `read` is not a field at all. Most lane PRs
# carry no labels, so this is the common row, not the corner. The query's own
# field order is pinned by the round-trip at the end of this fragment.
hd_draft() { printf '%s\t%s\t%s\tisDraft=%s ci=%s quiet=%s\t%s\n' \
                "$1" "$2" "$3" "${5:-true}" "${6:-GREEN}" "${7:-9000}" "${4:-}" > "$HD/drafts.tsv"; }

mkdir -p "$HAKUX_WORK/wt/selftesthd"; echo "# the original brief" > "$HAKUX_WORK/briefs/selftesthd.md"
rm -f "$HAKUX_WORK/attempts/selftesthd" "$HAKUX_WORK/handback/strand/selftesthd"

# ---------------------------------------------------------------- the join
# THE MEASUREMENT IT RESTORES. A draft lane PR, green, quiet for hours, unit
# not running: before this, no job in the harness asked both halves of that
# question and the PR was unreachable by anything but a person.
# This row carries NO labels, which is the common case and was the bug: with
# labels in the middle of the TSV, `IFS=$'\t' read` collapsed the empty field
# and every unlabelled stranded draft was refused as an unfiltered row.
D1=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1
hd_draft 301 lane/selftesthd "$D1"
out=$(hd list)
check "list names a stranded draft lane it would resume" grep -q "WOULD RESUME lane.selftesthd" <<< "$out"
check "list names the cause as a draft strand, not a label" grep -q "draft-strand-quiet" <<< "$out"
check "list starts no session" hd_no_run

hd_reset; hd >/dev/null
check "a stranded draft resumes its lane" hd_ran selftesthd
check "the resume is announced on the PR" hd_said "[job.handback] Resumed \`lane.selftesthd\`"
check "and says why nothing else could have done it" hd_said "all skip drafts"

# THE RESUME MUST CARRY THE RESOLVED STATE. A lane resumed with no new
# information repeats what it did before, which is how a PR burns four
# attempts having never been wrong about anything.
B="$HAKUX_WORK/briefs/selftesthd.md"
check "the strand goes into the lane's own brief" grep -q "is a draft and your lane was not running" "$B"
check "the brief names the CI state on the head" grep -q "GREEN" "$B"
check "the brief names the head it is talking about" grep -q "aaaaaaaaaa" "$B"
check "the brief tells the lane to mark the PR ready itself" grep -q "gh pr ready 301" "$B"
check "the original brief is still under it" grep -q "the original brief" "$B"

# ...AND THIS JOB MUST NOT MARK IT READY. The definition of done includes
# NOTES.md, the Files: line and the prediction refs; a script that flipped
# isDraft on green CI would declare finished work nobody verified.
# Anchored on the CALL, not on the words: the brief this job writes into
# tells the lane to run `gh pr ready` itself, so a grep for the phrase matches
# the prose and proves nothing. An invocation is `gh pr <verb>` at the start of
# a command; a mention is preceded by a backtick.
hd_verbs=$(grep -oE '(^|[^`])gh pr [a-z]+' "$HERE/handback.sh" | sed 's/.*gh pr //' | sort -u | tr '\n' ' ')
check "the job calls only gh pr list and gh pr comment -- it never marks one ready" \
    [ "$hd_verbs" = "comment list " ]
check "and says on the PR that the call stays with the lane" hd_said "does **not** mark a PR ready"

# WAITING IS NOT FAILING. lane.sh counts every resume as an attempt; the
# fourth escalates the model and the fifth is refused. A lane that ended
# because CI takes ten minutes has failed at nothing, so the count goes back.
check "a strand resume does not spend one of the lane's attempts" \
    [ "$(cat "$HAKUX_WORK/attempts/selftesthd" 2>/dev/null || echo 0)" = 0 ]
check "and the PR is told so, so the counter is not a mystery" hd_said "This did not spend one of the lane's attempts"

# ONCE PER CAUSE. A lane resumed every 30 minutes because its CI is still
# pending is worse than a stranded PR.
hd_reset; hd >/dev/null
check "the same head does not strand-resume the lane again" hd_no_run
check "and says nothing on the PR the second time" hd_quiet

# A DRAFT WITH A RUNNING LANE IS UNTOUCHABLE -- that is the normal state of
# every working lane, and a false positive here kills live work. The check is
# on the UNIT, never on a timestamp: a lane can be quiet for hours mid-build.
D2=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2
hd_reset; echo "hakux-lane-selftesthd" > "$HD/active"; hd_draft 301 lane/selftesthd "$D2"
out=$(hd list); hd >/dev/null
check "a draft whose lane IS running is not resumed" hd_no_run
check "  not even when it has been quiet for hours" grep -q "still running" <<< "$out"
check "  and nothing is said on the PR" hd_quiet
check "the liveness half of the join is systemd, not a clock" \
    grep -q 'systemctl --user is-active --quiet "hakux-lane-\$name"' "$HERE/handback.sh"
: > "$HD/active"

# A LANE THAT IS STILL WAITING IS NOT STRANDED. An arm is ~90 minutes. Resumed
# at 30, the session is handed the same "still queued" it ended on -- and the
# once-per-head marker would then stop it ever being resumed at that head
# again, so the false positive is not merely wasteful, it is terminal.
D3=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa3
# The strand count IS incremented by a resume -- that is what makes the cap
# below reachable at all -- so each block that needs a resume clears it first.
check "a strand resume is counted towards the cap" \
    [ "$(cat "$HAKUX_WORK/handback/strand/selftesthd" 2>/dev/null)" = 1 ]
rm -f "$HAKUX_WORK/handback/strand/selftesthd"
hd_reset; hd_draft 301 lane/selftesthd "$D3" "" true GREEN 600
out=$(hd list); hd >/dev/null
check "a draft quiet for only ten minutes is left alone" hd_no_run
check "  and the tick says the clock is why" grep -q "still waiting" <<< "$out"
check "  leaving no marker, so the next tick looks again" \
    [ ! -f "$HAKUX_WORK/handback/done/draft-strand-quiet-301-$D3" ]
hd_reset; hd_draft 301 lane/selftesthd "$D3" "" true GREEN 9000; hd >/dev/null
check "and the same head past the clock does resume it" hd_ran selftesthd

# A JUDGED ARM IS A LANDING, NOT A CLOCK. arms.sh labels the PR `verified` or
# `regressed` when a verdict is posted; that is information the lane has never
# seen, so it does not wait out DRAFT_STRAND_SECS -- and it is a DIFFERENT
# cause from the quiet clock, so a verdict landing after a quiet resume still
# reaches the lane at the same head.
D4=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa4
rm -f "$HAKUX_WORK/handback/strand/selftesthd"
hd_reset; hd_draft 301 lane/selftesthd "$D4" "" true GREEN 9000; hd >/dev/null
hd_reset; hd_draft 301 lane/selftesthd "$D4" "regressed" true GREEN 60
out=$(hd list); hd >/dev/null
check "a verdict landing at the same head resumes the lane again" hd_ran selftesthd
check "  as a cause of its own, without waiting out the quiet clock" \
    grep -q "WOULD RESUME lane.selftesthd (draft-strand-arm)" <<< "$out"
check "the brief tells the lane to read the verdict first" grep -q "Read that comment before anything else" "$B"
check "  and that a regressed PR is not fold-ready" grep -q "regressed\` PR is not fold-ready" "$B"

# THE BOUND THAT REPLACES THE ATTEMPT THIS CAUSE DOES NOT SPEND. Putting the
# counter back means the escalation policy can never end this, so something
# else must: a lane handed the resolved state DRAFT_STRAND_MAX times and still
# in draft is not waiting on anything this job can see.
D5=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5
hd_reset; mkdir -p "$HAKUX_WORK/handback/strand"; echo 3 > "$HAKUX_WORK/handback/strand/selftesthd"
rm -f "$HAKUX_WORK/handback/done/strandmax-301"
hd_draft 301 lane/selftesthd "$D5" "" true GREEN 9000
out=$(hd list); hd >/dev/null
check "a lane strand-resumed to the cap is not resumed again" hd_no_run
check "  and list says the cap is why" grep -q "DRAFT_STRAND_MAX" <<< "$out"
check "  the PR is labelled blocked:needs-owner" \
    grep -q 'api -X POST repos/example/hakux/issues/301/labels.*blocked:needs-owner' "$HD_LOG"
check "  and the comment says nothing else was going to stop it" hd_said "nothing else was going to stop this"
hd_reset; hd >/dev/null
check "  said once, not once a tick" hd_quiet
rm -f "$HAKUX_WORK/handback/strand/selftesthd" "$HAKUX_WORK/handback/done/strandmax-301"

# A PR ALREADY OWNED BY ANOTHER ACTOR IS NOT UNOWNED. `needs-rebase` has the
# rows above, the audit labels have the outlet, `blocked:needs-owner` has a
# person. Acting on one of those here is two sessions on one cause.
D6=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa6
for stale in needs-rebase needs-audit-1 needs-remediation blocked:needs-owner folded; do
    hd_reset; hd_draft 301 lane/selftesthd "$D6" "$stale" true GREEN 9000
    out=$(hd list); hd >/dev/null
    check "a draft carrying $stale is left to its own actor" hd_no_run
    # ...and left alone BY THE STALE RULE. Without this the check is green
    # against a build that has no draft pickup at all, which is the one it
    # replaces: a negative alone cannot tell "guarded" from "inert".
    check "  and says so, rather than never having seen the PR" \
        grep -q "$stale; already moved on" <<< "$out"
done

# AN IMPOSSIBLE ROW IS THE CHECK. Both halves of the draft filter live in the
# --jq, which nothing downstream re-reads. A row that comes back not a draft,
# or not on a lane/* branch, means the filter did not happen -- and the failure
# mode is not an empty list, it is resuming whichever lane owns the first open
# PR on the repository. The rows below are refused for the SHAPE they are in,
# not by a stale label: they carry none.
D7=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa7
hd_reset; hd_draft 301 lane/selftesthd "$D7" "" false GREEN 9000
out=$(hd list); hd >/dev/null
check "a row from the draft pickup that is not a draft resumes nobody" \
    hd_no_run
check "  refused as an unfiltered row, so the broken filter is diagnosable" \
    grep -q "the filter did not happen" <<< "$out"
check "  and it comments on nothing: an unfiltered row names no PR worth telling" \
    hd_quiet
hd_reset; hd_draft 301 claude/hakux-something "$D7" "" true GREEN 9000
out=$(hd list); hd >/dev/null
check "a row from the draft pickup on a non-lane branch resumes nobody" \
    hd_no_run
check "  refused for the shape it is in, not by never having been picked up" \
    grep -q "which is not lane/\*; the filter did not happen" <<< "$out"
check "  and is not commented on a person's PR" \
    hd_quiet

# A lane/cloud-* draft reaches the lane-naming rule, which is the right place
# for it -- but the comment must not name a label that does not exist.
D8=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa8
hd_reset; rm -f "$HAKUX_WORK/handback/done/noname-303"
hd_draft 303 lane/cloud-109 "$D8" "" true GREEN 9000; hd >/dev/null
check "a stranded lane/cloud-* draft starts no local lane" hd_no_run
check "  and is told cloud lanes remediate themselves" hd_said "cloud lanes remediate themselves"
check "  in words, not by naming a label the PR does not carry" \
    hd_unsaid '`draft-strand'
check "  saying what it actually observed" hd_said "unit is not running"

# THE ACTOR HAS TO RUN ON THE DAY IT IS NEEDED. handback.sh has no timer of its
# own: fold.sh calls it at the end of every tick. fold.sh used to `exit 0` the
# moment nothing carried `fold-ready` -- and NONE of handback's causes is that
# label. A handed-back PR has had `fold-ready` removed; a stranded draft never
# had it. So the one state in which nothing folds is exactly the state in which
# every PR that needs this actor is waiting, and the actor did not run.
hd_fold() { ( export PATH="$HD/bin:$PATH"; bash "$HERE/fold.sh" "$@" 2>&1 ); }
hd_reset; rm -f "$HD/drafts.tsv" "$HD/prs.fold-ready.tsv"
out=$(hd_fold list)
check "with nothing to fold, the fold tick still says so" \
    grep -q "nothing labelled fold-ready" <<< "$out"
# Anchored on a call ONLY handback.sh makes. `isDraft` was the first thing
# reached for and it is in fold.sh's own candidate query, so the check was
# green against the build it was written to falsify -- the grep matched the
# caller, not the callee.
check "  and still runs the handback actor" \
    grep -q -- "--label needs-rebase" "$HD_LOG"

# BOTH PICKUPS SHARE ONE BODY -- the lane name, the once-per-cause key, the
# worktree check, the liveness check, the cap, the counter, the comment are
# written once. A second copy is how the two causes drift apart.
check "there is one resume call site, not one per pickup" \
    [ "$(grep -c '"\$LANE_SH" resume' "$HERE/handback.sh")" -eq 1 ]
hd_no_systemd_run() { ! grep -qE "^[^#]*systemd-run" "$HERE/handback.sh"; }
check "handback.sh still starts no session itself; lane.sh does" hd_no_systemd_run
check "the draft pickup is a function of its own, not a line in the table" \
    grep -q '^stranded_drafts()' "$HERE/handback.sh"
check "roles/lane.md stops asking a waiting lane for something it cannot do" \
    grep -q 'lane.<name>] waiting:' "$HERE/roles/lane.md"
check "roles/board.md says the strand is handback.sh's, not the board's" \
    grep -q 'draft whose unit has exited is not yours' "$HERE/roles/board.md"

# THE --jq THE SHIM BYPASSES. gh runs it internally, so every check above is
# blind to a typo in it; jq is the same program gh embeds. This is the only
# place the real query is exercised.
if command -v jq >/dev/null 2>&1; then
    q=$(python3 - "$HERE/handback.sh" <<'PYQ'
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
fn = re.search(r"^stranded_drafts\(\).*?\n\}", src, re.S | re.M).group(0)
print(re.search(r"--jq '(.*?)'", fn, re.S).group(1))
PYQ
)
    fixture='[{"number":9,"headRefName":"lane/x","headRefOid":"ab","isDraft":true,
               "labels":[{"name":"verified"}],"updatedAt":"2020-01-01T00:00:00Z",
               "statusCheckRollup":[{"conclusion":"SUCCESS"},{"conclusion":"SKIPPED"}]},
              {"number":10,"headRefName":"lane/y","headRefOid":"cd","isDraft":false,
               "labels":[],"updatedAt":"2020-01-01T00:00:00Z","statusCheckRollup":[]},
              {"number":11,"headRefName":"claude/z","headRefOid":"ef","isDraft":true,
               "labels":[],"updatedAt":"2020-01-01T00:00:00Z","statusCheckRollup":[]},
              {"number":12,"headRefName":"lane/w","headRefOid":"gh","isDraft":true,
               "labels":[],"updatedAt":"2020-01-01T00:00:00Z",
               "statusCheckRollup":[{"conclusion":"SUCCESS"},{"conclusion":"FAILURE"}]},
              {"number":13,"headRefName":"lane/v","headRefOid":"ij","isDraft":true,
               "labels":[],"updatedAt":"2020-01-01T00:00:00Z","statusCheckRollup":[]},
              {"number":14,"headRefName":"lane/u","headRefOid":"kl","isDraft":true,
               "labels":[],"updatedAt":"2020-01-01T00:00:00Z",
               "statusCheckRollup":[{"conclusion":null,"state":"PENDING"}]}]'
    got=$(printf '%s' "$fixture" | jq -r "$q" 2>&1)
    check "the draft query yields number/branch/head/state/labels" \
        grep -q "^9	lane/x	ab	isDraft=true ci=GREEN quiet=[0-9][0-9]*	verified$" <<< "$got"
    check "  a non-draft PR is not in the pickup at all" hd_notin "^10	"
    check "  nor a PR whose head is not a lane/ branch" hd_notin "^11	"
    check "  a failing check reads RED" grep -q "^12	lane/w	gh	isDraft=true ci=RED " <<< "$got"
    check "  no runs at all reads NONE, never GREEN" grep -q "^13	lane/v	ij	isDraft=true ci=NONE " <<< "$got"
    check "  an unconcluded check reads PENDING, never GREEN" grep -q "^14	lane/u	kl	isDraft=true ci=PENDING " <<< "$got"
    # The empty field goes LAST or `read` eats it. A PR with no labels must
    # still end in a delimiter with nothing after it, never carry its state one
    # column to the right.
    check "  a PR with no labels ends the row, it does not shift the state left" \
        grep -q "^13	lane/v	ij	isDraft=true ci=NONE quiet=[0-9][0-9]*	$" <<< "$got"
    # The quiet clock is GitHub's updatedAt, not a file on this host: a job
    # redeployed at noon must not restart every stranded PR's clock at noon.
    check "  quiet is seconds since the PR last changed, and 2020 is a long time" \
        [ "$(sed -n '1s/.*quiet=\([0-9]*\).*/\1/p' <<< "$got")" -gt 100000000 ]
else
    echo "  note: jq not on PATH; the draft pickup query was not exercised"
fi
rm -f "$HD/drafts.tsv"
