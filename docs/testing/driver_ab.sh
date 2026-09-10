#!/usr/bin/env bash
#
# Run a suite twice, once on each GPU driver, and split its failures in two.
#
#   driver_ab.sh <suite name> <guest-dir> <turnip.adpkg.zip>
#
# ROADMAP.md section 3 asks for exactly this:
#
#   "Output differing *between drivers* is a driver bug; output identical
#    between them but diverging *from the goldens* is xemu's translation."
#
# We have ~1,300 tests that differ from hardware and no way to say which of
# those two things they are. This says. It is also the one measurement that
# cannot be moved off the handheld: lavapipe on the desktop is neither of the
# drivers in question.
#
# The switch is a preference, not a reinstall. MainActivity reads
# runtime_override_gpu_driver from x1box_prefs: "system" forces the Qualcomm
# driver, anything else uses whatever is installed in filesDir/gpu_driver.
# So both passes share one installed driver and differ only by that key.
set -u

SUITE="${1:?usage: driver_ab.sh <suite name> <guest-dir> <turnip .adpkg.zip>}"
GUEST="${2:?}"
PKG_ZIP="${3:?}"

SERIAL="${SERIAL:-$(adb devices | awk 'NR==2{print $1}')}"
PKG="${PKG:-com.jreinach.hakux.debug}"
WORK="${HAKUX_WORK:-$HOME/hakux-work}"
GOLDENS="${GOLDENS:-$HOME/goldens/results}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RESULTS_NAME="${SUITE// /_}"
PREF=/data/data/$PKG/shared_prefs/x1box_prefs.xml

a() { adb -s "$SERIAL" "$@"; }

set_driver() {   # "system" or "custom"
    if [ "$1" = system ]; then
        a shell "run-as $PKG sh -c 'mkdir -p shared_prefs; cat > $PREF'" <<'XML'
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="runtime_override_gpu_driver">system</string>
</map>
XML
    else
        a shell "run-as $PKG sh -c 'rm -f $PREF'" >/dev/null 2>&1
    fi
}

echo "== installing the custom driver =="
tmp=$(mktemp -d)
unzip -oq "$PKG_ZIP" -d "$tmp" || { echo "bad zip"; exit 1; }
[ -f "$tmp/meta.json" ] || { echo "no meta.json; not an adpkg"; exit 1; }
lib=$(python3 -c "import json,sys;print(json.load(open('$tmp/meta.json'))['libraryName'])")
a shell "run-as $PKG sh -c 'rm -rf files/gpu_driver && mkdir -p files/gpu_driver'"
for f in meta.json "$lib"; do
    a push "$tmp/$f" "/data/local/tmp/$f" >/dev/null
    a shell "run-as $PKG sh -c 'cp /data/local/tmp/$f files/gpu_driver/'"
    a shell "rm -f /data/local/tmp/$f"
done
rm -rf "$tmp"
a shell "run-as $PKG ls files/gpu_driver" | tr -d '\r' | sed 's/^/   /'

ISO="$WORK/iso-ab.iso"
python3 "$REPO/docs/testing/make_test_iso.py" \
    "${BASE_ISO:-$HOME/nxdk_pgraph_tests_xiso.iso}" -o "$ISO" \
    --progress-log --shutdown-on-completion --output-dir "e:/$GUEST" \
    --suite "$SUITE" >/dev/null || exit 1

for which in custom system; do
    echo "== pass: $which driver =="
    set_driver "$which"
    a shell am force-stop "$PKG" >/dev/null 2>&1
    rm -rf "$WORK/res-ab-$which"
    SERIAL="$SERIAL" bash "$REPO/docs/testing/run_disc.sh" \
        "$ISO" "$GUEST" "$WORK/res-ab-$which" 900 | sed 's/^/   /'
    a logcat -b all -d 2>/dev/null | grep -a "GPU driver:" | tail -1 | sed 's/^/   /'
done

set_driver custom   # leave the device on the custom driver, not mid-experiment

echo
echo "== verdict =="
python3 - "$WORK/res-ab-custom" "$WORK/res-ab-system" "$GOLDENS" "$RESULTS_NAME" <<'PY'
import os, sys, numpy as np
from PIL import Image
cu, sy, gold, suite = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
def load(p):
    return np.asarray(Image.open(p).convert("RGBA"), dtype=np.int16)
same_and_right = same_and_wrong = driver_diff = missing = 0
examples = []
for f in sorted(os.listdir(cu)):
    if not f.startswith(suite + "::") or not f.endswith(".png"):
        continue
    t = f[len(suite) + 2:-4]
    p_sy = os.path.join(sy, f)
    p_go = os.path.join(gold, suite, t + ".png")
    if not (os.path.exists(p_sy) and os.path.exists(p_go)):
        missing += 1
        continue
    c, s, g = load(os.path.join(cu, f)), load(p_sy), load(p_go)
    if c.shape != s.shape or c.shape != g.shape:
        missing += 1
        continue
    if np.any(c - s):
        driver_diff += 1
        if len(examples) < 6:
            examples.append((t, int(np.abs(c - s).max())))
    elif np.any(c - g):
        same_and_wrong += 1
    else:
        same_and_right += 1
n = same_and_right + same_and_wrong + driver_diff
print(f"  {n} tests compared" + (f" ({missing} skipped)" if missing else ""))
print(f"    identical on both drivers, matches hardware : {same_and_right}")
print(f"    identical on both drivers, differs          : {same_and_wrong}"
      f"   <- our translation")
print(f"    differs between drivers                     : {driver_diff}"
      f"   <- driver-dependent")
for t, d in examples:
    print(f"        {t}  (max delta between drivers {d})")
PY
