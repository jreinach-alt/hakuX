# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# status.sh: the lane table knows every lane on the board, not only the ones
# with a live unit.
#
# WHY THIS EXISTS. "Lanes running" listed active hakux-lane-* units and nothing
# else, so a lane that had stopped with a draft PR and nothing on a device --
# idle, with nothing that would ever wake it -- was on no page at all, and
# neither were lane.xbox and lane.remote, which have no unit. The owner found
# each by hand (2026-09-26). The table now starts from territory.toml, and the
# idle state is lifted into a warning and into the issue body.
#
# UPDATED FOR #432 (lane.dash432, 2026-09-26). The table became "what each
# one is doing": one state per lane from a fixed vocabulary, derived from
# facts. What changed here, and why:
#   - "IDLE, NO WORK" is now "stranded", the vocabulary's only lane alarm.
#   - blockx (an open issue whose blocked_on says "needs a silicon capture",
#     nothing in flight) was "blocked"; the board's free text is no longer
#     parsed into a state, so it is stranded, with the text kept as a note.
#   - jobx (standing, no issues, no PR) is a job's row: the Automation box.
#   - lane.xbox and lane.remote are rows of the table, not bullets below it.
#   - the index head gains a full stop: an excerpt that ends in no sentence
#     stop is never shown, since it may end mid-word.
#   - the host ops tick is a row of the Automation box.
#
# Runs after 62-status-freshness.sh, whose gh shim (a title for `issue list`,
# `[]` for `pr list`) is still on PATH: no lane here has a PR.

echo "== status.sh lane table"
SL_BOARD="$T/status-board"; mkdir -p "$SL_BOARD"
sl_old=$(date -u -d '1 hour ago' +%FT%TZ); sl_ancient=$(date -u -d '4 days ago' +%FT%TZ)
cat > "$SL_BOARD/territory.toml" <<EOF
wave = 1
[lane.idlex]
issues = ["901"]
files = []
[lane.busyx]
issues = ["902"]
files = []
[lane.blockx]
issues = ["903"]
files = []
[lane.jobx]
issues = []
standing = true
files = []
[lane.xbox]
issues = []
standing = true
files = []
[lane.remote]
issues = []
files = []
[retired.recentx]
issues = []
files = []
retired_utc = "$sl_old"
[retired.ancientx]
issues = []
files = []
retired_utc = "$sl_ancient"
EOF
cat > "$SL_BOARD/nv2a_issues.toml" <<'EOF'
[issue.902]
title = "t"
status = "open"
blocked_on = ""
[issue.903]
title = "t"
status = "open"
blocked_on = "needs a silicon capture"
EOF
# A device request from busyx's arm: the requester shape arms.sh writes.
SL_REQ="$DISPATCH_DIR/queue/zz-selftest-busyx.req"
printf '{"id": "1-arms-busyx-fix-1", "requester": "arms-busyx-fix"}\n' > "$SL_REQ"
cp "$HAKUX_WORK/logs/lane/index.tsv" "$T/status-lanes-index.bak" 2>/dev/null
printf '%s\tlane-idlex\tclaude-opus-5\t3\t60\t0\tok\tidlex.json\tidlex said its last word.\n' "$(date -u -d "30 minutes ago" +%FT%TZ)" >> "$HAKUX_WORK/logs/lane/index.tsv"
mkdir -p "$HAKUX_WORK/logs/hostops"
printf '=== 20260926T040800Z.json rc=0 success\nQuiet tick: the selftest fixture.\n' > "$HAKUX_WORK/logs/hostops/digest.log"

sout=$(STATUS_BOARD_DIR="$SL_BOARD" bash "$HERE/status.sh" --print 2>&1); src=$?
check "status.sh exits 0 with the lane table" [ "$src" -eq 0 ]
check "the page has the lane table" grep -q '^### Lanes: what each one is doing' <<< "$sout"
check "the page keeps the running-units table" grep -q '^### Lanes running' <<< "$sout"
check "an inactive lane with no PR and no request is stranded" \
    grep -qF '| idlex | local lane | #901 | stranded |' <<< "$sout"
check "...with its last session's words" grep -qF 'idlex said its last word.' <<< "$sout"
check "...and named in the warning above the table" grep -qF '**Stranded:** lane.blockx, lane.idlex.' <<< "$sout"
check "a lane with a queued arm reads as waiting on a device, not stranded" \
    grep -qF '| busyx | local lane | #902 t | waiting on device | 1 run queued, first at position' <<< "$sout"
check "a blocked_on in words, with nothing in flight, is not a state: stranded" \
    grep -qF '| blockx | local lane | #903 t | stranded |' <<< "$sout"
check "...and the board's words are not an alarm of their own" sf_nogrep -F 'blocked: #903' <<< "$sout"
check "a standing row with no issue is a job, in the Automation box" \
    grep -qF '| jobx | not recorded | no timer | a standing board row' <<< "$sout"
check "...not a lane" sf_nogrep -F '| jobx | local lane' <<< "$sout"
check "a lane retired within the day is under Finished today" grep -qF '| recentx | (harness work) |' <<< "$sout"
check "a lane retired days ago is not" sf_nogrep -F '| ancientx |' <<< "$sout"
check "lane.xbox is a row of the lane table" grep -qF '| xbox | console session |' <<< "$sout"
check "lane.remote is a row of the lane table" grep -qF '| remote | cloud session |' <<< "$sout"
check "the console meter degrades when the plug tool is absent" grep -qF 'console meter: not available' <<< "$sout"
sl_want=$(. "$HERE/localtime.sh"; local_hm 2026-09-26T04:08:00Z)
check "the host ops tick is an Automation row, at its time in the display zone ($sl_want)" \
    grep -qF "| hostops | $sl_want |" <<< "$sout"
check "...with its digest's first sentence" grep -qF 'Quiet tick: the selftest fixture.' <<< "$sout"
check "the stranded list is left for the body header" grep -qx 'blockx, idlex' "$HAKUX_WORK/status/idle-lanes"

# The real path: the idle lane reaches the issue BODY, the first thing a phone shows.
SL_LOG="$T/gh-lanes.log"; : > "$SL_LOG"
STATUS_BOARD_DIR="$SL_BOARD" SELFTEST_GH_LOG="$SL_LOG" bash "$HERE/status.sh" >/dev/null 2>&1
check "the body header names the stranded lanes" grep -qF '**Stranded:** blockx, idlex' "$HAKUX_WORK/status/HEADER.md"

# A PR list that could not be read is not "no PR": a gh failure must not flag
# every lane idle in the issue body.
mkdir -p "$T/status-ghfail"
printf '#!/usr/bin/env bash\n[ "$1 $2" = "pr list" ] && exit 1\n[ "$1 $2" = "auth status" ] && exit 0\nexit 0\n' > "$T/status-ghfail/gh"
chmod +x "$T/status-ghfail/gh"
sout=$(PATH="$T/status-ghfail:$PATH" STATUS_BOARD_DIR="$SL_BOARD" bash "$HERE/status.sh" --print 2>&1)
check "a failed PR list strands no lane" sf_nogrep -F '| stranded |' <<< "$sout"
check "...it says the PR state is unknown" grep -qF '| idlex | local lane | #901 | unknown (the PR list could not be read) |' <<< "$sout"

# No board to read: the page still renders and says so.
mkdir -p "$T/status-noboard"
sout=$(STATUS_BOARD_DIR="$T/status-noboard" bash "$HERE/status.sh" --print 2>&1); src=$?
check "a missing territory.toml does not fail the page" [ "$src" -eq 0 ]
check "...it says the board could not be read" grep -q 'territory.toml on origin/board could not be read' <<< "$sout"
check "...and the rest still renders" grep -q '^### Window budget' <<< "$sout"
check "...and an empty idle list clears the body's line" bash -c '! test -s "$1"' _ "$HAKUX_WORK/status/idle-lanes"

rm -f "$SL_REQ" "$HAKUX_WORK/status/idle-lanes"
rm -rf "$HAKUX_WORK/logs/hostops"
[ -f "$T/status-lanes-index.bak" ] && mv "$T/status-lanes-index.bak" "$HAKUX_WORK/logs/lane/index.tsv"
