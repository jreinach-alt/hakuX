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

# Always force-stop on the way out. The handheld does not charge over the adb
# cable, so a title left running flattens it -- and a game, unlike a test disc,
# never exits on its own.
#
# Disarming belongs here and not at the end of the happy path: a marker left
# behind by a run that crashed or was interrupted is exactly how the device
# came to be capturing audio for seven experiments that never asked for it.
release() {
    stop_route
    [ -n "$LOGCAT_PID" ] && kill "$LOGCAT_PID" 2>/dev/null
    a shell am force-stop "$PKG" >/dev/null 2>&1
    disarm_audio
    a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
    rm -f "$LEASE"
}
trap release EXIT INT TERM

a shell am force-stop "$PKG" >/dev/null 2>&1
a shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
arm_audio

if [ -n "$CAPTURE_LOG" ]; then
    a logcat -c >/dev/null 2>&1
    # Streamed, and started before `am start`: the lines worth having are
    # emitted in the first seconds and the ring turns over long before the
    # hold is up. Unwrapped by `a` deliberately -- this outlives the deadline.
    # shellcheck disable=SC2086
    adb -s "$SERIAL" logcat -v time $LOGCAT_SPEC >"$CAPTURE_LOG" 2>/dev/null &
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
