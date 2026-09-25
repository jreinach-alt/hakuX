#!/bin/bash
# Play a route: a small text file of gamepad steps, run against a title that
# soak_title.sh has already started.
#
#   SERIAL=<s> route.sh <file.route>      play it (soak_title.sh does this)
#   route.sh --check <file.route>         parse only; exit 2 on any error
#   ROUTE_DRY=1 route.sh <file.route>     play it against no device
#
# Grammar, one step per line, `#` to end of line is a comment:
#
#   wait <s>                    sleep (fractions allowed)
#   press <BTN> [ms]            press and release, held ms (default 60)
#   hold <BTN> / release <BTN>  for a long press or a held accelerator
#   axis <axis> <val>           axis: LX LY RX RY LT RT HATX HATY (resolved
#                               per pad by pad.sh), ABS_*, or a code; val is
#                               a number or min|max|mid. LY min is stick UP.
#   mash <BTN> <n> <gap_s>      n presses, gap_s apart
#   mark <label>                log it here AND in logcat, and take a frame
#   shot <label>                take a frame only
#   repeat <n|forever> {        a block; blocks nest; `}` on its own line
#   }
#
# `mark gameplay` STARTS THE SCORED WINDOW: title_verdict.py judges frame
# rate, hangs and audio only after the logcat line this writes
# (`I/hakuX-route: mark gameplay`). A mark is written to logcat rather than
# kept in host time because the verdict reads device time, and the host and
# the device clocks are not the same clock.
#
# Every step is logged with a host timestamp on stdout, prefixed `ROUTE`, so a
# run.log records exactly what was played and when.
#
# Frames go to $ROUTE_FRAMES (default: route-frames/ beside the route file,
# which in a dispatcher result dir is the result dir). A frame per mark is a
# handful of screencaps over a run, not the once-a-second capture that
# --frames-every warns costs frame rate; the contact sheet is built from them.
#
# NEVER `input keyevent`: a non-gamepad key exits the app. All input goes
# through perf/pad.sh, which sends only EV_KEY/EV_ABS to the pad node.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAD="$HERE/../perf/pad.sh"

CHECK=""
if [ "${1:-}" = "--check" ]; then CHECK=1; shift; fi
ROUTE="${1:?usage: route.sh [--check] <file.route>}"
[ -f "$ROUTE" ] || { echo "route.sh: no such route: $ROUTE" >&2; exit 2; }
ROUTE_FRAMES="${ROUTE_FRAMES:-$(dirname "$ROUTE")/route-frames}"

BUTTONS=" A B X Y START SELECT BACK L1 R1 L2 R2 L3 R3 UP DOWN LEFT RIGHT "
AXES=" LX LY RX RY LT RT HATX HATY ABS_X ABS_Y ABS_Z ABS_RX ABS_RY ABS_RZ ABS_GAS ABS_BRAKE ABS_HAT0X ABS_HAT0Y "

mapfile -t L < <(sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$ROUTE")
N=${#L[@]}

err() { echo "route.sh: $ROUTE:$(( $1 + 1 )): $2" >&2; exit 2; }
isnum() { [[ "$1" =~ ^[0-9]+(\.[0-9]+)?$ ]]; }
isbtn() { case "$BUTTONS" in *" $1 "*) return 0;; esac; return 1; }

# Index of the `}` closing the block opened on line $1.
close_of() {
    local i=$(( $1 + 1 )) depth=1
    while [ "$i" -lt "$N" ]; do
        case "${L[$i]}" in
            *'{') depth=$((depth+1)) ;;
            '}')  depth=$((depth-1)); [ "$depth" = 0 ] && { echo "$i"; return 0; } ;;
        esac
        i=$((i+1))
    done
    return 1
}

# Parse every line once, before anything is sent: a typo on line 40 must not
# be discovered twenty minutes into a soak, after the part of the route that
# worked has already been played.
validate() {
    local i=0 depth=0 w
    while [ "$i" -lt "$N" ]; do
        read -r -a w <<< "${L[$i]}"
        case "${w[0]:-}" in
            '') ;;
            wait)  isnum "${w[1]:-}" || err "$i" "wait wants seconds" ;;
            press) isbtn "${w[1]:-}" || err "$i" "unknown button '${w[1]:-}'"
                   [ -z "${w[2]:-}" ] || isnum "${w[2]}" || err "$i" "press hold wants ms" ;;
            hold|release) isbtn "${w[1]:-}" || err "$i" "unknown button '${w[1]:-}'" ;;
            axis)  case "$AXES" in *" ${w[1]:-} "*) ;; *) [[ "${w[1]:-}" =~ ^[0-9]+$ ]] \
                       || err "$i" "unknown axis '${w[1]:-}'";; esac
                   [[ "${w[2]:-}" =~ ^(min|max|mid|-?[0-9]+)$ ]] || err "$i" "axis value '${w[2]:-}'" ;;
            mash)  isbtn "${w[1]:-}" || err "$i" "unknown button '${w[1]:-}'"
                   [[ "${w[2]:-}" =~ ^[0-9]+$ ]] || err "$i" "mash wants a count"
                   isnum "${w[3]:-}" || err "$i" "mash wants a gap in seconds" ;;
            mark|shot) [ -n "${w[1]:-}" ] || err "$i" "${w[0]} wants a label"
                   [[ "${w[1]}" =~ ^[A-Za-z0-9_.-]+$ ]] || err "$i" "label '${w[1]}' must be [A-Za-z0-9_.-]" ;;
            repeat) [[ "${w[1]:-}" =~ ^([0-9]+|forever)$ ]] || err "$i" "repeat wants a count or 'forever'"
                    [ "${w[2]:-}" = '{' ] || err "$i" "repeat wants '{' on the same line"
                    depth=$((depth+1)) ;;
            '}') [ "$depth" -gt 0 ] || err "$i" "unmatched '}'"; depth=$((depth-1)) ;;
            *) err "$i" "unknown step '${w[0]}'" ;;
        esac
        i=$((i+1))
    done
    [ "$depth" = 0 ] || err "$((N-1))" "unclosed repeat block"
}
validate
if [ -n "$CHECK" ]; then echo "route ok: $ROUTE ($N lines)"; exit 0; fi

: "${SERIAL:?route.sh: SERIAL is required}"
export SERIAL

log() { echo "ROUTE $(date '+%H:%M:%S.%3N') $*"; }
pad() { bash "$PAD" "$@" || log "pad.sh $* failed (rc $?)"; }

# Interruptible sleep: soak_title.sh TERMs this script when the hold ends, and
# a bare `sleep 600` would keep the route's last wait alive past it.
SLEEP_PID=""
nap() { command sleep "$1" & SLEEP_PID=$!; wait "$SLEEP_PID"; SLEEP_PID=""; }

# Leave the pad as it was found: a route killed mid-hold must not leave the
# accelerator pressed or the stick pushed into whatever runs next.
HELD=""; MOVED=""; CLEANED=""
cleanup() {
    [ -z "$CLEANED" ] || return 0
    CLEANED=1
    [ -n "$SLEEP_PID" ] && kill "$SLEEP_PID" 2>/dev/null
    for b in $HELD; do bash "$PAD" release "$b" >/dev/null 2>&1; done
    for x in $MOVED; do bash "$PAD" axis "$x" mid >/dev/null 2>&1; done
    log "end"
}
trap 'cleanup; exit 0' TERM INT
trap cleanup EXIT

shot() {
    [ -n "${ROUTE_DRY:-}" ] && { log "shot $1 (dry)"; return 0; }
    mkdir -p "$ROUTE_FRAMES"
    local f; f="$ROUTE_FRAMES/$(date '+%H%M%S')-$1.png"
    timeout 30 adb -s "$SERIAL" exec-out screencap -p > "$f" 2>/dev/null
    [ -s "$f" ] || { rm -f "$f"; log "shot $1 FAILED"; return 0; }
    log "shot $1 -> $(basename "$f")"
}

run() {   # run <first line> <end line, exclusive>
    local i=$1 end=$2 w j k n
    while [ "$i" -lt "$end" ]; do
        read -r -a w <<< "${L[$i]}"
        case "${w[0]:-}" in
            '') ;;
            wait)  log "wait ${w[1]}"; nap "${w[1]}" ;;
            press) log "press ${w[1]} ${w[2]:-}"; pad press "${w[1]}" ${w[2]:-} ;;
            hold)  log "hold ${w[1]}"; pad hold "${w[1]}"; HELD="$HELD ${w[1]}" ;;
            release) log "release ${w[1]}"; pad release "${w[1]}"; HELD="${HELD// ${w[1]}/}" ;;
            axis)  log "axis ${w[1]} ${w[2]}"; pad axis "${w[1]}" "${w[2]}"
                   case "${w[2]}" in mid) MOVED="${MOVED// ${w[1]}/}";; *) MOVED="$MOVED ${w[1]}";; esac ;;
            mash)  log "mash ${w[1]} ${w[2]} ${w[3]}"
                   for ((k = 0; k < w[2]; k++)); do pad press "${w[1]}"; nap "${w[3]}"; done ;;
            mark)  log "mark ${w[1]}"
                   if [ -z "${ROUTE_DRY:-}" ]; then
                       timeout 20 adb -s "$SERIAL" shell log -t hakuX-route "'mark ${w[1]}'" >/dev/null 2>&1 \
                           || log "mark ${w[1]}: logcat write FAILED"
                   fi
                   shot "${w[1]}" ;;
            shot)  shot "${w[1]}" ;;
            repeat) j=$(close_of "$i")
                    n=${w[1]}; [ "$n" = forever ] && n=-1
                    k=0
                    while [ "$n" -lt 0 ] || [ "$k" -lt "$n" ]; do
                        k=$((k+1)); run $((i+1)) "$j"
                    done
                    i=$j ;;
            '}') ;;
        esac
        i=$((i+1))
    done
}

log "start $(basename "$ROUTE") serial=$SERIAL"
if [ -z "${PAD_DEV:-}" ]; then
    PAD_DEV=$(bash "$PAD" detect) || { log "no pad node found; route NOT played"; exit 1; }
fi
export PAD_DEV
log "pad $PAD_DEV"
run 0 "$N"
log "done"
