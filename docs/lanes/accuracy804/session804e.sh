#!/usr/bin/env bash
# One held Nova session for #804 (lane.accuracy804, addendum 10-04 16:00 PDT): does a PLAIN build
# (non-perflog debug app, no frame dump) of master blink on RalliSport's rival pass?
#
#   session804e.sh <outroot> [runs] [apk]
#
# Takes the Nova with hold.sh take + wait-idle, touches it only on exit 0 of both, and releases on
# every exit path. Records what is installed (APK sha256 against [apk], the env_vars pref), then per
# run: composes the titles disk (titlestate.prepare, the dispatcher's plan), launches RalliSport as
# pathfind does, plays rallisport-804e.route (804d's path, no screencap in the race; it ends at race
# clock ~4) and takes one screenrecord burst (burst_capture.py, which scores it with
# flicker_score.py). A second run happens only when the first scores p90 <= 5 (clean).
set -u
cd "$(dirname "$0")/../../.."
TAG=lane.accuracy804
H=docs/testing/jobs/hold.sh
S=ee317437
PKG=com.jreinach.hakux.debug
ISO=/storage/E6C6-D7AA/Games/XBox/4D53000F-RalliSport_Challenge.xiso.iso
ROUTE=docs/lanes/accuracy804/rallisport-804e.route
OUT=$1; RUNS=${2:-2}; APK=${3:-}
mkdir -p "$OUT"
# the host has no ffmpeg; flicker801's venv has imageio-ffmpeg's static binary (flicker_score.find_ffmpeg)
export FFMPEG=${FFMPEG:-/home/justin/hakux-work/wt/flicker801/.flkvenv/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2}
log() { echo "$(date '+%F %T') $*" | tee -a "$OUT/session.log"; }
A() { timeout 60 adb -s "$S" "$@"; }

bash "$H" take nova "$TAG" "RalliSport 804d video (#804): plain master build, 1-2 screenrecord bursts, ~12 min" \
    || { log "no hold"; exit 3; }
rp=; lp=; prepared=0
cleanup() {
    [ -n "$rp" ] && kill "$rp" 2>/dev/null
    [ -n "$lp" ] && kill "$lp" 2>/dev/null
    [ "$prepared" = 1 ] && python3 -c 'import sys; sys.path.insert(0, "docs/testing/titles"); import titlestate
titlestate.release("nova", log=lambda m: print(m, file=sys.stderr))' 2>>"$OUT/session.log"
    A shell am force-stop "$PKG"
    A shell input keyevent 223
    bash "$H" release nova "$TAG"; log "released"
}
trap cleanup EXIT
trap 'exit 143' TERM INT
bash "$H" wait-idle nova "${IDLE_S:-900}" || { log "not idle"; exit 3; }
log "held and idle"

# What will run: the installed APK and the env the app will read.
apkpath=$(A shell pm path "$PKG" | sed -n 's/^package://p' | tr -d '\r' | head -1)
dev_sha=$(A shell sha256sum "$apkpath" | awk '{print $1}')
log "installed $PKG at $apkpath sha256 $dev_sha"
if [ -n "$APK" ]; then
    want=$(sha256sum "$APK" | awk '{print $1}')
    log "wanted $APK sha256 $want"
    [ "$dev_sha" = "$want" ] || { log "installed APK is not the wanted build; stopping (no install by hand)"; exit 4; }
fi
A shell "run-as $PKG cat shared_prefs/x1box_prefs.xml" > "$OUT/x1box_prefs.xml"
grep -o '<string name="env_vars">[^<]*</string>' "$OUT/x1box_prefs.xml" | tee -a "$OUT/session.log"
grep -q '<string name="env_vars">[^<]' "$OUT/x1box_prefs.xml" && { log "env_vars is not empty; stopping"; exit 4; }
log "env_vars empty or absent"

spec=$(cd docs/testing/titles && python3 -c 'import pathfind; print(pathfind.LOGCAT_SPEC)')
for i in $(seq 1 "$RUNS"); do
    d="$OUT/run$i"; mkdir -p "$d"
    python3 -c 'import sys, json; sys.path.insert(0, "docs/testing/titles"); import titlestate
print(json.dumps(titlestate.prepare("nova", "4D53000F", "any", log=lambda m: print(m, file=sys.stderr)), indent=1))' \
        > "$d/hdd.json" 2>>"$OUT/session.log" || { log "run$i: titlestate.prepare refused"; exit 5; }
    prepared=1
    log "run$i: disk composed"
    A shell am force-stop "$PKG"
    A shell input keyevent KEYCODE_WAKEUP
    sleep 1.5
    adb -s "$S" logcat -v time -T 1 $spec > "$d/logcat.txt" 2>/dev/null &
    lp=$!
    A shell "am start -a android.intent.action.VIEW -n $PKG/com.rfandango.haku_x.LauncherActivity --es rom_path '$ISO'"
    SERIAL=$S bash docs/testing/perf/pad.sh detect >/dev/null 2>&1
    log "run$i: launched; route start"
    SERIAL=$S ROUTE_FRAMES="$d/route-frames" bash docs/testing/titles/route.sh "$ROUTE" > "$d/route.log" 2>&1 &
    rp=$!
    wait "$rp"; rc=$?; rp=
    log "run$i: route exit $rc"
    python3 docs/testing/burst_capture.py --device nova --hold-tag "$TAG" --seconds 6 --out "$d/b1" \
        --note "RalliSport rival pass, plain master, run $i" 2>&1 | tee -a "$OUT/session.log"
    A shell screencap -p /sdcard/Download/a804.png && A pull /sdcard/Download/a804.png "$d/after.png" >/dev/null
    A shell rm -f /sdcard/Download/a804.png
    kill "$lp" 2>/dev/null; lp=
    A shell am force-stop "$PKG"
    python3 -c 'import sys; sys.path.insert(0, "docs/testing/titles"); import titlestate
titlestate.release("nova", log=lambda m: print(m, file=sys.stderr))' 2>>"$OUT/session.log"
    prepared=0
    p90=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["flicker"].get("p90", -1))' "$d/b1/capture.json" 2>/dev/null)
    log "run$i: p90 $p90"
    python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) > 5 else 1)' "${p90:--1}" && { log "run$i scores a blink; no second run"; break; }
done
log "done"
