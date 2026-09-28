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
FG_WATCH_PID=""
# Written by the foreground watcher (fg_watch below) when it aborts the route.
FG_FLAG="${TMPDIR:-/tmp}/soak-fg.$$"; rm -f "$FG_FLAG"

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
#   PERF_REGIMEN=default  the device's own defaults before `am start`, REST
#                      after: performance_mode 0 (NORMAL) and fan_mode 4
#                      (SMART), the settings library's defaults on both
#                      handhelds (devices.sh). Not REST by another name:
#                      REST is what a handheld is left at and may change;
#                      this is the mode a player who never opens the OEM
#                      menu plays in, the one sustained play is judged at
#                      (#507, 2026-09-27). A thermal pause in a `default`
#                      run FAILS it (title_verdict.py); at MAX it voids.
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
# `display` holds what else sets a handheld's draw, read at `start` (after the
# modes are set) and at `end` (the hold over, the title still running):
# min_refresh_rate, peak_refresh_rate, screen_brightness and its mode, the
# Thor's dual_screen_display_mode, and each logical display's power state
# (`displays`, from dumpsys display: the Thor's second screen is one). A
# setting adb could not read is null; a device without it reads "null".
#
# A QUEUED SOAK picks its regimen with `request.sh --env PERF_REGIMEN=rest`.
# The dispatcher does not pass a request's env to this script (it goes to the
# app's env_vars pref, where an unknown name is harmless), so it is read here
# from the request the dispatcher is serving: CAPTURE_LOG is
# $D/results/<id>/logcat.txt and the request is $D/running/<id>.req while it
# runs. PERF_REQUEST names it directly. The shell's PERF_REGIMEN wins over
# both, and anything but max|rest|off|default is max.
if [ -z "${PERF_REGIMEN:-}" ]; then
    PERF_REQUEST="${PERF_REQUEST:-${CAPTURE_LOG:+$(dirname "$(dirname "$(dirname "$CAPTURE_LOG")")")/running/$(basename "$(dirname "$CAPTURE_LOG")").req}}"
    [ -n "$PERF_REQUEST" ] && [ -f "$PERF_REQUEST" ] &&
        PERF_REGIMEN=$(python3 -c 'import json,sys
for e in json.load(open(sys.argv[1])).get("env") or []:
    if e.startswith("PERF_REGIMEN="): print(e.split("=", 1)[1])' "$PERF_REQUEST" 2>/dev/null | tail -1)
fi
case "${PERF_REGIMEN:-}" in max|rest|off|default) ;; *) PERF_REGIMEN=max ;; esac
PERF_DEFAULT=0; FAN_DEFAULT=4
PERF_DISPLAY_START=""; PERF_DISPLAY_END=""
PERF_RESULT="${PERF_RESULT:-${CAPTURE_LOG:+$(dirname "$CAPTURE_LOG")/perf_regimen.json}}"
PERF_BEFORE=""; PERF_RAN=""; PERF_AFTER=""; PERF_RESTORED=""; PERF_SET=0
read -r PERF_MAX FAN_MAX PERF_REST FAN_REST <<<"$(device_perf_values "$SERIAL" 2>/dev/null)"

perf_write_result() {
    [ -n "$PERF_RESULT" ] || return 0
    python3 - "$PERF_RESULT" "$PERF_REGIMEN" "$PERF_BEFORE" "$PERF_RAN" \
        "$PERF_AFTER" "$PERF_RESTORED" "${PERF_MAX:-} ${FAN_MAX:-}" \
        "${PERF_REST:-} ${FAN_REST:-}" "$PERF_DEFAULT $FAN_DEFAULT" \
        "$PERF_DISPLAY_START" "$PERF_DISPLAY_END" <<'PY' 2>/dev/null
import json, sys
path, regimen, before, ran, after, restored, want_max, want_rest, want_default = sys.argv[1:10]
def disp(s):
    try:
        return json.loads(s) if s else None
    except ValueError:
        return None
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
               rest=dict(zip(("perf_mode", "fan_mode"), pair(want_rest))),
               default=dict(zip(("perf_mode", "fan_mode"), pair(want_default))),
               display=dict(start=disp(sys.argv[10]), end=disp(sys.argv[11]))),
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
        default) PERF_SET=1; PERF_RAN=$(device_perf_set "$PERF_DEFAULT" "$FAN_DEFAULT") ;;
        *)    PERF_RAN="$PERF_BEFORE" ;;
    esac
    echo "PERF: regimen=$PERF_REGIMEN before=[$PERF_BEFORE] running=[$PERF_RAN]"
    PERF_DISPLAY_START=$(perf_display)
    echo "PERF: display at start $PERF_DISPLAY_START"
    perf_write_result
}

# perf_display  ->  one JSON object of the display settings (see `display`
# above), from ONE adb call. {} when adb said nothing.
perf_display() {
    adb_call "${ADB_QUICK_TIMEOUT:-20}" "display settings read" shell \
        'for k in min_refresh_rate peak_refresh_rate screen_brightness screen_brightness_mode dual_screen_display_mode; do echo "set $k=$(settings get system $k)"; done; dumpsys display | grep "mBaseDisplayInfo="' \
        2>/dev/null | tr -d '\r' | python3 -c '
import json, re, sys
out, disp = {}, {}
for line in sys.stdin:
    m = re.match(r"set (\w+)=(.*)$", line.strip())
    if m:
        v = m.group(2).strip()
        out[m.group(1)] = None if v == "" else (int(v) if re.fullmatch(r"-?\d+", v) else float(v) if re.fullmatch(r"-?\d+\.\d+", v) else v)
        continue
    i, st = re.search(r"displayId (\d+)", line), re.search(r", state (\w+)", line)
    if i:
        disp[i.group(1)] = st.group(1) if st else None
# {} when adb answered but no display line matched: this firmware prints another shape.
if disp or out:
    out["displays"] = disp
print(json.dumps(out, sort_keys=True, separators=(",", ":")))'
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
    rm -f "$LEASE" "$FG_FLAG"
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

# THE DISPLAY MUST BE OURS. A foreign overlay on display 0 renders every
# hakuX frame black and stalls its flips while the device reads Awake
# (display_clear in devices.sh has the 2026-09-27 case). Checked after the
# wake and before anything is armed or started, so a refused run leaves no
# marker, no MAX mode and no title behind, and writes no frame to be scored.
# The `display-covered:` line lands in run.log at the start of a line, where
# title_verdict.py reads it and voids the run; the dispatcher writes its
# result either way, so the request ends as a void result, not a requeue.
# Unknown (adb could not say) is recorded and the run goes on: the
# black-frame guard below is the backstop for that case.
#
# The refusal skips release(): nothing it undoes has happened yet, and its
# KEYCODE_SLEEP would put the screen out under the owner's app, which is
# whatever raised the overlay. That is their session, not ours to put away.
DISPLAY_STATE=$(display_clear "$SERIAL"); display_rc=$?
echo "$DISPLAY_STATE"
if [ "$display_rc" = 1 ]; then
    trap - EXIT
    rm -f "$LEASE"
    echo "soak refused: display 0 is not hakuX's to draw on; nothing was started"
    exit 4
fi

# THE THERMAL RECORD (#507). Under MAX the Thor's kernel pauses cpu3-7 a few
# minutes in (`thermal-pause-F8`, bound to xo-therm's 78 C trip) and fps falls
# 5-7x; no other readout shows it. thermal_state.py reads every cooling device
# and zone in one adb call and appends one JSON line to thermal.jsonl beside
# the capture: once just before `am start`, once every THERMAL_EVERY_S (30 s)
# from the hold loop below (no second poller), and once at the end.
# title_verdict.py voids a scored window a pause may overlap; the `THERMAL:`
# line in run.log is for a reader.
THERMAL_OUT="${THERMAL_OUT:-${CAPTURE_LOG:+$(dirname "$CAPTURE_LOG")/thermal.jsonl}}"
thermal_sample() {   # <label>
    [ -n "$THERMAL_OUT" ] || return 0
    if [ ! -f "$HERE/thermal_state.py" ]; then
        # An older snapshot (see ROUTE NOT PLAYED below): say so once; no
        # thermal.jsonl then reads as `unread`, never as `no pause`.
        echo "THERMAL: not recorded: $HERE/thermal_state.py is missing from this snapshot"
        THERMAL_OUT=""
        return 0
    fi
    # stderr to run.log: a sampler traceback writes no line, and a reader
    # should see why a gap is there (the verdict voids it either way).
    python3 "$HERE/thermal_state.py" "$SERIAL" --label "$1" >>"$THERMAL_OUT"
    return 0
}
[ -n "$THERMAL_OUT" ] && rm -f "$THERMAL_OUT"

# THE COOL-DOWN GATE (#507; thermal_state.py has why). Before MAX is set, and
# with the title stopped, wait while THERMAL_COOL_ZONE reads at or above
# THERMAL_COOL_C or a pause device is set. The wait is capped at
# THERMAL_COOL_MAX_S (a run then starts hot, and says so) because
# harness_health.py calls a soak overrunning at `seconds` + 10 min. The
# samples are `cool` lines in thermal.jsonl. THERMAL_COOL_C=off turns it off.
# run.log gets one `COOLDOWN:` line, at the start of a line: `waited <s> s,
# xo <start> -> <end> C` (0 s when the first read was cool), `gave up at <C>
# C`, or `not gated`. The bracket holds --cool's own words for the last read.
#
# The wait is wall time ($SECONDS): each pass also costs an adb call and two
# python3 starts, and the overrun line counts those too. `--cool` reads the
# file's last line, so a sampler that wrote none (a traceback) would have the
# gate re-read the previous, hot sample: no new line is unread, not hot.
if [ "${THERMAL_COOL_C:-65}" != off ]; then
    cool_lines() { if [ -f "$THERMAL_OUT" ]; then wc -l < "$THERMAL_OUT"; else echo 0; fi; }
    cool_t0=$SECONDS; cool_from=""
    while :; do
        # Taken before the read, so a device that is cool at once waited 0 s.
        cool_waited=$((SECONDS - cool_t0))
        cool_n=$(cool_lines)
        thermal_sample cool
        [ -n "$THERMAL_OUT" ] || break
        if [ "$(cool_lines)" -le "$cool_n" ]; then
            echo "COOLDOWN: not gated after ${cool_waited} s: the sampler wrote no line"
            break
        fi
        cool_is=$(python3 "$HERE/thermal_state.py" --cool "$THERMAL_OUT" \
            "${THERMAL_COOL_ZONE:-xo-therm}" "${THERMAL_COOL_C:-65}" 2>&1); cool_rc=$?
        if [ "$cool_rc" = 2 ]; then
            echo "COOLDOWN: not gated after ${cool_waited} s: $cool_is"
            break
        fi
        # --cool's phrase opens `<zone> <C> C`.
        cool_c=$(printf '%s\n' "$cool_is" | sed -n 's/^[^ ]* \(-\{0,1\}[0-9.]*\) C.*/\1/p')
        [ -n "$cool_from" ] || cool_from="$cool_c"
        if [ "$cool_rc" = 0 ]; then
            echo "COOLDOWN: waited ${cool_waited} s, xo $cool_from -> $cool_c C [$cool_is]"
            break
        fi
        if [ "$cool_waited" -ge "${THERMAL_COOL_MAX_S:-360}" ]; then
            echo "COOLDOWN: gave up at $cool_c C after ${cool_waited} s, xo $cool_from -> $cool_c C [$cool_is]; starting hot"
            break
        fi
        sleep "${THERMAL_COOL_EVERY_S:-20}"
    done
fi

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

thermal_sample start

# Quoted for the device's sh by devices.sh: a bare '...' broke on a title
# with an apostrophe ("Tom Clancy's ...").
a shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path $(_dev_sq "$ISO")" >/dev/null 2>&1
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
    fg_wait || return 1
    SERIAL="$SERIAL" bash "$HERE/titles/route.sh" "$ROUTE_FILE" &
    ROUTE_PID=$!
    echo "ROUTE started pid $ROUTE_PID from $ROUTE_FILE"
    [ -n "${ROUTE_DRY:-}" ] && return 0
    fg_watch &
    FG_WATCH_PID=$!
}
# By PID, never by pattern (CLAUDE.md). route.sh traps TERM, releases any
# held button, recentres any moved stick, and logs `end`.
stop_route() {
    [ -n "$FG_WATCH_PID" ] && kill "$FG_WATCH_PID" 2>/dev/null && wait "$FG_WATCH_PID" 2>/dev/null
    FG_WATCH_PID=""
    [ -n "$ROUTE_PID" ] || return 0
    kill "$ROUTE_PID" 2>/dev/null
    wait "$ROUTE_PID" 2>/dev/null
    ROUTE_PID=""
}

# THE ROUTE DRIVES hakuX AND NOTHING ELSE. Its input is evdev events on the
# pad node, delivered to whichever window holds input focus. On 2026-09-27 a
# route pressed buttons into the Thor's launcher and started Lime3DS, and
# a route launched Lime3DS again at 12:12 (devices.sh hakux_in_front has
# both). So before the first input, and every FG_POLL_S (2 s) while the route
# runs, the input system's focused display must be 0 and its focused window
# hakuX's (read from `dumpsys input`, not from a first-match mCurrentFocus).
#
# Before the first input: wait up to FG_WAIT_S for hakuX to come up, then
# try ONE remedy that sends no input -- `am start` of hakuX on display 0 --
# and wait FG_REMEDY_S more. Never a tap or a key to move focus: that first
# input is exactly what drives the wrong app (one exception, the USB dialog,
# is under FG_POLL_S). Then abort.
#
# While the route runs: one `not-foreground` answer, or two unknowns in a
# row, TERMs route.sh at once, logs `ROUTE ABORTED: not foreground
# (<pkg>)` and a `not-foreground:` line, and ends the hold. It aborts; it
# never pauses and resumes. title_verdict.py voids a run on that line, and
# the soak exits 5.
#
# route.sh by PID, not its process group: a `press` is pad.sh sending
# key-down, sleeping 60 ms, then key-up, and a group kill in that gap leaves
# the button held down on the app in front. route.sh's TERM trap runs as soon
# as the press in flight returns (its `wait` on a sleep returns at once),
# stops the route there, and sends only releases for held buttons.
FG_POLL_S="${FG_POLL_S:-2}"
# ONE EXCEPTION to "never a key": a replugged handheld raises Android's "Use
# USB for" dialog, a bare system-alert window of the vendor settings package
# (com.rp.settings on the Nova, com.odin.settings on the Thor) that holds
# input focus on display 0 over hakuX. `am start` cannot close it, so on
# 2026-09-27 22:30 PDT every soak on both handhelds aborted until someone
# pressed BACK. One KEYCODE_BACK closes it and focus returns to hakuX. So the
# foreground wait, and only the wait (no route input has been sent), sends
# ONE BACK when display 0's focused window is exactly `<hash> <pkg>` for one
# of these packages: no `/`, so not an activity. An activity of any app, and
# a bare window of any other package, get nothing.
USB_DIALOG_PKGS="com.rp.settings com.odin.settings"
usb_dialog() {   # <hakux_in_front line> -> the package, if its window is the dialog
    local pkg="${1#not-foreground: }" p name
    case "$1" in "not-foreground: "*" (holds input focus on display 0 of "*) ;; *) return 1 ;; esac
    pkg="${pkg%% *}"
    for p in $USB_DIALOG_PKGS; do [ "$p" = "$pkg" ] && break; p=""; done
    [ -n "$p" ] || return 1
    # hakux_in_front keeps only the owner; re-read the raw name to see the `/`.
    # The live block only, as there: stop at the last ANR's snapshot.
    name=$(ADB_RETRIES=1 adb_call "${ADB_QUICK_TIMEOUT:-10}" "usb dialog read" shell "dumpsys input" \
            2>/dev/null | tr -d '\r' | awk '
        stop { next }
        /^  ANR:/ || (seen && /FocusedDisplayId:/) { stop = 1; next }
        /FocusedDisplayId:/ { seen = 1 }
        /^  [A-Za-z]+:/ { sec = $1; sub(/:.*/, "", sec) }
        sec == "FocusedWindows" && /displayId=0, name=\047/ {
            e = $0; sub(/.*displayId=0, name=\047/, "", e); sub(/\047.*/, "", e); print e; exit
        }')
    [[ "$name" =~ ^[0-9a-f]+\ ([^/\ ]+)$ ]] && [ "${BASH_REMATCH[1]}" = "$pkg" ] || return 1
    echo "$pkg"
}
# The BACK is read-then-act across two adb calls, and Android delivers a key
# to whatever holds focus when it is dispatched. If anything else closes the
# dialog in that gap (a person, or the host's interim dismisser timer), our
# BACK reaches hakuX, whose BACK toggles its pause menu: emulation paused, and
# the overlay is a view in hakuX's own window, so hakux_in_front still reads
# in-front and the route would play into the menu. The same holds for the
# other dismisser's BACK after ours. So after a BACK, before the route starts,
# read the overlay's visibility from `dumpsys activity top` (the view
# hierarchy: `PauseMenuOverlay{<hash> V...` shown, `G`/`I` not). Shown: one
# BACK, now to hakuX, resumes it; still shown, or no overlay line at all,
# aborts rather than play a route whose pause state is not known.
hakux_paused() {   # -> 0 paused, 1 not paused, 2 unknown
    local v
    v=$(ADB_RETRIES=1 adb_call "${ADB_QUICK_TIMEOUT:-10}" "pause menu read" shell \
            "dumpsys activity top | grep -F 'PauseMenuOverlay{'; true" 2>/dev/null \
        | tr -d '\r' | sed -n 's/.*PauseMenuOverlay{[0-9a-f]* \(.\).*/\1/p' | tr -d '\n')
    case "$v" in *V*) return 0 ;; ?*) return 1 ;; *) return 2 ;; esac
}
fg_unpaused() {   # after the dialog BACK, hakuX in front: 0 when it is not paused
    hakux_paused; case $? in
        1) return 0 ;;
        2) echo "FOREGROUND: hakuX's pause menu state is unreadable after the BACK"; return 1 ;;
    esac
    echo "FOREGROUND: hakuX is paused (a BACK reached it after the dialog closed); one BACK resumes it"
    a shell input keyevent KEYCODE_BACK >/dev/null 2>&1
    sleep "$FG_POLL_S"
    hakux_paused; case $? in
        1) echo "FOREGROUND: hakuX resumed"; return 0 ;;
        0) echo "FOREGROUND: hakuX is still paused after one BACK" ;;
        *) echo "FOREGROUND: hakuX's pause menu state is unreadable after the resume BACK" ;;
    esac
    return 1
}
fg_abort() {   # <hakux_in_front line>
    local pkg="${1#not-foreground: }"; pkg="${pkg%% *}"
    echo "ROUTE ABORTED: not foreground ($pkg)"
    echo "$1"
    : > "$FG_FLAG"
}
fg_wait() {
    local st rc last="" deadline remedy=0 back=0 pkg
    if [ -n "${ROUTE_DRY:-}" ]; then
        echo "FOREGROUND: not checked: ROUTE_DRY, the route sends no input"
        return 0
    fi
    deadline=$(( $(date +%s) + ${FG_WAIT_S:-30} ))
    while :; do
        st=$(hakux_in_front "$SERIAL"); rc=$?
        if [ "$rc" = 0 ]; then
            echo "$st"
            [ "$back" = 0 ] && return 0
            fg_unpaused && return 0
            fg_abort "not-foreground: hakuX-paused (its pause menu may hold input after the USB dialog BACK)"
            echo "ROUTE NOT PLAYED: hakuX's pause state after the USB dialog BACK is not known clear; no route input was sent"
            return 1
        fi
        [ "$st" = "$last" ] || echo "FOREGROUND: waiting: $st"; last="$st"
        if [ "$rc" = 1 ] && [ "$back" = 0 ] && pkg=$(usb_dialog "$st"); then
            back=1
            a shell input keyevent KEYCODE_BACK >/dev/null 2>&1
            echo "FOREGROUND: dismissed $pkg dialog (KEYCODE_BACK)"
            sleep "$FG_POLL_S"
            continue
        fi
        if [ "$(date +%s)" -ge "$deadline" ]; then
            [ "$remedy" = 1 ] && break
            remedy=1
            echo "FOREGROUND: re-issuing am start on display 0 (no input is sent)"
            a shell "am start --display 0 -a android.intent.action.VIEW -n $ACT --es rom_path $(_dev_sq "$ISO")" >/dev/null 2>&1
            deadline=$(( $(date +%s) + ${FG_REMEDY_S:-15} ))
        fi
        sleep "$FG_POLL_S"
    done
    [ "$rc" = 1 ] || st="not-foreground: unknown (${st#foreground-unknown: })"
    fg_abort "$st"
    echo "ROUTE NOT PLAYED: hakuX did not hold display 0 and input focus; no input was sent"
    return 1
}
fg_watch() {
    local st rc unk=0 state ps_out
    trap 'exit 0' TERM
    while :; do
        sleep "$FG_POLL_S"
        # A finished route is a zombie until stop_route reaps it: stop there.
        state=$(awk '{print $3}' "/proc/$ROUTE_PID/stat" 2>/dev/null)
        [ -n "$state" ] && [ "$state" != Z ] || return 0
        st=$(hakux_in_front "$SERIAL"); rc=$?
        if [ "$rc" = 2 ]; then
            unk=$((unk+1)); echo "FOREGROUND: $st ($unk/2)"
            [ "$unk" -ge 2 ] || continue
            st="not-foreground: unknown (${st#foreground-unknown: })"
        elif [ "$rc" = 0 ]; then
            unk=0; continue
        fi
        kill "$ROUTE_PID" 2>/dev/null
        # A guest that died closes hakuX to whatever is behind it, which then
        # reads as not in front. That run is an exit, not a void: stop the
        # route (its input must not reach the launcher either), raise no
        # flag, and let the hold loop's alive() report `guest exited`.
        # probe() is defined after this subshell forked, so ps is read here.
        ps_out=$(a shell 'ps -A -o NAME' 2>/dev/null | tr -d '\r' | sed 's/[[:space:]]*$//')
        if printf '%s\n' "$ps_out" | grep -qx NAME && ! printf '%s\n' "$ps_out" | grep -qx "$PKG:xemu"; then
            echo "ROUTE STOPPED: $PKG:xemu is gone, so the guest exited ($st)"
            return 0
        fi
        fg_abort "$st"
        return 0
    done
}

if ! start_route; then
    a shell log -t hakuX-route "'soak end'" >/dev/null 2>&1
    echo "soak aborted: not-foreground before the route's first input"
    exit 5
fi

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
SOAK_RC=0
t0=$(date +%s)
thermal_s=0
while [ "$s" -lt "$SECONDS_TO_HOLD" ]; do
    # SOAK_POLL_S / SOAK_RETRY_S exist for selftest.d/89, which drives this
    # loop against a fake adb in seconds rather than minutes.
    sleep "${SOAK_POLL_S:-5}"; s=$(( $(date +%s) - t0 ))
    touch "$LEASE"
    if [ $((s - thermal_s)) -ge "${THERMAL_EVERY_S:-30}" ]; then
        thermal_sample hold; thermal_s=$s
    fi
    if [ -f "$FG_FLAG" ]; then
        echo "soak aborted: not-foreground after ${s}s of ${SECONDS_TO_HOLD}s"
        SOAK_RC=5
        break
    fi
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
thermal_sample end
PERF_DISPLAY_END=$(perf_display)
echo "PERF: display at end $PERF_DISPLAY_END"
perf_write_result
[ -n "$THERMAL_OUT" ] && python3 "$HERE/thermal_state.py" --summary "$THERMAL_OUT"

# THE BLACK-FRAME GUARD. A 1920x1080 all-black PNG is 10,899 B; every route
# frame of the 2026-09-27 covered-display runs was exactly that. When every
# frame the route took is under DISPLAY_BLACK_B, nothing the route did was
# seen. Black frames have two causes, and they are not the same answer:
#   display-black:  something else covered display 0 or held focus -- a
#                   harness failure; title_verdict.py voids the run.
#   render-black:   display 0 is clear and hakuX holds focus, and hakuX drew
#                   black -- the title's failure, judged, not re-queued.
# The check that separates them is the one the soak starts with, run again
# now, while hakuX is still up: display_clear AND hakux_in_front. Both clear
# is render-black; anything else, unknown included, is display-black.
# title_verdict.py also voids a run on the frames themselves when run.log
# has no render-black line (a run.log from before this guard).
if [ -n "$ROUTE_FILE" ]; then
    rf="${ROUTE_FRAMES:-$(dirname "$ROUTE_FILE")/route-frames}"
    nf=0; nsmall=0; big=0
    for f in "$rf"/*.png; do
        [ -f "$f" ] || continue
        sz=$(stat -c%s "$f"); nf=$((nf+1))
        [ "$sz" -lt "${DISPLAY_BLACK_B:-12288}" ] && nsmall=$((nsmall+1))
        [ "$sz" -gt "$big" ] && big=$sz
    done
    if [ "$nf" -gt 0 ] && [ "$nsmall" = "$nf" ]; then
        black="all $nf route frames under ${DISPLAY_BLACK_B:-12288} B (largest $big B)"
        end_disp=$(display_clear "$SERIAL"); end_disp_rc=$?
        end_fg=$(hakux_in_front "$SERIAL"); end_fg_rc=$?
        if [ "$end_disp_rc" = 0 ] && [ "$end_fg_rc" = 0 ]; then
            echo "render-black: $black -- display 0 is clear and hakuX holds focus, so hakuX drew black ($end_disp; $end_fg)"
        else
            echo "display-black: $black -- display 0 was not hakuX's at the end of the hold ($end_disp; $end_fg)"
        fi
    fi
fi

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
exit "$SOAK_RC"
