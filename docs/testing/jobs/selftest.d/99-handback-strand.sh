# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# handback.sh's `draft-strand-arm`: resumed once per new VERDICT, not once per
# new head, and not at all while the lane's own arm is in flight.
#
# After 99-handback-draft.sh, whose gh/systemctl/systemd-run shims it copies
# into a directory of its own -- the same shims, so a row here is read exactly
# as that fragment's are, but none of its state, so a red here names this
# fragment's cause and not a neighbour's.
#
# THE DEFECT, measured 2026-09-25 on PR #245. The strand marker was
# `$label-$pr-$head` for both strand causes. lane.vshnobegin242 got one judged
# FAIL, registered a 3-run replicate to supersede it -- correct -- and was
# strand-resumed at 16:10Z, 16:29Z and 16:32Z on that one verdict, because
# every push made a new head. At 16:42Z it hit DRAFT_STRAND_MAX and was
# labelled `blocked:needs-owner` with its replicate still queued on the Thor.

echo "== handback.sh: a strand-arm resume is keyed on verdicts, not on the head"
HS="$T/handback-strand"; mkdir -p "$HS/bin" "$HAKUX_WORK/wt/selftesths"
for s in gh systemctl systemd-run; do
    cp "$T/handback-draft/bin/$s" "$HS/bin/$s" 2>/dev/null || bad "99-handback-draft.sh's $s shim is not there to build on"
done
: > "$HS/gh.log"; : > "$HS/comments.log"; : > "$HS/active"
echo "# the original brief" > "$HAKUX_WORK/briefs/selftesths.md"
rm -f "$HAKUX_WORK/attempts/selftesths" "$HAKUX_WORK/handback/strand/selftesths"
HS_TICK="$HAKUX_WORK/logs/handback/tick.log"
HS_A="$HAKUX_WORK/arms"; HS_Q="$DISPATCH_DIR"
mkdir -p "$HS_A/pairs" "$HS_A/judged" "$HS_Q/queue" "$HS_Q/running"

hs()        { ( export HD="$HS" HD_LOG="$HS/gh.log" PATH="$HS/bin:$PATH"; bash "$HERE/handback.sh" "$@" 2>&1 ); }
hs_reset()  { : > "$HS/gh.log"; : > "$HS/comments.log"; }
# Counted, not grepped: "one resume" means one, and a job that resumed twice in
# a tick would pass a grep.
hs_runs()   { grep -c "systemd-run.*hakux-lane-selftesths" "$HS/gh.log"; }
hs_ran()    { [ "$(hs_runs)" -eq 1 ]; }
hs_no_run() { [ "$(hs_runs)" -eq 0 ]; }
hs_quiet()  { [ ! -s "$HS/comments.log" ]; }
hs_said()   { grep -qF -- "$1" "$HS/comments.log"; }
hs_count()  { cat "$HAKUX_WORK/handback/strand/selftesths" 2>/dev/null || echo 0; }
# <head> <labels> <quiet>: one draft row, as 99-handback-draft.sh's hd_draft
# writes it -- state before labels.
hs_draft()  { printf '%s\t%s\t%s\tisDraft=true ci=GREEN quiet=%s\t%s\n' \
                 401 lane/selftesths "$1" "${3:-60}" "${2:-}" > "$HS/drafts.tsv"; }
# <sha> <branch> [<verdict line>]: a pair as arms.sh writes it, and its verdict
# as the judge writes it. No verdict means registered, not judged yet.
hs_pair()   { printf '{"sha": "%s", "source": "%s:docs/testing/predictions/%s.json", "issue": "", "queued_utc": "2026-09-25T16:00:00Z"}\n' \
                 "$1" "$2" "${1:0:6}" > "$HS_A/pairs/$1.json"
              [ -z "${3:-}" ] || printf '%s\n' "$3" > "$HS_A/judged/$1"; }
hs_req()    { printf '{"id": "%s", "requester": "%s", "purpose": "%s", "expect_sha": "%s"}\n' \
                 "$2" "$3" "$4" "$5" > "$HS_Q/$1/$2.req"; }

hs_sha() { printf '%064d' 0 | tr 0 "$1"; }
# THREE BRANCHES, OURS IN THE MIDDLE, by name and by sha. The last one shares
# our name as a PREFIX, so a reader that matched `startswith` would count its
# verdicts as ours; the first sorts ahead, so a first-wins reader is caught too.
BR_LO=lane/selftesthr; BR=lane/selftesths; BR_HI=lane/selftesths-x
S_LO=$(hs_sha 1); S1=$(hs_sha 5); S_HI=$(hs_sha 9)
S2=$(hs_sha 6); S3=$(hs_sha 7)
H1=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb1
H2=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb2
H3=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb3
H5=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb5

# ------------------------------------------------ (a) the verdict lands
hs_pair "$S_LO" "$BR_LO" "VERDICT: PASS -- 0 of 10 checks violated"
hs_pair "$S1"   "$BR"    "VERDICT: FAIL -- 4 of 403 checks violated:"
hs_pair "$S_HI" "$BR_HI" "VERDICT: PASS -- 0 of 10 checks violated"
hs_reset; hs_draft "$H1" regressed
out=$(hs list)
check "(a) list would resume the lane on the arm cause" grep -q "WOULD RESUME lane.selftesths (draft-strand-arm)" <<< "$out"
hs >/dev/null
check "(a) a judged verdict resumes the lane, once" hs_ran
check "(a)   and says so on the PR" hs_said "[job.handback] Resumed \`lane.selftesths\`"
check "(a)   keyed on the verdicts, not on the head" \
    bash -c "ls '$HAKUX_WORK/handback/done/' | grep -q '^draft-strand-arm-401-v[0-9a-f]\{16\}$'"
check "(a)   and no head-keyed marker was left for the arm cause" \
    [ ! -f "$HAKUX_WORK/handback/done/draft-strand-arm-401-$H1" ]

# THE RIGHT SET IS THE MIDDLE ONE. A verdict judged on either neighbour --
# including the one whose name ours is a prefix of -- is not ours.
hs_pair "$(hs_sha 2)" "$BR_LO" "VERDICT: FAIL -- 1 of 10 checks violated:"
hs_pair "$(hs_sha a)" "$BR_HI" "VERDICT: FAIL -- 1 of 10 checks violated:"
hs_reset; hs >/dev/null
check "(a) a verdict on a neighbouring branch does not resume this lane" hs_no_run
check "(a)   nor one on a branch whose name ours is a prefix of" hs_quiet

# ------------------------------------ (b) a new head, no new verdict
# THE DEFECT. The lane answered its FAIL by registering a replicate and
# pushing; the old key read that push as a new cause.
hs_reset; hs_draft "$H2" regressed
out=$(hs list); hs >/dev/null
check "(b) a new head with no new verdict does not resume the lane" hs_no_run
check "(b)   and nothing is said on the PR" hs_quiet
check "(b)   list says it was already actioned on these verdicts" \
    grep -q "draft-strand-arm already actioned on verdicts ${S1:0:12}=FAIL" <<< "$out"
check "(b)   the strand count did not move" [ "$(hs_count)" = 1 ]

# -------------------------------------- (c) the replicate is judged
hs_pair "$S2" "$BR" "VERDICT: PASS -- 0 of 403 checks violated"
hs_reset; hs_draft "$H2" regressed; hs >/dev/null
check "(c) a second judged verdict resumes the lane once more" hs_ran
check "(c)   counted towards the cap" [ "$(hs_count)" = 2 ]
hs_reset; hs_draft "$H3" verified; hs >/dev/null
check "(c)   and a push after it, with the label flipped, is still not a verdict" hs_no_run
# A line that says neither FAIL nor PASS is not a verdict (arms.sh's rule), so
# it is not new information either.
hs_pair "$S3" "$BR" "VERDICT: UNJUDGED -- no captures"
hs_reset; hs >/dev/null
check "(c)   an UNJUDGED line is not a new verdict" hs_no_run
rm -f "$HS_A/judged/$S3"

# -------------------------------- (d) the lane's own arm is in flight
# Three requests, ours in the middle: a neighbour's in each directory must not
# hold this lane, and ours must, from either directory.
S4=$(hs_sha 8)
hs_pair "$S4" "$BR"          # registered, not judged: the replicate's replicate
hs_req queue 100-arms-selftesthr-fix  arms-selftesthr-fix  "FIX arm, queued by the arms job from $BR_LO:x.json" "$S_LO"
hs_req queue 200-arms-selftesths-fix  arms-selftesths-fix  "FIX arm, queued by the arms job from $BR:y.json"    "$S4"
hs_req queue 300-arms-selftesths-x-fix arms-selftesths-x-fix "FIX arm, queued by the arms job from $BR_HI:z.json" "$S_HI"
# A verdict landing for the branch while its next arm waits: a real new set,
# so only the in-flight rule can be what holds it.
hs_pair "$S3" "$BR" "VERDICT: FAIL -- 2 of 403 checks violated:"
hs_reset; hs_draft "$H3" regressed
out=$(hs list); hs >/dev/null
check "(d) a lane whose own arm is queued is not resumed" hs_no_run
check "(d)   nor told anything on the PR" hs_quiet
check "(d)   list names the request it is waiting on" \
    grep -q "its arm is in flight (queue/200-arms-selftesths-fix)" <<< "$out"
hs_reset; hs >/dev/null
mv "$HS_Q/queue/200-arms-selftesths-fix.req" "$HS_Q/running/"
hs_reset; hs >/dev/null
check "(d)   nor once it is running" hs_no_run
check "(d)   and the tick log says so once per request, not once per tick" \
    [ "$(grep -c "#401: .*arm is in flight (.*/200-arms-selftesths-fix)" "$HS_TICK")" -eq 1 ]
check "(d)   the strand count did not move" [ "$(hs_count)" = 2 ]
# An ab_run.sh pair names the lane only as its requester.
rm -f "$HS_Q/running/200-arms-selftesths-fix.req"
hs_req running 400-selftesths-base selftesths-base "by hand" ""
hs_reset; out=$(hs list)
check "(d) a request by the lane's own ab_run.sh --who holds it too" \
    grep -q "its arm is in flight (running/400-selftesths-base)" <<< "$out"
# ...and with only the neighbours' requests left, the new verdict reaches it.
rm -f "$HS_Q/running/400-selftesths-base.req"
hs_reset; hs >/dev/null
check "(d) once its arm has left the queue, the waiting verdict resumes it" hs_ran
check "(d)   past the neighbours' requests, which never held it" \
    [ -f "$HS_Q/queue/100-arms-selftesthr-fix.req" ]
rm -f "$HS_Q/queue/100-arms-selftesthr-fix.req" "$HS_Q/queue/300-arms-selftesths-x-fix.req"

# ------------------------------------------ (e) the quiet clock, as today
rm -f "$HAKUX_WORK/handback/strand/selftesths"
hs_reset; hs_draft "$H5" "" 600; hs >/dev/null
check "(e) the quiet cause still waits out its clock" hs_no_run
hs_reset; hs_draft "$H5" "" 9000; hs >/dev/null
check "(e) and past it, resumes the lane" hs_ran
check "(e)   keyed on the head, as before" [ -f "$HAKUX_WORK/handback/done/draft-strand-quiet-401-$H5" ]
hs_reset; hs >/dev/null
check "(e)   and not twice at that head" hs_no_run

rm -f "$HS/drafts.tsv" "$HAKUX_WORK/handback/strand/selftesths"
rm -f "$HS_A/pairs/"{"$S_LO","$S1","$S_HI","$S2","$S3","$S4","$(hs_sha 2)","$(hs_sha a)"}.json
rm -f "$HS_A/judged/"{"$S_LO","$S1","$S_HI","$S2","$S3","$S4","$(hs_sha 2)","$(hs_sha a)"}
