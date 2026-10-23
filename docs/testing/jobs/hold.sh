#!/usr/bin/env bash
#
# Take and release a device hold. A hold is removed only by its taker.
#
#   hold.sh take    <label> [--tier blocker|fps|sweep] <tag> <why...>
#                                                       exit 0 taken, 3 held by someone else, 4 refused: non-release build (nova), 6 refused: owner-play capture would not start (hold not left behind), 8 refused: sweep tier beaten by queued/running 0-/1- work for this label
#   hold.sh release <label> <tag>                        exit 0 released, 3 not yours (nothing removed)
#   hold.sh who     <label>                              exit 0 held (prints holder), 1 free
#   hold.sh wait    <label> [--tier blocker|fps|sweep] <tag> <timeout_s> <why...>
#                                                       take, retrying every 15 s; exit 3 on timeout. At --tier sweep, never takes while 0-*/1-* work is queued or running for this label -- keeps retrying instead.
#   hold.sh wait-idle <label> <timeout_s>                exit 0 idle, 3 still busy at timeout, 1 no hold, 5 idle but an owner-play capture died
#   hold.sh yield-check <label> <tag>                    exit 0 keep going, 7 yield now: a 0-* request is queued or running for <label>, or a 1-* one has been queued at least HOLD_YIELD_S (60) s
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
# is a pidfile the capture writes itself (`hold/<label>.capture.pid`, its own
# `$$`) plus a check that the pid really is this label's capture: its
# /proc/<pid>/environ carries `PIDFILE=<that pidfile's path>`, which
# `--setenv` gave the unit and nothing else on the host has. (It used to be
# "/proc/<pid>/cmdline mentions logcat", which any `adb logcat` or `grep
# logcat` answers to, and which held only because the whole script was on
# bash's command line.) The same idiom `hold_py idle`'s `lanes/<label>` check
# below uses, for the same reason: a stale number is not proof of anything
# alive, and PID reuse after a reboot would otherwise lie.
#
# THE LAUNCH PASSES NO `$` TO SYSTEMD. systemd rewrites the command line of a
# unit before it execs it (systemd.service(5), "Command lines"): `$$` becomes
# `$`, `${VAR}` is replaced from the unit's environment, a whole argument
# `$VAR` is replaced and word-split (dropped if unset). A script handed over as
# `bash -c "$script"` therefore lost its `$$`, the pidfile held a literal `$`,
# and `take` exited 6 on 2026-10-22. The capture script is written to
# `hold/<label>.capture.sh` and run as `bash <file>`: the argv has no `$` in it
# for systemd to touch, whatever the script says.
#
# TIERS (#433, 10-19). A hold also carries a tier: blocker (a release defect
# that needs on-device time), fps (today's default -- also the FPS-focus
# chain's own tier), or sweep (idle-time screening of new titles, the
# lowest). --tier on take/wait sets it; env HOLD_TIER is the fallback; no
# tier at all is fps, so a caller nobody has updated keeps its old priority
# instead of silently dropping to the bottom. Recorded in <label>.tier,
# written by take's winner and removed by release, same rules as <label>.why.
#
# A SWEEP TAKE NEVER BEATS QUEUED WORK. take and wait at --tier sweep refuse
# (exit 8; wait keeps polling instead of exiting) while a `0-*` (blocker) or
# `1-*` (release/fps) request for this device label -- queued in
# dispatch/queue/, or already running -- exists. "For this label" is
# affinity.py's own answer, the same eligibility dispatcher.sh's serve_one
# asks, not a guess from the id string: an unpinned request counts too,
# since it could land on this label as easily as a pinned one.
#
# COOPERATIVE YIELD. A chain already holding a device at --tier sweep calls
# `hold.sh yield-check <label> <tag>` between steps, never mid-capture (an
# in-flight capture finishes first): exit 7 means release now and re-wait at
# --tier sweep; exit 0 means keep going. A sweep hold also expires on its
# own after HOLD_SWEEP_MAX_S (1800 s default) -- nothing runs on a timer to
# release it, so the next contending take notices the stale tier file and
# clears it rather than waiting forever on a chain that died without
# releasing.
#
# DISPATCH_DIR resolves as dispatcher.sh and request.sh resolve it.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
HOLD_WAIT_INTERVAL="${HOLD_WAIT_INTERVAL:-15}"
HOLD_IDLE_INTERVAL="${HOLD_IDLE_INTERVAL:-5}"

usage() { sed -n '3,27p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

valid() { [[ "$2" =~ ^[A-Za-z0-9._:-]+$ ]] || { echo "hold.sh: bad $1 '$2' (want [A-Za-z0-9._:-]+)" >&2; exit 2; }; }

# ------------------------------------------------------- owner-play capture

owner_play() { case "$1" in owner-play*) return 0 ;; *) return 1 ;; esac; }

cap_unit()     { printf 'hakux-ownerplay-capture-%s' "$1"; }
cap_pidfile()  { printf '%s/hold/%s.capture.pid' "$D" "$1"; }
cap_pathfile() { printf '%s/hold/%s.capture' "$D" "$1"; }
cap_script()   { printf '%s/hold/%s.capture.sh' "$D" "$1"; }

# cap_owns <label> <pid>  ->  0 when <pid> is a process started as <label>'s
# capture unit: its environment carries the exact `PIDFILE=` line the unit was
# given. A recycled pid, or any process that merely mentions logcat, is not.
cap_owns() {
    tr '\0' '\n' < "/proc/$2/environ" 2>/dev/null | grep -qxF -- "PIDFILE=$(cap_pidfile "$1")"
}

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
# pidfile's pid answers to a signal and cap_owns says it was started as this
# label's capture. Else 1 and nothing.
capture_running() {
    local pf path pid
    pf=$(cap_pidfile "$1"); path=$(cap_pathfile "$1")
    [ -f "$pf" ] && [ -f "$path" ] || return 1
    pid=$(cat "$pf" 2>/dev/null)
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    cap_owns "$1" "$pid" || return 1
    cat "$path"
}

# capture_stop <label>  ->  stops <label>'s capture unit. TERM to the pidfile's
# pid first, but only if cap_owns says it is the capture (a stale pidfile must
# not get an unrelated process killed): the script's TERM trap kills its adb
# child and exits. Then `systemctl --user stop`, which on a real systemd also
# takes the unit's whole cgroup and its name with it.
capture_stop() {
    local pid
    pid=$(cat "$(cap_pidfile "$1")" 2>/dev/null)
    [[ "$pid" =~ ^[0-9]+$ ]] && cap_owns "$1" "$pid" && kill "$pid" 2>/dev/null
    command -v systemctl >/dev/null 2>&1 && systemctl --user stop "$(cap_unit "$1")" >/dev/null 2>&1
    return 0
}

# capture_report <label>  ->  0 and "capture: <path> (running since <time>)"
# on stdout, else 1 and nothing.
capture_report() {
    local path
    path=$(capture_running "$1") || return 1
    printf 'capture: %s (running since %s)\n' "$path" "$(capture_since "$1")"
}

# capture_script  ->  the capture's script on stdout. A restart loop that
# appends on every (re)start, marking the gap, and exits cleanly (killing the
# current adb child with it) on SIGTERM -- the same trap/background/wait shape
# selftest.d/79-stop-hook-hold.sh's own dispatcher.sh fixture uses for "a
# backgrounded process that dies cleanly". Written to a file and run as
# `bash <file>` (see THE LAUNCH PASSES NO `$` TO SYSTEMD above), so every `$`
# below is bash's own. SERIAL/LOG/SPEC/PIDFILE arrive as its environment
# (--setenv); --setenv values are not expanded by systemd.
#
# THE TRAP IS SINGLE-QUOTED. Double-quoted (`trap "kill $cur ..."`), bash
# expands $cur when `trap` runs, with cur unset, and the stored trap is
# `kill  2>/dev/null; exit 0`: TERM then never reached the adb child. The sleep
# between restarts is a background child waited on, so a TERM during it is
# handled at once instead of after the sleep. `set -f`: SPEC ends in `*:S`, and
# it is word-split unquoted below, so it must not be globbed against the cwd.
capture_script() {
    cat <<'CAPTURE_SCRIPT'
# Written by hold.sh (capture_script). Run as `bash <this file>` by a transient
# user unit; SERIAL, LOG, SPEC and PIDFILE are in its environment.
set -f
cur=
trap 'kill "$cur" 2>/dev/null; exit 0' TERM
echo "$$" > "$PIDFILE"
while :; do
    printf '=== capture (re)start %s ===\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
    adb -s "$SERIAL" logcat -v threadtime -T 1 $SPEC >> "$LOG" 2>&1 &
    cur=$!
    wait "$cur"
    rc=$?
    printf '=== capture process exited rc=%s at %s; restarting after a gap ===\n' "$rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
    sleep 2 &
    cur=$!
    wait "$cur"
done
CAPTURE_SCRIPT
}

# capture_ensure <label>  ->  0 and the capture_report line (a pre-existing
# capture reused as-is, or a freshly started one), or 1 and a one-line reason
# on stdout, for the caller to print as `NO CAPTURE: <reason>`. A unit that
# systemd accepted but that never showed itself is stopped before the 1: left
# running it would hold the unit name against the next take and append to a log
# nobody is told about.
capture_ensure() {
    local label="$1" line serial spec capdir log pf cs
    if line=$(capture_report "$label"); then printf '%s\n' "$line"; return 0; fi
    command -v adb >/dev/null 2>&1 || { printf 'no adb on PATH\n'; return 1; }
    serial=$(label_serial "$label") || { printf 'device %s not listed by adb devices\n' "$label"; return 1; }
    spec=$(logcat_spec)
    [ -n "$spec" ] || { printf 'LOGCAT_SPEC unknown (dispatcher.sh did not export it)\n'; return 1; }
    capdir="$D/../captures/owner-play-$(date -u +%Y%m%d)"
    mkdir -p "$capdir" 2>/dev/null || { printf 'could not create %s\n' "$capdir"; return 1; }
    log="$capdir/logcat-$label-$(date -u +%H%M%S).txt"
    pf=$(cap_pidfile "$label"); cs=$(cap_script "$label")
    rm -f "$pf"
    capture_script > "$cs" 2>/dev/null || { printf 'could not write %s\n' "$cs"; return 1; }
    if ! systemd-run --user --unit "$(cap_unit "$label")" --collect \
            --setenv=SERIAL="$serial" --setenv=LOG="$log" --setenv=SPEC="$spec" --setenv=PIDFILE="$pf" \
            bash "$cs" >/dev/null 2>&1
    then
        rm -f "$cs"
        printf 'systemd-run refused to start %s\n' "$(cap_unit "$label")"
        return 1
    fi
    local tries=0
    while [ ! -s "$pf" ] && [ "$tries" -lt "${HOLD_CAPTURE_CONFIRM_TRIES:-25}" ]; do sleep 0.2; tries=$((tries + 1)); done
    printf '%s\n' "$log" > "$(cap_pathfile "$label")"
    if line=$(capture_report "$label"); then printf '%s\n' "$line"; return 0; fi
    capture_stop "$label"
    rm -f "$pf" "$(cap_pathfile "$label")" "$cs"
    printf '%s never confirmed running after systemd-run accepted it\n' "$(cap_unit "$label")"
    return 1
}

# capture_release <label>  ->  stops <label>'s capture (if any) and prints
# its file and size, or a "no record" line if there was none. Always
# succeeds: called only after a release has already succeeded, so there is
# nothing left to refuse.
capture_release() {
    local label="$1" pf path log size
    pf=$(cap_pidfile "$label"); path=$(cap_pathfile "$label")
    capture_stop "$label"
    if [ -f "$path" ]; then
        log=$(cat "$path")
        size=$(stat -c %s "$log" 2>/dev/null || echo '?')
        printf 'capture: %s (%s bytes)\n' "$log" "$size"
    else
        printf 'capture: no record for %s\n' "$label"
    fi
    rm -f "$pf" "$path" "$(cap_script "$label")"
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
tier_path = path + ".tier"
if op == "take":
    tier = sys.argv[5]
    reason = sys.argv[6]
    os.makedirs(hdir, exist_ok=True)
    def try_create():
        return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        fd = try_create()
    except FileExistsError:
        # A sweep hold expires on its own after HOLD_SWEEP_MAX_S (1800 s
        # default, #433 10-19): nothing runs on a timer to release it, so
        # the next contending take is what notices a stale one and clears
        # it, rather than a dead screening chain holding the device forever.
        expired = False
        if (read(tier_path) or "").strip() == "sweep":
            try:
                age = time.time() - os.path.getmtime(path)
            except OSError:
                age = 0.0
            max_s = float(os.environ.get("HOLD_SWEEP_MAX_S", "1800"))
            if age >= max_s:
                for p in (path, why, tier_path):
                    try:
                        os.remove(p)
                    except FileNotFoundError:
                        pass
                expired = True
        if not expired:
            print(holder() or "held: %s (released while reading)" % label, file=sys.stderr)
            sys.exit(3)
        try:
            fd = try_create()
        except FileExistsError:
            print(holder() or "held: %s (released while reading)" % label, file=sys.stderr)
            sys.exit(3)
    with os.fdopen(fd, "w") as f:
        f.write(tag + "\n")
    tmp = "%s.%d.tmp" % (why, os.getpid())
    with open(tmp, "w") as f:
        f.write("%s %s: %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), tag, reason))
    os.replace(tmp, why)
    ttmp = "%s.%d.tmp" % (tier_path, os.getpid())
    with open(ttmp, "w") as f:
        f.write(tier + "\n")
    os.replace(ttmp, tier_path)
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
    # .tier follows the same rule, for the same reason.
    try:
        os.remove(why)
    except FileNotFoundError:
        pass
    try:
        os.remove(tier_path)
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

# sweep_blocker <label>  ->  the first 0-*/1-* request id (queued in
# dispatch/queue/, or already running) that is FOR this device label, on
# stdout; nothing and exit 1 if none. "For this label" is affinity.py's own
# answer -- the same eligibility dispatcher.sh's serve_one asks -- not a
# guess from the id string: an unpinned 0-/1- request counts too, since it
# could land on this label as easily as a pinned one. A request already
# running is checked against its running/<id>.owner, where it actually
# landed, not affinity.py's answer for a request already claimed.
sweep_blocker() {
    local label="$1" f id owner want
    for f in "$D"/running/*.req; do
        [ -f "$f" ] || continue
        id=$(basename "$f" .req)
        case "$id" in 0-*|1-*) ;; *) continue ;; esac
        owner=$(cat "$D/running/$id.owner" 2>/dev/null)
        [ "$owner" = "$label" ] && { printf '%s\n' "$id"; return 0; }
    done
    for f in "$D"/queue/*.req; do
        [ -f "$f" ] || continue
        id=$(basename "$f" .req)
        case "$id" in 0-*|1-*) ;; *) continue ;; esac
        want=$(python3 "$HERE/../affinity.py" "$D" "$f" 2>/dev/null)
        if [ -z "$want" ] || [ "$want" = "$label" ]; then
            printf '%s\n' "$id"
            return 0
        fi
    done
    return 1
}

# yield_signal <label>  ->  the blocking request id and exit 0 when a sweep
# hold on <label> should release NOW: any 0-* request queued or running for
# it, or a 1-* one that has sat in queue/ (not yet running) at least
# HOLD_YIELD_S (60) seconds. Nothing and exit 1 otherwise. Shares
# sweep_blocker's running/ check (a 0-/1- already running is always urgent);
# the queue/ half re-checks age, so a 1- that just landed does not yield a
# sweep hold that was about to finish its own step anyway.
yield_signal() {
    local label="$1" f id epoch now owner want
    now=$(date +%s)
    for f in "$D"/running/*.req; do
        [ -f "$f" ] || continue
        id=$(basename "$f" .req)
        case "$id" in 0-*|1-*) ;; *) continue ;; esac
        owner=$(cat "$D/running/$id.owner" 2>/dev/null)
        [ "$owner" = "$label" ] && { printf '%s\n' "$id"; return 0; }
    done
    for f in "$D"/queue/*.req; do
        [ -f "$f" ] || continue
        id=$(basename "$f" .req)
        case "$id" in
            0-*) epoch="${id#0-}"; epoch="${epoch%%-*}" ;;
            1-*) epoch="${id#1-}"; epoch="${epoch%%-*}" ;;
            *) continue ;;
        esac
        want=$(python3 "$HERE/../affinity.py" "$D" "$f" 2>/dev/null)
        { [ -z "$want" ] || [ "$want" = "$label" ]; } || continue
        case "$id" in
            0-*) printf '%s\n' "$id"; return 0 ;;
            1-*)
                [[ "$epoch" =~ ^[0-9]+$ ]] || continue
                if [ $(( now - epoch )) -ge "${HOLD_YIELD_S:-60}" ]; then
                    printf '%s\n' "$id"
                    return 0
                fi
                ;;
        esac
    done
    return 1
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
shift 2
# --tier blocker|fps|sweep, take/wait only; env HOLD_TIER is the fallback;
# absent is fps (today's priority), not sweep -- a caller nobody has
# updated must not silently drop to the bottom. Consumed here, positionally,
# so every case body below still sees exactly the $3/$4/... shape it always
# has: $1=op $2=label, tag/timeout/why unchanged.
TIER="${HOLD_TIER:-}"
case "$op" in
    take|wait)
        if [ "${1:-}" = "--tier" ]; then
            [ $# -ge 2 ] || usage
            TIER=$2
            shift 2
        fi
        ;;
esac
case "$TIER" in
    ''|blocker|fps|sweep) ;;
    *) echo "hold.sh: bad --tier '$TIER' (want blocker|fps|sweep)" >&2; exit 2 ;;
esac
[ -n "$TIER" ] || TIER=fps
set -- "$op" "$label" "$@"
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
        if [ "$TIER" = sweep ] && blocker=$(sweep_blocker "$label"); then
            echo "hold.sh: refusing sweep take on $label: $blocker is queued or running for it" >&2
            exit 8
        fi
        hold_py take "$label" "$3" "$TIER" "${*:4}" || exit $?
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
    yield-check)
        [ $# -eq 3 ] || usage
        valid tag "$3"
        if blocker=$(yield_signal "$label"); then
            echo "hold.sh: yield: $blocker is queued for $label" >&2
            exit 7
        fi
        exit 0 ;;
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
            if [ "$TIER" = sweep ] && blocker=$(sweep_blocker "$label"); then
                echo "waiting for $label: $blocker (0-/1- tier) is queued or running; a sweep hold will not preempt it" >&2
            else
                hold_py take "$label" "$3" "$TIER" "${*:5}" 2>/dev/null && { notice_idle; exit 0; }
                rc=$?
                [ "$rc" -eq 3 ] || exit "$rc"
            fi
            if [ "$(date +%s)" -ge "$deadline" ]; then
                hold_py who "$label" >&2
                echo "hold.sh: timed out after $4 s waiting for $label" >&2
                exit 3
            fi
            sleep "$HOLD_WAIT_INTERVAL"
        done ;;
    *) usage ;;
esac
