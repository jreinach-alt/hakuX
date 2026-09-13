#!/usr/bin/env bash
#
#   collect_sweep.sh <label> [dispatch-dir]
#
# Gather a dispatcher sweep's per-request score sheets into one labelled
# directory and regenerate the scoreboard.
#
# The full-corpus sweep is enqueued as ~100 idle-priority `z-sweep-*` requests
# so that agent measurements always sort ahead of it (see the queue-priority
# note in dispatcher.sh). That means its results land in ~100 separate result
# directories rather than one, while scoreboard.py wants a directory of TSVs.
# This bridges the two, and it is a script rather than a one-liner because it
# has to be run repeatedly as the sweep fills in.
#
# Only rows with progress-log proof are taken. A truncated run leaves the
# previous image in place and reads as a pass, and two W buffering arms were
# lost that way in one afternoon -- so an arm whose own log does not show the
# tests completing must not reach a scoreboard column, where it would look
# like an accuracy change rather than a crash.
set -u

HERE_PROV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="${1:?usage: collect_sweep.sh <label> [dispatch-dir]}"
D="${2:-/home/justin/hakux-work/dispatch}"
OUT="/home/justin/hakux-work/scoreboard/$LABEL"

mkdir -p "$OUT"
rm -f "$OUT"/*.tsv "$OUT/.refs"

taken=0 skipped_noproof=0 skipped_empty=0
for rdir in "$D"/results/z-sweep-*/; do
    [ -d "$rdir" ] || continue
    tsv="$rdir/scores1.tsv"
    [ -s "$tsv" ] || { skipped_empty=$((skipped_empty+1)); continue; }

    # progress_log_proof is the gate. Read it from result.json rather than
    # trusting the presence of the TSV.
    proof=$(python3 -c "
import json,sys
try:
    m=json.load(open(sys.argv[1]))
    r=(m.get('runs') or [{}])[0]
    print('yes' if r.get('progress_log_proof') else 'no')
except Exception:
    print('no')" "$rdir/result.json" 2>/dev/null)
    if [ "$proof" != "yes" ]; then
        skipped_noproof=$((skipped_noproof+1))
        echo "  skipped (no progress-log proof): $(basename "$rdir")"
        continue
    fi
    cp "$tsv" "$OUT/$(basename "$rdir").tsv"
    python3 -c "
import json,sys
try: print(json.load(open(sys.argv[1])).get('ref') or '')
except Exception: print('')" "$rdir/result.json" >> "$OUT/.refs"
    taken=$((taken+1))
done

# Provenance: WHICH binary is already recorded per row as apk_sha, but not WHEN
# it is. On 2026-09-12 a sweep column labelled "today-partial" was built from a
# binary 87 commits and 2,111 hw/ insertions behind the branch tip -- every
# correctness fix of that day was missing from it, and the table read as though
# the day had achieved nothing. The apk_sha column could not catch that: the
# sha was perfectly consistent, and consistently old.
#
# So record how far the scored ref is from the tip, counting only commits that
# touch hw/. Commits that do not change the build cannot change a score, and
# counting them would cry wolf on a day of heavy doc work -- which is exactly
# the day someone stops reading the warning.
if [ -s "$OUT/.refs" ]; then
    python3 "$HERE_PROV/sweep_provenance.py" "$OUT" "$(git rev-parse --short HEAD)"
fi
rm -f "$OUT/.refs"

echo "collected $taken sheets into $OUT"
[ "$skipped_noproof" -gt 0 ] && echo "  $skipped_noproof skipped for missing progress-log proof"
[ "$skipped_empty" -gt 0 ] && echo "  $skipped_empty skipped as empty or unscored"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNS=()
for d in /home/justin/hakux-work/scoreboard/*/; do
    [ -n "$(ls -A "$d"/*.tsv 2>/dev/null)" ] || continue
    RUNS+=(--run "$(basename "$d")=$d")
done

python3 "$HERE/scoreboard.py" "${RUNS[@]}" \
    --goldens /home/justin/goldens/results \
    --md "$HERE/SCOREBOARD.md"
