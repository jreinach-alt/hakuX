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
# Overridable so the selftest (88-sweep-cover.sh) can run this whole script
# on a fixture without writing a column into the live board or SCOREBOARD.md.
SB_ROOT="${SCOREBOARD_ROOT:-/home/justin/hakux-work/scoreboard}"
SB_GOLDENS="${SCOREBOARD_GOLDENS:-/home/justin/goldens/results}"
OUT="$SB_ROOT/$LABEL"
# The request prefix, which is not always the column name: the first
# full-corpus sweep was queued as `z-sweep-*` before queue_full_sweep.sh
# existed, and its column is named for the binary it measured.
SWEEP_LABEL="${SWEEP_LABEL:-$LABEL}"
case "$LABEL" in pre-fixes-*) SWEEP_LABEL=sweep ;; esac

mkdir -p "$OUT"
rm -f "$OUT"/*.tsv "$OUT/.refs"

taken=0 skipped_noproof=0 skipped_empty=0 void_rows=0 void_sheets=0
seen_dirs=""
# Collect the label that was asked for. This globbed `z-sweep-*` regardless of
# the LABEL argument, which worked only while every sweep was called "sweep" --
# queue_full_sweep.sh names its requests `z-<label>-NNN-<Suite>`, so an
# after-sweep queued as `after` produced 100 results this could not see and
# would have reported an empty column rather than an error.
# Strictly this label's requests. The first version of this fix also globbed
# `z-sweep-*` as a fallback, which would have pulled the BEFORE column's 100
# results into the AFTER column -- the exact silent mixing this file's
# provenance record exists to catch, reintroduced while fixing something else.
# A label with no results is an empty column and says so; that is the right
# failure.
for rdir in "$D"/results/z-"$SWEEP_LABEL"-*/; do
    [ -d "$rdir" ] || continue
    case " $seen_dirs " in *" $rdir "*) continue;; esac
    seen_dirs="$seen_dirs $rdir"
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
    # Void rows are TAKEN, not skipped: scoreboard.py counts them as void, so
    # the column says how much of it was unmeasured. Named here per sheet
    # because a sheet with 56 unreadable rows passed the proof gate above --
    # the tests ran; the pull truncated their PNGs -- and read as 56 exact.
    v=$(python3 -c "
import csv,sys
sys.path.insert(0, sys.argv[2])
from scoreboard import is_scored
rows=[r for r in csv.DictReader(open(sys.argv[1]), delimiter='\t') if r.get('suite')]
print(sum(not is_scored(r) for r in rows))" "$tsv" "$HERE_PROV" 2>/dev/null)
    case "$v" in ''|*[!0-9]*) v=0; echo "  could not read statuses: $(basename "$rdir")" ;; esac
    if [ "$v" -gt 0 ]; then
        void_rows=$((void_rows+v)); void_sheets=$((void_sheets+1))
        echo "  $v void row(s) (status not scored): $(basename "$rdir")"
    fi
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
[ "$void_rows" -gt 0 ] && echo "  $void_rows VOID row(s) in $void_sheets sheet(s): not exact, not scored -- see the column's void count"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNS=()
for d in "$SB_ROOT"/*/; do
    [ -n "$(ls -A "$d"/*.tsv 2>/dev/null)" ] || continue
    RUNS+=(--run "$(basename "$d")=$d")
done

python3 "$HERE/scoreboard.py" "${RUNS[@]}" \
    --goldens "$SB_GOLDENS" \
    --md "${SCOREBOARD_MD:-$HERE/SCOREBOARD.md}"

# NAME THE GATE AT THE POINT SOMEONE IS ABOUT TO NEED IT.
#
# A fresh column exists for exactly one reason: to be compared with another
# one. That comparison is where #75 came from -- two columns diffed by hand,
# three movers read as a regression, a suspect commit named and a lane spawned
# to bisect nothing. `sweep_diff.py` refuses that attribution until a same-ref
# repeat exists, and it exits non-zero rather than warning.
#
# Printed rather than run, and deliberately: this script has just written a
# column, and which OTHER column is the meaningful comparison is a judgement
# nobody here can make. Naming the command with the arguments filled in is the
# most this can honestly do -- and it is what the rule in AGENTS.md asks for,
# at the moment the reader is looking.
OTHERS=$(for d in "$SB_ROOT"/*/; do
             b=$(basename "$d"); [ "$b" = "$LABEL" ] || printf '%s ' "$b"
         done)
if [ -n "$OTHERS" ]; then
    echo
    echo "before attributing any difference between this column and another to a"
    echo "commit, run the gate -- a one-run-per-suite column cannot tell a change"
    echo "from a suite's own variance:"
    for o in $OTHERS; do
        echo "    python3 $HERE/sweep_diff.py $o $LABEL"
    done
fi
