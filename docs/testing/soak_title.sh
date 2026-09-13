#!/usr/bin/env bash
#
#   soak_title.sh <device-iso-path> <seconds>
#
# Env: CAPTURE_LOG, LOGCAT_SPEC, PULL_GLOB, PULL_DEST, GUEST_FILES,
#      AUDIO_CAPTURE_MB (arm the APU PCM capture at this size cap, and clear
#      any previous capture first; disarmed again on the way out)
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

# Hold, but stop early if the guest dies -- a title that fails to boot should
# not burn the whole window, and "it exited" is itself a result worth having.
alive() { a shell 'ps -A -o NAME' | tr -d '\r' | grep -qx "$PKG:xemu"; }
s=0
appeared=0
while [ "$s" -lt "$SECONDS_TO_HOLD" ]; do
    sleep 5; s=$((s+5))
    touch "$LEASE"
    if alive; then
        appeared=1
    elif [ "$appeared" = 1 ]; then
        echo "guest exited after ${s}s of ${SECONDS_TO_HOLD}s"
        break
    fi
done

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
