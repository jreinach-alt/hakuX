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
titles/classify.py titles/waitfor_match.py"
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
SNAPSHOT_GLOBS="titles/drive-profiles/*.toml titles/drive-profiles/*/*.png"
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
             titles/saves.py titles/drive.py titles/classify.py titles/waitfor_match.py; do
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
adb_error() {   # <what failed> -> the ERROR line, naming a hung call if any
    if [ -s "${ADB_HUNG_FILE:-}" ]; then
        echo "$1: adb hung -- $(head -1 "$ADB_HUNG_FILE")"
    else
        echo "$1"
    fi
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
# titlestate/NOTES.md), and every other run leaves `hddPath` on hdd.img.
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
    adb_call "$ADB_QUICK_TIMEOUT" "run-as cat x1box_prefs.xml (hdd)" \
        shell "run-as $pkg cat shared_prefs/x1box_prefs.xml" 2>/dev/null | tr -d '\r' > "$tmp"
    if [ -s "${ADB_HUNG_FILE:-}" ] || [ ! -s "$tmp" ]; then
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
# dev_push <host path> <device path>: through <path>.new and a rename, checked.
# Mode 660 before the rename, so the file is never in place unopenable. A
# failure before the rename leaves <path> as it was and removes <path>.new.
dev_push_drop() {
    adb_call "$ADB_QUICK_TIMEOUT" "rm $1.new" shell "rm -f '$1.new'" >/dev/null 2>&1
}
dev_push() {
    local src="$1" dst="$2" want
    want=$(sha256sum "$src" | cut -d' ' -f1)
    adb_call 600 "push $dst" push "$src" "$dst.new" >/dev/null 2>&1 || { dev_push_drop "$dst"; return 1; }
    [ "$(dev_sha256 "$dst.new")" = "$want" ] || { log "  push $dst: the device's copy does not match"; dev_push_drop "$dst"; return 1; }
    dev_make_660 "$dst.new" || { dev_push_drop "$dst"; return 1; }
    adb_call "$ADB_QUICK_TIMEOUT" "mv $dst" shell "mv -f '$dst.new' '$dst'" >/dev/null 2>&1 || { dev_push_drop "$dst"; return 1; }
    [ "$(dev_sha256 "$dst")" = "$want" ] && [ "$(dev_mode "$dst")" = 660 ]
}

# titles_disk_prepare <id> <rdir> [<request env json>] [<title id>] [<state>]:
# make the device's titles disk the composed goldens for this title and state
# (titlestate.py, GOLDENS: every title's golden profile, minus this title's on
# a first-run) and point hddPath at it. Writes <rdir>/hdd.json, which records
# what was loaded: title, save, golden or none. Non-zero fails the request;
# 3 is a refusal (a returning state with no golden), written to
# <rdir>/hdd.refused, before any disk is touched.
titles_disk_prepare() {
    local id="$1" rdir="$2" renv="${3:-[]}" tid="${4:-}" tstate="${5:-any}" dev="${DEVICE_LABEL:-}" dpath x pj action reason bytes sha i
    local split="${HAKUX_TITLES_DISK:-1}" from=worker rsplit mode0 targs=()
    [ -n "$tid" ] && targs=(--title-id "$tid")
    targs+=(--state "$tstate")
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
    adb_call "$ADB_INSTALL_TIMEOUT" "adb install -r" install -r "$apk" 2>&1 | grep -q Success || {
        adb_error "install failed" > "$rdir/ERROR"; log "  INSTALL FAILED: $(cat "$rdir/ERROR")"
        mv "$req" "$rdir/request.json"; return 0
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
        mv "$req" "$rdir/request.json"; return 0
    fi
    req_env=$(python3 -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1])).get('env') or []))" "$req" 2>/dev/null || echo "[]")
    # A title run that never reached titles_disk_after left hddPath on the
    # titles disk; no run may start on the wrong one. No marker, no adb call.
    if ! restore_hdd_pref; then
        adb_error "could not restore hddPath after an earlier title run; see dispatcher.log" > "$rdir/ERROR"
        log "  HDD PREF RESTORE FAILED"
        mv "$req" "$rdir/request.json"; return 0
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
        # Under the first of the device's roots that has it (devices.sh).
        local tpath
        if ! tpath=$(device_title_path "$title"); then
            adb_error "$(device_title_miss "$title")" > "$rdir/ERROR"
            log "  TITLE NOT FOUND"; mv "$req" "$rdir/request.json"; return 0
        fi
        touch "$LEASE"
        # Before the titles disk, which edits the same file: a build from
        # before libfolders needs the old games folder key to boot anything.
        if ! ensure_legacy_folder_pref; then
            adb_error "could not give x1box_prefs.xml the pre-libfolders gamesFolderUri; see dispatcher.log" > "$rdir/ERROR"
            log "  FOLDER PREF FAILED"; mv "$req" "$rdir/request.json"; return 0
        fi
        # Which title, and the state its route was written for (request.sh
        # --route, titlestate.py resolve-route). A request queued before that
        # carries neither: its title from the ISO name, state `any`.
        local ttid tstate trc
        ttid=$(jq_get "$req" title_id "")
        [ -n "$ttid" ] || ttid=$(python3 "$TITLESTATE" tid-for-iso "$title" 2>/dev/null)
        tstate=$(jq_get "$req" title_state any)
        titles_disk_prepare "$id" "$rdir" "$req_env" "$ttid" "$tstate"; trc=$?
        if [ "$trc" = 3 ]; then
            echo "refused before the soak: the titles disk cannot carry what the route assumes: $(cat "$rdir/hdd.refused" 2>/dev/null)" > "$rdir/ERROR"
            log "  TITLES DISK REFUSED"
            restore_hdd_pref
            mv "$req" "$rdir/request.json"; return 0
        elif [ "$trc" != 0 ]; then
            adb_error "could not prepare the titles disk; see dispatcher.log" > "$rdir/ERROR"
            log "  TITLES DISK SETUP FAILED"
            restore_hdd_pref
            mv "$req" "$rdir/request.json"; return 0
        fi
        # The route's text travels in the request (request.sh --route); the
        # file soak_title.sh plays is written from it here, beside the result.
        python3 -c 'import json,sys; r=json.load(open(sys.argv[1])).get("route") or ""; r and open(sys.argv[2],"w").write(r.rstrip("\n")+"\n")' "$req" "$rdir/route.txt"
        start_frame_capture "$rdir" "$frames_every" "$seconds"
        SERIAL="$SERIAL" CAPTURE_LOG="$rdir/logcat.txt" \
            PULL_GLOB="$pull_glob" PULL_DEST="$rdir/pulled" \
            AUDIO_CAPTURE_MB="$audio_capture" \
            ROUTE_FILE="$([ -s "$rdir/route.txt" ] && echo "$rdir/route.txt")" \
            bash "$HERE/soak_title.sh" "$tpath" "$seconds" >>"$rdir/run.log" 2>&1
        # Before the result is written, so the count in result.json is final,
        # and unconditionally, so an early guest exit does not leave a
        # screencap loop running against the next request's title.
        stop_frame_capture
        titles_disk_after "$id" "$rdir"
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
def _battery(rdir):
    try:
        return json.load(open(os.path.join(rdir, "battery.json")))
    except (OSError, ValueError):
        return None
# WHICH DISK THE TITLE BOOTED (titles_disk_prepare): its device path, sha256
# at the start, the plans that made it current, and what the post-run
# harvest found. None before the split existed.
def _hdd(rdir):
    try:
        h = json.load(open(os.path.join(rdir, "hdd.json")))
    except (OSError, ValueError):
        return None
    try:
        h["after"] = json.load(open(os.path.join(rdir, "hdd.after.json")))
    except (OSError, ValueError):
        pass
    return h
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
               # What admitted it (battery_admit.py): battery_start, need,
               # rate. None when the run predates admission or it was off.
               battery=_battery(rdir)),
          open(os.path.join(rdir, "result.json"), "w"), indent=2)
print("soak done:", title, lines, "log lines")
PYEOF
        log "  soak done, $lines log lines -> $rdir/logcat.txt$(
            [ -d "$rdir/frames" ] && printf ', %s frames' "$(ls "$rdir/frames" | wc -l)")"
        mv "$req" "$rdir/request.json"
        rm -f "$D/running/$id.owner"
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
        return 0
    fi
    rm -f "$D/running/$id.owner"
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
