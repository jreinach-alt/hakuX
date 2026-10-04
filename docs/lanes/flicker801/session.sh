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
for t in "$@"; do
  d="$OUT/$t"; mkdir -p "$d"
  log "$t: pathfind start"
  PATHFIND_KNOW=.flkscratch/know python3 docs/testing/titles/pathfind.py "$t" --device nova \
      --budget-min 12 --hold-s 150 --no-record --out "$d/pf" > "$d/pf.log" 2>&1 &
  pf=$!
  while kill -0 "$pf" 2>/dev/null && [ ! -s "$d/pf/hold.jsonl" ]; do sleep 5; done
  if [ -s "$d/pf/hold.jsonl" ]; then
    log "$t: in hold-play"
    sleep 8
    for i in 1 2 3; do
      python3 docs/testing/burst_capture.py --device nova --hold-tag "$TAG" --seconds 4 \
          --out "$d/b$i" --note "$t hold-play burst $i" 2>&1 | sed "s/^/$t b$i: /"
      kill -0 "$pf" 2>/dev/null || break
      sleep 15
    done
    if [ "$first" = 1 ] && kill -0 "$pf" 2>/dev/null; then
      python3 docs/testing/burst_capture.py --device nova --hold-tag "$TAG" --seconds 4 \
          --method caps --out "$d/caps" --note "$t screencap rate" 2>&1 | sed "s/^/$t caps: /"
    fi
  else
    log "$t: pathfind ended before hold-play"
  fi
  wait "$pf"; log "$t: pathfind exit $?"
  first=0
done
log "done"
