#!/usr/bin/env bash
#
# Take and release a device hold. A hold is removed only by its taker.
#
#   hold.sh take    <label> <tag> <why...>               exit 0 taken, 3 held by someone else
#   hold.sh release <label> <tag>                        exit 0 released, 3 not yours (nothing removed)
#   hold.sh who     <label>                              exit 0 held (prints holder), 1 free
#   hold.sh wait    <label> <tag> <timeout_s> <why...>   take, retrying every 15 s; exit 3 on timeout
#
# <label> is the dispatcher's DEVICE_LABEL (thor, nova, ...). <tag> names the
# taker and is what release checks: use one nobody else would, e.g.
# lane.<name> or hostupd-<pid>. It is [A-Za-z0-9._:-]+.
#
# WHAT A HOLD IS. `$DISPATCH_DIR/hold/<label>` stops the dispatcher CLAIMING
# on that handheld (dispatcher.sh, top of the serve loop). It does not stop a
# request that is already running there, and so a running request
# (running/*.owner naming <label>) does NOT block `take`: the hold takes
# effect when that request ends. If you need the device idle, `take` and then
# wait for running/ to empty of <label> yourself.
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
#
# DISPATCH_DIR resolves as dispatcher.sh and request.sh resolve it.
set -u

D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
HOLD_WAIT_INTERVAL="${HOLD_WAIT_INTERVAL:-15}"

usage() { sed -n '3,19p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

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
        hold_py take "$label" "$3" "${*:4}" ;;
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
            hold_py take "$label" "$3" "${*:5}" 2>/dev/null && exit 0
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
