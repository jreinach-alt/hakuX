#!/usr/bin/env bash
#
# Is the harness doing anything? One screen, from the host.
#
#   docs/testing/jobs/board-status.sh
#
# Added the first evening the board job ran, when the owner asked exactly
# that and the answer was spread over a timer, a service, three logs and a
# TSV. A "nothing actionable" tick leaves no trace on GitHub by design, so
# the only place liveness is visible is here.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
D="${DISPATCH_DIR:-$WORK/dispatch}"
L="$WORK/logs/board"
now=$(date +%s)
ago() { local t=$1; [ -n "$t" ] || { echo "never"; return; }; local s=$(( now - t )); if [ $s -lt 120 ]; then echo "${s}s ago"; elif [ $s -lt 7200 ]; then echo "$(( s / 60 ))m ago"; else echo "$(( s / 3600 ))h ago"; fi; }

echo "== board timer"
systemctl --user list-timers hakux-board.timer --no-legend --no-pager 2>/dev/null | awk '{print "   next elapse: "$1" "$2" "$3"   last: "$5" "$6" "$7}' || echo "   (systemctl --user not available)"
st=$(systemctl --user show hakux-board.service -p Result -p ExecMainStatus -p ActiveState --no-pager 2>/dev/null | tr '\n' ' ')
echo "   service: ${st:-unknown}"

echo "== ticks (tail of $L/tick.log)"
if [ -f "$L/tick.log" ]; then
    tail -6 "$L/tick.log" | sed 's/^/   /'
    last=$(stat -c %Y "$L/tick.log"); echo "   last tick line written $(ago "$last")"
else
    echo "   no tick.log yet -- the timer has not fired, or board.sh could not start"
fi

echo "== model runs (tail of $L/index.tsv: time job turns secs cost ok/ERR log first-line)"
if [ -f "$L/index.tsv" ]; then tail -5 "$L/index.tsv" | sed 's/^/   /'; else echo "   none yet -- every tick so far found nothing actionable, or never reached claude -p"; fi
for j in "$L"/*.json; do [ -e "$j" ] || break; done
latest=$(ls -t "$L"/*.json 2>/dev/null | head -1)
if [ -n "$latest" ]; then
    echo "   latest run log: $latest ($(wc -c < "$latest") bytes)"
    if grep -q 'command not found' "$latest" 2>/dev/null; then
        echo "   !! 'command not found' in the run log: the unit's PATH lacks claude or gh."
        echo "      Fix: Environment=PATH=... in hakux-board.service, or symlink into /usr/local/bin."
    fi
    grep -o '"is_error": *[a-z]*' "$latest" | head -1 | sed 's/^/   /'
fi

echo "== systemd log (tail of $L/systemd.log)"
[ -f "$L/systemd.log" ] && tail -5 "$L/systemd.log" | sed 's/^/   /' || echo "   none"

echo "== host checkout (ExecStart paths live here; the jobs re-exec from the fetched trunk)"
R="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
echo "   $R on $(git -C "$R" rev-parse --abbrev-ref HEAD 2>/dev/null), $(git -C "$R" rev-list --count HEAD..origin/master 2>/dev/null || echo '?') behind origin/master"
echo "   lanes running: $(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend 2>/dev/null | wc -l) (cap: $(. "$WORK/limits.env" 2>/dev/null; echo "${LANE_MAX:-2}"))"
echo "   attempts: $(for f in "$WORK"/attempts/*; do [ -e "$f" ] && printf '%s=%s ' "$(basename "$f")" "$(cat "$f")"; done)"

echo "== dispatcher"
systemctl --user is-active hakux-dispatcher.service 2>/dev/null | sed 's/^/   service: /'
echo "   queue: $(ls "$D"/queue/*.req 2>/dev/null | wc -l) waiting, running: $(ls "$D"/running/*.req 2>/dev/null | wc -l), results: $(ls -d "$D"/results/*/ 2>/dev/null | wc -l)"
[ -f "$D/logs/dispatcher.log" ] && echo "   last line: $(tail -1 "$D/logs/dispatcher.log")"
holds=$(ls "$D"/hold 2>/dev/null | grep -v '\.why$' | grep -v '^lifted$' | tr '\n' ' ')
echo "   holds: ${holds:-none}"

echo "== arms job (queues registered predictions; judges pairs)"
A="$WORK/arms"
if [ -d "$A" ]; then
    pend=0; for p in "$A"/pairs/*.json; do [ -f "$p" ] || continue; [ -f "$A/judged/$(basename "$p" .json)" ] || pend=$((pend+1)); done
    echo "   $pend pair(s) awaiting a verdict, $(ls "$A"/judged 2>/dev/null | wc -l) judged, $(ls "$A"/skipped 2>/dev/null | wc -l) skipped; watermark $(cat "$A/since" 2>/dev/null)"
    [ -f "$WORK/logs/arms/tick.log" ] && tail -3 "$WORK/logs/arms/tick.log" | sed 's/^/   /'
else echo "   not installed (install-host.sh)"; fi
echo "== fold job"
[ -f "$WORK/logs/fold/tick.log" ] && tail -3 "$WORK/logs/fold/tick.log" | sed 's/^/   /' || echo "   no fold tick yet"
echo "== status roll-up: $WORK/status/STATUS.md ($( [ -f "$WORK/status/STATUS.md" ] && ago "$(stat -c %Y "$WORK/status/STATUS.md")" || echo never )); the same text is the comment on the harness-status issue"

echo "== what the board changed on GitHub (needs gh)"
if command -v gh >/dev/null 2>&1; then
    gh api 'repos/jreinach-alt/hakuX/issues/comments?since='"$(date -u -d '24 hours ago' +%FT%TZ)"'&per_page=100' \
        --jq '.[] | select(.body | startswith("[job.")) | "   \(.created_at) \(.html_url)"' 2>/dev/null | tail -5
    echo "   board branch: $(git -C "${HAKUX_REPO_DIR:-/home/justin/hakuX}" log -1 --format='%h %cr %s' origin/board 2>/dev/null || echo unknown)"
else
    echo "   gh not on PATH here"
fi
