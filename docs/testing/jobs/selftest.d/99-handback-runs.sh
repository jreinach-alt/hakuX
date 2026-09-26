# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# handback.sh's `draft-strand-runs` (defect 23 of the dispatch-hardening
# brief): a stranded draft whose lane's device requests have ALL finished,
# at least one since its last session ended, is resumed once -- within the
# tick, not on the two-hour quiet clock -- with the result dirs in its brief.
#
# After 99-handback-draft.sh, whose gh/systemctl/systemd-run shims it copies
# into a directory of its own, the way 99-handback-strand.sh does.
#
# THE DEFECT, measured 2026-09-25 23:45Z: the Nova had 23 lane requests
# waiting, perfarch's nine soaks among them at ~180 min, and a lane whose soak
# finished waited up to DRAFT_STRAND_SECS (2 h) for its own result, because
# this job resumed a waiting lane only on a JUDGED ARM or on that clock.

echo "== handback.sh: a lane whose device runs finished is resumed on them"
HR="$T/handback-runs"; mkdir -p "$HR/bin"
for s in gh systemctl systemd-run; do
    cp "$T/handback-draft/bin/$s" "$HR/bin/$s" 2>/dev/null || bad "99-handback-draft.sh's $s shim is not there to build on"
done
HR_Q="$DISPATCH_DIR"; HR_A="$HAKUX_WORK/arms"; HR_L="$HAKUX_WORK/logs/lane"
mkdir -p "$HR_Q/queue" "$HR_Q/running" "$HR_Q/results" "$HR_A/pairs" "$HR_A/judged" "$HR_L"
# THREE LANES, OURS IN THE MIDDLE. `selftestrq` sorts ahead of ours; the
# other is named with ours as a PREFIX, so an owner rule of "starts with the
# lane name" would count its requests as ours. All three are known lanes (a
# worktree each), which is what lets the longest match win.
LO=selftestrq; ME=selftestrs; HI=selftestrs-x
for l in "$LO" "$ME" "$HI"; do mkdir -p "$HAKUX_WORK/wt/$l"; done
BR="lane/$ME"; PR=402
HEAD1=cccccccccccccccccccccccccccccccccccccccc1

hr_state_reset() {
    rm -rf "$HR_Q/queue/"*-selftestr* "$HR_Q/running/"*-selftestr* "$HR_Q/results/"*selftestr*
    rm -f "$HAKUX_WORK/handback/done/"*"-$PR-"* "$HAKUX_WORK/handback/strand/$ME" "$HAKUX_WORK/attempts/$ME"
    rm -f "$HR_L/$ME."*.json
    echo "# the original brief" > "$HAKUX_WORK/briefs/$ME.md"
    : > "$HR/gh.log"; : > "$HR/comments.log"; : > "$HR/active"
    # The lane's last session ENDED an hour ago: that is the line between a
    # run it saw and a run it has not.
    echo '{}' > "$HR_L/$ME.20260925T220000Z.json"; touch -d '-1 hour' "$HR_L/$ME.20260925T220000Z.json"
    hr_draft "$HEAD1"
}
# <script> [args]: one tick of a handback.sh, with our shims on PATH.
# IDLE_GRACE_SECS held off: this lane's session ended an hour ago with nothing
# in flight, which is also the idle cause (99-handback-idle.sh), and leg (0)
# asks only whether an OLD RUN is news.
hr() { local s="$1"; shift; ( export HD="$HR" HD_LOG="$HR/gh.log" PATH="$HR/bin:$PATH" HAKUX_LANE_SH="$TESTING/lane.sh" IDLE_GRACE_SECS=999999; bash "$s" "$@" 2>&1 ); }
hr_reset()  { : > "$HR/gh.log"; : > "$HR/comments.log"; }
hr_runs()   { grep -cE "systemd-run.*hakux-lane-$ME( |$)" "$HR/gh.log"; }
hr_ran()    { [ "$(hr_runs)" -eq 1 ]; }
hr_no_run() { [ "$(hr_runs)" -eq 0 ]; }
hr_said()   { grep -qF -- "$1" "$HR/comments.log"; }
hr_quiet()  { [ ! -s "$HR/comments.log" ]; }
# A draft quiet for only 60 s: the quiet clock is nowhere near firing, so a
# resume here can only be the runs cause.
hr_draft()  { printf '%s\t%s\t%s\tisDraft=true ci=GREEN quiet=60\t\n' "$PR" "$BR" "$1" > "$HR/drafts.tsv"; }
# <dir> <id> <requester> [<extra json fields>]: a request as request.sh writes it.
hr_req()    { printf '{"id": "%s", "requester": "%s", "purpose": "a soak"%s}\n' "$2" "$3" "${4:-}" > "$HR_Q/$1/$2.req"; }
# <id> <requester> <DONE|ERROR> <age> [<extra>]: a finished request, its marker <age> old.
hr_done()   { mkdir -p "$HR_Q/results/$1"
              printf '{"id": "%s", "requester": "%s", "purpose": "a soak"%s}\n' "$1" "$2" "${5:-}" > "$HR_Q/results/$1/request.json"
              : > "$HR_Q/results/$1/$3"; touch -d "$4" "$HR_Q/results/$1/$3"; }
hr_brief()  { cat "$HAKUX_WORK/briefs/$ME.md"; }

# The scenario, as a function of the script under test, so a mutant and the
# old file run exactly the legs the real one does. Each leg echoes a word;
# the caller asserts on the words.
hr_scenario() {
    local s="$1" out
    hr_state_reset
    # (0) a run that finished BEFORE the session ended is not news.
    hr_done 1790000000-$ME-100 "$ME" DONE '-2 hours'
    hr_reset; hr "$s" >/dev/null
    hr_no_run && echo "LEG0=quiet" || echo "LEG0=resumed"
    # (a) one of ours finished, one still queued, the neighbours' queued:
    # every request must be finished, so this waits.
    hr_done 1790000100-$ME-101 "$ME" DONE '-5 minutes'
    hr_req queue 1790000200-$ME-102 "$ME"
    hr_req queue 1790000150-$LO-103 "lane.$LO"
    hr_req queue 1790000160-$HI-104 "$HI-soak"
    hr_reset; out=$(hr "$s" list); hr "$s" >/dev/null
    hr_no_run && echo "LEGa=quiet" || echo "LEGa=resumed"
    grep -q "its device request is in flight (queue/1790000200-$ME-102)" <<< "$out" && echo "LEGa_named=yes"
    # (b) ours all finished -- one ERROR, one by the `lane` field alone; the
    # neighbours' are still queued, one finished, and none of it is ours.
    rm -f "$HR_Q/queue/1790000200-$ME-102.req"
    hr_done 1790000200-$ME-102 "$ME" ERROR '-1 minute'
    hr_done 1790000300-host-105 host DONE '-1 minute' ', "lane": "'"$ME"'"'
    hr_done 1790000170-$HI-106 "$HI-soak" DONE '-1 minute'
    hr_reset; out=$(hr "$s" list); hr "$s" >/dev/null
    hr_ran && echo "LEGb=resumed" || echo "LEGb=quiet"
    grep -q "WOULD RESUME lane.$ME (draft-strand-runs)" <<< "$out" && echo "LEGb_cause=runs"
    hr_brief | grep -q "| \`1790000200-$ME-102\` | ERROR | \`$HR_Q/results/1790000200-$ME-102\` |" && echo "LEGb_error_row=yes"
    hr_brief | grep -q "1790000300-host-105" && echo "LEGb_lane_field=yes"
    hr_brief | grep -q "1790000100-$ME-101" && echo "LEGb_seen_run=yes"
    hr_brief | grep -q "1790000000-$ME-100" && echo "LEGb_old_run=yes"
    hr_brief | grep -q "1790000170-$HI-106" && echo "LEGb_neighbour=yes"
    hr_said "Finished runs this time:" && echo "LEGb_comment=yes"
    [ ! -f "$HAKUX_WORK/handback/strand/$ME" ] && echo "LEGb_uncapped=yes"
    [ ! -s "$HAKUX_WORK/attempts/$ME" ] || [ "$(cat "$HAKUX_WORK/attempts/$ME")" = 0 ] && echo "LEGb_uncounted=yes"
    # (c) the next tick, and a push: the same finished set is not news.
    hr_reset; hr "$s" >/dev/null
    hr_draft cccccccccccccccccccccccccccccccccccccccc2
    hr "$s" >/dev/null
    hr_no_run && hr_quiet && echo "LEGc=quiet" || echo "LEGc=resumed"
    # (d) an arm's own result is the arm cause's, not this one's: a finished
    # run whose expect_sha is a registered prediction resumes nothing here.
    local sha; sha=$(printf '%064d' 0 | tr 0 d)
    printf '{"sha": "%s", "source": "%s:docs/testing/predictions/x.json"}\n' "$sha" "$BR" > "$HR_A/pairs/$sha.json"
    # The session that (b) resumed has ended since, so (b)'s runs are old news
    # and the arm's result, newer than that, is the only candidate left.
    rm -f "$HR_L/$ME."*.json; echo '{}' > "$HR_L/$ME.20260925T230000Z.json"; touch -d '-30 seconds' "$HR_L/$ME.20260925T230000Z.json"
    hr_done 1790000400-arms-$ME-fix-107 "arms-$ME-fix" DONE 'now' ', "expect_sha": "'"$sha"'"'
    hr_reset; hr "$s" >/dev/null
    hr_no_run && echo "LEGd=quiet" || echo "LEGd=resumed"
    rm -f "$HR_A/pairs/$sha.json"
}

got=$(hr_scenario "$HERE/handback.sh")
check "(0) a run that finished before the lane's last session ended resumes nothing" grep -qx LEG0=quiet <<< "$got"
check "(a) one of the lane's requests still queued: not resumed" grep -qx LEGa=quiet <<< "$got"
check "(a)   and list names the request it waits on" grep -qx LEGa_named=yes <<< "$got"
check "(b) all finished: resumed once, inside the quiet clock" grep -qx LEGb=resumed <<< "$got"
check "(b)   on the runs cause" grep -qx LEGb_cause=runs <<< "$got"
check "(b)   the brief names the ERROR run and its result dir" grep -qx LEGb_error_row=yes <<< "$got"
check "(b)   a request owned by its lane field alone is the lane's" grep -qx LEGb_lane_field=yes <<< "$got"
check "(b)   and the one it finished beside it" grep -qx LEGb_seen_run=yes <<< "$got"
check "(b)   the run from before its session is not listed" bash -c '! grep -qx LEGb_old_run=yes <<< "$1"' _ "$got"
check "(b)   nor the prefix-named neighbour's run" bash -c '! grep -qx LEGb_neighbour=yes <<< "$1"' _ "$got"
check "(b)   the PR comment names the finished runs" grep -qx LEGb_comment=yes <<< "$got"
check "(b)   it does not spend a strand resume against DRAFT_STRAND_MAX" grep -qx LEGb_uncapped=yes <<< "$got"
check "(b)   nor an attempt" grep -qx LEGb_uncounted=yes <<< "$got"
check "(c) the same finished set, a tick later and after a push: not again" grep -qx LEGc=quiet <<< "$got"
check "(d) an arm's result is left to the arm cause" grep -qx LEGd=quiet <<< "$got"

# ---------------------------------------------------------------- mutants
# Each from a copy beside its sourced helpers; the real file is never touched.
hr_mutant() {   # <name> <python: old> <python: new> -> path, or "" if the anchor moved
    local md="$T/handback-runs-mut-$1"; rm -rf "$md"; mkdir -p "$md"
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
m=$(hr_mutant prefix 'return (max(hits, key=len) if hits else None), kind' 'return (name if name in hits else (max(hits, key=len) if hits else None)), kind')
if [ -n "$m" ]; then
    mg=$(hr_scenario "$m")
    if grep -qx LEGb_neighbour=yes <<< "$mg" || ! grep -qx LEGb=resumed <<< "$mg"; then
        ok "mutant 'first prefix, not longest' takes the neighbour's run as ours (red, as it must be)"
    else bad "mutant 'first prefix, not longest' passes: the fragment cannot see the owner rule"; fi
else bad "mutant anchor 'longest prefix' no longer matches handback.sh"; fi
m=$(hr_mutant anchor 'ended = max(os.path.getmtime(p) for p in logs)' 'ended = 0')
if [ -n "$m" ]; then
    mg=$(hr_scenario "$m")
    if grep -qx LEG0=resumed <<< "$mg"; then
        ok "mutant 'no session anchor' resumes on a run the lane already saw (red, as it must be)"
    else bad "mutant 'no session anchor' passes: leg (0) cannot see it"; fi
else bad "mutant anchor 'session end' no longer matches handback.sh"; fi
m=$(hr_mutant inflight '            print("INFLIGHT\t%s\t%s/%s" % (kind, d, r.get("id") or rid))
            sys.exit(0)' '            pass')
if [ -n "$m" ]; then
    mg=$(hr_scenario "$m")
    if grep -qx LEGa=resumed <<< "$mg"; then
        ok "mutant 'ignore requests in flight' resumes with a soak still queued (red, as it must be)"
    else bad "mutant 'ignore requests in flight' passes: leg (a) cannot see it"; fi
else bad "mutant anchor 'in flight' no longer matches handback.sh"; fi
m=$(hr_mutant armres '        continue                                                # the arm cause'"'"'s' '        pass')
if [ -n "$m" ]; then
    mg=$(hr_scenario "$m")
    if grep -qx LEGd=resumed <<< "$mg"; then
        ok "mutant 'count an arm's result as a run' resumes ahead of the verdict (red, as it must be)"
    else bad "mutant 'count an arm's result as a run' passes: leg (d) cannot see it"; fi
else bad "mutant anchor 'arm result' no longer matches handback.sh"; fi
rm -rf "$T"/handback-runs-mut-*

hr_state_reset; rm -f "$HR/drafts.tsv" "$HR_L/$ME."*.json
rm -rf "$HR_Q/results/"*selftestr* "$HR_Q/queue/"*-selftestr*
