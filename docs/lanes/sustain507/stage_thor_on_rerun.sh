#!/usr/bin/env bash
# Part C: re-run the Thor Blinx halt-ON arm. The first one
# (1-1790593205-lane.sustain507-3238469) started at xo 53.8 C, above the
# prediction's 50 C admission, so it is reported and not scored, and the pair
# is not judged until an ON arm starts cold. The prediction's admission rule
# re-queues it for the next cold slot.
#
# This writes the request into a PRIVATE dispatch dir (the worktree's .stage/),
# so a warm Thor cannot claim it, then moves it into
# $DISPATCH_DIR/parked/sustain507-cold-20260928/ for hostops' coldslot.sh. The
# pilot gate still reads the real dir (PILOT_DISPATCH_DIR).
# Run from the worktree root.
set -u
REAL=${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}
STAGE=$PWD/.stage
mkdir -p "$STAGE/queue"
out=$(env DISPATCH_DIR="$STAGE" PILOT_DISPATCH_DIR="$REAL" HAKUX_RELEASE_PRIO=1 \
    docs/testing/request.sh --who lane.sustain507 --device thor --ref 9d777502fa \
    --title '4D530013-Blinx_The_Time_Sweeper.xiso.iso' --route survey --seconds 2160 \
    --env PERF_REGIMEN=default --env HAKUX_IDLE_HALT=1 \
    --expect docs/testing/predictions/sustain507-levers.json \
    --purpose "#507 Part C: Thor Blinx halt ON, re-run (3238469 started 53.8 C, not admitted); needs a COLD start (xo <= 50 C, battery <= 36 C)" 2>&1)
echo "$out"
id=$(printf '%s\n' "$out" | sed -n 's/^queued //p')
[ -n "$id" ] || { echo "stage: no id" >&2; exit 1; }
python3 - "$STAGE/queue/$id.req" "$REAL/parked/sustain507-cold-20260928" "$id" <<'PY'
import os, shutil, sys, time
src, dst, rid = sys.argv[1:4]
shutil.move(src, os.path.join(dst, rid + ".req"))
with open(os.path.join(dst, "README"), "a") as f:
    f.write("PARKED %s (lane.sustain507): %s = thor Blinx halt ON re-run; the first ON "
            "(3238469) started at xo 53.8 C and is not admitted. Needs a cold slot like the others "
            "(coldslot.sh thor bdc158a5 <this .req>).\n" % (time.strftime("%m-%d %H:%M UTC", time.gmtime()), rid))
print("parked", rid)
PY
