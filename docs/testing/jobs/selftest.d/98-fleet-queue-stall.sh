# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# fleet.py: work nobody will claim must wake the board, and nothing else may.

echo "== fleet: a dispatch request every live claimer has walked past is a FAIL"
# WHY. status.sh renders "N arms on a device, M queued" every tick, and its
# own header says it exists because "a jammed fleet and a running fleet
# rendered identically". It fixed the RENDERING and nothing escalated the
# numbers, so on 2026-09-20 four arms sat unclaimed -- the oldest eighteen
# hours -- with two healthy handhelds, and nobody was woken.
#
# THE QUIET CASES ARE AS LOAD-BEARING AS THE LOUD ONES. Every FAIL line in
# fleet.py is a board wake-up: board.sh keeps fleet.py's stderr lines that
# start `FAIL` and starts a model session on any hit, so a FAIL that fires on
# a healthy fleet spends a window every twenty minutes for nothing.
#
# The first version of this check was "old, and a result landed since", and
# audit pass 1 on PR #206 (H1) showed it cannot tell "passed over" from
# "waiting its turn". Its fixtures could not see that because every one had a
# queue of depth one and lane files holding pid 1, which affinity.py's
# kill -0 reads as dead -- so they modelled an idle fleet with no live workers
# and called it a backlog. These build what the dispatcher really leaves on
# disk: live and dead lane pids, running/ entries with owners and claim times,
# siblings sharing a prediction, holds.
#
# SELFTEST_FLEET_SRC points the whole section at a directory holding another
# fleet.py/affinity.py pair -- a mutant, or master's -- so each check can be
# seen to fail rather than reasoned about. Anything else they import comes
# from the live tree. docs/lanes/dispatch-script-deps/NOTES.md lists the
# mutants and which check each one turns red.
QSRC="${SELFTEST_FLEET_SRC:-$TESTING}"

# qs <spec-json>: build a dispatch dir from the spec, ask fleet.queue_stall(),
# print "q=<queued> stalled=<ids> held=<ids> blind=<None|why>". Times are
# minutes before now. The spec rides on argv, not stdin: `python3 -` reads its
# PROGRAM from stdin, so a pipe would be swallowed by the heredoc.
qs() {
    python3 - "$T/qs" "$QSRC" "$1" "$TESTING" <<'PY'
import json, os, shutil, subprocess, sys, time
root, src, spec, testing = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), sys.argv[4]
shutil.rmtree(root, ignore_errors=True)
for d in ("queue", "running", "results", "lanes", "hold"):
    os.makedirs(os.path.join(root, d))
now = time.time()
def touch(p, minutes):
    t = now - float(minutes) * 60
    os.utime(p, (t, t))
def req(p, d):
    with open(p, "w") as f:
        json.dump({k: d[k] for k in ("device", "expect") if k in d}, f)
for q in spec.get("queue", []):
    p = os.path.join(root, "queue", q["name"] + ".req")
    req(p, q); touch(p, q["age"])
for r in spec.get("running", []):
    p = os.path.join(root, "running", r["name"] + ".req")
    req(p, r); touch(p, r["written"])
    o = os.path.join(root, "running", r["name"] + ".owner")
    open(o, "w").write(r["owner"] + "\n"); touch(o, r["claimed"])
for r in spec.get("between", []):       # an owner file whose request has left
    o = os.path.join(root, "running", r["name"] + ".owner")
    open(o, "w").write(r["owner"] + "\n"); touch(o, r["claimed"])
for r in spec.get("results", []):
    d = os.path.join(root, "results", r["name"])
    os.makedirs(d)
    req(os.path.join(d, "request.json"), r)
    touch(d, r["mtime"])
# A live pid is this process's own; a dead one is a child already reaped.
dead = subprocess.Popen(["true"]); dead.wait()
for lane, state in spec.get("lanes", {}).items():
    pid = os.getpid() if state == "live" else dead.pid
    open(os.path.join(root, "lanes", lane), "w").write("%d\n" % pid)
for h in spec.get("hold", []):
    open(os.path.join(root, "hold", h), "w").close()
# The last change to the claimer set. Stamped after every entry is made,
# because making one moves its directory's mtime to now.
changed = spec.get("changed", 600)
for d in ("lanes", "hold"):
    touch(os.path.join(root, d), changed)
for lane in spec.get("lanes", {}):
    touch(os.path.join(root, "lanes", lane), changed)
os.environ["DISPATCH_DIR"] = root
# The live tree second, for the modules a mutant directory does not carry
# (gh_rest.py): fleet.py puts its own directory first, so its fleet.py and
# affinity.py are the ones imported.
sys.path.insert(0, testing)
sys.path.insert(0, src)
import fleet
assert fleet.D == root, "fleet.py did not read this fixture's DISPATCH_DIR"
stalled, on_hold, blind = fleet.queue_stall(now=now)
print("q=%d stalled=%s held=%s blind=%s" % (
    len(os.listdir(os.path.join(root, "queue"))),
    ",".join(sorted(r[0] for r in stalled)),
    ",".join(sorted(r[0] for r in on_hold)), blind))
PY
}
qsis() {   # <label> <expected> <spec>: one check, with the actual on a miss
    local got; got=$(qs "$3" 2>&1)
    if [ "$got" = "$2" ]; then ok "$1"; else bad "$1 -- got: $got"; fi
}
ALL3='"lanes":{"nova":"live","thor":"live","desktop":"live"}'

# ------------------------------------------------------------------ LOUD
# The incident as the directory recorded it: the pair queued 300 min ago,
# nova since claimed later work, thor and desktop idle for hours. Positive
# control: every quiet case below is only informative because this one fires.
qsis "2026-09-20: nova claimed later work, thor and desktop idle -> FAIL" \
     "q=2 stalled=1100-arms-remote-base,1100-arms-remote-fix held= blind=None" \
     '{'"$ALL3"',
       "queue":[{"name":"1100-arms-remote-base","age":300,"expect":"k1.json"},
                {"name":"1100-arms-remote-fix","age":300,"expect":"k1.json"}],
       "running":[{"name":"1200-drvab77-t30-1","owner":"nova","written":200,"claimed":150}],
       "results":[{"name":"1050-arms-remote-base","mtime":290,"expect":"k0.json"}]}'
# The incident's quiet half: 05:44 to 14:35, nothing running anywhere and the
# arms still queued. The old check called this shape "backlog -> quiet".
qsis "an idle live fleet that leaves a request queued -> FAIL" \
     "q=1 stalled=1500-arms-x held= blind=None" \
     '{'"$ALL3"', "queue":[{"name":"1500-arms-x","age":300}],
       "results":[{"name":"1400-done","mtime":400}]}'
# No exemption for the corpus sweep. z-* waits behind agent work because of
# where it sorts (the quiet case below), not because this check looks away,
# so a sweep request that every idle claimer walks past is a stall too.
qsis "a sweep request every idle claimer walks past -> FAIL" \
     "q=1 stalled=z-tip-050-W_param held= blind=None" \
     '{'"$ALL3"', "queue":[{"name":"z-tip-050-W_param","age":999}],
       "results":[{"name":"1400-done","mtime":600}]}'
# A dead worker is not a claimer. Its orphan in running/ sorts BEFORE the
# request, so if thor counted as alive it would read as "busy with earlier
# work" and hide the stall.
qsis "a dead lane's orphan does not make it a claimer -> FAIL" \
     "q=1 stalled=1500-arms-x held= blind=None" \
     '{"lanes":{"nova":"live","thor":"dead","desktop":"live"},
       "queue":[{"name":"1500-arms-x","age":300}],
       "running":[{"name":"1400-orphan","owner":"thor","written":500,"claimed":400}],
       "results":[{"name":"1300-done","mtime":400}]}'
qsis "an explicit pin to a label no live worker serves, and nobody held -> FAIL" \
     "q=1 stalled=1700-soak held= blind=None" \
     '{"lanes":{"thor":"live","desktop":"live"},
       "queue":[{"name":"1700-soak","age":300,"device":"nova"}]}'

# ------------------------------------------------------------------ QUIET
# H1's case, and the one that decides the design. A burst of two pairs, both
# pinned to nova by rule 2; pair 1's base finished after the burst, its fix is
# on nova now; pair 2 has waited 150 min, past the old 120-min threshold;
# thor meanwhile finished one later soak and is running another. The old rule
# fires ("a result landed since"), and so does audit pass 1's proposed remedy
# ("a request queued after me completed": 1020 > 1000). Nova is busy with
# work it reached BEFORE pair 2, so pair 2 is waiting its turn.
qsis "H1: a pair waiting for its own busy device while the other serves later work -> quiet" \
     "q=2 stalled= held= blind=None" \
     '{'"$ALL3"',
       "queue":[{"name":"1000-arms-p2-base","age":150,"expect":"k2.json"},
                {"name":"1000-arms-p2-fix","age":150,"expect":"k2.json"}],
       "running":[{"name":"1000-arms-p1-fix","owner":"nova","written":150,"claimed":100,"expect":"k1.json"},
                  {"name":"1030-soak-y","owner":"thor","written":130,"claimed":60}],
       "results":[{"name":"1000-arms-p1-base","mtime":100,"expect":"k1.json"},
                  {"name":"1020-soak-x","mtime":70}]}'
qsis "normal: a recent request on a fleet busy with earlier work -> quiet" \
     "q=1 stalled= held= blind=None" \
     '{'"$ALL3"', "queue":[{"name":"1300-lane-x","age":5}],
       "running":[{"name":"1250-a","owner":"nova","written":40,"claimed":30},
                  {"name":"1260-b","owner":"thor","written":25,"claimed":20}]}'
qsis "sweep: z-* behind agent work waits by ORDER, not by exemption -> quiet" \
     "q=1 stalled= held= blind=None" \
     '{'"$ALL3"', "queue":[{"name":"z-tip-050-W_param","age":999}],
       "running":[{"name":"1400-arms-a-base","owner":"nova","written":30,"claimed":20},
                  {"name":"1400-arms-b-base","owner":"thor","written":30,"claimed":15}]}'
# Two shapes, because they are held back by different things. The unpinned
# one is quiet anyway: an idle claimer's evidence starts from when the request
# was written. The one pinned to a label nobody serves has no claimer to
# wait for, so only the age gate keeps a request seconds old -- one a
# restarting worker is about to take -- from being called stranded.
qsis "just queued: younger than a few worker ticks is not judged -> quiet" \
     "q=2 stalled= held= blind=None" \
     '{'"$ALL3"', "queue":[{"name":"1500-arms-x","age":1},
                            {"name":"1501-soak","age":1,"device":"odin"}],
       "results":[{"name":"1400-done","mtime":400}]}'
# Idle is not proven by an empty running/: a claimer that finished a moment
# ago has not walked the queue since. This is the gap between a finish and
# the next walk, and the only thing that makes "idle" evidence at all.
qsis "a claimer that just finished has not walked yet -> quiet" \
     "q=1 stalled= held= blind=None" \
     '{'"$ALL3"', "queue":[{"name":"1500-arms-x","age":300}],
       "results":[{"name":"1400-done","mtime":1}]}'
qsis "a claimer between two requests (owner file, request gone) is not idle -> quiet" \
     "q=1 stalled= held= blind=None" \
     '{'"$ALL3"', "queue":[{"name":"1500-arms-x","age":300}],
       "between":[{"name":"1450-requeued","owner":"nova","claimed":30}],
       "results":[{"name":"1400-done","mtime":400}]}'
# Evidence goes stale when what decides the pin changes. A worker restarted
# (the lane set changed 50 min ago) after nova claimed its later work 100 min
# ago: what nova walked past then says nothing about now.
qsis "evidence older than a change to the lane set does not count -> quiet" \
     "q=1 stalled= held= blind=None" \
     '{'"$ALL3"', "changed":50, "queue":[{"name":"1500-arms-x","age":300}],
       "running":[{"name":"1600-later","owner":"nova","written":150,"claimed":100}],
       "results":[{"name":"1400-done","mtime":100}]}'
# ...and when the request's own siblings move (affinity.py rule 2). thor is
# running 1900-arms-k-rerun, which sorts after 1800-arms-k-fix and was claimed
# after it -- but it names the same prediction, so its claim is what now pins
# the fix arm TO thor. That is the fix arm's turn coming, not a skip.
qsis "a claim by the request's own sibling is not evidence -> quiet" \
     "q=1 stalled= held= blind=None" \
     '{'"$ALL3"', "queue":[{"name":"1800-arms-k-fix","age":300,"expect":"k.json"}],
       "running":[{"name":"1900-arms-k-rerun","owner":"thor","written":100,"claimed":90,"expect":"k.json","device":"thor"}],
       "results":[{"name":"1400-done","mtime":400}]}'

# ------------------------------------------------------------------ HELD
# Out of service on purpose is reported on stdout and is never a wake-up.
# M1 (audit pass 1): lanes = {desktop, nova, thor} with nova and thor held
# must take this branch -- the old check compared every file in lanes/,
# desktop included, against the holds and never could.
qsis "every handheld held, desktop still serving -> waiting on the hold" \
     "q=1 stalled= held=1500-arms-x blind=None" \
     '{'"$ALL3"', "hold":["nova","thor"], "queue":[{"name":"1500-arms-x","age":300}],
       "results":[{"name":"1400-done","mtime":400}]}'
qsis "a dead lane file does not keep the held branch from being taken" \
     "q=1 stalled= held=1500-arms-x blind=None" \
     '{"lanes":{"nova":"dead","thor":"live","desktop":"live"}, "hold":["thor"],
       "queue":[{"name":"1500-arms-x","age":300}],
       "results":[{"name":"1400-done","mtime":400}]}'
qsis "an explicit pin to a held device waits by design, whoever else is idle" \
     "q=1 stalled= held=1600-soak blind=None" \
     '{"lanes":{"thor":"live","desktop":"live"}, "hold":["nova"],
       "queue":[{"name":"1600-soak","age":300,"device":"nova"}],
       "results":[{"name":"1400-done","mtime":400}]}'

# ------------------------------------------------ what the board actually reads
# L4 (audit pass 1): the checks above call queue_stall() directly, so deleting
# its call from main() would leave every one of them green. board.sh runs
# `fleet.py 2>&1 >/dev/null | grep '^FAIL'` -- stderr only, anchored -- so
# that exact pipeline is what is asserted here, against a scratch board that
# carries copies of the modules fleet.py imports.
QB="$T/qs-board"; rm -rf "$QB"; mkdir -p "$QB"
cp "$QSRC/fleet.py" "$QSRC/affinity.py" "$TESTING/board_files.py" "$TESTING/gh_rest.py" "$QB/"
printf '[free]\nnote = "x"\n' > "$QB/territory.toml"
printf '[issue.1]\ntitle = "t"\nstatus = "closed"\n' > "$QB/nv2a_issues.toml"
qs '{'"$ALL3"', "queue":[{"name":"1500-arms-x","age":300}],
     "results":[{"name":"1400-done","mtime":400}]}' >/dev/null
fails=$(env HAKUX_BOARD_REF= DISPATCH_DIR="$T/qs" python3 "$QB/fleet.py" 2>&1 >/dev/null | grep '^FAIL' || true)
check "board.sh's own pipeline sees the stall FAIL on stderr" \
      grep -q '^FAIL: 1 dispatch request(s) passed over by every live claimer -- oldest 1500-arms-x' <<< "$fails"
env HAKUX_BOARD_REF= DISPATCH_DIR="$T/qs" python3 "$QB/fleet.py" >/dev/null 2>&1; qrc=$?
check "...and fleet.py exits non-zero for it" test "$qrc" -ne 0
qs '{'"$ALL3"', "hold":["nova","thor"], "queue":[{"name":"1500-arms-x","age":300}],
     "results":[{"name":"1400-done","mtime":400}]}' >/dev/null
fails=$(env HAKUX_BOARD_REF= DISPATCH_DIR="$T/qs" python3 "$QB/fleet.py" 2>&1 >/dev/null | grep '^FAIL' || true)
out=$(env HAKUX_BOARD_REF= DISPATCH_DIR="$T/qs" python3 "$QB/fleet.py" 2>/dev/null || true)
check "a request waiting on a hold is said on stdout..." \
      grep -q '^queue: 1 request(s) can only run on a held device' <<< "$out"
qheld_quiet() { ! grep -q 'dispatch request(s) passed over' <<< "$fails"; }
check "...and costs no FAIL" qheld_quiet
unset QB fails out qrc

# The live tree must parse and answer, or the checks above prove nothing about
# the file the board actually runs.
check "fleet.py queue_stall is importable from the live tree" \
      python3 -c "import sys;sys.path.insert(0,'$TESTING');import fleet;fleet.queue_stall()"
