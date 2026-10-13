# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO, $TESTING,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# #433 Part D -- NEGATIVE RESULT, hitch_report.py is UNCHANGED. The brief: "Change, only if a
# measure separates the cases." ATV Quad Power Racing 2 (n-4143000A-1013r) never left the start
# line for its whole 649 s drive hold (speedometer 0 the entire time), but its verdict.json read
# `position: still 0 of 16 pairs, first_last 0.3338` (bar 0.025) -- the rider's pose, the preload
# gauge, the countdown overlay and the camera all change the screen while the quad stays parked,
# so hitch_report.py's existing full-frame position_change()/position_fail() never flagged it.
#
# The obvious fix is Part A's own band mask (GAS_MOVE_BAND, the vehicle/HUD band blacked out) on
# the route-frames samples position_change() already reads. It does not work: measured over every
# genre=="drive" run on disk (12 runs, not a sample -- the full table is in NOTES.md), ATV's own
# per-pair band-restricted motion ranges 0.046-0.460. Cel Damage (n-45410011-1007, a confirmed
# real drive) ranges 0.015-0.455 on the same measure -- almost the identical range. No single bar
# can fail ATV without also failing a real drive's own stillest moment, and no bar can pass a real
# drive's moving moments without also passing ATV's own busiest one. scene_shift (phase
# correlation) is worse: it reads ATV at 0-28 px while RalliSport Challenge 2 (also a confirmed
# real drive, Part A) reads 0-1.4 px -- lower than the parked quad.
#
# Zero ledger-banked Playable run is genre=="drive" today (NOTES.md), so the brief's falsifier
# ("must still PASS every banked Playable's own run") holds on the banked set vacuously; this
# fragment instead falsifies the band-mask candidate directly against a confirmed real drive,
# which is the stronger and more honest claim. A banked fighter (Mortal Kombat: Armageddon,
# armageddon1006d, attack genre, Playable) stands in for "stationary-camera games must pass":
# genre != "drive" so a drive-gated rule would never run on it at all, and on its own merits its
# frames are clearly active (not still) throughout.
#
# Fixtures (docs/lanes/holdinput1013/fixtures/positiontravel/) are real route-frames, recompressed
# to JPEG (quality 85; classify.motion() resizes to 160x120 before diffing regardless, so this
# changes nothing to four decimal places): ATV's own lowest- and highest-change pairs, Cel
# Damage's own lowest- and highest-change pairs, and one Armageddon pair.

echo "== position-travel (#433 Part D): the band-masked candidate does not separate a parked vehicle from a real drive"

FX="$REPO/docs/lanes/holdinput1013/fixtures/positiontravel"

pt_eval() {   # <a> <b> -> "full band"
    python3 -c '
import sys, os
sys.path.insert(0, sys.argv[1])
import classify
import pathfind as pf
ga, gb = classify.open_grey(sys.argv[2]), classify.open_grey(sys.argv[3])
full = classify.motion(ga, gb)[0]
band = classify.motion(ga, gb, mask_boxes=[pf.GAS_MOVE_BAND])[0]
print("%.4f %.4f" % (full, band))
' "$TESTING/titles" "$1" "$2"
}

read ATV_LOW_FULL ATV_LOW_BAND <<< "$(pt_eval "$FX/atv-low-a.jpg" "$FX/atv-low-b.jpg")"
read ATV_HIGH_FULL ATV_HIGH_BAND <<< "$(pt_eval "$FX/atv-high-a.jpg" "$FX/atv-high-b.jpg")"
read CEL_LOW_FULL CEL_LOW_BAND <<< "$(pt_eval "$FX/celdamage-low-a.jpg" "$FX/celdamage-low-b.jpg")"
read CEL_HIGH_FULL CEL_HIGH_BAND <<< "$(pt_eval "$FX/celdamage-high-a.jpg" "$FX/celdamage-high-b.jpg")"
read ARMAGEDDON_FULL ARMAGEDDON_BAND <<< "$(pt_eval "$FX/armageddon-a.jpg" "$FX/armageddon-b.jpg")"

echo "   ATV (parked)       low pair: full=$ATV_LOW_FULL  band=$ATV_LOW_BAND"
echo "   ATV (parked)      high pair: full=$ATV_HIGH_FULL band=$ATV_HIGH_BAND"
echo "   Cel Damage (real)  low pair: full=$CEL_LOW_FULL  band=$CEL_LOW_BAND"
echo "   Cel Damage (real) high pair: full=$CEL_HIGH_FULL band=$CEL_HIGH_BAND"
echo "   Armageddon (fighter) pair:   full=$ARMAGEDDON_FULL band=$ARMAGEDDON_BAND"

pt_cmp() {   # <a> <op> <b> -> python bool
    python3 -c "print($1 $2 $3)"
}

if [ "$(pt_cmp "$ATV_LOW_BAND" '>' "$CEL_LOW_BAND")" = "True" ]; then
    ok "falsifier 1: ATV's stillest pair ($ATV_LOW_BAND) reads MORE change than Cel Damage's stillest real-drive pair ($CEL_LOW_BAND) -- a bar between them would fail real driving before it fails the parked quad"
else
    bad "falsifier 1 did not reproduce: ATV low band $ATV_LOW_BAND vs Cel Damage low band $CEL_LOW_BAND (expected ATV strictly greater)"
fi

if [ "$(pt_cmp "$ATV_HIGH_BAND" '>' "$CEL_HIGH_BAND")" = "True" ]; then
    ok "falsifier 2: ATV's busiest pair ($ATV_HIGH_BAND) reads MORE change than Cel Damage's own busiest real-drive pair ($CEL_HIGH_BAND) -- no bar passes real driving without also passing the parked quad"
else
    bad "falsifier 2 did not reproduce: ATV high band $ATV_HIGH_BAND vs Cel Damage high band $CEL_HIGH_BAND (expected ATV strictly greater)"
fi

check "ATV's own stillest pair still clears classify.STATIC_BAR on the full frame (today's known gap: never flagged as still)" \
    python3 -c "import sys; sys.path.insert(0, sys.argv[1]); import classify
assert float(sys.argv[2]) > classify.STATIC_BAR" "$TESTING/titles" "$ATV_LOW_FULL"

check "Armageddon (banked fighter, attack genre): clearly active, not still -- a drive-gated rule never has to touch it" \
    python3 -c "import sys; sys.path.insert(0, sys.argv[1]); import classify
assert float(sys.argv[2]) > classify.STATIC_BAR" "$TESTING/titles" "$ARMAGEDDON_FULL"

echo "   -> no change made to hitch_report.py's position_change()/position_fail(); see NOTES.md Part D for the full 12-run table"
