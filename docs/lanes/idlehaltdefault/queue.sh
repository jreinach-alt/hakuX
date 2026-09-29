#!/usr/bin/env bash
# queue.sh <key> <arm A|B> <n>: queue one idlehaltdefault request (#525).
# Logs to docs/lanes/idlehaltdefault/.qlog/ (not committed); the id is its 'queued' line.
cd /home/justin/hakux-work/wt/idlehaltdefault || exit 1
key=$1 arm=$2 n=$3
REF=3a5d79e3ea225fd1a7673de28657b6eb14cc058c
case $key in
  kabuki)   T="43560001-Kabuki_Warriors.xiso.iso"; R=kabuki-warriors; S=420;;
  fuzion)   T="Fuzion Frenzy (USA).xiso.iso"; R=fuzion-frenzy; S=420;;
  forza)    T="4D53006E-Forza_Motorsport.xiso.iso"; R=survey; S=420;;
  doa1u)    T="54430006-Dead_or_Alive_1_Ultimate.xiso.iso"; R=survey; S=420;;
  blinx2)   T="4D530065-Blinx_2_Battle_of_Time_Space_Blinx_2_Masters_of_Time_Space.xiso.iso"; R=survey; S=420;;
  ghoulies) T="Grabbed by the Ghoulies (USA) (En,Fr,De,Es,It).xiso.iso"; R=ghoulies; S=730;;
  *) echo "unknown key $key"; exit 2;;
esac
envargs=()
what="halt off"
if [ "$arm" = B ]; then envargs=(--env HAKUX_IDLE_HALT=1); what="halt on"; fi
mkdir -p docs/lanes/idlehaltdefault/.qlog
log=docs/lanes/idlehaltdefault/.qlog/q_${key}_${arm}${n}.log
env HAKUX_RELEASE_PRIO=1 docs/testing/request.sh --who lane.idlehaltdefault \
  --purpose "#525 idlehaltdefault $key ${arm}${n}: $what" \
  --title "$T" --route "$R" --seconds "$S" --perflog --device nova --ref "$REF" \
  "${envargs[@]}" --expect "docs/testing/predictions/idlehaltdefault-$key.json" --issue 525 \
  > "$log" 2>&1
rc=$?
echo "$key ${arm}${n} rc=$rc"
tail -6 "$log"
