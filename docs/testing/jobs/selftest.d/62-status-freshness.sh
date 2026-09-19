# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# status.sh: the reader can tell when the page was written.
#
# WHY THIS EXISTS. status.sh PATCHes one comment in place, and GitHub renders a
# comment's `created_at`, never its `updated_at`, and never moves an edited
# comment. So the roll-up was correct and looked eleven hours old: #107 showed
# 02:28Z over a body written at 13:32Z, and a jammed fleet and a running fleet
# were indistinguishable on the only page built to tell them apart. The fix
# puts the clock in the issue BODY and the issue TITLE, which are what GitHub
# surfaces first, so the checks below are about those two PATCHes and about the
# page admitting a lapse in its own timer.
#
# Runs after 60-status.sh, which drives `status.sh --print` -- the print path
# exits before the GitHub work. This fragment drives the REAL path so the
# shimmed `gh` records the calls, and restores 60's shim and fixtures at the
# end for whatever is sourced next.

echo "== status.sh freshness"

# `grep -vq` is not a negation: it exits 0 as soon as ONE line fails to match,
# which every one of these files has. The assertions below that must find
# nothing go through this instead, in this shell, so they see the fixtures.
sf_nogrep() { ! grep -q "$@"; }

# A comment id the shim will confirm exists, so the PATCH-in-place branch runs
# rather than the create-if-missing one.
echo 5738613782 > "$HAKUX_WORK/status/comment-id"
SF_LOG="$T/gh-freshness.log"
HDR="$HAKUX_WORK/status/HEADER.md"

# ---- 1. a tick that follows a recent one: no lapse, and both PATCHes happen.
printf '%s\n' "$(( $(date +%s) - 60 ))" > "$HAKUX_WORK/status/last-run"
: > "$SF_LOG"; rm -f "$HDR"
sout=$(SELFTEST_GH_LOG="$SF_LOG" bash "$HERE/status.sh" 2>&1); src=$?
check "status.sh exits 0 on the GitHub path" [ "$src" -eq 0 ]
check "status.sh still PATCHes the one comment in place" \
    grep -q 'api -X PATCH repos/example/hakux/issues/comments/5738613782' "$SF_LOG"
check "status.sh PATCHes the issue BODY (renders above every comment)" \
    grep -q 'api -X PATCH repos/example/hakux/issues/107 -F body=' "$SF_LOG"
check "status.sh PATCHes the issue TITLE (all the issue list shows)" \
    grep -q 'api -X PATCH repos/example/hakux/issues/107 -f title=harness: live status' "$SF_LOG"
check "the title carries a UTC clock" \
    grep -qE -- '-f title=harness: live status -- [0-9]{2}:[0-9]{2}Z\+,' "$SF_LOG"
check "the title carries the lane and arm counts" \
    grep -qE -- '-f title=.*[0-9]+ lanes? running, [0-9]+ arms? on a device' "$SF_LOG"

check "the body header exists" [ -s "$HDR" ]
check "the body header leads with the minute it was written" \
    grep -qE '^\*\*Written [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2} UTC\.\*\*' "$HDR"
check "the body header states the deadline a reader judges staleness by" \
    grep -q 'Next roll-up due by' "$HDR"
check "the body header warns that a comment's rendered time is its posted time" \
    grep -q "posted\* time, not its edited time" "$HDR"
check "the body header links the roll-up comment" \
    grep -q 'issues/107#issuecomment-5738613782' "$HDR"
check "a tick one minute after the last one reports no lapse" \
    sf_nogrep 'roll-up lapsed' "$HDR"
check "status.sh stamps its own run for the next tick to compare against" \
    [ -s "$HAKUX_WORK/status/last-run" ]

# ---- 2. the page must say when the roll-up itself stopped.
#
# Two floors is the threshold, so back-date the stamp by five and assert the
# warning reaches BOTH surfaces: the roll-up a reader scrolls to and the header
# a reader lands on. A page that cannot report its own silence is this brief's
# defect one level up -- it shows the last good state and says nothing.
SF_OLD=$(( $(date +%s) - 5 * 1800 ))
printf '%s\n' "$SF_OLD" > "$HAKUX_WORK/status/last-run"
: > "$SF_LOG"
sout=$(SELFTEST_GH_LOG="$SF_LOG" bash "$HERE/status.sh" --print 2>&1)
check "a lapsed roll-up says so on the page" grep -q 'The roll-up lapsed for' <<< "$sout"
check "the lapse names how long it lasted" grep -qE 'lapsed for 2h [0-9]+m' <<< "$sout"
check "the lapse names the window that was not observed" \
    grep -q 'Nothing was observed across that window' <<< "$sout"
check "the page always states its next deadline" grep -q 'Next roll-up due by' <<< "$sout"
check "--print writes nothing to GitHub" sf_nogrep 'api -X PATCH' "$SF_LOG"
# `--print` is a dry run: it must not clear the lapse the next real tick owes
# the reader.
check "--print does not stamp a run" grep -qx "$SF_OLD" "$HAKUX_WORK/status/last-run"

: > "$SF_LOG"
SELFTEST_GH_LOG="$SF_LOG" bash "$HERE/status.sh" >/dev/null 2>&1
check "the lapse warning reaches the body header too" grep -q 'roll-up lapsed' "$HDR"
check "a real tick does stamp itself" sf_nogrep -x "$SF_OLD" "$HAKUX_WORK/status/last-run"

# ---- 3. an unchanged title is not re-PATCHed.
#
# A rename appends a permanent `renamed` row to the issue timeline; a PATCH to
# the SAME string appends nothing (both measured on this repo against PR #150,
# see docs/lanes/statusfresh/NOTES.md). status.sh runs at the end of every job
# tick, far more often than the clock in the title moves, so the common case
# must be silent. selftest.sh's shim answers `issue list` with the number
# alone; this one feeds a title back so the compare has something to compare.
cat > "$T/bin/gh" <<'GHEOF'
#!/usr/bin/env bash
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "auth status") exit 0 ;;
    "issue list") [[ "$args" == *"harness-status"* ]] && echo "107 ${SELFTEST_ISSUE_TITLE:-}"; exit 0 ;;
    "pr list") [[ "$args" == *"--jq"* ]] && exit 0; echo "[]"; exit 0 ;;
    "api "*|"api -X"*) [[ "$args" == *"--jq .id"* ]] && { echo 5; exit 0; }; exit 0 ;;
    *) exit 0 ;;
esac
GHEOF
chmod +x "$T/bin/gh"
# A day-long quantum so the two ticks below cannot straddle a boundary and make
# a real "unchanged" read as changed. The quantum's size is not what is under
# test here; whether an equal title is re-sent is.
: > "$SF_LOG"
STATUS_FLOOR_SECS=86400 SELFTEST_GH_LOG="$SF_LOG" bash "$HERE/status.sh" >/dev/null 2>&1
sf_want=$(grep -o -- '-f title=.*' "$SF_LOG" | head -1 | sed 's/^-f title=//; s/ --silent$//')
check "the first tick renames" [ -n "$sf_want" ]
: > "$SF_LOG"
STATUS_FLOOR_SECS=86400 SELFTEST_ISSUE_TITLE="$sf_want" SELFTEST_GH_LOG="$SF_LOG" \
    bash "$HERE/status.sh" >/dev/null 2>&1
check "a tick whose title is unchanged does not rename" sf_nogrep -- '-f title=' "$SF_LOG"
check "...but it still rewrites the body, which makes no timeline event" \
    grep -q 'api -X PATCH repos/example/hakux/issues/107 -F body=' "$SF_LOG"

# The issue number must survive the widened --jq. An empty issue list answers
# "null null", and `PATCH /issues/null` is the shape that writes the page
# nowhere while every call still returns 0.
check "the issue number is parsed out of the widened issue-list query" \
    grep -q 'issues/107 -F body=' "$SF_LOG"
check "no call is addressed to issue 'null'" sf_nogrep 'issues/null' "$SF_LOG"

# ---- restore selftest.sh's own shim and fixtures for any later fragment.
cat > "$T/bin/gh" <<'GHEOF'
#!/usr/bin/env bash
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "auth status") exit 0 ;;
    "pr list")
        if [[ "$args" == *"--head lane/selftest"* ]]; then
            [[ "$args" == *".[0].number"* ]] && { echo 102; exit 0; }
            echo "#102 draft"; exit 0
        fi
        [[ "$args" == *"--jq"* ]] && exit 0
        echo "[]"; exit 0 ;;
    "pr view") echo GREEN; exit 0 ;;
    "issue list") [[ "$args" == *"harness-status"* ]] && echo 107; exit 0 ;;
    "issue create") echo "https://github.com/example/hakux/issues/107"; exit 0 ;;
    "api "*|"api -X"*)
        [[ "$args" == *"--jq .id"* ]] && { echo 5; exit 0; }
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${SELFTEST_LABELS:-}; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
GHEOF
chmod +x "$T/bin/gh"
rm -f "$HAKUX_WORK/status/comment-id"
