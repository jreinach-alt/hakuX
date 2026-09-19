# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# fleet.py's running set, and the registry lane.sh now writes.
# Landed on master as an append to selftest.sh (#133, lane/fleetreg); carried
# here unchanged when that fold met this split.
#
# 96 because on master it sat after the affinity block, and the numbering
# keeps that position. It holds two `==` sections, as its author wrote them;
# a later lane splitting them into 96- and 97- is welcome, but that is an
# edit, and carrying this through the split was a move.
#
# Builds its own fixtures and shims; depends on no other fragment.

echo "== fleet.py: the running set is asked of systemd, not read from a file"
# THE SENSOR THE BOARD WAKES ON. board.sh greps fleet.py's FAIL lines and
# starts a model session on any hit. Until 2026-09-19 all four of those FAILs
# were computed from $DISPATCH_DIR/fleet/<lane>.json, "written by the
# ORCHESTRATOR" -- a role ORCHESTRATION-DESIGN.md §4 deleted, after which
# nothing wrote it. Measured with eight lanes running: fleet.py named four,
# two of them not running and one already merged, and six consecutive board
# ticks logged `nothing actionable`. A blind sensor reports calm.
#
# So these checks are about PROVENANCE, not formatting: a lane systemd calls
# active must appear even with no file, a file for a lane with no unit must
# not, and a systemd that cannot be reached must produce NO FAIL at all
# rather than the FAILs an empty fleet implies. That last one is the
# dangerous direction -- "nothing is running" and "I could not ask" would
# otherwise render identically, and the second hands DISPATCHABLE every
# issue a live lane already owns.
export FL="$T/fleet" TESTING; mkdir -p "$FL/bin" "$FL/blind" "$DISPATCH_DIR/fleet"
cat > "$FL/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *list-units*hakux-lane*) echo "hakux-lane-alive.service loaded active running claude" ;;
    *show*) printf 'Id=hakux-lane-alive.service\nActiveEnterTimestampMonotonic=1000000\n' ;;
    *is-active*) echo active ;;
esac
exit 0
EOF
cat > "$FL/blind/systemctl" <<'EOF'
#!/usr/bin/env bash
echo "Failed to connect to bus" >&2; exit 1
EOF
# A gh that answers fleet.py's two questions for real, so the DISPATCHABLE and
# READY-NOT-FOLDED paths run instead of falling into their blind branches.
cat > "$FL/bin/gh" <<'EOF'
#!/usr/bin/env bash
case "$1 $2" in
    "issue list") echo '[{"number":9401,"title":"selftest: an open issue no lane owns"}]' ;;
    "pr list")    cat "${SELFTEST_FLEET_PRS:?}" ;;
    *) exit 0 ;;
esac
exit 0
EOF
cp "$FL/bin/gh" "$FL/blind/gh"
chmod +x "$FL/bin/"* "$FL/blind/"*
# The entry the deleted orchestrator left behind, in its exact shape: state
# "running", for a lane whose unit has not existed since 09-14.
python3 -c 'import json,sys; json.dump({"lane":"ghostlane","agent":"a34b29","state":"running","issues":["9401"],"asked":"a lane that ended days ago","dispatched_utc":"2026-09-14T05:23:00Z"}, open(sys.argv[1],"w"))' "$DISPATCH_DIR/fleet/ghostlane.json"
echo '[]' > "$FL/prs.json"
fleet_run() {   # <bindir> <outfile>; stdout and stderr together, FAILs included
    ( export PATH="$1:$PATH" SELFTEST_FLEET_PRS="$FL/prs.json" HAKUX_REPO="example/hakux"
      cd "$REPO" && python3 docs/testing/fleet.py ) > "$2" 2>&1
}
fleet_run "$FL/bin" "$FL/live.txt"
check "a lane systemd calls active is RUNNING even with no registry entry" grep -qE '^  alive ' "$FL/live.txt"
check "a registry entry whose unit is gone is not reported as running" bash -c '! grep -q ghostlane "$FL/live.txt"'
check "the ignored entry is counted, not hidden" grep -q 'registry entr.*no active unit, ignored' "$FL/live.txt"
check "a running lane with no territory row FAILs, naming the live lane" grep -qE '^FAIL: 1 lane\(s\) are RUNNING with no territory row -- alive\.' "$FL/live.txt"
check "an issue no running lane owns FAILs as dispatchable" grep -qE '^FAIL: .*could be dispatched and are not' "$FL/live.txt"

# THE BLIND RUN. Same fixtures, a systemctl that cannot answer.
fleet_run "$FL/blind" "$FL/blind.txt"
check "a systemctl that cannot answer says FLEET-BLIND" grep -q 'FLEET-BLIND' "$FL/blind.txt"
# Exactly one, and it is the blindness. Not zero -- board.sh keeps only '^FAIL'
# and drops everything else, so a blindness announced any other way is
# announced to nobody, which is how this file reported calm for five days. And
# not the FAILs an empty running set implies: "I could not ask" is not
# "nothing is running", and the difference is the whole defect.
check "fleet-blind raises exactly one FAIL" bash -c '[ "$(grep -c "^FAIL" "$FL/blind.txt")" = 1 ]'
check "and that FAIL is the blindness, not the FAILs an empty fleet implies" grep -q '^FAIL: FLEET-BLIND' "$FL/blind.txt"
check "fleet-blind raises no RUNNING-WITH-NO-TERRITORY-ROW FAIL" bash -c '! grep -q "^FAIL.*RUNNING with no territory row" "$FL/blind.txt"'
check "fleet-blind says DISPATCHABLE was not computed rather than printing zero" grep -q 'DISPATCHABLE NOW, NOT DISPATCHED (0).*NOT COMPUTED' "$FL/blind.txt"
# The one section an empty running set makes maximally WRONG rather than
# merely silent: every territory row would read as an abandoned claim, and a
# reader acting on that retires the live fleet's rows.
check "fleet-blind lists no territory row as abandoned" grep -q 'LANE CLAIMED WITH NO RUNNING AGENT (0).*NOT COMPUTED' "$FL/blind.txt"

# READY, NOT FOLDED, asked of GitHub instead of a `state` field a lane would
# have had to write about itself.
cat > "$FL/prs.json" <<'EOF'
[{"number":9501,"headRefName":"lane/draftlane","isDraft":true,"labels":[],"updatedAt":"2026-09-19T06:00:00Z","title":"still working"},
 {"number":9502,"headRefName":"lane/donelane","isDraft":false,"labels":[],"updatedAt":"2026-09-19T06:00:00Z","title":"ready and unlabelled"},
 {"number":9503,"headRefName":"lane/heldlane","isDraft":false,"labels":[{"name":"fold-ready"}],"updatedAt":"2026-09-19T06:00:00Z","title":"the fold job has it"},
 {"number":9504,"headRefName":"lane/stucklane","isDraft":true,"labels":[{"name":"blocked"}],"updatedAt":"2026-09-19T06:00:00Z","title":"waiting on a file"},
 {"number":9505,"headRefName":"lane/alive","isDraft":true,"labels":[],"updatedAt":"2026-09-19T06:00:00Z","title":"the running lane's own PR"},
 {"number":9506,"headRefName":"board/not-a-lane","isDraft":false,"labels":[],"updatedAt":"2026-09-19T06:00:00Z","title":"not a lane branch"}]
EOF
fleet_run "$FL/bin" "$FL/prs.txt"
check "a READY lane PR with no pipeline label FAILs as unfolded" grep -qE '^FAIL: 1 lane PR\(s\) are READY and carry no pipeline label: #9502\.' "$FL/prs.txt"
check "a draft lane PR is not reported as ready" bash -c '! grep -q 9501 "$FL/prs.txt"'
check "a READY PR a job already holds (fold-ready) is not the board's item" bash -c '! grep -q 9503 "$FL/prs.txt"'
check "a READY PR that is not on a lane/ branch is nobody's lane" bash -c '! grep -q 9506 "$FL/prs.txt"'
check "a lane PR labelled blocked FAILs, replacing the orchestrator's waiting_on" grep -qE "^FAIL: 1 lane PR\(s\) labelled .blocked.: #9504\." "$FL/prs.txt"
check "the running lane's own PR is shown against it in RUNNING" grep -qE '^  alive .*PR #9505 draft' "$FL/prs.txt"

echo "== lane.sh writes the registry it used to leave to a role that no longer exists"
# `grep -n fleet docs/testing/lane.sh` returned nothing for the whole life of
# the file. These run the REAL start path against a throwaway origin, so the
# worktree, the attempt counter and the cap arithmetic all execute.
export LW="$FL/work" LD="$FL/dispatch"; mkdir -p "$LW/briefs" "$LD"
git init -q -b master "$FL/origin"
git -C "$FL/origin" -c user.email=s@t -c user.name=s commit -q --allow-empty -m base
git clone -q "$FL/origin" "$FL/repo"
printf '# brief for the selftest lane\n\nIt is asked to do "one thing" with a \\ in it.\n' > "$FL/brief.md"
( export PATH="$FL/bin:$PATH" HAKUX_WORK="$LW" HAKUX_REPO_DIR="$FL/repo" DISPATCH_DIR="$LD" \
         SELFTEST_GH_LOG="$FL/run.log"; : > "$FL/run.log"
  bash "$TESTING/lane.sh" start selftestlane "$FL/brief.md" 9401 ) > "$FL/start.txt" 2>&1
check "lane.sh start writes a registry entry for the lane it started" test -f "$LD/fleet/selftestlane.json"
check "the entry carries the brief it handed over, quotes and backslashes intact" \
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if "one thing" in d["asked"] and d["issues"]==["9401"] and d["branch"]=="lane/selftestlane" else 1)' "$LD/fleet/selftestlane.json"
check "the entry carries NO state field -- state is the thing that went stale" \
    python3 -c 'import json,sys; sys.exit(1 if "state" in json.load(open(sys.argv[1])) else 0)' "$LD/fleet/selftestlane.json"
check "the unit clears its own entry at exit" grep -q "lane.sh' fleet-end 'selftestlane'" "$FL/run.log"
( export PATH="$FL/bin:$PATH" HAKUX_WORK="$LW" DISPATCH_DIR="$LD"; bash "$TESTING/lane.sh" fleet-end selftestlane 0 ) >/dev/null 2>&1
# Both halves, so this cannot pass by there having been nothing to remove --
# which is exactly how it passed against the file being replaced.
check "fleet-end removes the entry, having first written its history line" \
    bash -c 'test -f "$LD/fleet/history.jsonl" && ! test -f "$LD/fleet/selftestlane.json"'
check "fleet-end keeps what the lane was asked, in history.jsonl" grep -q 'one thing' "$LD/fleet/history.jsonl"
check "history.jsonl is not a *.json file, so fleet.py never reads it as a lane" \
    bash -c 'case "$LD/fleet/history.jsonl" in *.json) exit 1 ;; esac; grep -q "\"lane\": \"selftestlane\"" "$LD/fleet/history.jsonl"'

# fleet-gc, and the refusal that matters more than the collection.
mkdir -p "$LD/fleet"   # the fixtures below must really exist, or "gc dropped it" is vacuous
cp "$DISPATCH_DIR/fleet/ghostlane.json" "$LD/fleet/ghostlane.json"
python3 -c 'import json,sys; json.dump({"lane":"alive"}, open(sys.argv[1],"w"))' "$LD/fleet/alive.json"
( export PATH="$FL/bin:$PATH" HAKUX_WORK="$LW" DISPATCH_DIR="$LD"; bash "$TESTING/lane.sh" fleet-gc ) >/dev/null 2>&1
check "fleet-gc drops the entry whose unit is gone" bash -c '! test -f "$LD/fleet/ghostlane.json"'
check "fleet-gc keeps the entry whose unit is active" test -f "$LD/fleet/alive.json"
check "fleet-gc REFUSES when systemd cannot answer, rather than clearing the live fleet" \
    bash -c 'out=$(PATH="$FL/blind:$PATH" HAKUX_WORK="$LW" DISPATCH_DIR="$LD" bash "$TESTING/lane.sh" fleet-gc 2>&1)
             case "$out" in *REFUSED*) ;; *) exit 1 ;; esac
             test -f "$LD/fleet/alive.json"'
