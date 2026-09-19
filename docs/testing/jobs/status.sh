#!/usr/bin/env bash
#
# The status roll-up: what is in flight, what finished, what the devices are
# doing -- one Markdown page, rewritten in place.
#
#   status.sh            write $WORK/status/STATUS.md and update the GitHub comment
#   status.sh --print    write the page and print it; do not touch GitHub
#
# It is written by every job at the end of its tick and by hakux-status.timer
# every 30 minutes as the floor. It goes to ONE comment on the issue labelled
# `harness-status` (created if none exists), edited in place, so the owner
# has a single URL, readable from a phone, that is never stale by more than
# a tick. The first evening of the job harness the same facts were spread
# over a timer, a service, four logs and two TSVs on the host, and the owner
# could not tell whether anything was running. This is the answer to that.
#
# WHERE THE CLOCK LIVES, AND WHY IT IS NOT ONLY IN THE COMMENT. GitHub renders
# a comment's `created_at` beside the author's name, leaves the comment where
# it was posted in the timeline, and marks an edit with nothing louder than a
# grey "edited" link. An in-place PATCH therefore moves NOTHING a reader sees
# first. On 2026-09-19 that made #107 -- rewritten eleven minutes earlier --
# read as eleven hours old, which is the one confusion this page exists to
# prevent: a jammed fleet and a running fleet rendered identically. So the
# time now goes in the two places GitHub does surface, measured on this repo
# (see docs/lanes/statusfresh/NOTES.md):
#
#   - the issue BODY, which renders above every comment and whose edit makes
#     no timeline event at all. This carries the minute, and is free.
#   - the issue TITLE, which is all the issue LIST shows -- the phone's first
#     screen. A title PATCH that changes the string appends a permanent
#     `renamed` row to the timeline (a PATCH to the SAME string appends
#     nothing), so the title's clock is quantised to $FLOOR: it can never
#     claim freshness finer than the timer promises, and it renames at most
#     twice an hour on a fleet that is otherwise standing still.
#
# Everything here fails soft: a section that cannot be computed says so and
# the rest still renders.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
D="${DISPATCH_DIR:-$WORK/dispatch}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
J="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S="$WORK/status"; mkdir -p "$S"
OUT="$S/STATUS.md"
. "$J/models.env" 2>/dev/null; [ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
now=$(date +%s)
ago() { local t=${1:-}; [ -n "$t" ] || { echo "never"; return; }; local s=$(( now - t )); if [ $s -lt 120 ]; then echo "${s}s ago"; elif [ $s -lt 7200 ]; then echo "$(( s / 60 ))m ago"; else echo "$(( s / 3600 ))h $(( (s % 3600) / 60 ))m ago"; fi; }
since_iso() { date -u -d "${1:-24 hours ago}" +%FT%TZ 2>/dev/null; }
have_gh=0; command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1 && have_gh=1
have_sd=0; systemctl --user list-units >/dev/null 2>&1 && have_sd=1

# ---- how fresh the page can honestly claim to be, and whether it lapsed.
#
# FLOOR is hakux-status.timer's period. Nothing here can report the page's
# CURRENT silence -- a roll-up that is not running writes nothing, by
# definition -- so the page states its own deadline instead and leaves the
# reader a rule: a clock older than the deadline means status.sh has stopped.
# What it CAN report is a lapse that has already ended, and that is the more
# useful half: the window it names is a window in which the fleet was not
# observed, so an absent lane row across it means nothing either way.
FLOOR="${STATUS_FLOOR_SECS:-1800}"
case "$FLOOR" in ''|*[!0-9]*|0) FLOOR=1800 ;; esac   # a junk override must not divide by zero below and abort the tick
STAMP="$S/last-run"
prev_run=$(cat "$STAMP" 2>/dev/null); case "${prev_run:-}" in ''|*[!0-9]*) prev_run=0 ;; esac
lapse=0
[ "$prev_run" -gt 0 ] && [ $(( now - prev_run )) -gt $(( FLOOR * 2 )) ] && lapse=$(( now - prev_run ))
due=$(date -u -d "@$(( now + FLOOR ))" '+%F %H:%M UTC' 2>/dev/null)

# ---- the one-glance summary, for the title and the body header.
#
# Hoisted above the page because the title is built from the same counts and
# must not re-shell for them; `units` is consumed by the lanes section below.
units=""
[ $have_sd = 1 ] && units=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend --plain 2>/dev/null | awk '{print $1}')
n_lanes=$(printf '%s' "$units" | grep -c . 2>/dev/null || true); n_lanes=${n_lanes:-0}
n_run=$(ls "$D"/running/*.req 2>/dev/null | wc -l); n_q=$(ls "$D"/queue/*.req 2>/dev/null | wc -l)
summary="$n_lanes lane$([ "$n_lanes" = 1 ] || echo s) running, $n_run arm$([ "$n_run" = 1 ] || echo s) on a device, $n_q queued"

pr_for_branch() { [ $have_gh = 1 ] || return; gh pr list --repo "$GH_REPO" --head "$1" --state all --json number,state,isDraft,url --jq '.[0] | "#\(.number) \(if .isDraft then "draft" else (.state|ascii_downcase) end)"' 2>/dev/null; }
issue_of_brief() { grep -o -m1 '#[0-9]\+' "$WORK/briefs/$1.md" 2>/dev/null | head -1; }

{
echo "## hakuX harness -- live status"
echo
echo "_Rewritten $(date -u '+%F %H:%M UTC') by \`status.sh\` on the host. Sections that could not be computed say so._"
echo
echo "_Next roll-up due by $due. A clock older than that means \`status.sh\` has stopped: a roll-up that is not running cannot say so itself._"
echo
if [ "$lapse" -gt 0 ]; then
    echo "> [!WARNING]"
    echo "> **The roll-up lapsed for $(ago "$prev_run" | sed 's/ ago$//') before this one** -- previous tick $(date -u -d "@$prev_run" '+%F %H:%M UTC' 2>/dev/null), this tick $(date -u '+%F %H:%M UTC'). Nothing was observed across that window, so a lane or an arm that started and finished inside it has no row below. The state here is current; the history is not."
    echo
fi

# ---------------------------------------------------------------- lanes
echo "### Lanes running (cap ${LANE_MAX:-2})"
echo
if [ $have_sd = 1 ]; then
    if [ -n "$units" ]; then                     # hoisted to the summary above
        echo "| lane | issue | attempt | model | running for | PR |"; echo "|---|---|---|---|---|---|"
        for u in $units; do
            n=${u#hakux-lane-}; n=${n%.service}
            att=$(cat "$WORK/attempts/$n" 2>/dev/null || echo "?")
            if [ "${att:-0}" -gt "${LANE_ESCALATE_AFTER:-3}" ] 2>/dev/null; then m="${MODEL_LANE_ESCALATED:-fable}"; else m="${MODEL_LANE:-opus}"; fi
            ts=$(systemctl --user show "$u" -p ActiveEnterTimestamp --value 2>/dev/null); t=$(date -d "$ts" +%s 2>/dev/null)
            echo "| $n | $(issue_of_brief "$n") | $att | $m | $(ago "$t") | $(pr_for_branch "lane/$n") |"
        done
    else
        echo "none. The board dispatches at most one per tick when an issue is dispatchable and files are free."
    fi
else
    echo "(systemd --user not reachable from here)"
fi
echo

echo "### Lane sessions finished (last 24h)"
echo
if [ -f "$WORK/logs/lane/index.tsv" ]; then
    cut=$(since_iso)
    rows=$(awk -F'\t' -v c="$cut" '$1 >= c' "$WORK/logs/lane/index.tsv" | tail -12)
    if [ -n "$rows" ]; then
        echo "| when (UTC) | lane | model | turns | min | result | PR | said |"; echo "|---|---|---|---|---|---|---|---|"
        while IFS=$'\t' read -r ts job model turns secs cost ok log head; do
            # Rows written before the model column existed have eight fields; shift them.
            if [[ "$model" =~ ^[0-9?]+$ ]]; then head="$log"; log="$ok"; ok="$cost"; cost="$secs"; secs="$turns"; turns="$model"; model="-"; fi
            n=${job#lane-}; if [[ "${secs:-}" =~ ^[0-9]+$ ]]; then mins=$(( secs / 60 )); else mins="?"; fi   # a "?" from an unparsed log is not a number, and an arithmetic error here aborted the whole page
            echo "| ${ts:5:11} | $n | ${model#claude-} | $turns | $mins | $ok | $(pr_for_branch "lane/$n") | $(echo "$head" | cut -c1-90 | sed 's/|/\\|/g') |"
        done <<< "$rows"
    else
        echo "none in the window."
    fi
    echo
    echo "_result: ok = ended on its own; MAXTURNS = cut at the turn cap, work kept; ERR = the session errored. A lane that ended without a ready PR is resumed by the board (attempts 1-${LANE_ESCALATE_AFTER:-3} on ${MODEL_LANE:-opus}, then ${MODEL_LANE_ESCALATED:-fable}, then decision-needed)._"
else
    echo "no lane index yet."
fi
echo

# ---------------------------------------------------------------- cloud
echo "### Cloud-class sessions (hourly, on the host; last 24h from their \`[job.cloud]\` comments)"
echo
if [ $have_gh = 1 ]; then
    c=$(gh api "repos/$GH_REPO/issues/comments?since=$(since_iso)&per_page=100" \
          --jq '.[] | select(.body | startswith("[job.cloud]")) | "- \(.created_at | .[5:16]) \(.html_url | sub(".*/(issues|pull)/"; "#") | sub("#issuecomment.*"; "")) \(.body | split("\n")[0] | .[11:120])"' 2>/dev/null | tail -10)
    [ -n "$c" ] && echo "$c" || echo "none. cloud.sh runs hourly and claims one \`needs-audit-*\` PR or one \`cloud\` issue per tick; a tick with nothing to claim leaves no comment."
    [ $have_sd = 1 ] && echo "- running now: $(systemctl --user list-units 'hakux-cloud-*' --state=active,activating --no-legend --plain 2>/dev/null | awk '{printf "%s ", $1}' | sed 's/hakux-//g; s/.service//g')"
    [ -f "$WORK/logs/cloud/index.tsv" ] && { echo; echo '```'; tail -4 "$WORK/logs/cloud/index.tsv" | awk -F'\t' '{printf "%s %s %s turns=%s %ss %s %s\n",$1,$2,$3,$4,$5,$7,substr($9,1,80)}'; echo '```'; }
else
    echo "(gh not available here)"
fi
echo

# ---------------------------------------------------------------- board
echo "### Board job (every 20 min)"
echo
if [ -f "$WORK/logs/board/tick.log" ]; then
    echo '```'; tail -6 "$WORK/logs/board/tick.log" | cut -c1-160; echo '```'
    [ -f "$WORK/logs/board/index.tsv" ] && { echo; echo "last model ticks:"; echo '```'; tail -3 "$WORK/logs/board/index.tsv" | awk -F'\t' '{printf "%s %s %s turns=%s %ss %s %s\n",$1,$2,$3,$4,$5,$7,substr($9,1,80)}'; echo '```'; }
    echo; echo "board branch: $(git -C "$REPO" log -1 --format='%h %cr -- %s' origin/board 2>/dev/null | cut -c1-120)"
else
    echo "no tick log."
fi
echo

# ---------------------------------------------------------------- arms
echo "### Handhelds and arms"
echo
if command -v adb >/dev/null 2>&1; then
    devs=$(adb devices 2>/dev/null | tr -d '\r' | awk 'NR>1 && $2!=""{printf "%s(%s) ", $1, $2}')
    echo "- adb: ${devs:-no device visible}"
fi
[ $have_sd = 1 ] && echo "- dispatcher: $(systemctl --user is-active hakux-dispatcher.service 2>/dev/null), workers: $(pgrep -fc 'dispatcher.sh worker' 2>/dev/null || echo ?)"
echo "- queue: $n_q waiting, $n_run running; holds: $(ls "$D"/hold 2>/dev/null | grep -v '\.why$' | grep -v '^lifted$' | tr '\n' ' ')"
for r in "$D"/running/*.req; do [ -f "$r" ] || continue; echo "  - running: $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('requester',''),d.get('ref','')[:10],'--',(d.get('purpose') or '')[:90])" "$r" 2>/dev/null)"; done
[ -f "$D/logs/dispatcher.log" ] && echo "- dispatcher last line: \`$(tail -1 "$D/logs/dispatcher.log" | cut -c1-140)\`"

# ---- affinity: which handheld a pair is pinned to, and when it was not.
#
# `affinity.py`'s whole job is keeping the two arms of an A/B on ONE device,
# and when it cannot it writes a note into `$D/splits/`. Until this section
# NOTHING READ THAT DIRECTORY. On 2026-09-19 #89's pair ran base on the thor
# and fix on the nova; the note saying so was written correctly and was found
# only by someone who already suspected it and knew the path. The note's own
# docstring says it exists "so the DECISION is discoverable rather than
# reconstructed from a pace difference" -- which requires a reader.
#
# Asking affinity.py for `serving` rather than counting files: `$D/lanes/` is
# shared with check_coverage.py's `<lane>.lastbrief` stamps, a different
# feature and a different meaning of "lane", so a file count there would
# report devices that do not exist.
if aff_live=$(python3 "$(dirname "$J")/affinity.py" "$D" --serving 2>/dev/null); then
    if [ -n "$aff_live" ]; then
        echo "- affinity: lanes serving \`$aff_live\` -- an A/B pair queued now is pinned to one of them"
    else
        echo "- affinity: **no device lane is registered** in \`$D/lanes\`. Pinning is inert: an A/B pair queued now can split across two handhelds, and \`ab_compare\` will refuse to attribute the result. Check that \`hakux-dispatcher.service\` is up."
    fi
else
    echo "- affinity: (could not read \`$D/lanes\`)"
fi
sp=$(find "$D/splits" -maxdepth 1 -name '*.txt' -mmin -1440 -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -5 | cut -d' ' -f2-)
if [ -n "$sp" ]; then
    echo "- affinity notes, last 24h (a pair named here may span two devices and cannot isolate run-to-run variation):"
    while read -r f; do
        [ -n "$f" ] || continue
        echo "  - \`$(basename "$f" | sed 's/\.req\.\(blind\.\)\?txt$//' | cut -c1-48)\`: $(tr '\n' ' ' < "$f" | cut -c1-220 | sed 's/|/\\|/g')"
    done <<< "$sp"
fi
A="$WORK/arms"
if [ -d "$A" ]; then
    pend=0; for p in "$A"/pairs/*.json; do [ -f "$p" ] || continue; sha=$(basename "$p" .json); [ -f "$A/judged/$sha" ] || pend=$((pend+1)); done
    echo "- arms job: $pend pair(s) queued or running and not yet judged; $(ls "$A"/judged 2>/dev/null | wc -l) judged; $(ls "$A"/skipped 2>/dev/null | wc -l) skipped (see \`arms.sh list\`); watermark $(cat "$A/since" 2>/dev/null)"
    v=$(ls -t "$A"/judged/* 2>/dev/null | head -5)
    if [ -n "$v" ]; then
        echo; echo "last verdicts:"; echo
        for f in $v; do sha=$(basename "$f"); src=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('source',''))" "$A/pairs/$sha.json" 2>/dev/null); echo "- \`${sha:0:10}\` $src: $(head -1 "$f" | cut -c1-120)"; done
    fi
    [ -f "$WORK/logs/arms/tick.log" ] && { echo; echo '```'; tail -4 "$WORK/logs/arms/tick.log" | cut -c1-160; echo '```'; }
    sk=$(ls -t "$A"/skipped/* 2>/dev/null | head -3)
    if [ -n "$sk" ]; then
        echo; echo "last refusals, in full (a refusal is recorded once; delete the file under \`\$WORK/arms/skipped/\` to retry):"; echo
        for f in $sk; do echo "- \`$(basename "$f" | cut -c1-10)\` $(cat "$f" | cut -c1-600)"; done
    fi
else
    echo "- arms job: not installed yet"
fi
echo

# ---------------------------------------------------------------- fold
echo "### Fold job (every 30 min)"
echo
if [ $have_gh = 1 ]; then
    echo "- fold-ready: $(gh pr list --repo "$GH_REPO" --state open --label fold-ready --json number --jq 'map("#\(.number)") | join(" ")' 2>/dev/null); needs-rebase: $(gh pr list --repo "$GH_REPO" --state open --label needs-rebase --json number --jq 'map("#\(.number)") | join(" ")' 2>/dev/null); needs-remediation: $(gh pr list --repo "$GH_REPO" --state open --label needs-remediation --json number --jq 'map("#\(.number)") | join(" ")' 2>/dev/null)"
    echo "- awaiting audit: needs-audit-1 $(gh pr list --repo "$GH_REPO" --state open --label needs-audit-1 --json number --jq 'map("#\(.number)") | join(" ")' 2>/dev/null); needs-audit-2 $(gh pr list --repo "$GH_REPO" --state open --label needs-audit-2 --json number --jq 'map("#\(.number)") | join(" ")' 2>/dev/null)"
fi
[ -f "$WORK/logs/fold/tick.log" ] && { echo '```'; tail -4 "$WORK/logs/fold/tick.log" | cut -c1-160; echo '```'; } || echo "no fold tick yet."
echo "- master: $(git -C "$REPO" log -1 --format='%h %cr -- %s' origin/master 2>/dev/null | cut -c1-120)"
echo

# ---------------------------------------------------------------- open PRs
echo "### Open lane PRs"
echo
if [ $have_gh = 1 ]; then
    gh pr list --repo "$GH_REPO" --state open --json number,title,isDraft,headRefName,labels,updatedAt \
        --jq '.[] | "- #\(.number) \(if .isDraft then "(draft) " else "" end)`\(.headRefName)` \(.title | .[0:80]) -- labels: \(.labels | map(.name) | join(", ") | if . == "" then "none" else . end)"' 2>/dev/null
fi
echo
echo "### Job errors (last 24h, from the units' logs)"
echo
errs=0
for j in board arms fold cloud status; do
    f="$WORK/logs/$j/systemd.log"; [ -f "$f" ] || continue
    [ "$(( now - $(stat -c %Y "$f") ))" -lt 86400 ] || continue
    e=$(grep -nE 'Traceback|error:|Error|No such file|command not found|REFUSED|FAILED' "$f" | tail -3)
    [ -n "$e" ] || continue
    errs=1; echo "- **$j** (\`$f\`):"; echo '```'; echo "$e" | cut -c1-200; echo '```'
done
[ $errs = 0 ] && echo "none seen."
echo
echo "### Host"
echo
echo "- checkout \`$REPO\` on $(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null), $(git -C "$REPO" rev-list --count HEAD..origin/master 2>/dev/null || echo '?') behind origin/master (jobs run the fetched trunk regardless)"
[ $have_sd = 1 ] && echo "- timers: $(systemctl --user list-timers 'hakux-*' --no-legend --plain 2>/dev/null | awk '{printf "%s next %s %s; ", $NF, $1, $2}' | sed 's/.service//g; s/hakux-//g' | cut -c1-300)"
echo "- attempts: $(for f in "$WORK"/attempts/*; do [ -e "$f" ] && printf '%s=%s ' "$(basename "$f")" "$(cat "$f")"; done)"
} > "$OUT" 2>/dev/null

[ "${1:-}" = "--print" ] && { cat "$OUT"; exit 0; }
echo "$now" > "$STAMP"          # a real tick ran; --print is a dry run and does not count
[ $have_gh = 1 ] || { echo "wrote $OUT (gh unavailable; comment not updated)"; exit 0; }

# ------------------------------------------------- the one comment on GitHub
#
# `--json number,title`: the title comes back in the call we already make, so
# deciding whether to rename costs no extra request.
il=$(gh issue list --repo "$GH_REPO" --label harness-status --state open --json number,title --jq '.[0] | "\(.number) \(.title)"' 2>/dev/null); ilrc=$?
issue=${il%% *}; cur_title=""; [ "$il" != "$issue" ] && cur_title=${il#* }
# An empty list interpolates to the literal "null", which is not empty and used
# to sail into `PATCH /issues/null` -- every call returning 0 while the page
# went nowhere. Treat anything that is not a number as "no issue".
case "${issue:-}" in ''|*[!0-9]*) issue="" ;; esac
if [ -z "$issue" ]; then
    # Only a query that SUCCEEDED and found nothing licenses a second status
    # issue. A network blip must not fork the one page the owner reads.
    [ $ilrc -eq 0 ] || { echo "the harness-status query failed; not creating a second status issue"; exit 0; }
    issue=$(gh issue create --repo "$GH_REPO" --title "harness: live status (auto-updated)" --label harness-status --label harness \
        --body "Rewritten by \`docs/testing/jobs/status.sh\` at the end of every job tick and every 30 minutes. Pin this issue. Do not comment here; the roll-up is the only content, and it is regenerated from the host each time." 2>/dev/null | grep -o '[0-9]*$')
    [ -n "$issue" ] || { echo "could not create the status issue"; exit 0; }
    cur_title=""
    rm -f "$S/comment-id"
fi
cid=$(cat "$S/comment-id" 2>/dev/null)
posted=""
if [ -n "$cid" ] && gh api "repos/$GH_REPO/issues/comments/$cid" --silent >/dev/null 2>&1; then
    gh api -X PATCH "repos/$GH_REPO/issues/comments/$cid" -F body=@"$OUT" --silent >/dev/null 2>&1 && posted="updated #$issue comment $cid"
fi
if [ -z "$posted" ]; then       # no id, a deleted comment, or a PATCH that failed
    cid=$(gh api -X POST "repos/$GH_REPO/issues/$issue/comments" -F body=@"$OUT" --jq .id 2>/dev/null)
    [ -n "$cid" ] && { echo "$cid" > "$S/comment-id"; posted="created #$issue comment $cid"; }
fi
echo "${posted:-could not write the #$issue comment}"

# ---------------------------------------- the body: what the page shows FIRST
#
# Short on purpose. The roll-up stays in the comment -- its URL is deep-linked
# from elsewhere and its content is unchanged -- and this is the header a phone
# lands on: the clock, the counts, the deadline, and the reason not to believe
# the timestamp printed beside the comment.
HDR="$S/HEADER.md"
{
echo "## hakuX harness -- live status"
echo
echo "**Written $(date -u '+%F %H:%M UTC').** $summary."
echo
echo "Next roll-up due by **$due** ($(( FLOOR / 60 ))-minute floor, plus one at the end of every job tick). If the clock above is older than that, \`status.sh\` itself has stopped -- the page cannot report its own silence, so judge it by this line."
if [ "$lapse" -gt 0 ]; then
    echo
    echo "> [!WARNING]"
    echo "> **The roll-up lapsed for $(ago "$prev_run" | sed 's/ ago$//') before this one** (previous tick $(date -u -d "@$prev_run" '+%F %H:%M UTC' 2>/dev/null)). The state below is current; nothing was observed across that window."
fi
echo
[ -n "$cid" ] && echo "The full roll-up is [in the comment below](https://github.com/$GH_REPO/issues/$issue#issuecomment-$cid), rewritten in place every tick."
echo "GitHub shows a comment's *posted* time, not its edited time, and never moves an edited comment -- so read the clock in this body and in the title above it, never the timestamp beside the comment."
echo
# Carried forward from the body this header replaces. It is the page's only
# standing instruction and the first tick after this landed would have been the
# last anyone saw of it.
echo "_Pin this issue. Do not comment here: the roll-up is the only content, and it is regenerated from the host each tick._"
} > "$HDR" 2>/dev/null
gh api -X PATCH "repos/$GH_REPO/issues/$issue" -F body=@"$HDR" --silent >/dev/null 2>&1 \
    && echo "updated #$issue body" || echo "could not update the #$issue body"

# ------------------------------------------ the title: all the issue LIST shows
#
# Quantised to $FLOOR (see the header of this file): a rename is a permanent
# timeline row, a PATCH to an unchanged title is not, and the page must not
# claim to be fresher than the timer that writes it. Reading the stamped time
# as exact therefore errs towards "staler than it is", which is the safe way
# round for the question this page answers.
q=$(( now - now % FLOOR ))
want="harness: live status -- $(date -u -d "@$q" '+%H:%M')Z+, $summary"
if [ "$want" != "$cur_title" ]; then
    gh api -X PATCH "repos/$GH_REPO/issues/$issue" -f title="$want" --silent >/dev/null 2>&1 \
        && echo "renamed #$issue: $want"
else
    echo "#$issue title unchanged"
fi
exit 0
