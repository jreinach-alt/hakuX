#!/usr/bin/env bash
#
# Take and release a device hold. A hold is removed only by its taker.
#
#   hold.sh take    <label> <tag> <why...>               exit 0 taken, 3 held by someone else, 4 refused: non-release build (nova), 6 refused: owner-play capture would not start (hold not left behind)
#   hold.sh release <label> <tag>                        exit 0 released, 3 not yours (nothing removed)
#   hold.sh who     <label>                              exit 0 held (prints holder), 1 free
#   hold.sh wait    <label> <tag> <timeout_s> <why...>   take, retrying every 15 s; exit 3 on timeout
#   hold.sh wait-idle <label> <timeout_s>                exit 0 idle, 3 still busy at timeout, 1 no hold, 5 idle but an owner-play capture died
#
# TO USE A DEVICE YOURSELF:  hold.sh take <label> <tag> <why> && hold.sh wait-idle <label> 900
# and touch the device only if that exits 0. Release the hold on every exit path.
#
# <label> is the dispatcher's DEVICE_LABEL (thor, nova, ...). <tag> names the
# taker and is what release checks: use one nobody else would, e.g.
# lane.<name> or hostupd-<pid>. It is [A-Za-z0-9._:-]+.
#
# WHAT A HOLD IS. `$DISPATCH_DIR/hold/<label>` stops the dispatcher CLAIMING
# on that handheld (dispatcher.sh, top of the serve loop). It does not stop a
# request that is already running there, and so a running request
# (running/*.owner naming <label>) does NOT block `take`: the hold takes
# effect when that request ends. `wait-idle` is the second half: it returns 0
# only once the hold exists, the device's dispatcher has seen it, and no
# running/*.owner names <label>.
#
# WHY THIS EXISTS. Every writer and remover of hold/<label> was ad hoc: lanes
# wrote and os.remove()d it inline, host tools touch/rm'd it. Nothing checked
# that a hold existed before taking one, or that it was still yours before
# removing it. On 2026-09-26 the host update window held the Thor at 16:58:52
# PDT; at 17:00:19 a lane took the Thor, having checked only running/*.owner,
# overwrote hold/thor.why, and at 17:02:28 removed hold/thor. At 17:02:43 the
# Thor claimed a request INSIDE the window. dispatcher.sh's lane_release had
# the same "removes by NAME, not by owner" defect and was fixed the same way:
# remove only a file that still holds my token.
#
#   take     creates hold/<label> with O_CREAT|O_EXCL, so of two concurrent
#            takers exactly one wins, and an existing hold -- including a
#            bare `touch`ed one -- is never overwritten. The file holds <tag>;
#            <label>.why is written only by the winner, after the create.
#   release  removes hold/<label> and <label>.why only if hold/<label> holds
#            exactly <tag>. An empty (touched) hold matches no tag: whoever
#            placed it by hand removes it by hand.
#   wait-idle  polls every 5 s until all of these hold at once:
#            1. hold/<label> exists (any tag). Without it nothing stops a new
#               claim, and "idle now" says nothing about a second from now.
#               Exit 1 at once: take the hold first.
#            2. the device's dispatcher has SEEN the hold. Its worker checks
#               hold/ at the top of each tick, then walks the queue (an
#               affinity.py and a battery read per request, seconds) and only
#               then claims. A take that lands inside that walk is followed by
#               a claim, so running/ empty at the take proves nothing. The
#               worker registers its pid in lanes/<label> on every unheld tick
#               and removes it on the first held one, so lanes/<label> gone, or
#               naming a pid that is no longer a dispatcher.sh process, means
#               any claim from before the hold has already been written.
#            3. no running/*.owner holds <label>. The owner file is written at
#               the claim and removed after the result is written, so it covers
#               the pull and teardown too, which running/*.req does not.
#            On timeout it prints what still blocks and exits 3; the hold stays
#            in place, and the caller decides whether to wait longer or release.
#
# WHY wait-idle EXISTS. The second half above was a sentence in this comment,
# and callers skipped it. On 2026-09-27 20:01 PDT an arm claimed the Thor one
# second before lane.titleroutes' take, and the lane's launch killed the arm.
# On 2026-10-01 at 21:58:16 PDT lane.titleroutes' session 61 took the Nova
# 2.5 min into 1790914021-lane.ibcache-3203127 and force-stopped hakuX twice
# (am_kill 21:58:26 and :29); the #507 leg died at 132 of 420 s and was void.
# take and wait also print a NOT IDLE notice on stderr when the device is busy.
#
# OWNER-PLAY HOLDS AND THE CAPTURE (#433, 10-18). A <tag> starting `owner-play`
# is a hold taken so the owner can play a title by hand, never automated. The
# release app writes no readable telemetry and the device's logcat ring turns
# over every ~2-3 minutes, so an owner playthrough survives only in a
# host-side `adb logcat` capture that was ALREADY running when the title
# launched. On 2026-10-18 the owner's first Fable launch (jerky intro videos,
# audio skips, the first 30 s) was lost because nothing was capturing when the
# hold was taken at 07:09; on 10-17 a Halo run survived only by luck (a
# capture left over from an unrelated lane run). Memory notes existed and
# were not enough -- the hold itself now does it:
#
#   take     starts the capture (`adb -s <serial> logcat -v threadtime -T 1
#            <LOGCAT_SPEC>`, the dispatcher's own spec, sourced fresh rather
#            than copied) as a transient user systemd unit,
#            `hakux-ownerplay-capture-<label>`, appended to
#            `$DISPATCH_DIR/../captures/owner-play-<YYYYMMDD>/logcat-<label>-
#            <HHMMSS>.txt`, so it outlives the shell that took the hold. If a
#            capture for that label is already running, take does not start a
#            second: it reports the existing one's path and age. If the
#            capture cannot be started at all (no adb, device not listed,
#            systemd refused), take prints `NO CAPTURE: ...` on stderr, exits
#            6, and the hold is NOT left behind -- an unrecorded owner session
#            is exactly the failure this exists to prevent, so a hold nobody
#            can act on is worse than no hold.
#   who      for an owner-play hold also prints the capture's path and age, or
#            `NO CAPTURE RUNNING` if the unit died under it.
#   wait-idle on an owner-play hold additionally checks the capture: exit 0
#            prints the capture line too, and a dead capture is now a failure
#            (exit 5) even though the device itself is idle -- the idle check
#            and the capture check are one gate, because "idle, unrecorded" is
#            exactly as dangerous as "busy, unrecorded".
#   release  stops the capture unit only when the release itself succeeded
#            (the taker's tag matched), and prints the capture file's path and
#            size. A refused release leaves the capture running, same as it
#            leaves the hold.
#
# Detection of "is label's capture still alive" is never by asking systemd:
# this harness's own selftest shims `systemctl ... is-active` to always print
# `active`, for any unit name, so that would be a check that cannot fail. It
# is a pidfile this file writes itself (`hold/<label>.capture.pid`, the
# capture loop's own `$$`) plus a `/proc/<pid>/cmdline` check -- the same
# "a pid naming what it claims to be" idiom `hold_py idle`'s `lanes/<label>`
# check below already uses, for the same reason: a stale number is not proof
# of anything alive, and PID reuse after a reboot would otherwise lie.
#
# DISPATCH_DIR resolves as dispatcher.sh and request.sh resolve it.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
HOLD_WAIT_INTERVAL="${HOLD_WAIT_INTERVAL:-15}"
HOLD_IDLE_INTERVAL="${HOLD_IDLE_INTERVAL:-5}"

usage() { sed -n '3,24p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

valid() { [[ "$2" =~ ^[A-Za-z0-9._:-]+$ ]] || { echo "hold.sh: bad $1 '$2' (want [A-Za-z0-9._:-]+)" >&2; exit 2; }; }

# ------------------------------------------------------- owner-play capture

owner_play() { case "$1" in owner-play*) return 0 ;; *) return 1 ;; esac; }

cap_unit()     { printf 'hakux-ownerplay-capture-%s' "$1"; }
cap_pidfile()  { printf '%s/hold/%s.capture.pid' "$D" "$1"; }
cap_pathfile() { printf '%s/hold/%s.capture' "$D" "$1"; }

# label_serial <label>  ->  the attached serial whose DEVICE_LABEL is <label>,
# on stdout; non-zero when no adb, or no attached device matches. Same shape
# as stop-emulator.sh's device_label_lease, run the other direction: devices.sh
# has no label->serial lookup (device_env only goes serial->label), so every
# caller that needs one iterates `adb devices` and matches $DEVICE_LABEL.
label_serial() {
    local label="$1" serial out
    command -v adb >/dev/null 2>&1 || return 1
    while IFS= read -r serial; do
        [ -n "$serial" ] || continue
        out=$( . "$HERE/../devices.sh" >/dev/null 2>&1
               device_env "$serial" >/dev/null 2>&1 && printf '%s' "$DEVICE_LABEL" )
        [ "$out" = "$label" ] && { printf '%s\n' "$serial"; return 0; }
    done < <(adb devices 2>/dev/null | tr -d '\r' | awk 'NR>1 && $2=="device"{print $1}')
    return 1
}

# logcat_spec  ->  dispatcher.sh's own LOGCAT_SPEC on stdout. Sourced fresh
# (one source, not a copy that can drift) the same way
# selftest.d/51-dispatch-hardening.sh already reads it back out: a bogus
# subcommand hits dispatcher.sh's `*)` fallthrough (usage text only, which is
# discarded here) after LOGCAT_SPEC is exported, so nothing beyond
# `mkdir -p "$D"/{queue,running,results,logs}` runs. In a subshell: dispatcher.sh
# sets and exports plenty that must not leak into this process.
logcat_spec() {
    ( export DISPATCH_DIR="$D" SERIAL="${SERIAL:-ee317437}"
      . "$HERE/../dispatcher.sh" hold-sh-logcat-spec >/dev/null 2>&1
      printf '%s' "$LOGCAT_SPEC" )
}

# capture_since <label>  ->  the capture's start time (the pidfile's mtime),
# UTC, or "unknown" if unreadable.
capture_since() {
    date -u -r "$(cap_pidfile "$1")" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown
}

# capture_running <label>  ->  0 and the log path on stdout when a capture
# process for <label> is alive and really is one (not a reused pid): the
# pidfile's pid answers to a signal and /proc/<pid>/cmdline still mentions
# logcat. Else 1 and nothing.
capture_running() {
    local pf path pid
    pf=$(cap_pidfile "$1"); path=$(cap_pathfile "$1")
    [ -f "$pf" ] && [ -f "$path" ] || return 1
    pid=$(cat "$pf" 2>/dev/null)
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    grep -q logcat "/proc/$pid/cmdline" 2>/dev/null || return 1
    cat "$path"
}

# capture_report <label>  ->  0 and "capture: <path> (running since <time>)"
# on stdout, else 1 and nothing.
capture_report() {
    local path
    path=$(capture_running "$1") || return 1
    printf 'capture: %s (running since %s)\n' "$path" "$(capture_since "$1")"
}

# capture_ensure <label>  ->  0 and the capture_report line (a pre-existing
# capture reused as-is, or a freshly started one), or 1 and a one-line reason
# on stdout, for the caller to print as `NO CAPTURE: <reason>`.
capture_ensure() {
    local label="$1" line serial spec capdir log pf
    if line=$(capture_report "$label"); then printf '%s\n' "$line"; return 0; fi
    command -v adb >/dev/null 2>&1 || { printf 'no adb on PATH\n'; return 1; }
    serial=$(label_serial "$label") || { printf 'device %s not listed by adb devices\n' "$label"; return 1; }
    spec=$(logcat_spec)
    [ -n "$spec" ] || { printf 'LOGCAT_SPEC unknown (dispatcher.sh did not export it)\n'; return 1; }
    capdir="$D/../captures/owner-play-$(date -u +%Y%m%d)"
    mkdir -p "$capdir" 2>/dev/null || { printf 'could not create %s\n' "$capdir"; return 1; }
    log="$capdir/logcat-$label-$(date -u +%H%M%S).txt"
    pf=$(cap_pidfile "$label")
    rm -f "$pf"
    # The script: a restart loop that appends on every (re)start, marking the
    # gap, and exits cleanly (killing the current adb child with it) on
    # SIGTERM -- the same trap/background/wait shape
    # selftest.d/79-stop-hook-hold.sh's own dispatcher.sh fixture uses for "a
    # backgrounded process that dies cleanly". Single-quoted here: every `$`
    # below must stay literal until the capture's own bash evaluates it --
    # SERIAL/LOG/SPEC/PIDFILE arrive as its environment (--setenv), not by
    # substitution into this string.
    local script='trap "kill $cur 2>/dev/null; exit 0" TERM
echo "$$" > "$PIDFILE"
while :; do
    printf "=== capture (re)start %s ===\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
    adb -s "$SERIAL" logcat -v threadtime -T 1 $SPEC >> "$LOG" 2>&1 &
    cur=$!
    wait "$cur"
    rc=$?
    printf "=== capture process exited rc=%s at %s; restarting after a gap ===\n" "$rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
    sleep 2
done'
    if ! systemd-run --user --unit "$(cap_unit "$label")" --collect \
            --setenv=SERIAL="$serial" --setenv=LOG="$log" --setenv=SPEC="$spec" --setenv=PIDFILE="$pf" \
            bash -c "$script" >/dev/null 2>&1
    then
        printf 'systemd-run refused to start %s\n' "$(cap_unit "$label")"
        return 1
    fi
    local tries=0
    while [ ! -s "$pf" ] && [ "$tries" -lt 25 ]; do sleep 0.2; tries=$((tries + 1)); done
    printf '%s\n' "$log" > "$(cap_pathfile "$label")"
    if line=$(capture_report "$label"); then printf '%s\n' "$line"; return 0; fi
    printf '%s never confirmed running after systemd-run accepted it\n' "$(cap_unit "$label")"
    return 1
}

# capture_release <label>  ->  stops <label>'s capture (if any) and prints
# its file and size, or a "no record" line if there was none. Always
# succeeds: called only after a release has already succeeded, so there is
# nothing left to refuse.
capture_release() {
    local label="$1" unit pf path pid log size
    unit=$(cap_unit "$label"); pf=$(cap_pidfile "$label"); path=$(cap_pathfile "$label")
    pid=$(cat "$pf" 2>/dev/null)
    # systemctl is the production mechanism (a real transient unit); killing
    # the pidfile's own pid is what actually guarantees the stop -- the only
    # mechanism this harness's own selftest (its systemd-run shim never
    # starts a real unit) can exercise, and it works the same way in
    # production: the capture script's own TERM trap tears down its current
    # adb child and exits.
    command -v systemctl >/dev/null 2>&1 && systemctl --user stop "$unit" >/dev/null 2>&1
    [[ "$pid" =~ ^[0-9]+$ ]] && kill "$pid" 2>/dev/null
    if [ -f "$path" ]; then
        log=$(cat "$path")
        size=$(stat -c %s "$log" 2>/dev/null || echo '?')
        printf 'capture: %s (%s bytes)\n' "$log" "$size"
    else
        printf 'capture: no record for %s\n' "$label"
    fi
    rm -f "$pf" "$path"
}

# The whole state machine is python: bash has O_EXCL (set -C) but no way to
# read-compare-remove without a second process, and one language for both
# halves keeps the file format in one place.
hold_py() {
    python3 - "$D" "$@" <<'PY'
import os, sys, time
d, op, label = sys.argv[1], sys.argv[2], sys.argv[3]
hdir = os.path.join(d, "hold")
path = os.path.join(hdir, label)
why = path + ".why"

def read(p):
    try:
        with open(p) as f:
            return f.read()
    except FileNotFoundError:
        return None

def holder():
    tag = read(path)
    if tag is None:
        return None
    tag = tag.rstrip("\n") or "(untagged: placed by hand; remove it by hand)"
    reason = (read(why) or "").strip() or "(no .why)"
    return "held: %s by %s -- %s" % (label, tag, reason)

if op == "who":
    h = holder()
    print(h or "free: %s" % label)
    sys.exit(0 if h else 1)

if op == "idle":
    # One poll of wait-idle (header, conditions 1-3), in that order: 2 before
    # 3, because a claim from inside the worker's last unheld walk writes its
    # owner file before the worker's next tick removes lanes/<label>.
    if read(path) is None:
        print("no hold: %s is not held, so nothing stops a new claim; take it first" % label)
        sys.exit(1)
    busy = []
    lane = (read(os.path.join(d, "lanes", label)) or "").strip()
    if lane.isdigit():
        try:
            with open("/proc/%s/cmdline" % lane, "rb") as f:
                live = b"dispatcher.sh" in f.read()
        except OSError:
            live = False
        if live:
            busy.append("dispatcher pid %s has not seen the hold yet (lanes/%s is still registered): "
                        "it may be claiming, or a request is running" % (lane, label))
    rdir = os.path.join(d, "running")
    try:
        names = sorted(os.listdir(rdir))
    except FileNotFoundError:
        names = []
    for n in names:
        if not n.endswith(".owner") or (read(os.path.join(rdir, n)) or "").strip() != label:
            continue
        rid = n[:-len(".owner")]
        if os.path.exists(os.path.join(rdir, rid + ".req")):
            busy.append("running: %s on %s" % (rid, label))
        else:
            busy.append("running: %s on %s (its .req has left running/: the result is being written "
                        "and the device torn down; the worker clears the owner file when it ends)" % (rid, label))
    if busy:
        print("\n".join(busy))
        sys.exit(3)
    print("idle: %s is held and runs nothing" % label)
    sys.exit(0)

tag = sys.argv[4]
if op == "take":
    reason = sys.argv[5]
    os.makedirs(hdir, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        print(holder() or "held: %s (released while reading)" % label, file=sys.stderr)
        sys.exit(3)
    with os.fdopen(fd, "w") as f:
        f.write(tag + "\n")
    tmp = "%s.%d.tmp" % (why, os.getpid())
    with open(tmp, "w") as f:
        f.write("%s %s: %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), tag, reason))
    os.replace(tmp, why)
    print("taken: %s by %s" % (label, tag))
    sys.exit(0)

if op == "release":
    cur = read(path)
    if cur is None:
        print("free: %s (nothing to release)" % label, file=sys.stderr)
        sys.exit(3)
    if cur.rstrip("\n") != tag:
        print(holder(), file=sys.stderr)
        print("not released: the hold is not %s's" % tag, file=sys.stderr)
        sys.exit(3)
    # .why first: a .why without a hold is harmless, a hold without its .why
    # is a hold nobody can explain. Between the compare and the unlink no
    # other taker can create the file (it exists); only a hand `rm` could.
    try:
        os.remove(why)
    except FileNotFoundError:
        pass
    os.remove(path)
    print("released: %s by %s" % (label, tag))
    sys.exit(0)
sys.exit(2)
PY
}

# THE BUILD GATE (10-06). A lane that holds the Nova to measure gets the build
# the Nova last ran, and a test build (a branch, an env A/B) left on it is
# what the next measurement runs on. Refused before the hold is written, with
# the build named: device_build.py reads the device's newest result.json. Only
# the labels in HOLD_RELEASE_LABELS are gated (nova); the Thor's screening
# runs deliberately vary their env. HOLD_RELEASE_LABELS="" turns it off.
HOLD_RELEASE_LABELS="${HOLD_RELEASE_LABELS-nova}"
label_gated() { case " $HOLD_RELEASE_LABELS " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
# ON A REFUSAL, PROMOTE THE RESTORE (#433, 10-11). The dispatcher's own
# off-master restore (queue_master_restore) names its request with a bare
# id, so it serves in ASCII order behind every release-tier request -- which
# is every request a lane queues on a night like 15:36-10-10's, so the lone
# restore starved for hours and a human renamed it by hand each time. Every
# served request installs its own apk and writes its own env before any
# soak starts (serve_one, dispatcher.sh:1375 build_ref, :1410 adb install,
# :1425 apply_env_pref, ahead of the restore exit at :1445 and the title/suite
# paths after it) -- so the bare id costs nothing to a served measurement.
# It only matters here, to a caller about to run something BY HAND on
# whatever the hold leaves installed. So the gate itself promotes: it finds
# the device's pending restore and gives it the file a "0-" prefix, queuing
# one first if none is pending. device_build.py's own restore_request stays
# bare; only the promote command's rename adds the prefix.
build_gate() {   # $1 label ; 0 pass, 4 refused (named on stderr)
    label_gated "$1" || return 0
    local out rc
    out=$(python3 "$(dirname "$0")/device_build.py" check "$D" "$1" 2>&1); rc=$?
    [ "$rc" -eq 0 ] && return 0
    echo "hold.sh: refusing $1: $out" >&2
    if [ "$rc" -eq 4 ]; then
        local pout
        pout=$(python3 "$(dirname "$0")/device_build.py" promote "$D" "$1" 2>&1)
        echo "hold.sh: $pout" >&2
    fi
    return "$rc"
}

# After a successful take: say so on stderr if the device is not idle yet. The
# exit code and stdout are take's own; this only puts the second half in front
# of a caller who reads one line and starts (session 61 read "taken:").
notice_idle() {
    local out
    out=$(hold_py idle "$label") && return 0
    [ $? -eq 3 ] || return 0
    printf 'NOT IDLE: %s is held but busy -- do not touch it yet:\n%s\n' "$label" "$out" >&2
    printf 'run: hold.sh wait-idle %s <timeout_s>, and touch the device only on exit 0\n' "$label" >&2
}

[ $# -ge 2 ] || usage
op=$1 label=$2
valid label "$label"
case "$op" in
    who)
        [ $# -eq 2 ] || usage
        hold_py who "$label"; rc=$?
        if [ "$rc" -eq 0 ] && owner_play "$(cat "$D/hold/$label" 2>/dev/null)"; then
            capture_report "$label" || echo "NO CAPTURE RUNNING"
        fi
        exit "$rc" ;;
    take)
        [ $# -ge 4 ] || usage
        valid tag "$3"
        build_gate "$label" || exit $?
        hold_py take "$label" "$3" "${*:4}" || exit $?
        if owner_play "$3"; then
            if ! cap_line=$(capture_ensure "$label"); then
                echo "NO CAPTURE: $cap_line" >&2
                hold_py release "$label" "$3" >/dev/null 2>&1
                exit 6
            fi
            echo "$cap_line"
            echo "$cap_line" >&2
        fi
        notice_idle ;;
    wait-idle)
        [ $# -eq 3 ] || usage
        [[ "$3" =~ ^[0-9]+$ ]] || { echo "hold.sh: timeout '$3' is not whole seconds" >&2; exit 2; }
        deadline=$(( $(date +%s) + $3 )) said=""
        while :; do
            out=$(hold_py idle "$label")
            rc=$?
            # 0 idle and 1 no hold are answers; anything but 3 is an error.
            if [ "$rc" -eq 3 ]; then
                : # still busy, fall through to the timeout/retry below
            elif [ "$rc" -eq 0 ] && owner_play "$(cat "$D/hold/$label" 2>/dev/null)"; then
                echo "$out"
                if cap_line=$(capture_report "$label"); then
                    echo "$cap_line"
                    exit 0
                fi
                echo "NO CAPTURE RUNNING: $label's owner-play capture died" >&2
                exit 5
            else
                [ "$rc" -eq 0 ] && echo "$out" || echo "$out" >&2
                exit "$rc"
            fi
            if [ "$(date +%s)" -ge "$deadline" ]; then
                echo "$out" >&2
                echo "hold.sh: $label still busy after $3 s; the hold is still yours to keep or release" >&2
                exit 3
            fi
            [ "$out" = "$said" ] || { echo "waiting for $label: $out" >&2; said=$out; }
            sleep "$HOLD_IDLE_INTERVAL"
        done ;;
    release)
        [ $# -eq 3 ] || usage
        valid tag "$3"
        hold_py release "$label" "$3"; rc=$?
        [ "$rc" -eq 0 ] && owner_play "$3" && capture_release "$label"
        exit "$rc" ;;
    wait)
        [ $# -ge 5 ] || usage
        valid tag "$3"
        [[ "$4" =~ ^[0-9]+$ ]] || { echo "hold.sh: timeout '$4' is not whole seconds" >&2; exit 2; }
        deadline=$(( $(date +%s) + $4 ))
        # A build-gate refusal (4) promoted the restore (build_gate's own
        # side effect); keep polling the gate, not exit at once, so a caller
        # already willing to wait gets to run once the ~60 s restore lands.
        # Any other refusal (gate off, or device_build.py itself erroring)
        # is not something waiting fixes.
        #
        # THE RACE (addendum 1, #433, 10-11). The dispatcher claims its next
        # request the instant the promoted restore finishes -- it checks
        # hold/<label> only at the top of its tick, before the queue
        # (dispatcher.sh:2354-2363) -- which can land seconds before this
        # loop's next poll. A poll that trusted build_gate alone would read
        # the restore's own result.json (still the newest; the new request
        # has not finished and written one yet), pass, and take the hold
        # while a fresh off-master request is running RIGHT NOW: exactly
        # what the gate exists to prevent. So for a gated label, ask what is
        # in running/ before trusting a pass:
        #   - the label's OWN restore is running: take the hold now, before
        #     it finishes, so the dispatcher's claim loop stops right after
        #     it and the device is left on master.
        #   - anything else is running: that run will leave the device off
        #     master when it ends. Do not even ask build_gate (its answer
        #     would be the stale pass above) -- keep polling. Its own
        #     completion re-queues a bare restore (device_build.py's
        #     restore hook), the next refusal promotes it, and the
        #     "restore running" case above then catches it.
        #   - nothing is running: build_gate's answer is current; act on it.
        # An ungated label skips the running check entirely (forced rrc=2,
        # straight to build_gate, which itself passes at once for it) -- the
        # Thor's screening runs are routinely "other" by design and must not
        # make wait sit there waiting for them to finish.
        #
        # THE FED-QUEUE GAP (addendum 2, #433, 10-11). On a queue that is
        # actually fed (the brief's own starting point: a release-tier
        # stream reclaiming the device within seconds of each run ending),
        # "something else is running" is what rrc reads on almost every
        # poll -- rrc=2, and therefore build_gate, and therefore promote, is
        # only reached in the rare instant between one run ending and the
        # next being claimed. Left as comment-and-sleep, this branch never
        # promotes anything, and wait times out with the restore still bare
        # -- worse than before this lane, when a human promoted it by hand.
        # So promote from here too, forced: the pending-restore and
        # running-restore checks in cmd_promote still run first and still
        # win (no duplicate), but when neither is true, --force skips the
        # "is a restore even needed" read (it would see whatever ran before
        # this in-flight request, which on a fed queue is often another
        # master run, and wrongly decline to queue one for the request
        # that is CURRENTLY running and WILL leave the device off master).
        # Once promoted, drop to the 5 s cap so the restore's transition
        # into running/ -- the rrc=0 case above -- is not missed either.
        interval="$HOLD_WAIT_INTERVAL"
        while :; do
            if label_gated "$label"; then
                rout=$(python3 "$(dirname "$0")/device_build.py" running "$D" "$label"); rrc=$?
            else
                rrc=2
            fi
            if [ "$rrc" -eq 0 ]; then
                echo "hold.sh: $label: $rout -- taking the hold before it finishes" >&2
                break
            elif [ "$rrc" -eq 2 ]; then
                build_gate "$label" && break
                rc=$?
                [ "$rc" -eq 4 ] || exit "$rc"
                interval=5
            else
                echo "hold.sh: $label: $rout is running (not the restore) -- waiting for it to finish" >&2
                pout=$(python3 "$(dirname "$0")/device_build.py" promote "$D" "$label" --force 2>&1)
                echo "hold.sh: $pout" >&2
                interval=5
            fi
            if [ "$(date +%s)" -ge "$deadline" ]; then
                echo "hold.sh: timed out after $4 s waiting for $label's master restore" >&2
                exit 4
            fi
            sleep "$interval"
        done
        while :; do
            hold_py take "$label" "$3" "${*:5}" 2>/dev/null && { notice_idle; exit 0; }
            rc=$?
            [ "$rc" -eq 3 ] || exit "$rc"
            if [ "$(date +%s)" -ge "$deadline" ]; then
                hold_py who "$label" >&2
                echo "hold.sh: timed out after $4 s waiting for $label" >&2
                exit 3
            fi
            sleep "$HOLD_WAIT_INTERVAL"
        done ;;
    *) usage ;;
esac
