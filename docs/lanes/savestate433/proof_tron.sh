#!/usr/bin/env bash
# lane.savestate433 device proof: Tron 2.0's Single Player menu on the Nova,
# booted once from the composed disk for `returning` (its golden, with its
# autosaves) and once for `first-run` (no Tron save). Two held runs, ~3 min
# each. Everything goes through titlestate.py prepare/release (the held-
# session path nav.py and pathfind.py now use); the hold is taken with
# hold.sh and released on every exit.
#
#   bash docs/lanes/savestate433/proof_tron.sh <out dir>
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
T="$HERE/../../testing"
OUT="${1:?out dir}"; mkdir -p "$OUT"
S=ee317437; DEV=nova; TID=42560001
PKG=com.jreinach.hakux.debug; ACT="$PKG/com.rfandango.haku_x.LauncherActivity"
ISO="Tron 2.0 - Killer App (USA, Europe).iso"
say() { echo "$(TZ=America/Los_Angeles date '+%H:%M:%S') $*" | tee -a "$OUT/proof.log"; }
a() { timeout 60 adb -s "$S" "$@"; }

bash "$T/jobs/hold.sh" take "$DEV" lane.savestate433 \
    "lane.savestate433 #433: 2 held Tron 2.0 boots to its menu (returning vs first-run titles disk), ~8 min" \
    || { say "nova is held by someone else"; exit 3; }
trap 'a shell am force-stop $PKG >/dev/null 2>&1; python3 "$T/titles/titlestate.py" release --device $DEV --run proof-exit >> "$OUT/proof.log" 2>&1; bash "$T/jobs/hold.sh" release $DEV lane.savestate433; say "hold released"' EXIT
bash "$T/jobs/hold.sh" wait-idle "$DEV" 900 || { say "nova not idle"; exit 3; }
lvl=$(a shell dumpsys battery | tr -d '\r' | awk '/level:/{print $2; exit}')
say "battery $lvl"
[ -n "$lvl" ] && [ "$lvl" -ge 35 ] || { say "battery below 35 or unreadable"; exit 4; }
ISOPATH=$(a shell "ls '/storage/E6C6-D7AA/Games/XBox/$ISO'" 2>/dev/null | tr -d '\r' | grep -v 'No such' | head -1)
[ -n "$ISOPATH" ] || { say "no $ISO on the Nova"; exit 5; }

for st in returning first-run; do
    d="$OUT/$st"; mkdir -p "$d"
    say "== $st: prepare"
    python3 "$T/titles/titlestate.py" prepare --device $DEV --title-id $TID --state "$st" --run "proof-$st" \
        > "$d/hdd.json" 2>> "$OUT/proof.log" || { say "prepare $st failed"; exit 6; }
    say "  loaded: $(python3 -c 'import json,sys;h=json.load(open(sys.argv[1]));print(h["loaded"], h["save"])' "$d/hdd.json")"
    a shell "run-as $PKG cat shared_prefs/x1box_prefs.xml" | tr -d '\r' | grep hddPath > "$d/hddPath.txt"
    say "  pref: $(cat "$d/hddPath.txt" | sed 's/^ *//')"
    a shell am force-stop $PKG
    a shell input keyevent KEYCODE_WAKEUP; sleep 1.5
    a shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path '$ISOPATH'" >/dev/null
    SERIAL=$S ROUTE_FRAMES="$d/frames" bash "$T/titles/route.sh" "$HERE/tron-menu.route" >> "$d/route.log" 2>&1
    say "  route rc $? ; frames: $(ls "$d/frames" | wc -l)"
    a shell am force-stop $PKG
    python3 "$T/titles/titlestate.py" release --device $DEV --run "proof-$st" > "$d/release.json" 2>> "$OUT/proof.log"
    say "  released: $(head -c 300 "$d/release.json")"
done
say "done"
