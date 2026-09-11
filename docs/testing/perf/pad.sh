#!/bin/bash
# Inject gamepad input at the evdev layer. `input keyevent` arrives with a
# non-gamepad source and the emulator treats it as an exit, so it must not be
# used here (see AGENTS.md, "Working with a device").
set -u
S=${SERIAL:-ee317437}; DEV=${PAD_DEV:-/dev/input/event7}
# evdev codes
declare -A BTN=( [A]=304 [B]=305 [X]=307 [Y]=308 [START]=315 [SELECT]=314 \
                 [L1]=310 [R1]=311 [UP]=544 [DOWN]=545 [LEFT]=546 [RIGHT]=547 )

press() {  # press <name> [hold_ms]
    local code=${BTN[$1]} hold=${2:-60}
    adb -s $S shell "sendevent $DEV 1 $code 1; sendevent $DEV 0 0 0"
    command sleep "$(awk "BEGIN{print $hold/1000}")"
    adb -s $S shell "sendevent $DEV 1 $code 0; sendevent $DEV 0 0 0"
}

axis() {  # axis <code> <value> — left stick X=0 Y=1, centre 128 on this pad
    adb -s $S shell "sendevent $DEV 3 $1 $2; sendevent $DEV 0 0 0"
}

case "${1:-}" in
    press) shift; press "$@" ;;
    axis)  shift; axis "$@" ;;
    mash)  shift; n=${1:-10}; gap=${2:-1.2}
           for i in $(seq 1 "$n"); do press A; command sleep "$gap"; done ;;
    *) echo "usage: pad.sh {press <BTN> [ms] | axis <code> <val> | mash [n] [gap_s]}"; exit 2 ;;
esac
