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

pr_for_branch() { [ $have_gh = 1 ] || return; gh pr list --repo "$GH_REPO" --head "$1" --state all --json number,state,isDraft,url --jq '.[0] | "#\(.number) \(if .isDraft then "draft" else (.state|ascii_downcase) end)"' 2>/dev/null; }
issue_of_brief() { grep -o -m1 '#[0-9]\+' "$WORK/briefs/$1.md" 2>/dev/null | head -1; }

{
echo "## hakuX harness -- live status"
echo
echo "_Rewritten $(date -u '+%F %H:%M UTC') by \`status.sh\` on the host. Sections that could not be computed say so._"
echo

# ---------------------------------------------------------------- lanes
echo "### Lanes running (cap ${LANE_MAX:-2})"
echo
if [ $have_sd = 1 ]; then
    units=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend --plain 2>/dev/null | awk '{print $1}')
    if [ -n "$units" ]; then
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
echo "- queue: $(ls "$D"/queue/*.req 2>/dev/null | wc -l) waiting, $(ls "$D"/running/*.req 2>/dev/null | wc -l) running; holds: $(ls "$D"/hold 2>/dev/null | grep -v '\.why$' | grep -v '^lifted$' | tr '\n' ' ')"
for r in "$D"/running/*.req; do [ -f "$r" ] || continue; echo "  - running: $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('requester',''),d.get('ref','')[:10],'--',(d.get('purpose') or '')[:90])" "$r" 2>/dev/null)"; done
[ -f "$D/logs/dispatcher.log" ] && echo "- dispatcher last line: \`$(tail -1 "$D/logs/dispatcher.log" | cut -c1-140)\`"
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
[ $have_gh = 1 ] || { echo "wrote $OUT (gh unavailable; comment not updated)"; exit 0; }

# ------------------------------------------------- the one comment on GitHub
issue=$(gh issue list --repo "$GH_REPO" --label harness-status --state open --json number --jq '.[0].number' 2>/dev/null)
if [ -z "$issue" ]; then
    issue=$(gh issue create --repo "$GH_REPO" --title "harness: live status (auto-updated)" --label harness-status --label harness \
        --body "The first comment below is rewritten by \`docs/testing/jobs/status.sh\` at the end of every job tick and every 30 minutes. Pin this issue. Do not comment here; the roll-up is the only content, and it is regenerated from the host each time." 2>/dev/null | grep -o '[0-9]*$')
    [ -n "$issue" ] || { echo "could not create the status issue"; exit 0; }
    rm -f "$S/comment-id"
fi
cid=$(cat "$S/comment-id" 2>/dev/null)
if [ -n "$cid" ] && gh api "repos/$GH_REPO/issues/comments/$cid" --silent >/dev/null 2>&1; then
    gh api -X PATCH "repos/$GH_REPO/issues/comments/$cid" -F body=@"$OUT" --silent >/dev/null 2>&1 && echo "updated #$issue comment $cid" && exit 0
fi
cid=$(gh api -X POST "repos/$GH_REPO/issues/$issue/comments" -F body=@"$OUT" --jq .id 2>/dev/null)
[ -n "$cid" ] && echo "$cid" > "$S/comment-id" && echo "created #$issue comment $cid"
exit 0
