#!/usr/bin/env bash
#
# The device dispatcher. Owns the Nova; nothing else touches it.
#
#   dispatcher.sh serve     service the queue until stopped
#   dispatcher.sh status    queue depth, what is running, recent results
#
# Agents do not run tests. They write a request with request.sh and wait for a
# result. This exists for three reasons, in order of value:
#
#   1. Batching. The overnight sweep only became viable by pulling the 1.5GB
#      disk image once per hundred tests instead of once per test -- three
#      hours against a day and a half. One requester cannot see that; a queue
#      can coalesce.
#   2. Comparability. Every result records the binary, the disc composition and
#      the classifier revision, so two results can be *checked* for
#      comparability rather than assumed. Comparing a shared-disc number with a
#      per-suite one caused a working fix to be reverted on 2026-09-12.
#   3. The lease. Held continuously while a run is in flight, so the Stop hook
#      cannot kill it -- that has destroyed three sessions.
#
# Request format, one JSON object per file in queue/:
#   {"id","requester","purpose","ref","suites":["Specular"],"arm":"company|solo",
#    "tests":[...]                      NOT IMPLEMENTED -- never read; request.sh refuses it
#    "skip_tests":["Suite::Test"]       optional, drop one test from the disc
#    "runs":1}                          >1 for no-oracle measurements
#
# skip_tests exists because a test can poison the tests that run after it.
# "Texture render target::RenderTextureLoop" disables the texture stage on its
# way out and the other 40 tests never set it up, so a disc that cannot drop it
# measures that suite at 3,209,634 px where the same build on a no-loop disc
# measures 324,349. It is part of the disc identity below: a loop-included and
# a loop-skipped result are not comparable and must not share a disc_id.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="${DISPATCH_TREE:-/home/justin/hakuX}"
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
# Which handheld this instance drives. Two dispatchers can share one queue:
# claiming a request is `mv queue/x running/x`, an atomic rename that either
# wins or returns non-zero, so whichever renames first owns it. Everything
# else that is per-device -- the lease, the SD card path, the orphan sweep --
# has to be keyed on the device, which is what devices.sh is for.
. "$HERE/devices.sh"
device_env "${SERIAL:-ee317437}" || exit 2
GOLDENS="${GOLDENS:-/home/justin/goldens/results}"
SWEEP_STATE="${SWEEP_STATE:-/home/justin/hakux-work/night19/sq_g0}"
LEASE="${HAKUX_DEVICE_LEASE:-/tmp/hakux-device-lease}"
export JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}"
export PATH="/home/justin/Android/Sdk/cmake/3.30.3/bin:$PATH"

mkdir -p "$D"/{queue,running,results,logs}

# Where the workers actually run from. Copied out of the tree so that a
# detached checkout during a build cannot change the code a worker re-execs
# into. Refreshed deliberately, at the moment a worker chooses to pick changes
# up, rather than continuously.
SNAP="$D/bin"
# The scripts a snapshot is taken FROM. This has to be the working tree and
# not $HERE: a worker runs from the snapshot, so $HERE *is* $SNAP there, and
# both halves of the pick-up-changes mechanism then read the copy instead of
# the original. snapshot_scripts became SNAP -> SNAP, the re-exec hash was the
# hash of the code already running, and a worker could no longer see an edit
# to the tree at all -- which is the very failure the re-exec exists to
# prevent, reintroduced by the fix for the one after it.
SRC="${DISPATCH_SRC:-$TREE/docs/testing}"
SCRIPT_DEPS="dispatcher.sh soak_title.sh run_disc.sh score_sweep.py"
# WHERE BUILDS HAPPEN, AND IT IS NEVER $TREE.
#
# Until 2026-09-19 a build detached the SHARED checkout onto the requested
# sha, so any tracked modification anywhere in it -- a lane's edit, a fold in
# progress, a checker's stamp file -- stalled every uncached build with a
# 30-second requeue loop: 251 requeues in one day, 129 from one stamp file,
# two fleet-wide stalls in an hour on 09-14. The refusal was correct and the
# recovery worked, and both were symptoms of building in a tree that other
# actors edit.
#
# So builds happen in a PRIVATE worktree that nothing else ever touches. It
# hangs off $REPO's object store (a worktree shares objects, so nothing is
# cloned), it is detached to the requested sha for the length of the build,
# and it keeps its gradle and cmake outputs between builds so the incremental
# case stays warm. Nobody edits it, so it is never dirty, so there is nothing
# to refuse. The dirty-tree path and dirty_wait_log are gone, not improved.
#
# $TREE is still the source the script SNAPSHOT is taken from (above), and
# the place a ref is first resolved. It is never checked out or detached.
REPO="${DISPATCH_REPO:-$TREE}"
BUILD_TREE="${DISPATCH_BUILD_TREE:-$D/build-tree}"
snapshot_scripts() {
    mkdir -p "$SNAP"
    for f in dispatcher.sh devices.sh soak_title.sh run_disc.sh score_sweep.py \
             affinity.py captures.py make_test_iso.py extract_results.py; do
        [ -f "$SRC/$f" ] && cp -f "$SRC/$f" "$SNAP/$f" 2>/dev/null
    done
}
# Hash of the scripts as they are IN THE TREE. This used to return empty
# while $TREE was detached for a build, because mid-build the tree held some
# other commit's scripts. Builds no longer touch $TREE (see BUILD_TREE), so
# the tree's scripts are always the tree's scripts and the hash is honest.
src_hash() {
    ( cd "$SRC" && cat $SCRIPT_DEPS 2>/dev/null | md5sum | cut -c1-12 )
}
# Logs go to the file and to STDERR, never stdout. build_ref's stdout is
# captured as the APK path, so a log line on stdout becomes the path: adding
# one informational message to the success path made every build return the
# log text instead of a file, and the run failed at install with an empty
# binary. Anything that writes to stdout inside a $(...) here is a bug.
log() { echo "$(date '+%m-%d %H:%M:%S') $*" | tee -a "$D/logs/dispatcher.log" >&2; }
jq_get() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],sys.argv[3] if len(sys.argv)>3 else ''))" "$1" "$2" "${3:-}"; }

device_present() {
    adb devices | tr -d '\r' | grep -q "^$SERIAL[[:space:]]*device$"
}

# Put the request's `env` into the app's environment for THIS RUN, and take it
# out again afterwards.
#
# WHY THIS EXISTS. The emulator reads its environment from the `env_vars` pref
# in x1box_prefs.xml (xemu_android.cpp:796), which splits on newlines and
# setenv()s each KEY=VALUE. Nothing in the dispatch path wrote that pref: the
# only script that wrote any pref was driver_ab.sh, by hand, for the driver
# override. So a runtime-selectable option was selectable by a person holding
# the device and NOT by a queued request, and lane.skew44 paid for that in
# builds -- three refs, each a child of the tip differing by one line of
# pfifo.c, to reach HAKUX_FIFO_SKEW_BOUND 0/1/2. One binary and three requests
# is the same experiment for a third of the device time and none of the
# rebasing.
#
# THE DANGEROUS HALF IS THE CLEANUP, NOT THE WRITE. A pref persists across
# runs, across installs and across reboots. An env left behind by request N
# silently joins request N+1, and on an A/B that is the purest available form
# of the failure this whole queue exists to prevent: arm B inherits arm A's
# independent variable, both arms report numbers, and nothing anywhere says
# they were not the same experiment. It has the exact shape of the stale APU
# capture marker that armed seven Galleon soaks nobody asked for.
#
# So the rule is: WE CLEAN UP AFTER OURSELVES, AND ONLY AFTER OURSELVES.
#
#   * request HAS env -> write it, verify it read back, record it. A failure
#     here fails the REQUEST. Running with the wrong environment would produce
#     a full set of plausible numbers measuring the wrong thing, and an
#     obvious failure beats a beautiful measurement of nothing.
#   * request has NO env, and a marker says WE set one last time -> clear it.
#   * request has NO env, and no marker -> TOUCH NOTHING. Not one adb call.
#     This is the overwhelmingly common case, so the cost of this feature on
#     every other request in the queue is a single json read on the host.
#
# The marker is why we do not simply clear the pref before every run. A human
# sets env_vars through the Settings screen, and a dispatcher that blanked it
# on every request would delete their setting with no trace and no warning --
# a gate firing on correct work. We only ever remove a value we put there.
#
# The device write is the driver_ab.sh shape, for the same reason it uses it:
# x1box_prefs.xml also holds the MCPX, flash and HDD paths and setup_complete,
# and an earlier version of that script cleared a key with `rm` and dropped the
# app into its setup wizard. Edit the one key; keep the rest byte for byte.
# A SOAK KEEPS NO FRAMES, AND THAT IS WHERE ITS EVIDENCE GOES TO DIE.
#
# A disc run pulls its captures into the result dir. A soak result carries
# `pulled: []` and a logcat, and nothing else. For #77's driver A/B the entire
# evidential basis -- 434 frames across four arms -- existed only in a lane's
# scratchpad, one reap from gone, with the result dir beside it recording that
# the run had produced nothing.
#
# There is no app-side frame dump to ask for: #77 records that
# nv2a_dbg_trigger_diag_frames is reachable only from the Debug Capture button
# and LauncherActivity reads only rom_path. What a lane actually did is
# `adb exec-out screencap`, so that is what this does, in the dispatcher rather
# than in a scratchpad.
#
# OPT-IN, AND IT HAS TO BE, for two reasons that are not disk space:
#
#   * IT PERTURBS THE THING BEING MEASURED. A screencap every second on a
#     handheld costs GPU and CPU, and soaks are how this campaign prices frame
#     rate -- gfps p90 is read off exactly these runs. A cost leg from a
#     frame-capturing soak is NOT comparable with one from a clean soak, so
#     `frames.every` goes into result.json and a reader who pools the two
#     across it is doing so with the fact in front of them.
#   * The images are ~1-2 MB each on a 1920x1080 panel. The hdd.img story in
#     run_disc.sh is the standing lesson here: a dynamically expanding WSL
#     VHDX never returns deleted blocks to the host, and 12 GB in an afternoon
#     killed the VM. So there is a hard cap as well as an interval.
#
# Killed BY PID. A pattern kill here would match this script's own command
# line -- the same trap run_disc.sh's logcat reader documents.
FRAME_PID=""
start_frame_capture() {   # <rdir> <interval-seconds> <hold-seconds>
    local rdir="$1" every="$2" hold="$3" cap
    FRAME_PID=""
    [ "${every:-0}" -gt 0 ] 2>/dev/null || return 0
    mkdir -p "$rdir/frames"
    # The cap is whichever is smaller: what the interval implies over the hold,
    # or HAKUX_SOAK_FRAME_CAP. A request that asks for a frame every second
    # over an hour asks for ~3.6 GB, and the honest response is to give it what
    # it can have and SAY the cap was hit rather than to fill the disk or to
    # silently widen the interval.
    cap=$(( hold / every + 2 ))
    [ "$cap" -gt "${HAKUX_SOAK_FRAME_CAP:-600}" ] && cap="${HAKUX_SOAK_FRAME_CAP:-600}"
    log "  frames: every ${every}s, cap $cap, -> $rdir/frames"
    (
        n=0
        while [ "$n" -lt "$cap" ]; do
            n=$((n+1))
            # exec-out, not `shell`, so the PNG is not mangled by the tty line
            # discipline -- `adb shell screencap -p` corrupts every 0x0a on
            # some transports and the file opens as a truncated image.
            timeout 30 adb -s "$SERIAL" exec-out screencap -p \
                > "$rdir/frames/$(printf 'f%05d' "$n").png" 2>/dev/null
            # An empty or tiny file is a failed capture, not a black frame.
            # Delete it: a 0-byte PNG in a frame set is an image tool's crash
            # later on, and a count that includes it is a lie about coverage.
            [ -s "$rdir/frames/$(printf 'f%05d' "$n").png" ] \
                || rm -f "$rdir/frames/$(printf 'f%05d' "$n").png"
            sleep "$every"
        done
    ) &
    FRAME_PID=$!
}
stop_frame_capture() {
    [ -n "$FRAME_PID" ] || return 0
    kill "$FRAME_PID" 2>/dev/null
    wait "$FRAME_PID" 2>/dev/null
    FRAME_PID=""
}

env_pref_marker() { echo "$D/.env_pref.${DEVICE_LABEL:-$SERIAL}"; }

# apply_env_pref <request.json> ; echoes the newline-joined env it installed
apply_env_pref() {
    local req="$1" marker want tmp pkg
    pkg="${PKG:-com.jreinach.hakux.debug}"
    marker="$(env_pref_marker)"
    want=$(python3 - "$req" <<'PYENV'
import json, sys
r = json.load(open(sys.argv[1]))
v = r.get("env") or []
# A dict is accepted on the way IN because a request could be hand-written,
# but it is never produced by request.sh -- see the note on the list form there.
if isinstance(v, dict):
    v = ["%s=%s" % (k, x) for k, x in v.items()]
print("\n".join(str(x) for x in v))
PYENV
)
    if [ -z "$want" ] && [ ! -f "$marker" ]; then
        return 0                    # nothing asked for, nothing of ours to undo
    fi
    # The app must not be running while we write: SharedPreferences are cached
    # in the process and flushed on commit, so a live process would overwrite
    # this the moment anything else touched a pref.
    adb -s "$SERIAL" shell am force-stop "$pkg" >/dev/null 2>&1
    tmp="$D/.prefs.${DEVICE_LABEL:-$SERIAL}.xml"
    adb -s "$SERIAL" shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" \
        2>/dev/null | tr -d '\r' > "$tmp"
    if [ ! -s "$tmp" ]; then
        if [ -z "$want" ]; then
            # Clearing, and we cannot read the file. Drop the marker: another
            # run of this would loop forever trying to undo something it
            # cannot see. Say so rather than failing a request that asked for
            # nothing.
            rm -f "$marker"
            log "  WARNING: cannot read x1box_prefs.xml to clear a previous env; marker dropped"
            return 0
        fi
        log "  ENV: cannot read x1box_prefs.xml (run-as failed?); refusing to guess"
        return 1
    fi
    python3 - "$tmp" "$want" <<'PYENV' || return 1
import re, sys
path, want = sys.argv[1], sys.argv[2]
s = open(path).read()
if "</map>" not in s:
    sys.exit("prefs file has no </map>; refusing to write")
# Remove the existing key wherever it is, then re-add if wanted. Exactly the
# _set_driver_pref.py shape, and for the same reason: every other key in this
# file has to survive byte for byte.
s = re.sub(r'\n?[ \t]*<string name="env_vars">.*?</string>', "", s, flags=re.S)
if want:
    esc = (want.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
               .replace("\n", "&#10;"))
    s = s.replace("</map>", '    <string name="env_vars">%s</string>\n</map>' % esc)
open(path, "w").write(s)
PYENV
    adb -s "$SERIAL" shell "run-as $pkg sh -c 'cat > shared_prefs/x1box_prefs.xml'" < "$tmp"
    # VERIFY BY READING BACK. A `cat >` over adb can truncate, and the failure
    # mode of a silently-unwritten pref is a run that measures the other arm.
    # Via a FILE and a quoted heredoc, not `python3 -c "..."`. The source below
    # is full of quotes, backslashes and an `&`, and a shell string is the
    # wrong container for any of them -- the same mistake that was running the
    # shell over the disc_id block's comments a few hundred lines down.
    adb -s "$SERIAL" shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" \
        2>/dev/null | tr -d '\r' > "$tmp.back"
    local back
    back=$(python3 - "$tmp.back" <<'PYENV'
import re, sys
m = re.search(r'<string name="env_vars">(.*?)</string>',
              open(sys.argv[1], errors="replace").read(), re.S)
v = m.group(1) if m else ""
# Unescape in the reverse of the order they were applied, or "&amp;#10;" --
# a literal ampersand followed by that text in somebody's value -- would come
# back as a newline.
v = v.replace("&#10;", "\n").replace("&gt;", ">").replace("&lt;", "<")
v = v.replace("&amp;", "&")
sys.stdout.write(v)
PYENV
)
    if [ "$back" != "$want" ]; then
        log "  ENV: wrote env_vars but read back something else; refusing this request"
        log "      wanted: $(printf '%s' "$want" | tr '\n' ' ')"
        log "      got:    $(printf '%s' "$back" | tr '\n' ' ')"
        return 1
    fi
    if [ -n "$want" ]; then
        printf '%s\n' "$want" > "$marker"
        log "  ENV: $(printf '%s' "$want" | tr '\n' ' ')"
    else
        rm -f "$marker"
        log "  ENV: cleared the previous request's env_vars"
    fi
    return 0
}

# The full sweep is idle-priority work and yields to requests. pause blocks
# until the runner has genuinely parked rather than setting a flag and hoping,
# and every resume reinstalls the baseline so a preempting binary cannot
# contaminate the rows that follow.
sweep_running() { [ -f "$SWEEP_STATE/pid" ] && kill -0 "$(cat "$SWEEP_STATE/pid")" 2>/dev/null; }
preempt_sweep() {
    sweep_running || return 0
    log "preempting the sweep"
    SWEEP_STATE="$SWEEP_STATE" bash "$HERE/sweep_queue.sh" pause >>"$D/logs/dispatcher.log" 2>&1
}
resume_sweep() {
    [ -f "$SWEEP_STATE/PAUSE" ] || return 0
    [ -n "$(ls -A "$D/queue" 2>/dev/null)" ] && return 0   # more work first
    log "queue empty, resuming the sweep"
    SWEEP_STATE="$SWEEP_STATE" bash "$HERE/sweep_queue.sh" resume >>"$D/logs/dispatcher.log" 2>&1
}

# The private build worktree, created on first use. --detach so it never
# holds a branch, which keeps `git worktree list` honest about what it is.
ensure_build_tree() {
    if [ -e "$BUILD_TREE/.git" ]; then return 0; fi
    mkdir -p "$(dirname "$BUILD_TREE")"
    git -C "$REPO" worktree add --quiet --detach "$BUILD_TREE" HEAD || {
        log "  could not create the build worktree at $BUILD_TREE from $REPO"; return 1; }
    log "  created the private build worktree at $BUILD_TREE"
}

build_ref() {  # $1 = ref ; $2 = "perflog" for a diagnostic build ; echoes the apk path
    # Serialised across devices, because there is ONE private build tree and
    # gradle's outputs live in it. Two workers here at once would each detach
    # it to a different sha and both would build whatever the other left
    # behind -- silently, since each would still produce an APK and call it
    # by its own sha. The APK cache below makes the common case free, so the
    # lock costs nothing when both devices want the same binary, which is
    # most of the time: the two arms of an A/B share one of their two refs
    # with whatever ran before them.
    local lock="$D/.build.lock"
    exec 9>"$lock"
    flock 9
    _build_ref_locked "$@"
    local rc=$?
    exec 9>&-
    return $rc
}

_build_ref_locked() {
    local ref="$1" variant="${2:-}" out="$D/builds"
    mkdir -p "$out"
    # A ref a cloud lane pushed may not be known locally yet; one fetch
    # before giving up. Resolved in $REPO, never in the build tree, so a
    # half-finished build cannot change what a name means.
    local sha
    sha=$(git -C "$REPO" rev-parse --short "$ref" 2>/dev/null) || {
        git -C "$REPO" fetch -q origin 2>/dev/null
        sha=$(git -C "$REPO" rev-parse --short "$ref" 2>/dev/null) || return 1
    }
    # THE CACHE KEY MUST CARRY THE VARIANT, and this is the whole reason the
    # perflog build needed a change here rather than an env var.
    #
    # The cache is what makes an A/B cheap: both arms usually share a ref with
    # something built before them. Keyed on the sha ALONE, a `-Pperflog=true`
    # build of a sha already built normally would be served the normal APK --
    # which emits no `hakuX-phase` lines at all, so the measurement comes back
    # EMPTY and reads exactly like a soak that produced nothing. And the
    # reverse is worse: a normal arm served a perflog APK is measured with the
    # extra instrumentation's cost folded into its frame rate, silently, with
    # its apk_sha agreeing with every other row.
    #
    # So the variant is part of the identity of the BINARY, not a flag on the
    # run. Downstream needs no change for this: `apk_sha` is a sha256 of the
    # APK file itself (see below), not of the ref, so the two variants of one
    # sha already carry different apk_shas and a column cannot mix them
    # unnoticed. That was luck rather than foresight, and it is worth knowing
    # which -- had apk_sha been derived from the ref, this cache-key fix alone
    # would have left the two builds indistinguishable in every result.
    local suffix="" gradle_args=""
    if [ "$variant" = "perflog" ]; then
        suffix="-perflog"
        gradle_args="-Pperflog=true"
    fi
    local apk="$out/$sha$suffix.apk"
    if [ -f "$apk" ]; then echo "$apk"; return 0; fi
    ensure_build_tree || return 2
    # Detach the PRIVATE tree, never $TREE. It is nobody's working copy, so
    # it is never dirty and nothing is disturbed. Any sha $REPO knows resolves
    # here, because a worktree shares the object store.
    git -C "$BUILD_TREE" checkout --quiet --detach "$sha" || {
        log "  checkout of $sha in $BUILD_TREE failed; not building"; return 2; }
    # local.properties is gitignored and required: without it meson fails with
    # "Could not detect Ninja", which reads as a code defect and is not
    # (AGENTS.md, "Working against a device"). Seed it from the owner's tree.
    if [ ! -f "$BUILD_TREE/android/local.properties" ] \
       && [ -f "$TREE/android/local.properties" ]; then
        cp "$TREE/android/local.properties" "$BUILD_TREE/android/local.properties"
    fi
    BUILD_LOG="$D/logs/build-$sha$suffix.log"   # not local: serve_one reads it for the cause
    # A MISSING BUILD TOOL IS THE ONE FAILURE THAT LOOKS LIKE A CODE DEFECT AND
    # IS NOT. meson lives in ~/.local/bin on this host, and a systemd user unit
    # does not inherit the login shell's PATH -- so every uncached build from
    # this daemon died at CMake configure with "meson not found in PATH;
    # required to build glib for Android", while the same build by hand
    # succeeded. It stayed invisible for as long as every requested ref was
    # already in the APK cache; the first uncached one was #89's arm, and both
    # sides of the pair failed identically, which reads like the branch.
    #
    # Two seconds here against 1m54s and a 1,200-line Gradle stack trace whose
    # one useful line is 80 lines in.
    local missing="" tool
    for tool in meson; do
        command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
    done
    if [ -n "$missing" ]; then
        { echo "build tool not on PATH:$missing"
          echo "PATH=$PATH"
          echo "This is the daemon's environment, not the code: a systemd user unit"
          echo "does not inherit the login shell's PATH. See the Environment=PATH line"
          echo "in docs/testing/systemd/hakux-dispatcher.service, and re-install the"
          echo "units with docs/testing/jobs/install-host.sh."
        } > "$BUILD_LOG"
        log "  BUILD TOOL MISSING:$missing -- not starting gradle"
        return 4
    fi
    (cd "$BUILD_TREE/android" && ./gradlew assembleDebug ${gradle_args:+$gradle_args}) \
        >>"$BUILD_LOG" 2>&1
    local rc=$?
    [ "$rc" -eq 0 ] || return 4
    cp "$BUILD_TREE/android/app/build/outputs/apk/debug/app-debug.apk" "$apk"
    echo "$apk"
}

# ------------------------------------------------------------ the lane file
#
# `lanes/<label>` holds a live worker's pid and is the ONLY input to
# affinity.py's serving(). Everything below exists because that file used to be
# written exactly twice in a worker's whole life -- once at startup, once on a
# hold release -- so ANY removal, by any actor, was PERMANENT until the
# dispatcher was restarted.
#
# It cost a measurement on 2026-09-19. Something emptied $D/lanes/ ten minutes
# after both workers started; serving() returned [] for the next five hours;
# rule 2's _live() was therefore false for a device that was in fact serving
# and rule 3 had no devices to hash over; #89's pair ran base on the thor and
# fix on the nova. affinity.py was not wrong, it was inert.
#
# WHAT REMOVED THEM IS STILL UNRESOLVED, and this deliberately does not chase
# it. The hold path is the obvious suspect and it is refuted by reading --
# held_logged is assigned on the same line-run as its `rm`, so a worker that
# starts under a hold does set it and does restore the file. (Also checked and
# killed: EXIT-trap leakage into `$(...)`, which bash does not do, and a third
# remover elsewhere in the tree, of which there is none.) The full forensics
# are in NOTES.md on lane/armpin; do not re-derive them.
#
# The whodunnit is not what made it expensive. PERMANENCE is. So:
#
#   lane_claim    re-asserts the registration every tick, so a removal by
#                 anyone costs one tick instead of one restart;
#   lane_release  removes the file only if it still holds MY pid.
#
# The second is not hypothetical tidiness. Workers are `&` children of the
# supervisor, so a supervisor killed with SIGKILL leaves them running; the next
# supervisor starts fresh workers under the same labels, which register
# themselves; and when an old worker finally exits, its EXIT trap removes the
# file its live successor owns. A trap that removes by NAME cannot tell those
# two cases apart, and the survivor never writes the file again. That is the
# one mechanism that fits every observation -- files present at start, gone ten
# minutes later, never restored, and correct again after a restart -- and this
# closes it without having to prove it was the one.
lane_file() { echo "$D/lanes/$DEVICE_LABEL"; }

lane_claim() {
    local f; f="$(lane_file)"
    # Cheap enough to call every tick: one read, and a write only when the
    # registration is missing or is somebody else's.
    [ "$(cat "$f" 2>/dev/null)" = "$$" ] && return 0
    mkdir -p "$D/lanes" 2>/dev/null
    printf '%s\n' "$$" > "$f" 2>/dev/null
}

lane_release() {
    local f; f="$(lane_file)"
    [ "$(cat "$f" 2>/dev/null)" = "$$" ] || return 0
    rm -f "$f"
}

# AN EMPTY serving() DEMOTES "PAIRS ARE PINNED" TO "PAIRS ARE RANDOM", AND DID
# IT SILENTLY. affinity.py fails open on purpose and that is the right call: a
# pin to a device that is not serving is a request nobody ever claims, and a
# silent stall costs more than a split pair. What it must not do is fail open
# with NO SIGN, which is how #89's arms ran on two handhelds for five hours
# with every actor behaving exactly as documented.
#
# Announced on the TRANSITION, not per claim. The corpus sweep enqueues one
# request per suite, and a line each would bury the log this exists to make
# readable. `blind_logged` is deliberately not `local`: it is the worker's
# state across claims, and the whole point is to say it once.
lane_blind_check() {
    local id="$1" live
    live=$(python3 "$HERE/affinity.py" "$D" --serving 2>/dev/null)
    if [ -z "$live" ]; then
        [ "${blind_logged:-0}" = 1 ] || \
            log "AFFINITY BLIND: no device lane is registered in $D/lanes, so nothing can be pinned; claiming $id unpinned -- an A/B queued now can split across handhelds"
        blind_logged=1
    elif [ "${blind_logged:-0}" = 1 ]; then
        log "affinity: lanes registered again ($live); pairs are pinned"
        blind_logged=0
    fi
}

serve_one() {
    local req="$1" id
    id=$(basename "$req" .req)
    # Affinity before claiming. The two arms of an A/B share a prediction
    # file, and running one on each handheld would change the binary AND the
    # hardware while presenting the result as a one-commit delta. affinity.py
    # pins a request to whichever device already ran its sibling.
    local want
    want=$(python3 "$HERE/affinity.py" "$D" "$req" 2>/dev/null)
    if [ -n "$want" ] && [ "$want" != "$DEVICE_LABEL" ]; then
        # Not ours. Non-zero so the caller tries the next request instead of
        # concluding it served something and sleeping.
        return 1
    fi
    # Losing this rename means the other worker claimed it first, which is the
    # mutex working. Also non-zero: try the next one.
    mv "$req" "$D/running/$id.req" 2>/dev/null || return 1
    printf '%s\n' "$DEVICE_LABEL" > "$D/running/$id.owner"
    req="$D/running/$id.req"
    # Say so if that `want` above was decided over an empty device set.
    lane_blind_check "$id"
    local requester purpose ref arm runs
    requester=$(jq_get "$req" requester unknown)
    purpose=$(jq_get "$req" purpose "")
    ref=$(jq_get "$req" ref HEAD)
    arm=$(jq_get "$req" arm company)
    runs=$(jq_get "$req" runs 1)
    local title seconds pull_glob audio_capture frames_every
    title=$(jq_get "$req" title "")
    seconds=$(jq_get "$req" seconds 60)
    pull_glob=$(jq_get "$req" pull_glob "")
    # Screen frames during a soak, off unless the request asks. See
    # start_frame_capture.
    frames_every=$(jq_get "$req" frames_every 0)
    # Arming the APU PCM capture is per REQUEST, not device state left lying
    # around. See arm_audio in soak_title.sh for the two ways the persistent
    # marker went wrong on 2026-09-12 -- in both directions, on the same day.
    audio_capture=$(jq_get "$req" audio_capture "")
    log "request $id from $requester: $purpose (ref=$ref arm=$arm runs=$runs)"

    local rdir="$D/results/$id"; mkdir -p "$rdir"
    local apk rc
    # `a || b && c || d` is a precedence trap in shell and this value decides
    # which binary runs, so spell it out.
    local perflog_req perflog=""
    perflog_req=$(jq_get "$req" perflog "")
    case "$perflog_req" in
        true|True|1|yes) perflog=perflog ;;
    esac
    [ -z "$perflog" ] || log "  diagnostic build requested: -Pperflog=true"
    apk=$(build_ref "$ref" "$perflog"); rc=$?
    if [ "$rc" != 0 ]; then
        # The arms job puts the first lines of this file on the lane's PR as
        # "[job.arms] ARM ERROR", and "code 4" tells a lane nothing it can act
        # on. The first line that names a cause in a Gradle log is typically 80
        # lines in and everything after it is a stack trace, so pull the lines
        # that name one rather than the head or the tail.
        { echo "build failed for ref $ref (code $rc)"
          grep -m3 -hE "CMake Error|not on PATH|not found in PATH|error:|FAILED: |What went wrong" \
               "${BUILD_LOG:-/dev/null}" 2>/dev/null | cut -c1-200 | sed 's/^/  /'
          echo "  full log: ${BUILD_LOG:-none}"
        } > "$rdir/ERROR"
        log "  BUILD FAILED (code $rc)"; mv "$req" "$rdir/request.json"; return 0
    fi
    if [ ! -f "$apk" ]; then
        echo "build_ref returned no usable apk: '$apk'" > "$rdir/ERROR"
        log "  BUILD RETURNED NO APK"; mv "$req" "$rdir/request.json"; return 0
    fi
    local sha; sha=$(sha256sum "$apk" | cut -c1-12)
    log "  binary $sha"

    if ! device_present; then
        log "  device absent; requeueing"
        mv "$req" "$D/queue/$id.req"; sleep 30; return 0
    fi
    preempt_sweep
    adb -s "$SERIAL" install -r "$apk" 2>&1 | grep -q Success || {
        echo "install failed" > "$rdir/ERROR"; log "  INSTALL FAILED"
        mv "$req" "$rdir/request.json"; return 0
    }

    # AFTER the install and BEFORE either run path, because both of them start
    # the app and neither may start it with the previous request's environment
    # still in the pref. See apply_env_pref: on a request with no `env` and no
    # marker this costs zero adb calls.
    local req_env=""
    if ! apply_env_pref "$req"; then
        echo "could not set the requested env_vars pref; see dispatcher.log" > "$rdir/ERROR"
        log "  ENV SETUP FAILED"
        mv "$req" "$rdir/request.json"; return 0
    fi
    req_env=$(python3 -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1])).get('env') or []))" "$req" 2>/dev/null || echo "[]")

    # A soak request runs a real title and keeps its log, instead of running a
    # test disc and scoring captures. It exists because some questions have no
    # golden framebuffer: the audio path is silent on the pgraph discs, so
    # "does any title actually program submix_headroom" can only be answered by
    # booting a game and reading the log. Same queue, same lease, same
    # preempt/resume, so it is scheduled against test work rather than racing
    # it -- and no human has to hold the handheld.
    if [ -n "$title" ]; then
        log "  soak: $title for ${seconds}s"
        local tpath="$DEVICE_ISO_ROOT/$title"
        if ! adb -s "$SERIAL" shell "[ -f '$tpath' ] && echo yes" 2>/dev/null | tr -d '\r' | grep -q yes; then
            echo "title not on device: $tpath" > "$rdir/ERROR"
            log "  TITLE NOT FOUND"; mv "$req" "$rdir/request.json"; return 0
        fi
        touch "$LEASE"
        start_frame_capture "$rdir" "$frames_every" "$seconds"
        SERIAL="$SERIAL" CAPTURE_LOG="$rdir/logcat.txt" \
            PULL_GLOB="$pull_glob" PULL_DEST="$rdir/pulled" \
            AUDIO_CAPTURE_MB="$audio_capture" \
            bash "$HERE/soak_title.sh" "$tpath" "$seconds" >>"$rdir/run.log" 2>&1
        # Before the result is written, so the count in result.json is final,
        # and unconditionally, so an early guest exit does not leave a
        # screencap loop running against the next request's title.
        stop_frame_capture
        local lines; lines=$(wc -l < "$rdir/logcat.txt" 2>/dev/null || echo 0)
        python3 - "$rdir" "$sha" "$title" "$seconds" "$requester" "$purpose" "$ref" "$lines" "$req_env" "$frames_every" <<'PYEOF'
import json, os, sys
(rdir, sha, title, seconds, who, purpose, ref, lines, req_env,
 frames_every) = sys.argv[1:11]
_fdir = os.path.join(rdir, "frames")
_frames = sorted(f for f in os.listdir(_fdir)) if os.path.isdir(_fdir) else []
pulled = []
pdir = os.path.join(rdir, "pulled")
if os.path.isdir(pdir):
    for f in sorted(os.listdir(pdir)):
        pulled.append(dict(file=f, bytes=os.path.getsize(os.path.join(pdir, f))))
# Which handheld produced this, on the soak path too. Only the disc path
# recorded it, and the omission is worse here than there: a soak has no
# golden to disagree with, so an audio level or a frame rate from the wrong
# device is not merely unlabelled, it is indistinguishable from the right
# one. Three audio titles live on the Thor and Galleon on the Nova, and the
# volume comparisons across them are exactly the measurement this silently
# mixes. devices.sh exists to stop that; it cannot stop what is never written.
# THE EFFECTIVE SPEC, on the soak path too. Only the disc path recorded it, and
# the omission is worse here for the same reason the device label was: a soak
# has no golden to disagree with, so from a soak result alone "the filter
# dropped the tag" and "the code does not log it" are INDISTINGUISHABLE. That
# cost a phase survey exactly this way. No fallback literal: if LOGCAT_SPEC is
# unset, say so rather than inventing the string it probably was.
_spec = os.environ.get("LOGCAT_SPEC", "(LOGCAT_SPEC UNSET -- spec unknown)")
json.dump(dict(apk_sha=sha, kind="soak", title=title, seconds=int(seconds),
               requester=who, purpose=purpose, ref=ref,
               logcat=dict(spec=_spec, lines=int(lines)),
               device_serial=os.environ.get("SERIAL", ""),
               device_label=os.environ.get("DEVICE_LABEL", ""),
               logcat_lines=int(lines), pulled=pulled,
               # THE ENVIRONMENT THIS RUN ACTUALLY RAN WITH. An env A/B has one
               # binary, so apk_sha is identical across its arms and cannot
               # distinguish them -- this field is the only thing in the result
               # that can. A result with no `env` key predates the feature;
               # `env: []` means it was checked and there was none.
               env=json.loads(req_env or "[]"),
               # THE FRAMES, AND THE INTERVAL THEY WERE TAKEN AT. The interval
               # is recorded even when it is 0, because a soak with frames and
               # a soak without are not comparable on COST: a screencap every
               # second takes GPU and CPU from the thing whose frame rate is
               # being measured. A reader pooling a frame-capturing run with a
               # clean one should have to see this field to do it.
               frames=dict(every=int(frames_every or 0),
                           count=len(_frames),
                           bytes=sum(os.path.getsize(os.path.join(_fdir, f))
                                     for f in _frames),
                           dir="frames" if _frames else None)),
          open(os.path.join(rdir, "result.json"), "w"), indent=2)
print("soak done:", title, lines, "log lines")
PYEOF
        log "  soak done, $lines log lines -> $rdir/logcat.txt$(
            [ -d "$rdir/frames" ] && printf ', %s frames' "$(ls "$rdir/frames" | wc -l)")"
        mv "$req" "$rdir/request.json"
        rm -f "$D/running/$id.owner"
    touch "$rdir/DONE"
        resume_sweep
        return 0
    fi

    # disc identity is part of the result: two results are comparable only if
    # the ref differs and the disc composition matches.
    # Suite names contain spaces ("Stipple tests"), so they cannot go through
    # word splitting -- doing that turned one suite into two bogus --suite
    # arguments and the self-test came back with 0 captures. One per line,
    # read with mapfile.
    local suitefile="$rdir/suites.txt"
    python3 -c "import json,sys
for s in json.load(open(sys.argv[1])).get('suites',[]): print(s)" "$req" > "$suitefile"
    mapfile -t SUITE_LIST < "$suitefile"
    [ "${#SUITE_LIST[@]}" -gt 0 ] || { echo "no suites named" > "$rdir/ERROR"; log "  NO SUITES"; mv "$req" "$rdir/request.json"; return 0; }
    local skipfile="$rdir/skip_tests.txt"
    python3 -c "import json,sys
for t in json.load(open(sys.argv[1])).get('skip_tests',[]): print(t)" "$req" > "$skipfile"
    mapfile -t SKIP_LIST < "$skipfile"
    # The ALLOW-LIST. `tests` was a field this dispatcher accepted, recorded and
    # never read, so a requester narrowing an arm to three captures silently
    # measured hundreds. `only_tests` is the implemented replacement, and this
    # is the line whose absence made `tests` a lie.
    local onlyfile="$rdir/.only_tests"
    python3 -c "import json,sys
r=json.load(open(sys.argv[1]))
print('\n'.join(r.get('only_tests') or []))" "$req" > "$onlyfile" 2>/dev/null || : > "$onlyfile"
    mapfile -t ONLY_LIST < "$onlyfile"

    local disc_id
    # disc_id must IDENTIFY the disc, because the dispatcher's rule is that two
    # results are comparable only if the disc identity matches. Truncating the
    # suite list to 40 characters broke exactly that: a four-suite disc read as
    # "4-suites:Depth buffer,Depth buffer fixed function", dropping two names,
    # so two different discs sharing a prefix were indistinguishable. Carry a
    # hash of the full sorted list for identity and keep the prefix for reading.
    #
    # skip_tests is part of that identity for the same reason and a sharper
    # one: the same suite with and without a poisoning test differs by 9.9x on
    # an unchanged build, so letting the two share a disc_id would present a
    # disc swap as a code regression.
    #
    # AND THE BASE ISO IS PART OF IT TOO, which it was not until 2026-09-13.
    # This hashed only `suites` and `skip_tests`, so nothing about the TEST
    # BINARY entered the identity -- and a single-suite request short-circuits
    # to the bare suite name. So a disc built from a different
    # DISPATCH_BASE_ISO and the stock one both got `disc_id == "Blend_tests"`,
    # and ab_compare -- which refuses only when disc_id DIFFERS -- would have
    # compared them as the same disc. That is exactly the silent two-disc
    # mixing this identity exists to prevent, one level below where it was
    # looking.
    #
    # It was latent until now and is about to be reachable: the owner has
    # decided on a maintained fork of the test suite to reach the 1,568
    # `TestDetailed` goldens, which means a rebuilt XBE and a second base ISO
    # on this machine. Fixed BEFORE the first scored run from it, not
    # documented afterwards.
    #
    # Keyed on the ISO's size and mtime rather than a full content hash: the
    # file is 5.7 MB and this runs per request, and size+mtime changes on any
    # rebuild. A stale mtime with identical content costs a spurious
    # incomparability, which is the safe direction.
    # PER-REQUEST base ISO, because the alternative is a global that re-bases
    # every queued request. DISPATCH_BASE_ISO is an env var on the serving
    # dispatcher: setting it to run ONE arm off the interactive disc silently
    # changes the disc under every other request in the queue, including the
    # hundred-suite corpus sweep. That is not a hypothetical -- it is how a
    # column comes to be scored against a disc nobody intended, with every
    # row's disc_id agreeing with every other.
    #
    # So a request may name its own `base_iso`, and it wins. The env var stays
    # as the fleet-wide default.
    #
    # A NAMED ISO THAT DOES NOT EXIST FAILS THE REQUEST. It must not fall back
    # to stock: an arm registered against the interactive disc, silently run
    # against the stock one, produces captures that are real, scored, and
    # about the wrong disc -- and its result.json would carry the stock
    # disc_id, so nothing downstream could tell. A missing file is the cheap
    # failure; a plausible wrong one is the expensive failure this campaign
    # keeps paying for.
    local base_iso
    base_iso=$(jq_get "$req" base_iso "")
    if [ -n "$base_iso" ]; then
        if [ ! -f "$base_iso" ]; then
            echo "base_iso named by the request does not exist: $base_iso" \
                > "$rdir/ERROR"
            log "  BASE ISO MISSING: $base_iso -- refusing rather than falling back to stock"
            mv "$req" "$rdir/request.json"
            return 0
        fi
    else
        base_iso="${DISPATCH_BASE_ISO:-/home/justin/nxdk_pgraph_tests_xiso.iso}"
    fi
    # A QUOTED HEREDOC, and the quoting is the whole point of the change.
    #
    # This block used to be python3 -c with a DOUBLE-quoted shell string, so
    # the shell ran command substitution over the Python source before Python
    # ever saw it. The eight backticks in the comments below pair into four
    # substitutions, and EVERY disc request on this queue printed
    #     suites: command not found
    #     skip_tests: command not found
    #     only_tests: command not found
    #     iso:85b525/Blend: No such file or directory
    # on stderr -- noise a lane has to rule out before trusting its own run --
    # while the comment text itself was deleted from what Python compiled, so
    # the reasoning recorded here was never actually in the file that ran.
    #
    # Cosmetic ONLY because the backticks happen to sit in comments. The
    # moment a pair wraps something executable it is a live defect, and $ and
    # backslash in this source are exposed by exactly the same mechanism --
    # the \n in the only_tests block above survives by luck, not by design.
    # Quoting the heredoc delimiter takes the shell out of the path entirely.
    disc_id=$(python3 - "$req" "$base_iso" <<'PYEOF'
import hashlib,json,os,sys
r=json.load(open(sys.argv[1]))
iso=sys.argv[2]
s=sorted(r.get('suites',[]))
k=sorted(r.get('skip_tests',[]))
# ONLY_TESTS BELONGS IN THE KEY, and leaving it out was a live hole.
#
# disc_id is the comparability key: ab_compare REFUSES a pair whose disc_ids
# differ, and `suites` and `skip_tests` are in it precisely because they change
# what the disc contains. `only_tests` changes it far more drastically -- a
# 1,673-capture disc becomes a 1-capture disc -- and I added the field this
# morning without adding it here, so all three compositions came back as the
# bare `iso:85b525/Blend tests`.
#
# That is not theoretical. Within hours I pooled 13 observations of one capture
# across a 1,673-test disc, a 5-test disc and a 1-test disc and reported a rate
# from them, because nothing said they were different discs. And the discs
# really do differ: 1-dstA_SUB_1-cRGB reads 16,384 on the full disc and 12,512
# on the 5-test one, which is the documented RenderTextureLoop class of
# poisoning -- state an earlier test leaves behind.
#
# Tagged rather than spelled out because 196 names do not belong in an id, and
# the COUNT is included so a human can see at a glance that the disc was
# narrowed.
o=sorted(r.get('only_tests',[]))
try:
    st=os.stat(iso)
    tag=hashlib.sha1(('%s|%d|%d' % (os.path.basename(iso), st.st_size,
                                    int(st.st_mtime))).encode()).hexdigest()[:6]
except OSError:
    tag='noiso'
# The stock disc keeps its bare, readable ids so every result already on disk
# stays comparable with new ones. Any OTHER base iso is tagged, loudly.
STOCK = '/home/justin/nxdk_pgraph_tests_xiso.iso'
pre = '' if os.path.abspath(iso) == STOCK else 'iso:%s/' % tag
if o:
    pre += 'only%d:%s/' % (len(o), hashlib.sha1(','.join(o).encode()).hexdigest()[:6])
if len(s)==1 and not k:
    print(pre + s[0])
elif len(s)==1:
    print(pre + '%s-no:%s' % (s[0], ','.join(t.split('::')[-1] for t in k)[:30]))
else:
    h=hashlib.sha1((','.join(s)+'|'+','.join(k)).encode()).hexdigest()[:8]
    print(pre + '%d-suites:%s:%s' % (len(s), h, ','.join(s)[:40]))
PYEOF
)

    local r
    for r in $(seq 1 "$runs"); do
        local args=() gdir="d$(echo "$id$r" | md5sum | cut -c1-6)"
        local s
        for s in "${SUITE_LIST[@]}"; do args+=(--suite "${s//_/ }"); done
        for s in "${SKIP_LIST[@]:-}"; do [ -n "$s" ] && args+=(--skip-test "$s"); done
        for s in "${ONLY_LIST[@]:-}"; do [ -n "$s" ] && args+=(--only-test "$s"); done
        python3 "$HERE/make_test_iso.py" "$base_iso" \
            -o "$rdir/disc$r.iso" "${args[@]}" --progress-log \
            --shutdown-on-completion --output-dir "e:/$gdir" >>"$rdir/run$r.log" 2>&1
        touch "$LEASE"
        SERIAL="$SERIAL" DEVICE_ISO_ROOT="$DEVICE_ISO_ROOT" DEVICE_LABEL="$DEVICE_LABEL" \
            HAKUX_DEVICE_LEASE="$LEASE" CAPTURE_LOG="$rdir/logcat$r.txt" \
            bash "$HERE/run_disc.sh" "$rdir/disc$r.iso" "$gdir" \
            "$rdir/captures$r" 1800 >>"$rdir/run$r.log" 2>&1
        rm -f "$rdir/disc$r.iso"
        python3 "$HERE/score_sweep.py" --out "$rdir/captures$r" --goldens "$GOLDENS" \
            --flat --apk-sha "$sha" --disc-id "$disc_id" --label "$requester" \
            --tsv "$rdir/scores$r.tsv" >>"$rdir/run$r.log" 2>&1
    done

    REQ_ENV_JSON="$req_env" \
    python3 - "$rdir" "$sha" "$disc_id" "$requester" "$purpose" "$ref" "$SNAP" <<'PYEOF'
import csv, glob, json, os, subprocess, sys
rdir, sha, disc, who, purpose, ref, snap = sys.argv[1:8]
meta = dict(apk_sha=sha, disc_id=disc, requester=who, purpose=purpose, ref=ref)
# THE ENVIRONMENT THIS RUN ACTUALLY RAN WITH, deliberately NOT folded into
# disc_id. disc_id says whether two runs scored the same captures, and an env
# A/B scores exactly the same captures on purpose -- putting env in there would
# make ab_compare refuse the one comparison this field was added to enable. It
# is the independent variable, not part of the disc, and ab_compare reads it as
# such. A result with no `env` key predates the feature; `env: []` means it was
# checked and there was none.
meta["env"] = json.loads(os.environ.get("REQ_ENV_JSON") or "[]")
# TWO revisions, because `classifier_rev` has been recording the WRONG FILE.
#
# The `status` column every consumer reads -- ok / label-differs /
# white-content -- is assigned by `score_sweep.py`. `classify_residuals.py`
# never touches it. So a column scored before score_sweep.py changed and one
# scored after can disagree on which captures are VOID with no pixel differing
# and nothing in the metadata to tell them apart.
#
# That is not hypothetical. The label-band fix landed in score_sweep.py at
# 06:20 on 2026-09-13; classify_residuals.py was last touched at 04:45. Two
# results with the SAME classifier_rev 37a5cc7ff3 produce the same 42/63 split
# on identical test names, and one calls those 63 `label-differs` (void) while
# the other calls them `white-content` (scorable) -- so the whole z-tip-* sweep
# column's void counts are inflated. ab_compare refuses a mismatched disc_id
# and had no equivalent guard here; the #75 filer re-scored both capture sets
# by hand specifically to rule this out, which is the work a recorded revision
# saves.
def _rev(path):
    try:
        return subprocess.run(
            ["git", "-C", "/home/justin/hakuX", "log", "-1", "--format=%h",
             "--", path], capture_output=True, text=True).stdout.strip() or "unknown"
    except Exception:
        return "unknown"
meta["classifier_rev"] = _rev("docs/testing/classify_residuals.py")
meta["scorer_rev"] = _rev("docs/testing/score_sweep.py")
# AND THE HASH OF THE FILE THAT ACTUALLY RAN, because `scorer_rev` above can
# name a revision that scored nothing.
#
# It is `git log -1` on the TREE at result-writing time, while the scoring was
# done by the SNAPSHOT under $DISPATCH_DIR/bin -- and the tree can move between
# those two moments: a worker snapshots at re-exec, then a commit lands while
# it is mid-run, and the result records the new revision against captures the
# old one scored. I introduced that field this morning and it has this hole in
# it, which is the same class of provenance bug it was added to close.
#
# A content hash of the snapshot cannot be wrong about which code ran. The git
# revision stays because it is what a human can look up; when they disagree,
# the hash is the fact and the revision is the guess.
try:
    import hashlib
    with open(os.path.join(snap, "score_sweep.py"), "rb") as fh:
        meta["scorer_sha256"] = hashlib.sha256(fh.read()).hexdigest()[:12]
except Exception:
    meta["scorer_sha256"] = "unknown"
runs = []
for t in sorted(glob.glob(os.path.join(rdir, "scores*.tsv"))):
    rows = [r for r in csv.DictReader(open(t), delimiter="\t") if r.get("suite")]
    # A run counts only if its own progress log shows tests completing.
    logdir = t.replace("scores", "captures").replace(".tsv", "")
    plog = os.path.join(logdir, "pgraph_progress_log.txt")
    proof = "completed normally" in open(plog, errors="replace").read() if os.path.exists(plog) else False
    runs.append(dict(tsv=os.path.basename(t), captures=len(rows),
                     exact=sum(1 for r in rows if int(r["differing"] or 0) == 0),
                     px=sum(int(r["differing"] or 0) for r in rows),
                     progress_log_proof=proof))
# Which device produced this. A scoreboard column that mixes two handhelds
# is the same failure as one that mixes two binaries, and apk_sha could not
# catch that one either -- it was perfectly consistent and consistently old.
meta["device_serial"] = os.environ.get("SERIAL", "")
meta["device_label"] = os.environ.get("DEVICE_LABEL", "")
meta["runs"] = runs

# Name the log explicitly, so "we captured nothing" and "the suite dropped
# nothing" are different answers. They looked identical before, which is the
# same failure the unhandled-method log exists to fix, one level up.
logs = []
for lg in sorted(glob.glob(os.path.join(rdir, "logcat*.txt"))):
    n = sum(1 for _ in open(lg, errors="replace"))
    logs.append(dict(file=os.path.basename(lg), lines=n))
# No fallback literal. If LOGCAT_SPEC is somehow unset, record that it was
# unset rather than inventing the string it probably was -- an invented spec
# is the provenance bug this field exists to prevent.
meta["logcat"] = dict(spec=os.environ.get("LOGCAT_SPEC", "(LOGCAT_SPEC UNSET -- spec unknown)"),
                      captured=bool(logs), files=logs)

# coverage against the oracle we own: the tell for a partially retired suite
cov = {}
suites = set()
for t in sorted(glob.glob(os.path.join(rdir, "scores*.tsv"))):
    for row in csv.DictReader(open(t), delimiter="\t"):
        if row.get("suite"):
            suites.add(row["suite"])
for s in sorted(suites):
    gd = os.path.join("/home/justin/goldens/results", s)
    have = len([f for f in os.listdir(gd)]) if os.path.isdir(gd) else 0
    got = sum(1 for t in sorted(glob.glob(os.path.join(rdir, "scores1.tsv")))
              for row in csv.DictReader(open(t), delimiter="\t")
              if row.get("suite") == s)
    cov[s] = dict(scored=got, goldens=have,
                  partial=bool(have and got < have))
meta["captures_vs_goldens"] = cov
json.dump(meta, open(os.path.join(rdir, "result.json"), "w"), indent=2)
print("captures:", sum(r["captures"] for r in runs),
      "partial:", [s for s, c in cov.items() if c["partial"]])
PYEOF

    local got; got=$(python3 -c "
import json,sys
m=json.load(open(sys.argv[1]))
print(sum(r['captures'] for r in m['runs']))" "$rdir/result.json" 2>/dev/null || echo 0)
    mv "$req" "$rdir/request.json"
    if [ "${got:-0}" = "0" ]; then
        # Zero captures is a failed run, not a result of zero. Handing a
        # requester an empty TSV as if it were an answer is how "this suite
        # renders nothing" gets believed.
        echo "ran but produced 0 captures; see run1.log and captures1/" > "$rdir/ERROR"
        log "  FAILED: 0 captures"
        return 0
    fi
    rm -f "$D/running/$id.owner"
    touch "$rdir/DONE"
    log "  done -> $rdir"
    adb -s "$SERIAL" shell am force-stop com.jreinach.hakux.debug >/dev/null 2>&1
}

# The logcat spec, defined ONCE and exported, because it was previously defined
# in three places that could disagree: the soak path passed one explicitly,
# the disc path fell through to run_disc.sh's own default, and the metadata
# writer recorded a third literal as "what was captured". A result claiming a
# spec that was never used is worse than one claiming none -- someone reads
# `logcat.spec`, sees the tag they need, finds no lines, and concludes the
# code does not log rather than that the filter dropped it.
#
# hakuX:I and hakuX-rw:I are here rather than at :W because two lines that
# answer "were the draw-reorder prefs on for this run?" are logged at I, and
# the #50 investigation could not answer that question from any of the
# dispatcher's own logcats.
# hakuX-phase and xemu-work were MISSING and it cost a survey. A -Pperflog=true
# build compiles NV2A_PERF_LOG in and logs under `hakuX-phase`; with the tag
# absent here the run produced ZERO phase lines while the binary was correct,
# which reads exactly like a soak that measured nothing. Established on the APK
# files rather than the device: libxemu.so from the perflog APK contains
# `hakuX-phase` and the normal one does not, with `hakuX-perf` in both as the
# control. `xemu-work` is in the same edit deliberately -- it carries BE:/TexU:,
# the instrumentation-INDEPENDENT workload control, without which a phase
# survey can be non-empty and still uninterpretable.
#
# `hakuX-lane` IS RESERVED FOR LANE INSTRUMENTATION, and it exists because this
# list is an ALLOW-LIST ending in `*:S`. Every tag not named here is silenced,
# so a lane that adds a new tag gets back a logcat with not one line of it --
# indistinguishable from the mechanism never firing. Three times now:
# `hakuX-phase` cost a whole phase survey, `xemu-work` would have made the next
# one uninterpretable, and a signed-blend lane printed a pass counter to
# `hakuX-signfold`, spent an arm, and read back zero lines.
#
# Adding each tag as it appears is the fix that does not scale, because the
# lane discovers the problem only after paying for an arm. So instrument under
# `hakuX-lane` and the output is captured with no edit here and no restart. A
# lane's own tag still works when added to this list, but it must be added
# BEFORE the arm rather than after reading an empty log.
#
# And the leg that belongs on any such counter: SILENCE IS VOID, never pass. An
# absent line means the capture failed, not that the condition did not occur.
#
# THE OVERRIDE IS `LOGCAT_SPEC_OVERRIDE`, NOT `LOGCAT_SPEC`, AND THAT IS THE
# WHOLE REASON ANY EDIT HERE TAKES EFFECT.
#
# This line used to read `${LOGCAT_SPEC:-...}` and then export LOGCAT_SPEC. A
# `:-` default only fires when the variable is UNSET, so once exported, the
# worker's own environment shadowed the default -- and a re-exec inherits that
# environment, so NO EDIT TO THIS SPEC COULD EVER REACH A RUNNING FLEET. The
# script read its own stale output as its input.
#
# Measured 2026-09-13, and it had eaten two fixes silently. The live worker's
# environment held a spec with neither `hakuX-phase` nor `xemu-work` -- added
# hours earlier, after an empty phase survey -- and then not `hakuX-lane`
# either. A lane registered a counter on `hakuX-lane`, got zero lines, and
# correctly reported the tag as reserved-but-silenced; the reservation was on
# disk and in the snapshot and inert in practice.
#
# With the override under its own name, the default here is authoritative on
# every re-exec, and a human or a test can still pin a spec deliberately. The
# general shape is worth keeping in mind: a variable that is both an input and
# an exported output cannot be changed by editing its default.
#
# `hakuX-tier1:D` ADDED 2026-09-14 for #81, and it is the case the paragraph
# above is about. The tag is compiled into accel/tcg (cpu-exec.c:155/182/204,
# translate-all.c:612/679) and predates the `hakuX-lane` convention, so it
# cannot be reached by instrumenting under the reserved tag without a build.
# Every spec this file has ever had ends `*:S`, which silenced it BEFORE the
# question was asked -- so the zero `[tier1]` lines on every logcat on disk are
# NOT evidence that the mechanism never fires. They are evidence of the filter.
# #81's first step is that measurement and not a fix, because "the slots fill
# with duplicates" and "the mechanism never fires" want different fixes.
#
# `:D` and not `:I` because four of the five sites log at priority 3 (DEBUG);
# only translate-all.c:612 is priority 4. `:I` would have captured one site in
# five and read as a partial answer. The sites are self-throttled -- first ten,
# then every ten-thousandth -- so this costs a handful of lines per run, not a
# flood; that was checked before adding it rather than assumed.
LOGCAT_SPEC="${LOGCAT_SPEC_OVERRIDE:-hakuX-crash:V hakuX-unhandled:W hakuX-audio:I hakuX-audiocap:I hakuX-build:I hakuX-perf:I hakuX-phase:I xemu-work:I hakuX-lane:I hakuX-tier1:D hakuX-pages:I hakuX:I hakuX-rw:I VALIDATION:W ValidationLayer:W vulkan:W VulkanLoader:W *:S}"
export LOGCAT_SPEC

# Which device runs the idle sweep. One of them must, and both of them must
# not: two workers driving one long sweep would fight over its disk image.
SWEEP_DEVICE="${SWEEP_DEVICE:-nova}"

case "${1:-status}" in
  serve)
    # Supervisor. One process owns every attached handheld and forks a worker
    # per device; the workers share the queue and claim by atomic rename.
    #
    # Two separate dispatcher processes would also have shared the queue, and
    # that was the first design. It is wrong, for a reason that has nothing to
    # do with throughput: nothing in it stops the two arms of an A/B landing
    # on different handhelds. A comparison is only a comparison if one thing
    # changed, and running `base` on the Nova and `fix` on the Thor changes
    # the binary AND the hardware while presenting the result as a one-commit
    # delta. Only a single scheduler can enforce that a pair stays together --
    # see affinity.py -- and only a single scheduler can say "this soak needs
    # a title only one device has", or keep two workers from entering
    # build_ref for the same sha at once.
    #
    # It also removes a class of bug outright: with one process there is no
    # question of whose orphan is whose.
    snapshot_scripts
    workers=()
    serials=()
    for s in $(adb devices | tr -d '\r' | awk 'NR>1 && $2=="device"{print $1}'); do
        if ! ( device_env "$s" ) 2>/dev/null; then
            log "skipping unknown device $s; add it to devices.sh"
            continue
        fi
        log "starting worker for $s"
        SERIAL="$s" bash "$SNAP/dispatcher.sh" worker "$s" &
        workers+=($!)
        serials+=("$s")
    done
    if [ "${#workers[@]}" -eq 0 ]; then
        echo "no known device attached" >&2; exit 2
    fi
    log "=== supervising ${#workers[@]} device worker(s) ==="
    trap 'kill ${workers[@]} 2>/dev/null; exit 0' INT TERM
    # Supervise, rather than merely start and wait. A worker that dies takes
    # its device out of service silently: the queue keeps accepting requests
    # pinned to it and nothing serves them. That happened within the hour --
    # a lane was down for twenty-five minutes and was noticed by an agent
    # wondering why its request never ran, not by anything here.
    #
    # So poll the children and restart any that have exited. Restarting is
    # safe because all state lives in the queue and results directories, and
    # a worker's own orphan sweep requeues only what it owns.
    while :; do
        sleep 20
        for i in "${!workers[@]}"; do
            if ! kill -0 "${workers[$i]}" 2>/dev/null; then
                log "worker for ${serials[$i]} (pid ${workers[$i]}) is gone; restarting"
                SERIAL="${serials[$i]}" bash "$SNAP/dispatcher.sh" worker "${serials[$i]}" &
                workers[$i]=$!
            fi
        done
    done
    ;;
  worker)
    # The loop parses this file once at startup, so an edit to it -- or to
    # soak_title.sh, run_disc.sh, score_sweep.py -- does not reach a running
    # server. That has now cost three measurements: a logcat capture that was
    # never wired, a soak whose pull did not exist yet, and a perf run whose
    # tags were not in the spec. Each time the symptom was an empty result
    # rather than an error.
    #
    # So the loop re-execs itself whenever its own inputs change on disk. State
    # lives in the queue and results directories, not in the process, so an
    # exec between requests is free. Hash the scripts it actually depends on.
    DISPATCH_SRC_HASH="$(src_hash)"
    export DISPATCH_SRC_HASH
    # Anything left in running/ belongs to a loop that is gone -- killed,
    # crashed, or restarted to pick up a change. Its request was accepted and
    # never answered, so put it back rather than leaving it to be found by
    # hand: restarting the loop between a build and a device run silently
    # orphaned a queued A/B arm exactly once, which is once more than it
    # should be possible to do.
    # Only OUR orphans. With two dispatchers sharing a queue, a blanket
    # requeue at startup would yank the other instance's in-flight request
    # back into the queue and it would be served twice -- on two different
    # devices, into one result id. The owner file is written at claim time.
    # Register this lane, so affinity.py knows how many devices a prediction
    # name is being divided over. The claim is "a worker for this label is
    # alive", and the only honest way to make it is to have the worker make it
    # about itself: a supervisor's list outlives the worker it describes, and a
    # timestamp cannot tell a dead lane from one 20 minutes into a 26-minute
    # A/B arm. A pid can, and needs no refreshing.
    # Registering here is no longer the only time it happens -- lane_claim runs
    # every tick below, because this file being written once per process is
    # exactly what turned a transient `rm` into a five-hour outage of the whole
    # pinning mechanism. See the lane_file block above.
    lane_claim
    trap lane_release EXIT

    for orphan in "$D"/running/*.req; do
        [ -e "$orphan" ] || continue
        oid=$(basename "$orphan" .req)
        owner=""
        [ -f "$D/running/$oid.owner" ] && owner=$(cat "$D/running/$oid.owner" 2>/dev/null)
        # Requeue ONLY what this device owns. An owner-less entry is NOT mine
        # by default: that is exactly what a second dispatcher meets on its
        # first start, when the other device's in-flight request predates the
        # owner file. Treating it as mine requeued a live run and handed the
        # same result id to two devices at once -- caught within seconds of
        # starting the Thor for the first time, which is the only reason this
        # reads as a comment rather than as a corrupted arm.
        #
        # The cost of being wrong the other way is a request that sits in
        # running/ until someone looks, which is loud and harmless. The cost
        # of being wrong this way is two devices writing one result.
        if [ "$owner" != "$DEVICE_LABEL" ]; then
            log "leaving orphan $oid alone; owner=${owner:-none}, I am $DEVICE_LABEL"
            continue
        fi
        log "requeueing orphan $oid from a previous loop"
        rm -f "$D/running/$oid.owner"
        mv "$orphan" "$D/queue/" 2>/dev/null || true
    done
    log "=== dispatcher serving; queue=$D/queue ==="
    held_logged=0
    while :; do
        shopt -s nullglob
        # A DEVICE CAN BE TAKEN OUT OF SERVICE WITHOUT STOPPING ANYTHING.
        #
        #     touch  $D/hold/<label>     # stop claiming on that handheld
        #     rm     $D/hold/<label>     # put it back in service
        #
        # There was no way to do this, and the absence showed: when the nova
        # went offline for four hours its worker kept claiming requests,
        # finding no device, and requeueing them every thirty seconds. Nothing
        # was lost -- the requeue path is correct -- but a claim/requeue churn
        # is indistinguishable in the log from the dirty-tree loop that cost
        # 251 requeues earlier the same day, and it occupies the queue head
        # against a device that cannot serve it.
        #
        # Killing the worker does not work either: the supervisor restarts any
        # worker that exits, by design, because a silently dead lane once took
        # a device out of service for twenty-five minutes. So the hold has to
        # be something the worker consults, not a process state.
        #
        # Checked HERE, at the top of the loop and before the queue is read, so
        # a hold placed mid-run takes effect after the current request rather
        # than interrupting it -- the same discipline as the re-exec below.
        if [ -e "$D/hold/$DEVICE_LABEL" ]; then
            [ "$held_logged" = 1 ] || log "HELD by $D/hold/$DEVICE_LABEL; claiming nothing until it is removed"
            held_logged=1
            lane_release   # affinity must not pin a pair to a device on hold
            sleep 30
            continue
        fi
        if [ "$held_logged" = 1 ]; then
            log "hold released; serving again"
            held_logged=0
        fi
        # Re-assert the registration on EVERY tick, not only after a hold.
        # held_logged is now purely a log-once flag: the restore no longer
        # depends on this process having been the one that observed the hold,
        # which was the brief's suspected defect even though the code did in
        # fact set the flag alongside its `rm`. Restoring unconditionally is
        # cheaper than arguing about which process saw what.
        #
        # AFTER the hold check, never before, or a held device would re-register
        # itself thirty seconds after taking itself out of service.
        lane_claim
        # Served in glob order, which is ASCII order, and that is the whole
        # priority mechanism. Normal requests are named with an epoch prefix so
        # they sort by arrival. Two conventions ride on top:
        #
        #   0-*   jumps the queue -- a 45-second probe that unblocks an agent
        #         should not sit behind two 26-minute A/B arms.
        #   z-*   idle priority -- the full-corpus scoreboard sweep enqueues
        #         one request per suite as z-sweep-*, so every digit-prefixed
        #         request from an agent sorts ahead of all of them. The sweep
        #         then fills whatever gaps the session leaves without ever
        #         blocking a fix from being verified.
        #
        # It yields between suites rather than mid-suite, so an agent waits at
        # most one suite instead of the remaining hours.
        now_hash="$(src_hash)"
        # A startup hash of "" -- the worker started while a build held the
        # tree detached -- must not read as "changed" on the first clean tick,
        # or every worker re-execs once for nothing. Adopt it silently.
        if [ -z "$DISPATCH_SRC_HASH" ] && [ -n "$now_hash" ]; then
            DISPATCH_SRC_HASH="$now_hash"
        fi
        if [ -n "$now_hash" ] && [ "$now_hash" != "$DISPATCH_SRC_HASH" ]; then
            log "dispatcher scripts changed on disk; re-execing to pick them up"
            # Exec the SNAPSHOT, never the working tree. build_ref detaches
            # that tree to an arbitrary commit for the length of a build, so a
            # re-exec landing inside another worker's build would exec
            # whatever dispatcher.sh that ref carries -- and an older one has
            # no `worker` subcommand at all, falls through the case to
            # `status`, prints and exits. That is how the Nova worker died
            # silently at 21:46 while the Thor was building, leaving a lane
            # that accepted no work for twenty-five minutes.
            #
            # Taking the build lock instead does not work and is worth saying
            # so: fd 9 survives exec, so the re-execed worker would hold the
            # lock for its whole life and every later build would block on it
            # forever. Tried, and it wedged the queue within a minute.
            #
            # A snapshot has neither problem -- it does not move when the tree
            # does, and it needs no lock.
            snapshot_scripts
            exec bash "$SNAP/dispatcher.sh" worker "$SERIAL"
        fi

        reqs=("$D"/queue/*.req)
        if [ "${#reqs[@]}" -eq 0 ]; then
            # Only the sweep-owning device resumes it, or two workers would
            # drive the same long sweep against one disk image.
            [ "$DEVICE_LABEL" = "$SWEEP_DEVICE" ] && resume_sweep
            sleep 10
            continue
        fi
        # Walk the queue in priority order rather than taking [0] blindly:
        # the first request may be pinned to the other handheld, and stopping
        # there would idle this one behind work it is not allowed to do.
        served=0
        for r in "${reqs[@]}"; do
            if serve_one "$r"; then served=1; break; fi
        done
        [ "$served" = 1 ] || sleep 5

        # Drop my own owner files whose request has left running/. serve_one
        # has seven post-claim exits -- build failed, no APK, title missing,
        # no suites -- and none of them clears the marker, so running/ slowly
        # filled with owners for finished work and stopped answering the one
        # question it exists to answer: whose is this. Self-healing here
        # rather than eight edits, so a new exit path cannot reintroduce it.
        for o in "$D"/running/*.owner; do
            [ -e "$o" ] || continue
            oid=$(basename "$o" .owner)
            [ -f "$D/running/$oid.req" ] && continue
            [ "$(cat "$o" 2>/dev/null)" = "$DEVICE_LABEL" ] && rm -f "$o"
        done
    done
    ;;
  status)
    echo "queue:   $(ls "$D/queue"/*.req 2>/dev/null | wc -l) waiting"
    echo "running: $(ls "$D/running"/*.req 2>/dev/null | wc -l)"
    echo "results: $(ls -d "$D/results"/*/ 2>/dev/null | wc -l)"
    device_present && echo "device:  present" || echo "device:  ABSENT"
    sweep_running && echo "sweep:   running" || echo "sweep:   not running"
    echo "build:   $BUILD_TREE @ $(git -C "$BUILD_TREE" rev-parse --short HEAD 2>/dev/null || echo 'not created yet')"
    tail -5 "$D/logs/dispatcher.log" 2>/dev/null
    ;;
  *) sed -n '3,12p' "$0" ;;
esac
