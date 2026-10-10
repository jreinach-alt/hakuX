# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# lane.harnessfix1006 (#433, 10-06): the Nova's runs are on a known build, and a
# test build never stays on it. jobs/device_build.py reads the device's newest
# result.json; jobs/hold.sh take refuses a non-release Nova; the dispatcher's
# queue_master_restore queues the 60 s master run after a run off master.
#
# THE INCIDENT, 10-05 night: four holds and three measured runs (about 2 h of
# Nova time) went to runs on a test build that nothing had put back.
#
# Each leg names the world in which it fails:
#   (a) the newest Nova result on a branch or with an env set reads as
#       non-release: a check that could not see the build passes everything.
#   (b) take on a non-release Nova writes hold/nova: the gate is absent.
#   (c) the refusal does not name the build: the lane cannot tell why.
#   (d) take on a release Nova is refused: the gate is too strict, and nothing
#       could ever be measured after one test run.
#   (e) the Thor is gated too: its screening runs vary env on purpose.
#   (f) a run off master queues no restore, or queues one with the wrong ref,
#       env or length.
#   (g) a run on master queues a restore anyway (a restore per run, forever).
#   (h) a restore run queues another restore (the loop the requester check
#       prevents).
#   (i) the dispatcher's restore hook is not wired into the run path, so the
#       functions above are never called. Checked by grep of dispatcher.sh.
#   (j) the restore request reaches the disc path, which refuses a request
#       with no suites ("NO SUITES"): the restore is refused and the device
#       stays on the test build. The restore ends in serve_one before the
#       title/disc split, after its build, install and env reset.
#   (k) a resolved sha -- the shape every real request carries, since
#       request.sh resolves --ref to a concrete sha AT QUEUE TIME before a
#       request ever reaches the dispatcher, and no caller writes the
#       literal string "master" except the restore's own direct queue write
#       (restore_request, which bypasses request.sh entirely) -- that is
#       reachable from origin/master reads as a branch and is refused
#       forever, with no MASTER_SHA and no literal ref string to match. A
#       Nova actually on a clean, slightly-behind-trunk build would then be
#       refused on every take, and queue_master_restore would queue a
#       60 s restore after every run, release or not, forever. Found 10-07
#       by running `device_build.py check` against the Nova's own live
#       result after a real restore: a clean build, flagged non-release.
#
# SELFTEST_HOLD_SH points leg (b) at another hold.sh. The mutant legs at the
# end run with the fix removed, and must show the thing the real leg refuses.
#
# Uses its own DISPATCH_DIR, never the harness's and never the host's.

echo "== device_build.py + hold.sh's build gate: a test build never stays on the Nova"

DB_PY="$HERE/device_build.py"
DB_SH="${SELFTEST_HOLD_SH:-$HERE/hold.sh}"
DB_D="$T/devbuild/dispatch"
rm -rf "$DB_D"; mkdir -p "$DB_D/results" "$DB_D/queue" "$DB_D/running"

# dbrun <id> <mtime> <label> <ref> <env-json> <requester>: a result.json the way
# the dispatcher writes one (device_label, ref, env, apk_sha, requester), with
# its mtime set explicitly so "newest" does not depend on the clock's grain.
dbrun() {
    mkdir -p "$DB_D/results/$1"
    python3 - "$DB_D/results/$1/result.json" "$3" "$4" "$5" "$6" <<'PY'
import json, sys
p, label, ref, env, req = sys.argv[1:6]
json.dump({"device_label": label, "ref": ref, "env": json.loads(env),
           "apk_sha": "deadbeef", "requester": req}, open(p, "w"))
PY
    touch -d "@$2" "$DB_D/results/$1/result.json"
}
dbcheck() { python3 "$DB_PY" check "$DB_D" "$1"; }
dbrc() { local want=$1; shift; "$@" >/dev/null 2>&1; [ $? -eq "$want" ]; }
db_hold() { DISPATCH_DIR="$DB_D" HOLD_WAIT_INTERVAL=1 HOLD_IDLE_INTERVAL=1 bash "$DB_SH" "$@"; }
db_hold_rc() { local want=$1; shift; db_hold "$@" >/dev/null 2>&1; [ $? -eq "$want" ]; }

check "device_build.py parses" python3 -m py_compile "$DB_PY"
check "hold.sh parses (bash -n)" bash -n "$DB_SH"

# (a) the newest Nova run is on a test build: an env A/B, then a branch ref
dbrun old 1000 nova master '[]' lane.a
dbrun new 2000 nova master '["HAKUX_X=1"]' lane.b
check "(a) newest Nova run with an env set is refused by check (exit 4)" dbrc 4 dbcheck nova
check "(a) the refusal names the env" bash -c "python3 '$DB_PY' check '$DB_D' nova 2>&1 | grep -q 'HAKUX_X=1'"
check "(a) the refusal names the device" bash -c "python3 '$DB_PY' check '$DB_D' nova 2>&1 | grep -q '^nova is on a non-release build'"
dbrun new 2000 nova feature/branch '[]' lane.b
check "(a) a branch ref with no env is not master: refused" dbrc 4 dbcheck nova
check "(a) the refusal names the ref" bash -c "python3 '$DB_PY' check '$DB_D' nova 2>&1 | grep -q 'ref feature/branch'"
dbrun new 2000 nova master '[]' dispatch.restore
check "(a) a master run with no env is release (exit 0)" dbrc 0 dbcheck nova

# a result that predates the env field is not known to be master
dbrun new 2000 nova master '[]' lane.b
python3 - "$DB_D/results/new/result.json" <<'PY'
import json, sys
p = sys.argv[1]; r = json.load(open(p)); del r["env"]; json.dump(r, open(p, "w"))
PY
check "(a) a result with no env key is not release (exit 4)" dbrc 4 dbcheck nova

# (b) hold.sh refuses to take the Nova on a test build, and writes nothing
dbrun new 2000 nova master '["HAKUX_X=1"]' lane.b
check "(b) take on a non-release Nova exits 4" db_hold_rc 4 take nova lane.test write proof
check "(b) no hold/nova is written by the refused take" [ ! -e "$DB_D/hold/nova" ]
check "(b) wait refuses at once on a non-release Nova (exit 4)" db_hold_rc 4 wait nova lane.test 5 write proof
# (c) the refusal names the build on stderr
check "(c) the refusal names the build on stderr" bash -c "DISPATCH_DIR='$DB_D' bash '$DB_SH' take nova lane.test write proof 2>&1 >/dev/null | grep -q 'HAKUX_X=1'"

# (d) a master run on the Nova is taken like any other
dbrun new 3000 nova master '[]' lane.b
check "(d) take on a release Nova exits 0" db_hold_rc 0 take nova lane.test write proof
check "(d) the taken hold is the taker's" bash -c "[ \"\$(cat '$DB_D/hold/nova')\" = lane.test ]"
db_hold release nova lane.test >/dev/null 2>&1

# (e) the Thor is not gated: its screening runs vary env on purpose
dbrun thorlast 4000 thor master '["HAKUX_X=1"]' lane.b
check "(e) take on a non-release Thor is not refused (exit 0)" db_hold_rc 0 take thor lane.test write proof
db_hold release thor lane.test >/dev/null 2>&1

# (f) the restore after a run off master: one request, master, no env, 60 s
dbrun new 2000 nova master '["HAKUX_X=1"]' lane.b
before=$(ls "$DB_D/queue" | wc -l)
rid=$(python3 "$DB_PY" restore "$DB_D" nova new)
after=$(ls "$DB_D/queue" | wc -l)
check "(f) a run off master queues exactly one restore request" [ $((after - before)) -eq 1 ]
check "(f) the restore's id is printed" [ -n "$rid" ]
rq=$(ls "$DB_D/queue"/*"$rid"*.req 2>/dev/null | head -1)
check "(f) the restore names ref master, env [], 60 s, device nova, requester dispatch.restore" \
    python3 -c "import json,sys; r=json.load(open(sys.argv[1])); assert r['ref']=='master' and r['env']==[] and r['seconds']==60 and r['device']=='nova' and r['requester']=='dispatch.restore' and r['title']==''" "$rq"

# (g) a run on master queues nothing
dbrun ok 5000 nova master '[]' lane.b
before=$(ls "$DB_D/queue" | wc -l)
python3 "$DB_PY" restore "$DB_D" nova ok >/dev/null
check "(g) a run on master queues no restore" [ "$(ls "$DB_D/queue" | wc -l)" -eq "$before" ]

# (h) a restore run that is itself off master queues no further restore
dbrun rs 6000 nova master '["HAKUX_X=1"]' dispatch.restore
before=$(ls "$DB_D/queue" | wc -l)
python3 "$DB_PY" restore "$DB_D" nova rs >/dev/null
check "(h) a restore run queues no restore of its own" [ "$(ls "$DB_D/queue" | wc -l)" -eq "$before" ]

# (i) the dispatcher calls the hook after both result writers, and the gate in hold.sh
check "(i) dispatcher.sh calls queue_master_restore after the soak and disc results" \
    [ "$(grep -cF 'queue_master_restore "$id"' "$HERE/../dispatcher.sh")" -ge 2 ]
check "(i) dispatcher.sh's hook calls device_build.py restore" grep -qF 'jobs/device_build.py" restore' "$HERE/../dispatcher.sh"

# (j) the restore ends in serve_one before the title and disc split. Ordering,
# not a grep for a line: the block must come first, write the kind=restore
# result that device_build.py reads, and sit before the "NO SUITES" refusal.
db_restore_exit() {   # <dispatcher.sh> ; 0 when the restore ends before the split
    python3 - "$1" <<'PY'
import sys
s = open(sys.argv[1]).read()
r = s.find('if [ "$requester" = dispatch.restore ]; then')
t = s.find('if [ -n "$title" ]; then', r) if r >= 0 else -1
n = s.find('"no suites named"')
sys.exit(0 if r >= 0 and t > r and n > r and 'kind="restore"' in s else 1)
PY
}
check "(j) the dispatcher ends a master restore before the title/disc split, with a restore result" \
    db_restore_exit "$HERE/../dispatcher.sh"

# (k) a resolved sha, reachable from origin/master, is release -- the real
# shape, not the literal "master" every fixture above uses. A throwaway
# repo, not $REPO: this lane's own commits become part of master's history
# the moment this PR is folded, so a real sha from this checkout would flip
# from "not on trunk" to "on trunk" right then and the leg would rot silently.
DB_REPO="$T/devbuild/repo"; rm -rf "$DB_REPO"; mkdir -p "$DB_REPO"
git -C "$DB_REPO" init -q
git -C "$DB_REPO" -c user.email=t@t.test -c user.name=t commit -q --allow-empty -m trunk
TRUNK_SHA=$(git -C "$DB_REPO" rev-parse --short HEAD)
git -C "$DB_REPO" update-ref refs/remotes/origin/master HEAD
git -C "$DB_REPO" checkout -q -b offtrunk
git -C "$DB_REPO" -c user.email=t@t.test -c user.name=t commit -q --allow-empty -m offtrunk
BRANCH_SHA=$(git -C "$DB_REPO" rev-parse --short HEAD)
dbcheck_repo() { DISPATCH_REPO="$1" python3 "$DB_PY" check "$DB_D" nova; }

dbrun ktrunk 7000 nova "$TRUNK_SHA" '[]' lane.gpunonrender
check "(k) a resolved sha reachable from origin/master is release, no MASTER_SHA needed" \
    dbrc 0 dbcheck_repo "$DB_REPO"

dbrun kbranch 8000 nova "$BRANCH_SHA" '[]' lane.b
check "(k) a resolved sha never merged to trunk is refused even with DISPATCH_REPO set" \
    dbrc 4 dbcheck_repo "$DB_REPO"

# MUTANTS: the fix removed must go red. Each mutant is checked for the very
# behaviour its leg above asserts, so a leg that passes on the mutant is vacuous.
DB_MUT="$T/devbuild/mut"; mkdir -p "$DB_MUT"
sed 's/build_gate "\$label" || exit \$?/:/' "$DB_SH" > "$DB_MUT/hold.sh"
check "the real hold.sh carries both gate calls (take and wait)" [ "$(grep -c 'build_gate "$label" ||' "$DB_SH")" -ge 2 ]
check "mutant built: hold.sh with its gate calls replaced by :" [ "$(grep -c 'build_gate "$label" ||' "$DB_MUT/hold.sh")" -eq 0 ]
cp "$DB_PY" "$DB_MUT/device_build.py"
sed -i 's/    return not build_of(rec)\[0\]/    return False/' "$DB_MUT/device_build.py"
check "mutant: hold.sh without the gate takes the non-release Nova (leg (b) is not vacuous)" \
    bash -c "DISPATCH_DIR='$DB_D' bash '$DB_MUT/hold.sh' take nova lane.test write proof >/dev/null 2>&1"
rm -f "$DB_D/hold/nova" "$DB_D/hold/nova.why"
check "mutant: device_build.py that never asks for a restore queues nothing (leg (f) is not vacuous)" \
    bash -c "b=\$(ls '$DB_D/queue' | wc -l); python3 '$DB_MUT/device_build.py' restore '$DB_D' nova new >/dev/null; [ \$(ls '$DB_D/queue' | wc -l) -eq \$b ]"

# The restore exit (leg (j)) removed from a copy of dispatcher.sh must fail the
# same ordering check, or the leg is vacuous.
DB_DISP_MUT="$DB_MUT/dispatcher.sh"
sed 's/if \[ "\$requester" = dispatch.restore \]; then/if false; then/' "$HERE/../dispatcher.sh" > "$DB_DISP_MUT"
check "mutant built: dispatcher.sh with the restore exit disabled" [ "$(grep -c 'if false; then' "$DB_DISP_MUT")" -eq 1 ]
db_restore_exit_absent() { ! db_restore_exit "$1"; }
check "mutant: without the restore exit the restore is not ended before the split (leg (j) is not vacuous)" \
    db_restore_exit_absent "$DB_DISP_MUT"

# Leg (k)'s mutant: device_build.py with the ancestry check's contribution
# to build_of removed. The trunk sha from (k) above is still the Nova's
# newest result (ktrunk, mtime 7000 < kbranch's 8000 -- re-run as newest).
dbrun ktrunk 9000 nova "$TRUNK_SHA" '[]' lane.gpunonrender
sed 's/ or _on_trunk(ref)//' "$DB_PY" > "$DB_MUT/device_build_k.py"
check "mutant built: device_build.py without the ancestry check at the call site" \
    bash -c "! grep -q 'or _on_trunk(ref)' '$DB_MUT/device_build_k.py'"
check "mutant: without the ancestry check a trunk sha is wrongly refused (leg (k) is not vacuous)" \
    bash -c "DISPATCH_REPO='$DB_REPO' python3 '$DB_MUT/device_build_k.py' check '$DB_D' nova; [ \$? -eq 4 ]"
