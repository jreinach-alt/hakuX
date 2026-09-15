#!/bin/bash
# Same build, several discs, three drivers each. Restores T30 whatever happens.
# Ordered by how likely the suite is to expose a driver difference: anisotropic
# filtering first (its far field is an acknowledged vendor tap pattern), then
# the primitive suite (stock Qualcomm lacks shaderTessellationAndGeometryPointSize
# and the emulator puts a geometry shader in front of every draw).
set -u
S=ee317437; PKG=com.jreinach.hakux.debug
W=/home/justin/hakux-work; R=/home/justin/hakuX/docs/testing; D=$W/drv

trap 'echo "--- restoring T30 ---"; bash $D/swap_driver.sh restore' EXIT

DISCS="aniso:aniso 3d_primitive:p3d blend_surface:blend_surface light:light dxt:dxt cubemap:cubemap"

adb -s $S shell am force-stop $PKG
adb -s $S install -r $W/apk-shadowgrid.apk 2>&1 | tail -1

for pair in $DISCS; do
    disc="${pair%%:*}"; guest="${pair##*:}"
    echo "############ disc $disc ############"
    for arm in t30 stock t26; do
        bash $D/swap_driver.sh $arm >/dev/null 2>&1
        out=$W/res_drv_${disc}_${arm}
        rm -rf $out
        SERIAL=$S bash $R/run_disc.sh "$W/iso-$disc.iso" "$guest" "$out" 1500 >/dev/null 2>&1
        adb -s $S shell am force-stop $PKG
        n=$(ls "$out"/*.png 2>/dev/null | wc -l)
        echo "  $arm: $n captures"
    done
    python3 - "$disc" <<'PY'
import sys, os, hashlib
disc = sys.argv[1]; W = "/home/justin/hakux-work"
arms = ["t30", "stock", "t26"]
dirs = {a: f"{W}/res_drv_{disc}_{a}" for a in arms}
if not all(os.path.isdir(d) for d in dirs.values()):
    print(f"  {disc}: a run produced no directory"); sys.exit()
names = sorted(f for f in os.listdir(dirs["t30"]) if f.endswith(".png"))
md5 = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
same = 0; moved = []
for n in names:
    hs = {a: md5(os.path.join(dirs[a], n))
          for a in arms if os.path.exists(os.path.join(dirs[a], n))}
    if len(hs) < 3:
        moved.append((n, "missing from an arm")); continue
    if len(set(hs.values())) == 1:
        same += 1
    else:
        who = "stock" if hs["t30"] == hs["t26"] else "mesa version"
        moved.append((n, who))
print(f"  == {disc}: {len(names)} captures, {same} byte-identical across all "
      f"three drivers, {len(moved)} differ")
for n, who in moved[:12]:
    print(f"       {n}  ({who})")
if len(moved) > 12:
    print(f"       ... and {len(moved) - 12} more")
PY
done
echo "############ sweep done ############"
