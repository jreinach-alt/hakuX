# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# #433 lane.restoreprio1011, 10-11. idlewatch's queue-starved jam fired on a
# lone dispatch.restore 7+ times since 15:36 PDT 10-10: restore_request names
# the restore a bare "<epoch>-dispatch.restore-<run8>" id (device_build.py),
# and the dispatcher serves queue/*.req in ASCII order (request.sh:726-732),
# so a bare id sorts behind every HAKUX_RELEASE_PRIO=1 request -- which is
# every request a lane queues while the restore waits. Hostops cleared it by
# hand each time, renaming it to a "0-" id.
#
# NOTES.md works out why the fix belongs in jobs/hold.sh's build gate rather
# than in restore_request itself: every served request -- restore, title
# soak, or suites/program run alike -- installs its own apk and writes its
# own env before any of them reach a soak or a disc (dispatcher.sh serve_one,
# unconditional ahead of every branch). So the bare id costs a SERVED
# measurement nothing; it only matters to a caller about to run something BY
# HAND on whatever the hold leaves installed, and that caller already goes
# through hold.sh's build gate (jobs/hold.sh:198-215, called at take's :244
# and wait's :257). The gate now promotes on its own refusal instead of just
# naming the build and giving up.
#
# Each leg names the world in which it fails:
#   (a) a refused take with a restore already queued leaves it bare: nothing
#       moved it ahead of the release-tier stream still feeding the device.
#   (b) a refused take with none queued never gets one: the device is stuck
#       on the test build until a human notices and queues one by hand.
#   (c) wait exits 4 on the first refusal instead of outlasting a restore
#       that is about to land -- the original defect `take` had, inherited
#       by `wait` for lack of a retry loop.
#   (d) restore_request's own id stays bare: the dispatcher's own post-run
#       hook (queue_master_restore, called with no hold involved) must not
#       start racing the release-tier queue for a top slot either -- only a
#       caller stuck behind a refused hold needs that.
#
# Addendum 1 (lane.local, 10-11): legs (a)-(d) above left a race in `wait`.
# The dispatcher claims its next request the instant the promoted restore
# finishes (checks hold/<label> only at the top of its tick, before the
# queue: dispatcher.sh:2354-2363) -- seconds before wait's next poll. A
# poll that trusted build_gate alone would read the restore's own
# result.json (still the newest result on disk) and pass, taking the hold
# while a fresh off-master request is running right now. `wait` now asks
# `device_build.py running` what is in running/ before trusting a pass:
#   (e) the label's own restore is running right now: wait must take the
#       hold before it finishes, not wait for its result to land.
#   (f) the gate alone would pass (the newest result IS a master restore),
#       but a non-restore request for the label is running right now: wait
#       must not trust that stale pass -- it keeps polling and times out.
#
# Uses its own DISPATCH_DIR, never the harness's shared one and never the
# host's real dispatch/ directory.

echo "== jobs/hold.sh's build gate promotes a starved master restore (#433)"

RP_PY="$HERE/device_build.py"
RP_SH="${SELFTEST_HOLD_SH:-$HERE/hold.sh}"
RP_D="$T/restoreprio/dispatch"
rm -rf "$RP_D"; mkdir -p "$RP_D/results" "$RP_D/queue" "$RP_D/running"

# rprun <id> <mtime> <label> <ref> <env-json> <requester>: a result.json the
# way the dispatcher writes one, as 99-build-gate.sh's dbrun does.
rprun() {
    mkdir -p "$RP_D/results/$1"
    python3 - "$RP_D/results/$1/result.json" "$3" "$4" "$5" "$6" <<'PY'
import json, sys
p, label, ref, env, req = sys.argv[1:6]
json.dump({"device_label": label, "ref": ref, "env": json.loads(env),
           "apk_sha": "deadbeef", "requester": req}, open(p, "w"))
PY
    touch -d "@$2" "$RP_D/results/$1/result.json"
}
# rp_queue_bare <id>: a bare dispatch.restore request for nova, the shape
# restore_request() writes, queued directly (the way hostops found it stuck).
rp_queue_bare() {
    python3 -c 'import json,sys
json.dump({"id":sys.argv[2],"requester":"dispatch.restore",
           "purpose":"master restore after run off1","program":"","suites":[],
           "tests":[],"skip_tests":[],"ref":"master","arm":"solo","runs":1,
           "title":"","seconds":60,"device":"nova","pull_glob":"",
           "audio_capture":"","base_iso":"","perflog":"","only_tests":[],
           "env":[],"frames_every":0,"route_name":"","route":"","title_id":"",
           "title_state":"any","identified":"","expect":"","expect_sha":"",
           "no_expect":"","priority":"study",
           "queued_utc":"2026-10-10T15:36:00Z"}, open(sys.argv[1],"w"))' \
        "$RP_D/queue/$1.req" "$1"
}
rp_hold() { DISPATCH_DIR="$RP_D" HOLD_WAIT_INTERVAL=1 HOLD_IDLE_INTERVAL=1 bash "$RP_SH" "$@"; }
rp_hold_rc() { local want=$1; shift; rp_hold "$@" >/dev/null 2>&1; [ $? -eq "$want" ]; }
rp_restores() { ls "$RP_D/queue"/*dispatch.restore*.req 2>/dev/null; }
# rp_running_restore <id>: nova's own dispatch.restore request, claimed and
# mid-serve (the shape dispatcher.sh moves from queue/ to running/).
rp_running_restore() {
    python3 -c 'import json,sys
json.dump({"id":sys.argv[2],"requester":"dispatch.restore","device":"nova",
           "ref":"master","env":[],"seconds":60}, open(sys.argv[1],"w"))' \
        "$RP_D/running/$1.req" "$1"
}
# rp_running_other <id> <requester> <ref>: some other request running for
# nova right now -- a run that will leave the device off master when it ends.
rp_running_other() {
    python3 -c 'import json,sys
json.dump({"id":sys.argv[2],"requester":sys.argv[3],"device":"nova",
           "ref":sys.argv[4],"env":[]}, open(sys.argv[1],"w"))' \
        "$RP_D/running/$1.req" "$1" "$2" "$3"
}

check "device_build.py parses" python3 -m py_compile "$RP_PY"
check "hold.sh parses (bash -n)" bash -n "$RP_SH"

# (a) a refused take with a restore already queued promotes it in place
rprun off1 1000 nova feature/branch '[]' lane.a
bare="1000-dispatch.restore-deadbeef"
rp_queue_bare "$bare"
check "(a) fixture: the bare restore is queued, unpromoted" [ -e "$RP_D/queue/$bare.req" ]
rp_err=$(DISPATCH_DIR="$RP_D" HOLD_WAIT_INTERVAL=1 bash "$RP_SH" take nova lane.test write proof 2>&1 >/dev/null)
rp_rc=$?
check "(a) a refused take exits 4" [ "$rp_rc" -eq 4 ]
check "(a) the bare restore request is gone (renamed, not duplicated)" [ ! -e "$RP_D/queue/$bare.req" ]
check "(a) exactly one dispatch.restore request remains queued" [ "$(rp_restores | wc -l)" -eq 1 ]
check "(a) it now carries the 0- priority prefix" [ -e "$RP_D/queue/0-$bare.req" ]
check "(a) its content is unchanged (device, requester, ref) aside from the filename" \
    python3 -c "import json,sys; r=json.load(open(sys.argv[1])); assert r['device']=='nova' and r['requester']=='dispatch.restore' and r['ref']=='master'" "$RP_D/queue/0-$bare.req"
check "(a) the take's refusal says what it promoted" bash -c "printf '%s' \"\$1\" | grep -q 'promoted: 0-$bare.req'" _ "$rp_err"
rm -f "$RP_D/queue"/*dispatch.restore*.req

# (b) a refused take with none queued queues exactly one, already promoted
check "(b) no restore is queued for nova yet" [ -z "$(rp_restores)" ]
check "(b) a refused take exits 4" rp_hold_rc 4 take nova lane.test write proof
check "(b) exactly one dispatch.restore request is now queued" [ "$(rp_restores | wc -l)" -eq 1 ]
rp_file=$(rp_restores)
check "(b) it carries the 0- priority prefix" bash -c 'case "$1" in */0-*) true;; *) false;; esac' _ "$rp_file"
check "(b) it names nova, master, env [], 60 s" \
    python3 -c "import json,sys; r=json.load(open(sys.argv[1])); assert r['device']=='nova' and r['ref']=='master' and r['env']==[] and r['seconds']==60 and r['requester']=='dispatch.restore'" "$rp_file"
check "(b) take on the same refusal again queues no second one" rp_hold_rc 4 take nova lane.test write proof
check "(b) still exactly one dispatch.restore request" [ "$(rp_restores | wc -l)" -eq 1 ]
rm -f "$RP_D/queue"/*dispatch.restore*.req

# (c) wait outlasts a refusal and passes once the fixture restore result lands
rprun off2 2000 nova feature/branch '[]' lane.a
( sleep 2
  rm -f "$RP_D/queue"/*dispatch.restore*.req
  rprun restored 3000 nova master '[]' dispatch.restore ) &
rp_bg=$!
t0=$(date +%s)
check "(c) wait passes once the restore result lands, inside its timeout" rp_hold_rc 0 wait nova lane.test 12 write proof
dt=$(( $(date +%s) - t0 ))
wait "$rp_bg"
check "(c) it did not return instantly (it outlasted at least one refusal)" [ "$dt" -ge 2 ]
check "(c) it did not run out its full 12 s timeout" [ "$dt" -le 10 ]
check "(c) the hold it took is lane.test's" bash -c "[ \"\$(cat '$RP_D/hold/nova')\" = lane.test ]"
rp_hold release nova lane.test >/dev/null 2>&1
rm -f "$RP_D/queue"/*dispatch.restore*.req "$RP_D/hold/nova" "$RP_D/hold/nova.why"

# (d) a release-tier stream with no hold involved leaves the restore bare:
# device_build.py's own post-run hook (what the dispatcher calls after every
# run, queue_master_restore) is untouched by this lane's fix.
rprun off3 4000 nova feature/branch '[]' lane.a
rid=$(python3 "$RP_PY" restore "$RP_D" nova off3)
check "(d) the dispatcher's own hook queues a restore" [ -n "$rid" ]
check "(d) its id is bare (no 0- prefix)" bash -c "case '$rid' in 0-*) false;; *) true;; esac"
check "(d) the queued file's name is bare too" [ -e "$RP_D/queue/$rid.req" ]
rm -f "$RP_D/queue"/*dispatch.restore*.req

# (e)-(f) and their mutants below each read the device's newest result by
# mtime (build_of/last_run over ALL of results/, not just what one leg
# writes) -- each resets results/ to just its own fixture first, or an
# earlier leg's record (leg (d)'s off3 at mtime 4000, or a later leg's own
# "master restore" record) would still be "newest" and the wrong reason
# would make a check pass or fail.
rp_results_reset() { rm -rf "$RP_D/results"; mkdir -p "$RP_D/results"; }

# (e) the label's own restore is running right now: wait takes the hold
# immediately, without waiting for the restore's result to land -- a gate
# pass alone cannot be trusted the instant the restore ends, since the
# dispatcher can claim its next request before this loop's next poll would
# see that result (addendum 1).
rp_results_reset
rprun offE 1000 nova feature/branch '[]' lane.a
rp_running_restore restoreE
t0=$(date +%s)
check "(e) wait on a running restore exits 0 without waiting for a result" rp_hold_rc 0 wait nova lane.test 10 write proof
dt=$(( $(date +%s) - t0 ))
check "(e) it did not wait out the timeout" [ "$dt" -le 5 ]
check "(e) the hold it took is lane.test's" bash -c "[ \"\$(cat '$RP_D/hold/nova')\" = lane.test ]"
rp_hold release nova lane.test >/dev/null 2>&1
rm -f "$RP_D/running"/*.req "$RP_D/queue"/*dispatch.restore*.req

# (f) the newest result IS a master restore (build_gate alone would pass),
# but a non-restore request for nova is running right now and will leave
# the device off master when it ends: wait must not trust the stale pass.
rp_results_reset
rprun restoredF 2000 nova master '[]' dispatch.restore
rp_running_other otherF lane.b feature/branch
t0=$(date +%s)
check "(f) wait with a non-restore request running times out (exit 4)" rp_hold_rc 4 wait nova lane.test 3 write proof
dt=$(( $(date +%s) - t0 ))
check "(f) it waited out the timeout, not take early" [ "$dt" -ge 3 ]
check "(f) no hold was written" [ ! -e "$RP_D/hold/nova" ]
rm -f "$RP_D/running"/*.req

# MUTANT: hold.sh's wait loop with the running-check's exit code forced to 2
# ("nothing running"), reproducing attempt 1's race exactly -- gate-only,
# trusting whatever build_gate's last-result read says. Copies device_build.py
# alongside so build_gate's own device_build.py calls still resolve.
RP_HMUT="$T/restoreprio/hmut"; mkdir -p "$RP_HMUT"
cp "$RP_PY" "$RP_HMUT/device_build.py"
sed 's/rrc=\$?/rrc=2/' "$RP_SH" > "$RP_HMUT/hold.sh"
check "the real hold.sh reads device_build.py running's exit code" \
    [ "$(grep -c 'rrc=\$?' "$RP_SH")" -eq 1 ]
check "mutant built: hold.sh with rrc forced to 2 (treats everything as idle)" \
    [ "$(grep -c 'rrc=\$?' "$RP_HMUT/hold.sh")" -eq 0 ]

rp_results_reset
rprun offEm 1000 nova feature/branch '[]' lane.a
rp_running_restore restoreEm
check "mutant: without the running check, a running restore is not taken early (leg (e) is not vacuous)" \
    bash -c "DISPATCH_DIR='$RP_D' HOLD_WAIT_INTERVAL=1 bash '$RP_HMUT/hold.sh' wait nova lane.test 3 write proof >/dev/null 2>&1; [ \$? -eq 4 ]"
rm -f "$RP_D/running"/*.req "$RP_D/hold/nova" "$RP_D/hold/nova.why" "$RP_D/queue"/*dispatch.restore*.req

rp_results_reset
rprun restoredFm 2000 nova master '[]' dispatch.restore
rp_running_other otherFm lane.b feature/branch
check "mutant: without the running check, a non-restore request running is missed and the hold is taken anyway (leg (f) is not vacuous)" \
    bash -c "DISPATCH_DIR='$RP_D' HOLD_WAIT_INTERVAL=1 bash '$RP_HMUT/hold.sh' wait nova lane.test 3 write proof >/dev/null 2>&1; [ \$? -eq 0 ]"
rm -f "$RP_D/running"/*.req "$RP_D/hold/nova" "$RP_D/hold/nova.why"

# MUTANT: device_build.py's promote command, with its rename disabled (it
# still reports "promoted"/"queued", but never moves the file) -- must turn
# leg (a) red: the bare request it was given must stay bare.
RP_MUT="$T/restoreprio/mut"; mkdir -p "$RP_MUT"
cp "$RP_PY" "$RP_MUT/device_build.py"
sed -i \
    -e 's/print("promoted: %s" % _promote(pending))/print("promoted: %s" % os.path.basename(pending))/' \
    -e 's/print("queued: %s" % _promote(path))/print("queued: %s" % os.path.basename(path))/' \
    "$RP_MUT/device_build.py"
check "mutant built: promote's rename call sites are gone" \
    [ "$(grep -c '% _promote(' "$RP_MUT/device_build.py")" -eq 0 ]
check "the real device_build.py still has both rename call sites" \
    [ "$(grep -c '% _promote(' "$RP_PY")" -eq 2 ]

bare_mut="5000-dispatch.restore-mutant1"
rp_queue_bare "$bare_mut"
python3 "$RP_MUT/device_build.py" promote "$RP_D" nova >/dev/null 2>&1
check "mutant: the bare request given to promote is still there, unrenamed (leg (a) is not vacuous)" \
    [ -e "$RP_D/queue/$bare_mut.req" ]
check "mutant: and it was never given the 0- prefix" [ ! -e "$RP_D/queue/0-$bare_mut.req" ]
rm -f "$RP_D/queue"/*dispatch.restore*.req
