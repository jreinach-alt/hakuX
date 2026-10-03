#!/usr/bin/env bash
#
# mode.sh normal|low|auto|status -- the harness's two operating modes,
# switched by the usage meter (meter.py) rather than by a person watching a
# dashboard (owner, 2026-10-02 10:10 PDT: 80% of the week used drops the
# harness into Low; back to Normal at the reset).
#
#   mode.sh low      force Low now; locked (manual) until `auto` or the reset
#   mode.sh normal   force Normal now; locked (manual) until `auto` or the reset
#   mode.sh auto     release any manual lock and evaluate immediately -- the
#                    default state: periodic ticks may switch the mode
#   mode.sh status   print the current mode, source, since, and the last
#                    meter reading, and exit 0 regardless (a status command
#                    that can fail is a status command nobody trusts)
#   mode.sh tick     THE TIMER'S OWN ENTRYPOINT, not one of the four above.
#                    units/hakux-usage-meter.service runs `meter.py && mode.sh
#                    tick` every 30 min. A no-op whenever a manual lock is
#                    held -- the brief's "never flaps: once Low, stay Low
#                    until the reset or a manual mode.sh normal" would not
#                    hold if the next tick just called the same evaluation
#                    `auto` does and silently cleared the lock.
#
# WHAT LOW CHANGES, AND WHY EACH ONE IS REVERSIBLE. Every dial Low touches is
# saved to $WORK/usage/saved/ the FIRST time it is touched (not re-saved on a
# second `mode.sh low` while already low, which would overwrite the real
# original with Low's own value) and restored byte-for-byte by `normal`:
#
#   LANE_MAX=3                         (was whatever limits.env had)
#   MODEL_LANE_ESCALATED=claude-sonnet-5
#   PATHFIND_MODEL_CALLS_MAX=20        (new dial; lane.pathfind's navigation
#                                       agent reads it from limits.env itself)
#   every $WORK/briefs/*.model -> claude-sonnet-5   (an OPUS LANE KEEPS ITS
#      RUNNING SESSION; a .model file is read fresh on the lane's NEXT
#      resume -- see selftest.d/99-lane-model-file.sh -- so this changes
#      what the next resume launches, not what is running right now)
#   hostops heartbeat 2h -> 4h, via a systemd timer drop-in (the same
#      technique host-tools/overnight_mode.sh already uses for its own
#      schedule change)
#
# NOT TOUCHED, ON PURPOSE: device work, the dispatcher, autoverdict, the
# check-in report, foldqueue. And NOT IMPLEMENTED HERE, because the files
# that would enforce it are outside this lane's territory: "no new lanes
# started by anything but lane.local." Low writes $WORK/usage/low-active (one
# line, the reason) as the signal; board.sh's capacity gate does not read it
# yet. See docs/lanes/usagemode/NOTES.md and OUTBOX.md for the exact patch
# board.sh needs.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
SYSTEMD_DIR="${HAKUX_SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}"
LIM="$WORK/limits.env"
MODE_FILE="$WORK/usage/mode"
SAVE_DIR="$WORK/usage/saved"
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

mkdir -p "$WORK/usage" "$SAVE_DIR"
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
restore_kv() {   # <file> <key> <saved value, "" meaning "was absent">
    local f=$1 k=$2 v=$3
    if [ -n "$v" ]; then set_kv "$f" "$k" "$v"; else unset_kv "$f" "$k"; fi
}

# ------------------------------------------------------------- .model files
model_save_dir() { echo "$SAVE_DIR/models"; }
save_models_once() {
    local d; d=$(model_save_dir)
    [ -d "$d" ] && return 0     # already captured this Low episode
    mkdir -p "$d"
    for f in "$WORK"/briefs/*.model; do
        [ -e "$f" ] || continue
        cp "$f" "$d/$(basename "$f")"
    done
}
apply_models_low() {
    for f in "$WORK"/briefs/*.model; do
        [ -e "$f" ] || continue
        echo claude-sonnet-5 > "$f"
    done
}
restore_models() {
    local d; d=$(model_save_dir)
    [ -d "$d" ] || return 0
    for f in "$WORK"/briefs/*.model; do
        [ -e "$f" ] || continue
        [ -e "$d/$(basename "$f")" ] || rm -f "$f"   # did not exist pre-Low
    done
    for f in "$d"/*.model; do
        [ -e "$f" ] || continue
        cp "$f" "$WORK/briefs/$(basename "$f")"
    done
    rm -rf "$d"
}

# ------------------------------------------------------------ hostops timer
hostops_low() {
    mkdir -p "$DROPIN_DIR"
    printf 'OnCalendar=\nOnCalendar=*-*-* 00/4:00:00\n' > "$DROPIN"
    systemctl --user daemon-reload 2>/dev/null
    systemctl --user try-restart hakux-hostops.timer 2>/dev/null \
        || systemctl --user restart hakux-hostops.timer 2>/dev/null || true
}
hostops_normal() {
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
    local src=$1 reason=$2
    local already; already=$(read_mode)
    if [ "$already" != low ]; then
        : > "$SAVE_DIR/limits.snapshot"
        printf 'LANE_MAX=%s\n' "$(get_kv "$LIM" LANE_MAX)" >> "$SAVE_DIR/limits.snapshot"
        printf 'MODEL_LANE_ESCALATED=%s\n' "$(get_kv "$LIM" MODEL_LANE_ESCALATED)" >> "$SAVE_DIR/limits.snapshot"
        printf 'PATHFIND_MODEL_CALLS_MAX=%s\n' "$(get_kv "$LIM" PATHFIND_MODEL_CALLS_MAX)" >> "$SAVE_DIR/limits.snapshot"
        save_models_once
        hostops_low
    fi
    set_kv "$LIM" LANE_MAX 3
    set_kv "$LIM" MODEL_LANE_ESCALATED claude-sonnet-5
    set_kv "$LIM" PATHFIND_MODEL_CALLS_MAX 20
    apply_models_low
    echo "$reason" > "$WORK/usage/low-active"
    write_mode low "$src" "$reason"
    log_switch "-> low ($src): $reason"
    echo "mode: low ($reason)"
}

apply_normal() {   # <source> <reason>
    local src=$1 reason=$2
    if [ -e "$SAVE_DIR/limits.snapshot" ]; then
        restore_kv "$LIM" LANE_MAX "$(get_kv "$SAVE_DIR/limits.snapshot" LANE_MAX)"
        restore_kv "$LIM" MODEL_LANE_ESCALATED "$(get_kv "$SAVE_DIR/limits.snapshot" MODEL_LANE_ESCALATED)"
        restore_kv "$LIM" PATHFIND_MODEL_CALLS_MAX "$(get_kv "$SAVE_DIR/limits.snapshot" PATHFIND_MODEL_CALLS_MAX)"
        rm -f "$SAVE_DIR/limits.snapshot"
    fi
    restore_models
    hostops_normal
    rm -f "$WORK/usage/low-active"
    write_mode normal "$src" "$reason"
    log_switch "-> normal ($src): $reason"
    echo "mode: normal ($reason)"
}

# ------------------------------------------------------------- evaluation
# Reads meter.py's last report (state.json's "last_report"); never runs the
# meter itself -- the timer's unit runs meter.py first, in its own step, so a
# `mode.sh auto|tick` with stale or absent data fails open (no switch) rather
# than guessing.
evaluate() {   # <source: auto|manual> -> 0 always; prints what it decided
    local src=$1
    [ -e "$STATE_JSON" ] || { echo "mode: no meter data yet ($STATE_JSON absent); no change"; return 0; }
    local now; now=$(now_epoch)
    local out
    out=$(HAKUX_NOW="$now" python3 - "$STATE_JSON" <<'PY'
import json, sys
try:
    state = json.load(open(sys.argv[1]))
except Exception:
    print("ERR no state"); sys.exit(0)
r = state.get("last_report") or {}
end = r.get("week_end_epoch")
pct = r.get("estimated_percent")
proj = r.get("projected_percent_at_reset")
import os
now = float(os.environ.get("HAKUX_NOW", "0"))
if end is not None and now >= end:
    print("RESET")
elif pct is None:
    print("ERR no estimate (no calibration capacity yet)")
else:
    trig = (pct >= 80) or (proj is not None and proj >= 100)
    print("TRIGGER %s %s" % (pct, proj if proj is not None else "?") if trig
          else "HOLD %s %s" % (pct, proj if proj is not None else "?"))
PY
)
    case "$out" in
        RESET)
            apply_normal "$src" "the account's weekly window has rolled over" ;;
        TRIGGER\ *)
            apply_low "$src" "estimated week usage ${out#TRIGGER } (pct, projected-at-reset) >= threshold (80% / 100%)" ;;
        HOLD\ *)
            echo "mode: holding at $(read_mode) (${out#HOLD } = pct, projected-at-reset; below threshold)" ;;
        ERR\ *)
            echo "mode: ${out#ERR }; no change" ;;
        *)
            echo "mode: unreadable meter state; no change" ;;
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
        echo "usage: mode.sh normal|low|auto|status" >&2
        exit 2 ;;
esac
