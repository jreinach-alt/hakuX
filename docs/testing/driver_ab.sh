#!/usr/bin/env bash
#
# Run a suite twice, once on each GPU driver, and split its failures in two.
#
#   driver_ab.sh <suite name> <turnip.adpkg.zip>
#
# ROADMAP.md section 3 asks for exactly this:
#
#   "Output differing *between drivers* is a driver bug; output identical
#    between them but diverging *from the goldens* is xemu's translation."
#
# ~1,300 tests differ from hardware with no way to say which of those two they
# are. This says. It is also the one measurement that cannot move off the
# handheld: lavapipe on the desktop is neither of the drivers in question.
#
# ONE TEST PER DISC, not one suite per disc. The between-drivers comparison
# would survive a shared disc -- contamination is identical in both passes and
# cancels -- but the third bucket would not. "Identical on both drivers and
# differing from the golden" is only evidence about our translation if the
# difference is not a previous test's leftovers, and issue #19 found 328 of 864
# tests rendering another test's image. Bump map alone scores 38/40 isolated
# against 36/40 sharing a disc with two other suites. So each test boots alone.
#
# The driver switch is a preference, not a reinstall: MainActivity reads
# runtime_override_gpu_driver from x1box_prefs, where "system" forces the
# Qualcomm driver and anything else uses whatever is installed in
# filesDir/gpu_driver. Both passes share one installed driver and differ only
# by that key -- and only that key is edited. An earlier version of this script
# deleted x1box_prefs.xml to clear it, which took the MCPX, flash and HDD paths
# with it and dropped the app into its setup wizard.
set -u

SUITE="${1:?usage: driver_ab.sh <suite name> <turnip .adpkg.zip>}"
PKG_ZIP="${2:?}"

SERIAL="${SERIAL:-$(adb devices | awk 'NR==2{print $1}')}"
PKG="${PKG:-com.jreinach.hakux.debug}"
WORK="${HAKUX_WORK:-$HOME/hakux-work}"
GOLDENS="${GOLDENS:-$HOME/goldens/results}"
BASE_ISO="${BASE_ISO:-$HOME/nxdk_pgraph_tests_xiso.iso}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RESULTS_NAME="${SUITE// /_}"
PREF="shared_prefs/x1box_prefs.xml"

a() { timeout "${ADB_TIMEOUT:-120}" adb -s "$SERIAL" "$@"; }
mkdir -p "$WORK/ab"

set_driver() {   # "system" or "custom" -- edits one key, preserves the rest
    a shell "run-as $PKG cat $PREF" 2>/dev/null | tr -d '\r' > "$WORK/ab/prefs.xml"
    [ -s "$WORK/ab/prefs.xml" ] || { echo "cannot read $PREF; refusing to guess"; exit 1; }
    python3 "$REPO/docs/testing/_set_driver_pref.py" "$WORK/ab/prefs.xml" "$1" || exit 1
    a shell "run-as $PKG sh -c 'cat > $PREF'" < "$WORK/ab/prefs.xml"
}

echo "== installing the custom driver =="
tmp="$WORK/ab/pkg"; rm -rf "$tmp"; mkdir -p "$tmp"
unzip -oq "$PKG_ZIP" -d "$tmp" || { echo "bad zip"; exit 1; }
[ -f "$tmp/meta.json" ] || { echo "no meta.json; not an adpkg"; exit 1; }
lib=$(python3 -c "import json;print(json.load(open('$tmp/meta.json'))['libraryName'])")
a shell "run-as $PKG sh -c 'rm -rf files/gpu_driver && mkdir -p files/gpu_driver'"
for f in meta.json "$lib"; do
    a push "$tmp/$f" "/data/local/tmp/$f" >/dev/null
    a shell "run-as $PKG sh -c 'cp /data/local/tmp/$f files/gpu_driver/'"
    a shell "rm -f /data/local/tmp/$f"
done
echo "   installed: $(a shell "run-as $PKG ls files/gpu_driver" | tr -d '\r' | tr '\n' ' ')"

# Every test in the suite that has a golden to compare against.
mapfile -t TESTS < <(ls "$GOLDENS/$RESULTS_NAME" 2>/dev/null | sed 's/\.png$//')
[ "${#TESTS[@]}" -gt 0 ] || { echo "no goldens for $RESULTS_NAME"; exit 1; }
echo "== $SUITE: ${#TESTS[@]} tests, one boot each, twice =="

for which in custom system; do
    echo "== pass: $which driver =="
    set_driver "$which"
    out="$WORK/ab/res-$which"; rm -rf "$out"; mkdir -p "$out"
    n=0
    for t in "${TESTS[@]}"; do
        plan=$(python3 "$REPO/docs/testing/make_isolation_discs.py" x \
                 --results "$out" --goldens "$GOLDENS" --base "$BASE_ISO" \
                 --out-dir "$WORK/ab/disc" --build-one "$RESULTS_NAME::$t" 2>/dev/null) || continue
        gdir=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['guest_dir'])" "$plan")
        iso=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['iso'])" "$plan")
        SERIAL="$SERIAL" bash "$REPO/docs/testing/run_disc.sh" \
            "$iso" "$gdir" "$WORK/ab/one" 120 >/dev/null 2>&1
        cp "$WORK/ab/one/$RESULTS_NAME::$t.png" "$out/" 2>/dev/null && n=$((n+1))
    done
    echo "   captured $n of ${#TESTS[@]}"
    a logcat -b all -d 2>/dev/null | grep -a "GPU driver:" | tail -1 | sed 's/.*MainActivity: /   /'
done

set_driver custom    # leave it somewhere deliberate, not mid-experiment

echo
echo "== verdict =="
python3 "$REPO/docs/testing/_driver_ab_verdict.py" \
    "$WORK/ab/res-custom" "$WORK/ab/res-system" "$GOLDENS" "$RESULTS_NAME"
