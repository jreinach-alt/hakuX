# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# jobs/issue-sweep.sh, and the fifth gate it hands its findings to in
# board.sh. 77, beside 76-pr-sweep.sh, because it is the other half of the
# same brief; it shares no fixture with it.
#
# THE BOARD FILES ARE FAKED AS FILES, NOT AS A BRANCH. board_files.load()
# prefers `origin/board` and falls back to the working tree, so a fixture that
# wrote a tracker into the tree would be read only on a host with no board
# branch -- green here, blind on the owner's machine. HAKUX_BOARD_REF is the
# documented way to point it somewhere else, and "" disables the ref entirely.
# So the fixture builds a whole scratch docs/testing (the two toml files plus
# a symlink to the real board_files.py) and empties HAKUX_BOARD_REF, which
# makes the "working tree" it falls back to the fixture's own.
#
# EVERY CLASS RUNS TWICE: once with the defect and once with the single fact
# that makes it not one. A sweep that says "nothing stuck" against a broken
# board is the failure it exists to catch, and a sweep that says everything is
# stuck is the failure that gets it switched off.

echo "== issue-sweep.sh: the backlog states no actor reaches"
IS="$T/issue-sweep"; mkdir -p "$IS/bin" "$IS/jobs" "$IS/testing"
ln -sf "$(dirname "$HERE")/board_files.py" "$IS/testing/board_files.py"
for f in "$HERE"/*.sh "$HERE"/*.py "$HERE"/*.env; do
    [ -e "$f" ] && ln -sf "$f" "$IS/jobs/$(basename "$f")"
done
# issue-sweep.sh derives its docs/testing from `dirname $J`, so $IS/jobs must
# sit under $IS/testing for board_files.py to be importable from it.
rm -rf "$IS/testing/jobs"; mv "$IS/jobs" "$IS/testing/jobs"

cat > "$IS/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "${IS_LOG:?}"
case "$1 $2" in
    "auth status") exit 0 ;;
    "issue list") cat "$IS_DIR/issues.json" 2>/dev/null || echo "[]"; exit 0 ;;
    "pr list")    cat "$IS_DIR/pr-heads" 2>/dev/null; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$IS/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *list-units*) cat "$IS_DIR/active" 2>/dev/null; exit 0 ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$IS/bin/"*
export IS_DIR="$IS" IS_LOG="$IS/calls.log"
IS_WORK="$IS/work"

is_reset() { rm -rf "$IS_WORK"; mkdir -p "$IS_WORK/board"; : > "$IS_LOG"
             : > "$IS/active"; : > "$IS/pr-heads"
             printf 'wave = 1\nupdated_utc = "2026-09-19T00:00:00Z"\n' > "$IS/testing/territory.toml"
             printf '[issue]\n' > "$IS/testing/nv2a_issues.toml"; }
# HAKUX_BOARD_REF="" is what makes board_files read the fixture's own tree.
is() { ( export PATH="$IS/bin:$PATH" HAKUX_WORK="$IS_WORK" HAKUX_REPO_DIR="$REPO" \
                HAKUX_BOARD_REF=""
         bash "$IS/testing/jobs/issue-sweep.sh" "$@" 2>&1 ); }
is_in()      { grep -q -- "$1" <<< "$got"; }
is_notin()   { ! grep -q -- "$1" <<< "$got"; }
is_findings(){ [ -s "$IS_WORK/board/issue-sweep.findings" ]; }
is_no_findings() { [ ! -s "$IS_WORK/board/issue-sweep.findings" ]; }
is_handed()  { grep -qF -- "$1" "$IS_WORK/board/issue-sweep.findings"; }
# Negatives are functions, never `bash -c '! ...'`: a child shell sees only
# exported variables, so such a check is green against anything.

# <num> <labels csv> <quiet secs> ... one array of open issues
is_issues() {
    python3 - "$IS/issues.json" "$@" <<'PY'
import datetime, json, sys
out = sys.argv[1]
now = datetime.datetime.now(datetime.timezone.utc)
rows = []
for spec in sys.argv[2:]:
    num, labels, quiet = spec.split("|")
    rows.append({"number": int(num), "title": "issue %s" % num,
                 "labels": [{"name": l} for l in labels.split(",") if l],
                 "updatedAt": (now - datetime.timedelta(seconds=int(quiet)))
                              .strftime("%Y-%m-%dT%H:%M:%SZ")})
json.dump(rows, open(out, "w"))
PY
}
is_row() {   # <num> <toml body lines...>  -- appended to the fixture tracker
    { printf '\n[issue.%s]\ntitle = "issue %s"\n' "$1" "$1"; shift
      printf '%s\n' "$@"; } >> "$IS/testing/nv2a_issues.toml"
}
is_lane() {  # <name> <issues csv>
    printf '\n[lane.%s]\nissues = [%s]\nfiles = []\nstanding = false\nnote = "x"\n' \
        "$1" "$(echo "$2" | sed 's/[^,]*/"&"/g')" >> "$IS/testing/territory.toml"
}

# ----------------------------------------------------- the quiet control first
# THE CONTROL COMES FIRST ON PURPOSE. Every "is reported" check below is
# meaningless unless a healthy board is silent, and every "is not reported"
# check is meaningless unless something in the same run IS reported. This
# establishes the first half once.
is_reset
is_issues "10|lane:live|900"
is_row 10 'disposition = "defect"' 'status = "open"' 'dispatch_state = "available"'
echo "hakux-lane-live.service" > "$IS/active"
got=$(is list)
check "a healthy backlog produces no finding"    is_in "Nothing stuck"
is >/dev/null
check "and hands the board nothing"              is_no_findings

# ==================================================================== class 1
# AN OPEN ISSUE WITH NO TRACKER ROW. #164 was in this state on 2026-09-19 and
# it is not a private inconvenience: check_coverage.py counts it as a gap, so
# preflight went red for EVERY lane and every fold at once.
is_reset
is_issues "164|harness|900" "10|lane:live|900"
is_row 10 'disposition = "defect"' 'status = "open"' 'dispatch_state = "available"'
echo "hakux-lane-live.service" > "$IS/active"
got=$(is list)
check "an open issue with no tracker row is found"  is_in "NO tracker row"
check "and it is named"                             is_in "#164"
check "and the covered issue beside it is not"      is_notin "#10 "
check "and the cost is said, not implied"           is_in "every lane's push and every fold is red"

is_reset
is_issues "164|harness|900"
is_row 164 'disposition = "defect"' 'status = "open"' 'dispatch_state = "available"'
got=$(is list)
check "the same issue WITH a row is not a finding"  is_notin "NO tracker row"

# ==================================================================== class 2
# AN OWNER THAT NO LONGER EXISTS. A lane exists if it has an active unit, a
# territory row, or an open PR on lane/<name>. The `lane:` LABEL is the
# dangerous shape: board_filter's SKIP_PREFIX drops every issue carrying one,
# so a label for a dead lane makes the issue invisible to dispatch forever.
is_reset
is_issues "20|lane:ghosty|900"
is_row 20 'disposition = "defect"' 'status = "open"'
got=$(is list)
check "an issue labelled for a lane that does not exist is found" is_in "lane that no longer exists"
check "and the label is quoted"                     is_in 'label `lane:ghosty`'
check "and why it is invisible to dispatch is said" is_in "SKIP_PREFIX"

# THREE INDEPENDENT WAYS TO STILL EXIST, and any one of them is enough. Each
# is checked on its own, because a check that only ever exercises the unit
# would pass with the other two arms deleted.
# Asserted on the LABEL shape specifically, not on the section heading: with a
# territory row present the row shape has its own verdict, and a check that
# looked only for "lane that no longer exists" could not tell which of the
# three shapes had spoken.
is_ghost_label() { grep -q 'label `lane:ghosty`' <<< "$got"; }
is_no_ghost_label() { ! grep -q 'label `lane:ghosty`' <<< "$got"; }

is_reset; is_issues "20|lane:ghosty|900"; is_row 20 'status = "open"'
echo "hakux-lane-ghosty.service" > "$IS/active"
got=$(is list)
check "  a running unit means the lane exists"      is_no_ghost_label
check "    and nothing else about it is reported either" is_notin "lane that no longer exists"

# A TERRITORY ROW VOUCHES FOR THE LABEL AND NOT FOR ITSELF. The board still
# has an allocation, so the label is not orphaned -- but the row claiming a
# lane with no unit and no PR is exactly the other shape, and it is reported.
is_reset; is_issues "20|lane:ghosty|900"; is_row 20 'status = "open"'; is_lane ghosty 20
got=$(is list)
check "  a territory row means the LABEL is not orphaned" is_no_ghost_label
check "    while the row claiming a dead lane still is"   is_in 'territory row `lane.ghosty`'

is_reset; is_issues "20|lane:ghosty|900"; is_row 20 'status = "open"'
echo "lane/ghosty" > "$IS/pr-heads"
got=$(is list)
check "  an open PR on its branch means the lane exists" is_no_ghost_label
check "    and nothing else about it is reported either" is_notin "lane that no longer exists"

# The same defect through the territory row and through the blocker text.
# A CLAIM CANNOT BE THE EVIDENCE FOR ITSELF. The first version of this used
# one predicate for all three shapes, and that predicate counted "has a
# territory row" -- so a stale territory row proved the lane existed and the
# whole shape was unreportable. The row is the thing under suspicion here, so
# only the two facts that are not board files count: a unit, or an open PR.
is_reset; is_issues "21||900"; is_row 21 'status = "open"' 'blocked_on = "x"'; is_lane deadlane 21
got=$(is list)
check "a territory row held by a lane that is gone is found" is_in 'territory row `lane.deadlane`'

is_reset; is_issues "21||900"; is_row 21 'status = "open"'; is_lane deadlane 21
echo "hakux-lane-deadlane.service" > "$IS/active"
got=$(is list)
check "  and not when that lane's unit is running"  is_notin 'territory row `lane.deadlane`'

is_reset; is_issues "21||900"; is_row 21 'status = "open"'; is_lane deadlane 21
echo "lane/deadlane" > "$IS/pr-heads"
got=$(is list)
check "  nor when it still has an open PR"          is_notin 'territory row `lane.deadlane`'

# A `standing` row is a long-lived reservation and is not tied to a session,
# so "no unit" says nothing at all about it.
is_reset; is_issues "23||900"; is_row 23 'status = "open"'
printf '\n[lane.reserved]\nissues = ["23"]\nfiles = []\nstanding = true\nnote = "x"\n' >> "$IS/testing/territory.toml"
got=$(is list)
check "a standing territory row with no unit is not a ghost" is_notin 'territory row `lane.reserved`'

# A BLOCKER NAMING A DEAD LANE IS HISTORY, AND THE SWEEP MUST NOT REPORT IT.
#
# The brief asked for this shape. It was implemented, and then measured
# against the live board on 2026-09-19: it produced 11 of 16 findings and
# every one was the field doing its job -- #91's blocker reads "PR #102
# (lane.blitsafe, folded into master 3d072c6ea6) did NOT deliver a fix here",
# #13's records a tracker note written at lane.lows' request. A blocker NAMES
# the lane that established it, and that lane having finished is the normal
# case. The fixture below is the real shape, taken from #91's own wording; a
# sweep that reports it has re-acquired the defect the measurement removed.
# The row is otherwise complete -- a real disposition, a real status -- so the
# ONLY thing that could put it in the output is the blocker's wording. A row
# left half-filled would land in the untriaged class and the check would pass
# for a reason that has nothing to do with what it is testing.
is_reset; is_issues "22||900"
is_row 22 'disposition = "defect"' 'status = "open"' \
       'blocked_on = "PR #102 (lane.vanished, folded into master 3d072c6ea6) did NOT deliver a fix here; the mechanism needs a device diagnosis nobody has completed"'
got=$(is list)
check "a blocker naming a lane that has finished is history, not a finding" \
      is_notin 'lane that no longer exists'
check "  so the issue is not reported at all"       is_in "Nothing stuck"

# ==================================================================== class 3
# UNTRIAGED. `unclassified` is LEGAL and check_coverage.py accepts it -- the
# tracker's own header says a guess is worse than an admission of ignorance --
# so nothing else on this host ever asks about one.
is_reset
is_issues "30||900"
is_row 30 'disposition = "unclassified"' 'status = "open"' 'dispatch_state = "available"'
got=$(is list)
check "an unclassified tracker row is found"        is_in "untriaged"
check "and the sweep does not tell the board to invent a disposition" \
      is_in "Do not invent a disposition"

is_reset
is_issues "30||900"
is_row 30 'disposition = "defect"' 'status = "open"' 'dispatch_state = "available"'
got=$(is list)
check "a triaged row is not a finding"              is_notin "untriaged"

# A MISSING disposition is the same defect written a different way, and the
# check_coverage enum never sees it because an absent field is not a value.
is_reset
is_issues "31||900"
is_row 31 'status = "open"' 'dispatch_state = "available"'
got=$(is list)
check "a row with NO disposition at all is untriaged too" is_in "untriaged"

# ==================================================================== class 4
# THE ROW SAYS THE WORK IS DONE AND THE ISSUE IS OPEN. check_coverage.py
# checks the OPPOSITE direction only (tracker `open`, GitHub closed), because
# that is the one that causes re-dispatch.
is_reset
is_issues "40||900"
is_row 40 'disposition = "defect"' 'status = "fixed-verified"' 'status_note = "arm PRE-REGISTERED PASS"'
got=$(is list)
check "a fixed-verified row on an open issue is found" is_in "already says the work is done"
check "and the evidence in the row is carried across"  is_in "PRE-REGISTERED PASS"

is_reset
is_issues "41||900"
is_row 41 'disposition = "unmodelled-hardware"' 'status = "unmodellable"'
got=$(is list)
check "an unmodellable row on an open issue is found too" is_in "already says the work is done"

is_reset
is_issues "42||900"
is_row 42 'disposition = "defect"' 'status = "fixed-part"' 'status_note = "half of it landed"'
got=$(is list)
check "fixed-part is NOT closable and is not reported" is_notin "already says the work is done"

# ==================================================================== class 5
# AVAILABLE AND NOBODY PICKED IT UP.
is_reset
is_issues "50||900000"
is_row 50 'disposition = "defect"' 'status = "open"' 'dispatch_state = "available"'
got=$(is list)
check "an available issue nobody took for days is found" is_in "nobody has picked up"

is_reset
is_issues "50||900"
is_row 50 'disposition = "defect"' 'status = "open"' 'dispatch_state = "available"'
got=$(is list)
check "one available since this morning is the ordinary condition of a backlog" \
      is_notin "nobody has picked up"

is_reset
is_issues "50||900000"
is_row 50 'disposition = "defect"' 'status = "open"' 'dispatch_state = "available"'
is_lane onit 50
echo "hakux-lane-onit.service" > "$IS/active"
got=$(is list)
check "and one a live lane holds is not unpicked"   is_notin "nobody has picked up"

# ================================================== the handoff to the board
# IT WRITES NO BOARD FILE AND OPENS NO ISSUE. roles/lane.md forbids the first
# and the owner's standing rule forbids the second; both are bounded by what
# this script is ALLOWED to do, so both are checked rather than assumed.
is_reset
is_issues "60||900"
is_row 60 'disposition = "unclassified"' 'status = "open"'
before=$(md5sum "$IS/testing/nv2a_issues.toml" "$IS/testing/territory.toml")
is >/dev/null
check "the sweep writes findings for the board"     is_findings
check "and the findings name the class"             is_handed "untriaged"
check "it edits neither board file"                 test "$before" = "$(md5sum "$IS/testing/nv2a_issues.toml" "$IS/testing/territory.toml")"
is_no_issue_opened() { ! grep -q "issue create" "$IS_LOG"; }
check "and it opens no GitHub issue"                is_no_issue_opened
is_no_comment() { ! grep -qE "^gh (issue|pr) comment" "$IS_LOG"; }
check "and comments on nothing: the board decides, not this script" is_no_comment

# THE TRIGGER IS THE FILE, so a run that finds nothing must REMOVE it. A
# findings file that outlives its findings is a gate that fires forever.
is_reset
is_issues "61|lane:live|900"
is_row 61 'disposition = "defect"' 'status = "open"' 'dispatch_state = "available"'
echo "hakux-lane-live.service" > "$IS/active"
echo "stale findings from a previous run" > "$IS_WORK/board/issue-sweep.findings"
is >/dev/null
check "a clean sweep removes the previous run's findings" is_no_findings

# A BLIND TICK ESTABLISHES NOTHING, so it must not discharge the last good
# findings either. Deleting them on a gh outage would lose a set nobody read.
is_reset
is_issues "62||900"
is_row 62 'disposition = "unclassified"' 'status = "open"'
echo "real findings nobody has read yet" > "$IS_WORK/board/issue-sweep.findings"
rm -f "$IS/testing/nv2a_issues.toml"          # the board files unreadable
got=$(is)
check "a tick that cannot read the board says so"   is_in "could not be read"
check "and leaves the unread findings alone"        is_handed "nobody has read yet"

# ============================================ board.sh reads them, once
# THE KEY IS A CONTENT HASH AND NOT A TIMESTAMP. The sweep rewrites the same
# findings for as long as they hold, twice a day, and board.sh ticks every
# twenty minutes; a gate that merely asked "does the file exist?" would wake a
# model tick every twenty minutes for as long as one row stayed untriaged.
BG="$T/board-gate"; mkdir -p "$BG/board" "$BG/logs/board"
bg() { ( export HAKUX_WORK="$BG" HAKUX_REPO_DIR="$REPO"
         bash "$HERE/board.sh" gate 2>&1 ); }
rm -f "$BG/board/issue-sweep.findings" "$BG/board/issue-sweep.seen"
got=$(bg)
check "no findings file is no trigger"              is_notin "issue-sweep findings"

printf '### 1 open issue(s) with NO tracker row\n\n- #164 x\n' > "$BG/board/issue-sweep.findings"
got=$(bg)
check "a fresh findings file wakes the board's gate" is_in "issue-sweep findings not yet seen"
check "and the gate shows the class, not the whole file" is_in "NO tracker row"

# `gate` IS A PROBE AND MARKS NOTHING SEEN -- a person runs it to ask why a
# tick did not wake, and the selftest runs it too. If it discharged the
# findings they would be gone before any tick read them.
check "the probe marks nothing seen"                test ! -f "$BG/board/issue-sweep.seen"

sha=$(sha256sum "$BG/board/issue-sweep.findings" | cut -d' ' -f1)
printf '%s\n' "$sha" > "$BG/board/issue-sweep.seen"
got=$(bg)
check "the same findings do not wake a second tick" is_notin "issue-sweep findings not yet seen"

printf '### 1 open issue(s) with NO tracker row\n\n- #164 x\n- #165 y\n' > "$BG/board/issue-sweep.findings"
got=$(bg)
check "a CHANGED set wakes it again"                is_in "issue-sweep findings not yet seen"

# AND IT IS MARKED SEEN ONLY ON A TICK THAT RAN. Checked by reading the code
# rather than by starting a model session: the mark is guarded on rc, and the
# failing branch says out loud that it left them unread.
check "board.sh marks the findings seen only when the tick returned 0" \
      grep -q 'if \[ -n "\$SWEEP_HASH" \] && \[ "\$rc" = 0 \]' "$HERE/board.sh"
check "and says so when it did not"                 grep -q "leaving them unread for the next tick" "$HERE/board.sh"
check "the brief carries the findings to the model" grep -q "issue sweep -- backlog states that no other actor reaches" "$HERE/board.sh"
check "and tells it this set is offered once"       grep -q "You are seeing this set ONCE" "$HERE/board.sh"
