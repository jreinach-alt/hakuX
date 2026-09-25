# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check, and the live prediction's
# fixtures. Not executable, no shebang, no exit -- `fail` is shared and is the
# run's verdict.
#
# AFTER 50: part E drives arms.sh over the queue and results 50 leaves, and
# leaves them as it found them (both halves of the live pair clean).
#
# Dispatcher hardening (docs/lanes/dispatch-hardening/NOTES.md):
#   A. an unscored capture is VOID in a verdict, not "repaired to exact";
#   B. result.json counts only scored captures, and the three copies of the
#      scored-status set agree;
#   C. a serve-path adb call that never answers returns within its deadline
#      and names itself in ERROR;
#   D. the sweep preemption is gone, and sweep_queue.sh pause reaches the
#      sweep's own device;
#   E. arms.sh counts a sha as run only when BOTH halves ran clean;
#   F. 0 captures with the WSL interop signature is requeued once, then final.
#
# Every mutant is confirmed to DIFFER from the real file before it is run, and
# lives in a symlink tree: the real docs/testing is never written.

DH="$T/dh"; rm -rf "$DH"; mkdir -p "$DH"
dhmut() {   # <path under docs/testing> <sed-expression> [name] -> echoes the tree
    local rel="$1" expr="$2" dir="$DH/${3:-mut}" x
    rm -rf "$dir"; mkdir -p "$dir/jobs"
    for x in "$TESTING"/*; do [ "$(basename "$x")" = jobs ] || ln -s "$x" "$dir/$(basename "$x")"; done
    for x in "$TESTING"/jobs/*; do ln -s "$x" "$dir/jobs/$(basename "$x")"; done
    rm -f "$dir/$rel"
    sed "$expr" "$TESTING/$rel" > "$dir/$rel" || return 1
    chmod +x "$dir/$rel"
    cmp -s "$dir/$rel" "$TESTING/$rel" && return 1
    printf '%s\n' "$dir"
}

# ---------------------------------------------------------------- A. void
echo "== dispatch hardening A: an unreadable capture is VOID, not 'now exact'"
# #224's arm (pair 42c014b32fab): the fix arm's pull truncated 56 W_param
# PNGs, score_sweep wrote each `unreadable` with differing=0, and the verdict
# counted 52 of them better -- "repaired to exact". Falsified on that real
# pair by hand: master's ab_compare says better 64 / repaired 52 / FAIL, this
# one better 12 / VOID 56 / INCOMPLETE (NOTES.md). This is the same shape,
# small: three captures, the void one in the MIDDLE, and a prediction whose
# must-move leg lands on it -- so the old arithmetic FAKES A PASS.
dharm() {   # <dir> <apk> <ref> <tsv rows...>
    local d="$1" apk="$2" ref="$3"; shift 3
    mkdir -p "$d"; : > "$d/DONE"
    printf 'suite\ttest\tsolo\tstatus\tdiffering\tmax_rgb\tmax_a\tpixels\toff_by_one\tapk_sha\tdisc_id\tlabel\n' > "$d/scores1.tsv"
    printf '%s\n' "$@" >> "$d/scores1.tsv"
    python3 - "$d/result.json" "$apk" "$ref" <<'PY'
import json, sys
json.dump({"apk_sha": sys.argv[2], "disc_id": "1-suites:x:S", "ref": sys.argv[3],
           "program": "pgraph", "device_label": "thor", "scorer_rev": "s",
           "classifier_rev": "c",
           "runs": [{"tsv": "scores1.tsv", "captures": 3, "progress_log_proof": True}]},
          open(sys.argv[1], "w"))
PY
}
TAB=$'\t'
dharm "$DH/a" aaaa ra "S${TAB}a_fixed${TAB}True${TAB}ok${TAB}100${TAB}9${TAB}0${TAB}1000${TAB}0" \
                      "S${TAB}b_lost${TAB}True${TAB}ok${TAB}500${TAB}9${TAB}0${TAB}1000${TAB}0" \
                      "S${TAB}c_same${TAB}True${TAB}ok${TAB}10${TAB}9${TAB}0${TAB}1000${TAB}0"
dharm "$DH/b" bbbb rb "S${TAB}a_fixed${TAB}True${TAB}ok${TAB}0${TAB}0${TAB}0${TAB}1000${TAB}0" \
                      "S${TAB}b_lost${TAB}True${TAB}unreadable${TAB}0${TAB}0${TAB}0${TAB}0${TAB}0" \
                      "S${TAB}c_same${TAB}True${TAB}ok${TAB}10${TAB}9${TAB}0${TAB}1000${TAB}0"
python3 - "$DH/expect.json" <<'PY'
import json, sys
json.dump({"a_ref": "ra", "b_ref": "rb", "expect": {"S/a_fixed": 0, "S/b_lost": 0},
           "must_not_move": ["S/c_same"], "must_not_regress": [], "expect_counts": {}},
          open(sys.argv[1], "w"))
PY
dhab() { python3 "$1/ab_compare.py" --a "$DH/a" --b "$DH/b" --expect "$DH/expect.json" 2>&1; }
DHO=$(dhab "$TESTING"); DHV=$(printf '%s\n' "$DHO" | grep -m1 '^VERDICT:')
case "$DHO" in *"better 1 "*) ok "A: one capture better -- the one that was measured" ;;
               *) bad "A: expected 'better 1'; got: $(printf '%s\n' "$DHO" | grep -m1 'better ')" ;; esac
case "$DHO" in *"VOID   1"*"S                           1  B unreadable"*) ok "A: the unreadable capture is listed VOID, by suite and cause" ;;
               *) bad "A: no VOID line naming S / B unreadable" ;; esac
case "$DHV" in "VERDICT: INCOMPLETE"*) ok "A: a leg on a VOID capture makes the verdict INCOMPLETE" ;;
               *) bad "A: verdict was: $DHV" ;; esac
# arms.sh reads the verdict line by substring; neither word may be on it.
case "$DHV" in *PASS*|*FAIL*) bad "A: the INCOMPLETE line carries PASS or FAIL, so arms.sh would label on it: $DHV" ;;
               *) ok "A: the INCOMPLETE line has neither PASS nor FAIL, so arms.sh sets no label" ;; esac
case "$DHO" in *"expect S/b_lost: 1 VOID capture(s) (B unreadable)"*) ok "A: the void leg is named" ;;
               *) bad "A: the void leg S/b_lost is not named" ;; esac
check "A: --probe refuses an unscored capture rather than printing median 0" \
    bash -c '! python3 "$1/ab_compare.py" --probe "$2" --capture S/b_lost' _ "$TESTING" "$DH/b"
# MUTANT: `unreadable` counted as scored is the old arithmetic.
DHM=$(dhmut ab_compare.py 's|^SCORED_STATUSES = ("ok",|SCORED_STATUSES = ("unreadable", "ok",|')
if [ -z "$DHM" ]; then
    bad "A MUTANT: could not build it (the sed matched nothing)"
else
    DHMO=$(dhab "$DHM")
    case "$DHMO" in *"VERDICT: PASS"*"better 2 "*|*"better 2 "*"VERDICT: PASS"*)
        ok "A MUTANT: with unreadable scored, the same arms FAKE A PASS on 'better 2' -- so A can go red" ;;
      *) bad "A MUTANT: expected the faked PASS; got $(printf '%s\n' "$DHMO" | grep -m1 '^VERDICT:')" ;; esac
fi

# ------------------------------------------------- B. result.json coverage
echo "== dispatch hardening B: result.json counts scored captures only"
# #224's fix arm: result.json said 110 of 110 W_param while score_sweep's own
# coverage said 54 of 110. The writer is dispatcher.sh's third heredoc; run it
# as written, on a TSV with the unreadable row in the middle.
mkdir -p "$DH/rw"
printf 'suite\ttest\tsolo\tstatus\tdiffering\n' > "$DH/rw/scores1.tsv"
printf 'S\ta\tTrue\tok\t0\nS\tb\tTrue\tunreadable\t0\nS\tc\tTrue\tok\t7\n' >> "$DH/rw/scores1.tsv"
sed -n '/^    python3 - "\$rdir" "\$sha" "\$disc_id"/,/^PYEOF$/p' "$TESTING/dispatcher.sh" \
    | sed '1d;$d' > "$DH/writer.py"
check "B: the result writer was extracted (non-empty, mentions SCORED_STATUSES)" \
    grep -q 'SCORED_STATUSES' "$DH/writer.py"
(cd "$DH" && python3 writer.py "$DH/rw" sha disc who purpose ref "$DH" pgraph >/dev/null 2>&1)
DHB=$(python3 -c 'import json,sys; r=json.load(open(sys.argv[1]))["runs"][0]; print(r["captures"], r["exact"], r["unscored"])' "$DH/rw/result.json" 2>&1)
check "B: captures=2 exact=1 and the unreadable row reported as unscored ($DHB)" \
    [ "$DHB" = "2 1 {'unreadable': 1}" ]
DHSETS=$(python3 - "$TESTING" <<'PY'
import re, sys
out = []
for f in ("score_sweep.py", "ab_compare.py", "dispatcher.sh"):
    m = re.search(r"^SCORED_STATUSES = (\(.*?\))", open(sys.argv[1] + "/" + f).read(), re.M)
    out.append(m.group(1) if m else "MISSING:" + f)
print(len(set(out)), out[0])
PY
)
check "B: score_sweep, ab_compare and dispatcher.sh carry ONE scored-status set ($DHSETS)" \
    [ "${DHSETS%% *}" = 1 ]

# ------------------------------------------------ C. a hung serve-path adb
echo "== dispatch hardening C: a serve-path adb call that never answers is bounded"
# On 09-14 the Thor sat in one request from 06:29 to 09-18 09:23 behind an
# adb call with no deadline. serve_one is sourced and run as written, with a
# fake adb that never returns from `install` (or, in C2, from any `shell`).
mkdir -p "$DH/fakebin"
cat > "$DH/fakebin/adb" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$DH_ADB_LOG"
case " $* " in *" devices "*|*" devices") printf 'List of devices attached\nbdc158a5\tdevice\nee317437\tdevice\n'; exit 0 ;; esac
case "$DH_ADB_MODE:$*" in
    hang-install:*install*|hang-shell:*shell*) echo $$ >> "$DH_ADB_PIDS"; exec sleep 300 ;;
    *install*) echo Success ;;
esac
exit 0
EOF
chmod +x "$DH/fakebin/adb"; : > "$DH/apk"
export DH_ADB_PIDS="$DH/adb.pids"; : > "$DH_ADB_PIDS"
cat > "$DH/drive.sh" <<'EOF'
# drive.sh <testing-dir> <dispatch-dir> <request-id>: one serve_one, as written
export DISPATCH_DIR="$2" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
. "$1/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
build_ref() { echo "$DH_APK"; }
serve_one "$2/queue/$3.req"
EOF
dhreq() {   # <dispatch-dir> <id> <json>
    mkdir -p "$1"/{queue,running,results,logs,lanes}; printf '%s\n' "$3" > "$1/queue/$2.req"; }
dhserve() {   # <testing-dir> <dispatch-dir> <id> <mode> <deadline-s> -> exit status of timeout
    PATH="$DH/fakebin:$PATH" DH_ADB_LOG="$2/adb.log" DH_ADB_MODE="$4" DH_APK="$DH/apk" \
    ADB_INSTALL_TIMEOUT=2 ADB_QUICK_TIMEOUT=2 ADB_RETRY_SLEEP=0 REPO="$REPO" \
        timeout -k 2 "$5" bash "$DH/drive.sh" "$1" "$2" "$3" >"$2/drive.out" 2>&1
}
dhreq "$DH/c1" 1-hang '{"requester":"selftest","purpose":"hang","ref":"HEAD"}'
SECONDS=0; dhserve "$TESTING" "$DH/c1" 1-hang hang-install 30; DHRC=$?; DHT=$SECONDS
check "C1: serve_one returned on its own (exit $DHRC, not the outer 124) in ${DHT}s" [ "$DHRC" != 124 ]
check "C1: ERROR names the hung install and its deadline" \
    grep -qx 'install failed: adb hung -- adb install -r (no answer in 2s)' "$DH/c1/results/1-hang/ERROR"
check "C1: the request left running/ through the post-claim exit" \
    test -f "$DH/c1/results/1-hang/request.json" -a ! -e "$DH/c1/running/1-hang.req"
dhreq "$DH/c2" 1-hang '{"requester":"selftest","purpose":"hang","ref":"HEAD","env":["X=1"]}'
dhserve "$TESTING" "$DH/c2" 1-hang hang-shell 40; DHRC=$?
check "C2: an env request whose pref calls hang returns on its own (exit $DHRC)" [ "$DHRC" != 124 ]
check "C2: ERROR names the first hung pref call" \
    grep -q 'env_vars pref.*adb hung -- am force-stop (env pref) (no answer in 2s)' "$DH/c2/results/1-hang/ERROR"
# MUTANT: adb_call without its deadline is the old serve path. It must hang
# at the install -- reached, not failed earlier -- and write no ERROR.
DHM=$(dhmut devices.sh 's|timeout -k 5 "\$secs" adb|adb|')
if [ -z "$DHM" ]; then
    bad "C MUTANT: could not build it (the sed matched nothing)"
else
    dhreq "$DH/cm" 1-hang '{"requester":"selftest","purpose":"hang","ref":"HEAD"}'
    dhserve "$DHM" "$DH/cm" 1-hang hang-install 8; DHRC=$?
    check "C MUTANT: without the deadline serve_one is still blocked when the outer 8s timeout fires (exit $DHRC)" [ "$DHRC" = 124 ]
    check "C MUTANT: blocked AT the install -- adb was asked to install -- and wrote no ERROR" \
        bash -c 'grep -q "install -r" "$1/adb.log" && [ ! -e "$1/results/1-hang/ERROR" ]' _ "$DH/cm"
fi
while read -r p; do kill "$p" 2>/dev/null; done < "$DH_ADB_PIDS"

# ------------------------------------------------ D. no sweep preemption
echo "== dispatch hardening D: the sweep preemption is gone; pause reaches the sweep's device"
check "D: dispatcher.sh has no code calling sweep_queue.sh, preempt_sweep or resume_sweep" \
    bash -c '! grep -v "^[[:space:]]*#" "$1/dispatcher.sh" | grep -qE "preempt_sweep|resume_sweep|sweep_running|sweep_queue\.sh (pause|resume)"' _ "$TESTING"
# sweep_queue.sh pause with NO build inputs set, the sweep recorded on the
# nova, and adb listing the thor FIRST -- the device the old pause would have
# force-stopped.
mkdir -p "$DH/sq"; echo ee317437 > "$DH/sq/serial"; : > "$DH/sq/IDLE"; : > "$DH/sq/queue.txt"
( unset BASE_ISO GOLDENS RESULTS BASELINE_APK SERIAL
  PATH="$DH/fakebin:$PATH" DH_ADB_LOG="$DH/sq/adb.log" DH_ADB_MODE=ok SWEEP_STATE="$DH/sq" \
      timeout 30 bash "$TESTING/sweep_queue.sh" pause ) > "$DH/sq/out" 2>&1
check "D: pause ran without BASE_ISO/GOLDENS/RESULTS/BASELINE_APK and reported the device free" \
    grep -q "paused" "$DH/sq/out"
check "D: pause force-stopped the app on the sweep's device (ee317437)" \
    grep -q -- "-s ee317437 shell am force-stop" "$DH/sq/adb.log"
check "D: and touched no other device" bash -c '! grep -q bdc158a5 "$1"' _ "$DH/sq/adb.log"

# ------------------------------------------------ E. both halves or neither
echo "== dispatch hardening E: a half-run pair can be queued again"
# vshconst (09-25): base lost its pull, fix was DONE, and the ARM ERROR
# advice to delete judged/<sha> and pairs/<sha>.json did nothing because the
# surviving half still counted as a run. 50 left both halves of the live pair
# clean; ERROR the OLDER one so exactly one half survives.
DHHALF=$(ls -dt "$DISPATCH_DIR"/results/*/ 2>/dev/null | sed -n 2p)
if [ -z "$DHHALF" ] || [ -n "$(ls "$DISPATCH_DIR"/queue/*.req 2>/dev/null)" ]; then
    bad "E: fixture not as 50 leaves it (two clean results, an empty queue)"
else
    echo simulated > "$DHHALF/ERROR"
    clear_markers
    bash "$HERE/arms.sh" >/dev/null 2>&1
    check "E: with one half ERRORed, the pair is queued again" \
        [ "$(ls "$DISPATCH_DIR"/queue/*.req 2>/dev/null | wc -l)" -ge 2 ]
    DHQ=$(ls "$DISPATCH_DIR"/queue/*.req 2>/dev/null | wc -l)
    rm -f "$DISPATCH_DIR"/queue/*.req; clear_markers
    DHM=$(dhmut jobs/arms.sh 's|    if len(got) >= 2:|    if len(got) >= 1:|')
    if [ -z "$DHM" ]; then
        bad "E MUTANT: could not build it (the sed matched nothing)"
    else
        bash "$DHM/jobs/arms.sh" >/dev/null 2>&1
        check "E MUTANT: counting either half as a run queues nothing (was $DHQ), so E can go red" \
            [ "$(ls "$DISPATCH_DIR"/queue/*.req 2>/dev/null | wc -l)" -eq 0 ]
    fi
    rm -f "$DISPATCH_DIR"/queue/*.req "$DHHALF/ERROR"; clear_markers
fi

# ------------------------------------------------ F. interop: requeue once
echo "== dispatch hardening F: 0 captures with the WSL interop signature is requeued once"
# The whole disc path of serve_one, as written, with the four programs it
# runs stubbed in a symlink tree: run_disc.sh prints the signature and the
# pull failure the real 1790325543-arms-vshconst-base run logged.
DHS=$(dhmut run_disc.sh '1a\
echo "<3>WSL (653704 - ) ERROR: UtilAcceptVsock:271: accept4 failed 110"; echo "pull failed or timed out"; exit 1' stub)
if [ -z "$DHS" ]; then
    bad "F: could not build the stub tree"
else
    rm -f "$DHS/make_test_iso.py" "$DHS/score_sweep.py"
    printf '%s\n' 'import sys' 'open(sys.argv[sys.argv.index("-o") + 1], "w").close()' > "$DHS/make_test_iso.py"
    printf '%s\n' 'import sys' 'sys.exit(0)' > "$DHS/score_sweep.py"
    : > "$DH/base.iso"
    DHREQ='{"requester":"selftest","purpose":"interop","ref":"HEAD","suites":["S"],"base_iso":"'"$DH/base.iso"'"}'
    dhreq "$DH/f" 1-lost "$DHREQ"
    dhserve "$DHS" "$DH/f" 1-lost ok 60
    check "F: first loss -- the attempt is kept aside with an interop ERROR" \
        grep -q "adb interop failure.*requeued once" "$DH/f/results/1-lost.interop1/ERROR"
    check "F: and the request is back in the queue, marked" grep -q interop_requeued "$DH/f/queue/1-lost.req"
    check "F: and results/1-lost is clear for the rerun" test ! -e "$DH/f/results/1-lost"
    dhserve "$DHS" "$DH/f" 1-lost ok 60
    check "F: second loss is final and says so" \
        grep -q "adb interop failure.*the one requeue, so it is final" "$DH/f/results/1-lost/ERROR"
    check "F: and nothing is queued a third time" test ! -e "$DH/f/queue/1-lost.req"
    # A 0-capture run WITHOUT the signature keeps the old ERROR and no requeue.
    DHS2=$(dhmut run_disc.sh '1a\
echo "pull failed or timed out"; exit 1' nosig)
    rm -f "$DHS2/make_test_iso.py" "$DHS2/score_sweep.py"
    cp "$DHS/make_test_iso.py" "$DHS/score_sweep.py" "$DHS2/"
    dhreq "$DH/f2" 1-lost "$DHREQ"
    dhserve "$DHS2" "$DH/f2" 1-lost ok 60
    check "F: without the signature, 0 captures is the plain ERROR and is not requeued" \
        bash -c 'grep -qx "ran but produced 0 captures; see run1.log and captures1/" "$1/results/1-lost/ERROR" && [ ! -e "$1/queue/1-lost.req" ]' _ "$DH/f2"
fi
unset DH DHM DHS DHS2 DHO DHV DHMO DHB DHSETS DHRC DHT DHHALF DHQ DHREQ DH_ADB_PIDS TAB
