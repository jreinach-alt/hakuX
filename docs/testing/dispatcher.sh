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
snapshot_scripts() {
    mkdir -p "$SNAP"
    for f in dispatcher.sh devices.sh soak_title.sh run_disc.sh score_sweep.py \
             affinity.py captures.py make_test_iso.py extract_results.py; do
        [ -f "$SRC/$f" ] && cp -f "$SRC/$f" "$SNAP/$f" 2>/dev/null
    done
}
# Hash of the scripts as they are IN THE TREE, or empty while the tree is
# detached for a build. Empty means "do not compare": mid-build the tree holds
# some other commit's scripts, and both answers there are wrong -- re-exec and
# a worker adopts a baseline's dispatcher, don't and the hash is a lie that
# suppresses the next real edit. DETACHED is written by build_ref for exactly
# this window.
src_hash() {
    [ -e "$D/DETACHED" ] && return 0
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

build_ref() {  # $1 = ref ; $2 = "perflog" for a diagnostic build ; echoes the apk path
    # Serialised across devices, because building detaches the SHARED
    # checkout. Two workers here at once would each `git checkout --detach` a
    # different sha in the same tree and both would build whatever the other
    # left behind -- silently, since each would still produce an APK and call
    # it by its own sha. The APK cache below makes the common case free, so
    # the lock costs nothing when both devices want the same binary, which is
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
    local sha; sha=$(git -C "$TREE" rev-parse --short "$ref" 2>/dev/null) || return 1
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
    # Requests name a ref, never "what is in the tree": with several
    # implementers holding uncommitted work, "run my build" is ambiguous the
    # moment two of them ask.
    if [ -n "$(git -C "$TREE" status --porcelain | grep -v '^??')" ]; then
        log "  tree is dirty; the binary would not be $sha"
        return 3
    fi
    # A baseline arm is never HEAD, so refusing non-HEAD refs made the one
    # comparison that matters impossible -- and comparing a fix against a
    # differently-composed earlier run is exactly the mistake that got a
    # working fix reverted. So build any committed ref by detaching onto it,
    # and put the branch back on every exit path. The tree is verified clean
    # above, and agents hold their own worktrees, so a detach here disturbs
    # nobody.
    local head restore=""
    head=$(git -C "$TREE" rev-parse --short HEAD)
    if [ "$sha" != "$head" ]; then
        restore=$(git -C "$TREE" symbolic-ref --quiet --short HEAD \
                  || git -C "$TREE" rev-parse HEAD)
        log "  ref $ref ($sha) is not HEAD ($head); detaching to build, restoring $restore after"
        git -C "$TREE" checkout --quiet --detach "$sha" || {
            log "  checkout of $sha failed; not building"; return 2; }
        # Visible while detached: anyone committing into this window would
        # commit onto the wrong base. `dispatcher.sh status` surfaces it.
        echo "detached at $sha to build a baseline; restoring $restore" > "$D/DETACHED"
    fi
    (cd "$TREE/android" && ./gradlew assembleDebug ${gradle_args:+$gradle_args}) \
        >>"$D/logs/build-$sha$suffix.log" 2>&1
    local rc=$?
    if [ -n "$restore" ]; then
        git -C "$TREE" checkout --quiet "$restore" \
            || log "  WARNING: could not restore $restore -- tree is left detached at $sha"
        rm -f "$D/DETACHED"
    fi
    [ "$rc" -eq 0 ] || return 4
    cp "$TREE/android/app/build/outputs/apk/debug/app-debug.apk" "$apk"
    echo "$apk"
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
    local requester purpose ref arm runs
    requester=$(jq_get "$req" requester unknown)
    purpose=$(jq_get "$req" purpose "")
    ref=$(jq_get "$req" ref HEAD)
    arm=$(jq_get "$req" arm company)
    runs=$(jq_get "$req" runs 1)
    local title seconds pull_glob audio_capture
    title=$(jq_get "$req" title "")
    seconds=$(jq_get "$req" seconds 60)
    pull_glob=$(jq_get "$req" pull_glob "")
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
    if [ "$rc" = 3 ]; then
        # A dirty tree is TRANSIENT -- someone is editing -- and must not
        # destroy queued work. Requeueing rather than failing is the same
        # lesson as the device-drop requeue and the orphan requeue: an
        # uncommitted edit of mine failed 54 consecutive scoreboard-sweep
        # requests in seconds, because each was answered with a hard ERROR
        # instead of being put back.
        log "  tree dirty; requeueing $id and waiting"
        rmdir "$rdir" 2>/dev/null
        mv "$req" "$D/queue/$id.req"; sleep 30; return 0
    fi
    if [ "$rc" != 0 ]; then
        echo "build failed for ref $ref (code $rc)" > "$rdir/ERROR"
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
        SERIAL="$SERIAL" CAPTURE_LOG="$rdir/logcat.txt" \
            PULL_GLOB="$pull_glob" PULL_DEST="$rdir/pulled" \
            AUDIO_CAPTURE_MB="$audio_capture" \
            bash "$HERE/soak_title.sh" "$tpath" "$seconds" >>"$rdir/run.log" 2>&1
        local lines; lines=$(wc -l < "$rdir/logcat.txt" 2>/dev/null || echo 0)
        python3 - "$rdir" "$sha" "$title" "$seconds" "$requester" "$purpose" "$ref" "$lines" <<'PYEOF'
import json, os, sys
rdir, sha, title, seconds, who, purpose, ref, lines = sys.argv[1:9]
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
               logcat_lines=int(lines), pulled=pulled),
          open(os.path.join(rdir, "result.json"), "w"), indent=2)
print("soak done:", title, lines, "log lines")
PYEOF
        log "  soak done, $lines log lines -> $rdir/logcat.txt"
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

    python3 - "$rdir" "$sha" "$disc_id" "$requester" "$purpose" "$ref" "$SNAP" <<'PYEOF'
import csv, glob, json, os, subprocess, sys
rdir, sha, disc, who, purpose, ref, snap = sys.argv[1:8]
meta = dict(apk_sha=sha, disc_id=disc, requester=who, purpose=purpose, ref=ref)
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
    mkdir -p "$D/lanes"
    printf '%s\n' "$$" > "$D/lanes/$DEVICE_LABEL"
    trap 'rm -f "$D/lanes/$DEVICE_LABEL"' EXIT

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
            rm -f "$D/lanes/$DEVICE_LABEL"   # affinity must not pin a pair here
            sleep 30
            continue
        fi
        if [ "$held_logged" = 1 ]; then
            log "hold released; serving again"
            held_logged=0
            printf '%s' "$$" > "$D/lanes/$DEVICE_LABEL"
        fi
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
    [ -f "$D/DETACHED" ] && echo "TREE:    $(cat "$D/DETACHED") -- DO NOT COMMIT"
    tail -5 "$D/logs/dispatcher.log" 2>/dev/null
    ;;
  *) sed -n '3,12p' "$0" ;;
esac
