# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# handback.sh: a PR or lane PARKED with a `blocked:*` label is not resumed by
# any cause -- not the strand clock, not an arm verdict, not needs-rebase, not
# the no-PR idle cause.
#
# THE DEFECT, 2026-09-26. #433's 0.5 policy parked drafts #436 (lane.visual404)
# and #439 (lane.fmv303c) with `blocked:after-0.5`. STRAND_STALE listed only
# `blocked:needs-owner`, so both read as unowned drafts and were strand-resumed
# at 21:50Z and 23:53Z (#436) and 21:52Z and 23:55Z (#439); each session only
# re-posted that it was parked, and each spent one of DRAFT_STRAND_MAX.
#
# Its own shims, in a directory of its own, as 99-handback-idle.sh does: this
# gh answers the blocked-issue query, which the other fragments' gh does not.

echo "== handback.sh: a PR or lane parked with blocked:* is not resumed"
HP="$T/handback-parked"; mkdir -p "$HP/bin"
cat > "$HP/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${HD_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        if [[ "$args" == *isDraft* ]]; then cat "$HD/drafts.tsv" 2>/dev/null
        elif [[ "$args" == *"--state all"* ]]; then cat "$HD/allprs.tsv" 2>/dev/null
        elif [[ "$args" =~ --label\ ([A-Za-z0-9:_.-]+) ]]; then cat "$HD/prs.${BASH_REMATCH[1]}.tsv" 2>/dev/null; fi
        exit 0 ;;
    "issue list")
        # decision-needed is the idle cause's own question; everything else
        # is the blocked:* query, answered "number<TAB>label".
        [[ "$args" == *decision-needed* ]] || cat "$HD/issues.tsv" 2>/dev/null
        exit 0 ;;
    "pr comment")
        b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$HD/comments.log"; b=""; }; [ "$a" = --body-file ] && b=1; done
        echo "--- end comment" >> "$HD/comments.log"; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HP/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) u="${!#}"; grep -qxF -- "$u" "$HD/active" 2>/dev/null ;;
    *list-units*) cat "$HD/active" 2>/dev/null; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HP/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${HD_LOG:?}"; exit 0
EOF
chmod +x "$HP/bin/"*
HP_L="$HAKUX_WORK/logs/lane"; mkdir -p "$HP_L" "$HAKUX_WORK/briefs"
# THREE LANES, OURS IN THE MIDDLE BY ISSUE: selftestpj's issue 960 is parked
# and it has no brief (so it is never a no-PR row itself); a reader that maps
# issue to lane by position or first match would park selftestpk for it.
LJ=selftestpj; LK=selftestpk; LL=selftestpl
for l in "$LJ" "$LK" "$LL"; do mkdir -p "$HAKUX_WORK/wt/$l"; done
cat > "$HP/territory.toml" <<EOF
[lane.$LJ]
issues = [960]
[lane.$LK]
issues = [961]
[lane.$LL]
issues = [962]
EOF
PR=460; BR="lane/$LK"
P1=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee1; P2=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee2
P3=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee3; P4=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee4
P5=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee5; P6=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee6

hp() { ( export HD="$HP" HD_LOG="$HP/gh.log" PATH="$HP/bin:$PATH" HAKUX_LANE_SH="$TESTING/lane.sh" HAKUX_TERRITORY="$HP/territory.toml"
         bash "$@" 2>&1 ); }
hp_reset() { : > "$HP/gh.log"; : > "$HP/comments.log"; }
hp_ran()   { grep -cE "systemd-run.*hakux-lane-$1( |$)" "$HP/gh.log"; }
# <head> <labels> [<quiet>]: our draft, green, quiet past DRAFT_STRAND_SECS by default.
hp_draft() { printf '%s\t%s\t%s\tisDraft=true ci=GREEN quiet=%s\t%s\n' "$PR" "$BR" "$1" "${3:-9000}" "${2:-}" > "$HP/drafts.tsv"; }
hp_state_reset() {
    rm -f "$HAKUX_WORK/handback/done/"*"-$PR-"* "$HAKUX_WORK/handback/done/"*"-461-"* "$HAKUX_WORK/handback/done/idle-no-pr-selftestp"* \
          "$HAKUX_WORK/handback/idle/selftestp"* "$HAKUX_WORK/handback/strand/selftestp"* "$HAKUX_WORK/attempts/selftestp"*
    rm -f "$HP_L/selftestp"*.json "$HP/prs."*.tsv "$HP/drafts.tsv"
    rm -f "$HAKUX_WORK/briefs/$LJ.md"
    for l in "$LK" "$LL"; do echo "# the original brief" > "$HAKUX_WORK/briefs/$l.md"; done
    : > "$HP/active"; : > "$HP/issues.tsv"
    printf 'lane/%s\tOPEN\n' "$LK" > "$HP/allprs.tsv"
    printf 'lane/%s\tOPEN\n' selftestpm >> "$HP/allprs.tsv"
    hp_reset
}

# The scenario as a function of the script, so a mutant and the real file run
# the same legs. Each leg echoes a word; the caller asserts on the words.
hp_scenario() {
    local s="$1" out
    hp_state_reset
    # (a) THE DEFECT: a draft labelled blocked:after-0.5, unit not running,
    # quiet past the clock. Parked, so skipped -- and list names the label.
    hp_draft "$P1" blocked:after-0.5
    out=$(hp "$s" list); hp "$s" >/dev/null
    [ "$(hp_ran "$LK")" -eq 0 ] && echo "a=quiet" || echo "a=resumed"
    grep -qF "#$PR $BR: draft-strand-quiet, skipped: parked by blocked:after-0.5" <<< "$out" && echo "a_list=label"
    [ -s "$HP/comments.log" ] || echo "a_nocomment=yes"
    [ -s "$HAKUX_WORK/handback/strand/$LK" ] || echo "a_uncounted=yes"
    # (b) the same fixture without the label: resumed. Same head, so the
    # parked tick above must have left no marker behind.
    hp_draft "$P1" ""
    hp_reset; hp "$s" >/dev/null
    [ "$(hp_ran "$LK")" -eq 1 ] && echo "b=resumed" || echo "b=quiet"
    # (c) a NEIGHBOUR lane's issue is parked: not ours, so a new head resumes.
    printf '960\tblocked:after-0.5\n' > "$HP/issues.tsv"
    hp_draft "$P2" ""
    hp_reset; hp "$s" >/dev/null
    [ "$(hp_ran "$LK")" -eq 1 ] && echo "c=resumed" || echo "c=quiet"
    # (d) OUR lane's issue is parked, the PR unlabelled: skipped, naming the issue.
    printf '960\tblocked:after-0.5\n961\tblocked:after-0.5\n962\t\n' > "$HP/issues.tsv"
    rm -f "$HAKUX_WORK/handback/strand/$LK"
    hp_draft "$P3" ""
    hp_reset; out=$(hp "$s" list); hp "$s" >/dev/null
    [ "$(hp_ran "$LK")" -eq 0 ] && echo "d=quiet" || echo "d=resumed"
    grep -qF "skipped: parked by issue #961 blocked:after-0.5" <<< "$out" && echo "d_list=issue"
    : > "$HP/issues.tsv"
    # (e) the explicit list still works: blocked:needs-owner is "moved on".
    hp_draft "$P4" blocked:needs-owner
    hp_reset; out=$(hp "$s" list); hp "$s" >/dev/null
    [ "$(hp_ran "$LK")" -eq 0 ] && echo "e=quiet" || echo "e=resumed"
    grep -qF "but also blocked:needs-owner" <<< "$out" && echo "e_list=stale"
    # (f) a judged arm on a parked PR: a verdict is news, but not to a parked lane.
    hp_draft "$P5" verified,blocked:after-0.5 60
    hp_reset; out=$(hp "$s" list); hp "$s" >/dev/null
    [ "$(hp_ran "$LK")" -eq 0 ] && echo "f=quiet" || echo "f=resumed"
    grep -qF "draft-strand-arm, skipped: parked by blocked:after-0.5" <<< "$out" && echo "f_list=label"
    rm -f "$HP/drafts.tsv"
    # (g) the label cause: needs-rebase on a parked PR is skipped before any fetch.
    printf '461\tlane/selftestpm\t%s\tneeds-rebase,blocked:after-0.5\n' "$P6" > "$HP/prs.needs-rebase.tsv"
    hp_reset; out=$(hp "$s" list)
    grep -qF "#461 lane/selftestpm: needs-rebase, skipped: parked by blocked:after-0.5" <<< "$out" && echo "g_list=label"
    rm -f "$HP/prs.needs-rebase.tsv"
    # (h) the no-PR idle cause: selftestpl has no PR and its session ended an
    # hour ago -- idle -- but its issue is parked.
    printf '%s\n' '{"type": "result", "result": "done for now"}' > "$HP_L/$LL.20260926T200000Z.json"
    touch -d '-1 hour' "$HP_L/$LL.20260926T200000Z.json"
    printf '962\tblocked:after-0.5\n' > "$HP/issues.tsv"
    hp_reset; out=$(hp "$s" list); hp "$s" >/dev/null
    [ "$(hp_ran "$LL")" -eq 0 ] && echo "h=quiet" || echo "h=resumed"
    grep -qF "lane/$LL: idle-no-pr, skipped: parked by issue #962 blocked:after-0.5" <<< "$out" && echo "h_list=issue"
    # (i) the same lane with the label lifted: resumed.
    : > "$HP/issues.tsv"
    hp_reset; hp "$s" >/dev/null
    [ "$(hp_ran "$LL")" -eq 1 ] && echo "i=resumed" || echo "i=quiet"
    [ "$(hp_ran "$LJ")" -eq 0 ] && echo "i_neighbour=left"
    # (j)-(m) THE IN-FLIGHT EXCEPTION, 2026-09-28. `blocked:in-flight` on an
    # issue means "lanes are already on this", so it must not park them. Each
    # leg from clean markers (hp_runs_world), so a quiet leg cannot be the
    # runs cause's once-per-set marker left by an earlier one. The draft is
    # quiet only 60 s: a resume can only be the runs cause, and the leg asks
    # for its marker by name.
    # (j) our issue carries only blocked:in-flight: resumed on the finished run.
    hp_runs_world "$P1" "" '961\tblocked:in-flight\n'
    out=$(hp "$s" list); hp "$s" >/dev/null
    [ "$(hp_ran "$LK")" -eq 1 ] && echo "j=resumed" || echo "j=quiet"
    compgen -G "$HAKUX_WORK/handback/done/draft-strand-runs-$PR-r*" >/dev/null && echo "j_cause=runs"
    grep -qF "#$PR $BR: draft-strand-quiet, skipped: parked" <<< "$out" || echo "j_list=unparked"
    # (k) the same lane with blocked:after-0.5 on its issue: parked.
    hp_runs_world "$P2" "" '961\tblocked:after-0.5\n'
    out=$(hp "$s" list); hp "$s" >/dev/null
    [ "$(hp_ran "$LK")" -eq 0 ] && echo "k=quiet" || echo "k=resumed"
    grep -qF "skipped: parked by issue #961 blocked:after-0.5" <<< "$out" && echo "k_list=issue"
    # (l) both on the issue, in-flight FIRST: the other label still parks.
    hp_runs_world "$P3" "" '961\tblocked:in-flight,blocked:after-0.5\n'
    out=$(hp "$s" list); hp "$s" >/dev/null
    [ "$(hp_ran "$LK")" -eq 0 ] && echo "l=quiet" || echo "l=resumed"
    grep -qF "skipped: parked by issue #961 blocked:after-0.5" <<< "$out" && echo "l_list=issue"
    # (m) the PR ITSELF labelled blocked:in-flight (#504's interim), issue
    # clean: the PR half takes no exception, so it stays parked.
    hp_runs_world "$P4" blocked:in-flight ''
    out=$(hp "$s" list); hp "$s" >/dev/null
    [ "$(hp_ran "$LK")" -eq 0 ] && echo "m=quiet" || echo "m=resumed"
    grep -qF "#$PR $BR: draft-strand-quiet, skipped: parked by blocked:in-flight" <<< "$out" && echo "m_list=label"
}
# <head> <PR labels> <issues.tsv printf format>: a clean world in which our
# lane's last session ended an hour ago and one of its runs finished since.
hp_runs_world() {
    hp_state_reset
    rm -rf "$DISPATCH_DIR/results/"*-selftestpk-*
    printf '%s\n' '{"type": "result", "result": "waiting on my soak"}' > "$HP_L/$LK.20260928T200000Z.json"
    touch -d '-1 hour' "$HP_L/$LK.20260928T200000Z.json"
    local id=1790009000-$LK-900
    mkdir -p "$DISPATCH_DIR/results/$id"
    printf '{"id": "%s", "requester": "%s", "purpose": "a soak"}\n' "$id" "$LK" > "$DISPATCH_DIR/results/$id/request.json"
    : > "$DISPATCH_DIR/results/$id/DONE"; touch -d '-5 minutes' "$DISPATCH_DIR/results/$id/DONE"
    printf "$3" > "$HP/issues.tsv"
    hp_draft "$1" "$2" 60
}

got=$(hp_scenario "$HERE/handback.sh")
hp_has() { grep -qx "$1" <<< "$got"; }
check "(a) a draft labelled blocked:after-0.5, quiet past the clock, is not resumed" hp_has a=quiet
check "(a)   list says it was skipped for that label" hp_has a_list=label
check "(a)   nothing is said on the PR" hp_has a_nocomment=yes
check "(a)   and DRAFT_STRAND_MAX is not spent" hp_has a_uncounted=yes
check "(b) the same draft without the label is resumed" hp_has b=resumed
check "(c) a neighbour lane's parked issue does not park this lane" hp_has c=resumed
check "(d) a draft whose lane's issue is labelled blocked:* is not resumed" hp_has d=quiet
check "(d)   list names the issue and its label" hp_has d_list=issue
check "(e) blocked:needs-owner is still skipped by the explicit list" hp_has e=quiet
check "(e)   as 'already moved on', as before" hp_has e_list=stale
check "(f) a judged arm on a parked draft does not resume it" hp_has f=quiet
check "(f)   list says so" hp_has f_list=label
check "(g) needs-rebase on a parked PR is skipped" hp_has g_list=label
check "(h) a no-PR lane whose issue is parked is not idle-resumed" hp_has h=quiet
check "(h)   list names the issue" hp_has h_list=issue
check "(i) the same lane with the label lifted is resumed" hp_has i=resumed
check "(i)   and the neighbour with no brief is left alone" hp_has i_neighbour=left
check "(j) a lane whose issue carries blocked:in-flight is resumed when its runs finish" hp_has j=resumed
check "(j)   by the runs cause" hp_has j_cause=runs
check "(j)   and list does not report it parked" hp_has j_list=unparked
check "(k) the same lane with blocked:after-0.5 on its issue is not resumed" hp_has k=quiet
check "(k)   list names the issue and that label" hp_has k_list=issue
check "(l) blocked:in-flight beside blocked:after-0.5 on the issue still parks" hp_has l=quiet
check "(l)   list names the parking label, not in-flight" hp_has l_list=issue
check "(m) a PR itself labelled blocked:in-flight is not resumed" hp_has m=quiet
check "(m)   list says it was skipped for that label" hp_has m_list=label

# ---------------------------------------------------------------- mutants
# Each from a copy beside its sourced helpers; the real file is never touched.
hp_mutant() {   # <name> <old> <new> -> path, or "" if the anchor moved
    local md="$T/handback-parked-mut-$1"; rm -rf "$md"; mkdir -p "$md"
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
hp_mut() {   # <name> <old> <new> <leg that must go wrong> <what it shows>
    local m mg; m=$(hp_mutant "$1" "$2" "$3")
    if [ -z "$m" ]; then bad "mutant anchor '$1' no longer matches handback.sh"; return; fi
    mg=$(hp_scenario "$m")
    if grep -qx "$4" <<< "$mg"; then ok "mutant '$1' $5 (red, as it must be)"
    else bad "mutant '$1' passes: the fragment cannot see it"; fi
}
hp_mut noprefix 'blocked:*) printf' 'blocked:needs-owner) printf' \
       a=resumed "with only the literal list resumes #436's shape"
hp_mut noissue 'PARKED_LANES=$(parked_lanes)' 'PARKED_LANES=""' \
       h=resumed "without the issue half idle-resumes a lane whose issue is parked"
# The in-flight exception removed: the world before 2026-09-28, #569's lanes
# parked by their own issue's in-flight label, never resumed on their runs.
hp_mut noinflight 'ISSUE_NOT_PARKING="blocked:in-flight"' 'ISSUE_NOT_PARKING=""' \
       j=quiet "without the in-flight exception parks #569's waiting lanes"
# The issue read on its first blocked:* label only (the old jq's `first`):
# in-flight listed first hides the label that does park.
hp_mut firstonly 'labs.split(",")' 'labs.split(",")[:1]' \
       l=resumed "reading only the issue's first blocked:* label resumes a lane after-0.5 parks"
# The exception applied to the PR half too: #504's interim label stops parking.
hp_mut prinflight 'blocked:*) printf' 'blocked:in-flight) ;; blocked:*) printf' \
       m=resumed "with the exception on the PR half resumes a PR labelled blocked:in-flight"
rm -rf "$T"/handback-parked-mut-*

hp_state_reset; rm -f "$HP_L/selftestp"*.json; rm -rf "$DISPATCH_DIR/results/"*-selftestpk-*
