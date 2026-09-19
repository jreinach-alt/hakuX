# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# fold.sh + handback.sh: a red about a base that has moved is handed back for a
# base merge, not refused forever.
#
# 87 because it sits with the other two fold gates (85 CI reporting, 86 the
# regressed gate) and reads none of their state.
#
# Self-contained: its own gh/systemctl/systemd-run shims under $SC/bin and its
# own HAKUX_WORK, because the shared gh shim answers every `pr view` GREEN and
# the shared systemctl answers every `is-active` active -- the two answers that
# make both jobs under test do nothing. The two halves DO share one
# $HAKUX_WORK on purpose: the cause file the fold half writes is the one the
# handback half reads, which is the join this change exists to create.

echo "== fold.sh: a red about a base that has moved is handed back, not refused forever"
# `selftest.d/86-fold-regressed.sh` was broken on master for most of
# 2026-09-19. `selftest` is a required check, so #152, #153, #155 and #163 all
# went red against the broken tree -- and GitHub does not re-run a pull
# request's checks when its base moves, so all four still read FAILURE hours
# after PR #167 fixed it. fold.sh refused them every tick, handback.sh fires
# only on `needs-rebase` and they had no conflict, board.sh only picks up
# unlabelled PRs and they were labelled: no actor at all, until a person
# pushed over them by hand.
SC="$T/staleci"; mkdir -p "$SC/bin" "$SC/work"/{briefs,wt,attempts} "$SC/work/logs"/{lane,fold,handback}
cat > "$SC/bin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"; echo "$args" >> "${SC_LOG:?}"
case "$1 $2" in
    # number, branch, head, isDraft, labels, title -- title last, the only
    # free-text field, as fold.sh's own --jq emits it.
    "pr list")  printf '%s\tlane/staleci\t%s\tfalse\t%s\tstaleci: a lane\n' \
                    "${SC_PR:?}" "${SC_HEAD:?}" "${SC_LABELS:-fold-ready}" ;;
    # TWO different --jq expressions go through `pr view` here: ci_green's,
    # which reduces the rollup to one word, and check_rows', which emits one
    # TSV line per check. Told apart by @tsv, which only the second has.
    "pr view")  if [[ "$args" == *"@tsv"* ]]; then cat "${SC_ROWS:?}" 2>/dev/null
                else echo "${SC_CI:?}"; fi ;;
    "pr comment") { echo "--- comment on $3"; cat "${args##*--body-file }"; } >> "${SC_COMMENTS:?}" ;;
    "api "*|"api -X"*)
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${SC_HAVE:-fold-ready}; exit 0; } ;;
esac
exit 0
EOF
cat > "$SC/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
# Every lane here has EXITED -- which is the case that actually stranded the
# four PRs on 2026-09-19: no session was running, so there was nothing to
# notice the jam. `is-active` false is the whole point of this shim.
case "$*" in *is-active*) exit 1 ;; *) exit 0 ;; esac
EOF
cat > "$SC/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${SC_LOG:?}"; exit 0
EOF
chmod +x "$SC/bin/"*
export SC SC_LOG="$SC/gh.log" SC_COMMENTS="$SC/comments.log" SC_ROWS="$SC/rows.tsv"
: > "$SC_LOG"; : > "$SC_COMMENTS"

# The clock this fixture reasons about, as real timestamps run through the
# same `date -u -d` the job uses -- a hand-typed epoch would be checking the
# fixture's arithmetic and not the job's.
FAIL_OLD=2026-09-19T17:14:32Z      # the run that stranded #152: before the fix
FAIL_NEW=2026-09-19T21:00:00Z      # a run against the repaired trunk
TIP_1=$(date -u -d 2026-09-19T19:47:52Z +%s)   # PR #167's green push run
TIP_2=$(date -u -d 2026-09-19T20:30:00Z +%s)   # the trunk moved again

sc_rows() {   # <name> <conclusion> <started> [...] -> the rollup for this tick
    : > "$SC_ROWS"
    while [ "$#" -ge 3 ]; do printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$SC_ROWS"; shift 3; done
}
sc_tick() {   # <ci word> <head> <tip sha> <tip epoch>: one tick of the real fold.sh
    SC_PR=301 SC_CI="$1" SC_HEAD="$2" FOLD_TIP_SHA="$3" FOLD_TIP_EPOCH="$4" \
    PATH="$SC/bin:$PATH" HAKUX_WORK="$SC/work" HAKUX_REPO_DIR="$REPO" \
        bash "$HERE/fold.sh" >/dev/null 2>&1
}
sc_list() {   # the same tick in `list` mode, whose whole contract is read-only
    SC_PR=301 SC_CI="$1" SC_HEAD="$2" FOLD_TIP_SHA="$3" FOLD_TIP_EPOCH="$4" \
    PATH="$SC/bin:$PATH" HAKUX_WORK="$SC/work" HAKUX_REPO_DIR="$REPO" \
        bash "$HERE/fold.sh" list 2>/dev/null
}
sc_said()  { grep -qF -- "$1" "$SC_COMMENTS"; }
# A negative runs as a function, not `bash -c '! grep ... "$SC/..."'`: $SC_LOG
# is exported but a path built from an unexported var in a child shell is "",
# grep fails, the negation succeeds and the check can never fail (85's header
# records the mutant that caught exactly that).
sc_unsaid() { ! grep -qF -- "$1" "$SC_COMMENTS"; }
sc_ncomments() { grep -c '^--- comment on 301' "$SC_COMMENTS" 2>/dev/null || echo 0; }
sc_labelled()  { grep -q "api -X POST repos/example/hakux/issues/301/labels.*$1" "$SC_LOG"; }
sc_unlabelled(){ grep -q "api -X DELETE repos/example/hakux/issues/301/labels/$1" "$SC_LOG"; }
sc_reset() { rm -rf "$SC/work/fold" "$SC/work/handback"; : > "$SC_LOG"; : > "$SC_COMMENTS"; }

HEAD_A=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
HEAD_B=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
TIPSHA1=1111111111111111111111111111111111111111
TIPSHA2=2222222222222222222222222222222222222222

# ------------------------------------------- the stale red: an actor at last
sc_reset; sc_rows selftest FAILURE "$FAIL_OLD" build SUCCESS "$FAIL_OLD"
out=$(sc_list RED "$HEAD_A" "$TIPSHA1" "$TIP_1")
check "list calls a red that predates the trunk head STALE" grep -q 'CI RED but STALE' <<< "$out"
check "  and list is still read-only: it labels nothing" sc_unlabelled fold-ready
check "  and says nothing on the PR" [ "$(sc_ncomments)" = 0 ]

sc_tick RED "$HEAD_A" "$TIPSHA1" "$TIP_1"
check "a stale red is reported on the PR" sc_said 'the red is not yours'
check "  naming the failing run and its own start time" sc_said "selftest, started $FAIL_OLD"
check "  and the trunk head it predates" sc_said "${TIPSHA1:0:10}"
check "  it rules out the re-run, which was measured and does not work" sc_said 'refs/pull/301/merge'
check "the PR is handed back: fold-ready off, needs-rebase on" \
    bash -c 'grep -q "api -X DELETE repos/example/hakux/issues/301/labels/fold-ready" "$SC_LOG" \
          && grep -q "api -X POST repos/example/hakux/issues/301/labels.*needs-rebase" "$SC_LOG"'
check "the cause is written where handback.sh reads it" [ -f "$SC/work/handback/cause/301-$HEAD_A" ]
check "  and it names the action, so the lane is told WHY and not just what" \
    grep -qx 'action=resume_stale_ci' "$SC/work/handback/cause/301-$HEAD_A"
check "  carrying the run as the detail" grep -q "^detail=selftest, started $FAIL_OLD" "$SC/work/handback/cause/301-$HEAD_A"
# A STALE RED IS NOT LICENCE TO FOLD. The gate stays; only "forever" goes.
check "a stale red does not fold: no merge worktree is ever created" [ ! -e "$SC/work/fold-wt" ]

# ONCE PER (PR, TRUNK HEAD). Each of these removes a label, writes a cause and
# starts a lane session; doing it twice on one pair acts on no new information.
sc_tick RED "$HEAD_A" "$TIPSHA1" "$TIP_1"
check "a second tick at the same trunk head hands it back again: no" [ "$(sc_ncomments)" = 1 ]
# ...but the trunk moving IS new information: the branch's red is stale about
# a different base now, and the lane may have been resumed and got nowhere.
sc_tick RED "$HEAD_A" "$TIPSHA2" "$TIP_2"
check "the trunk moving is a new pair, and is said once more" [ "$(sc_ncomments)" = 2 ]
check "  against the new trunk head" sc_said "${TIPSHA2:0:10}"
sc_tick RED "$HEAD_A" "$TIPSHA2" "$TIP_2"
check "  and only once for that one too" [ "$(sc_ncomments)" = 2 ]

# ------------------------------------------------- the red that is NOT stale
# The second mutant the brief asks for: the fresh verdict is ALSO red. Nothing
# here may hand it back -- that red is about the tree the PR actually has.
sc_reset; sc_rows selftest FAILURE "$FAIL_NEW" build SUCCESS "$FAIL_NEW"
sc_tick RED "$HEAD_B" "$TIPSHA1" "$TIP_1"
check "a red whose run POSTDATES the trunk head is live, and is reported as red" sc_said 'CI is red'
check "  it is not called stale" sc_unsaid 'the red is not yours'
check "  it is not handed back" bash -c '! grep -q "api -X POST repos/example/hakux/issues/301/labels.*needs-rebase" "$SC_LOG"'
check "  and no cause is written for it" [ ! -f "$SC/work/handback/cause/301-$HEAD_B" ]

# ONE LIVE FAILURE AMONG STALE ONES IS A LIVE RED. The test is over EVERY
# failing check, not the newest-looking one: a PR that really did break
# something, on a day the trunk also broke, must not be waved through to a
# lane as "not yours".
sc_reset; sc_rows selftest FAILURE "$FAIL_OLD" build FAILURE "$FAIL_NEW"
sc_tick RED "$HEAD_B" "$TIPSHA1" "$TIP_1"
check "a stale failure ALONGSIDE a live one is still a live red" sc_unsaid 'the red is not yours'

# AN IMPOSSIBLE ROW IS THE CHECK: a rollup gh calls RED with nothing failing in
# it. Every row here is plausible on its own, so a build that judged staleness
# from "the newest check" or from an empty failing set would pass an
# all-plausible fixture. `newest` starts at 0, which is before every trunk head
# there has ever been, so the empty case reads STALE unless it is refused.
sc_reset; sc_rows build "" 2026-09-19T21:30:00Z selftest PENDING 2026-09-19T21:30:00Z
sc_tick RED "$HEAD_B" "$TIPSHA1" "$TIP_1"
check "a rollup with NO failing check in it is never judged stale" sc_unsaid 'the red is not yours'

# A TIMESTAMP THAT CANNOT BE READ IS LIVE. `date -u -d ""` is not an error: it
# is MIDNIGHT TODAY at exit 0, so an entry with no startedAt would silently be
# compared as "started today" -- before the trunk head on any evening, which is
# every evening this job runs.
sc_reset; sc_rows selftest FAILURE ""
sc_tick RED "$HEAD_B" "$TIPSHA1" "$TIP_1"
check "a failing check with no start time is not judged stale" sc_unsaid 'the red is not yours'
sc_reset; sc_rows selftest FAILURE "not-a-date"
sc_tick RED "$HEAD_B" "$TIPSHA1" "$TIP_1"
check "nor is one whose start time will not parse" sc_unsaid 'the red is not yours'

# The other states are unchanged: this gate only ever adds an actor.
sc_reset; sc_rows selftest PENDING 2026-09-19T21:30:00Z
sc_tick NONE "$HEAD_B" "$TIPSHA1" "$TIP_1"
check "a head with no CI run at all is still reported as NONE, not as stale" \
    bash -c 'grep -qF "no CI run exists" "$SC_COMMENTS" && ! grep -qF "the red is not yours" "$SC_COMMENTS"'

# THE QUERY THE SHIM BYPASSES. gh runs `--jq` internally, so a typo in it is
# invisible to every check above; jq is the same program gh embeds. This is
# also the only place the empty-conclusion trap is reachable: `gh` prints ""
# for a run in flight and jq's `//` falls through on null and false ONLY, so
# `.conclusion // .state` yields "" and a running check reads as concluded.
if command -v jq >/dev/null 2>&1; then
    q=$(sed -n "s/^CHECK_ROWS_JQ='\(.*\)'$/\1/p" "$HERE/fold.sh" | head -1)
    check "fold.sh's rollup query is a single-line variable the test can reach" [ -n "$q" ]
    got=$(printf '%s' '{"statusCheckRollup":[
        {"__typename":"CheckRun","name":"build","conclusion":"","status":"IN_PROGRESS","startedAt":"2026-09-19T20:42:22Z"},
        {"__typename":"CheckRun","name":"selftest","conclusion":"FAILURE","status":"COMPLETED","startedAt":"2026-09-19T17:14:32Z"},
        {"__typename":"StatusContext","context":"legacy","state":"FAILURE","createdAt":"2026-09-19T17:10:00Z"}]}' \
        | jq -r "$q" 2>&1)
    want=$(printf 'build\tPENDING\t2026-09-19T20:42:22Z\nselftest\tFAILURE\t2026-09-19T17:14:32Z\nlegacy\tFAILURE\t2026-09-19T17:10:00Z')
    check "  an in-flight check reads PENDING, not \"\", and a StatusContext reads its state" [ "$got" = "$want" ]
else
    echo "  note: jq not on PATH; fold.sh's rollup query was not exercised"
fi

echo "== handback.sh: the stale red's lane is told it is not its defect"
# The other half of the join. The cause file below is the one the fold half
# WROTE, under the same $HAKUX_WORK -- if fold.sh stopped writing `action=`,
# or handback.sh stopped reading it, these go red rather than testing a
# fixture of their own invention.
HBS="$SC/hb"; mkdir -p "$HBS/bin"
cat > "$HBS/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${SC_LOG:?}"; args="$*"
case "$1 $2" in
    "pr list") [[ "$args" =~ --label\ ([A-Za-z0-9:_-]+) ]] && { f="$SC/prs.${BASH_REMATCH[1]}.tsv"; [ -f "$f" ] && cat "$f"; }; exit 0 ;;
    "pr comment") b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$SC_COMMENTS"; b=""; }; [ "$a" = --body-file ] && b=1; done
                  echo "--- end comment" >> "$SC_COMMENTS"; exit 0 ;;
    "api "*|"api -X"*) [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf 'needs-rebase\n'; exit 0; }; exit 0 ;;
esac
exit 0
EOF
cp "$SC/bin/systemctl" "$SC/bin/systemd-run" "$HBS/bin/"; chmod +x "$HBS/bin/"*
hbs() { ( export PATH="$HBS/bin:$PATH" HAKUX_WORK="$SC/work"; bash "$HERE/handback.sh" "$@" 2>&1 ); }
hbs_row() { printf '%s\tlane/%s\t%s\t%s\n' "$1" "$2" "$3" "${4:-needs-rebase}" > "$SC/prs.needs-rebase.tsv"; }
hbs_brief() { cat "$SC/work/briefs/staleci.md"; }

mkdir -p "$SC/work/wt/staleci"; echo "# the original brief" > "$SC/work/briefs/staleci.md"
: > "$SC_LOG"; : > "$SC_COMMENTS"
# The cause fold.sh wrote for $HEAD_A, above, at the FIRST trunk head.
printf 'label=needs-rebase\naction=resume_stale_ci\nbranch=lane/staleci\nhead=%s\ndetail=selftest, started %s\ntip=%s\n' \
    "$HEAD_A" "$FAIL_OLD" "$TIPSHA1" > "$SC/work/handback/cause/301-$HEAD_A"
hbs_row 301 staleci "$HEAD_A"; hbs >/dev/null
check "the stale red's lane is resumed, though its unit has exited" \
    grep -q 'systemd-run.*hakux-lane-staleci' "$SC_LOG"
check "its brief is told the red is about a base that has moved" \
    grep -q 'red is about a base that has moved' "$SC/work/briefs/staleci.md"
check "  naming the run and the date, so the lane can check it itself" \
    grep -qF "selftest, started $FAIL_OLD" "$SC/work/briefs/staleci.md"
check "  telling it NOT to start debugging the failing job" \
    grep -q 'Do not open the failing job' "$SC/work/briefs/staleci.md"
check "  and never claiming a conflict it does not have" \
    bash -c '! grep -q "no longer merges into" "$SC/work/briefs/staleci.md"'
check "  it still says merge, and still says why not rebase" \
    grep -q 'un-ancestors any registered' "$SC/work/briefs/staleci.md"
check "  and tells it to re-apply fold-ready afterwards" \
    grep -q 'gh-label.sh add 301 fold-ready' "$SC/work/briefs/staleci.md"
check "the PR comment says the red is stale, not that it conflicts" \
    bash -c 'grep -qF "its red is stale" "$SC_COMMENTS" && ! grep -qF "conflicting in" "$SC_COMMENTS"'

# THE DEFAULT MUST SURVIVE THE OVERRIDE. A conflict cause under the same label
# still gets the conflict brief; a dispatch that swallowed the row's own action
# would pass every check above and silently retitle every real rebase.
: > "$SC_LOG"; : > "$SC_COMMENTS"
printf 'label=needs-rebase\nbranch=lane/staleci\nhead=%s\nfiles=docs/testing/jobs/selftest.sh\n' "$HEAD_B" \
    > "$SC/work/handback/cause/301-$HEAD_B"
hbs_row 301 staleci "$HEAD_B"; hbs >/dev/null
check "a conflict cause at a new head still gets the conflict brief" \
    grep -q 'no longer merges into' "$SC/work/briefs/staleci.md"
check "  and its comment still names the conflicting files" sc_said 'conflicting in'

# `action=` comes out of a FILE and becomes the command word of an
# invocation. An unknown value falls back to the row's own action -- which is
# the label's meaning and is never wrong about what to DO -- and says so.
: > "$SC_LOG"; : > "$SC_COMMENTS"
HEAD_C=cccccccccccccccccccccccccccccccccccccccc
printf 'label=needs-rebase\naction=rm -rf /\nbranch=lane/staleci\nhead=%s\nfiles=a.sh\n' "$HEAD_C" \
    > "$SC/work/handback/cause/301-$HEAD_C"
hbs_row 301 staleci "$HEAD_C"; out=$(hbs)
check "an action the cause file invents is refused and named in the log" \
    grep -q "is not one of this job's" <<< "$out"
check "  and the row's own action runs instead" \
    [ "$(grep -c 'no longer merges into' "$SC/work/briefs/staleci.md")" -eq 2 ]

# THE LANE THAT IS GONE, NOT MERELY EXITED. An exited lane is resumed (every
# check above ran against `is-active` false, which is what the four stranded
# PRs had). A lane whose worktree is gone cannot be, and that PR was told so
# in a comment nothing polls -- so it now carries the label that means the
# owner's call and shows up in the roll-up.
: > "$SC_LOG"; : > "$SC_COMMENTS"
rm -rf "$SC/work/wt/staleci" "$SC/work/briefs/staleci.md"
HEAD_D=dddddddddddddddddddddddddddddddddddddddd
hbs_row 301 staleci "$HEAD_D"; hbs >/dev/null
check "a lane whose worktree is gone starts nothing" \
    bash -c '! grep -q "systemd-run.*hakux-lane-staleci" "$SC_LOG"'
check "  and its PR is labelled blocked:needs-owner, not only commented on" \
    grep -q 'api -X POST repos/example/hakux/issues/301/labels.*blocked:needs-owner' "$SC_LOG"
check "  saying plainly that nothing will act on it until someone does" \
    sc_said 'nothing will act on it until someone does'
