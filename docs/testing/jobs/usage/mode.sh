#!/usr/bin/env bash
#
# mode.sh normal|low|auto|status|tick -- the harness's two operating modes,
# switched by the usage meter (meter.py) so that nobody has to watch it
# (owner, 2026-10-09: "if we're projecting over on usage for the week, dial
# down the number of Opus lanes and defer for later, or run it on Sonnet").
#
#   mode.sh low      force Low now; locked (manual) until `auto`
#   mode.sh normal   force Normal now; locked (manual) until `auto`
#   mode.sh auto     release any manual lock and evaluate immediately
#   mode.sh status   print the current mode, source, since, and the last
#                    meter reading, and exit 0 regardless
#   mode.sh tick     THE TIMER'S ENTRYPOINT: units/hakux-usage-meter.service
#                    runs `meter.py && mode.sh tick` every 30 min. A no-op
#                    while a manual lock is held.
#
# LOW IS ONE FILE. Low creates $WORK/usage/low-active (one line, the reason);
# Normal removes it. Everything Low does is read from that file at the moment
# it matters, by the reader, so switching rewrites nothing that a later switch
# would have to put back:
#
#   lane.sh, at every start and resume: LANE_MAX capped at USAGE_LOW_LANE_MAX
#     (3), and any model other than Sonnet/Haiku -- a brief's .model, or the
#     escalation model -- runs on USAGE_LOW_MODEL (claude-sonnet-5) instead.
#     An explicit HAKUX_MODEL still wins. A RUNNING session keeps its model;
#     the cap applies from its next resume.
#   limits.env PATHFIND_MODEL_CALLS_MAX=20 while Low, absent while Normal
#     (lane.pathfind's navigation agent reads it itself; absent IS its normal).
#   hostops heartbeat 2h -> 4h, via a systemd timer drop-in.
#
# The first version of this script saved every dial and every .model file on
# the way into Low and restored them on the way out. The snapshot was taken
# once and never refreshed, so a week later "normal" would have restored
# Opus pins the owner had since removed; and Low latched until a week_end
# crossing that meter.py had always already moved past by the time this ran,
# so it never came back on its own.
#
# WHEN. Re-evaluated on every tick, no latch:
#   enter Low   when estimated% >= USAGE_LOW_PCT (80)
#               or projected-at-reset >= USAGE_LOW_PROJ (90)
#   back Normal when estimated% <  USAGE_LOW_PCT
#               and projected-at-reset < USAGE_NORMAL_PROJ (75)
# The gap between 90 and 75 keeps it from flapping on one busy hour. The week
# rolling over needs no special case: the estimate drops, and so does Low.
# A tick that changes nothing logs nothing.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
SYSTEMD_DIR="${HAKUX_SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}"
LIM="$WORK/limits.env"
MODE_FILE="$WORK/usage/mode"
LOW_FILE="$WORK/usage/low-active"
SWITCH_LOG="$WORK/usage/switches.log"
STATE_JSON="$WORK/usage/state.json"
DROPIN_DIR="$SYSTEMD_DIR/hakux-hostops.timer.d"
DROPIN="$DROPIN_DIR/usage-low.conf"

now_iso() {
    if [ -n "${HAKUX_NOW:-}" ]; then
        date -u -d "@$HAKUX_NOW" +%FT%TZ 2>/dev/null || date -u +%FT%TZ
    else
        date -u +%FT%TZ
    fi
}
now_epoch() { echo "${HAKUX_NOW:-$(date -u +%s)}"; }

mkdir -p "$WORK/usage"
[ -e "$LIM" ] || : > "$LIM"

# -------------------------------------------------------------- limits.env
get_kv() { sed -n "s/^$2=//p" "$1" | tail -1; }
set_kv() {   # <file> <key> <value>
    local f=$1 k=$2 v=$3
    if grep -q "^$k=" "$f" 2>/dev/null; then
        sed -i "s/^$k=.*/$k=$v/" "$f"
    else
        printf '%s=%s\n' "$k" "$v" >> "$f"
    fi
}
unset_kv() { sed -i "/^$2=/d" "$1" 2>/dev/null; }   # <file> <key>
dial() { local v; v=$(get_kv "$LIM" "$1"); echo "${v:-$2}"; }   # <key> <default>

# ------------------------------------------------------------ hostops timer
hostops_low() {
    mkdir -p "$DROPIN_DIR"
    printf 'OnCalendar=\nOnCalendar=*-*-* 00/4:00:00\n' > "$DROPIN"
    systemctl --user daemon-reload 2>/dev/null
    systemctl --user try-restart hakux-hostops.timer 2>/dev/null \
        || systemctl --user restart hakux-hostops.timer 2>/dev/null || true
}
hostops_normal() {
    [ -e "$DROPIN" ] || return 0
    rm -f "$DROPIN"
    rmdir "$DROPIN_DIR" 2>/dev/null
    systemctl --user daemon-reload 2>/dev/null
    systemctl --user try-restart hakux-hostops.timer 2>/dev/null \
        || systemctl --user restart hakux-hostops.timer 2>/dev/null || true
}

# ------------------------------------------------------------- mode + log
read_mode() { sed -n 's/^mode=//p' "$MODE_FILE" 2>/dev/null | tail -1; }
read_source() { sed -n 's/^source=//p' "$MODE_FILE" 2>/dev/null | tail -1; }
write_mode() {   # <mode> <source> <reason>
    printf 'mode=%s\nsource=%s\nsince=%s\nreason=%s\n' "$1" "$2" "$(now_iso)" "$3" > "$MODE_FILE"
}
log_switch() { printf '%s\t%s\n' "$(now_iso)" "$1" >> "$SWITCH_LOG"; }

apply_low() {   # <source> <reason>
    echo "$2" > "$LOW_FILE"
    set_kv "$LIM" PATHFIND_MODEL_CALLS_MAX 20
    hostops_low
    write_mode low "$1" "$2"
    log_switch "-> low ($1): $2"
    echo "mode: low ($2)"
}

apply_normal() {   # <source> <reason>
    rm -f "$LOW_FILE"
    unset_kv "$LIM" PATHFIND_MODEL_CALLS_MAX
    hostops_normal
    write_mode normal "$1" "$2"
    log_switch "-> normal ($1): $2"
    echo "mode: normal ($2)"
}

# ------------------------------------------------------------- evaluation
# Reads meter.py's last report (state.json's "last_report"); never runs the
# meter itself. Stale or absent data fails open: no switch.
evaluate() {   # <source> -> 0 always; prints what it decided
    local src=$1 cur out
    [ -e "$STATE_JSON" ] || { echo "mode: no meter data yet ($STATE_JSON absent); no change"; return 0; }
    cur=$(read_mode); cur=${cur:-normal}
    out=$(CUR="$cur" LOW_PCT="$(dial USAGE_LOW_PCT 80)" LOW_PROJ="$(dial USAGE_LOW_PROJ 90)" \
          NORMAL_PROJ="$(dial USAGE_NORMAL_PROJ 75)" python3 - "$STATE_JSON" <<'PY'
import json, os, sys
try:
    r = json.load(open(sys.argv[1])).get("last_report") or {}
except Exception:
    print("ERR unreadable meter state"); sys.exit(0)
pct, proj = r.get("estimated_percent"), r.get("projected_percent_at_reset")
if pct is None:
    print("ERR no estimate (no calibration capacity yet)"); sys.exit(0)
low_pct, low_proj, normal_proj = (float(os.environ[k]) for k in ("LOW_PCT", "LOW_PROJ", "NORMAL_PROJ"))
p = proj if proj is not None else pct
reading = "estimated %s%%, projected %s%% at reset" % (pct, "?" if proj is None else proj)
if pct >= low_pct or p >= low_proj:
    print("low %s >= %g%% used or %g%% projected" % (reading, low_pct, low_proj))
elif os.environ["CUR"] == "low" and p >= normal_proj:
    print("low %s: under the entry line, not yet under %g%% projected" % (reading, normal_proj))
else:
    print("normal %s" % reading)
PY
)
    # Holding still re-checks the one file, so a mode file and a low-active
    # that disagree (a hand edit, a crash between the two writes) heal here.
    case "$out" in
        "low "*)    [ "$cur" = low ] && [ -e "$LOW_FILE" ] && out="hold $out" ;;
        "normal "*) [ "$cur" = normal ] && [ ! -e "$LOW_FILE" ] && out="hold $out" ;;
    esac
    case "$out" in
        hold\ *)   echo "mode: $cur (${out#hold * })" ;;
        low\ *)    apply_low "$src" "${out#low }" ;;
        normal\ *) apply_normal "$src" "${out#normal }" ;;
        ERR\ *)    echo "mode: ${out#ERR }; no change" ;;
        *)         echo "mode: unreadable evaluation; no change" ;;
    esac
}

cmd="${1:-status}"
case "$cmd" in
    low)
        apply_low manual "manual: mode.sh low" ;;
    normal)
        apply_normal manual "manual: mode.sh normal" ;;
    auto)
        cur=$(read_mode); write_mode "${cur:-normal}" auto "manual: mode.sh auto (re-armed)"
        evaluate auto ;;
    tick)
        if [ "$(read_source)" = manual ]; then
            echo "mode: manual override active ($(read_mode)); tick skipped"
        else
            evaluate auto
        fi ;;
    status)
        m=$(read_mode); s=$(read_source)
        echo "mode=${m:-unknown} source=${s:-unknown}"
        [ -e "$MODE_FILE" ] && cat "$MODE_FILE"
        [ -e "$WORK/usage/summary.txt" ] && cat "$WORK/usage/summary.txt"
        ;;
    *)
        echo "usage: mode.sh normal|low|auto|status|tick" >&2
        exit 2 ;;
esac
