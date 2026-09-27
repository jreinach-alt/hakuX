# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# handback.sh: a lane that has MOVED ON to a second branch is found through its
# PR body's `Lane:` line, and its first PR is not labelled as abandoned.
#
# THE DEFECT, 2026-09-27. lane.flip474 opened draft #504 on `lane/flip474-ts`,
# then switched `$WORK/wt/flip474` to `lane/flip474-sysmem` (#516). Nothing had
# `lane/flip474-ts` checked out, so neither the branch strip nor the worktree
# resolver found a lane, and handback labelled #504 `blocked:needs-owner` at
# 22:52:08Z -- and again at 23:02:08Z after hostops removed it, every tick.
#
# The worlds each leg fails in:
#   (a) fails in a world where the body is not read, or is read and its name
#       not accepted: #504 is labelled again (the defect), or resumed as a
#       lane on a branch it is not on.
#   (b) fails in a world where the body's name is used unvalidated: `../x`
#       names a unit and a path outside wt/ -- it must fall to the old path.
#   (c) fails in a world where the new resolver swallows the dead end: a PR
#       with no Lane: line must still be labelled and commented, and the
#       comment must say the body was tried.

echo "== handback.sh: a moved lane's draft resolves from its PR body's Lane: line"
HL="$T/handback-laneline"; mkdir -p "$HL/bin"
cat > "$HL/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${HD_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        if [[ "$args" == *isDraft* ]]; then cat "$HD/drafts.tsv" 2>/dev/null; fi
        exit 0 ;;
    "pr view")
        [[ "$args" == *body* ]] && cat "$HD/body.md" 2>/dev/null
        exit 0 ;;
    "pr comment")
        b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$HD/comments.log"; b=""; }; [ "$a" = --body-file ] && b=1; done
        echo "--- end comment" >> "$HD/comments.log"; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HL/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) exit 3 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HL/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${HD_LOG:?}"; exit 0
EOF
chmod +x "$HL/bin/"*
: > "$HL/territory.toml"
mkdir -p "$HAKUX_WORK/briefs" "$HAKUX_WORK/wt"
LL=selftestll; LBR="lane/$LL-ts"
L1=cccccccccccccccccccccccccccccccccccccc51; L2=cccccccccccccccccccccccccccccccccccccc52
L3=cccccccccccccccccccccccccccccccccccccc53

hl() { ( export HD="$HL" HD_LOG="$HL/gh.log" PATH="$HL/bin:$PATH" HAKUX_LANE_SH="$TESTING/lane.sh" HAKUX_TERRITORY="$HL/territory.toml"
         bash "$@" 2>&1 ); }
hl_reset() { : > "$HL/gh.log"; : > "$HL/comments.log"; }
hl_ran()   { grep -cE "systemd-run.*hakux-lane-$1( |$)" "$HL/gh.log"; }
# <pr> <head>: a green draft on $LBR, quiet past the clock.
hl_draft() { printf '%s\t%s\t%s\tisDraft=true ci=GREEN quiet=9000\t\n' "$1" "$LBR" "$2" > "$HL/drafts.tsv"; }
hl_state_reset() {
    rm -rf "$HAKUX_WORK/wt/$LL" "$HAKUX_WORK/wt/$LL-ts"
    rm -f "$HAKUX_WORK/handback/done/"*"-55"[1-3]"-"* "$HAKUX_WORK/handback/done/noname-55"[1-3] \
          "$HAKUX_WORK/handback/strand/$LL"* "$HAKUX_WORK/attempts/$LL"* \
          "$HAKUX_WORK/briefs/$LL.md" "$HL/drafts.tsv" "$HL/body.md"
    hl_reset
}

hl_scenario() {
    local s="$1"
    hl_state_reset
    # The lane exists and has moved on: wt/$LL is on another branch, with a brief.
    git init -q "$HAKUX_WORK/wt/$LL"; git -C "$HAKUX_WORK/wt/$LL" symbolic-ref HEAD "refs/heads/lane/$LL-sysmem"
    echo "# brief" > "$HAKUX_WORK/briefs/$LL.md"
    # (a) THE DEFECT: body `Lane: $LL` resolves; not labelled, not resumed.
    printf 'Lane: %s            Issue: #474 [#462]\r\nBase: master\n' "$LL" > "$HL/body.md"
    hl_draft 551 "$L1"; hl_reset; hl "$s" >/dev/null
    grep -q "blocked:needs-owner" "$HL/gh.log" || echo "a_nolabel=yes"
    [ -s "$HL/comments.log" ] || echo "a_nocomment=yes"
    [ "$(hl_ran "$LL")" -eq 0 ] && [ "$(hl_ran "$LL-ts")" -eq 0 ] && echo "a=quiet"
    hl "$s" list | grep -qF "#551 $LBR: draft-strand-quiet, lane $LL (from the PR body's Lane: line) is live on lane/$LL-sysmem" && echo "a_list=named"
    # (b) body `Lane: ../x`: rejected by the name check, the old dead end.
    printf 'Lane: ../x\n' > "$HL/body.md"
    hl_draft 552 "$L2"; hl_reset; hl "$s" >/dev/null
    grep -q "blocked:needs-owner" "$HL/gh.log" && echo "b_label=yes"
    grep -qF "lane \`$LL-ts\` (resolved from branch \`$LBR\`" "$HL/comments.log" && echo "b_says=stripped"
    grep -qF "\`Lane:\` line does not name a lane" "$HL/comments.log" && echo "b_why=invalid"
    grep -qF "../x" "$HL/comments.log" || echo "b_noecho=yes"
    [ "$(hl_ran "$LL")" -eq 0 ] && echo "b=quiet"
    # (c) no Lane: line: the old behaviour, and the comment says the body was tried.
    printf 'Some PR with no header\n' > "$HL/body.md"
    hl_draft 553 "$L3"; hl_reset; hl "$s" >/dev/null
    grep -q "blocked:needs-owner" "$HL/gh.log" && echo "c_label=yes"
    grep -qF "the PR body has no \`Lane:\` line" "$HL/comments.log" && echo "c_why=noline"
    [ "$(hl_ran "$LL")" -eq 0 ] && echo "c=quiet"
}

got=$(hl_scenario "$HERE/handback.sh")
hl_has() { grep -qx "$1" <<< "$got"; }
check "(a) body Lane: $LL on a moved lane: #551 not labelled blocked:needs-owner" hl_has a_nolabel=yes
check "(a)   no comment on it" hl_has a_nocomment=yes
check "(a)   and no resume of either name" hl_has a=quiet
check "(a)   list names the lane and the branch it is live on" hl_has a_list=named
check "(b) body Lane: ../x falls to the old dead end (labelled)" hl_has b_label=yes
check "(b)   the comment names the stripped lane" hl_has b_says=stripped
check "(b)   and says the Lane: line is not a lane name" hl_has b_why=invalid
check "(b)   without echoing the body's text" hl_has b_noecho=yes
check "(b)   nothing resumed" hl_has b=quiet
check "(c) no Lane: line: still labelled blocked:needs-owner" hl_has c_label=yes
check "(c)   the comment says the body was tried" hl_has c_why=noline
check "(c)   nothing resumed" hl_has c=quiet

# ---------------------------------------------------------------- mutants
hl_mutant() {   # <name> <old> <new> -> path, or "" if the anchor moved
    local md="$T/handback-laneline-mut-$1"; rm -rf "$md"; mkdir -p "$md"
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
hl_mut() {   # <name> <old> <new> <leg that must NOT appear> <what it shows>
    local m mg; m=$(hl_mutant "$1" "$2" "$3")
    if [ -z "$m" ]; then bad "mutant anchor '$1' no longer matches handback.sh"; return; fi
    mg=$(hl_scenario "$m")
    if grep -qx "$4" <<< "$mg"; then bad "mutant '$1' passes: the fragment cannot see it"
    else ok "mutant '$1' $5 (red, as it must be)"; fi
}
hl_mut nobody '&& lane_from_body "$2" && return 0 ;;' ';;' \
       a_nolabel=yes "without the body resolver labels #504's shape again"
hl_mut noskip '            continue
        fi

        # RESUME ONLY ON A NEW CAUSE.' '        fi

        # RESUME ONLY ON A NEW CAUSE.' \
       a=quiet "that does not skip a body-resolved lane resumes it on a branch it left"
hl_mut novalidate '! [[ "$n" =~ ^[a-z0-9][a-z0-9-]*$ ]]' 'false' \
       b_why=invalid "without the name check cannot say ../x is not a lane"
rm -rf "$T"/handback-laneline-mut-*

hl_state_reset
