#!/bin/bash
# Re-score the two runs that carry the #297 rows with the scorer before this
# lane (036e6c191f) and with this tree's, then compare with rescore_cmp.py.
# Nothing under $DISPATCH_DIR is written; TSVs go to $1 (default /tmp/rescore297).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
OUT=${1:-/tmp/rescore297}
GOLDENS=${GOLDENS:-/home/justin/goldens/results}
RES=${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}/results
mkdir -p "$OUT"
git -C "$ROOT" show 036e6c191f:docs/testing/score_sweep.py > "$OUT/old_score_sweep.py"
for run in 1790373098-brdf315-964945 0-a-now-8e683b3a26-023-Depth_buffer_fixed_function; do
    for side in old new; do
        py="$ROOT/docs/testing/score_sweep.py"
        [ "$side" = old ] && py="$OUT/old_score_sweep.py"
        python3 "$py" --out "$RES/$run/captures1" --goldens "$GOLDENS" --flat \
            --tsv "$OUT/$run.$side.tsv" >/dev/null
    done
    echo "== $run"
    python3 "$HERE/rescore_cmp.py" "$OUT/$run.old.tsv" "$OUT/$run.new.tsv" \
        "$RES/$run/scores1.tsv"
done
