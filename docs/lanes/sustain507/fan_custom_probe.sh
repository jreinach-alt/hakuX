#!/usr/bin/env bash
# #507 Part D.1: what fan_mode 6 (CUSTOM) does, on an idle handheld, under a
# held session of at most ~5 min.
#
#   fan_custom_probe.sh <thor|nova>     log to fanprobe-<label>.txt beside this file
#
# 1. Take the hold (jobs/hold.sh, tag lane.sustain507). Refuse if the device
#    runs a request, or someone else holds it.
# 2. Snapshot `settings list system|global|secure` and the fan node.
# 3. fan_mode 6, then read duty/state/speed every 5 s for 60 s.
# 4. Snapshot the settings again, and diff: any key CUSTOM reads or writes.
# 5. Ask whether the shell can write the PWM duty itself (50000 = 100%):
#    write, read back 3 times over 10 s, and restore.
# 6. The AYN/Odin packages, and any settings key or provider naming a fan.
# 7. Restore fan_mode 4 and the duty (EXIT trap), and release the hold.
set -u
LABEL=${1:?thor or nova}
case "$LABEL" in thor) S=bdc158a5 ;; nova) S=ee317437 ;; *) echo "unknown $LABEL" >&2; exit 2 ;; esac
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
D=${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}
LOG="$HERE/fanprobe-$LABEL.txt"
TAG=lane.sustain507
F=/sys/class/gpio5_pwm2
a() { timeout 30 adb -s "$S" "$@"; }
log() { echo "$(date -u +%H:%M:%SZ) $*" | tee -a "$LOG"; }
fan() { a shell "echo mode=\$(settings get system fan_mode) duty=\$(cat $F/duty) period=\$(cat $F/period) state=\$(cat $F/state) speed=\$(cat $F/speed) xo=\$(for z in /sys/class/thermal/thermal_zone*; do [ \"\$(cat \$z/type)\" = xo-therm ] && cat \$z/temp; done | head -1)" | tr -d '\r'; }

: > "$LOG"
# A hold already ours (taken ahead, while the last request ran) is reused.
H="$REPO/docs/testing/jobs/hold.sh"
if ! bash "$H" take "$LABEL" "$TAG" "#507 D.1 fan_mode 6 probe, idle, < 5 min"; then
    case "$(bash "$H" who "$LABEL")" in *"$TAG"*) log "hold already ours" ;;
        *) log "REFUSED: hold not taken"; exit 3 ;; esac
fi
DUTY0=""
finish() {
    a shell settings put system fan_mode 4 >/dev/null 2>&1
    sleep 3
    log "restored: $(fan)"
    bash "$REPO/docs/testing/jobs/hold.sh" release "$LABEL" "$TAG" && log "hold released"
}
trap finish EXIT
trap 'exit 143' TERM; trap 'exit 130' INT
# A request claimed between the check and the take still runs: stop if so.
if grep -lqs "$LABEL" "$D"/running/*.owner; then log "REFUSED: $LABEL claimed a request before the hold"; exit 3; fi

log "device $LABEL $S; before: $(fan)"
for ns in system global secure; do a shell settings list $ns | tr -d '\r' | sort > "$HERE/.fp-$LABEL-$ns-0"; done
log "fan-named keys before: $(cat "$HERE"/.fp-$LABEL-*-0 | grep -i -E 'fan|pwm|duty|curve|custom' | tr '\n' ' ')"

log "== fan_mode 6"
a shell settings put system fan_mode 6
for i in $(seq 1 12); do sleep 5; log "  +$((i * 5)) s $(fan)"; done
for ns in system global secure; do
    a shell settings list $ns | tr -d '\r' | sort > "$HERE/.fp-$LABEL-$ns-1"
    ch=$(diff "$HERE/.fp-$LABEL-$ns-0" "$HERE/.fp-$LABEL-$ns-1" | grep '^[<>]' | tr '\n' ' ')
    log "settings $ns changed under mode 6: ${ch:-none}"
done

log "== can the shell hold duty 50000?"
DUTY0=$(a shell cat $F/duty | tr -d '\r')
log "  write: $(a shell "echo 50000 > $F/duty" 2>&1 | tr -d '\r' | tr '\n' ' ') (duty was $DUTY0)"
for i in 1 2 3; do sleep 3; log "  +$((i * 3)) s $(fan)"; done
a shell "echo $DUTY0 > $F/duty" >/dev/null 2>&1

log "== packages and providers"
log "  packages: $(a shell pm list packages | tr -d '\r' | grep -i -E 'ayn|odin|fan|retroid|moorechip' | tr '\n' ' ')"
log "  fan-named providers: $(a shell dumpsys package providers | tr -d '\r' | grep -i -E 'fan' | head -5 | tr '\n' ' ')"
log "  node perms: $(a shell ls -l $F/ | tr -d '\r' | tr '\n' '|')"
rm -f "$HERE"/.fp-$LABEL-*
