#!/usr/bin/env bash
#
#   soak_title.sh <device-iso-path> <seconds>
#
# Env: CAPTURE_LOG, LOGCAT_SPEC, PULL_GLOB, PULL_DEST, GUEST_FILES,
#      AUDIO_CAPTURE_MB (arm the APU PCM capture at this size cap, and clear
#      any previous capture first; disarmed again on the way out),
#      ROUTE_FILE (play this route with titles/route.sh while the title runs;
#      without one the soak plays no input and only ever sees intros, attract
#      demos and menus)
#
# Boot a real title, hold it for a while, keep the log, put the device back.
#
# The pgraph discs answer questions that have a golden framebuffer. Some do
# not: the test discs play no audio at all, so a question like "does any title
# actually program a non-zero submix_headroom" cannot be asked of them. This
# boots a game instead and keeps the log, which is the only oracle available
# until an audio harness exists.
#
# Called by dispatcher.sh, which owns the device, the lease and the sweep
# preemption. Not meant to be run by hand while the dispatcher is serving.
set -u

ISO="$1"
SECONDS_TO_HOLD="${2:-60}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Refuses rather than guesses when two handhelds are attached; see devices.sh.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/devices.sh"
SERIAL="${SERIAL:-$(device_default)}"
[ -n "$SERIAL" ] || exit 2
PKG="${PKG:-com.jreinach.hakux.debug}"
ACT="$PKG/com.rfandango.haku_x.LauncherActivity"
LEASE="${HAKUX_DEVICE_LEASE:-/tmp/hakux-device-lease}"
CAPTURE_LOG="${CAPTURE_LOG:-}"
LOGCAT_SPEC="${LOGCAT_SPEC:-hakuX-crash:V hakuX-audio:I hakuX-audiocap:I hakuX-build:I hakuX-perf:I hakuX-pages:I hakuX:W VALIDATION:W ValidationLayer:W vulkan:W VulkanLoader:W *:S}"
LOGCAT_PID=""
GUEST_FILES="${GUEST_FILES:-/sdcard/Android/data/$PKG/files}"
# MB cap for the APU PCM capture, or empty for no capture. See arm_audio below.
AUDIO_CAPTURE_MB="${AUDIO_CAPTURE_MB:-}"
AUDIO_MARKER="$GUEST_FILES/audio_capture.on"
AUDIO_PCM="$GUEST_FILES/apu_monitor.s16le48k2ch.pcm"
ROUTE_FILE="${ROUTE_FILE:-}"
ROUTE_PID=""

a() { timeout "${ADB_TIMEOUT:-120}" adb -s "$SERIAL" "$@"; }

# The APU's PCM capture is armed by the presence of a marker file whose
# contents are a size cap in MB (hw/xbox/mcpx/apu/apu.c, apu_capture_armed).
# Arming it per REQUEST rather than leaving the marker on the device is not a
# convenience; it is the fix for two failures that both happened on 2026-09-12,
# in opposite directions:
#
#   - A marker left on the device from an earlier experiment armed the capture
#     for seven unrelated Galleon soaks that never asked for it and never
#     pulled it, each writing ~192 KB/s to the SD card for four minutes.
#   - A marker that had since gone missing meant a soak that DID ask for a
#     capture got none -- and, because the last of those seven runs had left a
#     24 MB PCM behind, the pull returned that file instead. It measured as a
#     clean, plausible baseline. It was caught only by arithmetic: 126.976 s of
#     audio cannot come out of a 95 s app lifetime.
#
# The second is the dangerous one, and it is why this also DELETES any existing
# capture before the run. A stale PCM that measures well is indistinguishable
# from a good measurement; an absent one is an obvious failure. Given a choice
# between those two outcomes, take the obvious failure every time.
arm_audio() {
    [ -n "$AUDIO_CAPTURE_MB" ] || return 0
    # Order matters: clear the old capture FIRST, so that if arming then fails
    # there is nothing left to be mistaken for this run's output.
    a shell "rm -f '$AUDIO_PCM' '$AUDIO_PCM.json'" >/dev/null 2>&1
    a shell "mkdir -p '$GUEST_FILES' && echo $AUDIO_CAPTURE_MB > '$AUDIO_MARKER'" >/dev/null 2>&1
    if a shell "cat '$AUDIO_MARKER'" 2>/dev/null | tr -d '\r' | grep -qx "$AUDIO_CAPTURE_MB"; then
        echo "AUDIO: capture armed at ${AUDIO_CAPTURE_MB} MB, old capture cleared"
    else
        # Loud, because the alternative is a run that looks fine and measures
        # nothing. The caller can still decide to keep going.
        echo "AUDIO: FAILED to arm capture at $AUDIO_MARKER -- expect no PCM"
    fi
}

disarm_audio() {
    [ -n "$AUDIO_CAPTURE_MB" ] || return 0
    a shell "rm -f '$AUDIO_MARKER'" >/dev/null 2>&1
}

# THE GAMEPLAY REGIMEN. A title soak runs at the device's MAX performance and
# fan modes and puts it back to REST on the way out (the modes and their
# values are in devices.sh, device_perf_*). pgraph discs never come through
# here: run_disc.sh does not call this, and they do not need it.
#
#   PERF_REGIMEN=max   (the default) MAX before `am start`, REST after
#   PERF_REGIMEN=rest  REST before `am start`, REST after: the pilot's
#                      control arm, at a known mode rather than whatever
#                      the device was left at
#   PERF_REGIMEN=off   touch nothing; record what the device reads
#
# REST IS RESTORED FROM THE EXIT TRAP, never from the end of the happy path.
# The owner's words (2026-09-26): "the very last thing I want is to drain the
# battery because a run crashed and the device was left sitting at a desktop
# on high performance". So every exit this script has -- the hold running
# out, the guest exiting, an adb failure, a TERM from a timeout or a
# preemption, an INT -- passes through release(), and release() restores.
# The one exit it cannot see is SIGKILL; host-tools' device_reality.sh
# restores REST on an idle handheld every 10 minutes for that one.
#
# What was set and what was restored goes to $PERF_RESULT (JSON, beside the
# capture by default) and to run.log as `PERF:` lines: perf_mode and
# fan_mode are the modes the title ran at, as read back from the device, and
# perf_restored is whether the read-back after restoring equals REST.
#
# A QUEUED SOAK picks its regimen with `request.sh --env PERF_REGIMEN=rest`.
# The dispatcher does not pass a request's env to this script (it goes to the
# app's env_vars pref, where an unknown name is harmless), so it is read here
# from the request the dispatcher is serving: CAPTURE_LOG is
# $D/results/<id>/logcat.txt and the request is $D/running/<id>.req while it
# runs. PERF_REQUEST names it directly. The shell's PERF_REGIMEN wins over
# both, and anything but max|rest|off is max.
if [ -z "${PERF_REGIMEN:-}" ]; then
    PERF_REQUEST="${PERF_REQUEST:-${CAPTURE_LOG:+$(dirname "$(dirname "$(dirname "$CAPTURE_LOG")")")/running/$(basename "$(dirname "$CAPTURE_LOG")").req}}"
    [ -n "$PERF_REQUEST" ] && [ -f "$PERF_REQUEST" ] &&
        PERF_REGIMEN=$(python3 -c 'import json,sys
for e in json.load(open(sys.argv[1])).get("env") or []:
    if e.startswith("PERF_REGIMEN="): print(e.split("=", 1)[1])' "$PERF_REQUEST" 2>/dev/null | tail -1)
fi
case "${PERF_REGIMEN:-}" in max|rest|off) ;; *) PERF_REGIMEN=max ;; esac
PERF_RESULT="${PERF_RESULT:-${CAPTURE_LOG:+$(dirname "$CAPTURE_LOG")/perf_regimen.json}}"
PERF_BEFORE=""; PERF_RAN=""; PERF_AFTER=""; PERF_RESTORED=""; PERF_SET=0
read -r PERF_MAX FAN_MAX PERF_REST FAN_REST <<<"$(device_perf_values "$SERIAL" 2>/dev/null)"

perf_write_result() {
    [ -n "$PERF_RESULT" ] || return 0
    python3 - "$PERF_RESULT" "$PERF_REGIMEN" "$PERF_BEFORE" "$PERF_RAN" \
        "$PERF_AFTER" "$PERF_RESTORED" "${PERF_MAX:-} ${FAN_MAX:-}" \
        "${PERF_REST:-} ${FAN_REST:-}" <<'PY' 2>/dev/null
import json, sys
path, regimen, before, ran, after, restored, want_max, want_rest = sys.argv[1:9]
def pair(s):
    # "2 3" -> [2, 3]; anything adb could not answer is null, not a guess.
    out = []
    for w in (s.split() + ["", ""])[:2]:
        out.append(int(w) if w.lstrip("-").isdigit() else None)
    return out
b, r, a = pair(before), pair(ran), pair(after)
json.dump(dict(regimen=regimen,
               perf_mode=r[0], fan_mode=r[1],
               perf_restored={"1": True, "0": False}.get(restored),
               before=dict(perf_mode=b[0], fan_mode=b[1]),
               restored=dict(perf_mode=a[0], fan_mode=a[1]),
               max=dict(zip(("perf_mode", "fan_mode"), pair(want_max))),
               rest=dict(zip(("perf_mode", "fan_mode"), pair(want_rest)))),
          open(path, "w"), indent=2)
PY
}

perf_enter() {
    PERF_BEFORE=$(device_perf_get)
    if [ -z "$PERF_MAX" ] || [ -z "$FAN_REST" ]; then
        echo "PERF: no regimen values for $SERIAL in devices.sh -- running at the device's own modes"
        PERF_REGIMEN="off(no values)"
    fi
    case "$PERF_REGIMEN" in
        max)  PERF_SET=1; PERF_RAN=$(device_perf_set "$PERF_MAX" "$FAN_MAX") ;;
        rest) PERF_SET=1; PERF_RAN=$(device_perf_set "$PERF_REST" "$FAN_REST") ;;
        *)    PERF_RAN="$PERF_BEFORE" ;;
    esac
    echo "PERF: regimen=$PERF_REGIMEN before=[$PERF_BEFORE] running=[$PERF_RAN]"
    perf_write_result
}

# Idempotent, and cheap when there is nothing to do, because release() runs
# on every exit, including one before perf_enter ever ran.
perf_leave() {
    [ "$PERF_SET" = 1 ] || return 0
    PERF_SET=0
    if [ -z "$PERF_REST" ] || [ -z "$FAN_REST" ]; then
        echo "PERF: NOT RESTORED -- no REST values for $SERIAL in devices.sh"
        PERF_RESTORED=0
    elif PERF_AFTER=$(device_perf_set "$PERF_REST" "$FAN_REST"); then
        PERF_RESTORED=1
    else
        # One more try: a single vsock drop is the common failure, and a
        # device left at MAX is the one outcome this exists to prevent.
        sleep "${SOAK_RETRY_S:-2}"
        if PERF_AFTER=$(device_perf_set "$PERF_REST" "$FAN_REST"); then
            PERF_RESTORED=1
        else
            PERF_RESTORED=0
        fi
    fi
    echo "PERF: restored=[$PERF_AFTER] perf_restored=$([ "$PERF_RESTORED" = 1 ] && echo true || echo false)"
    perf_write_result
}

# Always force-stop on the way out. The handheld does not charge over the adb
# cable, so a title left running flattens it -- and a game, unlike a test disc,
# never exits on its own.
#
# Disarming belongs here and not at the end of the happy path: a marker left
# behind by a run that crashed or was interrupted is exactly how the device
# came to be capturing audio for seven experiments that never asked for it.
#
# REST comes after the force-stop, so the title is never running at REST
# while the log still counts it, and before the sleep, so the screen goes off
# with the device already at REST.
release() {
    stop_route
    [ -n "$LOGCAT_PID" ] && kill "$LOGCAT_PID" 2>/dev/null
    a shell am force-stop "$PKG" >/dev/null 2>&1
    disarm_audio
    perf_leave
    a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
    rm -f "$LEASE"
}
# A signal EXITS, and the exit runs release() once. This was
# `trap release EXIT INT TERM`, under which a TERM ran release() and then
# returned into the hold loop: the soak went on polling a force-stopped title
# until its deadline, and ran release() a second time at the end.
trap release EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

a shell am force-stop "$PKG" >/dev/null 2>&1
a shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
arm_audio
perf_enter

if [ -n "$CAPTURE_LOG" ]; then
    a logcat -c >/dev/null 2>&1
    # Streamed, and started before `am start`: the lines worth having are
    # emitted in the first seconds and the ring turns over long before the
    # hold is up. Unwrapped by `a` deliberately -- this outlives the deadline.
    #
    # And respawned: one WSL `UtilAcceptVsock` failure ends the stream, and on
    # 2026-09-26 that left a 783 s Nova soak with an empty logcat.txt and no
    # verdict. A restart asks the ring for everything from the last captured
    # line's stamp (`-T "$last"`, no inner quotes: see the restart below), so
    # the lines the device logged during the drop are read back while the ring
    # still holds them. That replay reprints
    # the line the capture ended on, and title_verdict.py reads an exact
    # duplicate once. Each break is written INTO the capture as a
    # `# hakuX-capture: stream ended` line: a restart whose replay does not
    # overlap the last line lost something, and the verdict takes that span
    # (in device time, from the lines either side) out of its windows and its
    # hang gaps rather than scoring it as a guest with no flips. A break that
    # nothing follows (the restarts ran out) is a truncated capture, and the
    # verdict names that rather than a short run.
    : >"$CAPTURE_LOG"
    (
        child=""
        trap '[ -n "$child" ] && kill "$child" 2>/dev/null; exit 0' TERM
        n=0; last=""
        while [ "$n" -le "${LOGCAT_RESTARTS:-30}" ]; do
            # No stamp yet means nothing was captured, and the whole ring
            # then duplicates nothing.
            # shellcheck disable=SC2086
            if [ "$n" = 0 ] || [ -z "$last" ]; then
                adb -s "$SERIAL" logcat -v time $LOGCAT_SPEC >>"$CAPTURE_LOG" 2>/dev/null &
            else
                # A plain argument, unlike `adb shell`'s "'mark x'": `adb
                # logcat` escapes each argument itself (commandline.cpp
                # logcat(): escape_arg per arg), so inner quotes would reach
                # logcat's -T parser, which rejects them and exits -- and every
                # restart after the first drop would fail the same way.
                adb -s "$SERIAL" logcat -v time -T "$last" $LOGCAT_SPEC >>"$CAPTURE_LOG" 2>/dev/null &
            fi
            child=$!
            wait "$child"
            n=$((n+1))
            # `-v time`: "09-25 13:31:41.662 I/tag( pid): msg"
            last=$(tail -n 200 "$CAPTURE_LOG" | grep -oE '^[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}' | tail -1)
            echo "# hakuX-capture: stream ended after ${last:-no line}; restart $n" >>"$CAPTURE_LOG"
            echo "LOGCAT: stream ended at $(date +%H:%M:%S); restart $n"
            sleep "${LOGCAT_RESTART_S:-2}"
        done
    ) &
    LOGCAT_PID=$!
fi

a shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path '$ISO'" >/dev/null 2>&1
# In logcat, not only here: the verdict works in device time, and this line
# and the `soak end` below bound the run in that clock.
a shell log -t hakuX-route "'soak start'" >/dev/null 2>&1

# The route runs beside the hold loop rather than inside it, so a long `wait`
# in a route cannot starve the liveness check or the lease.
start_route() {
    [ -n "$ROUTE_FILE" ] || return 0
    if [ ! -f "$HERE/titles/route.sh" ] || [ ! -f "$HERE/perf/pad.sh" ]; then
        # A worker snapshot taken by an older snapshot_scripts does not carry
        # the subdirectories (host memory: a new snapshot file misses the first
        # re-exec). Say so where the verdict and a reader will both see it,
        # rather than holding a title for twenty minutes with no input.
        echo "ROUTE NOT PLAYED: $HERE/titles/route.sh or perf/pad.sh is missing from this snapshot"
        return 0
    fi
    if [ ! -s "$ROUTE_FILE" ]; then
        echo "ROUTE NOT PLAYED: $ROUTE_FILE is missing or empty"
        return 0
    fi
    SERIAL="$SERIAL" bash "$HERE/titles/route.sh" "$ROUTE_FILE" &
    ROUTE_PID=$!
    echo "ROUTE started pid $ROUTE_PID from $ROUTE_FILE"
}
# By PID, never by pattern (CLAUDE.md). route.sh traps TERM, releases any
# held button, recentres any moved stick, and logs `end`.
stop_route() {
    [ -n "$ROUTE_PID" ] || return 0
    kill "$ROUTE_PID" 2>/dev/null
    wait "$ROUTE_PID" 2>/dev/null
    ROUTE_PID=""
}
start_route

# Hold, but stop early if the guest dies -- a title that fails to boot should
# not burn the whole window, and "it exited" is itself a result worth having.
#
# ONE FAILED adb CALL IS NOT A GUEST EXIT. This was a single `adb shell ps`
# piped into grep, so an adb failure and an absent process were the same
# answer: a WSL `UtilAcceptVsock` error ended a 180 s Ghoulies soak at 35 s on
# 2026-09-25 as "guest exited" while the emulator was running. Now an adb
# failure -- a non-zero exit, or output without the `NAME` header `ps` always
# prints -- is retried up to three times, 2 s apart, and counted separately.
# Three failures in a row answer "unknown", and unknown keeps holding: the
# lease and the deadline still bound the run, and a real exit shows up on
# the next probe that works.
ADB_FAILURES=0
probe() {   # 0 running, 1 not running, 2 adb failed
    local out
    out=$(a shell 'ps -A -o NAME' 2>&1) || { PROBE_ERR="$(printf '%s' "$out" | head -1)"; return 2; }
    # toybox pads each row to the column width: the Nova prints `NAME` and
    # 23 spaces, so strip trailing blanks or every probe reads as a failure.
    out=$(printf '%s\n' "$out" | tr -d '\r' | sed 's/[[:space:]]*$//')
    printf '%s\n' "$out" | grep -qx NAME || { PROBE_ERR="$(printf '%s' "$out" | head -1)"; return 2; }
    printf '%s\n' "$out" | grep -qx "$PKG:xemu"
}
alive() {   # 0 running, 1 not running, 2 unknown after three adb failures
    local try r
    for try in 1 2 3; do
        PROBE_ERR=""
        probe; r=$?
        [ "$r" = 2 ] || return "$r"
        ADB_FAILURES=$((ADB_FAILURES+1))
        echo "ADB: liveness probe failed (try $try/3): ${PROBE_ERR:-no output}"
        [ "$try" = 3 ] || sleep "${SOAK_RETRY_S:-2}"
    done
    return 2
}
#
# Wall clock, not a count of 5 s sleeps: a retried probe costs seconds, and a
# 20-minute confirmation run should be 20 minutes whatever adb is doing.
s=0
appeared=0
t0=$(date +%s)
while [ "$s" -lt "$SECONDS_TO_HOLD" ]; do
    # SOAK_POLL_S / SOAK_RETRY_S exist for selftest.d/89, which drives this
    # loop against a fake adb in seconds rather than minutes.
    sleep "${SOAK_POLL_S:-5}"; s=$(( $(date +%s) - t0 ))
    touch "$LEASE"
    alive; r=$?
    if [ "$r" = 0 ]; then
        appeared=1
    elif [ "$r" = 1 ] && [ "$appeared" = 1 ]; then
        echo "guest exited after ${s}s of ${SECONDS_TO_HOLD}s"
        break
    fi
done
stop_route
a shell log -t hakuX-route "'soak end'" >/dev/null 2>&1
echo "adb_failures=$ADB_FAILURES"

if [ "$appeared" = 0 ]; then
    echo "guest never appeared in ${SECONDS_TO_HOLD}s -- title did not boot"
else
    echo "held $(basename "$ISO") for ${s}s"
fi

# Pull anything the guest recorded. The audio harness needs this: a PCM tap in
# the APU writes to the app's external files dir, and a soak is worthless as a
# measurement if the capture stays on the device. Generic on purpose -- PULL_GLOB
# names what to fetch, so the same path serves audio captures, register dumps or
# anything else a future harness writes.
#
# Force-stop FIRST so the file is closed and flushed before it is read; a
# half-written capture measures as a quieter one, which is exactly the kind of
# artefact that would be mistaken for a level change.
if [ -n "${PULL_GLOB:-}" ] && [ -n "${PULL_DEST:-}" ]; then
    a shell am force-stop "$PKG" >/dev/null 2>&1
    mkdir -p "$PULL_DEST"
    files=$(a shell "ls -1 $GUEST_FILES/$PULL_GLOB 2>/dev/null" | tr -d '\r')
    if [ -z "$files" ]; then
        echo "PULL: nothing matched $PULL_GLOB"
    else
        for f in $files; do
            if a pull "$f" "$PULL_DEST/" >/dev/null 2>&1 && [ -s "$PULL_DEST/$(basename "$f")" ]; then
                echo "PULL: $(basename "$f") $(stat -c%s "$PULL_DEST/$(basename "$f")") bytes"
                # Remove it on the device so the next soak cannot measure this
                # run's audio appended to the next run's.
                a shell "rm -f '$f'" >/dev/null 2>&1
            else
                # A pull can exit 0 having written nothing; that has surfaced
                # thirty lines later as a missing-file error before now.
                echo "PULL FAILED or empty: $f"
            fi
        done
    fi
fi
