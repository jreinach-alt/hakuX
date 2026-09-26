#!/bin/bash
# Same build, same disc, three drivers. Restores T30 whatever happens.
set -u
S=ee317437; PKG=com.jreinach.hakux.debug
W=/home/justin/hakux-work; R=/home/justin/hakuX/docs/testing; D=$W/drv
ISO=${ISO:-$W/iso-shadow.iso}; GUEST=${GUEST:-shadow}; TAG=${TAG:-shadow}
ARMS=${ARMS:-"t30 stock t26"}

trap 'echo "--- restoring T30 ---"; bash $D/swap_driver.sh restore' EXIT

adb -s $S shell am force-stop $PKG
adb -s $S install -r $W/apk-shadowgrid.apk 2>&1 | tail -1

for arm in $ARMS; do
    echo "=================== $arm ==================="
    bash $D/swap_driver.sh $arm >/dev/null 2>&1
    out=$W/res_drv_${TAG}_${arm}
    rm -rf $out
    adb -s $S logcat -c 2>/dev/null
    SERIAL=$S bash $R/run_disc.sh "$ISO" "$GUEST" "$out" 1500 2>&1 | tail -1
    adb -s $S shell am force-stop $PKG
    adb -s $S logcat -d -s hakuX-stderr 2>/dev/null \
        | grep -iE "driver|vulkan 1|deviceName|apiVersion" | head -4
    python3 $R/score_sweep.py --out "$out" --goldens ~/goldens/results \
        --flat --tsv $W/drv_${TAG}_${arm}.tsv 2>&1 | sed -n '3,5p'
done
echo "=================== done ==================="
