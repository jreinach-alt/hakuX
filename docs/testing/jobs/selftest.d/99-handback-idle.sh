# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# handback.sh's idle cause (defect 25 of the dispatch-hardening brief): a lane
# whose unit is inactive, whose PR is a draft or absent, and which has nothing
# queued or running is resumed once per SESSION END -- not once per head.
#
# THE DEFECT, 2026-09-25: titlerun (#307), sweepcover (#298) and blankrule297
# (#335) each ended a session "until my background task notifies me". That
# task died with the headless session. Each was quiet-resumed once, ended the
# same way without pushing, and the quiet cause's marker is keyed on the head:
# blankrule297 was resumed at 20:12 PDT, ended at 20:56, and nothing could act
# on #335 at that head again. 3 to 8 hours idle, flagged by #107's lane table.
#
# Its own shims, in a directory of its own: the gh here answers two questions
# the other handback fragments' gh does not (the all-states PR list and a PR's
# comments), and sharing one would make a change here move their answers.

echo "== handback.sh: a lane idle with no work is resumed once per session end"
HI="$T/handback-idle"; mkdir -p "$HI/bin"
cat > "$HI/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${HD_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        if [[ "$args" == *isDraft* ]]; then cat "$HD/drafts.tsv" 2>/dev/null
        elif [[ "$args" == *"--state all"* ]]; then cat "$HD/allprs.tsv" 2>/dev/null; fi
        exit 0 ;;
    "pr view")
        [[ "$args" == *comments* ]] && cat "$HD/lastword.txt" 2>/dev/null
        exit 0 ;;
    "issue list") cat "$HD/dn.txt" 2>/dev/null; exit 0 ;;
    "pr comment")
        b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$HD/comments.log"; b=""; }; [ "$a" = --body-file ] && b=1; done
        echo "--- end comment" >> "$HD/comments.log"; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HI/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) u="${!#}"; grep -qxF -- "$u" "$HD/active" 2>/dev/null ;;
    *list-units*) cat "$HD/active" 2>/dev/null; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HI/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${HD_LOG:?}"; exit 0
EOF
chmod +x "$HI/bin/"*
HI_L="$HAKUX_WORK/logs/lane"; HI_Q="$DISPATCH_DIR"
mkdir -p "$HI_L" "$HI_Q/queue" "$HI_Q/results" "$HAKUX_WORK/briefs"
# THREE LANES ON THE BOARD, THE NO-PR ONE IN THE MIDDLE: `selftestia` has a
# merged PR (done, not idle), `selftestib` has none (idle), `selftestic` is
# standing (its resting state). Only the middle one may be picked up.
LA=selftestia; ME=selftestib; LC=selftestic; DR=selftestid
for l in "$LA" "$ME" "$LC" "$DR"; do mkdir -p "$HAKUX_WORK/wt/$l"; done
cat > "$HI/territory.toml" <<EOF
[lane.$LA]
issues = [901]
[lane.$ME]
issues = [902]
[lane.$LC]
issues = [903]
standing = true
[lane.$DR]
issues = [904]
EOF
PR=404; BR="lane/$DR"; H1=dddddddddddddddddddddddddddddddddddddddd1; H2=dddddddddddddddddddddddddddddddddddddddd2

hi() { ( export HD="$HI" HD_LOG="$HI/gh.log" PATH="$HI/bin:$PATH" HAKUX_LANE_SH="$TESTING/lane.sh" HAKUX_TERRITORY="$HI/territory.toml"
         bash "$@" 2>&1 ); }
hi_reset() { : > "$HI/gh.log"; : > "$HI/comments.log"; }
hi_ran()   { grep -cE "systemd-run.*hakux-lane-$1( |$)" "$HI/gh.log"; }
# <lane> <stamp> <age> [<result text>]: a finished session, as lane.sh leaves it.
hi_sess()  { rm -f "$HI_L/$1."*.json
             printf '{"type": "result", "result": "%s"}\n' "${4:-I will pick this up when the background job notifies me.}" > "$HI_L/$1.$2.json"
             touch -d "$3" "$HI_L/$1.$2.json"; }
# <head> <ci>: our draft, quiet for only 60 s, so the two-hour clock cannot be what fires.
hi_draft() { printf '%s\t%s\t%s\tisDraft=true ci=%s quiet=60\t\n' "$PR" "$BR" "$1" "${2:-GREEN}" > "$HI/drafts.tsv"; }
hi_state_reset() {
    rm -f "$HAKUX_WORK/handback/done/"*"-$PR-"* "$HAKUX_WORK/handback/done/idle-no-pr-"* \
          "$HAKUX_WORK/handback/idle/selftesti"* "$HAKUX_WORK/handback/strand/selftesti"* "$HAKUX_WORK/attempts/selftesti"*
    rm -f "$HI_L/selftesti"*.json "$HI_Q/queue/"*-selftesti*
    for l in "$LA" "$ME" "$LC" "$DR"; do echo "# the original brief" > "$HAKUX_WORK/briefs/$l.md"; done
    : > "$HI/active"; : > "$HI/lastword.txt"; : > "$HI/dn.txt"; rm -f "$HI/drafts.tsv"
    printf 'lane/%s\tMERGED\n' "$LA" > "$HI/allprs.tsv"
    printf 'lane/%s\tOPEN\n' "$DR" >> "$HI/allprs.tsv"
    hi_reset
}

# The scenario as a function of the script, so a mutant and the old file run
# the same legs. Each leg echoes a word; the caller asserts on the words.
hi_scenario() {
    local s="$1" out
    hi_state_reset
    # ---- the draft half
    hi_draft "$H1"
    # (0) the session ended ten minutes ago: inside the grace, not idle yet.
    hi_sess "$DR" 20260925T230000Z '-10 minutes'
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 0 ] && echo "D0=quiet" || echo "D0=resumed"
    # (a) an hour ago, CI green, nothing on a device: resumed, on the idle cause.
    hi_sess "$DR" 20260925T230000Z '-1 hour'
    hi_reset; out=$(hi "$s" list); hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 1 ] && echo "Da=resumed" || echo "Da=quiet"
    grep -q "WOULD RESUME lane.$DR (draft-strand-idle)" <<< "$out" && echo "Da_cause=idle"
    grep -q "notification can never come" "$HAKUX_WORK/briefs/$DR.md" && echo "Da_brief=yes"
    grep -q "idle with no work" "$HI/comments.log" && echo "Da_comment=yes"
    [ ! -s "$HAKUX_WORK/handback/strand/$DR" ] && echo "Da_uncapped=yes"
    { [ ! -s "$HAKUX_WORK/attempts/$DR" ] || [ "$(cat "$HAKUX_WORK/attempts/$DR")" = 0 ]; } && echo "Da_uncounted=yes"
    # (b) the next tick, the same session: not again.
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 0 ] && echo "Db=quiet" || echo "Db=resumed"
    # (c) blankrule297's shape: that session ended, idle again, SAME head.
    hi_sess "$DR" 20260926T000000Z '-1 hour'
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 1 ] && echo "Dc=resumed" || echo "Dc=quiet"
    # (d) it said it is waiting on something outside itself: honoured.
    hi_sess "$DR" 20260926T010000Z '-1 hour' "Posted [lane.$DR] waiting: request 1790000000-$DR-1 on the Nova."
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 0 ] && echo "Dd=quiet" || echo "Dd=resumed"
    # (e) ...or said so on the PR, as its newest word since the last resume.
    hi_sess "$DR" 20260926T020000Z '-1 hour'
    printf '%s\n' "[lane.$DR] waiting: the board's grant for dispatcher.sh" > "$HI/lastword.txt"
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 0 ] && echo "De=quiet" || echo "De=resumed"
    : > "$HI/lastword.txt"
    # (f) something of its own is queued on a device: waiting, rightly.
    printf '{"id": "1790000500-%s-1", "requester": "%s", "purpose": "a soak"}\n' "$DR" "$DR" > "$HI_Q/queue/1790000500-$DR-1.req"
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 0 ] && echo "Df=quiet" || echo "Df=resumed"
    rm -f "$HI_Q/queue/1790000500-$DR-1.req"
    # (g) CI still running on its head: that is what it waits for.
    hi_draft "$H1" PENDING
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 0 ] && echo "Dg=quiet" || echo "Dg=resumed"
    # (h) CI settled: resumed (the third time at H1).
    hi_draft "$H1" RED
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 1 ] && echo "Dh=resumed" || echo "Dh=quiet"
    # (i) IDLE_MAX=3 at one head: a fourth idle session at H1 is not resumed...
    hi_sess "$DR" 20260926T030000Z '-1 hour'
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 0 ] && echo "Di=quiet" || echo "Di=resumed"
    # (j) ...but a new head is progress, and resets it.
    hi_draft "$H2" GREEN
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$DR")" -eq 1 ] && echo "Dj=resumed" || echo "Dj=quiet"
    # ---- the no-PR half: every lane's session ended an hour ago, idle.
    rm -f "$HI/drafts.tsv"
    for l in "$LA" "$ME" "$LC"; do hi_sess "$l" 20260926T040000Z '-1 hour'; done
    hi_reset; out=$(hi "$s" list); hi "$s" >/dev/null
    [ "$(hi_ran "$ME")" -eq 1 ] && echo "Na=resumed" || echo "Na=quiet"
    grep -q "WOULD RESUME lane.$ME (idle-no-pr)" <<< "$out" && echo "Na_cause=idle-no-pr"
    grep -q "has no open PR and was not running" "$HAKUX_WORK/briefs/$ME.md" && echo "Na_brief=yes"
    [ "$(hi_ran "$LA")" -eq 0 ] && echo "Na_merged=left"
    [ "$(hi_ran "$LC")" -eq 0 ] && echo "Na_standing=left"
    [ "$(hi_ran "$DR")" -eq 0 ] && echo "Na_draft=left"
    grep -q "pr comment" "$HI/gh.log" || echo "Na_nocomment=yes"
    # (b) no-PR, same session, next tick: not again.
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$ME")" -eq 0 ] && echo "Nb=quiet" || echo "Nb=resumed"
    # (c) its issue carries decision-needed: the owner's, not idle.
    hi_sess "$ME" 20260926T050000Z '-1 hour'; echo 902 > "$HI/dn.txt"
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$ME")" -eq 0 ] && echo "Nc=quiet" || echo "Nc=resumed"
    : > "$HI/dn.txt"
    # (d) its unit is running: not a cause, and not a log line either.
    echo "hakux-lane-$ME" > "$HI/active"
    hi_reset; hi "$s" >/dev/null
    [ "$(hi_ran "$ME")" -eq 0 ] && echo "Nd=quiet" || echo "Nd=resumed"
    : > "$HI/active"
}

got=$(hi_scenario "$HERE/handback.sh")
hi_has() { grep -qx "$1" <<< "$got"; }
check "(0) a session that ended inside IDLE_GRACE_SECS is not idle yet" hi_has D0=quiet
check "(a) draft, settled CI, nothing on a device, session ended 1 h ago: resumed" hi_has Da=resumed
check "(a)   on the idle cause, not the two-hour quiet clock" hi_has Da_cause=idle
check "(a)   the brief says the background task died with the session" hi_has Da_brief=yes
check "(a)   the PR comment says it was idle with no work" hi_has Da_comment=yes
check "(a)   it does not spend DRAFT_STRAND_MAX" hi_has Da_uncapped=yes
check "(a)   nor an attempt" hi_has Da_uncounted=yes
check "(b) the same session, a tick later: not again" hi_has Db=quiet
check "(c) a new session end at the SAME head is a new cause (blankrule297)" hi_has Dc=resumed
check "(d) its last session said [lane.x] waiting: -- honoured" hi_has Dd=quiet
check "(e) its newest word on the PR is waiting: -- honoured" hi_has De=quiet
check "(f) a request of its own is queued: not idle" hi_has Df=quiet
check "(g) CI PENDING on its head: not idle" hi_has Dg=quiet
check "(h) CI settled RED: resumed" hi_has Dh=resumed
check "(i) a fourth idle session at one head: IDLE_MAX stops it" hi_has Di=quiet
check "(j) a new head resets that bound" hi_has Dj=resumed
check "(N a) a board lane with no PR, idle: resumed" hi_has Na=resumed
check "(N a)   on idle-no-pr" hi_has Na_cause=idle-no-pr
check "(N a)   with the no-PR brief" hi_has Na_brief=yes
check "(N a)   the lane whose PR merged is left alone" hi_has Na_merged=left
check "(N a)   the standing lane is left alone" hi_has Na_standing=left
check "(N a)   the draft lane is not picked up a second time as no-PR" hi_has Na_draft=left
check "(N a)   and nothing is commented, there being no PR" hi_has Na_nocomment=yes
check "(N b) the same session, a tick later: not again" hi_has Nb=quiet
check "(N c) an issue with decision-needed is the owner's, not idle" hi_has Nc=quiet
check "(N d) a running unit is not idle" hi_has Nd=quiet

# ---------------------------------------------------------------- mutants
# Each from a copy beside its sourced helpers; the real file is never touched.
hi_mutant() {   # <name> <old> <new> -> path, or "" if the anchor moved
    local md="$T/handback-idle-mut-$1"; rm -rf "$md"; mkdir -p "$md"
    cp "$HERE/gh-label.sh" "$HERE/localtime.sh" "$HERE/remote-lane.sh" "$md/"
    python3 - "$HERE/handback.sh" "$md/handback.sh" "$2" "$3" <<'PY' && echo "$md/handback.sh"
import sys
src, dst, old, new = sys.argv[1:]
s = open(src).read()
if s.count(old) != 1:
    sys.exit(1)
open(dst, "w").write(s.replace(old, new))
PY
}
hi_mut() {   # <name> <old> <new> <leg that must go wrong> <what it shows>
    local m mg; m=$(hi_mutant "$1" "$2" "$3")
    if [ -z "$m" ]; then bad "mutant anchor '$1' no longer matches handback.sh"; return; fi
    mg=$(hi_scenario "$m")
    # A leading `!` means the word must be MISSING from the mutant's run.
    if { [ "${4#!}" = "$4" ] && grep -qx "$4" <<< "$mg"; } || { [ "${4#!}" != "$4" ] && ! grep -qx "${4#!}" <<< "$mg"; }; then
        ok "mutant '$1' $5 (red, as it must be)"
    else bad "mutant '$1' passes: the fragment cannot see it"; fi
}
hi_mut headkey '$H/done/$label-$pr-s$SESS_STAMP"; keyed="on session $SESS_STAMP"' \
               '$H/done/$label-$pr-$head"; keyed="at ${head:0:10}"' \
       Dc=quiet "keyed on the head strands blankrule297's second session"
hi_mut nograce '[ "$SESS_AGE" -ge "$IDLE_GRACE_SECS" ] ||' ': ||' \
       D0=resumed "without the grace resumes a lane ten minutes after it pushed"
hi_mut nowait '[ "$SESS_WAIT" != 1 ] ||' ': ||' \
       Dd=resumed "ignoring the session's waiting: resumes a lane that said it was waiting"
hi_mut nomax '[ "$n" -lt "$IDLE_MAX" ] ||' ': ||' \
       Di=resumed "without IDLE_MAX resumes an idle lane at one head forever"
hi_mut merged 'if states.get("lane/" + name, set()) & {"OPEN", "MERGED"}:' 'if states.get("lane/" + name, set()) & {"OPEN"}:' \
       '!Na_merged=left' "that treats a merged PR as absent resumes a finished lane"
rm -rf "$T"/handback-idle-mut-*

hi_state_reset; rm -f "$HI_L/selftesti"*.json
