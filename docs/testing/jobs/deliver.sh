#!/usr/bin/env bash
#
# The delivery channel: routing a lane its work is a GitHub comment.
#
#   deliver.sh send <lane> <thread> [-F <file> | -b <text>]   route work
#   deliver.sh inbox <lane> [--since <iso>]                   read what was routed
#   deliver.sh last <lane>                                    when it was last briefed
#   deliver.sh scan [--since <iso>]                           refresh the cache from GitHub
#
# WHY THIS EXISTS, AND WHAT IT REPLACES.
#
# Routing used to be an append to `$DISPATCH_DIR/deliveries/<lane>.md`. The
# reasoning was right and is preserved verbatim in that file's own header: a
# message to a cloud session is one-way and leaves no record either side can
# check, and a file does. Four audit findings (M2, M4, P2, L5) were recorded as
# "routed to lane.remote" when nothing had been routed at all, and that file was
# the answer.
#
# It had three independent breaks, and the third is fatal:
#
#   1. The writer was deleted. ORCHESTRATION-DESIGN.md §4 removed the
#      orchestrator role, and nothing has written a delivery since 2026-09-18.
#   2. The stamp it fed, `$DISPATCH_DIR/lanes/<lane>.lastbrief`, was a second
#      thing to remember and was four days older than the delivery file it was
#      a fallback for, on both lanes that had one.
#   3. THE RECIPIENT CANNOT OPEN THE FILE. §5 of the same document: "the cloud
#      sessions cannot see the dispatch directory, and the owner reads GitHub
#      from a phone." `deliveries/` is on the host's disk, on no ref and no
#      remote. No amount of writing to it reaches anyone.
#
# A comment thread has the property the file was chosen for -- append-only, a
# record BOTH sides can check -- and, unlike the file, the recipient can read
# it. So the channel moves to GitHub and the file is retired rather than kept
# alongside: two channels is how the record and the delivery came apart in the
# first place.
#
# THE ONE ENDPOINT THAT REMOVES THE BLIND SPOT.
#
# `watch_remote_lane.sh` was retired into this and into comment_sweep.sh, and
# its lesson is the design here. It first polled PR #45's comments only, and
# missed three substantive replies because the lane answered on the ISSUE
# threads. Its fix was to enumerate every open issue AND the PR -- correct, and
# still an enumeration that can be wrong: a closed issue, a PR nobody listed,
# a thread opened since the loop started.
#
# `GET /repos/{o}/{r}/issues/comments` returns EVERY issue comment in the
# repository, including comments on pull requests, in one paginated call. There
# is no list of threads to get wrong, so the failure mode that cost a day
# cannot recur here by construction. Verified against this repository on
# 2026-09-19: one call returned comments on #10, #31, #143 and #151 -- two
# issues and two PRs -- with no enumeration of any kind.
set -u

GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
D="${DISPATCH_DIR:-$WORK/dispatch}"
CACHE="$D/delivery-cache"

# The marker. `[job.<name>]` is how every other job tags its output
# ([job.board], [job.arms], [job.fold], [job.cloud]), and the lane name after
# it is what makes a delivery addressable. Anchored at the start of the first
# line: matching the words anywhere would match this file being quoted in a
# comment, which is how a grep check once passed against the wrong file.
DELIVER_RE='^\[job\.deliver\] lane\.([A-Za-z0-9_.-]+)'
# The reply direction, already a convention: ORCHESTRATION-DESIGN.md §6.5 says
# "every comment carries the lane name in its first line so the triage job can
# route it", and lanes write `[lane.<name>]`.
REPORT_RE='^\[lane\.([A-Za-z0-9_.-]+)\]'

usage() { sed -n '3,9p' "$0" | sed 's/^# \?//'; exit 2; }
die() { echo "deliver: $*" >&2; exit 1; }
need_gh() {
    command -v gh >/dev/null 2>&1 || die "no gh on PATH"
    timeout 30 gh auth status >/dev/null 2>&1 || die "gh is not authenticated"
}

# ---------------------------------------------------------------- the cache
#
# WHAT THE CACHE IS, AND WHAT IT IS NOT. It is NOT a second channel. Nothing
# reads it to learn what was routed -- `inbox` reads GitHub for that. It is an
# index of one field, "when did the newest delivery comment arrive", so that
# check_coverage.py can answer UNBRIEFED without a network call on a path that
# runs inside every lane's preflight.
#
# Every timestamp in it is GITHUB'S OWN `created_at` for a comment that exists,
# read back from the API response of the write that created it, or from a scan
# of the thread. It is never a clock reading taken locally at the moment
# somebody decided they had briefed a lane -- which is exactly what
# `lanes/<lane>.lastbrief` was, and why it was four days stale on both lanes
# that had one.
#
# WHAT IT CANNOT SEE, stated so a zero is never mistaken for evidence:
#   - a delivery posted by hand or from a phone, until the next `scan`. `send`
#     writes the cache from the POST response, so the normal path is instant;
#     `scan` is what makes the hand-written path eventually visible, and the
#     `scanned` field below says how eventually.
#   - whether the lane READ the delivery, or whether it said anything useful.
#     It measures routing, not receipt -- the same limit the delivery file had,
#     carried forward honestly rather than quietly dropped.
#   - anything outside the scan window. `scan --since` defaults to 30 days; a
#     lane whose last delivery is older than that keeps whatever the cache
#     already holds, because the merge below only ever moves a timestamp
#     FORWARD.
cache_path() { printf '%s/%s.json\n' "$CACHE" "$1"; }

# merge <lane> <kind:delivered|reported> <iso> <thread> <url>
#
# Validated and built in memory, then renamed into place: a half-written JSON
# file here would be read by check_coverage.py on every lane's preflight.
cache_merge() {
    mkdir -p "$CACHE" || return 1
    python3 - "$(cache_path "$1")" "$1" "$2" "$3" "$4" "$5" <<'PY'
import json, os, sys, datetime
path, lane, kind, iso, thread, url = sys.argv[1:7]
cur = {}
if os.path.exists(path):
    try:
        cur = json.load(open(path)) or {}
    except Exception:
        cur = {}            # a corrupt cache is replaced, never merged into
cur["lane"] = lane
# MONOTONIC. A scan of a short window must never move a timestamp backwards,
# and two scans racing must not fight. ISO-8601 UTC sorts lexically, which is
# the whole reason this project writes it that way.
if iso and iso > (cur.get(kind) or ""):
    cur[kind] = iso
    cur[kind + "_thread"] = int(thread) if thread else None
    cur[kind + "_url"] = url or None
cur["scanned"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
cur["source"] = "GitHub issue comments in the repository; see docs/testing/jobs/deliver.sh"
blob = json.dumps(cur, indent=2, sort_keys=True) + "\n"
json.loads(blob)            # refuse to write what cannot be read back
tmp = path + ".tmp"
open(tmp, "w").write(blob)
os.replace(tmp, path)
PY
}

# ----------------------------------------------------------------- send
cmd_send() {
    local lane="${1:-}" thread="${2:-}"; shift 2 || usage
    [ -n "$lane" ] && [ -n "$thread" ] || usage
    local text="" file=""
    while [ $# -gt 0 ]; do
        case "$1" in
            -F|--file) file="${2:-}"; shift 2 ;;
            -b|--body) text="${2:-}"; shift 2 ;;
            *) usage ;;
        esac
    done
    [ -n "$file" ] && { [ -r "$file" ] || die "cannot read $file"; text="$(cat "$file")"; }
    [ -n "$text" ] || die "a delivery with no body routes nothing; pass -b or -F"
    need_gh

    local tmp; tmp="$(mktemp "${TMPDIR:-/tmp}/deliver.XXXXXX")" || die "mktemp"
    # The payload is built by python and not by string concatenation: a body
    # with a quote, a backslash or a newline in it is the normal case here, and
    # a hand-rolled JSON string is how a board file was broken three times in
    # one session.
    python3 - "$tmp" "$lane" "$text" <<'PY'
import json, sys
path, lane, text = sys.argv[1:4]
body = ("[job.deliver] lane.%s\n\n%s\n\n"
        "---\n"
        "_Routed by `docs/testing/jobs/deliver.sh`. This comment IS the "
        "delivery: the thread is append-only, both sides can read it, and "
        "`deliver.sh inbox %s` lists every one of these. "
        "`$DISPATCH_DIR/deliveries/%s.md` is retired and is not read by "
        "anything._\n" % (lane, text.rstrip(), lane, lane))
json.dump({"body": body}, open(path, "w"))
PY
    local out
    out="$(timeout 60 gh api -X POST "repos/$GH_REPO/issues/$thread/comments" \
             --input "$tmp" --jq '"\(.created_at)\t\(.html_url)"' 2>&1)" || {
        rm -f "$tmp"; die "gh refused the comment on #$thread: $out"; }
    rm -f "$tmp"
    local iso url
    IFS=$'\t' read -r iso url <<< "$out"
    # THE STAMP IS READ BACK FROM THE COMMENT, not taken from the local clock.
    # If GitHub did not create it, there is no timestamp to record and the lane
    # correctly keeps reading as unbriefed.
    [ -n "$iso" ] || die "the POST returned no created_at; nothing was recorded"
    cache_merge "$lane" delivered "$iso" "$thread" "$url" \
        || echo "deliver: WARNING: the comment was posted but the cache write failed; run 'deliver.sh scan'" >&2
    echo "delivered to lane.$lane on #$thread at $iso"
    echo "$url"
}

# --------------------------------------------------------------- the feed
#
# One paginated call, newest first. Emits TSV: iso, thread, url, first line.
# `since` filters on the comment's updated_at, so an edited old comment
# reappears; that is harmless for a max() and is why nothing here assumes the
# feed is only new material.
feed() {
    local since="$1"
    timeout 120 gh api --paginate \
        "repos/$GH_REPO/issues/comments?since=$since&sort=created&direction=desc&per_page=100" \
        --jq '.[] | [.created_at, (.issue_url | split("/") | last), .html_url,
                     (.body | split("\n")[0] | gsub("[\r\t]"; " "))] | @tsv' 2>/dev/null
}

iso_ago() { date -u -d "${1}" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null; }

# ----------------------------------------------------------------- scan
cmd_scan() {
    local since=""
    while [ $# -gt 0 ]; do
        case "$1" in --since) since="${2:-}"; shift 2 ;; *) usage ;; esac
    done
    [ -n "$since" ] || since="$(iso_ago '30 days ago')"
    need_gh
    local rows; rows="$(feed "$since")"
    # FAIL LOUD, NOT EMPTY. An unreachable API that returned "no deliveries"
    # would freeze every lane's brief age at whatever the cache last held and
    # read as a clean scan -- the shape comment_sweep.sh's own header calls the
    # worst outcome there is.
    [ -n "$rows" ] || { echo "deliver: scan found no comments since $since (API unreachable, or the repository really is quiet)" >&2; return 3; }
    local n=0
    while IFS=$'\t' read -r iso thread url first; do
        [ -n "$iso" ] || continue
        local lane=""
        if [[ "$first" =~ $DELIVER_RE ]]; then
            lane="${BASH_REMATCH[1]}"
            cache_merge "$lane" delivered "$iso" "$thread" "$url" && n=$((n+1))
        elif [[ "$first" =~ $REPORT_RE ]]; then
            lane="${BASH_REMATCH[1]}"
            cache_merge "$lane" reported "$iso" "$thread" "$url" && n=$((n+1))
        fi
    done <<< "$rows"
    echo "scanned since $since: $n delivery/report comment(s) folded into $CACHE"
}

# ----------------------------------------------------------------- inbox
#
# The READER side, and the reason the channel moved at all: this runs anywhere
# gh runs, including in a cloud session that cannot see this host's disk.
cmd_inbox() {
    local lane="${1:-}"; shift || true
    [ -n "$lane" ] || usage
    local since=""
    while [ $# -gt 0 ]; do
        case "$1" in --since) since="${2:-}"; shift 2 ;; *) usage ;; esac
    done
    [ -n "$since" ] || since="$(iso_ago '30 days ago')"
    need_gh
    timeout 120 gh api --paginate \
        "repos/$GH_REPO/issues/comments?since=$since&sort=created&direction=asc&per_page=100" \
        --jq '.[] | select(.body | startswith("[job.deliver] lane.'"$lane"'\n"))
              | "\n=== \(.created_at)  \(.html_url)\n\(.body)"' 2>/dev/null
}

# ------------------------------------------------------------------ last
#
# Prints `<iso>\t<thread>\t<url>` for the newest delivery this host knows of,
# from the cache. Exits 3 when there is none, which is "never briefed" and not
# "briefed a long time ago" -- the two must not be confused by a consumer.
cmd_last() {
    local lane="${1:-}"; [ -n "$lane" ] || usage
    local p; p="$(cache_path "$lane")"
    [ -f "$p" ] || { echo "no delivery on record for lane.$lane" >&2; return 3; }
    python3 - "$p" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    sys.exit("deliver: unreadable cache: %s" % e)
if not d.get("delivered"):
    sys.exit(3)
print("%s\t%s\t%s" % (d["delivered"], d.get("delivered_thread"), d.get("delivered_url")))
PY
}

case "${1:-}" in
    send)  shift; cmd_send "$@" ;;
    inbox) shift; cmd_inbox "$@" ;;
    last)  shift; cmd_last "$@" ;;
    scan)  shift; cmd_scan "$@" ;;
    *) usage ;;
esac
