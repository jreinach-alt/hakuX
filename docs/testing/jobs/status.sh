#!/usr/bin/env bash
#
# The status roll-up: what is in flight, what finished, what the devices are
# doing -- one Markdown page, rewritten in place.
#
#   status.sh            write $WORK/status/STATUS.md and index.html, publish the
#                        dashboard to gh-pages, and (until #107 is a pointer) the comment
#   status.sh --print    write the pages and print the Markdown; do not touch GitHub
#   status.sh --pages    write the pages and publish the dashboard only
#
# THE DASHBOARD (2026-09-26) is what the owner reads now: index.html on an
# orphan gh-pages branch, rendered by status_html.py. See "the dashboard" below;
# everything from here to there is the gathering, and the #107 machinery at the
# end runs only until #107 has been switched, once, to a pointer at the page.
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
. "$J/models.env" 2>/dev/null; . "$J/window.sh" 2>/dev/null; [ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
. "$J/localtime.sh"   # say_time/local_ts/tz_abbr: this page is read by a person, so it is shown in the display zone
# epoch: zone-free by construction, only ever subtracted (see ago()). STATUS_NOW pins it for a
# fixture (docs/lanes/dash432/fixtures): a page rendered from a snapshot must age from the snapshot.
now=${STATUS_NOW:-$(date +%s)}; case "$now" in ''|*[!0-9]*) now=$(date +%s) ;; esac
ago() { local t=${1:-}; [ -n "$t" ] || { echo "never"; return; }; local s=$(( now - t )); if [ $s -lt 120 ]; then echo "${s}s ago"; elif [ $s -lt 7200 ]; then echo "$(( s / 60 ))m ago"; else echo "$(( s / 3600 ))h $(( (s % 3600) / 60 ))m ago"; fi; }
# DATA, NOT DISPLAY -- STAYS UTC, for two independent reasons. It is handed
# to the GitHub API as `since=`, which is specified in UTC; and it is the
# right-hand side of the lexical `$1 >= c` awk comparison below against
# logs/*/index.tsv column 1, which summarise_run.py writes in UTC for exactly
# this reason. Making either side local silently drops or duplicates rows,
# and across the November fall-back it does so in the wrong order.
since_iso() { date -u -d "${1:-24 hours ago}" +%FT%TZ 2>/dev/null; }
# The tail of a logs/*/index.tsv, for a fenced block. Column 1 is written in
# UTC by summarise_run.py (it is what since_iso() filters on) and converted
# here, at the point of printing -- a fenced block on this page is still
# something a person reads, and a UTC line inside a page whose header says
# "every time here is PDT" is the two-zones-in-one-view the conversion exists
# to remove.
tsv_tail() {
    local f=$1 n=$2 ts rest
    tail -n "$n" "$f" | while IFS= read -r line; do
        ts=${line%%$'\t'*}; rest=${line#*$'\t'}
        printf '%s %s\n' "$(local_hm "$ts")" \
            "$(printf '%s' "$rest" | awk -F'\t' '{printf "%s %s turns=%s %ss %s %s",$1,$2,$3,$4,$6,substr($8,1,80)}')"
    done
}

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
# DISPLAY, so the display zone: this deadline is printed in the body and the
# comment and compared by nothing but a reader's eye.
due=$(local_ts "@$(( now + FLOOR ))")
# The window module's facts and reasons carry UTC instants ("2026-09-21T00:00Z")
# because window.sh compares them; this renders each one in the display zone
# at the point of printing and leaves the variables themselves untouched.
local_instants() {
    local s=$1 m
    while [[ "$s" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(:[0-9]{2})?Z) ]]; do
        m=${BASH_REMATCH[1]}
        s=${s//"$m"/$(local_ts "$m")}
        [[ "$(local_ts "$m")" == "$m" ]] && break     # unparsed: stop rather than loop on it
    done
    printf '%s' "$s"
}

# ---- the one-glance summary, for the title and the body header.
#
# Hoisted above the page because the title is built from the same counts and
# must not re-shell for them; `units` is consumed by the lanes section below.
units=""
[ $have_sd = 1 ] && units=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend --plain 2>/dev/null | awk '{print $1}')
n_lanes=$(printf '%s' "$units" | grep -c . 2>/dev/null || true); n_lanes=${n_lanes:-0}
# The z-* idle tier (the full-corpus sweep) is counted apart: it sorts behind
# everything and waiting for hours is its design, not a backlog.
n_run=$(ls "$D"/running/*.req 2>/dev/null | wc -l); n_z=$(ls "$D"/queue/z-*.req 2>/dev/null | wc -l)
n_q=$(ls "$D"/queue/*.req 2>/dev/null | grep -vc '/z-[^/]*$')
summary="$n_lanes lane$([ "$n_lanes" = 1 ] || echo s) running, $n_run arm$([ "$n_run" = 1 ] || echo s) on a device, $n_q queued$([ "$n_z" = 0 ] || echo " (+$n_z idle-tier sweep)")"

pr_for_branch() { [ $have_gh = 1 ] || return; gh pr list --repo "$GH_REPO" --head "$1" --state all --json number,state,isDraft,url --jq '.[0] | "#\(.number) \(if .isDraft then "draft" else (.state|ascii_downcase) end)"' 2>/dev/null; }
issue_of_brief() { grep -o -m1 '#[0-9]\+' "$WORK/briefs/$1.md" 2>/dev/null | head -1; }

{
echo "## hakuX harness -- live status"
echo
echo "_Rewritten $(say_time) by \`status.sh\` on the host. Every time on this page is $(tz_abbr). Sections that could not be computed say so._"
echo
echo "_Next roll-up due by $due. A clock older than that means \`status.sh\` has stopped: a roll-up that is not running cannot say so itself._"
echo
if [ "$lapse" -gt 0 ]; then
    echo "> [!WARNING]"
    echo "> **The roll-up lapsed for $(ago "$prev_run" | sed 's/ ago$//') before this one** -- previous tick $(local_ts "@$prev_run"), this tick $(say_time). Nothing was observed across that window, so a lane or an arm that started and finished inside it has no row below. The state here is current; the history is not."
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
        echo "none. The board dispatches up to three per tick when issues are dispatchable and their files are free."
    fi
else
    echo "(systemd --user not reachable from here)"
fi
echo

# ------------------------------------------------------------- every lane
#
# WHAT EACH LANE IS DOING, from facts (#432). The owner, 2026-09-26 16:20 PDT,
# could not read the table this replaced: "never" in a column meant three
# different things, every summary was cut at 90 characters, timer jobs, live
# lanes, parked lanes and twenty retired rows shared one table, and the board's
# `dispatch_state = blocked` -- written on EVERY owned issue so it will not
# start a second lane -- was read as "stuck". status_html.py `lanes` now derives
# one state per lane from a fixed vocabulary (running, waiting on device, in a
# device session, waiting on audit, waiting on a file, waiting on owner, parked,
# finished, stranded) out of units, the dispatch dirs, PR state and labels,
# territory.toml and the tracker, the lane logs, and for lane.xbox and
# lane.remote their GitHub comments. Only "stranded" is an alarm. It writes
# lanes.json (the dashboard's first screen), `idle-lanes` (the #107 body
# header), and these sections of STATUS.md.
#
# The console meter is read here, once, because it takes the plug's lock and
# the plug must not be polled more than once a minute: every job tick ends in
# this script, so the reading is cached for 60 s under $S.
KASA="$WORK/host-tools/kasa_console.py"
meter="console meter: not available"
if [ -x "$KASA" ]; then
    mc="$S/console-meter"; mt=$(stat -c %Y "$mc" 2>/dev/null || echo 0)
    if [ $(( now - mt )) -ge 60 ]; then
        # "plug KP115 <mac> (Xbox) at <ip>: ON, 66.1 W" -- the reading is the part after the last ": "
        r=$(timeout 75 "$KASA" status --no-find 2>&1 | tail -1 | sed 's/.*: //' | cut -c1-80)
        printf '%s\n' "${r:-no answer}" > "$mc"
    fi
    ma=$(( now - $(stat -c %Y "$mc" 2>/dev/null || echo "$now") )); [ "$ma" -ge 0 ] || ma=0
    meter="console meter: $(cat "$mc" 2>/dev/null) (read ${ma}s ago)"
fi
echo "### Lanes: what each one is doing ($(tz_abbr))"
echo
rm -f "$S/lanes.json"      # the dashboard must not show last tick's lanes as this tick's
STATUS_METER="$meter" WORK="$WORK" D="$D" REPO="$REPO" GH_REPO="$GH_REPO" J="$J" S="$S" STATUS_NOW="$now" \
HAVE_GH=$have_gh HAVE_SD=$have_sd UNITS="$units" timeout 300 python3 "$J/status_html.py" lanes \
    --json "$S/lanes.json" --idle "$S/idle-lanes" 2>"$S/lanes.err" \
    || echo "(the lane table could not be computed: $(tail -1 "$S/lanes.err" 2>/dev/null))"
echo

# ------------------------------------------------- the account's windows
#
# A FLEET THAT GOES QUIET FOR BUDGET REASONS LOOKS EXACTLY LIKE A FLEET THAT
# HAS JAMMED. That is the failure the whole job harness was rebuilt to remove,
# so the reserve says the same thing in three places: this section, the board's
# tick log, and the board session's own brief. If dispatch is held, the reason
# and the resume time are HERE, above the fold, next to the empty lane table
# that would otherwise be the only visible symptom.
echo "### Window budget (the account's five-hour and weekly windows)"
echo
if declare -f window_check >/dev/null 2>&1; then
    window_check
    if [ "${WINDOW_DEFER:-0}" = 1 ]; then
        # The resume time is the one line on this page a person acts on, and the
        # header above promises every time here is the display zone -- so it is
        # converted. So are the UTC instants inside $WINDOW_WHY/$WINDOW_FACTS,
        # by local_instants() at the point of printing: window.sh keeps them
        # UTC for its own comparisons and nothing here writes them back.
        # local_ts falls back to UTC (and then to its own argument) when the
        # zone or the parse is unavailable.
        echo "- **dispatch DEFERRED until $(local_ts "$WINDOW_UNTIL")** -- $(local_instants "$WINDOW_WHY")."
        echo "- This is a budget decision, not a failure. Folds, arms, labels, sessions already running and this page continue; no lane attempt is counted; nothing here needs investigating."
    else
        echo "- dispatching normally. Lanes and audits start as work allows; expanding is the default."
    fi
    echo "- $(local_instants "$WINDOW_FACTS")."
    if [ -s "$WORK/window/limits.tsv" ]; then
        echo "- usage-limit refusals recorded (\`\$WORK/window/limits.tsv\`), most recent last:"
        echo '```'; tail -5 "$WORK/window/limits.tsv" | while IFS= read -r l; do local_instants "$l"; echo; done; echo '```'
    else
        echo "- no session has ever been refused by the account's window on this host. That is the only first-hand evidence of a closed window there is: **the remaining five-hour and weekly balance cannot be queried from here**, so the weekly reserve arms on that evidence, or on \`WEEK_SPEND_BUDGET\` if the owner declares one in \`\$WORK/limits.env\`. Unknown means open, by design."
    fi
else
    echo "(jobs/window.sh not available here)"
fi
echo

echo "### Lane sessions finished (last 24h)"
echo
if [ -f "$WORK/logs/lane/index.tsv" ]; then
    cut=$(since_iso)
    rows=$(awk -F'\t' -v c="$cut" '$1 >= c' "$WORK/logs/lane/index.tsv" | tail -12)
    # The index keeps a 120-character head of each result: print only what ends
    # at a sentence stop inside it, never a word cut in half (#432).
    first_sentence_of() { printf '%s' "$1" | sed -E 's/^(.*[.!?])( .*)?$/\1/; t; s/.*/-/' | sed 's/|/\\|/g'; }
    if [ -n "$rows" ]; then
        echo "| when ($(tz_abbr)) | lane | model | turns | min | result | PR | said |"; echo "|---|---|---|---|---|---|---|---|"
        while IFS=$'\t' read -r ts job model turns secs cost ok log head; do
            # Rows written before the model column existed have eight fields; shift them.
            if [[ "$model" =~ ^[0-9?]+$ ]]; then head="$log"; log="$ok"; ok="$cost"; cost="$secs"; secs="$turns"; turns="$model"; model="-"; fi
            n=${job#lane-}; if [[ "${secs:-}" =~ ^[0-9]+$ ]]; then mins=$(( secs / 60 )); else mins="?"; fi   # a "?" from an unparsed log is not a number, and an arithmetic error here aborted the whole page
            # $ts is UTC on disk and converted HERE, at the point of printing.
            # The column it comes from is what since_iso() filters on above,
            # so the stored field must stay UTC; only the reader sees local.
            echo "| $(local_hm "$ts") | $n | ${model#claude-} | $turns | $mins | $ok | $(pr_for_branch "lane/$n") | $(first_sentence_of "$head") |"
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
    # created_at comes back in UTC (the API's own zone, which is also why
    # since= above must stay UTC). It is emitted whole and converted below
    # rather than sliced in jq, so the reader gets the same zone as the rest
    # of the page.
    c=$(gh api "repos/$GH_REPO/issues/comments?since=$(since_iso)&per_page=100" \
          --jq '.[] | select(.body | startswith("[job.cloud]")) | "\(.created_at)\t\(.html_url | sub(".*/(issues|pull)/"; "#") | sub("#issuecomment.*"; "")) \(.body | split("\n")[0] | .[11:120])"' 2>/dev/null | tail -10)
    if [ -n "$c" ]; then
        while IFS=$'\t' read -r cts crest; do
            [ -n "$cts" ] || continue
            echo "- $(local_hm "$cts") $crest"
        done <<< "$c"
    else
        echo "none. cloud.sh runs hourly and claims one \`needs-audit-*\` PR or one \`cloud\` issue per tick; a tick with nothing to claim leaves no comment."
    fi
    [ $have_sd = 1 ] && echo "- running now: $(systemctl --user list-units 'hakux-cloud-*' --state=active,activating --no-legend --plain 2>/dev/null | awk '{printf "%s ", $1}' | sed 's/hakux-//g; s/.service//g')"
    [ -f "$WORK/logs/cloud/index.tsv" ] && { echo; echo '```'; tsv_tail "$WORK/logs/cloud/index.tsv" 4; echo '```'; }
else
    echo "(gh not available here)"
fi
echo

# ---------------------------------------------------------------- board
echo "### Board job (every 20 min)"
echo
if [ -f "$WORK/logs/board/tick.log" ]; then
    echo '```'; tail -6 "$WORK/logs/board/tick.log" | cut -c1-160; echo '```'
    [ -f "$WORK/logs/board/index.tsv" ] && { echo; echo "last model ticks:"; echo '```'; tsv_tail "$WORK/logs/board/index.tsv" 3; echo '```'; }
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
echo "- queue: $n_q waiting, $n_z idle-tier z-* behind them, $n_run running; holds: $(ls "$D"/hold 2>/dev/null | grep -v '\.why$' | grep -v '^lifted$' | tr '\n' ' ')"
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
    echo "- arms job: $pend pair(s) queued or running and not yet judged; $(ls "$A"/judged 2>/dev/null | wc -l) judged; $(ls "$A"/skipped 2>/dev/null | wc -l) skipped (see \`arms.sh list\`); watermark $(local_ts "$(cat "$A/since" 2>/dev/null)") (stored as \`$(cat "$A/since" 2>/dev/null)\`: arms.sh compares that UTC string to registered_utc, so the file stays UTC and only this rendering is local)"
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
[ $have_sd = 1 ] && echo "- timers: $(systemctl --user list-timers 'hakux-*' --no-legend --plain 2>/dev/null | awk '{printf "%s next %s\n", $NF, ($1 == "-" ? "-" : $3 " " $4)}' | sed 's/.service//g; s/hakux-//g' | sort | paste -sd';' | sed 's/;/; /g' | cut -c1-400)"   # sorted by name: the dashboard republishes on a change, and the clock alone reorders by next elapse
echo "- attempts: $(for f in "$WORK"/attempts/*; do [ -e "$f" ] && printf '%s=%s ' "$(basename "$f")" "$(cat "$f")"; done)"
} > "$OUT" 2>/dev/null

# ================================================================ the dashboard
#
# THE PAGE THE OWNER READS (2026-09-26): a static index.html on an orphan
# `gh-pages` branch, https://<owner>.github.io/<repo>/. #107 could not be that
# page: its roll-up was a comment, so it rendered below the issue's timeline,
# and the per-tick title rename put 304 permanent `renamed` rows above it in a
# week. The page is ONE commit, force-pushed, so nothing ever accumulates.
#
# Bash gathers the first screen here into facts.tsv (key<TAB>value, plus
# `attn<TAB>kind<TAB>text` and `blocker<TAB>n<TAB>title` rows); the lane block
# above wrote lanes.json; status_html.py merges both with STATUS.md into
# status.json and renders index.html from it.
FACTS="$S/facts.tsv"
fact() { printf '%s\t%s\n' "$1" "$(printf '%s' "$2" | tr '\t\n' '  ')"; }
attn() { printf 'attn\t%s\t%s\n' "$1" "$(printf '%s' "$2" | tr '\t\n' '  ')"; }
HEARTBEAT="${STATUS_PAGES_HEARTBEAT:-1800}"; case "$HEARTBEAT" in ''|*[!0-9]*) HEARTBEAT=1800 ;; esac
{
fact now "$now"; fact floor_secs "$FLOOR"; fact heartbeat_secs "$HEARTBEAT"; fact next_due "$due"
fact queue "$n_q"; fact queue_idle "$n_z"; fact arms_running "$n_run"
fact lanes_running "$n_lanes"; fact lane_cap "${LANE_MAX:-2}"
[ "${WINDOW_DEFER:-0}" = 1 ] && fact window "dispatch deferred until $(local_ts "${WINDOW_UNTIL:-}") (budget, not a fault)"
# The last fold is the last `fold: PR` commit on master: fold.sh writes exactly that subject.
lf=$(git -C "$REPO" log -1 --format='%ct%x09%s' --grep='^fold: PR' origin/master 2>/dev/null)
[ -n "$lf" ] && { fact last_fold "${lf%%$'\t'*}"; fact last_fold_subject "$(printf '%s' "${lf#*$'\t'}" | sed 's/^fold: //' | cut -c1-90)"; }
[ -x "$KASA" ] && fact console "${meter#console meter: }"
[ "$lapse" -gt 0 ] && attn page "the roll-up itself lapsed for $(ago "$prev_run" | sed 's/ ago$//') before this tick (previous $(local_ts "@$prev_run")); nothing was observed across that window"
# The owner's open decisions (host-tools/escalations.md, one per line) are read by status_html.py's
# gather() into "What needs a person", each line whole. This block used to count only lines starting
# "- ", and the host writes them without a bullet: six open decisions read as zero at 16:24 PDT.
if [ $have_gh = 1 ]; then
    # A red CI on master: the newest COMPLETED run of each workflow. Reading run
    # state costs no Actions minutes.
    gh run list --repo "$GH_REPO" --branch master --limit 20 --json workflowName,status,conclusion,headSha,createdAt \
        --jq '[.[] | select(.status == "completed")] | group_by(.workflowName) | map(max_by(.createdAt)) | .[]
              | select(.conclusion == "failure" or .conclusion == "timed_out" or .conclusion == "startup_failure")
              | "\(.workflowName) \(.conclusion) on master at \(.headSha[0:10])"' 2>/dev/null \
        | while IFS= read -r l; do [ -n "$l" ] && attn ci "CI red: $l"; done
    # The release gate. Blockers are open issues carrying the label; the gate's
    # text is the owner's (hostops-poll item 10) and overridable in limits.env.
    fact release_name "${STATUS_RELEASE_NAME:-0.5}"
    fact release_gate "${STATUS_RELEASE_GATE:-Ghoulies median >= 25 gfps over 90-240 s on the candidate APK, both handhelds}"
    rc=$(gh release list --repo "$GH_REPO" --limit 30 --json tagName --jq ".[] | .tagName | select(startswith(\"${STATUS_RELEASE_TAG:-v0.5}\"))" 2>/dev/null | head -1)
    fact release_candidate "${rc:-none cut yet}"
    BL="${STATUS_BLOCKER_LABEL:-release-blocker}"; fact blocker_label "$BL"
    if bl=$(gh issue list --repo "$GH_REPO" --state open --label "$BL" --limit 20 --json number,title --jq '.[] | "\(.number)\t\(.title)"' 2>/dev/null); then
        fact blockers_known 1
        printf '%s\n' "$bl" | while IFS=$'\t' read -r bn bt; do [ -n "$bn" ] && printf 'blocker\t%s\t%s\n' "$bn" "$(printf '%s' "$bt" | cut -c1-100)"; done
    fi
    # The 0.5 panel's issues (#432): every open issue carrying the release's
    # label, and the lane on it (its `lane:` label; cloud when claimed there).
    if ri=$(gh issue list --repo "$GH_REPO" --state open --label "${STATUS_RELEASE_NAME:-0.5}" --limit 50 --json number,title,labels \
            --jq '.[] | "\(.number)\t\([.labels[].name | select(startswith("lane:")) | .[5:]] + [.labels[].name | select(. == "claimed:cloud") | "cloud"] | join(",") | if . == "" then "no lane" else "lane." + . end)\t\(.title)"' 2>/dev/null); then
        echo "r05issues_known"
        printf '%s\n' "$ri" | while IFS=$'\t' read -r rn rl rt; do [ -n "$rn" ] && printf 'r05issue\t%s\t%s\t%s\n' "$rn" "$rl" "$(printf '%s' "$rt" | cut -c1-100)"; done
    fi
fi
# The Ghoulies gate's measurement (#432), from the soaks that carry it. The
# title counts are NOT facts here any more: they are computed on the page from
# the 0.5 title table itself (status_html.py titles05), so a count can never
# disagree with its rows, and there is no "of 145" -- 145 is the per-minor quota
# from 0.6 on, not 0.5's target, which is release-0.5.toml's sentence.
fact release_gate_min "${STATUS_RELEASE_GATE_MIN:-25}"
timeout 60 python3 "$J/status_html.py" release05 --titles "${STATUS_TITLES_DIR:-$WORK/titles}" \
    --results "$D/results" --xiso "${HAKUX_XISO_DIR:-/mnt/d/hakux-staging/xiso}"
if [ $have_sd = 1 ]; then
    systemctl --user list-units 'hakux-*' --state=failed --no-legend --plain 2>/dev/null | awk '{print $1}' \
        | while read -r u; do [ -n "$u" ] && attn timer "$u has FAILED (systemctl --user status $u)"; done
    # An ACTIVE timer with no next elapse never fires again: unanchored. Not
    # while its service is running: an OnUnitInactiveSec timer shows no next
    # elapse for exactly as long as the run lasts, and is re-armed at its end.
    systemctl --user list-timers 'hakux-*' --no-legend --plain 2>/dev/null \
        | awk '$1 == "-" || $1 == "n/a" { for (i = 1; i <= NF; i++) if ($i ~ /\.timer$/) print $i }' \
        | while read -r u; do
            [ -n "$u" ] || continue
            case "$(systemctl --user is-active "${u%.timer}.service" 2>/dev/null)" in active|activating|reloading) continue ;; esac
            attn timer "$u is active but has no next run: it will not fire again until someone restarts it"
        done
fi
} > "$FACTS" 2>/dev/null
python3 "$J/status_html.py" build --facts "$FACTS" --lanes "$S/lanes.json" --md "$OUT" \
    --json "$S/status.json" --html "$S/index.html" 2>"$S/status_html.err" \
    || echo "the dashboard could not be rendered: $(tail -1 "$S/status_html.err")"

# ---- publishing: one commit on an orphan gh-pages branch, force-pushed.
#
# GitHub Pages branch builds are soft-limited to 10 an hour, and every job tick
# ends here. So: publish only when the content key (the page with the clock
# masked out, status_html.py key) moved, never twice inside PAGES_MIN_GAP, and
# otherwise at the heartbeat, so the page's own "updated N min ago" can tell a
# quiet fleet (republished within the heartbeat) from a stopped host (older).
# The git dir is a scratch one under $S, never the owner's checkout. There is
# no remote unless this is the real repository or a test names one: selftest
# drives this path with GH_REPO=example/hakux and must never reach the network.
PAGES_DIR="${STATUS_PAGES_DIR:-$S/pages}"
PAGES_REMOTE="${STATUS_PAGES_REMOTE-}"
[ -z "$PAGES_REMOTE" ] && [ "$GH_REPO" = jreinach-alt/hakuX ] && [ $have_gh = 1 ] && PAGES_REMOTE="https://github.com/$GH_REPO.git"
PAGES_MIN_GAP="${STATUS_PAGES_MIN_GAP:-600}"; case "$PAGES_MIN_GAP" in ''|*[!0-9]*) PAGES_MIN_GAP=600 ;; esac
PSTATE="$S/pages-state"          # "<epoch of the last publish> <its content key>"
publish_pages() {
    [ -n "$PAGES_REMOTE" ] || { echo "pages: no remote for $GH_REPO; not published"; return 0; }
    [ -s "$S/index.html" ] || { echo "pages: no page rendered; not published"; return 0; }
    local key last_t last_k age tree c
    key=$(python3 "$J/status_html.py" key "$S/index.html") || return 0
    last_t=0; last_k=""; [ -s "$PSTATE" ] && read -r last_t last_k < "$PSTATE"
    case "${last_t:-}" in ''|*[!0-9]*) last_t=0 ;; esac
    age=$(( now - last_t ))
    if [ "$key" = "${last_k:-}" ] && [ "$age" -lt "$HEARTBEAT" ]; then
        echo "pages: unchanged since $(local_ts "@$last_t"); not republished"; return 0
    fi
    if [ "$age" -lt "$PAGES_MIN_GAP" ]; then
        echo "pages: changed, but published $(( age / 60 )) min ago; the next tick after $(( PAGES_MIN_GAP / 60 )) min publishes it"; return 0
    fi
    [ -d "$PAGES_DIR/.git" ] || git init -q "$PAGES_DIR" 2>/dev/null || { echo "pages: cannot init $PAGES_DIR"; return 0; }
    cp "$S/index.html" "$PAGES_DIR/index.html" && : > "$PAGES_DIR/.nojekyll"
    git -C "$PAGES_DIR" add index.html .nojekyll 2>/dev/null
    tree=$(git -C "$PAGES_DIR" write-tree 2>/dev/null)
    # No parent, ever: the branch is this one commit.
    c=$(git -C "$PAGES_DIR" -c user.name=hakux-status -c user.email=hakux-status@users.noreply.github.com \
        commit-tree "$tree" -m "dashboard $(say_time)" 2>/dev/null)
    [ -n "$c" ] || { echo "pages: could not build the commit"; return 0; }
    if GIT_TERMINAL_PROMPT=0 timeout 120 git -C "$PAGES_DIR" push -q -f "$PAGES_REMOTE" "$c:refs/heads/gh-pages" 2>"$S/pages-push.log"; then
        echo "$now $key" > "$PSTATE"; echo "pages: published ${c:0:10} to gh-pages"
    else
        echo "pages: push failed: $(tail -1 "$S/pages-push.log" | cut -c1-160)"
    fi
}

[ "${1:-}" = "--print" ] && { cat "$OUT"; exit 0; }       # the page is rendered locally, never published
# --pages: publish the dashboard and touch nothing else (no stamp, no #107).
[ "${1:-}" = "--pages" ] && { publish_pages; exit 0; }
echo "$now" > "$STAMP"          # a real tick ran; --print is a dry run and does not count
publish_pages
[ $have_gh = 1 ] || { echo "wrote $OUT (gh unavailable; comment not updated)"; exit 0; }

# ================================================ #107: a pointer, switched ONCE
#
# Once the page has been published from here AND GitHub Pages serves it, #107 is
# rewritten one last time -- body, title, roll-up comment -- to point at the
# page, pinned, and locked; $POINTER records that, and from then on no tick
# touches the issue at all (no `renamed` rows, no edits). Until both hold, the
# legacy roll-up below keeps #107 current, so the owner is never left with
# neither.
POINTER="$S/issue-pointer"
if [ -s "$POINTER" ]; then
    echo "#$(cut -d' ' -f1 "$POINTER") points at the dashboard; not touched"
    exit 0
fi
pages_url=""
[ -s "$PSTATE" ] && pages_url=$(gh api "repos/$GH_REPO/pages" --jq .html_url 2>/dev/null)
case "$pages_url" in https://*) ;; *) pages_url="" ;; esac

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
if [ -n "$pages_url" ]; then
    [ -n "$issue" ] || { echo "the dashboard is live at $pages_url; no open harness-status issue to point at it"; exit 0; }
    PB="$S/POINTER.md"
    {
    echo "## hakuX harness status has moved"
    echo
    echo "### **$pages_url**"
    echo
    echo "One screen: the devices, the queue, running lanes, **NEEDS ATTENTION**, and the release gate, with the details below them. It is rewritten from the host at the end of every job tick and republished when it changes."
    echo
    echo "This issue stays pinned so the issue list still leads there, and is locked: nothing here is updated any more (switched $(say_time))."
    } > "$PB"
    if gh api -X PATCH "repos/$GH_REPO/issues/$issue" -F body=@"$PB" --silent >/dev/null 2>&1; then
        # The one rename left: the old title carried a clock and counts that
        # would otherwise read as current forever.
        [ "$cur_title" = "harness: live status -- moved to $pages_url" ] \
            || gh api -X PATCH "repos/$GH_REPO/issues/$issue" -f title="harness: live status -- moved to $pages_url" --silent >/dev/null 2>&1
        cid=$(cat "$S/comment-id" 2>/dev/null)
        [ -n "$cid" ] && gh api -X PATCH "repos/$GH_REPO/issues/comments/$cid" \
            -f body="The roll-up moved to **$pages_url**. This comment is no longer updated." --silent >/dev/null 2>&1
        gh issue pin "$issue" --repo "$GH_REPO" >/dev/null 2>&1       # already pinned is an error, and fine
        gh issue lock "$issue" --repo "$GH_REPO" >/dev/null 2>&1      # likewise already locked
        echo "$issue $pages_url $now" > "$POINTER"
        echo "#$issue now points at $pages_url (pinned, locked); status.sh will not touch it again"
    else
        echo "could not rewrite #$issue as a pointer; retrying next tick"
    fi
    exit 0
fi
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
echo "**Written $(say_time).** $summary."
# The condition the owner kept finding by hand, lifted from the lane table
# below (lanes_section writes it) to the first thing the page shows.
[ -s "$S/idle-lanes" ] && { echo; echo "**Idle with no work:** $(cat "$S/idle-lanes") -- unit stopped, nothing on a device, PR draft or none. See the lane table in the comment."; }
echo
echo "Next roll-up due by **$due** ($(( FLOOR / 60 ))-minute floor, plus one at the end of every job tick). If the clock above is older than that, \`status.sh\` itself has stopped -- the page cannot report its own silence, so judge it by this line."
if [ "$lapse" -gt 0 ]; then
    echo
    echo "> [!WARNING]"
    echo "> **The roll-up lapsed for $(ago "$prev_run" | sed 's/ ago$//') before this one** (previous tick $(local_ts "@$prev_run")). The state below is current; nothing was observed across that window."
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
#
# The clock is the display zone's ("21:00 PDT+"). $q is still quantised in
# epoch seconds, so a whole-hour offset keeps the same boundaries; the one
# rename this costs is the tick after the zone change lands.
q=$(( now - now % FLOOR ))
qt=$(local_ts "@$q")
want="harness: live status -- ${qt#* }+, $summary"
if [ "$want" != "$cur_title" ]; then
    gh api -X PATCH "repos/$GH_REPO/issues/$issue" -f title="$want" --silent >/dev/null 2>&1 \
        && echo "renamed #$issue: $want"
else
    echo "#$issue title unchanged"
fi
exit 0
