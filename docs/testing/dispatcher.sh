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
#    "runs":1}                          >1 for no-oracle measurements
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="${DISPATCH_TREE:-/home/justin/hakuX}"
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
SERIAL="${SERIAL:-ee317437}"
GOLDENS="${GOLDENS:-/home/justin/goldens/results}"
SWEEP_STATE="${SWEEP_STATE:-/home/justin/hakux-work/night19/sq_g0}"
LEASE="${HAKUX_DEVICE_LEASE:-/tmp/hakux-device-lease}"
export JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}"
export PATH="/home/justin/Android/Sdk/cmake/3.30.3/bin:$PATH"

mkdir -p "$D"/{queue,running,results,logs}
log() { echo "$(date '+%m-%d %H:%M:%S') $*" | tee -a "$D/logs/dispatcher.log"; }
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
    mv "$req" "$D/running/$id.req" 2>/dev/null || return 0
    req="$D/running/$id.req"
    local requester purpose ref arm runs
    requester=$(jq_get "$req" requester unknown)
    purpose=$(jq_get "$req" purpose "")
    ref=$(jq_get "$req" ref HEAD)
    arm=$(jq_get "$req" arm company)
    runs=$(jq_get "$req" runs 1)
    log "request $id from $requester: $purpose (ref=$ref arm=$arm runs=$runs)"

    local rdir="$D/results/$id"; mkdir -p "$rdir"
    local apk; apk=$(build_ref "$ref") || {
        echo "build failed for ref $ref (code $?)" > "$rdir/ERROR"
        log "  BUILD FAILED"; mv "$req" "$rdir/request.json"; return 0
    }
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
    local disc_id
    disc_id=$(python3 -c "
import json,sys
s=json.load(open(sys.argv[1])).get('suites',[])
print(s[0] if len(s)==1 else '%d-suites:%s' % (len(s), ','.join(sorted(s))[:40]))" "$req")

    local r
    for r in $(seq 1 "$runs"); do
        local args=() gdir="d$(echo "$id$r" | md5sum | cut -c1-6)"
        local s
        for s in "${SUITE_LIST[@]}"; do args+=(--suite "${s//_/ }"); done
        python3 "$HERE/make_test_iso.py" "${DISPATCH_BASE_ISO:-/home/justin/nxdk_pgraph_tests_xiso.iso}" \
            -o "$rdir/disc$r.iso" "${args[@]}" --progress-log \
            --shutdown-on-completion --output-dir "e:/$gdir" >>"$rdir/run$r.log" 2>&1
        touch "$LEASE"
        SERIAL="$SERIAL" CAPTURE_LOG="$rdir/logcat$r.txt" \
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
meta["runs"] = runs

# Name the log explicitly, so "we captured nothing" and "the suite dropped
# nothing" are different answers. They looked identical before, which is the
# same failure the unhandled-method log exists to fix, one level up.
logs = []
for lg in sorted(glob.glob(os.path.join(rdir, "logcat*.txt"))):
    n = sum(1 for _ in open(lg, errors="replace"))
    logs.append(dict(file=os.path.basename(lg), lines=n))
meta["logcat"] = dict(spec=os.environ.get("LOGCAT_SPEC",
                                          "hakuX-unhandled:W hakuX:W *:S"),
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
    touch "$rdir/DONE"
    log "  done -> $rdir"
    adb -s "$SERIAL" shell am force-stop com.jreinach.hakux.debug >/dev/null 2>&1
}

case "${1:-status}" in
  serve)
    log "=== dispatcher serving; queue=$D/queue ==="
    while :; do
        shopt -s nullglob
        reqs=("$D"/queue/*.req)
        if [ "${#reqs[@]}" -eq 0 ]; then
            resume_sweep
            sleep 10
            continue
        fi
        serve_one "${reqs[0]}"
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
