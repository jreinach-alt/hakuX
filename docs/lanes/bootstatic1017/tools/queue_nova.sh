#!/usr/bin/env bash
# Queue the Nova before/after launch captures for #1045: three titles of
# different engines, each on the probe-only ref (before) and the R1+R2 ref
# (after). Every run: video from the soak start (before `am start`), the
# present probe on for 40 s, its files pulled. Judged by tools/judge_video.py.
#
#   queue_nova.sh BEFORE_SHA AFTER_SHA OUT_IDS_FILE
#
# 6 runs x (75 s + 90 s setup) = 16.5 min of device time, inside the 30-min
# pilot allowance. Both arms carry the same env, so the pref left on the device
# until the next request is the probe's, which only writes files.
set -u
BEFORE="$1"; AFTER="$2"; OUT="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
REQ="$HERE/../../../testing/request.sh"
TITLES=("Halo Combat Evolved.iso|Halo CE (Blam)" \
        "4D530035-Top_Spin.xiso.iso|Top Spin (PAM)" \
        "5454000E-Grand_Theft_Auto_III.xiso.iso|GTA III (RenderWare)")
for arm in before after; do
    ref="$BEFORE"; [ "$arm" = after ] && ref="$AFTER"
    for t in "${TITLES[@]}"; do
        iso="${t%%|*}"; name="${t#*|}"
        id=$(bash "$REQ" --who lane.bootstatic1017 \
            --purpose "#1045 launch flash, $arm ($ref), $name: every frame from launch" \
            --ref "$ref" --title "$iso" --device nova \
            --seconds 75 --video-seconds 60 --video-after 0 \
            --env HAKUX_BOOTPROBE=1 --env HAKUX_BOOTPROBE_SECS=40 --env HAKUX_BOOTPROBE_MAXDUMP=200 \
            --pull 'boot1045_*' --issue 1045 \
            --no-expect "launch-flash capture judged per frame by docs/lanes/bootstatic1017/tools/judge_video.py, not a golden arm" 2>&1)
        rc=$?
        printf '%s\t%s\t%s\trc=%s\t%s\n' "$arm" "$ref" "$name" "$rc" "$(echo "$id" | tail -n 3 | tr '\n' ' ')" | tee -a "$OUT"
    done
done
