# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# handback.sh: a lane whose PR is on a branch other than `lane/<its name>` is
# found through the worktree that has that branch checked out.
#
# THE DEFECT, 2026-09-27. lane.flip474 opened #504 on `lane/flip474-ts`,
# checked out in `$WORK/wt/flip474` with `briefs/flip474.md`. lane_name()
# stripped `lane/` to a lane `flip474-ts`, found no `wt/flip474-ts`, and at
# 20:25:11Z labelled #504 `blocked:needs-owner` -- "nothing will act on it" --
# while the lane was alive and waiting on four queued device requests.
#
# Its own shims, in a directory of its own, as 99-handback-parked.sh does.

echo "== handback.sh: a PR on a second branch resolves to the lane whose worktree has it"
HB="$T/handback-branch"; mkdir -p "$HB/bin"
cat > "$HB/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${HD_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        if [[ "$args" == *isDraft* ]]; then cat "$HD/drafts.tsv" 2>/dev/null; fi
        exit 0 ;;
    "pr comment")
        b=""; for a in "$@"; do [ -n "$b" ] && { cat "$a" >> "$HD/comments.log"; b=""; }; [ "$a" = --body-file ] && b=1; done
        echo "--- end comment" >> "$HD/comments.log"; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HB/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) exit 3 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HB/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${HD_LOG:?}"; exit 0
EOF
chmod +x "$HB/bin/"*
: > "$HB/territory.toml"
mkdir -p "$HAKUX_WORK/briefs" "$HAKUX_WORK/wt"
LA=selftestbf; LB=selftestbg; BR="lane/$LA-ts"
H1=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb1; H2=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb2
H3=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb3; H4=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb4

hb() { ( export HD="$HB" HD_LOG="$HB/gh.log" PATH="$HB/bin:$PATH" HAKUX_LANE_SH="$TESTING/lane.sh" HAKUX_TERRITORY="$HB/territory.toml"
         bash "$@" 2>&1 ); }
hb_reset() { : > "$HB/gh.log"; : > "$HB/comments.log"; }
hb_ran()   { grep -cE "systemd-run.*hakux-lane-$1( |$)" "$HB/gh.log"; }
# <dir> <branch>: a worktree with <branch> checked out (unborn is enough for symbolic-ref).
hb_wt()    { rm -rf "$HAKUX_WORK/wt/$1"; git init -q "$HAKUX_WORK/wt/$1"; git -C "$HAKUX_WORK/wt/$1" symbolic-ref HEAD "refs/heads/$2"; }
# <pr> <head>: a green draft on $BR, quiet past the clock.
hb_draft() { printf '%s\t%s\t%s\tisDraft=true ci=GREEN quiet=9000\t\n' "$1" "$BR" "$2" > "$HB/drafts.tsv"; }
hb_state_reset() {
    rm -rf "$HAKUX_WORK/wt/$LA" "$HAKUX_WORK/wt/$LB" "$HAKUX_WORK/wt/$LA-ts"
    rm -f "$HAKUX_WORK/handback/done/"*"-50"[1-4]"-"* "$HAKUX_WORK/handback/done/noname-50"[1-4] \
          "$HAKUX_WORK/handback/strand/selftestb"* "$HAKUX_WORK/attempts/selftestb"* \
          "$HAKUX_WORK/briefs/$LA.md" "$HAKUX_WORK/briefs/$LB.md" "$HB/drafts.tsv"
    hb_reset
}

hb_scenario() {
    local s="$1"
    hb_state_reset
    # (a) THE DEFECT: $BR checked out in wt/$LA, which has a brief. Resumed as
    # $LA, and nothing is labelled.
    hb_wt "$LA" "$BR"; echo "# brief" > "$HAKUX_WORK/briefs/$LA.md"
    hb_draft 501 "$H1"; hb_reset; hb "$s" >/dev/null
    [ "$(hb_ran "$LA")" -eq 1 ] && echo "a=resumed-$LA"
    grep -q "blocked:needs-owner" "$HB/gh.log" || echo "a_nolabel=yes"
    # (b) no worktree has the branch: today's dead end, and the comment names
    # the branch AND the lane it resolved to.
    hb_wt "$LA" "lane/$LA"
    hb_draft 502 "$H2"; hb_reset; hb "$s" >/dev/null
    [ "$(hb_ran "$LA")" -eq 0 ] && [ "$(hb_ran "$LA-ts")" -eq 0 ] && echo "b=quiet"
    grep -q "blocked:needs-owner" "$HB/gh.log" && echo "b_label=yes"
    grep -qF "lane \`$LA-ts\` (resolved from branch \`$BR\`" "$HB/comments.log" && echo "b_says=both"
    # (c) two worktrees with briefs both have the branch: refused, both named.
    hb_wt "$LA" "$BR"; hb_wt "$LB" "$BR"; echo "# brief" > "$HAKUX_WORK/briefs/$LB.md"
    hb_draft 503 "$H3"; hb_reset; hb "$s" >/dev/null
    [ "$(hb_ran "$LA")" -eq 0 ] && [ "$(hb_ran "$LB")" -eq 0 ] && echo "c=quiet"
    grep -qF "more than one lane's worktree (\`$LA $LB\`" "$HB/comments.log" && echo "c_says=both"
    grep -q "blocked:needs-owner" "$HB/gh.log" || echo "c_nolabel=yes"
    # (d) the one worktree with the branch has no brief: not a lane, dead end.
    rm -rf "$HAKUX_WORK/wt/$LB"; rm -f "$HAKUX_WORK/briefs/$LA.md"
    hb_draft 504 "$H4"; hb_reset; hb "$s" >/dev/null
    [ "$(hb_ran "$LA")" -eq 0 ] && echo "d=quiet"
    grep -qF "lane \`$LA-ts\` (resolved from branch \`$BR\`" "$HB/comments.log" && echo "d_says=stripped"
}

got=$(hb_scenario "$HERE/handback.sh")
hb_has() { grep -qx "$1" <<< "$got"; }
check "(a) lane/$LA-ts checked out in wt/$LA with a brief resumes lane $LA" hb_has "a=resumed-$LA"
check "(a)   and does not label the PR blocked:needs-owner" hb_has a_nolabel=yes
check "(b) no worktree on the branch: nothing resumed" hb_has b=quiet
check "(b)   the old dead end still labels blocked:needs-owner" hb_has b_label=yes
check "(b)   and its comment names the branch and the lane it resolved" hb_has b_says=both
check "(c) two worktrees on one branch: nothing resumed" hb_has c=quiet
check "(c)   the comment names both worktrees" hb_has c_says=both
check "(c)   and is not the dead-end label" hb_has c_nolabel=yes
check "(d) a worktree on the branch with no brief is not a lane" hb_has d=quiet
check "(d)   the dead end names the stripped lane" hb_has d_says=stripped

# ---------------------------------------------------------------- mutants
hb_mutant() {   # <name> <old> <new> -> path, or "" if the anchor moved
    local md="$T/handback-branch-mut-$1"; rm -rf "$md"; mkdir -p "$md"
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
hb_mut() {   # <name> <old> <new> <leg that must NOT appear> <what it shows>
    local m mg; m=$(hb_mutant "$1" "$2" "$3")
    if [ -z "$m" ]; then bad "mutant anchor '$1' no longer matches handback.sh"; return; fi
    mg=$(hb_scenario "$m")
    if grep -qx "$4" <<< "$mg"; then bad "mutant '$1' passes: the fragment cannot see it"
    else ok "mutant '$1' $5 (red, as it must be)"; fi
}
# The unmodified strip: `${1#lane/}` and nothing else.
hb_mut strip '[ -d "$WORK/wt/$NAME" ] && return 0' 'return 0' \
       "a=resumed-$LA" "with only \${1#lane/} dead-ends #504's shape"
hb_mut guess 'hits+="${hits:+ }${d##*/}"' 'hits="${d##*/}"' \
       c=quiet "that keeps the last match guesses between two worktrees"
hb_mut nobrief '[ -f "$WORK/briefs/${d##*/}.md" ] || continue' ':' \
       d_says=stripped "without the brief test takes a briefless worktree for a lane"
rm -rf "$T"/handback-branch-mut-*

hb_state_reset
