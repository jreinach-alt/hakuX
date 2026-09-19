# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, $DISPATCH_DIR, the shims on PATH, ok/bad/check. Not executable, no
# shebang, no exit -- `fail` is shared and is the run's verdict.
#
# THE DELIVERY CHANNEL (#154). Routing a lane its work used to be an append to
# `$DISPATCH_DIR/deliveries/<lane>.md`, and the recipient -- a cloud session --
# cannot open a file on this host's disk (ORCHESTRATION-DESIGN.md §5). It is
# now a `[job.deliver] lane.<name>` comment.
#
# 66 is a free number and nothing more: this fragment has NO ordering
# requirement in either direction, which is the property worth stating. It
# builds its own dispatch directory, its own gh shim, its own board and its own
# sweep directory, reads nothing another fragment wrote, and leaves nothing in
# the shared $DISPATCH_DIR -- 96-fleet-registry.sh asserts on the exact file
# count there, and a fragment that drops fixtures in a shared directory for a
# later one to trip over is the coupling the selftest split was done to remove.
#
# SELFTEST_DELIVER_SRC exists so this whole section can be pointed at the OLD
# scripts and seen to fail, rather than being reasoned about. It must contain
# `comment_sweep.sh`, `watch_remote_lane.sh`, `check_coverage.py`,
# `board_files.py` and `jobs/deliver.sh` -- extract them with
# `git show origin/master:docs/testing/<f>`.
#
# WHAT THIS FRAGMENT CANNOT SEE, so that a green run is not read as more than
# it is: the gh shim answers the `--jq` expressions with real `jq`, which is
# close to gh's built-in gojq but not identical, and the positive control
# immediately below fails loudly if jq is absent rather than letting every
# assertion pass on an empty feed. It does not exercise GitHub's pagination,
# its `since` filter, or the rate limiter.

echo "== the delivery channel: a comment the recipient can read"

DSRC="${SELFTEST_DELIVER_SRC:-$TESTING}"
DD="$T/deliver"; DBIN="$DD/bin"; DDISP="$DD/dispatch"; DSWEEP="$DD/sweep"
DBOARD="$DD/board"
mkdir -p "$DBIN" "$DDISP" "$DSWEEP" "$DBOARD" "$DD/posted"
export DELIVER_GH_LOG="$DD/gh.log"; : > "$DELIVER_GH_LOG"

# ------------------------------------------------------------------ the feed
#
# One array, the shape `GET /repos/{o}/{r}/issues/comments` really returns.
# Note #45 is a PULL REQUEST thread and #62 an issue: the endpoint does not
# distinguish them, which is the entire reason it replaced an enumeration of
# open issues that could only ever see one of the two.
cat > "$DD/feed.json" <<'EOF'
[
 {"created_at":"2026-09-19T08:00:00Z","issue_url":"https://api.github.com/repos/example/hakux/issues/60",
  "html_url":"https://github.com/example/hakux/issues/60#issuecomment-0","user":{"login":"owner"},
  "body":"[job.deliver] lane.remote\n\nAn EARLIER delivery to the same lane, on a different thread, placed FIRST on purpose. This array is deliberately NOT in the order the live endpoint returns: the URL asks for newest-first, and if somebody drops that parameter GitHub's default for this endpoint is oldest-first. A scan that took the first match it saw would record this one and name #60."},
 {"created_at":"2026-09-19T09:00:00Z","issue_url":"https://api.github.com/repos/example/hakux/issues/62",
  "html_url":"https://github.com/example/hakux/issues/62#issuecomment-1","user":{"login":"owner"},
  "body":"[job.deliver] lane.remote\n\nTake #62 next; the blocker is refuted."},
 {"created_at":"2026-09-19T08:30:00Z","issue_url":"https://api.github.com/repos/example/hakux/issues/71",
  "html_url":"https://github.com/example/hakux/issues/71#issuecomment-0b","user":{"login":"owner"},
  "body":"[job.deliver] lane.remote\n\nA third delivery to the same lane, older than #62's and placed AFTER it. THE THREE ROWS ARE THE FIXTURE: one older BEFORE the newest and one older AFTER it, so the newest is neither first nor last. A reader that takes the first match it sees records #60; one that lets the last row overwrite records #71; only one that compares the timestamps records #62. Both of those shapes existed in this change and each is now a mutant that trips."},
 {"created_at":"2026-09-19T10:00:00Z","issue_url":"https://api.github.com/repos/example/hakux/issues/62",
  "html_url":"https://github.com/example/hakux/issues/62#issuecomment-2","user":{"login":"bot"},
  "body":"[lane.remote] triaged in full on this thread; needs a direction."},
 {"created_at":"2026-09-19T11:00:00Z","issue_url":"https://api.github.com/repos/example/hakux/issues/45",
  "html_url":"https://github.com/example/hakux/pull/45#issuecomment-3","user":{"login":"owner"},
  "body":"Please rerun the arm before folding this."},
 {"created_at":"2026-09-19T11:30:00Z","issue_url":"https://api.github.com/repos/example/hakux/issues/31",
  "html_url":"https://github.com/example/hakux/issues/31#issuecomment-4","user":{"login":"bot"},
  "body":"[job.board] Not dispatching. The capacity gate was blind this tick."},
 {"created_at":"2026-09-19T11:45:00Z","issue_url":"https://api.github.com/repos/example/hakux/issues/31",
  "html_url":"https://github.com/example/hakux/issues/31#issuecomment-5","user":{"login":"bot"},
  "body":"For the record the old marker was\n[job.deliver] lane.ghost\nand it is quoted here, not sent."}
]
EOF

# --------------------------------------------------------------- the gh shim
#
# It answers `api` calls by running the caller's own --jq over a canned body,
# so the jq expressions in deliver.sh and comment_sweep.sh are executed rather
# than assumed. Every call is logged; every POST body is kept.
cat > "$DBIN/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${DELIVER_GH_LOG:?}"
[ "$1 $2" = "auth status" ] && exit 0
if [ "$1" = "issue" ] && [ "$2" = "list" ]; then
    case "$*" in
        *harness-status*) echo 107 ;;                       # --jq .[0].number
        *) echo '[{"number":1,"title":"the only issue"}]' ;;  # a board fixture
    esac
    exit 0
fi
[ "$1" = "api" ] || exit 0
url=""; jqx=""; method=GET; input=""; bodyfile=""
shift
while [ $# -gt 0 ]; do
    case "$1" in
        -X) method="$2"; shift 2 ;;
        --jq) jqx="$2"; shift 2 ;;
        --input) input="$2"; shift 2 ;;
        -F) case "$2" in body=@*) bodyfile="${2#body=@}" ;; esac; shift 2 ;;
        --paginate|--silent) shift ;;
        -*) shift ;;
        *) [ -z "$url" ] && url="$1"; shift ;;
    esac
done
emit() {   # <json>
    if [ -n "$jqx" ]; then printf '%s' "$1" | jq -r "$jqx"; else printf '%s\n' "$1"; fi
}
case "$url" in
    *"issues/comments?"*)   emit "$(cat "${DELIVER_FEED:?}")" ;;
    *"issues/comments/"*)   # the "does this comment still exist" probe, then PATCH
        [ "$method" = PATCH ] && { cp "${bodyfile:-/dev/null}" "$DELIVER_POSTS/patched.md" 2>/dev/null; exit 0; }
        exit "${DELIVER_CID_EXISTS:-0}" ;;
    *"/comments")           # POST a new comment on a thread
        n="${url##*/issues/}"; n="${n%%/*}"
        if [ -n "$input" ]; then
            python3 -c 'import json,sys;sys.stdout.write(json.load(open(sys.argv[1]))["body"])' \
                "$input" > "$DELIVER_POSTS/body-$n.md"
        elif [ -n "$bodyfile" ]; then
            cp "$bodyfile" "$DELIVER_POSTS/body-$n.md"
        fi
        emit "{\"id\":9001,\"created_at\":\"${DELIVER_CREATED:-2026-09-19T12:00:00Z}\",\"html_url\":\"https://github.com/example/hakux/issues/$n#issuecomment-9001\"}" ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$DBIN/gh"
export DELIVER_FEED="$DD/feed.json" DELIVER_POSTS="$DD/posted"

dgh() { env PATH="$DBIN:$PATH" GH_REPO="example/hakux" DISPATCH_DIR="$DDISP" "$@"; }

# THE POSITIVE CONTROL, FIRST. Everything below reads an empty feed as "no
# deliveries", which is indistinguishable from a working shim on a quiet
# repository. Establish that the instrument can see the thing before any check
# is allowed to conclude from its absence.
probe="$(dgh gh api "repos/example/hakux/issues/comments?since=x" --jq '.[] | .created_at' 2>&1)"
check "the shim's feed is readable at all -- if this fails, jq is missing and every check below is blind" \
    grep -q "2026-09-19T09:00:00Z" <<< "$probe"

# --------------------------------------------------------------------- scan
out="$(dgh bash "$DSRC/jobs/deliver.sh" scan --since 2026-09-01T00:00:00Z 2>&1)"
check "deliver.sh scan folds the feed into the delivery cache" \
    test -f "$DDISP/delivery-cache/remote.json"
jget() { python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' "$1" "$2" 2>/dev/null; }
check "the recorded brief time is GITHUB'S created_at for the delivery comment" \
    test "$(jget "$DDISP/delivery-cache/remote.json" delivered)" = "2026-09-19T09:00:00Z"
# The feed carries TWO deliveries to this lane, 09:00 on #62 and 08:00 on #60,
# with the older one placed last. Naming #62 is the assertion that the scan
# compares timestamps rather than trusting the `sort=` parameter in a URL two
# functions away -- a coupling that survives right up until somebody edits the
# URL, and that nothing else here would notice.
check "...and it remembers which thread the NEWEST one was routed on, not the last row read" \
    test "$(jget "$DDISP/delivery-cache/remote.json" delivered_thread)" = "62"
check "the lane's own report is recorded separately from what was routed to it" \
    test "$(jget "$DDISP/delivery-cache/remote.json" reported)" = "2026-09-19T10:00:00Z"
# THE FALSIFIER FOR THE MARKER ITSELF. A comment that QUOTES the tag mid-body
# is prose about a delivery, not one. This project has already had a check pass
# against the wrong file because the file's own comment contained the words it
# was grepping for.
check "a comment merely QUOTING the marker does not manufacture a delivery" \
    bash -c '! test -e "$1/delivery-cache/ghost.json"' _ "$DDISP"

# --------------------------------------------------------------------- send
out="$(dgh bash "$DSRC/jobs/deliver.sh" send remote 62 -b 'Take #34; the GL arm is the only one that can see it.' 2>&1)"
check "deliver.sh send posts a comment" test -f "$DD/posted/body-62.md"
check "...whose FIRST LINE is the addressable marker, so the lane can find its own" \
    bash -c 'head -1 "$1" | grep -qx "\[job.deliver\] lane.remote"' _ "$DD/posted/body-62.md"
check "...carrying the body it was given" \
    grep -q "the GL arm is the only one that can see it" "$DD/posted/body-62.md"
check "...and saying, in the comment itself, that the old file is retired" \
    grep -q "deliveries/remote.md\` is retired" "$DD/posted/body-62.md"
check "the stamp advances to the created_at the SERVER returned for that comment" \
    test "$(jget "$DDISP/delivery-cache/remote.json" delivered)" = "2026-09-19T12:00:00Z"

# MONOTONIC, and this is not decoration: `scan` runs on a one-hour window every
# hour, and a window that happens to contain an older delivery than the cache
# already holds must not make a briefed lane read as stale.
DELIVER_CREATED=2020-01-01T00:00:00Z dgh bash "$DSRC/jobs/deliver.sh" send remote 62 -b 'older' >/dev/null 2>&1
check "an OLDER delivery never moves the stamp backwards" \
    test "$(jget "$DDISP/delivery-cache/remote.json" delivered)" = "2026-09-19T12:00:00Z"

# A delivery with no body routes nothing, and must not be recorded as one: a
# stamp that moves on an empty comment is the `lastbrief` defect with a new
# storage medium.
: > "$DELIVER_GH_LOG"
dgh bash "$DSRC/jobs/deliver.sh" send remote 62 >/dev/null 2>&1
check "an empty delivery is refused before anything is posted" \
    bash -c '! grep -q "issues/62/comments" "$1"' _ "$DELIVER_GH_LOG"

# -------------------------------------------------------------------- inbox
out="$(dgh bash "$DSRC/jobs/deliver.sh" inbox remote 2>&1)"
check "deliver.sh inbox reads the channel back from GitHub, where the lane can reach it" \
    grep -q "the blocker is refuted" <<< "$out"

# ------------------------------------------------------ the UNBRIEFED source
#
# THE DISCRIMINATING FIXTURE. `deliveries/alpha.md` is written FRESH here, with
# an mtime of now, and the cache says the last delivery comment was ten hours
# ago. The old check_coverage.py read the file's mtime and reported the lane
# briefed; the truth is that nothing has been routed to it since yesterday, and
# nothing ever could be, because the file is on a disk the lane cannot see.
cp "$DSRC/check_coverage.py" "$DSRC/board_files.py" "$DBOARD/"
printf '[lane.alpha]\nfiles = []\nissues = [1]\n\n[free]\nnote = "x"\n' > "$DBOARD/territory.toml"
printf '[issue.1]\ntitle = "t"\nstatus = "open"\nstatus_note = "n"\nblocked_on = ""\n' > "$DBOARD/nv2a_issues.toml"
mkdir -p "$DDISP/deliveries"
printf 'a fresh append that reaches nobody\n' > "$DDISP/deliveries/alpha.md"
brief_cache() {   # <hours since the delivery> <hours since the last scan>
    python3 - "$DDISP/delivery-cache/alpha.json" "$1" "$2" <<'PY'
import datetime, json, os, sys
os.makedirs(os.path.dirname(sys.argv[1]), exist_ok=True)
now = datetime.datetime.now(datetime.timezone.utc)
iso = lambda h: (now - datetime.timedelta(hours=float(h))).strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump({"lane": "alpha", "delivered": iso(sys.argv[2]), "delivered_thread": 1,
           "delivered_url": "https://example.invalid/1", "scanned": iso(sys.argv[3])},
          open(sys.argv[1], "w"))
PY
}
cov_d() { env PATH="$DBIN:$PATH" HAKUX_BOARD_REF= DISPATCH_DIR="$DDISP" \
              python3 "$DBOARD/check_coverage.py" 2>&1; }

brief_cache 10 0; out="$(cov_d)"
check "a lane with a fresh deliveries/<lane>.md and a TEN-HOUR-OLD delivery comment reads UNBRIEFED" \
    grep -q "UNBRIEFED: alpha 1 unblocked issue(s), last brief 10.0h" <<< "$out"
check "...and the note names the comment it was derived from, not a file on this host" \
    grep -q "the newest \[job.deliver\] comment, on #1" <<< "$out"
# BOTH DIRECTIONS, or "reports UNBRIEFED" is satisfied by a check that always
# does. The same fresh file is still sitting there; only the comment moved.
brief_cache 0.3 0; out="$(cov_d)"
check "a delivery comment twenty minutes old silences it" \
    bash -c '! grep -q UNBRIEFED <<< "$1"' _ "$out"
check "...on the SUMMARY line, which is the only line the idle watchdog prints" \
    grep -q "^coverage ok (1 open:" <<< "$out"
# A CACHE NOBODY IS REFRESHING STILL PRINTS AN HOURS FIGURE, and that figure
# is a lower bound on the truth rather than the truth: a delivery posted by
# hand an hour ago is invisible until the next sweep folds it in. `scanned` is
# written by every cache write, so it can never be older than `delivered` --
# which means the honest fixture is a stale scan UNDER a stale delivery, and
# the note has to say which of the two you are looking at.
brief_cache 10 9; out="$(cov_d)"
check "a delivery cache nobody has refreshed for 9h says so rather than reading fresh" \
    grep -q "cache last refreshed 9.0h ago" <<< "$out"
rm -f "$DDISP/delivery-cache/alpha.json"; out="$(cov_d)"
check "no delivery on record reads 'never', not 'a long time ago'" \
    grep -q "last brief never" <<< "$out"

# --------------------------------------------------------------- the sweep
#
# THE ENDPOINT WAS WRONG, NOT THE PAGE -- watch_remote_lane.sh's own words, and
# the reason this check exists. The gh shim's `issue list` returns exactly one
# issue, #1, and NOT #45. A sweep that enumerates issues therefore cannot see
# the owner's comment on PR #45 at all; the one that asks for every comment in
# the repository sees it without knowing #45 exists.
: > "$DELIVER_GH_LOG"
out="$(env PATH="$DBIN:$PATH" GH_REPO="example/hakux" DISPATCH_DIR="$DDISP" \
       HAKUX_SWEEP_DIR="$DSWEEP" bash "$DSRC/comment_sweep.sh" 2>&1)"
rep="$DSWEEP/unread.md"
check "the sweep wrote a report" test -s "$rep"
check "a comment on a PULL REQUEST thread is swept, though no issue list names it" \
    grep -q "^### #45" "$rep"
check "...and its text survives into the report" \
    grep -q "rerun the arm before folding" "$rep"
check "a job's own output is filtered, and the report SAYS how many it dropped" \
    grep -qE "[0-9]+ written by a job" "$rep"
check "the report carries the routed-in/reported-out table the watcher was for" \
    grep -q "last report from it" "$rep"
# Same order-independence as the scan, in the other renderer: the feed holds two
# deliveries to lane.remote and the older one is first.
check "...naming the NEWEST delivery to a lane, not whichever row came last" \
    grep -qE '^\| .lane.remote. \| \[2026-09-19T09:00:00Z\]' "$rep"
# THE DESTINATION. A sweep that writes a file nobody opens is the defect, not
# the fix: this one ends at the single `harness-status` comment the owner reads
# from a phone.
check "the report is POSTED, not just written to this host's disk" \
    grep -q "issues/107/comments" "$DELIVER_GH_LOG"
check "...and the run says where it went" grep -q "created #107 comment 9001" <<< "$out"
: > "$DELIVER_GH_LOG"
out="$(env PATH="$DBIN:$PATH" GH_REPO="example/hakux" DISPATCH_DIR="$DDISP" \
       HAKUX_SWEEP_DIR="$DSWEEP" bash "$DSRC/comment_sweep.sh" 2>&1)"
check "the second sweep EDITS that comment instead of posting a new one each hour" \
    grep -q "PATCH" "$DELIVER_GH_LOG"
check "...and does not post a second" \
    bash -c '! grep -q "POST repos/example/hakux/issues/107/comments" "$1"' _ "$DELIVER_GH_LOG"
check "the sweep refreshed the delivery cache on the way past" \
    test -f "$DDISP/delivery-cache/remote.json"

# A COMMENT HAS A CEILING AND THE PAGE DOES NOT. The first live run produced 44
# KB from a 24-hour window against GitHub's 65536-character limit. A POST that
# fails for length loses the whole report while every gate here still says
# "swept". POST_MAX is the same knob the script reads, turned down until the
# fixture's own report is over it, which is the mutant: at the real 58000 the
# body below is a few kilobytes and this check fails, so it is measuring the
# truncation and not the fixture.
: > "$DELIVER_GH_LOG"; rm -f "$DSWEEP/comment-id"
env PATH="$DBIN:$PATH" GH_REPO="example/hakux" DISPATCH_DIR="$DDISP" \
    HAKUX_SWEEP_DIR="$DSWEEP" POST_MAX=500 bash "$DSRC/comment_sweep.sh" >/dev/null 2>&1
check "an over-long report is truncated before it is posted" \
    bash -c 'test "$(wc -c < "$1")" -lt "$(wc -c < "$2")"' _ "$DD/posted/body-107.md" "$DSWEEP/unread.md"
check "...and SAYS it was truncated, because a page that stops at the limit reads like a quiet day" \
    grep -q "Truncated to fit one comment" "$DD/posted/body-107.md"
check "...and names where the whole page is" \
    grep -q "unread.md" "$DD/posted/body-107.md"
check "the on-disk page is NOT truncated; only the comment is" \
    bash -c '! grep -q "Truncated to fit one comment" "$1"' _ "$DSWEEP/unread.md"

# ------------------------------------------------------- the retired watcher
#
# ASSERT ON THE WORDS, NOT THE EXIT CODE. The old file exits non-zero here too
# -- 124, because `timeout` kills its sixty-second poll loop -- so rc alone
# cannot tell a retired script from a running one.
wout="$(timeout 10 bash "$DSRC/watch_remote_lane.sh" 2>&1; echo "rc=$?")"
check "watch_remote_lane.sh no longer polls: it returns at once" \
    bash -c '! grep -q "rc=124" <<< "$1"' _ "$wout"
check "...and names the job its polling moved into" \
    grep -q "comment_sweep.sh" <<< "$wout"
check "...and the tool that replaced its hand-written channel" \
    grep -q "deliver.sh" <<< "$wout"
check "...and refuses, so nothing restarts it as a background loop" \
    bash -c 'grep -q "rc=0" <<< "$1" && exit 1; exit 0' _ "$wout"
