#!/usr/bin/env bash
#
# ops_escalate.sh <class> <subject> <evidence-file> <model> [escalation-number]
#
# One `claude -p` session for ONE jam ops_tick.py could not clear itself:
# either its scripted remedy survived 30+ minutes, or it has no scripted
# remedy at all. Modelled on run-claude-job.sh (same JSON log, same
# summarise_run.py index) but scoped to a single jam's evidence rather than
# a brief file, and on its own tool allowlist (allowed-tools.ops-escalate:
# no `gh`, no WebFetch -- GitHub stays untouched here, not just unused).
#
# Prints `COST_USD=<n>` on its last line of stdout; ops_tick.py reads it to
# total the day's escalation spend in jams.tsv/summary.txt. Logs the full
# run under $WORK/logs/ops-escalate/ the same way every other job logs,
# so the escalation has the same audit trail (no transcript-reading needed).
set -u
cls=${1:?class}; subject=${2:?subject}; evidence=${3:?evidence file}
model=${4:?model}; escnum=${5:-1}
JOBS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # .../docs/testing/jobs
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
[ -f "$evidence" ] || { echo "no evidence file at $evidence" >&2; exit 2; }

log="$WORK/logs/ops-escalate/$(date -u +%Y%m%dT%H%M%SZ)-$(echo "$cls-$subject" | tr -c 'A-Za-z0-9_.-' '_').json"
mkdir -p "$(dirname "$log")"

prompt="Jam escalation #$escnum for class '$cls', subject '$subject'. This is $( [ "$escnum" -ge 2 ] && echo "the SECOND (or later) escalation -- a prior session already tried and the jam is still open; read its remedy_tried note below before repeating it." || echo "the first escalation for this jam." )

Evidence (from \$OPS_STATE_DIR/evidence-*.txt):
$(cat "$evidence")
"

timeout "${OPS_ESCALATE_TIMEOUT:-20m}" claude -p "$prompt" \
    --model "$model" \
    --max-turns 40 \
    --output-format json \
    --permission-mode acceptEdits \
    --allowedTools "$(cat "$JOBS/ops/allowed-tools.ops-escalate")" \
    --append-system-prompt-file "$JOBS/ops/escalate-role.md" \
    > "$log" 2>&1
rc=$?
python3 "$JOBS/summarise_run.py" "$log" "ops-escalate-$cls" "$model" >> "$WORK/logs/ops-escalate/index.tsv"

cost=$(python3 -c "
import json, sys
try:
    raw = open('$log', encoding='utf-8', errors='replace').read()
    start = raw.find('{')
    d = json.loads(raw[start:raw.rfind('}') + 1]) if start >= 0 else {}
    print(d.get('total_cost_usd', 0) or 0)
except Exception:
    print(0)
")
echo "ops_escalate: $cls $subject on $model (escalation #$escnum) -> rc=$rc log=$log cost=\$$cost"
echo "COST_USD=$cost"
exit 0   # a capped or errored escalation is still logged and still costs money; ops_tick.py re-checks the jam next tick regardless
