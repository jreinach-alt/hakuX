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
#    "tests":["Suite::Test"]            optional, solo arm only
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

build_ref() {  # $1 = ref ; echoes the apk path, or fails
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
    local ref="$1" out="$D/builds"
    mkdir -p "$out"
    local sha; sha=$(git -C "$TREE" rev-parse --short "$ref" 2>/dev/null) || return 1
    local apk="$out/$sha.apk"
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
    (cd "$TREE/android" && ./gradlew assembleDebug) >>"$D/logs/build-$sha.log" 2>&1
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
    apk=$(build_ref "$ref"); rc=$?
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
json.dump(dict(apk_sha=sha, kind="soak", title=title, seconds=int(seconds),
               requester=who, purpose=purpose, ref=ref,
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
    disc_id=$(python3 -c "
import hashlib,json,sys
r=json.load(open(sys.argv[1]))
s=sorted(r.get('suites',[]))
k=sorted(r.get('skip_tests',[]))
if len(s)==1 and not k:
    print(s[0])
elif len(s)==1:
    print('%s-no:%s' % (s[0], ','.join(t.split('::')[-1] for t in k)[:30]))
else:
    h=hashlib.sha1((','.join(s)+'|'+','.join(k)).encode()).hexdigest()[:8]
    print('%d-suites:%s:%s' % (len(s), h, ','.join(s)[:40]))" "$req")

    local r
    for r in $(seq 1 "$runs"); do
        local args=() gdir="d$(echo "$id$r" | md5sum | cut -c1-6)"
        local s
        for s in "${SUITE_LIST[@]}"; do args+=(--suite "${s//_/ }"); done
        for s in "${SKIP_LIST[@]:-}"; do [ -n "$s" ] && args+=(--skip-test "$s"); done
        python3 "$HERE/make_test_iso.py" "${DISPATCH_BASE_ISO:-/home/justin/nxdk_pgraph_tests_xiso.iso}" \
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

    python3 - "$rdir" "$sha" "$disc_id" "$requester" "$purpose" "$ref" <<'PYEOF'
import csv, glob, json, os, subprocess, sys
rdir, sha, disc, who, purpose, ref = sys.argv[1:7]
meta = dict(apk_sha=sha, disc_id=disc, requester=who, purpose=purpose, ref=ref)
try:
    meta["classifier_rev"] = subprocess.run(
        ["git", "-C", "/home/justin/hakuX", "log", "-1", "--format=%h",
         "--", "docs/testing/classify_residuals.py"],
        capture_output=True, text=True).stdout.strip()
except Exception:
    meta["classifier_rev"] = "unknown"
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
LOGCAT_SPEC="${LOGCAT_SPEC:-hakuX-crash:V hakuX-unhandled:W hakuX-audio:I hakuX-audiocap:I hakuX-build:I hakuX-perf:I hakuX-pages:I hakuX:I hakuX-rw:I VALIDATION:W ValidationLayer:W vulkan:W VulkanLoader:W *:S}"
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
    while :; do
        shopt -s nullglob
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
