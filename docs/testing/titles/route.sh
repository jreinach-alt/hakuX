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
#   flush [timeout_s]           send the app to the background so it writes
#                               its disk, and wait (default 10 s) for
#                               `deferred bdrv_flush_all completed`. LAST
#                               STEP ONLY: the title is paused after it.
#   waitfor <name> <timeout_s> <x,y,w,h> <threshold>
#                               poll the region once a second against the
#                               reference crop routes/refs/<route>/<name>.png
#                               (mean abs diff, grayscale, downscaled to
#                               64x48) until it MATCHES (score <= threshold)
#                               or the timeout passes. A timeout ABORTS the
#                               route (`ROUTE FAIL waitfor <name>`): a route
#                               that cannot see the screen it needs must
#                               stop, not carry on pressing into whatever is
#                               actually up.
#   press-until <BTN> <name> <max_n> <gap_s> <x,y,w,h> <threshold>
#                               press BTN, wait gap_s, compare the region to
#                               the reference crop; repeat up to max_n times
#                               until it NO LONGER matches (score >
#                               threshold) -- the reference is the state
#                               BEFORE the press is expected to work (e.g.
#                               an empty name field), so success is a
#                               mismatch. Exhausting max_n ABORTS the route
#                               (`ROUTE FAIL press-until <BTN> <name>`).
#
# WHY waitfor/press-until exist at all: a route otherwise plays fixed `wait`
# timers against a screen it never looks at. castlevania-cod.first-run's
# newgame -> Name Entry transition varied by 10+ seconds between runs; a
# `wait 14` that covered it once left every press of an unattended replay
# landing on a screen that had not loaded yet, typing nothing for 900s
# (docs/lanes/titleroutes/NOTES.md, session 60). `shot`/`mark` take a frame
# but never read it back, so that failure was invisible until someone
# opened the frames by hand. Reference crops are part of the route: commit
# them next to the route file under `routes/refs/<route-stem>/`, and note
# in the route's own comments which screen each one came from.
#
# WHY `flush`. A soak ends with `am force-stop` (SIGKILL), and the app
# flushes its qcow2 disk only when it is backgrounded or terminated
# (ui/xemu.c, SDL_APP_WILLENTERBACKGROUND). A profile a first-run creates
# is written into clusters whose allocation is still in memory, so the
# force-stop loses it and the next boot asks for the profile again
# (GoldenEye: Rogue Agent, 09-26, three times). A route that exists to
# leave a save on the disk ends with `flush`. The background is a HOME
# intent (`am start -c android.intent.category.HOME`), never
# `input keyevent`. The title stops rendering, so a flush after
# `mark gameplay` reads as a hang to title_verdict.py: a flushing run
# makes a save, not a measurement.
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

# routes/refs/<route-stem>/<name>.png: the reference crop a `waitfor` or
# `press-until` step with this name compares against.
ref_path() { echo "$(dirname "$ROUTE")/refs/$(basename "$ROUTE" .route)/$1.png"; }
isregion() { [[ "$1" =~ ^[0-9]+,[0-9]+,[0-9]+,[0-9]+$ ]]; }

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
            flush) # whole seconds: flush_disk counts its polls with an integer test
                   [ -z "${w[1]:-}" ] || [[ "${w[1]}" =~ ^[0-9]+$ ]] || err "$i" "flush wants a timeout in whole seconds"
                   [ "$depth" = 0 ] || err "$i" "flush inside a repeat block"
                   # the FIRST flush: everything after it is checked, a second flush included
                   [ -n "$FLUSH_AT" ] || FLUSH_AT=$i ;;
            waitfor) [ -n "${w[1]:-}" ] || err "$i" "waitfor wants a name"
                   [[ "${w[1]}" =~ ^[A-Za-z0-9_.-]+$ ]] || err "$i" "waitfor name '${w[1]}' must be [A-Za-z0-9_.-]"
                   isnum "${w[2]:-}" || err "$i" "waitfor wants a timeout in seconds"
                   isregion "${w[3]:-}" || err "$i" "waitfor wants a region x,y,w,h"
                   isnum "${w[4]:-}" || err "$i" "waitfor wants a threshold"
                   [ -f "$(ref_path "${w[1]}")" ] || err "$i" "waitfor '${w[1]}': no reference crop $(ref_path "${w[1]}")" ;;
            press-until) isbtn "${w[1]:-}" || err "$i" "unknown button '${w[1]:-}'"
                   [ -n "${w[2]:-}" ] || err "$i" "press-until wants a name"
                   [[ "${w[2]}" =~ ^[A-Za-z0-9_.-]+$ ]] || err "$i" "press-until name '${w[2]}' must be [A-Za-z0-9_.-]"
                   [[ "${w[3]:-}" =~ ^[0-9]+$ ]] || err "$i" "press-until wants a max press count"
                   isnum "${w[4]:-}" || err "$i" "press-until wants a gap in seconds"
                   isregion "${w[5]:-}" || err "$i" "press-until wants a region x,y,w,h"
                   isnum "${w[6]:-}" || err "$i" "press-until wants a threshold"
                   [ -f "$(ref_path "${w[2]}")" ] || err "$i" "press-until '${w[2]}': no reference crop $(ref_path "${w[2]}")" ;;
            *) err "$i" "unknown step '${w[0]}'" ;;
        esac
        i=$((i+1))
    done
    [ "$depth" = 0 ] || err "$((N-1))" "unclosed repeat block"
    # Nothing but waits, shots and comments may follow a flush: the title is
    # in the background, and input sent to it goes nowhere.
    if [ -n "$FLUSH_AT" ]; then
        i=$((FLUSH_AT + 1))
        while [ "$i" -lt "$N" ]; do
            read -r -a w <<< "${L[$i]}"
            case "${w[0]:-}" in ''|wait|shot) ;; *) err "$i" "'${w[0]}' after flush: flush is the last step" ;; esac
            i=$((i+1))
        done
    fi
}
FLUSH_AT=""
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

# The mark is the line the whole scored window hangs on, so it is retried as
# soak_title.sh retries its liveness probe: three tries, 2 s apart. `log`
# prints nothing when it works, so output on a zero exit (a WSL vsock error
# text) is a failure too. The last line is what title_verdict.py reads.
mark_logcat() {
    local try out
    for try in 1 2 3; do
        if out=$(timeout 20 adb -s "$SERIAL" shell log -t hakuX-route "'mark $1'" 2>&1) && [ -z "$out" ]; then
            return 0
        fi
        log "mark $1: logcat write failed (try $try/3): $(printf '%s' "$out" | head -1)"
        [ "$try" = 3 ] || nap "${ROUTE_RETRY_S:-2}"
    done
    log "mark $1: logcat write FAILED"
    return 1
}

# The flush is judged by the app's own line, stamped after the request on the
# DEVICE clock (the host and device clocks differ): a line from an earlier
# background in the same logcat buffer must not count.
flush_disk() {   # flush_disk <timeout_s>
    local t0 out waited=0
    t0=$(timeout 20 adb -s "$SERIAL" shell date +%s 2>/dev/null | tr -dc 0-9)
    [ -n "$t0" ] || { log "flush: no device clock; flush NOT confirmed"; return 1; }
    out=$(timeout 20 adb -s "$SERIAL" shell am start -a android.intent.action.MAIN \
          -c android.intent.category.HOME 2>&1) || { log "flush: HOME intent failed: $(printf '%s' "$out" | head -1)"; return 1; }
    while :; do
        if timeout 20 adb -s "$SERIAL" shell logcat -d -v epoch -s hakuX:I 2>/dev/null \
            | awk -v t0="$t0" '$1 + 0 >= t0 && /deferred bdrv_flush_all completed/ { f = 1 } END { exit !f }'; then
            log "flush: bdrv_flush_all completed after ${waited}s"
            return 0
        fi
        [ "$waited" -lt "$1" ] || break
        nap 1; waited=$((waited + 1))
    done
    log "flush: no 'deferred bdrv_flush_all completed' within ${1}s; flush NOT confirmed"
    return 1
}

# Screencap to a scratch file for comparison only: no log line, no frame
# kept in ROUTE_FRAMES. waitfor/press-until poll up to once a second and
# must not fill the frames dir with one entry per poll.
capture_tmp() {   # capture_tmp <dest file>
    [ -n "${ROUTE_DRY:-}" ] && return 1
    timeout 30 adb -s "$SERIAL" exec-out screencap -p > "$1" 2>/dev/null
    [ -s "$1" ]
}

# waitfor <name> <timeout_s> <region> <threshold>: see the grammar comment
# at the top of this file for why this exists at all.
waitfor_step() {
    local name="$1" timeout="$2" region="$3" threshold="$4" ref tmp waited=0 out rc
    ref="$(ref_path "$name")"
    if [ -n "${ROUTE_DRY:-}" ]; then
        log "waitfor $name (dry, assumed matched)"
        return 0
    fi
    mkdir -p "$ROUTE_FRAMES"
    tmp="$(mktemp)"
    while :; do
        if capture_tmp "$tmp"; then
            out="$(python3 "$HERE/waitfor_match.py" "$tmp" "$ref" "$region" "$threshold" 2>&1)"; rc=$?
        else
            out="(screencap failed)"; rc=2
        fi
        if [ "$rc" = 0 ]; then
            log "waitfor $name: matched after ${waited}s ($out)"
            cp "$tmp" "$ROUTE_FRAMES/$(date '+%H%M%S')-$name.png" 2>/dev/null
            rm -f "$tmp"
            return 0
        fi
        [ "$waited" -lt "$timeout" ] || break
        nap 1; waited=$((waited + 1))
    done
    log "ROUTE FAIL waitfor $name: timed out after ${timeout}s ($out)"
    cp "$tmp" "$ROUTE_FRAMES/$(date '+%H%M%S')-$name-timeout.png" 2>/dev/null
    rm -f "$tmp"
    return 1
}

# press-until <BTN> <name> <max_n> <gap_s> <region> <threshold>: see the
# grammar comment at the top of this file. <name>'s reference crop is the
# state BEFORE the press is expected to work, so success is a MISMATCH.
press_until_step() {
    local btn="$1" name="$2" max_n="$3" gap="$4" region="$5" threshold="$6" ref tmp n out rc
    ref="$(ref_path "$name")"
    if [ -n "${ROUTE_DRY:-}" ]; then
        log "press-until $btn $name (dry, assumed changed after 1 press)"
        pad press "$btn"
        return 0
    fi
    mkdir -p "$ROUTE_FRAMES"
    tmp="$(mktemp)"
    for ((n = 1; n <= max_n; n++)); do
        log "press-until $btn $name: press $n/$max_n"
        pad press "$btn"
        nap "$gap"
        if capture_tmp "$tmp"; then
            out="$(python3 "$HERE/waitfor_match.py" "$tmp" "$ref" "$region" "$threshold" 2>&1)"; rc=$?
        else
            out="(screencap failed)"; rc=0
        fi
        if [ "$rc" = 1 ]; then
            log "press-until $btn $name: changed after $n press(es) ($out)"
            cp "$tmp" "$ROUTE_FRAMES/$(date '+%H%M%S')-$name.png" 2>/dev/null
            rm -f "$tmp"
            return 0
        fi
    done
    log "ROUTE FAIL press-until $btn $name: no change after $max_n presses ($out)"
    cp "$tmp" "$ROUTE_FRAMES/$(date '+%H%M%S')-$name-stuck.png" 2>/dev/null
    rm -f "$tmp"
    return 1
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
                   [ -n "${ROUTE_DRY:-}" ] || mark_logcat "${w[1]}"
                   shot "${w[1]}" ;;
            shot)  shot "${w[1]}" ;;
            flush) log "flush ${w[1]:-10}"
                   [ -n "${ROUTE_DRY:-}" ] || flush_disk "${w[1]:-10}" ;;
            waitfor) log "waitfor ${w[1]} (timeout ${w[2]}s)"
                   waitfor_step "${w[1]}" "${w[2]}" "${w[3]}" "${w[4]}" || exit 1 ;;
            press-until) log "press-until ${w[1]} ${w[2]} (max ${w[3]} presses, ${w[4]}s apart)"
                   press_until_step "${w[1]}" "${w[2]}" "${w[3]}" "${w[4]}" "${w[5]}" "${w[6]}" || exit 1 ;;
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
