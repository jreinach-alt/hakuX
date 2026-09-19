#!/usr/bin/env bash
#
# Sweep every comment in the repository for what nobody has absorbed, refresh
# the delivery cache from the same pass, and PUT THE RESULT WHERE SOMEBODY
# READS IT.
#
# WHY THIS EXISTS, and it is not "because reading comments is good practice".
# The orchestrator went a week without reading any, and the first pass that
# did found FIVE open issues whose comments carried verified results the
# tracker did not reflect -- three of them closable, one whose only copy of a
# 126-check PASS was a bare unexpanded path into a scratchpad that gets reaped.
# A lane reporting into an issue and nobody reading it is the cheapest possible
# way to lose finished work.
#
# THEN IT WAS UNWOUND THE OBVIOUS WAY. A "standing lane, scheduled" was created
# for it, run ONCE, and never scheduled -- so the process reverted to the
# orchestrator not doing it, which is exactly where it started. That is why
# this is a timer and a file on disk rather than an intention: a habit that
# depends on remembering is a habit that ends at the next context boundary.
#
# AND THEN IT LOST ITS READER ANYWAY. The timer kept running hourly and wrote
# `unread.md` to a directory on this host; the orchestrator role that was going
# to read it was deleted by ORCHESTRATION-DESIGN.md §4. The hand-off of
# 2026-09-19 records it as "still runs hourly; read by nobody". A sweep with no
# destination is the same defect as no sweep, one layer out -- it just costs an
# API call to fail. So this now ends at a GitHub comment, for §5's reason: the
# owner reads GitHub from a phone, and nothing else here is reachable from one.
#
# IT ALSO ABSORBED watch_remote_lane.sh, which polled every open issue plus PR
# #45 every sixty seconds to wake a session that no longer exists. Its lesson
# is the design below and is worth keeping precisely: its first version watched
# the PR alone and missed three substantive replies because the lane answered
# on the ISSUE threads, so "silence" and "nothing to say" became
# indistinguishable. Its fix was to enumerate open issues AND the PR -- right,
# and still an enumeration that can be wrong about a closed issue or a thread
# opened since the loop started.
#
#   `GET /repos/{o}/{r}/issues/comments?since=` RETURNS EVERY ISSUE COMMENT IN
#   THE REPOSITORY, INCLUDING COMMENTS ON PULL REQUESTS, IN ONE PAGINATED CALL.
#
# There is no list of threads to get wrong, so the blind spot that cost a day
# cannot recur here by construction, and the closed-issue hole this file used
# to paper over with `--state all` closes with it. Verified on 2026-09-19: one
# call returned comments on #10, #31, #143 and #151 -- two issues and two pull
# requests -- with no enumeration of anything.
#
# WHAT IT DOES NOT DO. It does not judge, close, or edit the tracker. It
# reports what changed since its last run. Deciding what a comment means is the
# board's, and a sweeper that draws conclusions from a comment it read once is
# how #82 came to carry "read from source, not confirmed against a binary" as
# its own last line. The one filter it applies is stated where it is applied.
set -u

REPO="${GH_REPO:-jreinach-alt/hakuX}"
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
OUT_DIR="${HAKUX_SWEEP_DIR:-$WORK/comment-sweep}"
STAMP="$OUT_DIR/last-run"
REPORT="$OUT_DIR/unread.md"
CID="$OUT_DIR/comment-id"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$OUT_DIR"

# FAIL OPEN, for the backlog gate's reason: any failure to establish state must
# not manufacture a false "nothing new". A silent empty report is worse than a
# loud failure, because it reads as a clean sweep.
since="$(cat "$STAMP" 2>/dev/null)"
[ -n "$since" ] || since="$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)"
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if ! command -v gh >/dev/null 2>&1; then
    echo "SWEEP FAILED: no gh. State NOT advanced, so the next run re-covers this window." >&2
    exit 2
fi

# THE DELIVERY CACHE, REFRESHED FROM THE SAME WINDOW.
#
# This is the machine half of the destination: check_coverage.py's UNBRIEFED
# note reads the cache deliver.sh writes, and that note lands on the summary
# line the board job and the idle watchdog both read. `deliver.sh send` already
# writes the cache from its own POST response, so this pass exists for the
# deliveries nobody sent through the tool -- one posted by hand, or from the
# owner's phone, which is the case the whole channel was moved to GitHub to
# allow.
#
# It runs BEFORE the report and its failure is not fatal to the report: two
# destinations, and one being unreachable must not take the other with it.
if [ -f "$SELF/jobs/deliver.sh" ]; then
    GH_REPO="$REPO" bash "$SELF/jobs/deliver.sh" scan --since "$since" \
        || echo "SWEEP: delivery cache not refreshed (deliver.sh scan exited $?)" >&2
else
    echo "SWEEP: no jobs/deliver.sh beside this script; the delivery cache is not refreshed" >&2
fi

# ONE CALL, EVERY THREAD. See the header. Emitted as TSV so the loop below does
# no JSON parsing of its own; the body's newlines and tabs are flattened by jq
# because a TSV row that contains a newline is a row this loop would silently
# split in half.
rows="$(timeout 180 gh api --paginate \
          "repos/$REPO/issues/comments?since=$since&sort=created&direction=desc&per_page=100" \
          --jq '.[] | [.created_at,
                       (.issue_url | split("/") | last),
                       .user.login,
                       .html_url,
                       (.body | gsub("[\r\n\t]"; " ") | .[0:400])] | @tsv' 2>/dev/null)" || {
    echo "SWEEP FAILED: the comments feed. State NOT advanced." >&2
    exit 2
}

{
    echo "## Comments since \`$since\`"
    echo
    echo "_Swept \`$now\` by \`docs/testing/comment_sweep.sh\` over every issue"
    echo "and pull-request comment in the repository (one \`issues/comments\`"
    echo "call; nothing is enumerated, so nothing can be left out). This page"
    echo "does not judge -- it reports._"
    echo
} > "$REPORT.tmp"

# THE FEED GOES IN A FILE AND ITS PATH GOES IN ARGV. `python3 -` reads its
# program from stdin, so a here-string of the data on the same call replaces
# the heredoc holding the program -- the parse then sees whichever redirection
# came last and one of the two vanishes silently. That exact shape has cost
# this project a debugging session before.
FEED="$OUT_DIR/.feed.tsv"
printf '%s\n' "$rows" > "$FEED"
python3 - "$REPORT.tmp" "$FEED" <<'PY'
import re, sys, collections
out = open(sys.argv[1], "a")
rows = [l.split("\t") for l in open(sys.argv[2]).read().splitlines() if l.strip()]
rows = [r for r in rows if len(r) >= 5]
# THE ONE FILTER, STATED WHERE IT IS APPLIED: a comment a JOB wrote is that
# job's own output, already delivered to whoever that job reports to, and it is
# the bulk of the volume. A delivery is exempt -- it is a job comment, and it
# is the one kind that is addressed to somebody. The count of what was filtered
# is printed, so the omission is visible and never silent.
JOB = re.compile(r"^\s*\[job\.[a-z]+\]")
DELIVER = re.compile(r"^\s*\[job\.deliver\] lane\.([A-Za-z0-9_.-]+)")
LANE = re.compile(r"^\s*\[lane\.([A-Za-z0-9_.-]+)\]")
jobs = [r for r in rows if JOB.match(r[4]) and not DELIVER.match(r[4])]
rest = [r for r in rows if r not in jobs]
by_thread = collections.OrderedDict()
for r in sorted(rest, key=lambda r: r[0]):
    by_thread.setdefault(r[1], []).append(r)

deliveries = {m.group(1): r for r in rows for m in [DELIVER.match(r[4])] if m}
reports = {}
for r in sorted(rows, key=lambda r: r[0]):
    m = LANE.match(r[4])
    if m:
        reports[m.group(1)] = r

out.write("%d comment(s) in the window: %d written by a job (its own output, "
          "already delivered; not listed) and %d below.\n\n"
          % (len(rows), len(jobs), len(rest)))

# THE ANSWERED/UNANSWERED TABLE IS THE POINT, and it is what
# watch_remote_lane.sh was trying to say. A lane that reported and was never
# routed an answer is the stall that had to be reported by the owner twice.
if deliveries or reports:
    out.write("### Lanes: routed in, reported out\n\n")
    out.write("| lane | last delivery routed to it | last report from it |\n|---|---|---|\n")
    for lane in sorted(set(deliveries) | set(reports)):
        d, p = deliveries.get(lane), reports.get(lane)
        out.write("| `lane.%s` | %s | %s |\n" % (
            lane,
            "[%s](%s) on #%s" % (d[0], d[3], d[1]) if d else "none in window",
            "[%s](%s) on #%s" % (p[0], p[3], p[1]) if p else "none in window"))
    out.write("\n_Window only. `deliver.sh last <lane>` is the standing answer,"
              " and `check_coverage.py` reports a lane whose newest delivery is"
              " more than three hours old as UNBRIEFED._\n\n")

if not by_thread:
    out.write("No unabsorbed comments in this window.\n")
for n, rs in sorted(by_thread.items(), key=lambda kv: int(kv[0])):
    out.write("### #%s\n\n" % n)
    for ts, _n, who, url, body in ((r[0], r[1], r[2], r[3], r[4]) for r in rs):
        out.write("- **%s** %s — %s [↗](%s)\n" % (ts, who, body.strip(), url))
    out.write("\n")
out.close()
PY
rc=$?
# A report the renderer did not finish is not a report. Leaving `.tmp` in place
# and not advancing the watermark means the next sweep re-covers this window,
# which is the same discipline every other failure path here follows.
[ "$rc" -eq 0 ] || { echo "SWEEP FAILED: the report renderer exited $rc. State NOT advanced." >&2; exit 2; }
found="$(grep -c '^### #' "$REPORT.tmp" 2>/dev/null || true)"
found="${found:-0}"
rm -f "$FEED"
mv "$REPORT.tmp" "$REPORT"


# A COMMENT HAS A CEILING AND THIS PAGE DOES NOT. Measured on the first live
# run: a 24-hour window produced 232 comments and a 44 KB page, against
# GitHub's 65536-character limit -- comfortable until a busy day, and a POST
# that fails for being too long would lose the whole report while every gate
# here still reported a clean sweep. So the POSTED copy is bounded and the
# truncation SAYS SO and says where the rest is; the on-disk page stays whole.
POST_MAX=${POST_MAX:-58000}
BODY="$REPORT"
python3 - "$REPORT" "$REPORT.post" "$POST_MAX" "$REPORT" <<'PY'
import sys
src, dst, cap, where = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
text = open(src).read()
if len(text) <= cap:
    sys.exit(1)                       # nothing to do; the caller posts the original
# Cut on a thread boundary so the last entry shown is a whole one.
head = text[:cap]
cut = head.rfind("\n### ")
if cut > 0:
    head = head[:cut + 1]
dropped = text[len(head):].count("\n### ")
open(dst, "w").write(
    head + "\n---\n\n_**Truncated to fit one comment.** %d further thread(s) "
    "are in the full page on the host at `%s`. This notice is here because a "
    "report that silently stops at the character limit reads exactly like a "
    "quiet day._\n" % (dropped, where))
PY
[ $? -eq 0 ] && BODY="$REPORT.post"

# THE DESTINATION. One comment, edited in place, on the issue labelled
# `harness-status` -- the same single URL status.sh writes to, for the same
# reason: the owner reads it from a phone and never has to find it twice. It is
# a job's roll-up and not discussion, which is what that issue's body asks of
# anyone commenting there, and it never grows: the comment id is remembered in
# $CID and PATCHed.
issue="$(timeout 60 gh issue list --repo "$REPO" --label harness-status --state open \
           --json number --jq '.[0].number' 2>/dev/null)"
if [ -z "$issue" ]; then
    echo "swept $now: $found thread(s) with new comments -> $REPORT (no harness-status issue; not posted)"
else
    cid="$(cat "$CID" 2>/dev/null)"
    posted=""
    if [ -n "$cid" ] && timeout 30 gh api "repos/$REPO/issues/comments/$cid" --silent >/dev/null 2>&1; then
        timeout 60 gh api -X PATCH "repos/$REPO/issues/comments/$cid" -F body=@"$BODY" --silent >/dev/null 2>&1 \
            && posted="updated #$issue comment $cid"
    fi
    if [ -z "$posted" ]; then
        cid="$(timeout 60 gh api -X POST "repos/$REPO/issues/$issue/comments" -F body=@"$BODY" --jq .id 2>/dev/null)"
        [ -n "$cid" ] && { echo "$cid" > "$CID"; posted="created #$issue comment $cid"; }
    fi
    echo "swept $now: $found thread(s) with new comments -> $REPORT (${posted:-NOT POSTED: gh refused})"
fi

# Advance the watermark ONLY on a clean sweep. A partial sweep that advanced it
# would silently drop the comments it failed to fetch -- the same shape as a
# zero mistaken for evidence. Everything that could fail above exits non-zero
# before reaching this line, except the POST, which loses a report and not a
# comment: the next sweep re-reads from the watermark either way.
echo "$now" > "$STAMP"
