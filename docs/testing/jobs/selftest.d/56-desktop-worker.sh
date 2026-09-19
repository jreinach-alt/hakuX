# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, and ok/bad/check. Not executable, no shebang,
# no exit -- `fail` is shared and is the run's verdict.
#
# THE DESKTOP CHANNEL HAS A WORKER, AND THE WORKER IS THE HALF THAT WAS
# MISSING. `55-affinity-offpool.sh` next door proves the SCHEDULER never
# chooses the desktop, and it proves it against three lane files written by
# hand -- because on 2026-09-19 there was no process that would ever write
# `lanes/desktop`. `desktop_channel.sh` had `build` and `run` and nothing
# else, there was no unit, and an explicit `--device desktop` request sat in
# the queue unclaimed forever with nothing anywhere saying so.
#
# So these checks are about the CLAIM side, and every one of them runs against
# the real `desktop_channel.sh serve`:
#
#   A. the worker registers `lanes/desktop` holding its own pid, `serving()`
#      sees it, and it is removed when the worker is stopped;
#   B. with a REAL desktop worker registered -- not a hand-written pid file --
#      rule 3 still sends no unpinned pair there;
#   C. a request pinned with `device: desktop` is claimed by it;
#   D. an UNPINNED request is NOT claimed by it. This is the one thing this
#      worker does differently from every other worker in the fleet and it is
#      worth the most: a handheld's serve_one takes a request when affinity
#      answers its own label OR answers nothing, because "" means "free,
#      anyone may take it". A desktop worker doing the same would run work
#      nobody asked to put on OpenGL/llvmpipe and it would be scored against
#      Adreno-Vulkan goldens -- the failure with no symptom that OFFPOOL
#      exists to prevent, reintroduced one layer below where OFFPOOL can see;
#   E. a HANDHELD worker does not claim a desktop-pinned request -- checked by
#      calling dispatcher.sh's own serve_one, not by restating its rule here.
#
# EVERY ONE OF THESE HAS A MUTANT BELOW, and each mutant is confirmed to
# DIFFER from the real file before it is run: a `sed` whose pattern has
# drifted out of the file produces a byte-identical "mutant", the
# falsification behaves exactly like the real code, and the check it was
# supposed to trip stays green -- which reads as "the invariant is enforced"
# and means "the experiment did not happen".
#
# Mutants live in a SYMLINK TREE ($T/desktopw/mut) with one entry replaced.
# The real docs/testing is never written to and never renamed: swapping a file
# by redirect in the live tree cost a lane its whole session once.

echo "== desktop channel: the worker registers, claims only what is pinned to it, and stays off-pool"
export DW="$T/desktopw"
rm -rf "$DW"; mkdir -p "$DW"/{queue,running,results,lanes,hold,logs,dcroot}
DWCH="$TESTING/desktop_channel.sh"

# A pid that is certainly alive, for the two handheld lanes. serving() tests
# liveness with kill -0 and nothing else, so a fake lane needs a real pid.
sleep 900 & DWLIVE=$!
printf '%s\n' "$DWLIVE" > "$DW/lanes/nova"
printf '%s\n' "$DWLIVE" > "$DW/lanes/thor"

# --------------------------------------------------------------- the fixtures

# A mutant tree: every entry of docs/testing symlinked, one file replaced by a
# sed of itself. Echoes the tree, or NOTHING if the sed changed nothing.
dwmut() {   # <basename> <sed-expression>
    local f="$1" expr="$2" dir="$DW/mut" x
    rm -rf "$dir"; mkdir -p "$dir"
    for x in "$TESTING"/*; do ln -s "$x" "$dir/$(basename "$x")" 2>/dev/null; done
    rm -f "$dir/$f"
    sed "$expr" "$TESTING/$f" > "$dir/$f" || return 1
    chmod +x "$dir/$f"
    cmp -s "$dir/$f" "$TESTING/$f" && return 1
    printf '%s\n' "$dir"
}

# Start a worker and wait for its registration. Echoes the pid. The wait is
# bounded in TENTHS so the negative cases (a mutant that never registers) do
# not spend ten seconds proving it.
dwstart() {   # <dispatch-dir> <script> <log> [tenths]
    DISPATCH_DIR="$1" DC_ROOT="$DW/dcroot" WORK="$DW" DC_POLL=1 \
        bash "$2" serve >"$3" 2>&1 &
    local p=$! n=0
    while [ ! -s "$1/lanes/desktop" ] && [ "$n" -lt "${4:-100}" ]; do
        sleep 0.1; n=$((n + 1))
    done
    printf '%s\n' "$p"
}
dwstop() { kill "$1" 2>/dev/null; wait "$1" 2>/dev/null; }

# One COMPLETE tick: hold check, registration, claim decision, service. What
# is observed here is what the daemon does, not a reduced version of it.
dwtick() {   # <dispatch-dir> <script> <log>
    DISPATCH_DIR="$1" DC_ROOT="$DW/dcroot" WORK="$DW" DC_SERVE_ONCE=1 DC_POLL=0 \
        bash "$2" serve >"$3" 2>&1
}

dwreq() { printf '%s\n' "$3" > "$1/queue/$2.req"; }
# A substring test as a FUNCTION called by `check`, never `bash -c '[[ ]]'`: a
# child shell does not inherit these locals, so a negative written that way is
# green against anything, including the code it is meant to fail on.
dwhas() { case "$2" in *"$1"*) return 0;; *) return 1;; esac; }

# ---------------------------------------------------------------- A. the lane
DWPID="$(dwstart "$DW" "$DWCH" "$DW/daemon.log")"
check "A: the worker registers \$DISPATCH_DIR/lanes/desktop" [ -s "$DW/lanes/desktop" ]
# THE PID, not merely a file. affinity.py's serving() reads this and kill -0's
# it, so a file holding anything else is either invisible (not an int ->
# ValueError -> skipped) or a claim about somebody else's process.
check "A: and it holds the worker's own live pid" \
    [ "$(cat "$DW/lanes/desktop" 2>/dev/null)" = "$DWPID" ]
check "A: affinity --serving now lists all three lanes" \
    [ "$(python3 "$TESTING/affinity.py" "$DW" --serving 2>/dev/null)" = "desktop nova thor" ]
check "A: --serving-pooled still shows only the two the scheduler may choose" \
    [ "$(python3 "$TESTING/affinity.py" "$DW" --serving-pooled 2>/dev/null)" = "nova thor" ]

# ------------------------------------------------- B. still off-pool, LIVE
#
# 55-affinity-offpool.sh asks this of a hand-written pid file. This asks it
# with the real worker running, which is the state that did not exist when
# OFFPOOL was written and the state every future tick is in. Counted over 60
# distinct keys rather than spot-checked: one key that happens to miss the
# desktop says nothing about a modulus.
dwroute() {   # <dispatch-dir> <key>
    printf '{"requester":"r","expect":"/p/%s.json"}\n' "$2" > "$1/q.req"
    python3 "$TESTING/affinity.py" "$1" "$1/q.req" 2>/dev/null
}
dwdesk=0; dwhand=0
for i in $(seq 0 59); do
    case "$(dwroute "$DW" "k$i")" in
        desktop)   dwdesk=$((dwdesk + 1)) ;;
        nova|thor) dwhand=$((dwhand + 1)) ;;
    esac
done
check "B: with the REAL worker serving, rule 3 sends 0 of 60 unpinned pairs to the desktop" \
    [ "$dwdesk" -eq 0 ]
# The instrument has to be able to produce an answer at all, or the line above
# is satisfied by affinity printing nothing 60 times -- which is what an empty
# lanes/, a crashed script and a broken pool all look like.
check "B: and it did route them -- all 60 went to a handheld" [ "$dwhand" -eq 60 ]

# ------------------------------------------------- A (cont). removed on exit
dwstop "$DWPID"
DWN=0
while [ -e "$DW/lanes/desktop" ] && [ "$DWN" -lt 100 ]; do sleep 0.1; DWN=$((DWN + 1)); done
check "A: the registration is removed on SIGTERM, which is how systemd stops it" \
    [ ! -e "$DW/lanes/desktop" ]
check "A: and --serving drops back to the two handhelds" \
    [ "$(python3 "$TESTING/affinity.py" "$DW" --serving 2>/dev/null)" = "nova thor" ]
rm -f "$DW/q.req"

# ------------------------------------------------------------ C and D. claims
#
# THE PINNED REQUEST CARRIES NO only_tests ON PURPOSE. The worker refuses that
# AFTER it has claimed and BEFORE any build, so this exercises the whole claim
# path -- the atomic rename, the owner file, the result directory,
# request.json, DONE -- without configuring qemu or copying a disk image. The
# ERROR text is then the proof that it was THIS worker that answered.
dwreq "$DW" "0-pinned"   '{"requester":"selftest","device":"desktop","purpose":"pinned"}'
dwreq "$DW" "1-unpinned" '{"requester":"selftest","expect":"/p/dwfree.json","purpose":"free"}'
dwtick "$DW" "$DWCH" "$DW/tick-claim.log"
check "C: the desktop-pinned request left the queue" [ ! -e "$DW/queue/0-pinned.req" ]
check "C: it has a finished result directory" [ -f "$DW/results/0-pinned/DONE" ]
check "C: its request.json was filed with the result" [ -f "$DW/results/0-pinned/request.json" ]
check "C: no owner file is left behind in running/" [ ! -e "$DW/running/0-pinned.owner" ]
DWERR="$(cat "$DW/results/0-pinned/ERROR" 2>/dev/null)"
check "C: and the desktop worker is what answered, by its own refusal message" \
    dwhas "only_tests" "$DWERR"
# A SECOND TICK, because the first one broke out of the queue walk the moment
# it served the pinned request and never reached the unpinned one. Asserting
# D off that first tick would be asserting that a request the worker never
# looked at was not claimed.
check "D: the unpinned request survived the first tick" [ -e "$DW/queue/1-unpinned.req" ]
dwtick "$DW" "$DWCH" "$DW/tick-free.log"
check "D: and a tick with ONLY the unpinned request in the queue leaves it there" \
    [ -e "$DW/queue/1-unpinned.req" ]
check "D: nothing was claimed for it" [ ! -d "$DW/results/1-unpinned" ]

# --------------------------------------------- E. a handheld leaves it alone
#
# dispatcher.sh's OWN serve_one, sourced rather than restated. Restating the
# rule here would make this a copy of the thing it is checking, which passes
# whatever the dispatcher actually does. Sourced in a SUBSHELL: that file sets
# HERE, D, SERIAL and a dozen exports at import time and calls device_env, and
# none of it may leak into the rest of this run.
mkdir -p "$DW/hh"/{queue,running,results,lanes,logs}
printf '%s\n' "$DWLIVE" > "$DW/hh/lanes/nova"
printf '%s\n' "$DWLIVE" > "$DW/hh/lanes/desktop"
dwreq "$DW/hh" "0-pinned" '{"requester":"selftest","device":"desktop","purpose":"pinned"}'
(
  export DISPATCH_DIR="$DW/hh" SERIAL=ee317437
  . "$TESTING/dispatcher.sh" >/dev/null 2>&1
  serve_one "$DW/hh/queue/0-pinned.req" >/dev/null 2>&1
); DWHH=$?
check "E: the nova's serve_one declines a desktop-pinned request (non-zero)" [ "$DWHH" -ne 0 ]
check "E: and it did not claim it -- the request is still in the queue" \
    [ -e "$DW/hh/queue/0-pinned.req" ]

# ----------------------------------------------------------------- mutants
#
# Each re-runs a check above against a deliberately broken copy and asserts
# that the check GOES RED. A check that cannot go red is not a check.

# M1 -> check D. The claim rule relaxed to the handheld's: take it if affinity
# names me OR says nothing. The single most valuable invariant here, and the
# easiest to lose to a copy-paste out of dispatcher.sh.
DWM="$(dwmut desktop_channel.sh \
    's|^    \[ "\$want" = "\$DC_DEVICE_LABEL" \]$|    [ -z "$want" ] \|\| [ "$want" = "$DC_DEVICE_LABEL" ]|')"
if [ -z "$DWM" ]; then
    bad "M1: could not build the relaxed-claim mutant (the sed matched nothing)"
else
    rm -rf "$DW/m1"; mkdir -p "$DW/m1"/{queue,running,results,lanes,hold,logs}
    printf '%s\n' "$DWLIVE" > "$DW/m1/lanes/nova"
    dwreq "$DW/m1" "1-unpinned" '{"requester":"selftest","expect":"/p/dwfree.json"}'
    dwtick "$DW/m1" "$DWM/desktop_channel.sh" "$DW/m1.log"
    check "M1 MUTANT: a worker that also takes UNPINNED work claims it, so check D can go red" \
        [ ! -e "$DW/m1/queue/1-unpinned.req" ]
fi

# M2 -> check A. The registration never written.
DWM="$(dwmut desktop_channel.sh 's|^    printf .%s\\n. "\$\$" > "\$f" 2>/dev/null$|    :|')"
if [ -z "$DWM" ]; then
    bad "M2: could not build the no-registration mutant (the sed matched nothing)"
else
    rm -rf "$DW/m2"; mkdir -p "$DW/m2"/{queue,running,results,lanes,hold,logs}
    # Observed WHILE THE WORKER IS ALIVE. After a worker exits the file is
    # gone either way -- the EXIT trap removes it -- so a one-tick run would
    # find it absent for the real code too and this mutant would prove
    # nothing at all.
    DWM2PID="$(dwstart "$DW/m2" "$DWM/desktop_channel.sh" "$DW/m2.log" 30)"
    check "M2 MUTANT: a worker that never writes lanes/desktop leaves it absent while alive, so check A can go red" \
        [ ! -s "$DW/m2/lanes/desktop" ]
    dwstop "$DWM2PID"
fi

# M3 -> the release's pid check. The failure it models is the real one: a
# worker outlives its supervisor, a fresh worker registers under the same
# label, and the old one's EXIT trap then deletes its LIVE SUCCESSOR's file.
# Sourced with `env` (a subcommand with no side effects outside the subshell)
# so dc_lane_release can be called directly against a file holding somebody
# else's pid -- a daemon would overwrite that file at startup via
# dc_lane_claim and the race would decide the answer.
DWM="$(dwmut desktop_channel.sh 's|^    \[ "\$(cat "\$f" 2>/dev/null)" = "\$\$" \] \|\| return 0$|    :|')"
if [ -z "$DWM" ]; then
    bad "M3: could not build the release-by-name mutant (the sed matched nothing)"
else
    rm -rf "$DW/m3" "$DW/m3c"
    mkdir -p "$DW/m3/lanes" "$DW/m3c/lanes"
    printf '%s\n' "$DWLIVE" > "$DW/m3/lanes/desktop"    # somebody ELSE's live pid
    printf '%s\n' "$DWLIVE" > "$DW/m3c/lanes/desktop"
    ( export DISPATCH_DIR="$DW/m3"
      . "$DWM/desktop_channel.sh" env >/dev/null 2>&1; dc_lane_release ) >/dev/null 2>&1
    check "M3 MUTANT: a release that skips the pid check deletes another worker's registration" \
        [ ! -e "$DW/m3/lanes/desktop" ]
    # THE CONTROL, same fixture and the real file. Without it the mutant shows
    # only that something was deleted, not that the PID CHECK is what stops it.
    ( export DISPATCH_DIR="$DW/m3c"
      . "$DWCH" env >/dev/null 2>&1; dc_lane_release ) >/dev/null 2>&1
    check "CONTROL: the real release leaves another worker's registration alone" \
        [ -e "$DW/m3c/lanes/desktop" ]
fi

# M4 -> check B. OFFPOOL emptied: rule 3 starts hashing over three lanes and
# one unpinned pair in three lands on a renderer nobody asked for.
DWM="$(dwmut affinity.py 's|^OFFPOOL = frozenset({"desktop"})$|OFFPOOL = frozenset()|')"
if [ -z "$DWM" ]; then
    bad "M4: could not build the empty-OFFPOOL mutant (the sed matched nothing)"
else
    rm -rf "$DW/m4"; mkdir -p "$DW/m4"/{queue,running,results,lanes}
    printf '%s\n' "$DWLIVE" > "$DW/m4/lanes/nova"
    printf '%s\n' "$DWLIVE" > "$DW/m4/lanes/thor"
    printf '%s\n' "$DWLIVE" > "$DW/m4/lanes/desktop"
    dwmdesk=0
    for i in $(seq 0 59); do
        printf '{"requester":"r","expect":"/p/k%s.json"}\n' "$i" > "$DW/m4/q.req"
        [ "$(python3 "$DWM/affinity.py" "$DW/m4" "$DW/m4/q.req" 2>/dev/null)" = desktop ] \
            && dwmdesk=$((dwmdesk + 1))
    done
    check "M4 MUTANT: with OFFPOOL empty, rule 3 sends unpinned pairs to the desktop, so check B can go red" \
        [ "$dwmdesk" -gt 0 ]
fi

# --------------------------------------------------- the unit, read as a file
#
# NOT cosmetic, and not a grep for its own sake. A systemd user unit does not
# inherit the login PATH; meson lives in ~/.local/bin; and that exact omission
# made every uncached Android build from hakux-dispatcher.service die at CMake
# configure while the same build by hand succeeded. It stayed invisible for as
# long as every requested ref was already cached. This channel configures and
# builds qemu from a daemon, so it is the same trap on a longer fuse.
DWUNIT="$TESTING/systemd/hakux-desktop.service"
check "unit: docs/testing/systemd/hakux-desktop.service exists" [ -f "$DWUNIT" ]
check "unit: it carries an explicit Environment=PATH" \
    grep -q '^Environment=PATH=' "$DWUNIT"
check "unit: and that PATH includes /home/justin/.local/bin, where meson lives" \
    grep -q '^Environment=PATH=.*/home/justin/\.local/bin' "$DWUNIT"
check "unit: it starts the serve subcommand, not build or run" \
    grep -q '^ExecStart=.*desktop_channel\.sh serve$' "$DWUNIT"
# A UNIT THAT IS INSTALLED AND NEVER STARTED IS THE SAME KIND OF INVISIBLE AS
# NO UNIT AT ALL, which is what this whole lane is about. install-host.sh
# copies systemd/*.service in a loop and then enables a NAMED list.
check "unit: install-host.sh enables it, not merely copies it" \
    grep -q 'enable --now .*hakux-desktop\.service' "$HERE/install-host.sh"

kill "$DWLIVE" 2>/dev/null; wait "$DWLIVE" 2>/dev/null
rm -rf "$DW/mut"
unset DW DWCH DWLIVE DWPID DWN DWM DWM2PID DWERR DWHH DWUNIT
unset dwdesk dwhand dwmdesk
unset -f dwmut dwstart dwstop dwtick dwreq dwhas dwroute
