# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# affinity: a free request leaves a handheld whose battery gate refuses it.
#
# WHY. On 2026-09-28 three arm pairs (ibcache, gpl569, tcg424flip) were queued
# with no `device` and rule 3 hashed all of them to the nova. The nova, at
# 35-39 % on its 500 mA port, refused them on every walk for 8-14 h (level 35
# < need 49.6) while the thor sat at 80-83 % and would have admitted them. It
# never saw them: the battery gate is asked only on the device affinity names.
# battery_admit.py now records each refusal (.battery_refused.<label>) and
# affinity.py passes over a device that has refused a key for
# AFFINITY_REFUSED_MOVE_S when another pooled device's level covers its need.
#
# The fixture is the incident: the real ids and prediction name (which really
# does hash to the nova), nova at 35 refusing at 49.6, thor at 80.
#
# Builds its own dispatch trees under $T/afbt*; touches nothing the other
# fragments read. Starts its own live pid and kills it at the end.

echo "== affinity: a free request leaves a handheld whose battery gate refuses it"
BT="$T/afbt"; rm -rf "$BT"; mkdir -p "$BT"/{lanes,queue,running,results,splits}
sleep 600 & BTLIVE=$!
printf '%s\n' "$BTLIVE" > "$BT/lanes/nova"; printf '%s\n' "$BTLIVE" > "$BT/lanes/thor"
BTK=ibcache-probe-pixels.json
BTA=1-1790639762-arms-ibcache-base-184395; BTB=1-1790639762-arms-ibcache-fix-184418
printf '%s\n' '{"requester":"arms-ibcache-base","expect":"/p/'"$BTK"'","runs":3}' > "$BT/queue/$BTA.req"
printf '%s\n' '{"requester":"arms-ibcache-fix","expect":"/p/'"$BTK"'","runs":3}'  > "$BT/queue/$BTB.req"
btaff() {  # <dispatch dir> <req> [python for affinity.py] -> its device
    python3 "${3:-$TESTING/affinity.py}" "$1" "$1/queue/$2.req" 2>/dev/null
}
btpair() { echo "$(btaff "$1" "$BTA" "${2:-}") $(btaff "$1" "$BTB" "${2:-}")"; }
btlevel() { printf '%s %s\n' "$(date +%s)" "$3" > "$1/.battery_level.$2"; }
btrefuse() {  # <dir> <label> <age s> <need> <level> <id>... -> the refusal record
    python3 - "$@" <<'PY'
import json, sys, time
d, label, age, need, level = sys.argv[1:6]
now = time.time()
json.dump({i: dict(since=now - float(age), t=now, need=float(need), level=float(level))
           for i in sys.argv[6:]}, open("%s/.battery_refused.%s" % (d, label), "w"))
PY
}

check "fixture: rule 3 alone hashes $BTK to the nova" \
    [ "$(python3 -c 'import hashlib,sys; print(["nova","thor"][int(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:8],16)%2])' "$BTK")" = nova ]
btlevel "$BT" nova 35; btlevel "$BT" thor 80
check "no refusal recorded: both arms go to the hash device, the nova" [ "$(btpair "$BT")" = "nova nova" ]

btrefuse "$BT" nova 900 49.6 35 "$BTA" "$BTB"
check "the nova has refused the pair for 15 min and the thor at 80 would admit it: both arms go to the thor" \
    [ "$(btpair "$BT")" = "thor thor" ]
check "and the move is noted where a reader can find it" [ -s "$BT/moves/$BTA.req.battery.txt" ]
check "and not as a split (status.sh reads splits/ as 'may span two devices')" \
    bash -c '[ -z "$(ls "$1"/splits 2>/dev/null)" ]' _ "$BT"
BTM="$BT/moves/$BTK.battery.json"
check "and the move is kept for the key, naming the thor" \
    python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["to"] == "thor" else 1)' "$BTM"

# THE CLAIM WINDOW (audit of #611, M1). The thor decided arm A, and while its
# battery gate is reading the level (A still in queue/, invisible to rule 2)
# the nova's level crosses the need it refused at. Re-derived from live state,
# arm B would hash back to the nova and be admitted there: a split pair. The
# kept move is followed instead.
btlevel "$BT" nova 55
check "M1: the nova's level crosses its need mid-claim; the pair still goes to the thor" \
    [ "$(btpair "$BT")" = "thor thor" ]
cp "$BTM" "$T/afbt-move.json"; rm -f "$BTM"
check "M1 (the check separates): with no kept move, the same state sends the pair back to the nova" \
    [ "$(btpair "$BT")" = "nova nova" ]
rm -f "$BTM"; cp "$T/afbt-move.json" "$BTM"
btrefuse "$BT" thor 60 90 80 "$BTA" "$BTB"
check "the kept move is given up only when its target refuses: back to the nova, which admits at 55" \
    [ "$(btpair "$BT")" = "nova nova" ]
check "and a claim that gives it up retires it" [ ! -e "$BTM" ]
rm -f "$BT/.battery_refused.thor"; btlevel "$BT" nova 35
check "a kept move naming none of the key's live ids has lapsed and is re-derived" \
    bash -c 'printf "%s\n" "{\"to\":\"nova\",\"ids\":[\"1-1-gone\"]}" > "$1"; [ "$(python3 "$2" "$3" "$3/queue/$4.req")" = thor ]' \
    _ "$BTM" "$TESTING/affinity.py" "$BT" "$BTA"
check "a question (CHOOSE pricing, notes off) writes no move" python3 -c '
import os, sys; sys.path.insert(0, sys.argv[1]); import affinity as a
p = sys.argv[2] + "/moves/" + sys.argv[3] + ".battery.json"
os.remove(p); a.decide(sys.argv[2], a.load(sys.argv[2] + "/queue/" + sys.argv[4] + ".req"), sys.argv[4] + ".req", notes=False)
sys.exit(1 if os.path.exists(p) else 0)' "$TESTING" "$BT" "$BTK" "$BTA"

# From here each check re-derives the move from its state, so the kept move is
# cleared first (`btfresh`).
btfresh() { rm -f "$BTM"; }
btfresh; btrefuse "$BT" nova 900 49.6 35 "$BTA"
check "one arm's refusal moves both (the pair shares the key)" [ "$(btpair "$BT")" = "thor thor" ]
btfresh; rm -f "$BT/.battery_level.thor"
check "a thor with no fresh level reading counts as admitting (it reads one when offered)" \
    [ "$(btpair "$BT")" = "thor thor" ]
btlevel "$BT" thor 80

# MUTANT: affinity.py without its battery rule (a lone copy, _ba None) is the
# old rule 3, and must fail the move check above.
mkdir -p "$T/afbt-m"; cp "$TESTING/affinity.py" "$T/afbt-m/"
check "MUTANT: affinity.py without battery_admit beside it sends the refused pair to the nova" \
    [ "$(btpair "$BT" "$T/afbt-m/affinity.py")" = "nova nova" ]

# Controls: every other state gives the answer it always did.
btfresh; btrefuse "$BT" nova 300 49.6 35 "$BTA" "$BTB"
check "CONTROL: refused for only 5 min, the pair stays on the nova" [ "$(btpair "$BT")" = "nova nova" ]
btfresh; btrefuse "$BT" nova 900 49.6 35 "$BTA" "$BTB"; btrefuse "$BT" thor 60 90 80 "$BTA" "$BTB"
check "CONTROL: the thor refusing too, the pair stays on the hash device" [ "$(btpair "$BT")" = "nova nova" ]
btfresh; rm -f "$BT/.battery_refused.thor"; btlevel "$BT" thor 15
check "CONTROL: the thor's level below its own need, the pair stays on the hash device" [ "$(btpair "$BT")" = "nova nova" ]
btfresh; btlevel "$BT" thor 80; btlevel "$BT" nova 55
check "CONTROL: no move kept and the nova's level now covers the need it refused at: the nova" \
    [ "$(btpair "$BT")" = "nova nova" ]
btfresh; btlevel "$BT" nova 35
printf '%s\n' "$BTLIVE" > "$BT/lanes/desktop"; rm -f "$BT/lanes/thor"
check "CONTROL: no other POOLED device serving (thor gone, desktop off-pool), no move: the pair is free" \
    [ "$(btpair "$BT")" = " " ]
printf '%s\n' "$BTLIVE" > "$BT/lanes/thor"; rm -f "$BT/lanes/desktop"
check "(the pair is back on the thor with it serving again)" [ "$(btpair "$BT")" = "thor thor" ]

# Rule 2 still outranks the battery: an arm that already RAN on the nova pulls
# its partner there. The move is for a pair where nothing has landed.
mkdir -p "$BT/results/r-base"
printf '%s\n' '{"expect":"/p/'"$BTK"'"}' > "$BT/results/r-base/request.json"
printf '%s\n' '{"device_label":"nova"}' > "$BT/results/r-base/result.json"
check "CONTROL: a sibling that ran on the nova still pulls its partner there" \
    [ "$(btaff "$BT" "$BTB")" = nova ]
rm -rf "$BT/results/r-base"

# A load pin (arms.sh --choose) is a preference: refused on battery, it falls
# through like a pin to a held device, and both arms move together. A hand pin
# stays absolute.
btfresh; sed -i 's/"runs":3}/"runs":3,"device":"nova"}/' "$BT/queue/$BTA.req" "$BT/queue/$BTB.req"
check "an arms-job load pin to the refusing nova falls through, both arms to the thor" \
    [ "$(btpair "$BT")" = "thor thor" ]
printf '%s\n' '{"requester":"titleplay","device":"nova","title":"t","seconds":60}' > "$BT/queue/1-1790639800-hand.req"
btrefuse "$BT" nova 900 49.6 35 "$BTA" "$BTB" 1-1790639800-hand
check "CONTROL: a hand pin to the refusing nova still holds (rule 1)" [ "$(btaff "$BT" 1-1790639800-hand)" = nova ]
btfresh; btrefuse "$BT" nova 300 49.6 35 "$BTA" "$BTB"
check "CONTROL: a load pin refused for only 5 min holds" [ "$(btpair "$BT")" = "nova nova" ]

# --- the writer. battery_admit.py check records a refusal and clears it on
# admission, and prunes ids that left the queue; the per-request line keeps
# naming the id and the device.
BW="$T/afbt-w"; rm -rf "$BW"; mkdir -p "$BW"/{queue,running,results}
cp "$BT/queue/$BTA.req" "$BT/queue/$BTB.req" "$BW/queue/"
btout=$(env -u BATTERY_FLOOR_nova python3 "$TESTING/battery_admit.py" check "$BW" nova "$BW/queue/$BTA.req" 35 "" | head -1)
check "a refusal still logs its id and device" grep -q "^BATTERY: skip $BTA on nova: level 35 < need" <<< "$btout"
check "and is recorded with its need and level" python3 -c '
import json, sys
r = json.load(open(sys.argv[1] + "/.battery_refused.nova"))[sys.argv[2]]
sys.exit(0 if r["level"] == 35 and r["need"] > 35 and r["since"] <= r["t"] else 1)' "$BW" "$BTA"
btsince=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]+"/.battery_refused.nova"))[sys.argv[2]]["since"])' "$BW" "$BTA")
env -u BATTERY_FLOOR_nova python3 "$TESTING/battery_admit.py" check "$BW" nova "$BW/queue/$BTA.req" 34 "" >/dev/null
check "a repeated refusal keeps its first 'since'" python3 -c '
import json, sys
sys.exit(0 if json.load(open(sys.argv[1]+"/.battery_refused.nova"))[sys.argv[2]]["since"] == float(sys.argv[3]) else 1)' "$BW" "$BTA" "$btsince"
env -u BATTERY_FLOOR_nova python3 "$TESTING/battery_admit.py" check "$BW" nova "$BW/queue/$BTB.req" 35 "$BTA" >/dev/null
check "a refusal behind the head is recorded too" python3 -c '
import json, sys; sys.exit(0 if sys.argv[2] in json.load(open(sys.argv[1]+"/.battery_refused.nova")) else 1)' "$BW" "$BTB"
btout=$(env -u BATTERY_FLOOR_nova python3 "$TESTING/battery_admit.py" check "$BW" nova "$BW/queue/$BTA.req" 90 "" | head -1)
check "an admission logs its id and device" grep -q "^BATTERY: admit $BTA on nova: level 90 >= need" <<< "$btout"
check "and clears that id's refusal, not its sibling's" python3 -c '
import json, sys; r = json.load(open(sys.argv[1]+"/.battery_refused.nova")); sys.exit(0 if sys.argv[2] not in r and sys.argv[3] in r else 1)' "$BW" "$BTA" "$BTB"
rm -f "$BW/queue/$BTB.req"
printf '%s\n' '{"requester":"x","runs":1}' > "$BW/queue/1-1790639900-x.req"
env -u BATTERY_FLOOR_nova python3 "$TESTING/battery_admit.py" check "$BW" nova "$BW/queue/1-1790639900-x.req" 10 "" >/dev/null
check "a write prunes ids that left the queue" python3 -c '
import json, sys; r = json.load(open(sys.argv[1]+"/.battery_refused.nova")); sys.exit(0 if list(r) == ["1-1790639900-x"] else 1)' "$BW"

# --- the replay, end to end through both files: the nova's own check writes
# the refusal, fifteen minutes pass, and the thor's worker is then sent the pair.
BR="$T/afbt-r"; rm -rf "$BR"; mkdir -p "$BR"/{lanes,queue,running,results}
cp "$BT/lanes/nova" "$BT/lanes/thor" "$BR/lanes/"
printf '%s\n' '{"requester":"arms-ibcache-base","expect":"/p/'"$BTK"'","runs":3}' > "$BR/queue/$BTA.req"
printf '%s\n' '{"requester":"arms-ibcache-fix","expect":"/p/'"$BTK"'","runs":3}'  > "$BR/queue/$BTB.req"
btlevel "$BR" nova 35; btlevel "$BR" thor 80
env -u BATTERY_FLOOR_nova python3 "$TESTING/battery_admit.py" check "$BR" nova "$BR/queue/$BTA.req" 35 "" >/dev/null
env -u BATTERY_FLOOR_nova python3 "$TESTING/battery_admit.py" check "$BR" nova "$BR/queue/$BTB.req" 35 "$BTA" >/dev/null
check "replay: just refused, the pair is still the nova's" [ "$(btpair "$BR")" = "nova nova" ]
check "replay: fifteen minutes on (AFFINITY_REFUSED_MOVE_S=0 stands in), the pair is the thor's" \
    [ "$(env AFFINITY_REFUSED_MOVE_S=0 python3 "$TESTING/affinity.py" "$BR" "$BR/queue/$BTA.req") $(env AFFINITY_REFUSED_MOVE_S=0 python3 "$TESTING/affinity.py" "$BR" "$BR/queue/$BTB.req")" = "thor thor" ]
check "replay: and the thor admits it (level 80 >= its own need)" \
    python3 "$TESTING/battery_admit.py" check "$BR" thor "$BR/queue/$BTA.req" 80 ""

kill "$BTLIVE" 2>/dev/null; wait "$BTLIVE" 2>/dev/null
