#!/bin/bash
# Inject gamepad input at the evdev layer. `input keyevent` arrives with a
# non-gamepad source and the emulator treats it as an exit, so it must not be
# used here (see AGENTS.md, "Working with a device"). Nothing in this file
# sends anything but EV_KEY/EV_ABS/EV_SYN to the pad's own node.
#
#   SERIAL=<serial> pad.sh detect            print (and cache) the pad node
#   SERIAL=<serial> pad.sh press <BTN> [ms]
#   SERIAL=<serial> pad.sh hold <BTN> | release <BTN>
#   SERIAL=<serial> pad.sh axis <LX|LY|RX|RY|LT|RT|HATX|HATY|ABS_*|code> <min|max|mid|value>
#   SERIAL=<serial> pad.sh mash [n] [gap_s] | startmash [n] [gap_s]
#
# SERIAL IS REQUIRED. This used to default to the Nova's serial and event7,
# which made every script that forgot to pass one drive the Nova, and made the
# Thor unreachable without editing the file.
#
# PAD_DEV, when unset, is the /dev/input/event* node whose `getevent -pl`
# lists a south button AND ABS_X: a pad, not the power key or the touch
# panel. getevent names code 304 by whichever alias its table has first --
# BTN_GAMEPAD on both handhelds (2026-09-25), BTN_SOUTH or BTN_A elsewhere --
# so all three are accepted. Found on 2026-09-25, read-only:
#   Nova ee317437  /dev/input/event7  "Retroid Pocket Controller"
#   Thor bdc158a5  /dev/input/event9  "Odin Controller"
# Both report the sticks as -32767..32767 centred on 0 (this file used to say
# 0..255 centred on 128), the RIGHT stick on ABS_Z/ABS_RZ rather than
# ABS_RX/ABS_RY, and the triggers on ABS_BRAKE/ABS_GAS. So routes name LOGICAL
# axes -- LX LY RX RY LT RT HATX HATY -- and this file resolves each against
# what the pad actually has. The node and every axis's min/max are cached per
# serial in $HAKUX_WORK/pad-dev.<serial>; `min|max|mid` read that. `detect`
# always re-reads the device and rewrites the cache (event numbers can move
# across a reboot); the other verbs trust the cache when there is one, since
# route.sh runs `detect` once at the start of every route.
set -u
S="${SERIAL:-}"
[ -n "$S" ] || { echo "pad.sh: SERIAL is required (no default device)" >&2; exit 2; }
CACHE="${HAKUX_WORK:-/home/justin/hakux-work}/pad-dev.$S"
# ROUTE_DRY=1 prints what would be sent and touches no device: route.sh's
# --dry mode and the selftest use it.
DRY="${ROUTE_DRY:-}"

# evdev key codes
declare -A BTN=( [A]=304 [B]=305 [X]=307 [Y]=308 [START]=315 [SELECT]=314 [BACK]=314 \
                 [L1]=310 [R1]=311 [L2]=312 [R2]=313 [L3]=317 [R3]=318 \
                 [UP]=544 [DOWN]=545 [LEFT]=546 [RIGHT]=547 )
declare -A ABS=( [ABS_X]=0 [ABS_Y]=1 [ABS_Z]=2 [ABS_RX]=3 [ABS_RY]=4 [ABS_RZ]=5 \
                 [ABS_GAS]=9 [ABS_BRAKE]=10 [ABS_HAT0X]=16 [ABS_HAT0Y]=17 )
# Logical axis -> the evdev axes that can carry it, first present wins.
declare -A LOGICAL=( [LX]="ABS_X" [LY]="ABS_Y" [RX]="ABS_RX ABS_Z" [RY]="ABS_RY ABS_RZ" \
                     [LT]="ABS_BRAKE ABS_Z" [RT]="ABS_GAS ABS_RZ" \
                     [HATX]="ABS_HAT0X" [HATY]="ABS_HAT0Y" )

sh_adb() {
    if [ -n "$DRY" ]; then echo "DRY adb shell $*"; return 0; fi
    timeout "${ADB_TIMEOUT:-20}" adb -s "$S" shell "$@"
}

# Parse `getevent -pl` for the pad node and each ABS axis's range. Prints the
# cache file's contents: dev=<node> then ABS_<name>=<min>,<max> lines.
detect() {
    local out
    if [ -n "$DRY" ]; then
        printf 'dev=/dev/input/event-dry\nABS_X=-32767,32767\nABS_Y=-32767,32767\nABS_Z=-32767,32767\nABS_RZ=-32767,32767\n'
        return 0
    fi
    # Three tries, 2 s apart: one WSL `UtilAcceptVsock` failure returns nothing,
    # and on 2026-09-26 that alone left a 13-minute Nova run with no input.
    local try
    for try in 1 2 3; do
        out=$(timeout "${ADB_TIMEOUT:-20}" adb -s "$S" shell getevent -pl 2>/dev/null | tr -d '\r')
        [ -n "$out" ] && break
        echo "pad.sh: getevent -pl returned nothing on $S (try $try/3)" >&2
        [ "$try" = 3 ] || sleep "${PAD_RETRY_S:-2}"
    done
    [ -n "$out" ] || return 1
    printf '%s\n' "$out" | python3 -c '
import re, sys
blocks, cur = [], None
for line in sys.stdin:
    m = re.match(r"add device \d+: (\S+)", line)
    if m:
        cur = {"dev": m.group(1), "text": "", "abs": {}}
        blocks.append(cur)
        continue
    if cur is None:
        continue
    cur["text"] += line
    a = re.search(r"\b(ABS_[A-Z0-9_]+)\s*:\s*value -?\d+, min (-?\d+), max (-?\d+)", line)
    if a:
        cur["abs"][a.group(1)] = (int(a.group(2)), int(a.group(3)))
for b in blocks:
    if re.search(r"\bBTN_(SOUTH|A|GAMEPAD)\b", b["text"]) and "ABS_X" in b["abs"]:
        print("dev=" + b["dev"])
        for k, (lo, hi) in sorted(b["abs"].items()):
            print("%s=%d,%d" % (k, lo, hi))
        sys.exit(0)
sys.exit(1)
' || { echo "pad.sh: no node on $S lists BTN_SOUTH/BTN_A and ABS_X" >&2; return 1; }
}

load() {
    DEV="${PAD_DEV:-}"
    [ -n "$DEV" ] && return 0
    if [ ! -s "$CACHE" ] && [ -z "$DRY" ]; then
        detect > "$CACHE.tmp" && mv "$CACHE.tmp" "$CACHE" || { rm -f "$CACHE.tmp"; exit 1; }
    fi
    if [ -n "$DRY" ]; then DEV=/dev/input/event-dry; return 0; fi
    DEV=$(sed -n 's/^dev=//p' "$CACHE")
    [ -n "$DEV" ] || { echo "pad.sh: $CACHE names no device" >&2; exit 1; }
}

btn() {
    [ -n "${BTN[$1]:-}" ] || { echo "pad.sh: unknown button '$1'" >&2; exit 2; }
    echo "${BTN[$1]}"
}

key() {   # key <code> <0|1>
    sh_adb "sendevent $DEV 1 $1 $2; sendevent $DEV 0 0 0"
}

press() {  # press <name> [hold_ms]
    local code hold=${2:-60}
    code=$(btn "${1:-}") || exit 2
    key "$code" 1
    command sleep "$(awk "BEGIN{print $hold/1000}")"
    key "$code" 0
}

ranges() {   # the cached ABS_<name>=min,max lines
    if [ -n "$DRY" ]; then detect | grep '^ABS_'; else grep '^ABS_' "$CACHE" 2>/dev/null; fi
}

axis() {  # axis <logical|ABS_*|code> <min|max|mid|value>
    local want="$1" val="$2" name="" code range lo hi c
    if [ -n "${LOGICAL[$want]:-}" ]; then
        for c in ${LOGICAL[$want]}; do
            ranges | grep -q "^$c=" && { name=$c; break; }
        done
        [ -n "$name" ] || { echo "pad.sh: this pad has none of ${LOGICAL[$want]} for $want" >&2; exit 2; }
    elif [ -n "${ABS[$want]:-}" ]; then name=$want
    else
        case "$want" in ''|*[!0-9]*) echo "pad.sh: unknown axis '$want'" >&2; exit 2;; esac
        code=$want
    fi
    [ -n "$name" ] && code=${ABS[$name]}
    case "$val" in
        min|max|mid)
            range=$(ranges | sed -n "s/^${name:-none}=//p")
            [ -n "$range" ] || { echo "pad.sh: no range cached for ${name:-axis $code}; give a number" >&2; exit 2; }
            lo=${range%,*}; hi=${range#*,}
            case "$val" in min) val=$lo;; max) val=$hi;; mid) val=$(( (lo + hi) / 2 ));; esac ;;
        -[0-9]*|[0-9]*) ;;
        *) echo "pad.sh: bad axis value '$val'" >&2; exit 2;;
    esac
    sh_adb "sendevent $DEV 3 $code $val; sendevent $DEV 0 0 0"
}

case "${1:-}" in
    detect) out=$(detect) || exit 1
            [ -n "$DRY" ] || { printf '%s\n' "$out" > "$CACHE.tmp" && mv "$CACHE.tmp" "$CACHE"; }
            printf '%s\n' "$out" | sed -n 's/^dev=//p' ;;
    press)   shift; load; press "$@" ;;
    hold)    shift; c=$(btn "${1:-}") || exit 2; load; key "$c" 1 ;;
    release) shift; c=$(btn "${1:-}") || exit 2; load; key "$c" 0 ;;
    axis)    shift; load; axis "$@" ;;
    mash)  shift; load; n=${1:-10}; gap=${2:-1.2}
           for i in $(seq 1 "$n"); do press A; command sleep "$gap"; done ;;
    # Alternating Start and A. Some titles need Start to leave an attract or
    # "press start" screen and A to take menu defaults; A alone stalls on the
    # first and Start alone stalls on the second.
    startmash) shift; load; n=${1:-10}; gap=${2:-1.0}
           for i in $(seq 1 "$n"); do
               press START; command sleep "$gap"
               press A;     command sleep "$gap"
           done ;;
    *) echo "usage: SERIAL=<s> pad.sh {detect | press <BTN> [ms] | hold <BTN> | release <BTN> |" \
            "axis <LX|LY|RX|RY|LT|RT|HATX|HATY|ABS_*|code> <min|max|mid|val> | mash [n] [gap_s] | startmash [n] [gap_s]}" >&2; exit 2 ;;
esac
