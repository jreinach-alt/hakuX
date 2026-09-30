# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# handback.sh: a lane it skips as PARKED while its device requests are still
# queued or running gets a waiter, `hakux-waiter-<lane>`, once -- not a silent
# skip that nothing ever resumes.
#
# THE DEFECT, 2026-09-28/29. shaderfb569, litcompile569, memfast, ibcache,
# gpl569 (#594) and verdict433 (#610) were parked by a blocked:* label with
# runs in flight; the parked skip was a bare `continue`, and each needed a
# hand-started `systemd-run --user --unit=hakux-waiter-<lane>` after
# harness_health's `parked-nowaker` fired.
#
# systemd is shimmed, as 99-handback-parked.sh does: CI has no user manager,
# and a real transient unit would run the host's waiter against the fixture.
# The shim's systemd-run adds the unit to the active set, so `is-active` after
# an arm reads it armed exactly as the real one would.

echo "== handback.sh: a parked lane with runs in flight gets one waiter"
HW="$T/handback-waiter"; mkdir -p "$HW/bin"
cat > "$HW/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${HD_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        if [[ "$args" == *isDraft* ]]; then cat "$HD/drafts.tsv" 2>/dev/null
        elif [[ "$args" == *"--state all"* ]]; then cat "$HD/allprs.tsv" 2>/dev/null; fi
        exit 0 ;;
    "issue list")
        [[ "$args" == *decision-needed* ]] || cat "$HD/issues.tsv" 2>/dev/null
        exit 0 ;;
    "pr comment")
        b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$HD/comments.log"; b=""; }; [ "$a" = --body-file ] && b=1; done
        echo "--- end comment" >> "$HD/comments.log"; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HW/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
echo "systemctl $*" >> "${HD_LOG:?}"
case "$*" in
    *is-active*) u="${!#}"; grep -qxF -- "${u%.service}" "$HD/active" 2>/dev/null ;;
    *list-units*) cat "$HD/active" 2>/dev/null; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HW/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${HD_LOG:?}"
for a in "$@"; do case "$a" in --unit=*) echo "${a#--unit=}" >> "$HD/active" ;; esac; done
exit 0
EOF
chmod +x "$HW/bin/"*
echo '#!/bin/bash' > "$HW/waiter.sh"
LW=selftestwk; LX=selftestwx; PRW=470; BRW="lane/$LW"
HW_Q="$DISPATCH_DIR/queue"; mkdir -p "$HW_Q" "$DISPATCH_DIR/running" "$HAKUX_WORK/wt/$LW" "$HAKUX_WORK/wt/$LX"
cat > "$HW/territory.toml" <<EOF
[lane.$LW]
issues = [970]
[lane.$LX]
issues = [971]
EOF
W1=fffffffffffffffffffffffffffffffffffffff1

hw() { ( export HD="$HW" HD_LOG="$HW/gh.log" PATH="$HW/bin:$PATH" HAKUX_LANE_SH="$TESTING/lane.sh" \
                HAKUX_TERRITORY="$HW/territory.toml" HAKUX_PARK_WAITER="$HW/waiter.sh"
         bash "$@" 2>&1 ); }
# systemd-run calls that name our waiter unit, and comments that mention it.
hw_armed()    { grep -cE "^systemd-run .*--unit=hakux-waiter-$LW( |$)" "$HW/gh.log"; }
hw_lane_ran() { grep -cE "^systemd-run .*hakux-lane-$LW( |$)" "$HW/gh.log"; }
hw_said()     { grep -c "^\[job.handback\].*$1" "$HW/comments.log" 2>/dev/null; }
hw_reset() {
    : > "$HW/gh.log"; : > "$HW/comments.log"; : > "$HW/active"; : > "$HW/issues.tsv"
    rm -f "$HW_Q/"*"$LW"* "$HW_Q/"*-other-* "$HAKUX_WORK/attempts/$LW" \
          "$HAKUX_WORK/handback/done/"*"$LW"* "$HAKUX_WORK/handback/done/"*"-$PRW-"* "$HAKUX_WORK/handback/strand/$LW"
    rm -f "$HAKUX_WORK/logs/lane/$LW."*.json
    printf '%s\tOPEN\n' "$BRW" > "$HW/allprs.tsv"
    echo "# the original brief" > "$HAKUX_WORK/briefs/$LW.md"
}
# <labels>: our draft, CI green, quiet past DRAFT_STRAND_SECS.
hw_draft() { printf '%s\t%s\t%s\tisDraft=true ci=GREEN quiet=9000\t%s\n' "$PRW" "$BRW" "$W1" "$1" > "$HW/drafts.tsv"; }
# <id> [<json extra>]: a queued request of the lane's.
hw_queue() { printf '{"id": "%s", "requester": "lane.%s", "purpose": "a soak"%s}\n' "$1" "$LW" "${2:-}" > "$HW_Q/$1.req"; }

hw_scenario() {
    local s="$1" out
    # (a) THE DEFECT: parked by its PR label, a request queued, no lane unit,
    # no waiter. List names the decision; a run arms exactly one waiter and
    # says so on the PR; the lane itself is not resumed.
    hw_reset; hw_draft blocked:after-0.5; hw_queue 1790009100-lane.$LW-1
    out=$(hw "$s" list)
    grep -qF "#$PRW $BRW: parked with queue/1790009100-lane.$LW-1 in flight and no waiter; WOULD ARM hakux-waiter-$LW" <<< "$out" && echo "a_list=would"
    [ "$(hw_armed)" -eq 0 ] && echo "a_list_inert=yes"
    hw "$s" >/dev/null
    [ "$(hw_armed)" -eq 1 ] && echo "a=armed" || echo "a=unarmed"
    grep -qE "^systemd-run --user --unit=hakux-waiter-$LW bash $HW/waiter.sh $LW $LW 14$" "$HW/gh.log" && echo "a_argv=waiter"
    grep -qx "hakux-waiter-$LW" "$HW/active" && echo "a_active=yes"
    [ "$(hw_said "Armed \`hakux-waiter-$LW\`")" -eq 1 ] && echo "a_comment=one"
    [ "$(hw_lane_ran)" -eq 0 ] && echo "a_lane=quiet"
    # (b) the next tick, immediately: the waiter is active, so no second arm,
    # no second comment, and list says it is already armed.
    hw "$s" >/dev/null; out=$(hw "$s" list)
    [ "$(hw_armed)" -eq 1 ] && echo "b=once" || echo "b=rearmed"
    [ "$(grep -cx "hakux-waiter-$LW" "$HW/active")" -eq 1 ] && echo "b_units=one"
    [ "$(hw_said "Armed")" -eq 1 ] && echo "b_comment=one"
    grep -qF "waiter hakux-waiter-$LW already armed" <<< "$out" && echo "b_list=armed"
    # (c) parked by its lane's ISSUE rather than its PR label: armed the same.
    hw_reset; hw_draft ""; hw_queue 1790009101-lane.$LW-1
    printf '970\tblocked:tracking\n' > "$HW/issues.tsv"
    hw "$s" >/dev/null
    [ "$(hw_armed)" -eq 1 ] && echo "c=armed" || echo "c=unarmed"
    # (d) parked, nothing in flight: nothing to wait for, nothing armed or said.
    hw_reset; hw_draft blocked:after-0.5
    hw "$s" >/dev/null
    [ "$(hw_armed)" -eq 0 ] && echo "d=unarmed" || echo "d=armed"
    [ -s "$HW/comments.log" ] || echo "d_nocomment=yes"
    # (e) at LANE_MAX_ATTEMPTS: lane.sh resume would refuse, so no waiter; the
    # cap is named on the PR once, not every tick.
    hw_reset; hw_draft blocked:after-0.5; hw_queue 1790009102-lane.$LW-1
    echo 4 > "$HAKUX_WORK/attempts/$LW"
    out=$(hw "$s" list); hw "$s" >/dev/null; hw "$s" >/dev/null
    [ "$(hw_armed)" -eq 0 ] && echo "e=unarmed" || echo "e=armed"
    [ "$(hw_said "LANE_MAX_ATTEMPTS=4")" -eq 1 ] && echo "e_comment=once"
    grep -qF "NOT ARMING hakux-waiter-$LW (lane.sh resume would refuse)" <<< "$out" && echo "e_list=cap"
    # (e') one under the cap: armed.
    hw_reset; hw_draft blocked:after-0.5; hw_queue 1790009103-lane.$LW-1
    echo 3 > "$HAKUX_WORK/attempts/$LW"
    hw "$s" >/dev/null
    [ "$(hw_armed)" -eq 1 ] && echo "e2=armed" || echo "e2=unarmed"
    # (f) in flight by the request's `lane` field, under an id the waiter's
    # [-.]<lane>- pattern cannot see: the waiter would resume at once, so it
    # is not armed, and that is said once.
    hw_reset; hw_draft blocked:after-0.5
    printf '{"id": "1790009104-other-1", "requester": "other", "lane": "%s"}\n' "$LW" > "$HW_Q/1790009104-other-1.req"
    out=$(hw "$s" list); hw "$s" >/dev/null; hw "$s" >/dev/null
    [ "$(hw_armed)" -eq 0 ] && echo "f=unarmed" || echo "f=armed"
    [ "$(hw_said "does not match")" -eq 1 ] && echo "f_comment=once"
    grep -qF "no queued or running id matches [-.]$LW-; NOT ARMING" <<< "$out" && echo "f_list=unseen"
    # (g) the lane's own session is still running: it has not ended waiting
    # yet, so no waiter this tick.
    hw_reset; hw_draft blocked:after-0.5; hw_queue 1790009105-lane.$LW-1
    echo "hakux-lane-$LW" > "$HW/active"
    hw "$s" >/dev/null
    [ "$(hw_armed)" -eq 0 ] && echo "g=unarmed" || echo "g=armed"
    # (h) NOT parked, run in flight: the existing wait path, no waiter.
    hw_reset; hw_draft ""; hw_queue 1790009106-lane.$LW-1
    hw "$s" >/dev/null
    [ "$(hw_armed)" -eq 0 ] && echo "h=unarmed" || echo "h=armed"
    [ "$(hw_lane_ran)" -eq 0 ] && echo "h_lane=quiet"
    # (i) a queued request of a NEIGHBOUR lane does not arm ours.
    hw_reset; hw_draft blocked:after-0.5
    printf '{"id": "1790009107-lane.%s-1", "requester": "lane.%s"}\n' "$LX" "$LX" > "$HW_Q/1790009107-lane.$LX-1.req"
    hw "$s" >/dev/null
    [ "$(hw_armed)" -eq 0 ] && echo "i=unarmed" || echo "i=armed"
    rm -f "$HW_Q/"*"$LX"*
}

got=$(hw_scenario "$HERE/handback.sh")
hw_has() { grep -qx "$1" <<< "$got"; }
check "(a) a parked draft with a queued request gets hakux-waiter-<lane>" hw_has a=armed
check "(a)   running the host's waiter on the lane, for 14 h" hw_has a_argv=waiter
check "(a)   and the unit is then active" hw_has a_active=yes
check "(a)   list names the decision" hw_has a_list=would
check "(a)   and list arms nothing" hw_has a_list_inert=yes
check "(a)   one PR comment says so" hw_has a_comment=one
check "(a)   and the lane itself is not resumed" hw_has a_lane=quiet
check "(b) the next tick does not arm a second waiter" hw_has b=once
check "(b)   one hakux-waiter-<lane> unit exists" hw_has b_units=one
check "(b)   and says nothing more on the PR" hw_has b_comment=one
check "(b)   list reports it already armed" hw_has b_list=armed
check "(c) a lane parked by its issue's label is armed the same" hw_has c=armed
check "(d) a parked lane with nothing in flight gets no waiter" hw_has d=unarmed
check "(d)   and no comment" hw_has d_nocomment=yes
check "(e) a lane at LANE_MAX_ATTEMPTS gets no waiter" hw_has e=unarmed
check "(e)   the cap is named on the PR once" hw_has e_comment=once
check "(e)   list says why" hw_has e_list=cap
check "(e') one attempt under the cap is armed" hw_has e2=armed
check "(f) a request the waiter's pattern cannot see arms nothing" hw_has f=unarmed
check "(f)   and is said once" hw_has f_comment=once
check "(f)   list says why" hw_has f_list=unseen
check "(g) a lane whose session is still running gets no waiter yet" hw_has g=unarmed
check "(h) an unparked lane waiting on a run gets no waiter" hw_has h=unarmed
check "(h)   and is not resumed" hw_has h_lane=quiet
check "(i) a neighbour lane's request does not arm this lane's waiter" hw_has i=unarmed

# ---------------------------------------------------------------- mutants
# Each from a copy beside its sourced helpers and models.env; the real file is
# never touched.
hw_mutant() {   # <name> <old> <new> -> path, or "" if the anchor moved
    local md="$T/handback-waiter-mut-$1"; rm -rf "$md"; mkdir -p "$md"
    cp "$HERE/gh-label.sh" "$HERE/localtime.sh" "$HERE/remote-lane.sh" "$HERE/models.env" "$md/"
    python3 - "$HERE/handback.sh" "$md/handback.sh" "$2" "$3" <<'PY' && echo "$md/handback.sh"
import sys
src, dst, old, new = sys.argv[1:]
s = open(src).read()
if s.count(old) != 1:
    sys.exit(1)
open(dst, "w").write(s.replace(old, new))
PY
}
hw_mut() {   # <name> <old> <new> <leg that must go wrong> <what it shows>
    local m mg; m=$(hw_mutant "$1" "$2" "$3")
    if [ -z "$m" ]; then bad "mutant anchor '$1' no longer matches handback.sh"; return; fi
    mg=$(hw_scenario "$m")
    if grep -qx "$4" <<< "$mg"; then ok "mutant '$1' $5 (red, as it must be)"
    else bad "mutant '$1' passes: the fragment cannot see it"; fi
}
# The arm step reverted: the parked skip is a bare `continue` again.
hw_mut noarm '            park_waiter "$pr" "$branch" "$park"
' '' a=unarmed "without the arm step leaves #594's shape stranded"
hw_mut noidem 'if systemctl --user is-active --quiet "$unit.service" 2>/dev/null; then' 'if false; then' \
       b=rearmed "without the is-active check arms a second waiter every tick"
hw_mut nocap '[ "$n" -ge "$PARK_MAX_ATTEMPTS" ]' 'false' \
       e=armed "without the cap arms a waiter lane.sh will refuse"
hw_mut nopattern '| grep -q -- "[-.]$name-"; then' '| true; then' \
       f=armed "without the pattern check arms a waiter that resumes at once"
rm -rf "$T"/handback-waiter-mut-*

hw_reset; rm -f "$HW/drafts.tsv"
