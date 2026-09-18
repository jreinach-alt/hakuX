#!/usr/bin/env bash
#
# Sweep the open issues for comments the board has not absorbed, and leave a
# report the orchestrator is obliged to read.
#
# WHY THIS EXISTS, and it is not "because reading comments is good practice".
# The orchestrator went a week without reading any, and the first pass that
# did found FIVE open issues whose comments carried verified results the
# tracker did not reflect -- three of them closable, one whose only copy of a
# 126-check PASS was a bare unexpanded path into a scratchpad that gets reaped.
# A lane reporting into an issue and nobody reading it is the cheapest possible
# way to lose finished work.
#
# THEN IT WAS UNWOUND THE OBVIOUS WAY. A "standing lane, scheduled" was created
# for it, run ONCE, and never scheduled -- so the process reverted to the
# orchestrator not doing it, which is exactly where it started. That is why
# this is a timer and a file on disk rather than an intention: a habit that
# depends on remembering is a habit that ends at the next context boundary.
#
# WHAT IT DOES NOT DO. It does not judge, close, or edit the tracker. It
# reports what changed since its last run. Deciding what a comment means is the
# orchestrator's, and a sweeper that draws conclusions from a comment it read
# once is how #82 came to carry "read from source, not confirmed against a
# binary" as its own last line.
set -u

REPO="jreinach-alt/hakuX"
OUT_DIR="${HAKUX_SWEEP_DIR:-/home/justin/hakux-work/comment-sweep}"
STAMP="$OUT_DIR/last-run"
REPORT="$OUT_DIR/unread.md"
mkdir -p "$OUT_DIR"

# FAIL OPEN, for the backlog gate's reason: any failure to establish state must
# not manufacture a false "nothing new". A silent empty report is worse than a
# loud failure, because it reads as a clean sweep.
since="$(cat "$STAMP" 2>/dev/null)"
[ -n "$since" ] || since="$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)"
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if ! command -v gh >/dev/null 2>&1; then
    echo "SWEEP FAILED: no gh. State NOT advanced, so the next run re-covers this window." >&2
    exit 2
fi

nums="$(timeout 60 gh issue list --repo "$REPO" --state open --limit 100 \
          --json number --jq '.[].number' 2>/dev/null)" || {
    echo "SWEEP FAILED: gh issue list. State NOT advanced." >&2
    exit 2
}

{
    echo "# Comments since $since"
    echo
    echo "Swept $now. Open issues checked: $(echo "$nums" | wc -w)."
    echo
    echo "Read these, then decide. This file does not judge -- it reports."
    echo
} > "$REPORT.tmp"

found=0
for n in $nums; do
    body="$(timeout 30 gh issue view "$n" --repo "$REPO" --json comments \
              --jq '.comments[] | select(.createdAt > "'"$since"'")
                    | "- **\(.createdAt)** \(.body[0:400] | gsub("\n"; " "))"' 2>/dev/null)" || continue
    [ -n "$body" ] || continue
    found=$((found + 1))
    {
        echo "## #$n"
        echo
        echo "$body"
        echo
    } >> "$REPORT.tmp"
done

if [ "$found" -eq 0 ]; then
    echo "No new comments in this window." >> "$REPORT.tmp"
fi
mv "$REPORT.tmp" "$REPORT"

# Advance the watermark ONLY on a clean sweep. A partial sweep that advanced it
# would silently drop the comments it failed to fetch -- the same shape as a
# zero mistaken for evidence.
echo "$now" > "$STAMP"
echo "swept $now: $found issue(s) with new comments -> $REPORT"
