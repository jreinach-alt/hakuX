#!/bin/bash
# Fuzion Frenzy baseline. It asks for every VBLANK and we do not sustain it, so
# unlike Crimson Skies it can show an improvement above 30. Gameplay is about
# ninety seconds away behind a Start/A mash, with no menu to navigate.
set -u
W=/home/justin/hakux-work/perf
export GAME='/storage/E6C6-D7AA/Games/XBox/Fuzion Frenzy (USA).xiso.iso'
export MASH="startmash 5 1.2"
export BOOT_S=70 SETTLE_S=3
bash $W/run_perf.sh "${1:-1}" "${2:-ff}" "${3:-40}"
