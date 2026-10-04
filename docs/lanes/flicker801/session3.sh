#!/usr/bin/env bash
# One Nova session of flicker bursts (#801): for each title, pathfind.py drives
# it into play and holds it there (model-free genre loop); once hold-play has
# started (hold.jsonl exists) this records 3 screenrecord bursts of 4 s, 20 s
# apart, and on the first title one back-to-back screencap burst, to measure
# why screencap is not the instrument.
#
#   session.sh <outroot> <title>...      (titles as pathfind.py takes them)
#
# Runs in a systemd --user unit (a tool call reaps setsid jobs). Takes the
# Nova with hold.sh wait (queues behind whoever holds it), waits for idle, and
# releases on every exit path, TERM included.
set -u
cd "$(dirname "$0")/../../.."
TAG=lane.flicker801
H=docs/testing/jobs/hold.sh
OUT=$1; shift
mkdir -p "$OUT"
log() { echo "$(date '+%F %T') $*"; }

log "waiting for the nova"
bash "$H" wait nova "$TAG" 21600 "lane.flicker801: flicker burst captures (#801): RalliSport + Orta + Halo, ~30 min" || { log "no hold"; exit 3; }
pf=
trap '[ -n "$pf" ] && kill "$pf" 2>/dev/null && adb -s ee317437 shell am force-stop com.jreinach.hakux.debug; bash "$H" release nova "$TAG"; log released' EXIT
trap 'exit 143' TERM INT
bash "$H" wait-idle nova 900 || { log "not idle"; exit 3; }
log "held and idle"
adb -s ee317437 shell dumpsys display > "$OUT/display.txt" 2>&1
adb -s ee317437 shell dumpsys SurfaceFlinger > "$OUT/surfaceflinger.txt" 2>&1

first=1
n=0
for arg in "$@"; do
  n=$((n+1))
  # claim:<title> bursts from pathfind's FIRST gameplay step (a race start, cars still together: RalliSport's
  # hold-play drives off alone in bumper view, run 1) instead of from hold-play
  t=${arg#claim:}; mode=hold; [ "$t" != "$arg" ] && mode=claim
  d="$OUT/$t-$mode-$n"; mkdir -p "$d"
  hs=150; [ "$mode" = claim ] && hs=0
  log "$t: pathfind start ($mode)"
  PATHFIND_KNOW=.flkscratch/know python3 docs/testing/titles/pathfind.py "$t" --device nova \
      --budget-min 12 --hold-s "$hs" --no-record --out "$d/pf" > "$d/pf.log" 2>&1 &
  pf=$!
  if [ "$mode" = claim ]; then
    ready() { grep -q -E '^\[ *[0-9.]+s\] # *[0-9]+ gameplay ' "$d/pf.log"; }
  else
    ready() { [ -s "$d/pf/hold.jsonl" ]; }
  fi
  while kill -0 "$pf" 2>/dev/null && ! ready; do sleep 1; done
  if ready; then
    log "$t: ready ($mode)"
    [ "$mode" = hold ] && sleep 8
    for i in 1 2 3; do
      secs=4; [ "$mode" = claim ] && [ "$i" = 1 ] && secs=8
      python3 docs/testing/burst_capture.py --device nova --hold-tag "$TAG" --seconds "$secs" \
          --out "$d/b$i" --note "$t hold-play burst $i" 2>&1 | sed "s/^/$t b$i: /"
      kill -0 "$pf" 2>/dev/null || break
      [ "$mode" = hold ] && sleep 15
    done
    if [ "$first" = 1 ] && kill -0 "$pf" 2>/dev/null; then
      python3 docs/testing/burst_capture.py --device nova --hold-tag "$TAG" --seconds 4 \
          --method caps --out "$d/caps" --note "$t screencap rate" 2>&1 | sed "s/^/$t caps: /"
    fi
  else
    log "$t: pathfind ended before $mode"
  fi
  wait "$pf"; log "$t: pathfind exit $?"
  first=0
done
log "done"
