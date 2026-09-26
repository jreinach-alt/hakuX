#!/bin/bash
# Swap the GPU driver the emulator loads. Arms: t30, t26, stock.
# The loader reads files/gpu_driver/meta.json for a libraryName and loads that
# .so from the same directory; with no meta.json it falls back to the system
# driver. T30 is the resting state and restore() always puts it back.
set -u
S=${SERIAL:-ee317437}; PKG=com.jreinach.hakux.debug; D=/home/justin/hakux-work/drv

push_driver() {  # $1 = local dir holding meta.json + vulkan.purple.so
    adb -s $S push -q "$1/vulkan.purple.so" /data/local/tmp/drv.so >/dev/null 2>&1 \
        || adb -s $S push "$1/vulkan.purple.so" /data/local/tmp/drv.so >/dev/null
    adb -s $S push "$1/meta.json" /data/local/tmp/drv.json >/dev/null
    adb -s $S shell "run-as $PKG cp /data/local/tmp/drv.so files/gpu_driver/vulkan.purple.so"
    adb -s $S shell "run-as $PKG cp /data/local/tmp/drv.json files/gpu_driver/meta.json"
    adb -s $S shell rm -f /data/local/tmp/drv.so /data/local/tmp/drv.json
}

restore() {
    adb -s $S shell am force-stop $PKG
    push_driver "$D/T30"
    # the stock arm renames meta.json rather than deleting it; drop the spare
    # so the driver directory is left exactly as it was found
    adb -s $S shell "run-as $PKG rm -f files/gpu_driver/meta.json.off"
    echo "restored: $(adb -s $S shell run-as $PKG cat files/gpu_driver/meta.json | grep packageVersion)"
}

case "${1:-}" in
  t30)   adb -s $S shell am force-stop $PKG; push_driver "$D/T30" ;;
  t26)   adb -s $S shell am force-stop $PKG; push_driver "$D/T26" ;;
  stock) adb -s $S shell am force-stop $PKG
         adb -s $S shell "run-as $PKG mv files/gpu_driver/meta.json files/gpu_driver/meta.json.off" 2>/dev/null
         adb -s $S shell "run-as $PKG ls files/gpu_driver/" ;;
  restore) restore ;;
  *) echo "usage: $0 {t30|t26|stock|restore}"; exit 2 ;;
esac
