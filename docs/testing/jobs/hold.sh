#!/usr/bin/env bash
#
# Take and release a device hold. A hold is removed only by its taker.
#
#   hold.sh take    <label> <tag> <why...>               exit 0 taken, 3 held by someone else
#   hold.sh release <label> <tag>                        exit 0 released, 3 not yours (nothing removed)
#   hold.sh who     <label>                              exit 0 held (prints holder), 1 free
#   hold.sh wait    <label> <tag> <timeout_s> <why...>   take, retrying every 15 s; exit 3 on timeout
#   hold.sh wait-idle <label> <timeout_s>                exit 0 idle, 3 still busy at timeout, 1 no hold
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
# DISPATCH_DIR resolves as dispatcher.sh and request.sh resolve it.
set -u

D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
HOLD_WAIT_INTERVAL="${HOLD_WAIT_INTERVAL:-15}"
HOLD_IDLE_INTERVAL="${HOLD_IDLE_INTERVAL:-5}"

usage() { sed -n '3,24p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

valid() { [[ "$2" =~ ^[A-Za-z0-9._:-]+$ ]] || { echo "hold.sh: bad $1 '$2' (want [A-Za-z0-9._:-]+)" >&2; exit 2; }; }

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
        hold_py who "$label" ;;
    take)
        [ $# -ge 4 ] || usage
        valid tag "$3"
        hold_py take "$label" "$3" "${*:4}" || exit $?
        notice_idle ;;
    wait-idle)
        [ $# -eq 3 ] || usage
        [[ "$3" =~ ^[0-9]+$ ]] || { echo "hold.sh: timeout '$3' is not whole seconds" >&2; exit 2; }
        deadline=$(( $(date +%s) + $3 )) said=""
        while :; do
            out=$(hold_py idle "$label")
            rc=$?
            # 0 idle and 1 no hold are answers; anything but 3 is an error.
            [ "$rc" -eq 3 ] || { [ "$rc" -eq 0 ] && echo "$out" || echo "$out" >&2; exit "$rc"; }
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
        hold_py release "$label" "$3" ;;
    wait)
        [ $# -ge 5 ] || usage
        valid tag "$3"
        [[ "$4" =~ ^[0-9]+$ ]] || { echo "hold.sh: timeout '$4' is not whole seconds" >&2; exit 2; }
        deadline=$(( $(date +%s) + $4 ))
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
