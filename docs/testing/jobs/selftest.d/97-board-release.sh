# Sourced by ../selftest.sh with the harness already built: $T, $HERE,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# RELEASE AT READY (owner, 2026-09-26; roles/board.md). A lane whose PR is
# ready -- out of draft, CI green on its head, unit gone -- has finished
# writing, and its files become available to the next lane while its PR waits
# for audit and fold. Before this, a file was held until the fold, and on
# 2026-09-26 nine hot files held that way kept 31 dispatchable issues waiting.
#
# Three readers of one field, `released = [...]` on a territory row:
#   check_territory.py  a released file may have ONE more (unreleased) holder
#   fleet.py            names ready PRs whose files are not released yet, and
#                       fold-ready PRs that are not folding, with the reason
#   board.sh released   the tick brief's list: AVAILABLE, or taken by whom
#
# Each tool runs from a COPY beside fixture board files, with HAKUX_BOARD_REF
# empty, so board_files reads the fixtures and never origin/board. Brings its
# own gh and systemctl shims; depends on no other fragment.

echo "== release at ready: a ready PR's files are available to the next lane"
BR="$T/boardrelease"; mkdir -p "$BR/bin" "$BR/testing/jobs" "$BR/fx"
cp "$TESTING/check_territory.py" "$TESTING/fleet.py" "$TESTING/gh_rest.py" \
   "$TESTING/board_files.py" "$BR/testing/"
cp "$HERE/board.sh" "$HERE/localtime.sh" "$HERE/window.sh" "$BR/testing/jobs/"
printf '[issue.1]\ntitle = "x"\nstatus = "open"\n' > "$BR/testing/nv2a_issues.toml"

# -------------------------------------------------- check_territory.py
# <territory body> -> the checker's output and exit, as "rc=N" on the last line
br_terr() {
    { printf 'wave = 1000000\n\n'; cat; } > "$BR/testing/territory.toml"
    ( cd "$BR/testing" && HAKUX_BOARD_REF="" python3 check_territory.py 2>&1; echo "rc=$?" )
}
# The released overlap: lane.done's PR is ready and released hw/a.c; one
# later lane took it. The row that released keeps it in `files`.
out=$(br_terr <<'EOF'
[lane.done]
files = ["hw/a.c", "hw/b.c"]
released = ["hw/a.c", "hw/b.c"]
released_at_ready = 9601
[lane.next]
files = ["hw/a.c"]
EOF
)
check "check_territory: a released file may be claimed by a second lane" grep -qx 'rc=0' <<< "$out"
check "...and the summary counts the released files" grep -q '2 released at ready' <<< "$out"
# The same overlap, not released: the rule this table exists for, unchanged.
out=$(br_terr <<'EOF'
[lane.done]
files = ["hw/a.c", "hw/b.c"]
released = ["hw/b.c"]
[lane.next]
files = ["hw/a.c"]
EOF
)
check "check_territory: an unreleased overlap still FAILs" grep -qx 'rc=1' <<< "$out"
check "...naming the file and both lanes" grep -q 'hw/a.c is claimed by both done and next' <<< "$out"
# One more holder, not two: two later lanes on one released file is the
# collision again, and so is a remediation that took its file back after
# another lane started on it (both are two unreleased holders).
out=$(br_terr <<'EOF'
[lane.done]
files = ["hw/a.c"]
released = ["hw/a.c"]
[lane.next]
files = ["hw/a.c"]
[lane.third]
files = ["hw/a.c"]
EOF
)
check "check_territory: two later lanes on one released file FAIL" grep -q 'hw/a.c is claimed by both next and third' <<< "$out"
# A release of a path the row does not hold frees nothing, and says it did.
out=$(br_terr <<'EOF'
[lane.done]
files = ["hw/a.c"]
released = ["hw/a.cc"]
[lane.next]
files = ["hw/a.c"]
EOF
)
check "check_territory: a release naming a file the row does not hold FAILs" grep -q "hw/a.cc is in done's released list but not in its files" <<< "$out"
check "...and frees nothing: the real file is still a collision" grep -q 'hw/a.c is claimed by both done and next' <<< "$out"

# -------------------------------------------------- board.sh released
{ printf 'wave = 1000000\n\n'; cat; } > "$BR/testing/territory.toml" <<'EOF'
[lane.done]
files = ["hw/a.c", "hw/b.c", "hw/c.c"]
released = ["hw/a.c", "hw/b.c"]
released_at_ready = 9601
[lane.next]
files = ["hw/b.c"]
[lane.draft]
files = ["hw/d.c"]
EOF
# NEVER RUN A board.sh THAT LACKS THE MODE. An unknown argument is ignored and
# the script runs a whole tick: on 2026-09-26 the falsification run of this
# fragment did exactly that against the old copy, and its audit outlet claimed
# a real audit. So the mode is checked for first, and the call is fenced
# anyway: a scratch $HAKUX_WORK and a repo dir that does not exist, so a
# fall-through dies at "cannot create" before the outlet.
if grep -q '"${1:-}" = "released"' "$BR/testing/jobs/board.sh"; then
    out=$(HAKUX_BOARD_REF="" HAKUX_WORK="$BR/work" HAKUX_REPO_DIR="$BR/no-such-repo" \
          bash "$BR/testing/jobs/board.sh" released 2>&1)
else
    out="board.sh has no released mode"
fi
check "board.sh released: a ready PR's released file is AVAILABLE, with its PR" \
    grep -qx 'hw/a.c  released by lane.done (PR #9601 ready) -- AVAILABLE' <<< "$out"
check "...a released file a later lane took is not available again" \
    grep -qx 'hw/b.c  released by lane.done (PR #9601 ready) -- taken by lane.next' <<< "$out"
check "...a file the ready lane did not release is not listed" bash -c '! grep -q "hw/c.c" <<< "$1"' _ "$out"
check "...a draft lane's file is not listed" bash -c '! grep -q "hw/d.c" <<< "$1"' _ "$out"

# -------------------------------------------------- fleet.py
# The fleet's territory. Every row holds a file it has NOT released, so
# whether fleet.py asks for a release depends only on the PR's state:
#   readylane   ready, CI green, unit gone       -> release hw/r.c  (the one)
#   draftlane   draft, CI green, unit gone       -> no: still working
#   redlane     ready, CI red, unit gone         -> no: not finished
#   livelane    ready, CI green, unit ACTIVE     -> no: may still push
#   donelane    ready, CI green, unit gone, but everything released -> no
# The fold-ready PRs have no rows, so they are never release candidates:
#   9605 foldconf   CONFLICTING, labelled 5 min ago  -> FAIL at once
#   9606 foldred    CI red, labelled 2 h ago         -> FAIL, CI red
#   9607 foldnever  no check runs, labelled 2 h ago  -> FAIL, CI never ran
#   9608 foldfresh  CI red, labelled 10 min ago      -> not yet
{ printf 'wave = 1000000\n\n'; cat; } > "$BR/testing/territory.toml" <<'EOF'
[lane.readylane]
files = ["hw/r.c", "docs/lanes/readylane/**"]
[lane.draftlane]
files = ["hw/d.c"]
[lane.redlane]
files = ["hw/x.c"]
[lane.livelane]
files = ["hw/l.c"]
[lane.donelane]
files = ["hw/n.c"]
released = ["hw/n.c"]
EOF
cat > "$BR/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *list-units*hakux-lane*) echo "hakux-lane-livelane.service loaded active running claude" ;;
    *show*) printf 'Id=hakux-lane-livelane.service\nActiveEnterTimestampMonotonic=1000000\n' ;;
esac
exit 0
EOF
cat > "$BR/bin/gh" <<'EOF'
#!/usr/bin/env bash
# REST only, as fleet.py asks: the list, then one pull, its head's check runs,
# and (for a fold-ready PR) its label events.
p="$*"
case "$p" in
    *"/issues?"*) echo '[]' ;;
    *"/pulls?"*)  cat "$BR_FX/prs.json" ;;
    *"/pulls/"*)  n=${p##*/pulls/}; cat "$BR_FX/pull-${n%%[!0-9]*}.json" ;;
    *"/check-runs"*) s=${p##*/commits/}; cat "$BR_FX/runs-${s%%/*}.json" ;;
    *"/events"*)  n=${p##*/issues/}; cat "$BR_FX/events-${n%%/*}.json" 2>/dev/null || echo '[]' ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$BR/bin/"*
pr() {   # <n> <branch> <draft> <labels json>
    printf '{"number":%s,"head":{"ref":"%s"},"draft":%s,"labels":%s,"updated_at":"2026-09-26T00:00:00Z","title":"pr %s"}' "$1" "$2" "$3" "$4" "$1"
}
{ echo '['
  pr 9601 lane/readylane false '[]'; echo ,
  pr 9602 lane/draftlane true  '[]'; echo ,
  pr 9603 lane/redlane   false '[]'; echo ,
  pr 9604 lane/livelane  false '[]'; echo ,
  pr 9609 lane/donelane  false '[]'; echo ,
  pr 9605 lane/foldconf  false '[{"name":"fold-ready"}]'; echo ,
  pr 9606 lane/foldred   false '[{"name":"fold-ready"}]'; echo ,
  pr 9607 lane/foldnever false '[{"name":"fold-ready"}]'; echo ,
  pr 9608 lane/foldfresh false '[{"name":"fold-ready"}]'
  echo ']'; } > "$BR/fx/prs.json"
green='{"total_count":2,"check_runs":[{"name":"build","status":"completed","conclusion":"success"},{"name":"selftest","status":"completed","conclusion":"success"}]}'
red='{"total_count":2,"check_runs":[{"name":"build","status":"completed","conclusion":"success"},{"name":"selftest","status":"completed","conclusion":"failure"}]}'
for n in 9601 9602 9603 9604 9605 9606 9607 9608 9609; do
    m=true; [ "$n" = 9605 ] && m=false
    printf '{"number":%s,"mergeable":%s,"head":{"sha":"sha%s0000000"}}' "$n" "$m" "$n" > "$BR/fx/pull-$n.json"
done
for n in 9601 9602 9604 9605 9609; do printf '%s' "$green" > "$BR/fx/runs-sha${n}0000000.json"; done
for n in 9603 9606 9608; do printf '%s' "$red" > "$BR/fx/runs-sha${n}0000000.json"; done
echo '{"total_count":0,"check_runs":[]}' > "$BR/fx/runs-sha96070000000.json"
ago() { date -u -d "$1 ago" +%Y-%m-%dT%H:%M:%SZ; }
ev() { printf '[{"event":"labeled","label":{"name":"needs-audit-1"},"created_at":"%s"},{"event":"labeled","label":{"name":"fold-ready"},"created_at":"%s"}]' "$(ago '1 day')" "$(ago "$1")"; }
ev '5 minutes'  > "$BR/fx/events-9605.json"
ev '2 hours'    > "$BR/fx/events-9606.json"
ev '2 hours'    > "$BR/fx/events-9607.json"
ev '10 minutes' > "$BR/fx/events-9608.json"
out=$( cd "$BR/testing" && PATH="$BR/bin:$PATH" BR_FX="$BR/fx" HAKUX_BOARD_REF="" \
       HAKUX_REPO="example/hakux" FLEET_MERGEABLE_WAIT=0 python3 fleet.py 2>&1 )
check "fleet: a ready PR (CI green, unit gone) with unreleased files FAILs, naming the row and files" \
    grep -qx "FAIL: lane.readylane's PR #9601 is ready .*Add them to .released. on \[lane.readylane\].*: hw/r.c, docs/lanes/readylane/\*\*" <<< "$out"
check "...and it is the only release asked for" bash -c '[ "$(grep -c "^FAIL: lane\..*is ready" <<< "$1")" = 1 ]' _ "$out"
# The negatives read only the release lines: a ready PR still appears in
# READY, NOT FOLDED, which is a different question.
check "fleet: a draft PR's files are not released" bash -c '! grep -qE "lane.draftlane.s PR|^    draftlane " <<< "$1"' _ "$out"
check "fleet: a ready PR with red CI is not released" bash -c '! grep -qE "lane.redlane.s PR|^    redlane " <<< "$1"' _ "$out"
check "fleet: a ready PR whose unit is still active is not released" bash -c '! grep -qE "lane.livelane.s PR|^    livelane " <<< "$1"' _ "$out"
check "fleet: a row that already released everything is not asked again" bash -c '! grep -qE "lane.donelane.s PR|^    donelane " <<< "$1"' _ "$out"
check "fleet: a released file untaken is counted available" grep -q 'RELEASED AT READY -- available to the next lane (1)' <<< "$out"
check "fleet: a CONFLICTING fold-ready PR FAILs at once, naming who fixes it" \
    grep -q '^FAIL: fold-ready PR #9605 (lane.foldconf) is not folding.*CONFLICTING with master. Fix: host-tools/unjam_index.sh' <<< "$out"
check "fleet: a fold-ready PR with red CI for over 60 min FAILs with the check's name" \
    grep -q '^FAIL: fold-ready PR #9606 (lane.foldred) is not folding after 2.0h: CI red: selftest on sha9606000' <<< "$out"
check "fleet: a fold-ready PR whose CI never ran FAILs, saying so" \
    grep -q '^FAIL: fold-ready PR #9607 (lane.foldnever) is not folding after 2.0h: CI never ran' <<< "$out"
check "fleet: a fold-ready PR labelled 10 min ago is not flagged yet" bash -c '! grep -q "#9608" <<< "$1"' _ "$out"
