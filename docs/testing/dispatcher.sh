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
# EVERY FILE snapshot_scripts SHIPS, or a change to one never reaches a worker.
#
# This listed four of the nine files the snapshot copies. The other five --
# affinity.py, devices.sh, captures.py, make_test_iso.py, extract_results.py --
# could be edited, committed and folded without changing this hash, so no
# worker ever re-execed and no worker ever re-snapshotted: they kept executing
# whatever copy was in $SNAP when they last restarted.
#
# That is not hypothetical. 37af3f02fe changed affinity.py to keep handheld
# work off the desktop lane. The running workers never saw it, kept the older
# copy, and it pinned every queued A/B to `desktop` -- a lane no dispatcher
# worker serves. Both handhelds skipped those requests silently, which is what
# serve_one does with a pin that is not its own, and four arms sat unclaimed
# for eighteen hours with two healthy devices idle.
#
# The two sets must be the same set. Keep this in sync with snapshot_scripts.
#
# AND THE SET MUST BE CLOSED: every sibling a shipped script runs from its own
# directory ($HERE/x, $(cd ... && pwd)/x, os.path.join(HERE, "x"), a Python
# import) is shipped too, because in a worker $HERE IS $SNAP and anything not
# copied there does not exist. preempt_sweep ran $HERE/sweep_queue.sh, which
# was in neither list, and that script runs make_isolation_discs.py (audit
# pass 1 on #206, M2). selftest.d/97 checks the closure, not only equality.
SCRIPT_DEPS="dispatcher.sh devices.sh soak_title.sh run_disc.sh score_sweep.py \
affinity.py captures.py make_test_iso.py extract_results.py sweep_queue.sh \
make_isolation_discs.py vsh_score.py thermal_state.py titles/route.sh perf/pad.sh \
battery_admit.py titles/titlestate.py titles/saves.py titles/drive.py \
titles/classify.py titles/waitfor_match.py titles/pathclass.py titles/pathknow/learned.py \
titles/pathbook.py jobs/device_build.py \
jobs/models.py jobs/models.toml dispatch_doctor.sh jobs/window.sh jobs/models.sh \
jobs/allowed-tools.doctor jobs/roles/dispatchdoctor.md"
# DATA A SHIPPED SCRIPT PICKS AT RUN TIME, shipped by glob, never by name.
#
# route.sh's `drive <profile>` step runs drive.py on
# $HERE/drive-profiles/<profile>.toml, and classify.py reads that profile's
# reference crops from drive-profiles/<profile>/*.png. None of it was in the
# snapshot, so `route.sh --check` on any .drive.route failed in a worker with
# "no profile" and no dispatched run could play one (#433, routedriver2
# NOTES section 4). A profile is added per title, so naming them here would
# go stale with the next title; the globs pick up a new one at the next
# re-exec, and src_hash covers what they match, so adding one IS a re-exec.
# drive-profiles/selftest/ is classify's fixtures, not data a run reads.
#
# A profile with `classifier = "pathclass"` (drive-profiles/generic.toml, #433) makes
# classify.py load titles/pathclass.py's trained head at runtime -- a single fixed file,
# not one per title, but still data a shipped script picks up rather than imports, so it
# is listed here rather than in SCRIPT_DEPS: without it every dispatched `drive generic`
# step would fail closed with `pathclass unavailable` for a reason that is purely a
# snapshot omission, not a real unavailability.
#
# titlestate.py's `admit` (profile_gate_check's only subcommand) opens three more files
# beside itself, none of them in SCRIPT_DEPS: targets.toml (titlestate.py targets(), read
# on every claim), routes/<name>.route (titlestate.py proven_route(), the --find-route R3
# check) and profile-transition.toml (titlestate.py live_transition(), the returning/
# first-run claim path). Without targets.toml a claim that reaches it crashes outright
# (snaptargets1018, #433): any first-run or find-route title, since a title with a golden
# short-circuits admit() before targets() is ever called. The other two fail closed and
# silent instead of crashing -- proven_route()'s and load_transitions()'s opens are both
# try/excepted -- which is worse: a title with an already-proven route looks unproven (R3
# stops protecting anything) and the transition grandfather never fires, both from the
# worker only, with nothing in the log to say why. All three are a fixed file (or, for
# routes, a file per title, same shape as a drive profile), so they ship here, not in
# SCRIPT_DEPS; src_hash already covers whatever this matches.
#
# pathknow/paths/<TID>.json: pathfind.py's recorded paths into play, one per title.
# drive.py replays one (pathbook.py load(), beside itself) when it beats the title's
# drive-built book in $D/paths; without them a re-run of a pathfind title starts from
# trial again (routebuild1021).
SNAPSHOT_GLOBS="titles/drive-profiles/*.toml titles/drive-profiles/*/*.png titles/pathknow/classifier/head.npz \
titles/targets.toml titles/profile-transition.toml titles/routes/*.route titles/pathknow/paths/*.json"
snapshot_globbed() {   # every file SNAPSHOT_GLOBS matches in $SRC, relative to it
    ( cd "$SRC" 2>/dev/null || exit 0
      local f
      for f in $SNAPSHOT_GLOBS; do
          case "$f" in */selftest/*) continue ;; esac
          [ -f "$f" ] && printf '%s\n' "$f"
      done )
}
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
    local f g
    # `for f in` stays one loop over literal names: 97-dispatch-deploy parses
    # this list and compares it with SCRIPT_DEPS.
    for f in dispatcher.sh devices.sh soak_title.sh run_disc.sh score_sweep.py \
             affinity.py captures.py make_test_iso.py extract_results.py \
             sweep_queue.sh make_isolation_discs.py vsh_score.py thermal_state.py \
             titles/route.sh perf/pad.sh battery_admit.py titles/titlestate.py \
             titles/saves.py titles/drive.py titles/classify.py titles/waitfor_match.py \
             titles/pathclass.py titles/pathknow/learned.py titles/pathbook.py jobs/device_build.py \
             jobs/models.py jobs/models.toml \
             dispatch_doctor.sh jobs/window.sh jobs/models.sh jobs/allowed-tools.doctor \
             jobs/roles/dispatchdoctor.md; do
        snapshot_one "$f"
    done
    for g in $(snapshot_globbed); do
        snapshot_one "$g"
    done
}
snapshot_one() {   # snapshot_one <path relative to $SRC>
    local f="$1" SRC="$SRC" SNAP="$SNAP"
    # Some live in subdirectories. Each file is resolved against its own
    # directory, so the write-beside-and-rename below stays in one directory,
    # and cp gets a directory that exists.
    if [ "${f%/*}" != "$f" ]; then
        SRC="$SRC/${f%/*}"; SNAP="$SNAP/${f%/*}"; f="${f##*/}"
    fi
    [ -f "$SRC/$f" ] || return 0
    mkdir -p "$SNAP" 2>/dev/null
    cmp -s "$SRC/$f" "$SNAP/$f" 2>/dev/null && return 0
    # NEVER REWRITE A SNAPSHOT FILE IN PLACE. $SNAP is shared by every
    # worker, and bash reads a running script lazily, by byte offset: a
    # `cp -f` over run_disc.sh while the other device's worker was inside
    # it made that bash read the new file at the old offset (`line 137:
    # cess: command not found`), and a real run was voided as "the
    # emulator never started" (2026-09-25, dispatch-hardening defect 13).
    # Write beside it and rename: the rename swaps the inode, and a
    # process already reading the old file keeps the old one.
    cp -f "$SRC/$f" "$SNAP/.$f.tmp.$$" 2>/dev/null \
        && mv -f "$SNAP/.$f.tmp.$$" "$SNAP/$f" 2>/dev/null \
        || rm -f "$SNAP/.$f.tmp.$$"
}
# Hash of the scripts as they are IN THE TREE. This used to return empty
# while $TREE was detached for a build, because mid-build the tree held some
# other commit's scripts. Builds no longer touch $TREE (see BUILD_TREE), so
# the tree's scripts are always the tree's scripts and the hash is honest.
# The globbed files go in by name AND content, so adding, renaming or editing a
# profile or one of its crops moves the hash.
src_hash() {
    local globbed; globbed=$(snapshot_globbed)
    ( cd "$SRC" && { cat $SCRIPT_DEPS
                     for f in $globbed; do echo "$f"; cat "$f"; done
                   } 2>/dev/null | md5sum | cut -c1-12 )
}
# Logs go to the file and to STDERR, never stdout. build_ref's stdout is
# captured as the APK path, so a log line on stdout becomes the path: adding
# one informational message to the success path made every build return the
# log text instead of a file, and the run failed at install with an empty
# binary. Anything that writes to stdout inside a $(...) here is a bug.
log() { echo "$(date '+%m-%d %H:%M:%S') $*" | tee -a "$D/logs/dispatcher.log" >&2; }
jq_get() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],sys.argv[3] if len(sys.argv)>3 else ''))" "$1" "$2" "${3:-}"; }

device_present() {
    timeout -k 5 30 adb devices | tr -d '\r' | grep -q "^$SERIAL[[:space:]]*device$"
}

# EVERY adb CALL IN THE SERVE PATH GOES THROUGH adb_call (devices.sh), with a
# deadline sized to the operation. The install, the run-as pref calls and the
# force-stops had none, and one of them held the Thor from 09-14 06:29 to
# 09-18 09:23 while the queue waited behind it. A call that hangs is written
# to ADB_HUNG_FILE (per device, cleared at each claim); adb_error turns that
# into the request's ERROR line, so the result names the call that hung and
# the worker leaves through the post-claim exit it would have taken anyway.
ADB_INSTALL_TIMEOUT="${ADB_INSTALL_TIMEOUT:-300}"   # a ~100 MB apk over USB
ADB_QUICK_TIMEOUT="${ADB_QUICK_TIMEOUT:-30}"        # a pref read, a force-stop

# THE FLOOR (dispatchdoctor1017, #938-adjacent owner word 2026-10-13): a push
# that stages a missing title never leaves less than this much free on the
# device's games card. Never touched to make the push fit; a push that would
# cross it fails, after make_room_for_push has already tried to clear owned,
# verified-elsewhere-safe ISOs out of the way. Overridable, like every other
# constant in this file, so a selftest fixture can work in kilobytes.
FREE_FLOOR_BYTES="${FREE_FLOOR_BYTES:-$((25 * 1024 * 1024 * 1024))}"
adb_error() {   # <what failed> -> the ERROR line, naming a hung call if any
    if [ -s "${ADB_HUNG_FILE:-}" ]; then
        echo "$1: adb hung -- $(head -1 "$ADB_HUNG_FILE")"
    else
        echo "$1"
    fi
}

# dispatchdoctor1017 Section 2 (owner, 2026-10-17: "it should troubleshoot
# and resolve launch failures ... not just be a script"). Called AFTER
# $rdir/ERROR and $rdir/request.json are both written, at the small set of
# ERROR sites below that are a real failure rather than a deliberate
# hdd.refused/profile.refused safety stop (those keep going straight to
# `return 0`, untouched -- lane.profilegate1011's gate in particular is not
# this lane's to alter). dispatch_doctor.sh's own classify() is the real
# filter: most of what reaches here is still not a class it recognises, and
# it gives up with no model call at all in that case, so calling this at a
# handful of sites costs nothing on the ones it declines.
#
# On a `retry` verdict, requeues the SAME id once, exactly the way the one
# WSL-interop requeue below already does (never a new id): the claimed
# result dir is moved aside so the retry gets a clean one, and the request
# (now carrying doctor_requeued, so dispatch_doctor.sh's cap sees this id
# already has a logs/dispatch-doctor.tsv row and never runs a second
# session on it) goes back into $D/queue/$id.req for the main loop's next
# claim to pick up.
#
# `[ -f ]`, not `[ -x ]`: the doctor is run as `bash "$ddt"`, so its exec bit
# means nothing -- and as Section 2 was first committed (mode 644) an `-x`
# guard silently turned the doctor off everywhere. A request.json with no
# body is skipped with no ERROR line: every lever the doctor has (push-iso,
# attach-route, restore-profile) and the brief it reads start from the
# request's own title/title_id, so an empty one leaves it nothing to act on.
# (In practice that is only 99-iso-roots.sh's extracted-block fixture, whose
# ERROR must end exactly with device_title_miss's text.)
maybe_run_doctor() {   # <id> <rdir>
    local id="$1" rdir="$2" ddt="$HERE/dispatch_doctor.sh" out verdict aside
    [ -f "$ddt" ] || return 0
    [ -s "$rdir/request.json" ] || return 0
    out=$(bash "$ddt" diagnose "$id" "$rdir" 2>>"$D/logs/dispatcher.log")
    verdict=$(printf '%s\n' "$out" | sed -n 's/^VERDICT //p' | tail -1)
    log "  DOCTOR: ${verdict:-no verdict}"
    # Section 3 (owner 10-17, "no longer silent"): the ERROR a human reads
    # says whether the doctor ran and what it decided, not just the original
    # failure. Appended here, before a retry moves the dir aside, so the
    # line travels with the result wherever it ends up.
    if [ -f "$rdir/ERROR" ]; then
        printf 'doctor: %s%s\n' "${verdict:-no verdict}" \
            "$([ -f "$rdir/doctor.md" ] && echo ' (see doctor.md)')" >> "$rdir/ERROR"
    fi
    [ "$verdict" = retry ] || return 0
    python3 -c 'import json, sys, time
r = json.load(open(sys.argv[1]))
r["doctor_requeued"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(r, open(sys.argv[2], "w"), indent=2)' \
        "$rdir/request.json" "$D/queue/$id.req" 2>>"$D/logs/dispatcher.log" || return 0
    aside="$rdir.doctor1"
    [ -e "$aside" ] && aside="$rdir.doctor1.$(date +%s)"
    mv "$rdir" "$aside"
    rm -f "$D/running/$id.owner"
    log "  DOCTOR: fix applied, requeued once as $id (attempt kept at $aside)"
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
            local f="$rdir/frames/$(printf 'f%05d' "$n").png"
            # exec-out, not `shell`, so the PNG is not mangled by the tty line
            # discipline -- `adb shell screencap -p` corrupts every 0x0a on
            # some transports and the file opens as a truncated image.
            timeout 30 adb -s "$SERIAL" exec-out screencap -p > "$f" 2>/dev/null
            # An empty or tiny file is a failed capture, not a black frame.
            # Delete it: a 0-byte PNG in a frame set is an image tool's crash
            # later on, and a count that includes it is a lie about coverage.
            if [ -s "$f" ]; then
                # THE DEVICE CLOCK, not the host's: hitch_report.py's mark
                # comes from a logcat line stamped by the device (#433
                # Addendum 1), and the host clock on this machine steps
                # backward periodically and cannot be trusted to agree with
                # it. One extra cheap call per frame, appended to a sidecar
                # so the f%05d names stay what every reader already cites.
                local devt; devt=$(timeout "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell date +%H:%M:%S 2>/dev/null | tr -d '\r\n')
                [ -n "$devt" ] && printf '%s\t%s\n' "$(basename "$f")" "$devt" >> "$rdir/frames/index.tsv"
            else
                rm -f "$f"
            fi
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

# start_soak_video / stop_soak_video: a video of the screen during a soak,
# the way start_frame_capture gives one screencap every N seconds -- for the
# class of defect a still only catches by luck (#433, lane.soakvideo1011; see
# the "Why" table in docs/lanes/soakvideo1011/NOTES.md). OPT-IN for the same
# cost reason frames are: `video` goes into result.json whether it ran or
# not, so a reader pooling a video soak with a clean one has to see it.
#
# <rdir>/video/.stop IS THE ONLY SIGNAL stop_soak_video has to the background
# loop below, and it is host-side, never on the device: the brief's rule is
# no device write but the temporary hakux_vid_*.mp4 files, which rules out a
# remote marker (a PID file) for coordinating the stop. The loop checks it at
# every wait point -- the mark wait, the `after` wait, between segments -- so
# an external stop is noticed within about a second from any of them.
#
# STOPPING `screenrecord` EARLY NEEDS A SIGNAL TO THE REMOTE PROCESS, NOT THE
# LOCAL `adb` CLIENT. `adb shell screenrecord ...` run non-interactively (no
# pty, which is what a backgrounded non-tty call is) does not reliably
# forward a signal delivered to the local adb process across to the remote
# command -- that forwarding is a pty behaviour (interactive `adb shell`,
# Ctrl-C). `adb shell pkill -2 screenrecord` sends SIGINT directly to the
# remote process instead: no new device file, and it is the documented way
# to stop `screenrecord` so it finalizes its `moov` atom and the mp4 plays,
# rather than leaving a container a reader cannot open. (GNU `timeout`, which
# wraps the local call below so a hung adb cannot wedge the loop, does
# forward an externally-delivered SIGINT to ITS child -- verified separately
# -- but that signal is never used here: the remote stop is this independent
# `pkill` call, not a signal to the `timeout` wrapper.)
# mark_wall / start_wall are read from the DEVICE clock (#433 Addendum 1),
# the same one the hakuX-route mark line and frames/index.tsv are on, so a
# moment in the video lines up with the stills and logcat without any
# host/device conversion -- and so the host clock's periodic backward step
# (docs/lanes/soakvideo1011/NOTES.md) cannot put a segment's own start
# before its predecessor's.
# Retried: a single adb flake here must not read as "the mark never came"
# (see docs/testing/jobs/selftest.d and the device-run-flakes lesson).
_device_epoch() {
    local t try
    for try in 1 2 3; do
        t=$(timeout "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell date +%s 2>/dev/null | tr -dc 0-9)
        [ -n "$t" ] && { printf '%s' "$t"; return 0; }
    done
    return 1
}
# _device_clock: HH:MM:SS.mmm on the device clock, matching the format
# score2.py's rt-down argument expects (captures/fpsnext1019/scripts/arm.sh's
# own DT0/DTR1) -- NOT the epoch integer _device_epoch returns above, and not
# the host clock (it steps back ~31s periodically; hub-devices.md).
_device_clock() {
    local t try
    for try in 1 2 3; do
        t=$(timeout "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell 'date +%H:%M:%S.%N' 2>/dev/null | tr -d '\r\n' | cut -c1-12)
        [ -n "$t" ] && { printf '%s' "$t"; return 0; }
    done
    return 1
}
VIDEO_PID=""
VIDEO_RDIR=""
_soak_video_meta() {   # <rdir> <seconds> <after> <mark_wall|""> <skip reason|"">
    python3 - "$1" "$2" "$3" "$4" "$5" <<'PYEOF'
import json, sys
rdir, secs, after, mark_wall, reason = sys.argv[1:6]
d = dict(seconds=int(secs), after=int(after),
          mark_wall=(float(mark_wall) if mark_wall else None),
          segments=[], bytes=0)
if reason:
    d["skipped"] = reason
json.dump(d, open(rdir + "/video/meta.json", "w"), indent=2)
PYEOF
}
start_soak_video() {   # <rdir> <seconds> <after> <has-route 0|1> <hold-seconds>
    local rdir="$1" secs="$2" after="$3" has_route="$4" hold="$5"
    VIDEO_PID=""; VIDEO_RDIR="$rdir"
    mkdir -p "$rdir/video"
    rm -f "$rdir/video/.stop"
    # Cleared before the first segment too (not only at stop), so a run that
    # crashed mid-recording cannot leave files on the device for long.
    timeout "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell "rm -f /sdcard/Download/hakux_vid_*.mp4" >/dev/null 2>&1
    if ! [ "${secs:-0}" -gt 0 ] 2>/dev/null; then
        _soak_video_meta "$rdir" 0 "$after" "" "off"
        return 0
    fi
    (
        local waited=0 mark_wall="" mark_seen=0
        if [ "$has_route" = 1 ]; then
            # The route player writes "ROUTE HH:MM:SS.mmm mark <name>" to
            # run.log (titles/route.sh's log(), the "mark" step). Watched
            # here, not in logcat, because this is the same file the
            # dispatcher is already writing the soak into.
            while [ "$waited" -lt "$hold" ]; do
                [ -f "$rdir/video/.stop" ] && break
                if grep -q ' mark ' "$rdir/run.log" 2>/dev/null; then
                    mark_seen=1; mark_wall=$(_device_epoch); break
                fi
                sleep 1; waited=$((waited + 1))
            done
        else
            mark_seen=1; mark_wall=$(_device_epoch)
        fi
        if [ -z "$mark_wall" ]; then
            if [ "$mark_seen" = 1 ]; then
                _soak_video_meta "$rdir" "$secs" "$after" "" "mark seen, but the device clock could not be read"
            else
                _soak_video_meta "$rdir" "$secs" "$after" "" "no mark line seen in run.log before the soak ended"
            fi
            exit 0
        fi
        local a=0
        while [ "$a" -lt "$after" ]; do
            [ -f "$rdir/video/.stop" ] && break
            sleep 1; a=$((a + 1))
        done
        if [ -f "$rdir/video/.stop" ]; then
            _soak_video_meta "$rdir" "$secs" "$after" "$mark_wall" "stopped before recording started"
            exit 0
        fi
        local seg="${HAKUX_SOAK_VIDEO_SEG:-60}"
        # screenrecord v1.3's own per-call maximum (brief, and the Nova's).
        [ "$seg" -gt 180 ] && seg=180
        local remaining="$secs" k=0 pull_pid="" segs="$rdir/video/.segs"
        : > "$segs"
        while [ "$remaining" -gt 0 ]; do
            [ -f "$rdir/video/.stop" ] && break
            k=$((k + 1))
            local this="$seg"
            [ "$this" -gt "$remaining" ] && this="$remaining"
            local remote="/sdcard/Download/hakux_vid_${k}.mp4"
            local start_wall; start_wall=$(_device_epoch)
            # Blocks until the segment's own time-limit elapses, OR until
            # stop_soak_video's `pkill -2 screenrecord` reaches the device --
            # either way screenrecord has already finalized the file by the
            # time this returns.
            timeout $((this + 30)) adb -s "$SERIAL" shell screenrecord --time-limit "$this" --bit-rate 10000000 "$remote" >/dev/null 2>&1
            # Segment k+1 starts as soon as k's recording ends; k's pull runs
            # in the background so the gap between segments stays short. The
            # PREVIOUS segment's pull is waited on here (not at loop end
            # only), so a pull never overlaps the next segment's own pull.
            [ -n "$pull_pid" ] && wait "$pull_pid" 2>/dev/null
            (
                local v="$rdir/video/$(printf 'v%05d.mp4' "$k")"
                local rsize; rsize=$(timeout "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell "stat -c %s '$remote' 2>/dev/null" 2>/dev/null | tr -d '\r\n')
                timeout 120 adb -s "$SERIAL" pull "$remote" "$v" >/dev/null 2>&1
                local lsize; lsize=$(stat -c %s "$v" 2>/dev/null || echo -1)
                # Deleted only once the pull is verified by size -- the
                # pull-verify lesson (58-pull-verify.sh) applies here too.
                if [ -n "$rsize" ] && [ "$lsize" != -1 ] && [ "$rsize" = "$lsize" ]; then
                    timeout "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell rm -f "$remote" >/dev/null 2>&1
                fi
                printf '%s\t%s\t%s\n' "$(basename "$v")" "$start_wall" "$lsize" >> "$segs"
            ) &
            pull_pid=$!
            remaining=$((remaining - this))
        done
        [ -n "$pull_pid" ] && wait "$pull_pid" 2>/dev/null
        python3 - "$rdir" "$secs" "$after" "$mark_wall" <<'PYEOF'
import json, os, sys
rdir, secs, after, mark_wall = sys.argv[1:5]
segs, p = [], rdir + "/video/.segs"
if os.path.exists(p):
    for line in open(p):
        f, sw, sz = line.rstrip("\n").split("\t")
        sz = int(sz) if sz not in ("", "-1") else 0
        segs.append(dict(file=f, start_wall=float(sw), bytes=sz))
    os.remove(p)
json.dump(dict(seconds=int(secs), after=int(after), mark_wall=float(mark_wall),
               segments=segs, bytes=sum(s["bytes"] for s in segs)),
          open(rdir + "/video/meta.json", "w"), indent=2)
PYEOF
    ) &
    VIDEO_PID=$!
}
stop_soak_video() {
    [ -n "$VIDEO_PID" ] || return 0
    : > "$VIDEO_RDIR/video/.stop" 2>/dev/null
    timeout "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell pkill -2 screenrecord >/dev/null 2>&1
    wait "$VIDEO_PID" 2>/dev/null
    VIDEO_PID=""
    # Unconditionally, like the clear at start: an early exit must not leave
    # a segment's temporary file on the device.
    timeout "$ADB_QUICK_TIMEOUT" adb -s "$SERIAL" shell "rm -f /sdcard/Download/hakux_vid_*.mp4" >/dev/null 2>&1
}

# write_route_refs <rdir> <req>: materialize the route's reference crops
# (request.sh --route; "route_refs" in the request, each value base64 PNG
# bytes keyed by "<name>.png") at <rdir>/refs/route.txt/<name>.png -- the
# path route.sh's ref_path() resolves a `waitfor`/`press-until` step against
# when it plays <rdir>/route.txt. Addendum 3, #433: before this, nothing
# wrote that directory, so a route naming a crop could be queued (request.sh
# checked the crop existed next to the route) but never played one -- the
# worker's route.sh found no reference, failed its first waitfor/press-until
# line, and the soak ran on with no input (castlevania-cod.first-run and
# every other route with a crop, lane.nfsroute1011's included).
# No "/" or ".." escapes this directory: a name failing
# [A-Za-z0-9._-]+\.png is refused (stdout, exit 1), before any file is
# written for this call -- a function so a selftest can call it directly.
write_route_refs() {   # <rdir> <req>
    local rdir="$1" req="$2"
    python3 -c '
import base64, json, os, re, sys
rdir, req = sys.argv[1], sys.argv[2]
refs = json.load(open(req)).get("route_refs") or {}
if not refs:
    raise SystemExit(0)
name_re = re.compile(r"^[A-Za-z0-9._-]+\.png$")
for name in refs:
    if not name_re.match(name):
        print("route_refs: refused name %r (must be [A-Za-z0-9._-]+.png)" % name)
        raise SystemExit(1)
outdir = os.path.join(rdir, "refs", "route.txt")
os.makedirs(outdir, exist_ok=True)
for name, b64 in refs.items():
    open(os.path.join(outdir, name), "wb").write(base64.b64decode(b64))
' "$rdir" "$req"
}

env_pref_marker() { echo "$D/.env_pref.${DEVICE_LABEL:-$SERIAL}"; }

# A NEW APK STARTS WITH NO SHADER CACHE, per device.
#
# The app wipes its Vulkan caches only when the driver identity, a struct
# size or SHADER_STATE_LAYOUT_VERSION changes (check_driver_identity_and_
# wipe_caches, vk/renderer.c). A build that adds an ENUM VALUE changes none
# of those. #235's fix arm persisted geometry-shader keys carrying
# PRIM_TYPE_TRIANGLES_ADJACENCY into shader_module_keys.bin on both
# handhelds; the next master build regenerated them at startup and aborted
# at geom.c:240, which voided two runs of somebody else's work. The host
# bumped the version for that one case; the next lane to add an enum value
# does it again.
#
# So the dispatcher clears the three paths the app itself clears (filesDir:
# spv_cache/, vk_pipeline_cache.bin, shader_module_keys.bin) whenever the apk
# it just installed differs from the one the previous run on THIS device
# used. Not before every run: a same-apk run keeps its warm cache, because
# soaks price frame rate and shader warm-up would land in their first minute.
# The last apk is recorded per device only after a successful clear, so a
# failed clear is retried next time. SHADER_CACHE_STATE goes into result.json.
shader_apk_marker() { echo "$D/.shader_cache_apk.${DEVICE_LABEL:-$SERIAL}"; }
clear_shader_caches_on_apk_change() {   # <apk sha>
    local sha="$1" last pkg="${PKG:-com.jreinach.hakux.debug}"
    last=$(cat "$(shader_apk_marker)" 2>/dev/null)
    if [ "$last" = "$sha" ]; then
        export SHADER_CACHE_STATE="kept: same apk as this device's previous run"
        return 0
    fi
    adb_call "$ADB_QUICK_TIMEOUT" "am force-stop (shader cache)" shell am force-stop "$pkg" >/dev/null 2>&1
    if ! adb_call "$ADB_QUICK_TIMEOUT" "run-as rm shader caches" \
            shell "run-as $pkg rm -rf files/spv_cache files/vk_pipeline_cache.bin files/shader_module_keys.bin" \
            >/dev/null 2>&1; then
        log "  SHADER CACHE: could not clear for apk $sha (previous ${last:-none})"
        return 1
    fi
    printf '%s\n' "$sha" > "$(shader_apk_marker)"
    export SHADER_CACHE_STATE="cleared: apk ${last:-unrecorded} -> $sha on this device"
    log "  shader cache $SHADER_CACHE_STATE"
}

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
    adb_call "$ADB_QUICK_TIMEOUT" "am force-stop (env pref)" shell am force-stop "$pkg" >/dev/null 2>&1
    tmp="$D/.prefs.${DEVICE_LABEL:-$SERIAL}.xml"
    adb_call "$ADB_QUICK_TIMEOUT" "run-as cat x1box_prefs.xml" \
        shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" \
        2>/dev/null | tr -d '\r' > "$tmp"
    # A HUNG device is not an unreadable file. The clearing branch below drops
    # its marker on an unreadable file, which is right for a run-as that
    # refuses and wrong for a call that never answered: the env would be left
    # on the device with nothing remembering to take it off.
    if [ -s "${ADB_HUNG_FILE:-}" ]; then
        log "  ENV: adb hung ($(head -1 "$ADB_HUNG_FILE")); marker kept"
        return 1
    fi
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
    adb_call "$ADB_QUICK_TIMEOUT" "run-as write x1box_prefs.xml" --in "$tmp" \
        shell "run-as $pkg sh -c 'cat > shared_prefs/x1box_prefs.xml'"
    # VERIFY BY READING BACK. A `cat >` over adb can truncate, and the failure
    # mode of a silently-unwritten pref is a run that measures the other arm.
    # Via a FILE and a quoted heredoc, not `python3 -c "..."`. The source below
    # is full of quotes, backslashes and an `&`, and a shell string is the
    # wrong container for any of them -- the same mistake that was running the
    # shell over the disc_id block's comments a few hundred lines down.
    adb_call "$ADB_QUICK_TIMEOUT" "run-as read back x1box_prefs.xml" \
        shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" \
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

# TITLE RUNS BOOT A TITLES DISK; DISC RUNS KEEP hdd.img.
#
# Until 2026-09-29 every soak and every nxdk disc run shared the one
# files/x1box/hdd.img on each handheld. Title saves, the titles' X:/Y:/Z:
# utility caches and the discs' E:\nxdk_* output all piled onto it and nothing
# ever took anything off: the Thor's reached 6.9 GB of its 8 GiB, and a
# Crimson Skies soak's "gameplay" frames were the title's "not enough free
# blocks to save games" dialog (#474). The real saves on it were a few MB.
#
# So a title run points `hddPath` at files/x1box/titles.qcow2, a disk the
# host builds from its save store (titles/titlestate.py, docs/lanes/
# titlestate/NOTES.md), and every other run leaves `hddPath` on hdd.img -- a
# disc run no longer assumes that, it makes it so (disc_hdd_prepare, below).
# titlestate.py `plan` decides what happens to the titles disk before a run
# (seed / harvest / build / keep); after the run the disk is pulled and its
# saves harvested, so the store stays the truth and a rebuild loses nothing.
#
# The pref follows the env_vars rule: we undo only what we did. A marker
# holds the hddPath we found; it is put back after the title run, and at the
# start of any request that finds the marker still there (a worker that died
# mid-run). No marker: not one adb call.
#
# HAKUX_TITLES_DISK=0 on the worker turns the split off: title runs boot
# hdd.img as they did before. A request's own env HAKUX_TITLES_DISK (request.sh
# --env) beats the worker's, either way: the switch lives in the worker's
# environment, which a request cannot reach, and a proof run of the split must
# be able to turn it on for itself alone while it stays off for everyone else.
#
# THE DISK MUST BE MODE 660. The app reaches files in its x1box directory
# through a group, and `adb push` leaves them 0644: the app can read the disk
# but not open it read-write. xemu's own check (xemu_check_file, system/vl.c)
# only opens it "rb", so the -drive is added, qemu's configure_blockdev then
# fails "Could not open ...: Permission denied" and exit()s on the qemu thread
# while the render thread holds GL, and the process dies in the GPU driver:
# SIGSEGV in libGLESv2_adreno.so or "pthread_mutex_lock called on a destroyed
# mutex", 2-7 ms after sdl2_display_early_init, before stderr reaches logcat.
# Every title run on #622's first pushed disks died that way (lane.hddcrash,
# docs/lanes/hddcrash/NOTES.md). dev_push sets the mode before the rename, and
# titles_disk_prepare checks it before every title run, so a disk pushed
# before this fix is repaired rather than booted.
TITLESTATE="$HERE/titles/titlestate.py"
SAVES_PY="$HERE/titles/saves.py"
# saves.py loads tools/make_xbox_hdd.py, which is not under docs/testing and so
# not in the snapshot: name the tree's copy.
export MAKE_XBOX_HDD="${MAKE_XBOX_HDD:-$TREE/tools/make_xbox_hdd.py}"
export TITLESTATE_DIR="${TITLESTATE_DIR:-$D/titlestate}"
x1box_dir() { echo "/storage/emulated/0/Android/data/${PKG:-com.jreinach.hakux.debug}/files/x1box"; }
hdd_pref_marker() { echo "$D/.hdd_pref.${DEVICE_LABEL:-$SERIAL}"; }

# hdd_pref_edit get|set <file> [value]: the one key, every other byte kept.
# An empty value removes the key.
hdd_pref_edit() {
    python3 - "$@" <<'PYHDD'
import re, sys
mode, path = sys.argv[1], sys.argv[2]
s = open(path, errors="replace").read()
pat = r'\n?[ \t]*<string name="hddPath">(.*?)</string>'
if mode == "get":
    m = re.search(pat, s, re.S)
    v = m.group(1) if m else ""
    sys.stdout.write(v.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&"))
    sys.exit(0)
want = sys.argv[3]
if "</map>" not in s:
    sys.exit("prefs file has no </map>; refusing to write")
esc = want.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
key = r'(<string name="hddPath">)(.*?)(</string>)'
if want and re.search(key, s, re.S):
    # In place, so a restore puts the file back byte for byte.
    s = re.sub(key, lambda m: m.group(1) + esc + m.group(3), s, count=1, flags=re.S)
else:
    s = re.sub(pat, "", s, flags=re.S)
    if want:
        s = s.replace("</map>", '    <string name="hddPath">%s</string>\n</map>' % esc)
open(path, "w").write(s)
PYHDD
}

# hdd_pref_fetch <file>: the app's x1box_prefs.xml, as it is on the device
# now, written to <file>. Exit 1 when it could not be read (no run-as, a hung
# call). The one read set_hdd_pref and hdd_pref_point both start from.
hdd_pref_fetch() {
    local pkg="${PKG:-com.jreinach.hakux.debug}" out="$1"
    adb_call "$ADB_QUICK_TIMEOUT" "run-as cat x1box_prefs.xml (hdd)" \
        shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" 2>/dev/null | tr -d '\r' > "$out"
    if [ -s "${ADB_HUNG_FILE:-}" ] || [ ! -s "$out" ]; then
        return 1
    fi
}

# set_hdd_pref <path> [marker] ; echoes the hddPath it replaced. Verified by
# reading back. With a marker, the value to put back is recorded there BEFORE
# the write (unless a marker is already there): a write that lands and a
# read-back that hangs, or a worker that dies between them, must still leave
# restore_hdd_pref something to restore. Never records the titles disk as the
# original -- that would make it permanent -- but hdd.img in its place.
set_hdd_pref() {
    local want="$1" marker="${2:-}" pkg tmp was back
    pkg="${PKG:-com.jreinach.hakux.debug}"
    tmp="$D/.prefs.${DEVICE_LABEL:-$SERIAL}.hdd.xml"
    adb_call "$ADB_QUICK_TIMEOUT" "am force-stop (hdd pref)" shell am force-stop "$pkg" >/dev/null 2>&1
    if ! hdd_pref_fetch "$tmp"; then
        log "  HDD PREF: cannot read x1box_prefs.xml"; return 1
    fi
    was=$(hdd_pref_edit get "$tmp")
    if [ -n "$marker" ] && [ ! -f "$marker" ]; then
        [ "$was" = "$(x1box_dir)/titles.qcow2" ] && was="$(x1box_dir)/hdd.img"
        printf '%s' "$was" > "$marker" || { log "  HDD PREF: cannot write $marker"; return 1; }
    fi
    hdd_pref_edit set "$tmp" "$want" || return 1
    adb_call "$ADB_QUICK_TIMEOUT" "run-as write x1box_prefs.xml (hdd)" --in "$tmp" \
        shell "run-as $pkg sh -c 'cat > shared_prefs/x1box_prefs.xml'" >/dev/null 2>&1
    adb_call "$ADB_QUICK_TIMEOUT" "run-as read back x1box_prefs.xml (hdd)" \
        shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" 2>/dev/null | tr -d '\r' > "$tmp.back"
    back=$(hdd_pref_edit get "$tmp.back")
    if [ "$back" != "$want" ]; then
        log "  HDD PREF: wrote hddPath=$want but read back '$back'"; return 1
    fi
    printf '%s' "$was"
}

# restore_hdd_pref: put back the hddPath a title run replaced, if one did.
restore_hdd_pref() {
    local marker; marker="$(hdd_pref_marker)"
    [ -f "$marker" ] || return 0
    local orig; orig=$(cat "$marker")
    # A marker written before set_hdd_pref refused this value names the titles
    # disk; put the discs' disk back instead.
    [ "$orig" = "$(x1box_dir)/titles.qcow2" ] && orig="$(x1box_dir)/hdd.img"
    set_hdd_pref "$orig" >/dev/null || return 1
    rm -f "$marker"
    log "  hddPath restored to ${orig:-(unset)}"
}

# A DISC RUN BOOTS hdd.img, WHATEVER hddPath SAYS (suitesha1022).
#
# "Every other run leaves hddPath on hdd.img" was a sentence, not a check. The
# owner points hddPath at their own image to play (hdd-owner-1018.img, GTA III
# and its save states) and nothing puts it back: every pgraph disc run on the
# Nova from 10-19 booted that image, wrote its e:/d<hash> output dir into it,
# and run_disc.sh then pulled hdd.img, found no such dir, and the extractor
# said "d98f15f not found". 0 captures from a clean 225 s run, and the doctor
# read it as a host-side lookup.
#
# So a disc run does for itself what a title run does for the titles disk: if
# hddPath is not hdd.img, set_hdd_pref points it there with the one marker, and
# restore_hdd_pref puts back exactly what was there, afterwards or, for a
# worker that died, at the start of the next request. The owner's path comes
# back unchanged and the owner's image is never opened, copied, pushed over or
# removed by this: only the pref moves. A pref that is already hdd.img costs one
# read and no write and leaves no marker.
#
# THE MARKER IS SHARED WITH TITLE RUNS and that is safe because set_hdd_pref
# never overwrites one: a request restores at its start (serve_one), so by the
# time either kind of run sets the pref the marker is gone and its own original
# is the one recorded. A title run that died leaves the owner's path in the
# marker; the next request, disc or title, puts it back first.
#
# hdd_pref_point <json> <want>: point hddPath at <want> for one run, the one
# way a disc run and a scene run both do it. Sets HDD_POINT_ACTION (kept: it
# already named <want>, no write and no marker; set: moved, the original is in
# the marker; failed: could not be moved; unread: the prefs file could not be
# read) and HDD_POINT_WAS (what it named), and writes them to <json> with
# "restored": null for hdd_pref_after to fill in.
HDD_POINT_ACTION=""; HDD_POINT_WAS=""
hdd_pref_point() {
    local json="$1" want="$2" tmp
    tmp="$D/.prefs.${DEVICE_LABEL:-$SERIAL}.hdd.point.xml"
    HDD_POINT_ACTION=""; HDD_POINT_WAS=""
    if ! hdd_pref_fetch "$tmp"; then
        HDD_POINT_ACTION=unread
    else
        HDD_POINT_WAS=$(hdd_pref_edit get "$tmp")
        if [ "$HDD_POINT_WAS" = "$want" ]; then
            HDD_POINT_ACTION=kept
        elif set_hdd_pref "$want" "$(hdd_pref_marker)" >/dev/null; then
            HDD_POINT_ACTION=set
        else
            HDD_POINT_ACTION=failed
        fi
    fi
    python3 - "$json" "$HDD_POINT_ACTION" "$HDD_POINT_WAS" "$want" <<'PYHDD'
import json, sys
out, action, was, want = sys.argv[1:5]
json.dump({"action": action, "was": was, "want": want, "restored": None}, open(out, "w"), indent=1)
PYHDD
}

# hdd_pref_after <json>: put hddPath back if hdd_pref_point moved it, and say
# so in <json>. A failure leaves the marker, and the next request's restore
# retries.
hdd_pref_after() {
    local json="$1" ok=true
    [ -f "$(hdd_pref_marker)" ] || return 0
    restore_hdd_pref || { ok=false; log "  WARNING: hddPath not restored after the run; the next request retries"; }
    python3 - "$json" "$ok" <<'PYHDD' 2>/dev/null
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["restored"] = sys.argv[2] == "true"
json.dump(d, open(p, "w"), indent=1)
PYHDD
    return 0
}

# disc_hdd_prepare <rdir>: 0 = go ahead, 1 = hddPath is another image and could
# not be moved (DISC_HDD_WAS says what it names); a disc must not run on it.
# An unreadable prefs file is not a refusal (a release package has no run-as):
# run_disc.sh reads the disk the guest actually booted from its own logcat, and
# that is the guard then. Writes <rdir>/hdd_disc.json.
DISC_HDD_WAS=""
disc_hdd_prepare() {
    local rdir="$1"
    hdd_pref_point "$rdir/hdd_disc.json" "$(x1box_dir)/hdd.img"
    DISC_HDD_WAS="$HDD_POINT_WAS"
    case "$HDD_POINT_ACTION" in
        unread) log "  HDD PREF: cannot read x1box_prefs.xml; only run_disc.sh's check of the guest's own log guards this run's disk";;
        set) log "  HDD PREF: disc run boots hdd.img (hddPath was ${DISC_HDD_WAS:-(unset)}; put back afterwards)";;
    esac
    [ "$HDD_POINT_ACTION" != failed ]
}

# disc_hdd_after <rdir>: put hddPath back if disc_hdd_prepare moved it.
disc_hdd_after() { hdd_pref_after "$1/hdd_disc.json"; }

# LOAD A SAVE STATE WITHOUT DRIVING THE PAUSE MENU (#433, lane.savestate-req1019).
#
# request.sh --load-state/--scene names a slot (0-9, 10=auto) and, for a host
# file, a .hxs to push into it. hxs_newest_loadable() (android native) picks
# by the FILE'S OWN saved_at metadata, not by push time or mtime -- so the
# only way to force auto-load to pick a given slot is to make every other
# slot file in states/<title_id>/ absent from the directory for the run, by
# parking it (rename to NAME.hld), never by overwriting or deleting it. The
# target slot's own prior contents are likewise parked, not clobbered, so
# restore_scene_pref can put everything back byte for byte -- same contract
# as restore_hdd_pref, extended from one pref value to a set of files.
#
# savestate_auto_load is a boolean SharedPreference, same prefs file as
# hddPath (shared_prefs/x1box_prefs.xml, internal storage: needs run-as).
# The state files themselves live under x1box_dir(), external storage, app-
# specific but shell-accessible -- dev_push/dev_pull/dev_sha256 already reach
# them with plain `adb shell`, no run-as (confirmed by reading those
# functions; the save-state dir is not shared_prefs).
scene_state_dir() { echo "$(x1box_dir)/states/$1"; }   # <title_id hex>

hxs_slot_name() {   # <slot 0-9|10|auto>
    case "$1" in
        10|auto) echo auto.hxs;;
        [0-9]) echo "slot$1.hxs";;
        *) echo "";;
    esac
}

scene_pref_marker() { echo "$D/.scene_pref.${DEVICE_LABEL:-$SERIAL}"; }
scene_files_marker() { echo "$D/.scene_files.${DEVICE_LABEL:-$SERIAL}"; }

# savestate_pref_edit get|set <file> [0|1]: same one-key-kept shape as
# hdd_pref_edit, for the savestate_auto_load boolean instead of hddPath.
savestate_pref_edit() {
    python3 - "$@" <<'PYSS'
import re, sys
mode, path = sys.argv[1], sys.argv[2]
s = open(path, errors="replace").read()
if mode == "get":
    m = re.search(r'<boolean name="savestate_auto_load" value="(true|false)"', s)
    sys.stdout.write(m.group(1) if m else "false")
    sys.exit(0)
want = "true" if sys.argv[3] == "1" else "false"
if "</map>" not in s:
    sys.exit("prefs file has no </map>; refusing to write")
key = r'(<boolean name="savestate_auto_load" value=")(?:true|false)("\s*/>)'
if re.search(key, s):
    s = re.sub(key, lambda m: m.group(1) + want + m.group(2), s, count=1)
else:
    s = s.replace("</map>", '    <boolean name="savestate_auto_load" value="%s" />\n</map>' % want)
open(path, "w").write(s)
PYSS
}

# set_savestate_pref <0|1> [marker]; echoes the previous value (true/false).
# Same snapshot-before/write/verify-readback shape as set_hdd_pref.
set_savestate_pref() {
    local want="$1" marker="${2:-}" pkg tmp was back want_s
    pkg="${PKG:-com.jreinach.hakux.debug}"
    tmp="$D/.prefs.${DEVICE_LABEL:-$SERIAL}.ss.xml"
    adb_call "$ADB_QUICK_TIMEOUT" "am force-stop (savestate pref)" shell am force-stop "$pkg" >/dev/null 2>&1
    adb_call "$ADB_QUICK_TIMEOUT" "run-as cat x1box_prefs.xml (savestate)" \
        shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" 2>/dev/null | tr -d '\r' > "$tmp"
    if [ -s "${ADB_HUNG_FILE:-}" ] || [ ! -s "$tmp" ]; then
        log "  SAVESTATE PREF: cannot read x1box_prefs.xml"; return 1
    fi
    was=$(savestate_pref_edit get "$tmp")
    if [ -n "$marker" ] && [ ! -f "$marker" ]; then
        printf '%s' "$was" > "$marker" || { log "  SAVESTATE PREF: cannot write $marker"; return 1; }
    fi
    savestate_pref_edit set "$tmp" "$want" || return 1
    adb_call "$ADB_QUICK_TIMEOUT" "run-as write x1box_prefs.xml (savestate)" --in "$tmp" \
        shell "run-as $pkg sh -c 'cat > shared_prefs/x1box_prefs.xml'" >/dev/null 2>&1
    adb_call "$ADB_QUICK_TIMEOUT" "run-as read back x1box_prefs.xml (savestate)" \
        shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" 2>/dev/null | tr -d '\r' > "$tmp.back"
    back=$(savestate_pref_edit get "$tmp.back")
    want_s=$([ "$want" = 1 ] && echo true || echo false)
    if [ "$back" != "$want_s" ]; then
        log "  SAVESTATE PREF: wrote auto_load=$want_s but read back '$back'"; return 1
    fi
    printf '%s' "$was"
}

restore_savestate_pref() {
    local marker; marker="$(scene_pref_marker)"
    [ -f "$marker" ] || return 0
    local orig want
    orig=$(cat "$marker")
    want=0; [ "$orig" = true ] && want=1
    set_savestate_pref "$want" >/dev/null || return 1
    rm -f "$marker"
    log "  savestate_auto_load restored to $orig"
}

# set_scene_pref <req> <rdir> <ttid>: isolate load_slot (request.sh
# --load-state/--scene) on the device -- park every other states/<ttid>/*.hxs
# file, push a host file into the target slot if one was named (backing up
# whatever was already there, sha256-tracked, never overwritten in place),
# and turn savestate_auto_load on for this run only. A no-op when the
# request named no load_slot. Everything needed to reverse this is written
# to scene_files_marker() before any adb mutation after it, so a worker that
# dies partway still leaves restore_scene_pref something to work from.
set_scene_pref() {   # <req> <rdir> <ttid>
    local req="$1" ttid="$3" load_slot want load_file sdir marker list park f pushed=0 backup="" backup_sha=""
    load_slot=$(jq_get "$req" load_slot "")
    [ -n "$load_slot" ] || return 0
    marker="$(scene_files_marker)"
    if [ -f "$marker" ]; then
        log "  SCENE: a stale scene marker from an earlier run; restoring it first"
        restore_scene_pref
    fi
    want="$(hxs_slot_name "$load_slot")"
    [ -n "$want" ] || { log "  SCENE: bad load_slot '$load_slot'"; return 1; }
    load_file=$(jq_get "$req" load_state_file "")
    sdir="$(scene_state_dir "$ttid")"

    list=$(adb_call "$ADB_QUICK_TIMEOUT" "ls $sdir" shell "ls '$sdir' 2>/dev/null")
    if [ -s "${ADB_HUNG_FILE:-}" ]; then
        log "  SCENE: adb hung listing $sdir"; return 1
    fi
    park=$(printf '%s\n' "$list" | tr -d '\r' | grep -E '^(slot[0-9]|auto|undo-save)\.hxs$' | grep -v -x "$want" || true)

    if [ -n "$load_file" ]; then
        if [ "$(dev_bytes "$sdir/$want")" != -1 ]; then
            backup="$want.orig.hld"
            adb_call "$ADB_QUICK_TIMEOUT" "backup $want" shell "cp '$sdir/$want' '$sdir/$backup'" >/dev/null 2>&1 \
                || { log "  SCENE: could not back up $want before pushing a state into it"; return 1; }
            backup_sha=$(dev_sha256 "$sdir/$backup")
        fi
        dev_push "$load_file" "$sdir/$want" || { log "  SCENE: push of $load_file -> $sdir/$want failed"; return 1; }
        pushed=1
    fi

    local parked=()
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        adb_call "$ADB_QUICK_TIMEOUT" "park $f" shell "mv '$sdir/$f' '$sdir/$f.hld'" >/dev/null 2>&1 && parked+=("$f")
    done <<<"$park"

    python3 -c 'import json,sys
json.dump(dict(dir=sys.argv[1], want=sys.argv[2],
               parked=[p for p in sys.argv[3].split(",") if p],
               pushed=bool(int(sys.argv[4])), backup=sys.argv[5], backup_sha=sys.argv[6]),
          open(sys.argv[7], "w"))' \
        "$sdir" "$want" "$(IFS=,; echo "${parked[*]-}")" "$pushed" "$backup" "$backup_sha" "$marker"

    if ! set_savestate_pref 1 "$(scene_pref_marker)" >/dev/null; then
        log "  SCENE: could not set savestate_auto_load=1"; restore_scene_pref; return 1
    fi
    log "  SCENE: slot $load_slot ($want), parked ${#parked[@]} other slot file(s)${load_file:+, pushed $load_file}"
}

# restore_scene_pref: put back whatever set_scene_pref moved aside or
# overwrote, and the savestate_auto_load pref -- unconditionally, on every
# exit from a scene request, success or refusal, exactly like
# restore_hdd_pref. A pushed state's backup is sha256-verified before its
# marker is trusted away.
restore_scene_pref() {
    local marker; marker="$(scene_files_marker)"
    [ -f "$marker" ] || { restore_savestate_pref; return $?; }
    local sdir want pushed backup backup_sha rc=0
    sdir=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["dir"])' "$marker")
    want=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["want"])' "$marker")
    pushed=$(python3 -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["pushed"]))' "$marker")
    backup=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("backup") or "")' "$marker")
    backup_sha=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("backup_sha") or "")' "$marker")
    if [ "$pushed" = 1 ]; then
        if [ -n "$backup" ]; then
            adb_call "$ADB_QUICK_TIMEOUT" "restore $want" shell "mv '$sdir/$backup' '$sdir/$want'" >/dev/null 2>&1 || rc=1
            if [ -n "$backup_sha" ] && [ "$(dev_sha256 "$sdir/$want")" != "$backup_sha" ]; then
                log "  SCENE: restored $want but its sha256 does not match the backup taken before the push"
                rc=1
            fi
        else
            adb_call "$ADB_QUICK_TIMEOUT" "drop pushed $want (had none before)" shell "rm -f '$sdir/$want'" >/dev/null 2>&1 || rc=1
        fi
    fi
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        adb_call "$ADB_QUICK_TIMEOUT" "unpark $f" shell "mv '$sdir/$f.hld' '$sdir/$f'" >/dev/null 2>&1 || rc=1
    done < <(python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1])).get("parked") or []))' "$marker")
    rm -f "$marker"
    restore_savestate_pref || rc=1
    if [ "$rc" = 0 ]; then
        log "  SCENE: restored (slots unparked, pref put back)"
    else
        log "  SCENE: restore had at least one failure; see the lines above"
    fi
    return $rc
}

# A SCENE BOOTS A COPY OF THE DISK ITS STATE WAS SAVED ON (#433).
#
# Every save takes a disk snapshot and names it in the state (hxs.c
# make_disk_snapshot, meta disk_snap), and a load refuses
# disk-snapshot-missing unless the disk booted now holds that snapshot by
# name; then it takes an undo-load snapshot and rolls the disk back to the
# state's (bdrv_all_goto_snapshot). So a load needs the disk the state was
# saved on, and it writes to that disk. A title run's own disk, titles.qcow2,
# is composed from goldens and rebuilt once a run writes to it, so it keeps
# no state's snapshot; on a device with no titles
# registry, or HAKUX_TITLES_DISK=0, the run boots whatever hddPath names,
# which on the Nova is the owner's image: a load there rolls the owner's
# disk back. A byte copy of the qcow2 keeps its internal snapshots, and the
# snapshot names carry the states dir's id, not the disk's path, so a copy
# made with the app stopped loads every state the original does.
#
# So a scene names its disk (scenes.tsv `hdd`, or request.sh --load-hdd): a
# file in x1box_dir(). scene_hdd_check refuses, before the install, a load
# that names none, a name that is the owner's image or a harness disk, and a
# name the device does not have. scene_hdd_prepare points hddPath at it in
# place of titles_disk_prepare, through hdd_pref_point (the disc runs' one
# marker and readback), and scene_hdd_after puts the pref back. The copy is
# the scene's own: a load leaves it rolled back to the state, which is where
# the next load of that state starts anyway.

# scene_hdd_name_refusal <name>: why a scene may not boot <name>, or nothing.
# Lower-cased first: the device's shared storage matches names without case.
scene_hdd_name_refusal() {
    local n="$1" lc="${1,,}"
    case "$n" in
        "") echo "a save-state load names no hdd: a state loads only on a disk holding the snapshot it was saved with, and without one the run boots titles.qcow2 (composed from goldens: no such snapshot, the load VOIDs) or whatever hddPath names (on the Nova the owner's image, which the load would roll back); name a copy of the disk the state was saved on in the scene's scenes.tsv hdd column, or pass --load-hdd <name>"; return;;
        */*) echo "scene hdd '$n' is a path; name a file in the device's x1box dir (where hdd.img is)"; return;;
        .|..|-*|*[!A-Za-z0-9._-]*) echo "scene hdd '$n' is not a plain file name (letters, digits, . _ - only)"; return;;
    esac
    case "$lc" in
        hdd-owner-*) echo "scene hdd '$n' is the owner's image (hdd-owner-*): a load rolls the disk it boots back to the state's snapshot, so a scene boots a copy of that image, never the image itself";;
        titles.qcow2|hdd.img) echo "scene hdd '$n' is a harness disk (other runs rebuild and boot it); name a copy of the disk the state was saved on";;
    esac
}

# scene_hdd_check <req> <rdir>: 0 = no load, or the named disk is there; 3 =
# refused, the reason in <rdir>/scene_hdd.refused; 1 = the device did not
# answer. Run before the install, so a refused scene changes nothing.
scene_hdd_check() {   # <req> <rdir>
    local req="$1" rdir="$2" title load_slot name why p ans
    title=$(jq_get "$req" title "")
    load_slot=$(jq_get "$req" load_slot "")
    name=$(jq_get "$req" scene_hdd "")
    [ -n "$title" ] || return 0
    [ -n "$load_slot$name" ] || return 0
    why=$(scene_hdd_name_refusal "$name")
    if [ -z "$why" ]; then
        p="$(x1box_dir)/$name"
        ans=$(adb_call "$ADB_QUICK_TIMEOUT" "test scene hdd $name" \
            shell "if [ -f '$p' ]; then echo file; elif [ -e '$p' ]; then echo other; else echo none; fi" \
            2>/dev/null | tr -d '\r' | head -1)
        [ -s "${ADB_HUNG_FILE:-}" ] && return 1
        case "$ans" in
            file) return 0;;
            none) why="scene hdd '$name' does not exist on the device ($p); copy the disk the state was saved on there first, with the app stopped";;
            other) why="scene hdd '$name' on the device ($p) is not a file";;
            *) return 1;;
        esac
    fi
    printf '%s\n' "$why" > "$rdir/scene_hdd.refused"
    log "  SCENE HDD: REFUSED: $why"
    return 3
}

# scene_hdd_prepare <rdir> <req>: the title run's disk is the scene's copy.
# Mode 660 first (THE DISK MUST BE MODE 660), then hddPath, so a failure
# leaves the pref alone. Writes <rdir>/hdd_scene.json (hdd_pref_point) and
# <rdir>/hdd.json, the record of the disk the run booted. 0, or 1.
scene_hdd_prepare() {   # <rdir> <req>
    local rdir="$1" req="$2" name want mode0
    name=$(jq_get "$req" scene_hdd "")
    want="$(x1box_dir)/$name"
    mode0=$(dev_mode "$want")
    dev_make_660 "$want" || { log "  SCENE HDD: cannot make $want mode 660"; return 1; }
    hdd_pref_point "$rdir/hdd_scene.json" "$want"
    case "$HDD_POINT_ACTION" in
        kept|set) ;;
        unread) log "  SCENE HDD: cannot read x1box_prefs.xml, so hddPath cannot be pointed at $name; the load must not run on whatever it names"; return 1;;
        *) log "  SCENE HDD: could not point hddPath at $want (it names ${HDD_POINT_WAS:-(unset)})"; return 1;;
    esac
    python3 - "$rdir/hdd.json" "$want" "$name" "$mode0" <<'PYHDD'
import json, sys
out, path, name, mode0 = sys.argv[1:5]
json.dump({"path": path, "split": "off: scene hdd %s" % name, "scene_hdd": name,
           "mode_found": mode0 or None, "mode": "660"}, open(out, "w"), indent=1)
PYHDD
    if [ "$HDD_POINT_ACTION" = kept ]; then
        log "  hddPath already names $want (scene hdd; nothing to put back)"
    else
        log "  hddPath -> $want (scene hdd; was ${HDD_POINT_WAS:-(unset)}, put back afterwards)"
    fi
}

# scene_hdd_after <rdir>: put hddPath back after a scene run, on every exit.
scene_hdd_after() {   # <rdir>
    [ -f "$1/hdd_scene.json" ] || { restore_hdd_pref; return $?; }
    hdd_pref_after "$1/hdd_scene.json"
}

SCENE_WATCH_PID=""
# start_scene_watch <rdir> <req>: runs whenever the request named a
# load_slot, whether or not it also named a hold trigger -- this is what
# enforces "no op=load within 30s is loud, never a silent run" (#433) in
# real time, polling the live logcat while the soak is still running. Only
# once a load is seen and ok=1, and only when hold_trigger named an axis,
# it also presses and holds that axis for the window, logging
# <AXIS>_DOWN/<AXIS>_RELEASED device-clock timestamps in score2.py's own
# input format (captures/fpsnext1019/scripts/arm.sh's DT0/DTR1 -- NOT
# _device_epoch's integer seconds) so an arm script can score the window
# exactly as it would a by-hand run.
start_scene_watch() {   # <rdir> <req>
    local rdir="$1" req="$2" load_slot
    SCENE_WATCH_PID=""
    load_slot=$(jq_get "$req" load_slot "")
    [ -n "$load_slot" ] || return 0
    (
        local log="$rdir/logcat.txt" trig axis secs waited=0 line="" clk
        local timeout="${SCENE_LOAD_TIMEOUT:-30}"
        trig=$(jq_get "$req" hold_trigger "")
        : > "$rdir/rt_hold.log"
        while [ "$waited" -lt "$timeout" ]; do
            line=$(grep -a -m1 '\[savestate\] op=load' "$log" 2>/dev/null)
            [ -n "$line" ] && break
            sleep 1; waited=$((waited+1))
        done
        if [ -z "$line" ]; then
            echo "LOAD_TIMEOUT waited=${waited}s" >> "$rdir/rt_hold.log"
            exit 0
        fi
        if printf '%s' "$line" | grep -q 'ok=1'; then
            echo "LOAD_OK $line" >> "$rdir/rt_hold.log"
        else
            echo "LOAD_REFUSED $line" >> "$rdir/rt_hold.log"
            exit 0
        fi
        [ -n "$trig" ] || exit 0
        axis="${trig%%:*}"; secs="${trig##*:}"
        SERIAL="$SERIAL" bash "$HERE/perf/pad.sh" axis "${axis^^}" max >/dev/null 2>&1
        clk="$(_device_clock)"
        echo "${axis^^}_DOWN $clk" >> "$rdir/rt_hold.log"
        sleep "$secs"
        SERIAL="$SERIAL" bash "$HERE/perf/pad.sh" axis "${axis^^}" min >/dev/null 2>&1
        clk="$(_device_clock)"
        echo "${axis^^}_RELEASED $clk" >> "$rdir/rt_hold.log"
    ) &
    SCENE_WATCH_PID=$!
}
stop_scene_watch() {
    [ -n "${SCENE_WATCH_PID:-}" ] || return 0
    kill "$SCENE_WATCH_PID" 2>/dev/null
    wait "$SCENE_WATCH_PID" 2>/dev/null
    SCENE_WATCH_PID=""
}

# scene_verdict <rdir> <req> <apk sha>: read AFTER the soak has finished, off
# the complete logcat and rt_hold.log -- writes <rdir>/scene.json and, on a
# void, prints the reason. VOID conditions (#433, loud never silent): no
# op=load within 30s (start_scene_watch's own LOAD_TIMEOUT), a refused load
# (ok=0 / LOAD_REFUSED), or any op=save line anywhere in the run. Names which
# build (apk sha) the state loaded, or was refused, under.
scene_verdict() {   # <rdir> <req> <apk sha>
    local rdir="$1" req="$2" apksha="$3" load_slot
    load_slot=$(jq_get "$req" load_slot "")
    [ -n "$load_slot" ] || return 0
    python3 - "$rdir" "$load_slot" "$apksha" <<'PYVOID'
import json, os, re, sys
rdir, slot, apksha = sys.argv[1], sys.argv[2], sys.argv[3]
watch_path = os.path.join(rdir, "rt_hold.log")
watch_text = open(watch_path, errors="replace").read() if os.path.exists(watch_path) else ""
log_path = os.path.join(rdir, "logcat.txt")
try:
    log_text = open(log_path, errors="replace").read()
except OSError:
    log_text = ""
void = None
save_m = re.search(r"\[savestate\] op=save\b.*", log_text)
if save_m:
    void = "a [savestate] op=save line appeared mid-run: %s" % save_m.group(0).strip()[:200]
elif "LOAD_TIMEOUT" in watch_text:
    void = "no [savestate] op=load line within 30s (slot %s, apk %s)" % (slot, apksha or "?")
elif "LOAD_REFUSED" in watch_text:
    rline = next((l for l in watch_text.splitlines() if l.startswith("LOAD_REFUSED")), "")
    void = ("the save state refused to load (slot %s, apk %s): %s"
            % (slot, apksha or "?", rline[len("LOAD_REFUSED "):].strip()))
elif "LOAD_OK" not in watch_text:
    void = "no load window was ever observed (slot %s, apk %s); see rt_hold.log" % (slot, apksha or "?")
rt_down = next((l.split(" ", 1)[1] for l in watch_text.splitlines() if "_DOWN " in l), "")
rt_released = next((l.split(" ", 1)[1] for l in watch_text.splitlines() if "_RELEASED " in l), "")
json.dump(dict(load_slot=slot, apk_sha=apksha, void=void, rt_down=rt_down, rt_released=rt_released,
               rt_hold_log=watch_text.strip().splitlines()),
          open(os.path.join(rdir, "scene.json"), "w"), indent=2)
if void:
    print(void)
PYVOID
}

# A BUILD FROM BEFORE LIBFOLDERS MUST STILL FIND ITS GAMES FOLDER.
#
# Since 10f14d301d (libfolders) the app keeps its games folders as a JSON
# array in `gamesFolderUris`, and GamesFolders.read() migrates the old single
# `gamesFolderUri` into it and DELETES the old key; every write() deletes it
# again. A build from an older ref reads only `gamesFolderUri`, finds nothing,
# opens the setup wizard ("Games Folder: Not set"), and the soak reports that
# the title did not boot -- a void that names neither cause nor ref. Once one
# libfolders build has run on a handheld, every older soak on it went that way
# (fmv303c's 179114986 on the Thor).
#
# So before a soak the pref carries both keys: when `gamesFolderUris` has
# entries and `gamesFolderUri` is absent, `gamesFolderUri` gets the first one.
# A libfolders build ignores the old key while the new one is there, so this
# changes nothing for it. Every other byte of the file is kept, as with
# env_vars and hddPath. No entries, or the old key already present: no write.
# A write that does not read back fails the request -- the run would be the
# void this exists to prevent, and a `cat >` that truncated the file would be
# the setup wizard for every request after it.
#
# folder_pref_edit need|get|set <file> [value]
#   need: the first gamesFolderUris entry when gamesFolderUri is absent, else ""
#   get:  gamesFolderUri, unescaped
#   set:  add gamesFolderUri=<value> (the file must not hold it already)
folder_pref_edit() {
    python3 - "$@" <<'PYFOLD'
import html, json, re, sys
mode, path = sys.argv[1], sys.argv[2]
s = open(path, errors="replace").read()
def val(key):
    m = re.search(r'<string name="%s">(.*?)</string>' % re.escape(key), s, re.S)
    return None if m is None else html.unescape(m.group(1))
legacy = val("gamesFolderUri")
if mode == "get":
    sys.stdout.write(legacy or "")
    sys.exit(0)
if mode == "need":
    if legacy is not None:
        sys.exit(0)
    try:
        uris = json.loads(val("gamesFolderUris") or "[]")
    except ValueError:
        sys.exit("gamesFolderUris is not a JSON array; leaving it alone")
    if isinstance(uris, list) and uris and isinstance(uris[0], str):
        sys.stdout.write(uris[0])
    sys.exit(0)
want = sys.argv[3]
if "</map>" not in s:
    sys.exit("prefs file has no </map>; refusing to write")
if legacy is not None:
    sys.exit("gamesFolderUri is already set; refusing to overwrite it")
esc = want.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
s = s.replace("</map>", '    <string name="gamesFolderUri">%s</string>\n</map>' % esc)
open(path, "w").write(s)
PYFOLD
}

# ensure_legacy_folder_pref: sets FOLDER_PREF_STATE (result.json); 1 = fail.
ensure_legacy_folder_pref() {
    local pkg tmp want back
    pkg="${PKG:-com.jreinach.hakux.debug}"
    tmp="$D/.prefs.${DEVICE_LABEL:-$SERIAL}.folder.xml"
    FOLDER_PREF_STATE=""
    adb_call "$ADB_QUICK_TIMEOUT" "am force-stop (folder pref)" shell am force-stop "$pkg" >/dev/null 2>&1
    adb_call "$ADB_QUICK_TIMEOUT" "run-as cat x1box_prefs.xml (folder)" \
        shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" 2>/dev/null | tr -d '\r' > "$tmp"
    if [ -s "${ADB_HUNG_FILE:-}" ]; then
        log "  FOLDER PREF: adb hung ($(head -1 "$ADB_HUNG_FILE"))"; return 1
    fi
    if [ ! -s "$tmp" ]; then
        # No prefs at all is a device never set up; nothing here can fix that.
        export FOLDER_PREF_STATE="unread: x1box_prefs.xml empty or run-as refused"
        log "  WARNING: FOLDER PREF: cannot read x1box_prefs.xml; left as is"
        return 0
    fi
    if ! want=$(folder_pref_edit need "$tmp" 2>"$tmp.err"); then
        export FOLDER_PREF_STATE="kept: $(head -1 "$tmp.err")"
        log "  WARNING: FOLDER PREF: $FOLDER_PREF_STATE"
        return 0
    fi
    if [ -z "$want" ]; then
        export FOLDER_PREF_STATE="kept: no change needed"
        return 0
    fi
    if ! folder_pref_edit set "$tmp" "$want" 2>"$tmp.err"; then
        log "  FOLDER PREF: $(head -1 "$tmp.err")"; return 1
    fi
    adb_call "$ADB_QUICK_TIMEOUT" "run-as write x1box_prefs.xml (folder)" --in "$tmp" \
        shell "run-as $pkg sh -c 'cat > shared_prefs/x1box_prefs.xml'" >/dev/null 2>&1
    adb_call "$ADB_QUICK_TIMEOUT" "run-as read back x1box_prefs.xml (folder)" \
        shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" 2>/dev/null | tr -d '\r' > "$tmp.back"
    back=$(folder_pref_edit get "$tmp.back")
    # The key goes in just before </map>, so a read-back holding both is a
    # file that was written to its end.
    if [ "$back" != "$want" ] || ! grep -q '</map>' "$tmp.back"; then
        log "  FOLDER PREF: wrote gamesFolderUri=$want but read back '$back'"; return 1
    fi
    export FOLDER_PREF_STATE="added: gamesFolderUri from gamesFolderUris[0]"
    log "  folder pref: gamesFolderUri=$want (for a build before libfolders)"
}

# dev_sha256 <device path> -> sha256, or "" when the file is absent
dev_sha256() {
    adb_call 300 "sha256sum $1" shell "sha256sum '$1' 2>/dev/null || true" 2>/dev/null \
        | tr -d '\r' | awk 'NR==1 && $1 ~ /^[0-9a-f]{64}$/ {print $1}'
}
# dev_bytes <device path> -> size, or -1 when the file is absent
dev_bytes() {
    local n
    n=$(adb_call "$ADB_QUICK_TIMEOUT" "stat $1" shell "stat -c %s '$1' 2>/dev/null || echo -1" 2>/dev/null | tr -d '\r' | head -1)
    [[ "$n" =~ ^[0-9]+$ ]] && echo "$n" || echo -1
}
# dev_pull <device path> <host path> <sha256>: pulled and matching, or 1.
# Never `request.sh --pull`: soak_title.sh deletes what that pulls.
dev_pull() {
    local src="$1" dst="$2" want="$3" try
    mkdir -p "$(dirname "$dst")"
    for try in 1 2 3; do
        rm -f "$dst"
        adb_call 600 "pull $src" pull "$src" "$dst" >/dev/null 2>&1
        [ -s "$dst" ] && [ "$(sha256sum "$dst" | cut -d' ' -f1)" = "$want" ] && return 0
        log "  pull $try of $src: missing or not the device's file"
    done
    rm -f "$dst"; return 1
}
# dev_mode <device path> -> octal mode (e.g. 660), or "" when the file is absent
dev_mode() {
    adb_call "$ADB_QUICK_TIMEOUT" "stat mode $1" shell "stat -c %a '$1' 2>/dev/null" 2>/dev/null \
        | tr -d '\r' | awk 'NR==1 && $1 ~ /^[0-7]+$/ {print $1}'
}
# dev_make_660 <device path>: mode 660, read back (see THE DISK MUST BE MODE
# 660 above), or 1.
dev_make_660() {
    local m
    m=$(dev_mode "$1")
    [ "$m" = 660 ] && return 0
    adb_call "$ADB_QUICK_TIMEOUT" "chmod 660 $1" shell "chmod 660 '$1'" >/dev/null 2>&1
    m=$(dev_mode "$1")
    [ "$m" = 660 ] || { log "  $1: mode ${m:-unreadable} after chmod 660; the app could not open it read-write"; return 1; }
}
# dev_push <host path> <device path> [ro]: through <path>.new and a rename,
# checked. Mode 660 before the rename, so the file is never in place
# unopenable. A failure before the rename leaves <path> as it was and
# removes <path>.new.
#
# `ro` skips the 660 step and the final mode check -- for a disc pushed to
# DEVICE_ISO_ROOT (the SD card), whose mode the mount synthesizes: `chmod
# 660` is a no-op there and the mode always reads back 770, so the titles-
# disk rule below ("THE DISK MUST BE MODE 660") always failed it even
# though xemu opens a disc read-only and 770 is fine (dispatcher.log,
# mkdawhite1018 10-18 11:05, docs/lanes/mkdawhite1018/NOTES.md section 7.1).
# The sha check still runs either way. Every other caller -- titles.qcow2
# and the hdd-guard push, both opened read-write -- omits `ro` and keeps the
# 660 requirement unchanged.
dev_push_drop() {
    adb_call "$ADB_QUICK_TIMEOUT" "rm $1.new" shell "rm -f '$1.new'" >/dev/null 2>&1
}
dev_push() {
    local src="$1" dst="$2" ro="${3:-}" want wsrc
    want=$(sha256sum "$src" | cut -d' ' -f1)
    # adb is Windows adb.exe; it cannot stat /mnt/... or a bare /home/... path
    # (AGENTS.md, "Disc images live on D:"). wslpath -w turns a /mnt/d source
    # into D:\... and a /home source into the \\wsl.localhost\... form adb.exe
    # already resolves, so this covers both without a source-path branch.
    wsrc=$(wslpath -w "$src")
    adb_call 600 "push $dst" push "$wsrc" "$dst.new" >/dev/null 2>&1 || { dev_push_drop "$dst"; return 1; }
    [ "$(dev_sha256 "$dst.new")" = "$want" ] || { log "  push $dst: the device's copy does not match"; dev_push_drop "$dst"; return 1; }
    [ -n "$ro" ] || dev_make_660 "$dst.new" || { dev_push_drop "$dst"; return 1; }
    adb_call "$ADB_QUICK_TIMEOUT" "mv $dst" shell "mv -f '$dst.new' '$dst'" >/dev/null 2>&1 || { dev_push_drop "$dst"; return 1; }
    [ "$(dev_sha256 "$dst")" = "$want" ] && { [ -n "$ro" ] || [ "$(dev_mode "$dst")" = 660 ]; }
}

# dev_free_bytes <device dir> -> bytes free on the filesystem holding it, or
# -1 when adb could not say. `df -k`'s Available column, counted from the
# end (Mounted-on, Use%, Available), so a Filesystem field is never mistaken
# for it.
dev_free_bytes() {
    local dir="${1:?dev_free_bytes needs a device dir}" line avail
    line=$(adb_call "${ADB_QUICK_TIMEOUT:-30}" "df $dir" shell \
        "df -k $(_dev_sq "$dir") 2>/dev/null | tail -1" 2>/dev/null | tr -d '\r')
    avail=$(printf '%s\n' "$line" | awk '{print $(NF-2)}')
    [[ "$avail" =~ ^[0-9]+$ ]] && echo $((avail * 1024)) || echo -1
}

# title_claimed <title id>: 0 when a queued or running request names this
# title, by title_id or by its own --title string resolving to it; 1 when
# none does. Read before make_room_for_push deletes an on-device ISO -- a
# title another request is about to need is never cleared to make room for
# this one.
title_claimed() {
    local tid="${1:-}" f rid rtitle
    [ -n "$tid" ] || return 1
    for f in "$D"/queue/*.req "$D"/running/*.req; do
        [ -f "$f" ] || continue
        rid=$(jq_get "$f" title_id "")
        [ "$rid" = "$tid" ] && return 0
        rtitle=$(jq_get "$f" title "")
        [ -n "$rtitle" ] && [ "$(python3 "$TITLESTATE" tid-for-iso "$rtitle" 2>/dev/null)" = "$tid" ] && return 0
    done
    return 1
}

# make_room_for_push <device root> <need bytes> <rdir>: delete on-device
# ISOs, as listed, until <device root> has <need bytes> plus FREE_FLOOR_BYTES
# free -- never to make an unrelated push fit, only to admit the title THIS
# claim needs. Deletes a file only when it (a) is not named by any queued or
# running request (title_claimed) and (b) verifies by sha256 against a copy
# this host also holds on D: staging -- an ISO this host does not also hold
# is never deleted, whatever the floor needs (owner, 2026-10-13: pushes and
# deletes on the Nova are fine; the floor itself and app data are not touched
# to make room). Every deletion is logged to dispatcher.log and rdir/room.log.
# 1 when the floor still cannot be met from what could be verified; the
# caller must fail the claim rather than push into it.
make_room_for_push() {
    local root="$1" need="$2" rdir="$3" free f base tid staged ssha dsha
    free=$(dev_free_bytes "$root")
    [ "$free" -ge 0 ] || { log "  make_room: could not read free space on $root"; return 1; }
    [ $((free - need)) -ge "$FREE_FLOOR_BYTES" ] && return 0
    log "  make_room: $root has $((free / 1048576)) MiB free, need $(( (need + FREE_FLOOR_BYTES) / 1048576 )) MiB clear"
    while IFS= read -r base; do
        case "$base" in
            [0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]-*) ;;
            *) continue ;;
        esac
        tid=$(printf '%s' "${base:0:8}" | tr '[:lower:]' '[:upper:]')
        if title_claimed "$tid"; then
            log "  make_room: keeping $base, a queued or running request names it"; continue
        fi
        if ! staged=$(staging_find_tid "$tid"); then
            log "  make_room: keeping $base, no copy on D: staging to verify it against"; continue
        fi
        dsha=$(dev_sha256 "$root/$base")
        ssha=$(staging_file_sha "$staged")
        if [ -z "$dsha" ] || [ "$dsha" != "$ssha" ]; then
            log "  make_room: keeping $base, its sha does not verify against $staged"; continue
        fi
        adb_call "$ADB_QUICK_TIMEOUT" "rm $root/$base" shell "rm -f $(_dev_sq "$root/$base")" >/dev/null 2>&1
        printf '%s deleted %s (verified against %s)\n' "$(date '+%m-%d %H:%M:%S')" "$base" "$staged" >> "$rdir/room.log"
        log "  make_room: deleted $base (verified against $staged)"
        free=$(dev_free_bytes "$root")
        [ $((free - need)) -ge "$FREE_FLOOR_BYTES" ] && return 0
    done < <(adb_call "$ADB_QUICK_TIMEOUT" "ls $root" shell "ls -1 $(_dev_sq "$root")" 2>/dev/null | tr -d '\r')
    log "  make_room: still short of the floor after clearing every ISO that could be verified"
    return 1
}

# console_stage_tid <title id> <rdir>: last resort, when no staging root has
# the title -- titles/bin/stage_xiso.py's read-only FTP mirror from the
# console (outside this repo; never edited here). Respects its own
# PAUSE/STOP control files and is given a generous timeout (manifest history:
# 300-450s/title). The staged path on stdout and 0 when the mirror produced
# one; 1 and nothing otherwise (console unreachable, PAUSE/STOP set, the
# title is not on the console, or the mirror exceeded the timeout) -- never
# itself a claim failure, only "this did not help".
#
# Section 3: why it did not help goes to <rdir>/console-stage.result (one
# line), which ensure_title_staged folds into the ERROR -- this runs in a
# command substitution, so a variable would not reach the caller.
STAGE_XISO="${STAGE_XISO:-/home/justin/hakux-work/titles/bin/stage_xiso.py}"
console_stage_tid() {
    local tid="$1" rdir="$2" xdir="${HAKUX_XISO_DIR:-/mnt/d/hakux-staging/xiso}" why="" rc=0
    if [ -f "$xdir/PAUSE" ]; then why="not tried, $xdir/PAUSE is set"
    elif [ -f "$xdir/STOP" ]; then why="not tried, $xdir/STOP is set"
    elif [ ! -f "$STAGE_XISO" ]; then why="not tried, $STAGE_XISO not found"
    fi
    if [ -n "$why" ]; then
        log "  console stage: $why"; echo "$why" > "$rdir/console-stage.result"; return 1
    fi
    log "  console stage: mirroring $tid from the console (can take 5-8 minutes)"
    timeout -k 10 900 python3 "$STAGE_XISO" --only "$tid" --max 1 >> "$rdir/console-stage.log" 2>&1
    rc=$?
    if staging_find_tid "$tid"; then
        echo "staged $tid from the console (console-stage.log)" > "$rdir/console-stage.result"
        return 0
    fi
    case "$rc" in
        0)   why="the console answered but $tid did not come back (not on the console?); console-stage.log" ;;
        124) why="the console mirror timed out after 900 s; console-stage.log" ;;
        *)   why="the console did not answer (stage_xiso.py exit $rc); console-stage.log" ;;
    esac
    log "  console stage: $why"; echo "$why" > "$rdir/console-stage.result"
    return 1
}

# _bytes_h <bytes>: a size a reader can take in at a glance (GiB/MiB/bytes).
_bytes_h() {
    awk -v b="$1" 'BEGIN { if (b >= 1073741824) printf "%.1f GiB", b / 1073741824;
                           else if (b >= 1048576) printf "%.1f MiB", b / 1048576;
                           else printf "%d bytes", b }'
}

# inputs_note <rdir> <disc|route|profile> <text>: dispatchdoctor1017 Section
# 3, and the brief's Section 1 ("the dispatcher must see to all three, and
# say in the result dir which it did"). One line per input the claim saw to
# -- the disc image, the recorded route, the profile -- appended to
# <rdir>/inputs.txt, so a reader of the result sees what was found and done
# for each without reading dispatcher.log.
inputs_note() {
    printf '%s: %s\n' "$2" "$3" >> "$1/inputs.txt" 2>/dev/null || true
}

# stage_summary <rdir>: what the staging fast path found, for the front of a
# title-miss ERROR -- ensure_title_staged's own disc line when it wrote one,
# else the roots it would have searched.
stage_summary() {
    local l
    l=$(sed -n 's/^disc: //p' "$1/inputs.txt" 2>/dev/null | tail -1)
    if [ -n "$l" ]; then printf 'staging: %s' "${l#NOT STAGED: }"; return; fi
    printf 'staging searched %s, none had it' "$(staging_roots | paste -sd, - | sed 's/,/, /g')"
}

# ensure_title_staged <title> <rdir> <req>: the deterministic fast path
# (dispatchdoctor1017 Section 1), called only after device_title_path has
# already missed. Finds TITLE under a host staging root by its TitleID
# head, makes room if the push would cross FREE_FLOOR_BYTES, and pushes it
# to the device under the exact TITLE string the request named, so the
# caller's immediately-following device_title_path("$title") finds it.
#
# Reads only its own three arguments, never an outer-scope $ttid or $id:
# the soak block's `local tpath ... fi`, which calls this, is sed-extracted
# VERBATIM by jobs/selftest.d/99-iso-roots.sh and run with only $title,
# $rdir and $req bound -- an unbound variable there would fail that fixture
# under `set -u`, not this one.
#
# 0 when the title is on the device by the time this returns (pushed now, or
# a console mirror just produced it); 1, with the reason logged, when it is
# not -- the caller's existing ERROR path is unchanged either way. Section 3:
# every outcome also leaves one `disc:` line in <rdir>/inputs.txt ("pushed
# ..." or "NOT STAGED: <where it looked and what it found>"), which
# stage_summary puts at the front of the title-miss ERROR.
ensure_title_staged() {
    local title="$1" rdir="$2" req="$3" tid src need free why roots
    roots=$(staging_roots | paste -sd, - | sed 's/,/, /g')
    tid=$(jq_get "$req" title_id "" 2>/dev/null)
    [ -n "$tid" ] || tid=$(python3 "$TITLESTATE" tid-for-iso "$title" 2>/dev/null)
    if [ -z "$tid" ]; then
        why="not looked up, '$title' has no TitleID (no targets.toml \`iso\` entry, no 8-hex prefix)"
        log "  stage: $why"; inputs_note "$rdir" disc "NOT STAGED: $why"
        return 1
    fi
    if ! src=$(staging_find_tid "$tid"); then
        if ! src=$(console_stage_tid "$tid" "$rdir"); then
            why="no $tid-* image under $roots; console: $(cat "$rdir/console-stage.result" 2>/dev/null || echo 'not tried')"
            log "  stage: $why"; inputs_note "$rdir" disc "NOT STAGED: $why"
            return 1
        fi
    fi
    need=$(stat -c %s "$src" 2>/dev/null || echo -1)
    if [ "$need" -lt 0 ]; then
        why="found $src but could not stat it"
        log "  stage: $why"; inputs_note "$rdir" disc "NOT STAGED: $why"
        return 1
    fi
    free=$(dev_free_bytes "$DEVICE_ISO_ROOT")
    if [ "$free" -lt 0 ] || [ $((free - need)) -lt "$FREE_FLOOR_BYTES" ]; then
        if ! make_room_for_push "$DEVICE_ISO_ROOT" "$need" "$rdir"; then
            free=$(dev_free_bytes "$DEVICE_ISO_ROOT")
            why="found $src ($(_bytes_h "$need")) but did not push it: $DEVICE_ISO_ROOT has $(_bytes_h "$free") free and must keep $(_bytes_h "$FREE_FLOOR_BYTES") after the push; no on-device ISO was both unclaimed and verifiable against D: to delete (room.log, dispatcher.log)"
            [ "$free" -lt 0 ] && why="found $src but could not read the free space on $DEVICE_ISO_ROOT, so did not push it"
            log "  stage: $why"; inputs_note "$rdir" disc "NOT STAGED: $why"
            return 1
        fi
    fi
    if dev_push "$src" "$DEVICE_ISO_ROOT/$title" ro; then
        log "  stage: pushed $src -> $DEVICE_ISO_ROOT/$title"
        inputs_note "$rdir" disc "pushed $src -> $DEVICE_ISO_ROOT/$title ($(_bytes_h "$need"), sha checked)"
        return 0
    fi
    why="found $src but the push to $DEVICE_ISO_ROOT/$title failed (dispatcher.log)"
    log "  stage: $why"; inputs_note "$rdir" disc "NOT STAGED: $why"
    return 1
}

# profile_gate_check <request.json path> <rdir> [<title id>]: titlestate.py
# admit(), re-run at claim (lane.profilegate1011, #433) exactly as request.sh
# ran it at queue time -- nothing here is grandfathered, so a request written
# straight into dispatch/queue (no request.sh) is gated the same way. TITLE_ID
# defaults to the request's own title_id field when not given. On refusal,
# writes the one-line reason to <rdir>/profile.refused and returns 3; the
# caller decides how to report it (ERROR/log) and whether to restore hddPath,
# same division as titles_disk_prepare/hdd.refused.
profile_gate_check() {
    local req="$1" rdir="$2" ttid="${3:-}" route find reason remake broken out rc textfile
    [ -n "$ttid" ] || ttid=$(jq_get "$req" title_id "")
    route=$(jq_get "$req" route_name "")
    find=$(jq_get "$req" find_route "")
    remake=$(jq_get "$req" remake_profile "")
    broken=$(jq_get "$req" path_broken "")
    textfile=$(mktemp)
    python3 -c 'import json,sys; r=json.load(open(sys.argv[1])).get("route") or ""; open(sys.argv[2],"w").write(r)' \
        "$req" "$textfile"
    out=$(python3 "$TITLESTATE" admit ${ttid:+--title-id "$ttid"} ${route:+--route "$route"} \
          --route-text-file "$textfile" ${DEVICE_LABEL:+--device "$DEVICE_LABEL"} \
          ${find:+--find-route "$find"} ${remake:+--remake-profile "$remake"} \
          ${broken:+--path-broken "$broken"} 2>&1)
    rc=$?
    rm -f "$textfile"
    [ "$rc" = 0 ] && return 0
    reason=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("refuse") or sys.argv[1])' "$out" 2>/dev/null) \
        || reason="titlestate.py admit failed: $out"
    printf '%s\n' "$reason" > "$rdir/profile.refused"
    return 3
}

# ensure_route_attached <title id> <title> <rdir> <req>: dispatchdoctor1017
# Section 1b (owner 10-17, "it should know to copy ... the pathing ... to
# the right locations"). A request that names no route, or only the generic
# `survey` (never one typed deliberately -- see NOTES.md), gets this title's
# best recorded route attached here exactly as request.sh --route resolves
# one, mutating $req in place before profile_gate_check/titles_disk_prepare
# read it, so a request queued before this existed (or queued by a tool
# other than request.sh) is treated identically to a user-chosen --route.
# Never overrides a route the request already names; never invents one --
# titlestate.py suggest_route only returns a PROVEN route or targets.toml's
# own configured one, the same two sources route_path()/single_route() already
# trust.
#
# Section 3 / brief 1b: a recorded route that is found but cannot travel --
# resolve-route refuses it, it fails its own route.sh --check (a missing
# reference crop is the common case, and --check names the crop), or its
# crops cannot be embedded -- ends the claim: the reason goes to
# <rdir>/route.refused and this returns 3, which the soak block turns into a
# "refused before the soak" ERROR. The brief: "the refusal text is the
# answer, not a fallback to mashing". (request.sh's queue-time attach already
# fails the same way, through its own resolve/--check.) Every outcome, attach
# or not, leaves one `route:` line in <rdir>/inputs.txt saying which route
# and why.
ensure_route_attached() {
    local ttid="$1" title="$2" rdir="$3" req="$4"
    local cur sug name src res refuse path rname state refsout refsrefuse note chk why="" ncrops
    cur=$(jq_get "$req" route_name "")
    if [ -n "$cur" ] && [ "$cur" != survey ]; then
        inputs_note "$rdir" route "'$cur', named by the request (left as is)"
        return 0
    fi
    if [ -z "$ttid" ]; then
        inputs_note "$rdir" route "none: '$title' has no TitleID, so no recorded route can be looked up${cur:+ (running the survey the request asked for)}"
        return 0
    fi
    # Never on a request that already names a deliberate profile-gate
    # override: see request.sh's matching guard, same reasoning.
    if [ -n "$(jq_get "$req" find_route "")" ] || [ -n "$(jq_get "$req" remake_profile "")" ] \
       || [ -n "$(jq_get "$req" path_broken "")" ]; then
        inputs_note "$rdir" route "none attached: the request carries --find-route/--remake-profile/--path-broken, which the profile gate decides"
        return 0
    fi
    sug=$(python3 "$TITLESTATE" suggest-route --title-id "$ttid" 2>&1)
    # suggest-route prints JSON whether or not it found one; anything else is
    # a crash (a snapshot missing targets.toml raises FileNotFoundError), and
    # "no recorded route" would then be a claim nobody checked. Say it failed
    # and run as queued: the lookup's failure is not the request's.
    if ! python3 -c 'import json,sys; json.loads(sys.argv[1])' "$sug" 2>/dev/null; then
        note=$(printf '%s\n' "$sug" | grep -v '^[[:space:]]*$' | tail -1)
        log "  ROUTE LOOKUP FAILED for $ttid: titlestate.py suggest-route: ${note:-no output}"
        inputs_note "$rdir" route "none: could not look up a route for $ttid, titlestate.py suggest-route failed (${note:-no output}); $([ -n "$cur" ] && echo 'running the survey the request asked for' || echo 'running with no scripted input, as queued')"
        return 0
    fi
    name=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("name") or "")' "$sug" 2>/dev/null)
    if [ -z "$name" ]; then
        note=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("note") or "no recorded or proven route")' "$sug" 2>/dev/null)
        log "  route: ${note:-no recorded or proven route} for $ttid; leaving the request as queued"
        inputs_note "$rdir" route "none: no proven or recorded route for $ttid (${note:-no recorded or proven route}); the generic survey does not reach gameplay for most titles; $([ -n "$cur" ] && echo 'running the survey the request asked for' || echo 'running with no scripted input, as queued')"
        return 0
    fi
    src=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("source") or "")' "$sug" 2>/dev/null)
    res=$(python3 "$TITLESTATE" resolve-route --route "$name" --title-id "$ttid" ${DEVICE_LABEL:+--device "$DEVICE_LABEL"} 2>&1)
    refuse=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("refuse") or "")' "$res" 2>/dev/null) || refuse="titlestate.py resolve-route failed: $res"
    if [ -n "$refuse" ]; then
        why="recorded route '$name' ($src) for $ttid does not resolve: $refuse"
    else
        path=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["path"])' "$res")
        rname=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["route_name"])' "$res")
        state=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["state"])' "$res")
        if ! chk=$(bash "$HERE/titles/route.sh" --check "$path" 2>&1); then
            why="recorded route '$rname' ($src) for $ttid fails its own check: $(printf '%s' "$chk" | grep -v '^[[:space:]]*$' | head -3 | paste -sd';' - | sed 's/;/; /g')"
        else
            refsout=$(python3 "$TITLESTATE" route-refs --route-path "$path" 2>&1)
            refsrefuse=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("refuse") or "")' "$refsout" 2>/dev/null) || refsrefuse="titlestate.py route-refs failed: $refsout"
            [ -n "$refsrefuse" ] && why="recorded route '$rname' ($src) for $ttid: $refsrefuse"
        fi
    fi
    if [ -n "$why" ]; then
        log "  route: $why; refusing the claim rather than running without it"
        printf '%s\n' "$why" > "$rdir/route.refused"
        inputs_note "$rdir" route "REFUSED: $why"
        return 3
    fi
    python3 -c '
import json, sys
req, path, rname, state, refsjson = sys.argv[1:6]
d = json.load(open(req))
d["route_name"] = rname
d["route"] = open(path).read()
d["title_state"] = state
refs = json.loads(refsjson).get("refs") or {}
if refs:
    d["route_refs"] = refs
json.dump(d, open(req, "w"))
' "$req" "$path" "$rname" "$state" "$refsout"
    log "  route: auto-attached '$rname' ($src) for $ttid, state=$state"
    ncrops=$(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1]).get("refs") or {}))' "$refsout" 2>/dev/null)
    inputs_note "$rdir" route "attached '$rname' for $ttid, state=$state, ${ncrops:-0} reference crop(s); why: $(
        [ "$src" = proven ] && echo 'proven, a judged run on it reached gameplay' \
                            || echo "the title's configured route in targets.toml (recorded, not yet proven)")$(
        [ -n "$cur" ] && echo "; replaces the generic survey the request named")"
}

# archive_backup_dir <tid>: dispatchdoctor1017 Section 1c. The first
# saves/<TID> tree (an HDD-GUARD-shaped export: save.json per save id) under
# any nova-archive-*/lanelocal-* staging root -- the two archive kinds the
# brief names for a profile backup, never sweep/xiso/staging/ingest, which
# Section 1 already established are disc-image-only. Prints the first
# match; non-zero, nothing printed, when none of those roots have one.
archive_backup_dir() {
    local tid="$1" root hit
    while IFS= read -r root; do
        case "$root" in *nova-archive-*|*lanelocal-*) ;; *) continue ;; esac
        hit=$(find "$root" -type f -name save.json -path "*/saves/$tid/save.json" 2>/dev/null | head -1)
        if [ -n "$hit" ]; then printf '%s\n' "$(dirname "$hit")"; return 0; fi
    done < <(staging_roots)
    return 1
}

# device_bak_auto_dir <tid> <rdir>: dispatchdoctor1017 Section 1c. This
# device's own hdd.img.bak-auto (hdd_img_guard's pre-reset copy,
# dispatcher.sh's hdd_img_guard) pulled, listed with saves.py, and -- only
# when it actually carries TID's save -- extracted into an import-save-able
# directory under $TITLESTATE_DIR/pull. Prints that directory; non-zero,
# nothing printed, when the device has no bak-auto file, or it has one but
# not this title's save. Scratch files are removed after use either way --
# this never leaves a second copy of a backup lying around, only the one
# import-save itself makes in the store.
device_bak_auto_dir() {
    local tid="$1" bak sha pulled outdir have
    bak="$(x1box_dir)/hdd.img.bak-auto"
    sha=$(dev_sha256 "$bak")
    [ -n "$sha" ] || return 1
    pulled="$TITLESTATE_DIR/pull/${DEVICE_LABEL:-dev}-bak-auto.img"
    dev_pull "$bak" "$pulled" "$sha" || return 1
    have=$(python3 "$SAVES_PY" list "$pulled" 2>/dev/null | awk -v t="$tid" '$1==t{print; exit}')
    if [ -z "$have" ]; then rm -f "$pulled"; return 1; fi
    outdir="$TITLESTATE_DIR/pull/${DEVICE_LABEL:-dev}-bak-auto-$tid"
    rm -rf "$outdir"
    python3 "$SAVES_PY" pull "$pulled" "$tid" "$outdir" >/dev/null 2>&1 || { rm -f "$pulled"; return 1; }
    rm -f "$pulled"
    [ -f "$outdir/save.json" ] || return 1
    printf '%s\n' "$outdir"
}

# ensure_profile_restored <title id> <state> <rdir> <req>: dispatchdoctor1017
# Section 1c ("a profile that has already been created and backed up must
# be on the device's disk image when the title launches ... the dispatcher
# must not respond by creating a profile again", owner 10-17). Runs after
# the profile gate and before titles_disk_prepare, so a title with no
# golden gets one FOUND here rather than titles_disk_prepare's own compose
# refusing "no golden profile" -- but only ever as this title's FIRST
# golden (a replace stays lane.local's: titlestate.py restore-backup
# refuses outright when a golden already exists, same as `promote` without
# `--replace` would). Looks, in order, at: a save already in this title's
# own store but never promoted (titlestate.py backup-candidates); an
# HDD-GUARD reset's saves/<TID> tree on the host (same subcommand); a
# nova-archive-*/lanelocal-* staging root's saves/<TID> tree; this device's
# own hdd.img.bak-auto. First one found is restored -- never a pick among
# several. Writes $rdir/profile-backup.json naming every place this looked,
# what (if anything) it found, and whether the restore stuck -- so a title
# with nothing anywhere still leaves a readable trail behind the ERROR
# titles_disk_prepare's own compose call goes on to raise.
ensure_profile_restored() {
    local ttid="$1" tstate="$2" rdir="$3" req="$4"
    local g has searched="" kind="" detail="" rj="" refuse
    if [ -z "$ttid" ]; then
        inputs_note "$rdir" profile "none looked for: the title has no TitleID"; return 0
    fi
    if [ "$tstate" = first-run ]; then
        inputs_note "$rdir" profile "none loaded: a first-run route starts this title with no profile by design"; return 0
    fi
    g=$(python3 "$TITLESTATE" golden --title-id "$ttid" --json 2>/dev/null)
    has=$(python3 -c '
import json, sys
d = json.loads(sys.argv[1] or "{}")
rec = next(iter(d.values()), {})
g = rec.get("golden") or {}
print((g.get("save") or "?") if g else "")
' "$g" 2>/dev/null)
    if [ -n "$has" ]; then
        inputs_note "$rdir" profile "$ttid's golden (save $has) is in the store; the titles disk is composed with it"; return 0
    fi

    local cand sid path
    cand=$(python3 "$TITLESTATE" backup-candidates --title-id "$ttid" --json 2>/dev/null)
    searched="store"
    sid=$(python3 -c '
import json, sys
for c in json.loads(sys.argv[1] or "[]"):
    if c["kind"] == "store" and c.get("has_save_dir"):
        print(c["save"]); break
' "$cand" 2>/dev/null)
    [ -n "$sid" ] && { kind=store; detail="$sid"; }

    if [ -z "$kind" ]; then
        searched="$searched,hdd-reset"
        path=$(python3 -c '
import json, sys
for c in json.loads(sys.argv[1] or "[]"):
    if c["kind"] == "hdd-reset":
        print(c["path"]); break
' "$cand" 2>/dev/null)
        [ -n "$path" ] && { kind=hdd-reset; detail="$path"; }
    fi
    if [ -z "$kind" ]; then
        searched="$searched,archive"
        path=$(archive_backup_dir "$ttid")
        [ -n "$path" ] && { kind=archive; detail="$path"; }
    fi
    if [ -z "$kind" ]; then
        searched="$searched,device-bak-auto"
        path=$(device_bak_auto_dir "$ttid")
        [ -n "$path" ] && { kind=device-bak-auto; detail="$path"; }
    fi

    if [ -z "$kind" ]; then
        python3 -c 'import json,sys; json.dump({"title_id": sys.argv[1], "searched": sys.argv[2].split(","), "found": None}, open(sys.argv[3], "w"))' \
            "$ttid" "$searched" "$rdir/profile-backup.json"
        log "  profile backup: none found for $ttid (looked: $searched)"
        inputs_note "$rdir" profile "$ttid has no golden and no backup was found (looked: ${searched//,/, }); nothing restored, no profile created"
        return 0
    fi

    if [ "$kind" = store ]; then
        rj=$(python3 "$TITLESTATE" restore-backup --title-id "$ttid" --save "$detail" --by dispatcher 2>&1)
    else
        rj=$(python3 "$TITLESTATE" restore-backup --title-id "$ttid" --import-dir "$detail" --by dispatcher 2>&1)
    fi
    refuse=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("refuse") or "")' "$rj" 2>/dev/null) || refuse="titlestate.py restore-backup failed: $rj"
    if [ -n "$refuse" ]; then
        python3 -c 'import json,sys; json.dump({"title_id": sys.argv[1], "searched": sys.argv[2].split(","), "found": sys.argv[3], "detail": sys.argv[4], "restored": False, "refuse": sys.argv[5]}, open(sys.argv[6], "w"))' \
            "$ttid" "$searched" "$kind" "$detail" "$refuse" "$rdir/profile-backup.json"
        log "  profile backup: found a candidate ($kind: $detail) for $ttid but restore-backup refused: $refuse"
        inputs_note "$rdir" profile "$ttid has no golden; found a backup ($kind: $detail) but restore-backup refused it: $refuse"
        return 0
    fi
    python3 -c 'import json,sys; json.dump({"title_id": sys.argv[1], "searched": sys.argv[2].split(","), "found": sys.argv[3], "detail": sys.argv[4], "restored": True}, open(sys.argv[5], "w"))' \
        "$ttid" "$searched" "$kind" "$detail" "$rdir/profile-backup.json"
    log "  profile backup: restored $ttid's golden from $kind ($detail)"
    inputs_note "$rdir" profile "restored $ttid's first golden from a backup ($kind: $detail; copied, the backup is untouched)"
}

# verify_profile_on_device <title id> <state> <rdir>: dispatchdoctor1017
# Section 1c step 4, "Verify on the device". After titles_disk_prepare has
# pushed (or kept) the composed titles.qcow2, pull it back and check it with
# saves.py verify against the STORE's own save.json for the save hdd.json
# says it loaded -- dev_push's own sha check already proves the BYTES
# landed; this proves the title's save inside them is the one the claim
# thinks it composed, which is the gap the brief names ("disk pushed but
# the profile is not on it"). saves.py list's "saves" column is the
# on-device FATX folder name a save's paths were originally pulled under
# (titlestate1017's own fixture work found this the hard way: that folder
# name is NOT the store's content-hash save id, so a bare `list`+grep for
# the id would never match a real composed disk); `saves.py verify` instead
# re-checks every path/hash saves.py pull itself once recorded for that
# save, wherever on the image they are -- the same check 99-hdd-split.sh's
# own verify_on() runs against a store save dir. Nothing was loaded for
# this title (a first-run route, or a request with no title at all) is not
# a failure -- there is nothing to verify, same as before this existed. A
# mismatch is refused exactly like compose's own NoGolden, via
# $rdir/hdd.refused and exit 3, which the soak block already turns into an
# ERROR before launch. Writes $rdir/hdd.verify.json either way.
verify_profile_on_device() {
    local ttid="$1" tstate="$2" rdir="$3" hdd
    hdd="$rdir/hdd.json"
    [ -n "$ttid" ] || return 0
    [ "$tstate" = first-run ] && return 0
    [ -f "$hdd" ] || return 0
    local save path sha pulled savedir bad rc
    save=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("save") or "")' "$hdd" 2>/dev/null)
    if [ -z "$save" ]; then
        python3 -c 'import json,sys; json.dump({"title_id": sys.argv[1], "save": None, "verified": None}, open(sys.argv[2], "w"))' \
            "$ttid" "$rdir/hdd.verify.json"
        inputs_note "$rdir" profile "device check: the composed titles disk loads no save for $ttid, nothing to verify"
        return 0
    fi
    savedir=$(python3 "$TITLESTATE" store-dir --title-id "$ttid" --save "$save" 2>/dev/null)
    path=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("path") or "")' "$hdd" 2>/dev/null)
    [ -n "$path" ] || path="$(x1box_dir)/titles.qcow2"
    sha=$(dev_sha256 "$path")
    pulled="$TITLESTATE_DIR/pull/${DEVICE_LABEL:-dev}-verify-$ttid.qcow2"
    if ! dev_pull "$path" "$pulled" "$sha"; then
        echo "no profile: could not pull $path off the device to verify $ttid's save $save is on it" > "$rdir/hdd.refused"
        log "  PROFILE VERIFY: pull of $path failed"
        python3 -c 'import json,sys; json.dump({"title_id": sys.argv[1], "save": sys.argv[2], "verified": False, "reason": "pull failed"}, open(sys.argv[3], "w"))' \
            "$ttid" "$save" "$rdir/hdd.verify.json"
        inputs_note "$rdir" profile "device check FAILED: could not pull $path back to verify save $save"
        return 3
    fi
    bad=$(python3 "$SAVES_PY" verify "$pulled" "$savedir" 2>&1)
    rc=$?
    rm -f "$pulled"
    if [ "$rc" != 0 ]; then
        echo "no profile: the composed disk claims $ttid's save is $save, but saves.py verify does not find it on the pushed image ($bad)" > "$rdir/hdd.refused"
        log "  PROFILE VERIFY: $save does not verify on device for $ttid ($bad)"
        python3 -c 'import json,sys; json.dump({"title_id": sys.argv[1], "save": sys.argv[2], "verified": False, "detail": sys.argv[3]}, open(sys.argv[4], "w"))' \
            "$ttid" "$save" "$bad" "$rdir/hdd.verify.json"
        inputs_note "$rdir" profile "device check FAILED: save $save is not on the pushed titles disk ($bad)"
        return 3
    fi
    log "  PROFILE VERIFY: $ttid save $save confirmed on device"
    inputs_note "$rdir" profile "device check: save $save pulled back off $path and verified (hdd.verify.json)"
    python3 -c 'import json,sys; json.dump({"title_id": sys.argv[1], "save": sys.argv[2], "verified": True}, open(sys.argv[3], "w"))' \
        "$ttid" "$save" "$rdir/hdd.verify.json"
}

# titles_disk_prepare <id> <rdir> [<request env json>] [<title id>] [<state>] [<save>]:
# make the device's titles disk the composed goldens for this title and state
# (titlestate.py, GOLDENS: every title's golden profile, minus this title's on
# a first-run) and point hddPath at it. SAVE (the request's --save; lane.
# profilegate1011, #433), when given, swaps that stored save in for this
# title's slot instead of its golden. Writes <rdir>/hdd.json, which records
# what was loaded: title, save, golden or none. Non-zero fails the request;
# 3 is a refusal (a returning state with no golden, or a --save that is not
# in the store / was rejected on this device / carries no save directory on
# a returning route), written to <rdir>/hdd.refused, before any disk is
# touched.
titles_disk_prepare() {
    local id="$1" rdir="$2" renv="${3:-[]}" tid="${4:-}" tstate="${5:-any}" tsave="${6:-}" dev="${DEVICE_LABEL:-}" dpath x pj action reason bytes sha i
    local split="${HAKUX_TITLES_DISK:-1}" from=worker rsplit mode0 targs=()
    [ -n "$tid" ] && targs=(--title-id "$tid")
    targs+=(--state "$tstate")
    [ -n "$tsave" ] && targs+=(--save "$tsave")
    [ -n "${HAKUX_TITLES_DISK:-}" ] || from=default
    # The request's own HAKUX_TITLES_DISK, when it names one, wins.
    rsplit=$(python3 -c '
import json, sys
v = json.loads(sys.argv[1] or "[]")
v = ["%s=%s" % kv for kv in v.items()] if isinstance(v, dict) else v
print(([str(e).split("=", 1)[1] for e in v if str(e).startswith("HAKUX_TITLES_DISK=")] or [""])[-1])' "$renv" 2>/dev/null)
    [ -n "$rsplit" ] && { split="$rsplit"; from=request; }
    x="$(x1box_dir)"; dpath="$x/titles.qcow2"
    case "$dev" in nova|thor) ;; *)
        printf '{"path": null, "split": "off: no titles registry for device %s"}\n' "$dev" > "$rdir/hdd.json"
        return 0 ;; esac
    if [ "$split" = 0 ]; then
        printf '{"path": null, "split": "off: HAKUX_TITLES_DISK=0", "split_from": "%s"}\n' "$from" > "$rdir/hdd.json"
        return 0
    fi
    [ "$from" = request ] && log "  titles disk: on for this request (its env HAKUX_TITLES_DISK=$split beats the worker's ${HAKUX_TITLES_DISK:-unset})"
    # Nothing may hold the disk while it is read or replaced.
    adb_call "$ADB_QUICK_TIMEOUT" "am force-stop (titles disk)" shell am force-stop "${PKG:-com.jreinach.hakux.debug}" >/dev/null 2>&1
    : > "$rdir/hdd.plan"
    for i in 1 2 3 4 5; do
        bytes=$(dev_bytes "$dpath"); sha=""
        [ "$bytes" -ge 0 ] && sha=$(dev_sha256 "$dpath")
        pj=$(python3 "$TITLESTATE" plan --device "$dev" --device-bytes "$bytes" --device-sha "$sha" "${targs[@]}") || {
            log "  TITLES DISK: plan failed"; return 1; }
        printf '%s\n' "$pj" >> "$rdir/hdd.plan"
        action=$(python3 -c 'import json,sys;print(json.loads(sys.argv[1])["action"])' "$pj")
        reason=$(python3 -c 'import json,sys;print(json.loads(sys.argv[1])["reason"])' "$pj")
        log "  titles disk: $action ($reason)"
        case "$action" in
            keep) break ;;
            refuse)
                printf '%s\n' "$reason" > "$rdir/hdd.refused"
                log "  TITLES DISK: REFUSED: $reason"; return 3 ;;
            preserve)
                # The harvest of this disk failed: keep all of it on the host,
                # then rebuild. A disk a run wrote to is never booted again.
                local keep; keep="$TITLESTATE_DIR/unharvested/$dev-${sha:0:12}.qcow2"
                dev_pull "$dpath" "$keep" "$sha" || { log "  TITLES DISK: cannot pull the disk to preserve it"; return 1; }
                python3 "$TITLESTATE" preserved --device "$dev" --sha "$sha" --path "$keep" || return 1 ;;
            seed)
                local h hs; h="$TITLESTATE_DIR/pull/$dev-hdd.img"
                hs=$(dev_sha256 "$x/hdd.img")
                [ -n "$hs" ] && dev_pull "$x/hdd.img" "$h" "$hs" || { log "  TITLES DISK: cannot pull hdd.img to seed"; return 1; }
                python3 "$TITLESTATE" seed --device "$dev" --image "$h" --run "$id" > "$rdir/hdd.seed.json" \
                    || { rm -f "$h"; log "  TITLES DISK: seed failed"; return 1; }
                rm -f "$h" ;;
            harvest)
                titles_disk_harvest "$id:before" "$dpath" "$sha" "$rdir/hdd.harvest-before.json" || return 1 ;;
            build)
                local bj img isha built
                bj=$(python3 "$TITLESTATE" rebuild --device "$dev" "${targs[@]}") || { log "  TITLES DISK: rebuild failed"; return 1; }
                printf '%s\n' "$bj" > "$rdir/hdd.build.json"
                img=$(python3 -c 'import json,sys;print(json.loads(sys.argv[1])["path"])' "$bj")
                built=$(python3 -c 'import json,sys;print(json.dumps(json.loads(sys.argv[1])["built_from"]))' "$bj")
                dev_push "$img" "$dpath" || { log "  TITLES DISK: push failed"; return 1; }
                python3 "$TITLESTATE" pushed --device "$dev" --image "$img" --device-path "$dpath" \
                    --built-from "$built" || return 1 ;;
            *) log "  TITLES DISK: unknown plan '$action'"; return 1 ;;
        esac
    done
    [ "$action" = keep ] || { log "  TITLES DISK: no stable plan after $i rounds"; return 1; }
    # A kept disk may predate dev_push's chmod (THE DISK MUST BE MODE 660).
    mode0=$(dev_mode "$dpath")
    dev_make_660 "$dpath" || { log "  TITLES DISK: cannot make $dpath mode 660"; return 1; }
    [ "$mode0" = 660 ] || log "  titles disk: mode ${mode0:-unreadable} -> 660"
    # The FIRST value found is the one to put back: a marker already there
    # (a worker that died mid-run) holds it, and hddPath now reads ours.
    # set_hdd_pref writes the marker before the pref, so a failure here still
    # leaves serve_one's restore_hdd_pref the value to put back.
    set_hdd_pref "$dpath" "$(hdd_pref_marker)" >/dev/null || return 1
    local cj; cj=$(python3 "$TITLESTATE" compose --device "$dev" "${targs[@]}") || cj='{}'
    python3 - "$rdir" "$dpath" "$sha" "$bytes" "$mode0" "$from" "$cj" <<'PYHDD'
import json, os, sys
rdir, path, sha, n, mode0, frm, cj = sys.argv[1:8]
plans = [json.loads(l) for l in open(os.path.join(rdir, "hdd.plan")) if l.strip()]
c = json.loads(cj)
c.pop("built_from", None)
# title_id, disk_title_id, state, save, loaded (golden|none), golden_status:
# what this run's title found on the disk (titlestate.py compose).
json.dump(dict(c, path=path, sha256_at_start=sha, bytes_at_start=int(n), plans=plans,
               mode_found=mode0 or None, mode="660",
               split="on", split_from=frm), open(os.path.join(rdir, "hdd.json"), "w"), indent=1)
PYHDD
    log "  hddPath -> $dpath (sha256 ${sha:0:12}, $bytes B; ${tid:-title unknown} $tstate: $(python3 -c 'import json,sys;c=json.loads(sys.argv[1]);print(c.get("loaded"), c.get("save") or "")' "$cj" 2>/dev/null))"
}

# titles_disk_harvest <run> <device path> <sha> <out.json>: pull, harvest.
titles_disk_harvest() {
    local run="$1" dpath="$2" sha="$3" out="$4" h
    h="$TITLESTATE_DIR/pull/${DEVICE_LABEL}-titles.qcow2"
    dev_pull "$dpath" "$h" "$sha" || { log "  TITLES DISK: pull for harvest failed"; return 1; }
    python3 "$TITLESTATE" after-run --device "$DEVICE_LABEL" --image "$h" --run "$run" \
        --device-sha "$sha" > "$out" || { rm -f "$h"; return 1; }
    rm -f "$h"
    log "  titles disk harvested: $(cat "$out")"
}

# titles_disk_after <id> <rdir>: after the soak (the app is force-stopped):
# harvest whatever the run wrote, then put hddPath back. Never fails the
# request: the run already happened; what did not harvest, plan() refuses to
# rebuild over next time.
titles_disk_after() {
    local id="$1" rdir="$2" dpath bytes sha pj
    grep -q '"split": "on"' "$rdir/hdd.json" 2>/dev/null || { restore_hdd_pref; return 0; }
    dpath="$(x1box_dir)/titles.qcow2"
    adb_call "$ADB_QUICK_TIMEOUT" "am force-stop (titles disk after)" shell am force-stop "${PKG:-com.jreinach.hakux.debug}" >/dev/null 2>&1
    bytes=$(dev_bytes "$dpath"); sha=$(dev_sha256 "$dpath")
    pj=$(python3 "$TITLESTATE" plan --device "$DEVICE_LABEL" --device-bytes "$bytes" --device-sha "$sha")
    case "$pj" in
        *'"action": "harvest"'*)
            titles_disk_harvest "$id" "$dpath" "$sha" "$rdir/hdd.after.json" \
                || printf '{"error": "pull or harvest failed; see dispatcher.log"}\n' > "$rdir/hdd.after.json" ;;
        *) printf '{"unchanged_or_blocked": %s, "sha256": "%s"}\n' "$pj" "$sha" > "$rdir/hdd.after.json" ;;
    esac
    titles_first_run_golden "$id" "$rdir"
    restore_hdd_pref || log "  WARNING: hddPath not restored; the next request retries"
}

# titles_first_run_golden <id> <rdir>: a first-run whose route reached `mark
# profile-saved` made the title's profile; when the title has no golden, the
# harvested save becomes it (titlestate.py first-run-saved never replaces one).
titles_first_run_golden() {
    local id="$1" rdir="$2" dt save
    grep -q '"state": "first-run"' "$rdir/hdd.json" 2>/dev/null || return 0
    grep -q 'mark profile-saved' "$rdir/run.log" 2>/dev/null || return 0
    dt=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("disk_title_id") or "")' "$rdir/hdd.json" 2>/dev/null)
    save=$(python3 -c 'import json,sys;print((json.load(open(sys.argv[1])).get("harvested") or {}).get(sys.argv[2]) or "")' \
           "$rdir/hdd.after.json" "$dt" 2>/dev/null)
    if [ -z "$dt" ] || [ -z "$save" ]; then
        log "  first-run reached profile-saved, but no save of ${dt:-the title} was harvested; no golden made"
        return 0
    fi
    python3 "$TITLESTATE" first-run-saved --title-id "$dt" --save "$save" --run "$id" \
        > "$rdir/hdd.golden.json" 2>&1 && log "  golden: $(cat "$rdir/hdd.golden.json")"
}

# hdd_img_guard <rdir>: disc runs keep hdd.img, and it still grows (E:\nxdk_*
# output, a few MB a run, plus whatever the pre-split title runs left). Past
# HAKUX_HDD_RESET_BYTES (1 GiB) it is reset through saves.py reset -- every
# title's save pulled, a fresh disk built from them, each verified -- and the
# old one kept on the device as hdd.img.bak-auto. A failed reset changes
# nothing and says so. Writes <rdir>/hdd_guard.json when it acts.
#
# A reset that fails for a reason that will not change (saves.py refuses the
# disk, or the device has no room for the backup) is recorded against the
# disk's size and mtime in $D/.hdd_guard_failed.<device>; while hdd.img still
# has that size and mtime, later requests write the alert without paying for
# the sha256, the pull and the reset again. Any write to hdd.img, or removing
# the file, re-arms the guard.
hdd_img_guard() {
    local rdir="$1" x dpath bytes limit="${HAKUX_HDD_RESET_BYTES:-1073741824}" sha h sdir stamp fp failed
    x="$(x1box_dir)"; dpath="$x/hdd.img"
    bytes=$(dev_bytes "$dpath")
    [ "$bytes" -gt "$limit" ] || return 0
    failed="$D/.hdd_guard_failed.${DEVICE_LABEL:-$SERIAL}"
    fp=$(adb_call "$ADB_QUICK_TIMEOUT" "stat $dpath (guard)" shell "stat -c '%s %Y' '$dpath' 2>/dev/null" 2>/dev/null | tr -d '\r' | head -1)
    [[ "$fp" =~ ^[0-9]+\ [0-9]+$ ]] || fp=""
    if [ -n "$fp" ] && [ -f "$failed" ] && [ "$(head -1 "$failed")" = "$fp" ]; then
        log "  HDD GUARD: hdd.img ($bytes B) is the disk whose reset already failed; not retried"
        printf '{"action": "alert", "bytes": %s, "limit": %s, "repeat": true, "why": "%s"}\n' \
            "$bytes" "$limit" "$(sed -n 2p "$failed" | tr -d '"')" > "$rdir/hdd_guard.json"
        return 0
    fi
    log "  HDD GUARD: hdd.img is $bytes B > $limit B; resetting it (saves.py reset)"
    stamp=$(date -u +%Y%m%dT%H%M%SZ); sdir="$D/hdd-reset/${DEVICE_LABEL:-$SERIAL}-$stamp"
    h="$sdir/pulled.img"; mkdir -p "$sdir"
    guard_fail() {
        log "  HDD GUARD ALERT: $1; hdd.img left as it was ($bytes B)"
        printf '{"action": "alert", "bytes": %s, "limit": %s, "why": "%s"}\n' "$bytes" "$limit" "$1" > "$rdir/hdd_guard.json"
        rm -f "$h" "$sdir/hdd.img"
    }
    # guard_fail_final: the same disk would fail the same way next time.
    guard_fail_final() {
        guard_fail "$1"
        [ -n "$fp" ] && printf '%s\n%s\n' "$fp" "$1" > "$failed"
    }
    adb_call "$ADB_QUICK_TIMEOUT" "am force-stop (hdd guard)" shell am force-stop "${PKG:-com.jreinach.hakux.debug}" >/dev/null 2>&1
    sha=$(dev_sha256 "$dpath")
    [ -n "$sha" ] && dev_pull "$dpath" "$h" "$sha" || { guard_fail "pull failed"; return 0; }
    python3 "$SAVES_PY" reset "$h" "$sdir/hdd.img" "$sdir/saves" > "$sdir/reset.json" 2>>"$sdir/reset.err" \
        || { guard_fail_final "saves.py reset refused: $(tail -1 "$sdir/reset.err" | tr -d '"')"; return 0; }
    rm -f "$h"
    # A partial backup holds the space the next attempt needs: removed.
    adb_call 600 "back up hdd.img" shell "cp -f '$dpath' '$dpath.bak-auto'" >/dev/null 2>&1 \
        && [ "$(dev_sha256 "$dpath.bak-auto")" = "$sha" ] || {
            adb_call "$ADB_QUICK_TIMEOUT" "rm partial hdd.img.bak-auto" shell "rm -f '$dpath.bak-auto'" >/dev/null 2>&1
            guard_fail_final "could not back up hdd.img on the device"; return 0; }
    dev_push "$sdir/hdd.img" "$dpath" || { guard_fail "push of the rebuilt disk failed (hdd.img.bak-auto is the original)"; return 0; }
    python3 - "$rdir/hdd_guard.json" "$sdir/reset.json" "$bytes" "$limit" "$sdir" <<'PYHDD'
import json, sys
out, rj, n, lim, sdir = sys.argv[1:6]
r = json.load(open(rj))
json.dump({"action": "reset", "bytes": int(n), "limit": int(lim), "after_bytes": r["bytes"],
           "titles": r["titles"], "saves": sdir + "/saves", "backup": "hdd.img.bak-auto"},
          open(out, "w"), indent=1)
PYHDD
    rm -f "$sdir/hdd.img" "$failed"
    log "  HDD GUARD: hdd.img reset, $bytes B -> $(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["bytes"])' "$sdir/reset.json") B, saves in $sdir/saves"
}

# THERE IS NO SWEEP PREEMPTION HERE, and there was one until 2026-09-25.
# preempt_sweep/resume_sweep drove sweep_queue.sh pause/resume around every
# install. It never ran: sweep_queue.sh demanded four build inputs before its
# `pause` case, which were not passed, so it exited first; it was given no
# SERIAL, so had it run it would have force-stopped the app on the FIRST adb
# device rather than the sweep's; and its guard read a pid file in a 09-12
# state dir whose runner had been dead since 09-12. dispatcher.log (which
# starts 09-12 11:03) holds no "preempting the sweep" line at all. A path
# that has never run is not a feature, and this one carried a force-stop
# aimed at whichever device was listed first, so it was deleted rather than
# repaired. The corpus sweep is queue work now (z-sweep-* requests, sorted
# last by the claim loop), which yields to requests without any of this.
# sweep_queue.sh remains as a standalone tool and records its own device.

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

# THE DISPATCHER MUST NEVER INSTALL THE RELEASE PACKAGE (com.jreinach.hakux,
# no suffix): that is the owner's stable playtest channel (owner_build.sh,
# the nightly), and a lane's run reinstalling over it would make "which
# build is this" unanswerable the same way the debug app already was (#433).
#
# _build_ref_locked only ever runs `assembleDebug` and copies the `debug`
# variant's output, so there is today no path from here to a release apk --
# but that is an invariant of this file's code, not of the apk on disk, and
# it is cheap to check the thing that is actually installed rather than trust
# that nothing upstream changed. A release apk's compiled manifest carries
# its applicationId as a plain string in AndroidManifest.xml's string pool
# (usually UTF-16LE); this looks for the bare id with no following "." --
# which is what a debug or debug2 suffix would add -- so `com.jreinach.hakux`
# alone refuses and `com.jreinach.hakux.debug` does not.
#
# A file zipfile cannot open (including the empty placeholder selftest.d's
# fakes use in place of a real build) is NOT refused: there is nothing to
# read the applicationId from, and failing closed here would block every
# test that fakes build_ref. The real guarantee is structural (above); this
# is defense in depth against a future change to build_ref, not the only
# thing standing between a lane and the release package.
guard_not_release_apk() {   # <apk path> ; 0 = fine to install, 1 = refuse
    local apk="$1"
    [ -s "$apk" ] || return 0
    python3 - "$apk" <<'PY' 2>/dev/null
import re, sys, zipfile
try:
    with zipfile.ZipFile(sys.argv[1]) as z:
        manifest = z.read("AndroidManifest.xml")
except Exception:
    sys.exit(0)
needle = "com.jreinach.hakux"
text = manifest.decode("utf-16-le", "ignore") + "\n" + manifest.decode("utf-8", "ignore")
sys.exit(1 if re.search(re.escape(needle) + r'(?![.\w])', text) else 0)
PY
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

# THE MASTER RESTORE (10-06). A run that left its handheld on a test build (a
# branch ref, an env_vars A/B) is followed by a 60 s master run queued here, so
# the next measurement does not start on that build. device_build.py decides
# whether this run needs one and writes the request into queue/; it writes
# nothing for a run already on master, or for a restore itself. A failure here
# is logged and never fails the run it follows.
queue_master_restore() {   # $1 = run id (results/<id>)
    local out
    # DISPATCH_REPO: $HERE is the snapshot in a worker ($HERE *is* $SNAP
    # there, see the comment above SRC), which has no .git above it, so
    # device_build.py's own ancestry check needs the real repo named
    # explicitly rather than guessed from its own path.
    out=$(DISPATCH_REPO="$REPO" python3 "$HERE/jobs/device_build.py" restore "$D" "$DEVICE_LABEL" "$1" 2>&1) \
        && { [ -z "$out" ] || log "  master restore queued: $out"; } \
        || log "  master restore NOT queued for $1: $out"
    return 0
}

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

# PER-RUN BATTERY ADMISSION (#507, owner 2026-09-28). A handheld on its 500 mA
# port was taken out of service below 15 % and put back only at 80 %, about
# eleven hours, while a queue of 6-8 minute runs it could have served at 24 %
# waited. So each request is admitted on its own: only when the level covers
# 15 % + 5 % + the learned drain over the run. battery_admit.py has the rule,
# the learning, and why a long head is not starved by the short runs behind it.
#
# battery_level: dumpsys's `level:`, read at most once a minute (the queue walk
# asks once per request per tick). Empty when it cannot be read; the caller
# then claims nothing (battery_unreadable).
battery_level() {
    local f="$D/.battery_level.$DEVICE_LABEL" now t l
    now=$(date +%s)
    if read -r t l < "$f" 2>/dev/null && [ -n "$l" ] \
       && [ $((now - t)) -lt "${BATTERY_CACHE_S:-60}" ]; then
        printf '%s\n' "$l"; return 0
    fi
    l=$(ADB_RETRIES=0 adb_call "${ADB_QUICK_TIMEOUT:-30}" "battery level" shell dumpsys battery 2>/dev/null \
        | tr -d '\r' | sed -n 's/^ *level: *\([0-9][0-9]*\) *$/\1/p' | head -1)
    [ -n "$l" ] || return 0
    printf '%s %s\n' "$now" "$l" > "$f"
    printf '%s\n' "$l"
}

# battery_admit <req> <id> -> 0 to claim it, 1 not now. Sets BATT_JSON (what
# result.json records) on 0, and BATT_HEAD -- the first request this tick
# refused, the device's head -- on the first refusal. Each distinct line is
# logged once per request, not every five seconds.
declare -A BATT_SAID=()
BATT_UNREAD_SINCE=""
# battery_unreadable <id>: FAIL CLOSED. The first live hours admitted a run
# unchecked on an unreadable level (16:41:17 on 09-28) while the Nova's USB
# link was failing, and the run voided. An unreadable level almost always IS
# that link, so nothing is claimed; the next walk reads again. One read per
# walk (BATT_WALK_UNREAD), one line per episode, and one when it recovers.
battery_unreadable() {
    BATT_WALK_UNREAD=1
    if [ -z "$BATT_UNREAD_SINCE" ]; then
        BATT_UNREAD_SINCE=$(date +%s)
        log "BATTERY: level unreadable on $DEVICE_LABEL; not claiming $1, reading again at the next walk"
    fi
}
battery_admit() {
    local req="$1" id="$2" level out rc line
    BATT_JSON=""
    [ "${BATTERY_ADMIT:-on}" = off ] && return 0
    [ -z "${BATT_WALK_UNREAD:-}" ] || return 1
    level=$(battery_level)
    [ -n "$level" ] || { battery_unreadable "$id"; return 1; }
    if [ -n "$BATT_UNREAD_SINCE" ]; then
        log "BATTERY: level readable again on $DEVICE_LABEL ($level) after $(( $(date +%s) - BATT_UNREAD_SINCE ))s unreadable"
        BATT_UNREAD_SINCE=""
    fi
    out=$(python3 "$HERE/battery_admit.py" check "$D" "$DEVICE_LABEL" "$req" "$level" "${BATT_HEAD:-}")
    rc=$?
    line=$(printf '%s\n' "$out" | sed -n 1p)
    case "$rc" in
        0) BATT_JSON=$(printf '%s\n' "$out" | sed -n 2p); log "$line"; unset "BATT_SAID[$id]"; return 0 ;;
        1) [ -n "${BATT_HEAD:-}" ] || BATT_HEAD="$id" ;;
        3) ;;
        *) # The helper itself failed: admit, as for an unreadable level.
           log "BATTERY: battery_admit.py exited $rc on $id; admitting unchecked: $line"
           BATT_JSON='{"battery_start": '"$level"', "unchecked": "battery_admit.py failed"}'
           return 0 ;;
    esac
    # Level and need change slowly; say it again only when the words change.
    # The head's refusal line and the hold line each carry a running clock,
    # so compare without it.
    local key
    key=$(printf '%s\n' "$line" | sed 's/; head, refused for [0-9]*s$//; s/ (refused for [0-9]*s >= [0-9]*s)//')
    if [ "${BATT_SAID[$id]:-}" != "$key" ]; then
        BATT_SAID[$id]="$key"
        log "$line"
    fi
    return 1
}

# serve_queue <req>... -> 0 once one is served. The queue walk, in priority
# order; BATT_HEAD is per walk, so a head is the first refusal of THIS tick.
serve_queue() {
    BATT_HEAD="" BATT_WALK_UNREAD=""
    local r
    for r in "$@"; do
        serve_one "$r" && return 0
    done
    return 1
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
    # Battery after affinity (a request pinned elsewhere costs no adb read) and
    # before the claim, so a refusal leaves it in the queue for the next tick,
    # or for the other handheld.
    battery_admit "$req" "$id" || return 1
    # Losing this rename means the other worker claimed it first, which is the
    # mutex working. Also non-zero: try the next one.
    mv "$req" "$D/running/$id.req" 2>/dev/null || return 1
    printf '%s\n' "$DEVICE_LABEL" > "$D/running/$id.owner"
    req="$D/running/$id.req"
    # Per device and per request: a hang recorded here is THIS request's.
    export ADB_HUNG_FILE="$D/.adb_hung.${DEVICE_LABEL:-$SERIAL}"
    rm -f "$ADB_HUNG_FILE"
    # Say so if that `want` above was decided over an empty device set.
    lane_blind_check "$id"
    local requester purpose ref arm runs
    requester=$(jq_get "$req" requester unknown)
    purpose=$(jq_get "$req" purpose "")
    ref=$(jq_get "$req" ref HEAD)
    arm=$(jq_get "$req" arm company)
    runs=$(jq_get "$req" runs 1)
    local title seconds pull_glob audio_capture frames_every video_seconds video_after
    title=$(jq_get "$req" title "")
    seconds=$(jq_get "$req" seconds 60)
    pull_glob=$(jq_get "$req" pull_glob "")
    # Screen frames during a soak, off unless the request asks. See
    # start_frame_capture.
    frames_every=$(jq_get "$req" frames_every 0)
    # A video of the screen during a soak, off unless the request asks. See
    # start_soak_video.
    video_seconds=$(jq_get "$req" video_seconds 0)
    video_after=$(jq_get "$req" video_after 30)
    # Arming the APU PCM capture is per REQUEST, not device state left lying
    # around. See arm_audio in soak_title.sh for the two ways the persistent
    # marker went wrong on 2026-09-12 -- in both directions, on the same day.
    audio_capture=$(jq_get "$req" audio_capture "")
    log "request $id from $requester: $purpose (ref=$ref arm=$arm runs=$runs)"

    local rdir="$D/results/$id"; mkdir -p "$rdir"
    # What admitted it: level, need, rate. Both result.json writers carry it as
    # `battery`, so a later check can ask whether a low-charge run measured
    # differently. battery_admit.py learns overhead from its `t_device`.
    [ -z "$BATT_JSON" ] || printf '%s\n' "$BATT_JSON" > "$rdir/battery.json"
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

    if ! guard_not_release_apk "$apk"; then
        echo "refusing to install $apk: it reports applicationId com.jreinach.hakux (the release package); the dispatcher may only install a debug-suffixed build" > "$rdir/ERROR"
        log "  REFUSING RELEASE INSTALL"
        mv "$req" "$rdir/request.json"; return 0
    fi

    if ! device_present; then
        log "  device absent; requeueing"
        mv "$req" "$D/queue/$id.req"; sleep 30; return 0
    fi
    # The device's part of this request starts here, not at the claim: the
    # build before it drains nothing.
    [ ! -f "$rdir/battery.json" ] || python3 -c 'import json,sys,time
p=sys.argv[1]; b=json.load(open(p)); b["t_device"]=time.time(); json.dump(b,open(p,"w"))' "$rdir/battery.json" 2>/dev/null
    # A save-state load's disk, by name and on the device, before anything is
    # installed or launched (see A SCENE BOOTS A COPY). No load, no adb call.
    local shrc; scene_hdd_check "$req" "$rdir"; shrc=$?
    if [ "$shrc" = 3 ]; then
        echo "refused before the install: $(cat "$rdir/scene_hdd.refused" 2>/dev/null)" > "$rdir/ERROR"
        log "  SCENE HDD REFUSED"
        mv "$req" "$rdir/request.json"; return 0
    elif [ "$shrc" != 0 ]; then
        adb_error "could not check the scene's hdd on the device; see dispatcher.log" > "$rdir/ERROR"
        log "  SCENE HDD CHECK FAILED"
        mv "$req" "$rdir/request.json"; return 0
    fi
    adb_call "$ADB_INSTALL_TIMEOUT" "adb install -r" install -r "$apk" 2>&1 | grep -q Success || {
        adb_error "install failed" > "$rdir/ERROR"; log "  INSTALL FAILED: $(cat "$rdir/ERROR")"
        mv "$req" "$rdir/request.json"; maybe_run_doctor "$id" "$rdir"; return 0
    }
    if ! clear_shader_caches_on_apk_change "$sha"; then
        adb_error "could not clear the shader caches for a new apk; see dispatcher.log" > "$rdir/ERROR"
        log "  SHADER CACHE CLEAR FAILED"
        mv "$req" "$rdir/request.json"; return 0
    fi

    # AFTER the install and BEFORE either run path, because both of them start
    # the app and neither may start it with the previous request's environment
    # still in the pref. See apply_env_pref: on a request with no `env` and no
    # marker this costs zero adb calls.
    local req_env=""
    if ! apply_env_pref "$req"; then
        adb_error "could not set the requested env_vars pref; see dispatcher.log" > "$rdir/ERROR"
        log "  ENV SETUP FAILED"
        mv "$req" "$rdir/request.json"; maybe_run_doctor "$id" "$rdir"; return 0
    fi
    req_env=$(python3 -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1])).get('env') or []))" "$req" 2>/dev/null || echo "[]")
    # A title run that never reached titles_disk_after left hddPath on the
    # titles disk, and a disc run that never reached disc_hdd_after left it on
    # hdd.img with the owner's path in the marker; no run may start on the wrong
    # one, and this is also what makes the one marker safe to share (see
    # disc_hdd_prepare). No marker, no adb call.
    if ! restore_hdd_pref; then
        adb_error "could not restore hddPath after an earlier title or disc run; see dispatcher.log" > "$rdir/ERROR"
        log "  HDD PREF RESTORE FAILED"
        mv "$req" "$rdir/request.json"; return 0
    fi
    # Same reasoning as restore_hdd_pref just above, for a scene's parked
    # slot files and savestate_auto_load: a dead earlier run must not leave
    # the device isolated on someone else's slot (#433).
    if ! restore_scene_pref; then
        adb_error "could not restore a scene's save-state slots after an earlier run; see dispatcher.log" > "$rdir/ERROR"
        log "  SCENE RESTORE FAILED"
        mv "$req" "$rdir/request.json"; return 0
    fi

    # THE MASTER RESTORE ENDS HERE. device_build.py queues it after a run off
    # master: no title and no suites. Its build, install and env reset above are
    # the whole job. The disc path refuses a request with no suites ("NO SUITES"),
    # so without this exit the restore is refused and the device keeps the test
    # build. The result.json written here is what device_build.py reads as the
    # device's newest run, so a restore that ran shows master and env [] there.
    if [ "$requester" = dispatch.restore ]; then
        python3 - "$rdir" "$sha" "$ref" "$requester" "$req_env" "$purpose" <<'PYEOF'
import json, os, sys
rdir, sha, ref, who, env, purpose = sys.argv[1:7]
json.dump(dict(kind="restore", apk_sha=sha, ref=ref, env=json.loads(env),
               requester=who, purpose=purpose, seconds=0,
               device_label=os.environ.get("DEVICE_LABEL", "")),
          open(os.path.join(rdir, "result.json"), "w"), indent=2)
PYEOF
        log "  master restore done: ref $ref binary $sha, env $req_env"
        mv "$req" "$rdir/request.json"
        rm -f "$D/running/$id.owner"
        touch "$rdir/DONE"
        return 0
    fi

    # A soak request runs a real title and keeps its log, instead of running a
    # test disc and scoring captures. It exists because some questions have no
    # golden framebuffer: the audio path is silent on the pgraph discs, so
    # "does any title actually program submix_headroom" can only be answered by
    # booting a game and reading the log. Same queue, same lease, same
    # preempt/resume, so it is scheduled against test work rather than racing
    # it -- and no human has to hold the handheld.
    if [ -n "$title" ]; then
        log "  soak: $title for ${seconds}s"
        touch "$LEASE"
        # Under the first of the device's roots that has it (devices.sh). A
        # miss is not immediately an ERROR (dispatchdoctor1017, #938-adjacent
        # owner word 2026-10-13, "it should know to copy the disk image ...
        # to the right location and not just fail"): try the deterministic
        # fast path once -- stage it from D:, or the console -- before
        # giving up on it.
        local tpath
        if ! tpath=$(device_title_path "$title"); then
            if ensure_title_staged "$title" "$rdir" "$req"; then
                tpath=$(device_title_path "$title") || tpath=""
            fi
            if [ -z "$tpath" ]; then
                # device_title_miss's own text goes LAST and unchanged: a
                # Nova (single-root) miss's ERROR is matched to end exactly
                # with "searched <root>" by jobs/selftest.d/99-iso-roots.sh,
                # which is not this lane's to edit. What staging found and
                # did (stage_summary, Section 3) goes first.
                adb_error "$(stage_summary "$rdir"); $(device_title_miss "$title")" > "$rdir/ERROR"
                log "  TITLE NOT FOUND"; mv "$req" "$rdir/request.json"
                # $(basename "$rdir"), not a bare $id: this line is inside the
                # soak block jobs/selftest.d/99-iso-roots.sh sed-extracts
                # verbatim and runs with only $title/$rdir/$req bound: see
                # ensure_title_staged's comment above, same constraint.
                maybe_run_doctor "$(basename "$rdir")" "$rdir"; return 0
            fi
        fi
        grep -q '^disc: ' "$rdir/inputs.txt" 2>/dev/null \
            || inputs_note "$rdir" disc "already on the device at $tpath"
        # Before the titles disk, which edits the same file: a build from
        # before libfolders needs the old games folder key to boot anything.
        if ! ensure_legacy_folder_pref; then
            adb_error "could not give x1box_prefs.xml the pre-libfolders gamesFolderUri; see dispatcher.log" > "$rdir/ERROR"
            log "  FOLDER PREF FAILED"; mv "$req" "$rdir/request.json"; return 0
        fi
        # Which title, and the state its route was written for (request.sh
        # --route, titlestate.py resolve-route). A request queued before that
        # carries neither: its title from the ISO name, state `any`.
        local ttid tstate tsave trc pbsearched scene_hdd dwhat
        ttid=$(jq_get "$req" title_id "")
        [ -n "$ttid" ] || ttid=$(python3 "$TITLESTATE" tid-for-iso "$title" 2>/dev/null)
        # A scene's own disk, in place of the titles disk (A SCENE BOOTS A COPY).
        scene_hdd=$(jq_get "$req" scene_hdd "")

        # --load-state/--scene (#433): isolate the named slot on the device
        # before anything else touches it, so every refusal path below has
        # something to restore_scene_pref back from.
        if ! set_scene_pref "$req" "$rdir" "$ttid"; then
            adb_error "could not set up the requested save-state slot; see dispatcher.log" > "$rdir/ERROR"
            log "  SCENE SETUP FAILED"
            restore_scene_pref
            mv "$req" "$rdir/request.json"; return 0
        fi

        # dispatchdoctor1017 Section 1b: a request with no route (or only
        # the generic survey) gets one attached here, before tstate/tsave
        # are read, so a route this call attaches is seen by everything
        # below exactly as a user's own --route would be.
        if ! ensure_route_attached "$ttid" "$title" "$rdir" "$req"; then
            echo "refused before the soak: $(cat "$rdir/route.refused" 2>/dev/null)" > "$rdir/ERROR"
            log "  ROUTE ATTACH REFUSED: $(cat "$rdir/route.refused" 2>/dev/null)"
            restore_hdd_pref
            restore_scene_pref
            mv "$req" "$rdir/request.json"; return 0
        fi

        tstate=$(jq_get "$req" title_state any)
        tsave=$(jq_get "$req" save "")

        # THE PROFILE GATE, RE-CHECKED AT CLAIM (lane.profilegate1011, #433).
        # request.sh already ran this at queue time, but nothing is
        # grandfathered here: a request written straight into dispatch/queue
        # (no request.sh) is checked exactly like any other. Before
        # titles_disk_prepare, so a refused run never touches the disk.
        if ! profile_gate_check "$req" "$rdir" "$ttid"; then
            log "  PROFILE GATE REFUSED: $(cat "$rdir/profile.refused" 2>/dev/null)"
            printf 'refused before the soak: no profile: %s\n' "$(cat "$rdir/profile.refused" 2>/dev/null)" > "$rdir/ERROR"
            restore_hdd_pref
            restore_scene_pref
            mv "$req" "$rdir/request.json"; return 0
        fi

        # dispatchdoctor1017 Section 1c: before titles_disk_prepare's own
        # compose call can refuse "no golden profile", give an
        # existing-but-not-yet-golden backup a chance to become this
        # title's FIRST golden (never a replace).
        ensure_profile_restored "$ttid" "$tstate" "$rdir" "$req"

        if [ -n "$scene_hdd" ]; then
            dwhat="the scene's disk $scene_hdd"
            scene_hdd_prepare "$rdir" "$req"; trc=$?
        else
            dwhat="the titles disk"
            titles_disk_prepare "$id" "$rdir" "$req_env" "$ttid" "$tstate" "$tsave"; trc=$?
        fi
        if [ "$trc" = 3 ]; then
            pbsearched=$(python3 -c 'import json,sys
try: print(", ".join(json.load(open(sys.argv[1])).get("searched") or []))
except Exception: print("")' "$rdir/profile-backup.json" 2>/dev/null)
            echo "refused before the soak: the titles disk cannot carry what the route assumes: $(cat "$rdir/hdd.refused" 2>/dev/null)${pbsearched:+ (profile backup search looked at: $pbsearched)}" > "$rdir/ERROR"
            log "  TITLES DISK REFUSED"
            restore_hdd_pref
            restore_scene_pref
            mv "$req" "$rdir/request.json"; return 0
        elif [ "$trc" != 0 ]; then
            adb_error "could not prepare $dwhat; see dispatcher.log" > "$rdir/ERROR"
            log "  TITLES DISK SETUP FAILED ($dwhat)"
            scene_hdd_after "$rdir"
            restore_scene_pref
            mv "$req" "$rdir/request.json"; maybe_run_doctor "$id" "$rdir"; return 0
        fi
        # The scene's copy carries the owner's profile, not a composed save.
        trc=0
        [ -n "$scene_hdd" ] || { verify_profile_on_device "$ttid" "$tstate" "$rdir"; trc=$?; }
        if [ "$trc" = 3 ]; then
            echo "refused before the soak: $(cat "$rdir/hdd.refused" 2>/dev/null)" > "$rdir/ERROR"
            log "  PROFILE VERIFY REFUSED"
            restore_hdd_pref
            restore_scene_pref
            mv "$req" "$rdir/request.json"; return 0
        fi
        # The route's text travels in the request (request.sh --route); the
        # file soak_title.sh plays is written from it here, beside the result.
        python3 -c 'import json,sys; r=json.load(open(sys.argv[1])).get("route") or ""; r and open(sys.argv[2],"w").write(r.rstrip("\n")+"\n")' "$req" "$rdir/route.txt"
        refmsg=$(write_route_refs "$rdir" "$req") || {
            echo "refused before the soak: ${refmsg:-a route_refs entry failed validation}" > "$rdir/ERROR"
            log "  ROUTE REFS REFUSED: ${refmsg:-?}"
            scene_hdd_after "$rdir"
            restore_scene_pref
            mv "$req" "$rdir/request.json"; return 0
        }
        # The soak below passes TITLE_ID/TITLE_NAME and the two dirs to drive.py
        # through route.sh (routebuild1021): the title's book is read from, and
        # written back to, $D/paths (pathbook.py; the repo's pathfind paths ship
        # in the snapshot, read-only), and what drive.py learns on unnamed
        # screens goes to $D/learned -- both outside $SNAP, which is rebuilt.
        start_frame_capture "$rdir" "$frames_every" "$seconds"
        start_soak_video "$rdir" "$video_seconds" "$video_after" "$([ -s "$rdir/route.txt" ] && echo 1 || echo 0)" "$seconds"
        start_scene_watch "$rdir" "$req"
        SERIAL="$SERIAL" CAPTURE_LOG="$rdir/logcat.txt" \
            PULL_GLOB="$pull_glob" PULL_DEST="$rdir/pulled" \
            AUDIO_CAPTURE_MB="$audio_capture" \
            ROUTE_FILE="$([ -s "$rdir/route.txt" ] && echo "$rdir/route.txt")" \
            TITLE_ID="$ttid" TITLE_NAME="$title" HAKUX_PATHS_DIR="$D/paths" HAKUX_LEARNED_DIR="$D/learned" \
            bash "$HERE/soak_title.sh" "$tpath" "$seconds" >>"$rdir/run.log" 2>&1
        # Before the result is written, so the count in result.json is final,
        # and unconditionally, so an early guest exit does not leave a
        # screencap loop running against the next request's title.
        stop_frame_capture
        stop_soak_video
        stop_scene_watch
        if [ -n "$scene_hdd" ]; then
            scene_hdd_after "$rdir"
        else
            titles_disk_after "$id" "$rdir"
        fi
        local scene_void; scene_void=$(scene_verdict "$rdir" "$req" "$sha")
        restore_scene_pref || log "  WARNING: scene slots not restored; the next request retries"
        [ -z "$scene_void" ] || log "  SCENE VOID: $scene_void"
        local lines; lines=$(wc -l < "$rdir/logcat.txt" 2>/dev/null || echo 0)
        python3 - "$rdir" "$sha" "$title" "$seconds" "$requester" "$purpose" "$ref" "$lines" "$req_env" "$frames_every" <<'PYEOF'
import json, os, sys
(rdir, sha, title, seconds, who, purpose, ref, lines, req_env,
 frames_every) = sys.argv[1:11]
scene_path = os.path.join(rdir, "scene.json")
scene = json.load(open(scene_path)) if os.path.exists(scene_path) else None
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
def _battery(rdir):
    try:
        return json.load(open(os.path.join(rdir, "battery.json")))
    except (OSError, ValueError):
        return None
# WHICH DISK THE TITLE BOOTED (titles_disk_prepare): its device path, sha256
# at the start, the plans that made it current, and what the post-run
# harvest found. None before the split existed. A scene's own disk
# (scene_hdd_prepare) carries `pref`: how hddPath was moved and put back.
def _hdd(rdir):
    try:
        h = json.load(open(os.path.join(rdir, "hdd.json")))
    except (OSError, ValueError):
        return None
    for key, name in (("after", "hdd.after.json"), ("pref", "hdd_scene.json")):
        try:
            h[key] = json.load(open(os.path.join(rdir, name)))
        except (OSError, ValueError):
            pass
    return h
# THE SCREEN VIDEO, read straight from the mp4: there is no ffmpeg or
# ffprobe on this host and none is installed. `mvhd` (inside `moov`) gives
# the movie's timescale and duration; `stsz` (moov/trak/mdia/minf/stbl)
# gives the sample count in its fourth 4-byte field regardless of whether
# samples are constant-size (its own third field nonzero, no per-sample
# table after it) or not -- both forms carry sample_count at that offset.
def _mp4_info(path):
    try:
        data = open(path, "rb").read()
    except OSError:
        return 0.0, 0
    def boxes(start, end):
        pos, out = start, []
        while pos + 8 <= end:
            size = int.from_bytes(data[pos:pos + 4], "big")
            typ = data[pos + 4:pos + 8].decode("latin1", "replace")
            hdr = 8
            if size == 1 and pos + 16 <= end:
                size = int.from_bytes(data[pos + 8:pos + 16], "big"); hdr = 16
            elif size == 0:
                size = end - pos
            if size < hdr:
                break
            out.append((typ, pos + hdr, pos + size))
            pos += size
        return out
    def find(start, end, path):
        for typ, s, e in boxes(start, end):
            if typ == path[0]:
                if len(path) == 1:
                    return s, e
                sub = find(s, e, path[1:])
                if sub:
                    return sub
        return None
    duration_s, samples = 0.0, 0
    mvhd = find(0, len(data), ["moov", "mvhd"])
    if mvhd:
        s, _ = mvhd
        if data[s] == 1:   # version 1: 64-bit times
            timescale = int.from_bytes(data[s + 20:s + 24], "big")
            duration = int.from_bytes(data[s + 24:s + 32], "big")
        else:
            timescale = int.from_bytes(data[s + 12:s + 16], "big")
            duration = int.from_bytes(data[s + 16:s + 20], "big")
        duration_s = round(duration / timescale, 3) if timescale else 0.0
    stsz = find(0, len(data), ["moov", "trak", "mdia", "minf", "stbl", "stsz"])
    if stsz:
        s, _ = stsz
        samples = int.from_bytes(data[s + 8:s + 12], "big")
    return duration_s, samples
# THE VIDEO, written even when it was off (video/meta.json always exists --
# see start_soak_video / _soak_video_meta), for the same cost reason as
# `frames`: a video soak costs encoder and GPU time a clean soak does not,
# so a reader pooling the two has to see this field to do it.
def _video(rdir):
    try:
        v = json.load(open(os.path.join(rdir, "video", "meta.json")))
    except (OSError, ValueError):
        return dict(seconds=0, after=0, mark_wall=None, segments=[], bytes=0,
                    skipped="video/meta.json missing (video capture did not run)")
    for seg in v.get("segments", []):
        d, n = _mp4_info(os.path.join(rdir, "video", seg["file"]))
        seg["duration_s"] = d
        seg["samples"] = n
    return v
json.dump(dict(apk_sha=sha, kind="soak", title=title, seconds=int(seconds),
               hdd=_hdd(rdir),
               requester=who, purpose=purpose, ref=ref,
               logcat=dict(spec=_spec, lines=int(lines)),
               device_serial=os.environ.get("SERIAL", ""),
               device_label=os.environ.get("DEVICE_LABEL", ""),
               logcat_lines=int(lines), pulled=pulled,
               # Cold or warm shader cache: a cleared cache puts shader
               # warm-up in the first minute of a frame-rate soak.
               shader_cache=os.environ.get("SHADER_CACHE_STATE", ""),
               # Whether the old games folder key had to be put back for a
               # build from before libfolders (ensure_legacy_folder_pref).
               folder_pref=os.environ.get("FOLDER_PREF_STATE", ""),
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
                           dir="frames" if _frames else None),
               video=_video(rdir),
               # What admitted it (battery_admit.py): battery_start, need,
               # rate. None when the run predates admission or it was off.
               battery=_battery(rdir),
               # --load-state/--scene (#433): None when the request named no
               # scene. void is loud and specific (no op=load within 30s, a
               # refused state, or a mid-run op=save) -- never a silent run
               # from the title screen; a reader that only checks `void` at
               # the top level catches a scene request exactly like any
               # other voided run.
               scene=scene,
               void=(scene or {}).get("void") if scene else None),
          open(os.path.join(rdir, "result.json"), "w"), indent=2)
print("soak done:", title, lines, "log lines")
PYEOF
        log "  soak done, $lines log lines -> $rdir/logcat.txt$(
            [ -d "$rdir/frames" ] && printf ', %s frames' "$(ls "$rdir/frames" | wc -l)")"
        mv "$req" "$rdir/request.json"
        rm -f "$D/running/$id.owner"
    queue_master_restore "$id"
    touch "$rdir/DONE"
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
    local base_iso program
    base_iso=$(jq_get "$req" base_iso "")
    # WHICH TEST PROGRAM the disc carries. "pgraph" is every request before
    # this field existed. "vsh" is nxdk_vsh_tests: a different config file, a
    # different output directory, and a result that is diffed against the
    # console's printed values rather than scored against pgraph goldens -- so
    # it has no stock disc to fall back to, and a vsh request without its own
    # base_iso is refused here rather than built from the pgraph disc.
    program=$(jq_get "$req" program pgraph)
    case "$program" in
        pgraph) ;;
        vsh)
            if [ -z "$base_iso" ]; then
                echo "program vsh needs a base_iso; there is no stock vsh disc" > "$rdir/ERROR"
                log "  VSH WITHOUT BASE ISO -- refusing"
                mv "$req" "$rdir/request.json"
                return 0
            fi ;;
        *)
            echo "unknown program '$program'" > "$rdir/ERROR"
            log "  UNKNOWN PROGRAM $program -- refusing"
            mv "$req" "$rdir/request.json"
            return 0 ;;
    esac
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
# A vsh disc is a different PROGRAM, not a different composition of the same
# one. The prefix keeps its id from ever equalling a pgraph disc_id, so no
# pgraph comparison can pair with it even on a suite name the two might share.
if r.get('program', 'pgraph') == 'vsh':
    pre = 'vsh:' + pre
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

    hdd_img_guard "$rdir"
    # The disc boots hdd.img whatever hddPath said when the request arrived. A
    # pref that names another image and cannot be moved refuses the run: the
    # guest would write its output into that image (the owner's, on the Nova).
    if ! disc_hdd_prepare "$rdir"; then
        adb_error "could not point hddPath at hdd.img for this disc run (it names ${DISC_HDD_WAS:-nothing readable}); a disc must not run on another image; see dispatcher.log" > "$rdir/ERROR"
        log "  HDD PREF SET FAILED"
        disc_hdd_after "$rdir"
        mv "$req" "$rdir/request.json"; maybe_run_doctor "$id" "$rdir"; return 0
    fi
    local r
    for r in $(seq 1 "$runs"); do
        local args=() gdir="d$(echo "$id$r" | md5sum | cut -c1-6)"
        local s
        if [ "$program" = vsh ]; then
            # nxdk_vsh_tests: vsh_tests.cnf, not the pgraph JSON, and no
            # output-dir to choose -- from DVD it always writes
            # e:\nxdk_vsh_tests. make_test_iso.py reads the program off the
            # image and refuses a mismatch, an unknown suite, or a rebooting
            # build; a refusal here is the request's ERROR, not a run that
            # burns 900 s on a hung guest.
            gdir="nxdk_vsh_tests"
            for s in "${SUITE_LIST[@]}"; do args+=(--suite "$s"); done
            if ! python3 "$HERE/make_test_iso.py" "$base_iso" --program vsh \
                    -o "$rdir/disc$r.iso" "${args[@]}" >>"$rdir/run$r.log" 2>&1; then
                { echo "make_test_iso.py refused the vsh disc:"
                  tail -3 "$rdir/run$r.log" | sed 's/^/  /'; } > "$rdir/ERROR"
                log "  VSH DISC REFUSED"
                rm -f "$rdir/disc$r.iso"; mv "$req" "$rdir/request.json"
                disc_hdd_after "$rdir"
                return 0
            fi
            touch "$LEASE"
            PROGRAM=vsh SERIAL="$SERIAL" DEVICE_ISO_ROOT="$DEVICE_ISO_ROOT" \
                DEVICE_LABEL="$DEVICE_LABEL" HAKUX_DEVICE_LEASE="$LEASE" \
                CAPTURE_LOG="$rdir/logcat$r.txt" \
                bash "$HERE/run_disc.sh" "$rdir/disc$r.iso" "$gdir" \
                "$rdir/captures$r" 900 >>"$rdir/run$r.log" 2>&1
            # Scored whatever it returned, so the verdict it reached (TIMEOUT,
            # INCOMPLETE, STALE LOG) goes in the result, not only in run$r.log.
            echo $? > "$rdir/run_disc$r.rc"
            rm -f "$rdir/disc$r.iso"
            local vsuites=()
            for s in "${SUITE_LIST[@]}"; do vsuites+=(--suite "$s"); done
            python3 "$HERE/vsh_score.py" "$rdir/captures$r" "${vsuites[@]}" \
                --json "$rdir/vsh$r.json" --tsv "$rdir/vsh$r.tsv" \
                > "$rdir/vsh$r.txt" 2>&1
            continue
        fi
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
    # The runs are over: hddPath goes back to what it was (nothing to do when
    # it was already hdd.img). Before the result is written, so every return
    # below leaves the pref as the owner had it.
    disc_hdd_after "$rdir"

    REQ_ENV_JSON="$req_env" \
    python3 - "$rdir" "$sha" "$disc_id" "$requester" "$purpose" "$ref" "$SNAP" "$program" <<'PYEOF'
import csv, glob, json, os, subprocess, sys
rdir, sha, disc, who, purpose, ref, snap, program = sys.argv[1:9]
meta = dict(apk_sha=sha, disc_id=disc, requester=who, purpose=purpose, ref=ref)
# WHICH PROGRAM RAN. Every result says so, pgraph included, so that "absent"
# never has to be read as "pgraph": a reader pooling results filters on this
# field, and a vsh result also carries kind "vsh", which no pgraph reader
# (ab_compare, scoreboard, sweep tooling) treats as a disc result.
meta["program"] = program
if program == "vsh":
    meta["kind"] = "vsh"
# THE ENVIRONMENT THIS RUN ACTUALLY RAN WITH, deliberately NOT folded into
# disc_id. disc_id says whether two runs scored the same captures, and an env
# A/B scores exactly the same captures on purpose -- putting env in there would
# make ab_compare refuse the one comparison this field was added to enable. It
# is the independent variable, not part of the disc, and ab_compare reads it as
# such. A result with no `env` key predates the feature; `env: []` means it was
# checked and there was none.
meta["env"] = json.loads(os.environ.get("REQ_ENV_JSON") or "[]")
# Whether this run started on a cleared shader cache (clear_shader_caches_on_
# apk_change): "cleared: apk X -> Y", "kept: ...", or "" before the field.
meta["shader_cache"] = os.environ.get("SHADER_CACHE_STATE", "")
# hdd_img_guard: present only when hdd.img was past its limit before this run.
try:
    meta["hdd_guard"] = json.load(open(os.path.join(rdir, "hdd_guard.json")))
except (OSError, ValueError):
    pass
# disc_hdd_prepare: what hddPath was, what the disc run set it to, and whether
# it was put back.
try:
    meta["hdd_disc"] = json.load(open(os.path.join(rdir, "hdd_disc.json")))
except (OSError, ValueError):
    pass
# A run run_disc.sh refused for its disk (WRONG HDD / HDD UNKNOWN) is not a run
# that scored 0: it is named here, and the request fails on it below.
hdd_verdicts = []
for lg in sorted(glob.glob(os.path.join(rdir, "run*.log"))):
    for line in open(lg, errors="replace"):
        if line.startswith(("WRONG HDD:", "HDD UNKNOWN:")):
            hdd_verdicts.append(dict(file=os.path.basename(lg), verdict=line.strip()))
            break
if hdd_verdicts:
    meta["hdd_verdicts"] = hdd_verdicts
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
# Keep equal to score_sweep.py's SCORED_STATUSES (selftest fragment
# 51-dispatch-hardening.sh checks). A row outside it -- `unreadable` after a
# truncated pull, above all -- carries differing=0 because there is no number,
# so it is neither a capture nor exact. Counting it as both is how #224's fix
# arm recorded 110 of 110 W_param while score_sweep said 54 of 110.
SCORED_STATUSES = ("ok", "blank", "label-differs", "white-content")
runs = []
for t in sorted(glob.glob(os.path.join(rdir, "scores*.tsv"))):
    every = [r for r in csv.DictReader(open(t), delimiter="\t") if r.get("suite")]
    rows = [r for r in every if r.get("status") in SCORED_STATUSES]
    unscored = {}
    for r in every:
        if r.get("status") not in SCORED_STATUSES:
            unscored[r.get("status") or "?"] = unscored.get(r.get("status") or "?", 0) + 1
    # A run counts only if its own progress log shows tests completing.
    logdir = t.replace("scores", "captures").replace(".tsv", "")
    plog = os.path.join(logdir, "pgraph_progress_log.txt")
    proof = "completed normally" in open(plog, errors="replace").read() if os.path.exists(plog) else False
    runs.append(dict(tsv=os.path.basename(t), captures=len(rows),
                     exact=sum(1 for r in rows if int(r["differing"] or 0) == 0),
                     px=sum(int(r["differing"] or 0) for r in rows),
                     unscored=unscored,
                     progress_log_proof=proof))
# A vsh run has no scores TSV: vsh_score.py wrote a verdict per test against
# the console's printed values. `captures` counts the tests whose .txt came
# back from THIS run (a STALE file is an earlier run's), so the 0-captures
# failure below means the same thing for both programs.
for j in sorted(glob.glob(os.path.join(rdir, "vsh*.json"))):
    v = json.load(open(j))
    c = v.get("counts", {})
    rcf = os.path.join(rdir, "run_disc%s.rc" % os.path.basename(j)[3:-5])
    rc = int(open(rcf).read().strip()) if os.path.exists(rcf) else None
    runs.append(dict(json=os.path.basename(j),
                     captures=sum(c.get(k, 0) for k in ("IDENTICAL", "DIFFERS", "NO-REFERENCE")),
                     identical=c.get("IDENTICAL", 0), differs=c.get("DIFFERS", 0),
                     missing=c.get("MISSING", 0), stale=c.get("STALE", 0),
                     no_reference=c.get("NO-REFERENCE", 0),
                     log_completed=bool(v.get("log_completed")),
                     log_stale=bool(v.get("log_stale")),
                     run_disc_exit=rc,
                     staleness=v.get("staleness", "")))
# Which device produced this. A scoreboard column that mixes two handhelds
# is the same failure as one that mixes two binaries, and apk_sha could not
# catch that one either -- it was perfectly consistent and consistently old.
meta["device_serial"] = os.environ.get("SERIAL", "")
meta["device_label"] = os.environ.get("DEVICE_LABEL", "")
meta["runs"] = runs
# What admitted it (battery_admit.py): battery_start, need, rate.
try:
    meta["battery"] = json.load(open(os.path.join(rdir, "battery.json")))
except (OSError, ValueError):
    meta["battery"] = None

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
for s in sorted(suites if program != "vsh" else ()):
    gd = os.path.join("/home/justin/goldens/results", s)
    have = len([f for f in os.listdir(gd)]) if os.path.isdir(gd) else 0
    got = sum(1 for t in sorted(glob.glob(os.path.join(rdir, "scores1.tsv")))
              for row in csv.DictReader(open(t), delimiter="\t")
              if row.get("suite") == s and row.get("status") in SCORED_STATUSES)
    cov[s] = dict(scored=got, goldens=have,
                  partial=bool(have and got < have))
meta["captures_vs_goldens"] = cov
if program == "vsh":
    # The oracle is the console's text, not the golden tree; say which.
    meta["vsh_scorer_sha256"] = "unknown"
    try:
        import hashlib
        with open(os.path.join(snap, "vsh_score.py"), "rb") as fh:
            meta["vsh_scorer_sha256"] = hashlib.sha256(fh.read()).hexdigest()[:12]
    except Exception:
        pass
json.dump(meta, open(os.path.join(rdir, "result.json"), "w"), indent=2)
print("captures:", sum(r["captures"] for r in runs),
      "partial:", [s for s, c in cov.items() if c["partial"]])
PYEOF

    local got; got=$(python3 -c "
import json,sys
m=json.load(open(sys.argv[1]))
print(sum(r['captures'] for r in m['runs']))" "$rdir/result.json" 2>/dev/null || echo 0)
    mv "$req" "$rdir/request.json"
    # A run on a disk other than the one the harness reads is not a run, and
    # it is not "0 captures" either: the verdict run_disc.sh wrote is the
    # ERROR, first line, where the doctor keys on it. Checked ahead of the
    # zero-capture block, whose generic text sent the doctor looking at the
    # extractor.
    local hdd_bad; hdd_bad=$(grep -hs -m1 -E '^(WRONG HDD|HDD UNKNOWN):' "$rdir"/run*.log | head -1)
    if [ -n "$hdd_bad" ]; then
        adb_error "$hdd_bad" > "$rdir/ERROR"
        log "  FAILED: $(head -1 "$rdir/ERROR")"
        maybe_run_doctor "$id" "$rdir"
        return 0
    fi
    if [ "${got:-0}" = "0" ]; then
        # Zero captures is a failed run, not a result of zero. Handing a
        # requester an empty TSV as if it were an answer is how "this suite
        # renders nothing" gets believed.
        #
        # AND ZERO WITH THE WSL INTEROP SIGNATURE IN THE LOG IS A LOST PULL,
        # not a failed run. 1790325543-arms-vshconst-base logged four
        # `UtilAcceptVsock ... accept4 failed 110`, "pull failed or timed out"
        # and nothing else, and its pair came back ARM ERROR; the next one lost
        # its captures after a logcat showing a normal run. Say which it was,
        # and run it once more: the attempt is moved aside to <id>.interop1 so
        # the rerun gets a clean result dir, and a second loss is final.
        local msg="ran but produced 0 captures; see run1.log and captures1/"
        local crash; crash=$(grep -h -m1 "emulator started and CRASHED" "$rdir"/run*.log 2>/dev/null | head -1)
        if [ -n "$crash" ]; then
            msg="0 captures: $crash"
        elif grep -qs "UtilAcceptVsock" "$rdir"/run*.log; then
            msg="adb interop failure: 0 captures, and run*.log carries the WSL UtilAcceptVsock signature -- the captures were lost between device and host, not unrendered"
            if [ -z "$(jq_get "$rdir/request.json" interop_requeued "")" ] &&
               python3 - "$rdir/request.json" "$D/queue/$id.req" <<'PYEOF'
import json, sys, time
r = json.load(open(sys.argv[1]))
r["interop_requeued"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(r, open(sys.argv[2], "w"), indent=2)
PYEOF
            then
                echo "$msg; requeued once as $id" > "$rdir/ERROR"
                local aside="$rdir.interop1"
                [ -e "$aside" ] && aside="$rdir.interop1.$(date +%s)"
                mv "$rdir" "$aside"
                rm -f "$D/running/$id.owner"
                log "  FAILED: 0 captures, adb interop failure; requeued once (attempt kept at $aside)"
                return 0
            fi
            [ -n "$(jq_get "$rdir/request.json" interop_requeued "")" ] && msg="$msg; this was the one requeue, so it is final"
        fi
        adb_error "$msg" > "$rdir/ERROR"
        log "  FAILED: $(head -1 "$rdir/ERROR")"
        maybe_run_doctor "$id" "$rdir"
        return 0
    fi
    rm -f "$D/running/$id.owner"
    queue_master_restore "$id"
    touch "$rdir/DONE"
    log "  done -> $rdir"
    adb_call "$ADB_QUICK_TIMEOUT" "am force-stop (after run)" shell am force-stop com.jreinach.hakux.debug >/dev/null 2>&1
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
#
# libc:F, DEBUG:F and hakuX-stderr:E were MISSING, and every assert's text
# went with them. 1790344835-vsh-2413308 (thor) and 1790344836-vsh-2413360
# (nova) both SIGABRTed in pgraph_glsl_gen_vsh_prog; vsh-prog.c has four
# asserts and the logcat could not say which fired. The hakuX crash handler
# (android_crash_handler.cpp) logs the signal, the fault pc and a frame-
# pointer backtrace under `hakuX` -- but not the abort message. Bionic logs
# "file:line: func: assertion ... failed" under `libc` at F; crash_dump's
# tombstone under `DEBUG` at F repeats it as "Abort message:" with an
# unwinder-built backtrace of every thread, which the FP walk cannot give
# past a frame without a frame pointer. `hakuX-stderr` is the app's pump for
# the process's stderr, which is where pgraph prints the offending format
# before it aborts. All three are emitted only on the way down, so they cost
# nothing on a run that does not crash. hakuX-vk:I is one line, the app's own
# "Cache identity mismatch: wiping" -- whether this run started cold.
#
# hakuX-stall, hakuX-rpbrk, hakuX-cpu, xemu-gpu and xemu-sfp ADDED 2026-09-26
# for #372. All five are NV2A_PERF_LOG lines (a -Pperflog=true build), one per
# 60 guest frames, so a normal apk logs none of them. The #372 perflog soak
# measured `Sd2` finishes per frame on `xemu-work` but could not say which
# surface-download site fired: that split is on `hakuX-stall` (sd[...],
# dlSrc[...], dif[...]), and GPU time per frame is on `xemu-gpu`.
#
# xemu-surf ADDED 2026-09-26 for #413, same shape (NV2A_PERF_LOG, one line per
# 60 guest frames, profile.c). It is the sub-split of `Surf` -- populate,
# dirty, lookup hit/evict/nosurf, create, put, bind, upload, download,
# expire -- and DOA2U's perflog soak (1790450181-doa413-1721403) spent 33-52
# ms per frame in `Surf` without it, so the soak could not say which part.
LOGCAT_SPEC="${LOGCAT_SPEC_OVERRIDE:-hakuX-crash:V hakuX-unhandled:W hakuX-audio:I hakuX-audiocap:I hakuX-build:I hakuX-perf:I hakuX-phase:I xemu-work:I hakuX-lane:I hakuX-tier1:D hakuX-pages:I hakuX:I hakuX-rw:I hakuX-stderr:E hakuX-vk:I hakuX-route:I hakuX-pace:I hakuX-stall:I hakuX-rpbrk:I hakuX-cpu:I xemu-gpu:I xemu-sfp:I xemu-surf:I libc:F DEBUG:F VALIDATION:W ValidationLayer:W vulkan:W VulkanLoader:W *:S}"
export LOGCAT_SPEC

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
    unknown=" "
    # Start a worker for every attached, known serial that has none yet.
    # Called at start AND from the supervise loop below: a handheld that is
    # off adb when serve starts -- unplugged to charge on its 500 mA port --
    # was otherwise never served until the next restart. 2026-09-26: the
    # update window restarted serve at 20:12 PDT with the Thor off adb, the
    # owner plugged it back at 20:35, and no worker ever started for it; the
    # only remedy was a drain-restart holding both devices for 30 min.
    #
    # adb is Windows adb.exe through interop and can hang or fail with the
    # UtilAcceptVsock transient, so the listing has a deadline and a failed
    # listing changes nothing. A serial with a worker is never started twice:
    # a dead worker is the restart loop's to bring back, not this one's.
    attach_workers() {   # <suffix for the log line>
        local listing s i have
        listing=$(timeout -k 5 30 adb devices 2>/dev/null) || return 0
        for s in $(printf '%s\n' "$listing" | tr -d '\r' | awk 'NR>1 && $2=="device"{print $1}'); do
            have=0
            for i in "${!serials[@]}"; do [ "${serials[$i]}" = "$s" ] && have=1; done
            [ "$have" = 1 ] && continue
            if ! ( device_env "$s" ) >/dev/null 2>&1; then
                # Once per serial, not once a minute for as long as it is plugged in.
                case "$unknown" in *" $s "*) ;; *)
                    log "skipping unknown device $s; add it to devices.sh"
                    unknown="$unknown$s " ;; esac
                continue
            fi
            log "starting worker for $s${1:-}"
            SERIAL="$s" bash "$SNAP/dispatcher.sh" worker "$s" &
            workers+=($!)
            serials+=("$s")
        done
    }
    attach_workers
    if [ "${#workers[@]}" -eq 0 ]; then
        # NOT an exit. Exiting 2 here made the unit crash-loop, or sit dead,
        # while every handheld was off charging; supervising an empty set lets
        # the first one to come back be served by the late-attach path.
        log "no known device attached; supervising none until one attaches"
    fi
    log "=== supervising ${#workers[@]} device worker(s) ==="
    trap 'kill ${workers[@]} 2>/dev/null; exit 0' INT TERM
    # Both overridable for the selftest only (98-dispatch-late-device.sh).
    SUPERVISE_SLEEP="${DISPATCH_SUPERVISE_SLEEP:-20}"
    RESCAN_SECS="${DISPATCH_RESCAN_SECS:-60}"
    last_scan=$SECONDS
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
        sleep "$SUPERVISE_SLEEP"
        if [ $((SECONDS - last_scan)) -ge "$RESCAN_SECS" ]; then
            last_scan=$SECONDS
            attach_workers " (attached late)"
        fi
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
    # And snapshot with THIS file's lists, after the hash. The re-exec that
    # started this worker was carried out by the previous version's
    # snapshot_scripts, which copies the previous version's list: a file a
    # fold ADDS to the lists was never copied, and nothing re-snapshots until
    # some later fold moves the hash (vsh_score.py, 2026-09-25: missing from
    # bin/ after #229 folded, and request.sh refused vsh work waiting on a
    # re-exec that was not coming). Hash first: a tree edit landing between
    # the two leaves the snapshot NEWER than the hash, so the next tick
    # re-execs; the other order would leave it older with nothing to notice.
    snapshot_scripts
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
            sleep 10
            continue
        fi
        # Walk the queue in priority order rather than taking [0] blindly:
        # the first request may be pinned to the other handheld, and stopping
        # there would idle this one behind work it is not allowed to do.
        # serve_queue, so the battery head (battery_admit) is per walk.
        served=0
        serve_queue "${reqs[@]}" && served=1
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
    echo "build:   $BUILD_TREE @ $(git -C "$BUILD_TREE" rev-parse --short HEAD 2>/dev/null || echo 'not created yet')"
    tail -5 "$D/logs/dispatcher.log" 2>/dev/null
    ;;
  *) sed -n '3,12p' "$0" ;;
esac
