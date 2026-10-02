#!/bin/bash
# batch.sh <device> <outroot> <title>...: run pathfind.py on each title in turn,
# then copy the record (result, steps, calls, strip, gameplay frame) into
# docs/lanes/pathfind/runs/<slug>/. One title's failure does not stop the batch.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$HERE/../../testing/titles"
dev=$1; root=$2; shift 2
for t in "$@"; do
    slug=$(echo "$t" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9\n' '-' | sed 's/-*$//')
    out="$root/$slug"
    echo "=== $(date +%T) $t -> $out"
    python3 "$TOOLS/pathfind.py" "$t" --device "$dev" --budget-min "${BUDGET_MIN:-15}" --out "$out"
    echo "=== $(date +%T) $t exit $?"
    keep="$HERE/runs/$slug"
    mkdir -p "$keep"
    cp "$out"/result.json "$out"/steps.jsonl "$out"/calls.jsonl "$out"/strip.jpg "$keep"/ 2>/dev/null
    python3 - "$out" "$keep" <<'EOF'
import json, os, shutil, sys
out, keep = sys.argv[1:]
r = json.load(open(os.path.join(out, "result.json")))
for k in ("gameplay_frame", "last_frame"):
    if r.get(k) and os.path.exists(r[k]):
        shutil.copy(r[k], os.path.join(keep, k + ".jpg"))
EOF
done
