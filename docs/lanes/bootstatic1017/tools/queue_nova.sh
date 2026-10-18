#!/usr/bin/env bash
# Queue the Nova before/after launch captures for #1045: three titles of
# different engines, each on the probe-only ref (before) and the R1+R2 ref
# (after). Every run: video from before `am start`, the present probe on for
# 40 s, its files pulled. Judged by tools/judge_video.py and tools/judge_nova.py.
#
#   [VIDEO_AFTER=10] [ARMS="before after"] queue_nova.sh BEFORE_SHA AFTER_SHA OUT_IDS_FILE
#
# ARMS=after queues only the after arm: R5 (2a012b14fc) is judged against the
# R1+R2 after runs and the probe-only before runs already in OUT_IDS_FILE.
#
# VIDEO_AFTER is 10, not 0: soak_title.sh puts the screen out for its cool-down
# gate (KEYCODE_SLEEP, line 493) and wakes it after (line 577), and a recording
# started before the sleep gets no frame and writes an empty file (1792282757,
# --video-after 0: v00001.mp4 0 bytes). On that run the gate's sample was at
# +5.6 s from the video's start and `am start` at +13.9 s; 10 s lands between.
#
# 6 runs x (75 s + 90 s setup) = 16.5 min of device time, inside the 30-min
# pilot allowance. Both arms carry the same env, so the pref left on the device
# until the next request is the probe's, which only writes files.
#
# ONLY (an ERE over the title's name) queues a subset. Attempt 3 requeued Top
# Spin and GTA III with VIDEO_AFTER=7: with 10, their videos started 0.05-1.7 s
# after the first present (the wake-to-launch gap is shorter than Halo's).
set -u
BEFORE="$1"; AFTER="$2"; OUT="$3"
VIDEO_AFTER="${VIDEO_AFTER:-10}"
ARMS="${ARMS:-before after}"
ONLY="${ONLY:-.}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REQ="$HERE/../../../testing/request.sh"
TITLES=("Halo Combat Evolved.iso|Halo CE (Blam)" \
        "4D530035-Top_Spin.xiso.iso|Top Spin (PAM)" \
        "5454000E-Grand_Theft_Auto_III.xiso.iso|GTA III (RenderWare)")
for arm in $ARMS; do
    ref="$BEFORE"; [ "$arm" = after ] && ref="$AFTER"
    for t in "${TITLES[@]}"; do
        iso="${t%%|*}"; name="${t#*|}"
        echo "$name" | grep -Eq "$ONLY" || continue
        id=$(bash "$REQ" --who lane.bootstatic1017 \
            --purpose "#1045 launch flash, $arm ($ref), $name: every frame from launch" \
            --ref "$ref" --title "$iso" --device nova \
            --seconds 75 --video-seconds 60 --video-after "$VIDEO_AFTER" \
            --env HAKUX_BOOTPROBE=1 --env HAKUX_BOOTPROBE_SECS=40 --env HAKUX_BOOTPROBE_MAXDUMP=200 \
            --pull 'boot1045_*' --issue 1045 \
            --no-expect "launch-flash capture judged per frame by docs/lanes/bootstatic1017/tools/judge_video.py, not a golden arm" 2>&1)
        rc=$?
        printf '%s\t%s\t%s\trc=%s\t%s\n' "$arm" "$ref" "$name" "$rc" "$(echo "$id" | tail -n 3 | tr '\n' ' ')" | tee -a "$OUT"
    done
done
