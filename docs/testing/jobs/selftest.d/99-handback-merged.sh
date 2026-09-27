# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# handback.sh's `merged-runs` cause: a lane with a live territory row, a
# MERGED PR on its branch and no OPEN one is resumed once when nothing of its
# is in flight and a device run of its has finished since its last session.
#
# THE DEFECT, 2026-09-27: lane.titleroutes (#397) merged batch 5 as #476,
# queued three Thor soaks for batch 6 and ended its session at 07:31 PDT with
# no open PR. The draft pickups need an open draft and the no-PR pickup
# skipped it as merged ("merged is done"), so the soaks finished and nothing
# resumed it.
#
# Every leg asserts a `list` line as well as the resume count, because "not
# resumed" alone is also what a handback.sh that never looks at a merged lane
# says; the list line is the proof that it looked and declined for the named
# reason. Its own shims, in a directory of its own, as 99-handback-idle.sh.

echo "== handback.sh: a merged lane whose next runs finished is resumed on them"
HM="$T/handback-merged"; mkdir -p "$HM/bin"
cat > "$HM/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${HD_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        [[ "$args" == *"--state all"* ]] && cat "$HD/allprs.tsv" 2>/dev/null
        exit 0 ;;
    "pr comment") echo "pr comment" >> "$HD/comments.log"; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HM/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) u="${!#}"; grep -qxF -- "$u" "$HD/active" 2>/dev/null ;;
    *list-units*) cat "$HD/active" 2>/dev/null; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$HM/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${HD_LOG:?}"; exit 0
EOF
chmod +x "$HM/bin/"*
HM_L="$HAKUX_WORK/logs/lane"; HM_Q="$DISPATCH_DIR"
mkdir -p "$HM_L" "$HM_Q/queue" "$HM_Q/running" "$HM_Q/results" "$HAKUX_WORK/briefs"
# TWO LANES ON THE BOARD, BOTH WITH NEW RUNS: `selftestmg` has only a merged
# PR (ours); `selftestmo` has a merged PR AND an open one, which is the draft
# pickups' business and must not be picked up a second time here.
ME=selftestmg; MO=selftestmo
for l in "$ME" "$MO"; do mkdir -p "$HAKUX_WORK/wt/$l"; done
cat > "$HM/territory.toml" <<EOF
[lane.$ME]
issues = [911]
[lane.$MO]
issues = [912]
EOF

hm() { ( export HD="$HM" HD_LOG="$HM/gh.log" PATH="$HM/bin:$PATH" HAKUX_LANE_SH="$TESTING/lane.sh" HAKUX_TERRITORY="$HM/territory.toml" IDLE_GRACE_SECS=999999
         bash "$@" 2>&1 ); }
hm_reset() { : > "$HM/gh.log"; : > "$HM/comments.log"; }
hm_ran()   { grep -cE "systemd-run.*hakux-lane-$1( |$)" "$HM/gh.log"; }
# <id> <requester> <age>: a finished request, its DONE marker <age> old.
hm_done()  { mkdir -p "$HM_Q/results/$1"
             printf '{"id": "%s", "requester": "%s", "purpose": "a soak"}\n' "$1" "$2" > "$HM_Q/results/$1/request.json"
             : > "$HM_Q/results/$1/DONE"; touch -d "$3" "$HM_Q/results/$1/DONE"; }
hm_state_reset() {
    rm -rf "$HM_Q/queue/"*-selftestm* "$HM_Q/running/"*-selftestm* "$HM_Q/results/"*-selftestm*
    rm -f "$HAKUX_WORK/handback/done/merged-runs-selftestm"* "$HAKUX_WORK/handback/done/idle-no-pr-selftestm"* \
          "$HAKUX_WORK/handback/idle/selftestm"* "$HAKUX_WORK/attempts/selftestm"* "$HM_L/selftestm"*.json
    for l in "$ME" "$MO"; do
        echo "# the original brief" > "$HAKUX_WORK/briefs/$l.md"
        # The session ENDED an hour ago: the line between a run it saw and one it has not.
        echo '{}' > "$HM_L/$l.20260927T143100Z.json"; touch -d '-1 hour' "$HM_L/$l.20260927T143100Z.json"
    done
    : > "$HM/active"
    printf 'lane/%s\tMERGED\nlane/%s\tMERGED\nlane/%s\tOPEN\n' "$ME" "$MO" "$MO" > "$HM/allprs.tsv"
    hm_reset
}

hm_scenario() {
    local s="$1" out
    hm_state_reset
    # (1) merged, row live, one run finished five minutes ago: resumed once.
    hm_done 1790517591-$ME-1523259 "$ME" '-5 minutes'
    hm_done 1790517592-$MO-1523260 "$MO" '-5 minutes'
    hm_reset; out=$(hm "$s" list); hm "$s" >/dev/null
    [ "$(hm_ran "$ME")" -eq 1 ] && echo "L1=resumed" || echo "L1=quiet"
    grep -q "WOULD RESUME lane.$ME (merged-runs)" <<< "$out" && echo "L1_cause=merged-runs"
    grep -q "your next runs are back" "$HAKUX_WORK/briefs/$ME.md" \
        && grep -q "1790517591-$ME-1523259" "$HAKUX_WORK/briefs/$ME.md" && echo "L1_brief=yes"
    { [ ! -s "$HAKUX_WORK/attempts/$ME" ] || [ "$(cat "$HAKUX_WORK/attempts/$ME")" = 0 ]; } && echo "L1_uncounted=yes"
    [ "$(hm_ran "$MO")" -eq 0 ] && ! grep -q "lane/$MO: merged\|lane.$MO (merged-runs)" <<< "$out" && echo "L1_open=left"
    [ -s "$HM/comments.log" ] || echo "L1_nocomment=yes"
    # (2) the next tick, the same set of runs: not again, and it says why.
    hm_reset; out=$(hm "$s" list); hm "$s" >/dev/null
    [ "$(hm_ran "$ME")" -eq 0 ] && grep -q "merged-runs already actioned on finished runs" <<< "$out" && echo "L2=once"
    # (3) a new run finished but another is still queued: waiting, rightly.
    hm_state_reset
    hm_done 1790519286-$ME-2112912 "$ME" '-5 minutes'
    printf '{"id": "1790519290-%s-2113140", "requester": "%s", "purpose": "a soak"}\n' "$ME" "$ME" > "$HM_Q/queue/1790519290-$ME-2113140.req"
    hm_reset; out=$(hm "$s" list); hm "$s" >/dev/null
    [ "$(hm_ran "$ME")" -eq 0 ] && grep -q "lane/$ME: merged, but its device request is in flight (queue/1790519290-$ME-2113140)" <<< "$out" && echo "L3=waiting"
    # (4) only a run that finished BEFORE its last session: done, not resumed.
    hm_state_reset
    hm_done 1790500000-$ME-1000 "$ME" '-2 hours'
    hm_reset; out=$(hm "$s" list); hm "$s" >/dev/null
    [ "$(hm_ran "$ME")" -eq 0 ] && grep -q "lane/$ME: merged, and no run of its has finished since its last session; done" <<< "$out" && echo "L4=done"
}

got=$(hm_scenario "$HERE/handback.sh")
hm_has() { grep -qx "$1" <<< "$got"; }
check "(1) merged PR, row live, a run finished since its session: resumed" hm_has L1=resumed
check "(1)   on merged-runs" hm_has L1_cause=merged-runs
check "(1)   with the result in its brief" hm_has L1_brief=yes
check "(1)   without spending an attempt" hm_has L1_uncounted=yes
check "(1)   a lane with an OPEN PR beside its merged one is left to the draft pickups" hm_has L1_open=left
check "(1)   and nothing is commented, there being no open PR" hm_has L1_nocomment=yes
check "(2) the same runs, a tick later: not again, keyed on the result set" hm_has L2=once
check "(3) a request of its own still queued: waiting, not resumed" hm_has L3=waiting
check "(4) no run newer than its last session: done, not resumed" hm_has L4=done

# ---------------------------------------------------------------- mutants
hm_mutant() {   # <name> <old> <new> -> path, or "" if the anchor moved
    local md="$T/handback-merged-mut-$1"; rm -rf "$md"; mkdir -p "$md"
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
hm_mut() {   # <name> <old> <new> <word that must be missing> <what it shows>
    local m mg; m=$(hm_mutant "$1" "$2" "$3")
    if [ -z "$m" ]; then bad "mutant anchor '$1' no longer matches handback.sh"; return; fi
    mg=$(hm_scenario "$m")
    if ! grep -qx "$4" <<< "$mg"; then ok "mutant '$1' $5 (red, as it must be)"
    else bad "mutant '$1' passes: the fragment cannot see it"; fi
}
hm_mut nomerged 'if "MERGED" in st and "OPEN" not in st:' 'if False:' \
       L1=resumed "that never emits a merged lane strands titleroutes' soaks"
hm_mut rekey 'marker="$H/done/$label-$name-r$RKEY"' 'marker="$H/done/$label-$name-r$RKEY-$RANDOM"' \
       L2=once "keyed on anything but the result set resumes the lane every tick"
hm_mut inflight $'if [ -n "$INFLIGHT" ]; then\n                [ "$mode" = list ] && echo "$branch: merged' \
                $'if false; then\n                [ "$mode" = list ] && echo "$branch: merged' \
       L3=waiting "without the in-flight gate resumes a lane whose soak is still queued"
hm_mut norkey $'if [ -z "$RKEY" ]; then\n                [ "$mode" = list ] && echo "$branch: merged, and no' \
              $'if false; then\n                [ "$mode" = list ] && echo "$branch: merged, and no' \
       L4=done "without the new-run gate resumes a finished lane"
rm -rf "$T"/handback-merged-mut-*

hm_state_reset
