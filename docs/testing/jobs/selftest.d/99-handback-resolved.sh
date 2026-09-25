# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# handback.sh: a `needs-rebase` PR whose conflict the lane has already resolved.
#
# THE DEFECT, 2026-09-25. `resume_rebase` ends "once CI is green on the new
# head, swap needs-rebase for fold-ready". A lane cannot wait ten minutes, so it
# pushes the merge and exits with the swap undone; the PR still carries
# `needs-rebase`, its head is new, and the next tick resumed it again for a
# conflict that no longer existed. #234 wasted an attempt that way; #237 was
# labelled `blocked:needs-owner` with a clean head whose CI went green minutes
# later.
#
# Same shim shape as 99-handback.sh, under its own $HR so neither fragment can
# say the other's check broke. The one thing those shims cannot fake is the
# merge: handback.sh asks `git merge-tree` about real commits, so this builds a
# real origin (a bare repository) and a real clone, and points HAKUX_REPO_DIR
# at the clone. Nothing here touches the checkout the self-test runs from.

echo "== handback.sh: a needs-rebase PR whose conflict is already resolved"
HR="$T/handback-resolved"; mkdir -p "$HR/bin" "$HAKUX_WORK/wt" "$HAKUX_WORK/briefs"
cat > "$HR/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${HR_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        [[ "$args" =~ --label\ ([A-Za-z0-9:_-]+) ]] && { f="$HR/prs.${BASH_REMATCH[1]}.tsv"; [ -f "$f" ] && cat "$f"; }
        exit 0 ;;
    "pr view")
        # head_ci's answer, as its --jq emits it: "<headRefOid>\t<STATE>". The
        # query itself is run through the real jq at the end of this fragment.
        [ -f "$HR/ci.$3" ] && cat "$HR/ci.$3"; exit 0 ;;
    "pr comment")
        b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$HR/comments.log"; b=""; }; [ "$a" = --body-file ] && b=1; done
        echo "--- end comment" >> "$HR/comments.log"; exit 0 ;;
    "api "*|"api -X"*)
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { echo needs-rebase; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HR/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) exit 3 ;;
    *list-units*) exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HR/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${HR_LOG:?}"; exit 0
EOF
chmod +x "$HR/bin/"*
export HR HR_LOG="$HR/gh.log"; : > "$HR_LOG"; : > "$HR/comments.log"

# ---- a real trunk and four real lane heads
#   base -- M (master: f.txt = master)
#     \---- C (lane/hrconf: f.txt = lane)          conflicts
#     \---- K (lane/hr*:    g.txt added)            merges cleanly, lacks M
#            \-- merge of M                         contains the trunk
hr_git() { git -c user.name=t -c user.email=t@t -c init.defaultBranch=master -c advice.detachedHead=false "$@"; }
rm -rf "$HR/origin.git" "$HR/seed" "$HR/clone"
hr_git init -q --bare "$HR/origin.git"
hr_git init -q "$HR/seed"
echo base > "$HR/seed/f.txt"; hr_git -C "$HR/seed" add f.txt; hr_git -C "$HR/seed" commit -qm base
hr_git -C "$HR/seed" branch -q side
echo master > "$HR/seed/f.txt"; hr_git -C "$HR/seed" commit -qam master
hr_git -C "$HR/seed" checkout -q -b lane/hrconf side
echo lane > "$HR/seed/f.txt"; hr_git -C "$HR/seed" commit -qam conflicting
hr_git -C "$HR/seed" checkout -q -b lane/hrclean side
echo g > "$HR/seed/g.txt"; hr_git -C "$HR/seed" add g.txt; hr_git -C "$HR/seed" commit -qm clean
hr_git -C "$HR/seed" checkout -q -b lane/hrmerged lane/hrclean
hr_git -C "$HR/seed" merge -q --no-edit master
hr_git -C "$HR/seed" push -q "$HR/origin.git" master lane/hrconf lane/hrclean lane/hrmerged
hr_git clone -q "$HR/origin.git" "$HR/clone"
H_TIP=$(git -C "$HR/seed" rev-parse master)
H_CONF=$(git -C "$HR/seed" rev-parse lane/hrconf)
H_CLEAN=$(git -C "$HR/seed" rev-parse lane/hrclean)
H_MERGED=$(git -C "$HR/seed" rev-parse lane/hrmerged)
# Every clean-case branch name points at a clean head; the row's sha is what is judged.
for b in hrgreen hrpend hrred hrnone hrstale hrlive; do
    hr_git -C "$HR/seed" push -q "$HR/origin.git" "lane/hrclean:refs/heads/lane/$b"
done

hr()       { ( export PATH="$HR/bin:$PATH" HAKUX_REPO_DIR="$HR/clone"; bash "$HERE/handback.sh" "$@" 2>&1 ); }
hr_reset() { : > "$HR_LOG"; : > "$HR/comments.log"; rm -f "$HR"/prs.*.tsv "$HR"/ci.*; }
hr_row()   { printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "${4:-needs-rebase}" > "$HR/prs.needs-rebase.tsv"; }
hr_ci()    { printf '%s\t%s\n' "$2" "$3" > "$HR/ci.$1"; }
hr_lane()  { mkdir -p "$HAKUX_WORK/wt/$1"; echo "# brief for $1" > "$HAKUX_WORK/briefs/$1.md"; rm -f "$HAKUX_WORK/attempts/$1"; }
# Negatives as functions, never `bash -c '! grep'` over an unexported variable.
hr_ran()       { grep -q "systemd-run.*hakux-lane-$1" "$HR_LOG"; }
hr_not_ran()   { ! grep -q "systemd-run" "$HR_LOG"; }
hr_relabel()   { grep -q "api -X DELETE repos/example/hakux/issues/$1/labels/needs-rebase" "$HR_LOG" \
                 && grep -q "api -X POST repos/example/hakux/issues/$1/labels -f labels\[\]=fold-ready" "$HR_LOG"; }
hr_no_label()  { ! grep -q "api -X" "$HR_LOG"; }
hr_said()      { grep -qF -- "$1" "$HR/comments.log"; }
hr_quiet()     { [ ! -s "$HR/comments.log" ]; }
hr_in()        { grep -qF -- "$1" <<< "$got"; }
hr_count_in()  { [ "$(grep -cF -- "$1" <<< "$got")" -eq "$2" ]; }

# (a) THE HEAD STILL CONFLICTS: resumed, exactly as before.
hr_reset; hr_lane hrconf; hr_row 301 lane/hrconf "$H_CONF"; hr_ci 301 "$H_CONF" GREEN
got=$(hr)
check "(a) a head that still conflicts resumes its lane" hr_ran hrconf
check "(a)   and is not relabelled, even with CI GREEN" hr_no_label
check "(a)   and the resume is announced as before" hr_said "[job.handback] Resumed \`lane.hrconf\`"
check "(a)   the brief still says it no longer merges" grep -q "no longer merges into" "$HAKUX_WORK/briefs/hrconf.md"

# (b) CLEAN AND GREEN: the lane's own last step, done here. No resume, no attempt.
hr_reset; hr_lane hrgreen; echo 2 > "$HAKUX_WORK/attempts/hrgreen"
hr_row 302 lane/hrgreen "$H_CLEAN"; hr_ci 302 "$H_CLEAN" GREEN
got=$(hr list)
check "(b) list says it would relabel, not resume" hr_in "WOULD RELABEL fold-ready (no resume)"
check "(b)   and list changes no label" hr_no_label
got=$(hr)
check "(b) a clean, green head is relabelled needs-rebase -> fold-ready" hr_relabel 302
check "(b)   lane.sh is NOT called" hr_not_ran
check "(b)   the attempt counter is unchanged" [ "$(cat "$HAKUX_WORK/attempts/hrgreen")" = 2 ]
check "(b)   the brief is untouched" [ "$(cat "$HAKUX_WORK/briefs/hrgreen.md")" = "# brief for hrgreen" ]
check "(b)   the comment names the head" hr_said "${H_CLEAN:0:10}"
check "(b)   and the trunk head it was checked against" hr_said "\`master\` at \`${H_TIP:0:10}\`"
check "(b)   and the CI state" hr_said "**GREEN**"
check "(b)   and says no attempt was spent" hr_said "no attempt was spent"
check "(b)   exactly one comment" [ "$(grep -c -- '--- end comment' "$HR/comments.log")" -eq 1 ]
check "(b)   the tick log says why" hr_in "relabelled needs-rebase -> fold-ready, lane not resumed"

# (c) CLEAN AND PENDING: waiting, not failing. Nothing called, nothing labelled.
hr_reset; hr_lane hrpend; hr_row 303 lane/hrpend "$H_CLEAN"; hr_ci 303 "$H_CLEAN" PENDING
got=$(hr)
check "(c) a clean, pending head resumes nobody" hr_not_ran
check "(c)   is not relabelled" hr_no_label
check "(c)   and comments nothing" hr_quiet
check "(c)   the log says it is waiting" hr_in "CI PENDING, waiting (not resumed)"
got=$(hr)
check "(c)   and says so once per head, not once per tick" hr_count_in "CI PENDING" 0
check "(c)   a second tick still resumes nobody" hr_not_ran
check "(c)   the attempt counter was never written" [ ! -f "$HAKUX_WORK/attempts/hrpend" ]

# (d) CLEAN AND RED: a live failure; the lane needs it back. Three reasons, one
# per state the red can be in, so the lane reads the right sentence.
hr_reset; hr_lane hrred; hr_row 304 lane/hrred "$H_CLEAN"; hr_ci 304 "$H_CLEAN" RED
got=$(hr)
check "(d) a clean, red head resumes its lane" hr_ran hrred
check "(d)   and is not relabelled" hr_no_label
check "(d)   the comment says the conflict no longer reproduces" hr_said "the conflict no longer reproduces"
check "(d)   and the brief carries the check it was resumed on" grep -q "Checked before this resume" "$HAKUX_WORK/briefs/hrred.md"

hr_reset; hr_lane hrstale; hr_row 305 lane/hrstale "$H_CLEAN"; hr_ci 305 "$H_CLEAN" RED
printf 'label=needs-rebase\naction=resume_stale_ci\nbranch=lane/hrstale\nhead=%s\ndetail=selftest, started 2026-01-01T00:00:00Z\n' "$H_CLEAN" \
    > "$HAKUX_WORK/handback/cause/305-$H_CLEAN"
got=$(hr)
check "(d) a clean red head handed back as stale CI resumes its lane" hr_ran hrstale
check "(d)   and the reason names the stale-CI cause" hr_said "its red is the stale-CI cause"
check "(d)   the brief is the stale-CI one, not the conflict one" grep -q "red is about a base that has moved" "$HAKUX_WORK/briefs/hrstale.md"

hr_reset; hr_lane hrlive; hr_row 306 lane/hrlive "$H_MERGED"; hr_ci 306 "$H_MERGED" RED
git -C "$HR/seed" push -q "$HR/origin.git" "lane/hrmerged:refs/heads/lane/hrlive" -f 2>/dev/null
got=$(hr)
check "(d) a red head that already contains the trunk resumes its lane" hr_ran hrlive
check "(d)   and the reason calls it a live failure" hr_said "live failure on this branch"

# (e) CLEAN AND NO CI AT ALL: not green. Never relabelled.
hr_reset; hr_lane hrnone; hr_row 307 lane/hrnone "$H_CLEAN"; hr_ci 307 "$H_CLEAN" NONE
got=$(hr)
check "(e) a clean head with no CI run is not relabelled" hr_no_label
check "(e)   it is resumed as before" hr_ran hrnone
check "(e)   and told it has no CI run" hr_said "NO CI run at all"

# A PUSH BETWEEN THE PICKUP AND THE CI READ: the green belongs to another commit.
hr_reset; hr_lane hrgreen; hr_row 308 lane/hrgreen "$H_CLEAN"; hr_ci 308 "$H_MERGED" GREEN
got=$(hr)
check "a CI state read for a different head relabels nothing" hr_no_label
check "  and resumes nobody; the next tick sees the new head" hr_not_ran
check "  and says the head moved" hr_in "head moved"

# THE jq THE SHIM BYPASSES: head_ci's query, through the real jq, with the
# traps the classifier exists for -- "" for a running check, and no runs at all.
if command -v jq >/dev/null 2>&1; then
    q=$(python3 - "$HERE/handback.sh" <<'PYQ'
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
d = re.search(r"^CI_STATE_JQ='(.*?)'$", src, re.S | re.M).group(1)
fn = re.search(r"^head_ci\(\).*?\n\}", src, re.S | re.M).group(0)
print(d + re.search(r"--jq \"\$CI_STATE_JQ\"'(.*?)'", fn, re.S).group(1))
PYQ
)
    hr_jq() { printf '%s' "{\"headRefOid\":\"ab\",\"statusCheckRollup\":$1}" | jq -r "$q" 2>&1; }
    check "head_ci: all success reads GREEN" [ "$(hr_jq '[{"conclusion":"SUCCESS"},{"conclusion":"SKIPPED"}]')" = "ab	GREEN" ]
    check "head_ci: an empty conclusion reads PENDING, never GREEN" \
        [ "$(hr_jq '[{"conclusion":"SUCCESS"},{"conclusion":"","status":"IN_PROGRESS"}]')" = "ab	PENDING" ]
    check "head_ci: no runs at all reads NONE, never GREEN" [ "$(hr_jq '[]')" = "ab	NONE" ]
    check "head_ci: a failure reads RED" [ "$(hr_jq '[{"conclusion":"SUCCESS"},{"conclusion":"FAILURE"}]')" = "ab	RED" ]
else
    echo "  note: jq not on PATH; head_ci's query was not exercised"
fi
check "one classifier: the draft pickup and head_ci both use CI_STATE_JQ" \
    [ "$(grep -c -- '--jq "$CI_STATE_JQ"' "$HERE/handback.sh")" -eq 2 ]
hr_reset
