# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# fleet.py: work nobody claims must wake the board, and nothing else may.

echo "== fleet: a dispatch request the fleet passed over is a FAIL"
# WHY. status.sh renders "N arms on a device, M queued" every tick, and its
# own header says it exists because "a jammed fleet and a running fleet
# rendered identically". It fixed the RENDERING and nothing escalated the
# numbers, so on 2026-09-20 four arms sat unclaimed -- the oldest eighteen
# hours -- with two healthy handhelds, and the status page said so the whole
# time while nobody was woken.
#
# THE CONDITION IS "PASSED OVER", NOT "OLD", and these checks pin that
# distinction because getting it wrong is expensive in both directions.
# Every FAIL line in fleet.py is a board wake-up: board.sh greps stdout and
# stderr for '^FAIL' and starts a model session on any hit, so a FAIL that
# fires on a healthy fleet spends a window every twenty minutes for nothing.
# The three quiet cases below are therefore as load-bearing as the loud one.
qs() {   # <req_age_min> <result_age_min|none> <held:0|1> <name> -> "stall=B held=B"
    python3 - "$T/qs" "$1" "$2" "$3" "$4" "$TESTING" <<'PY'
import json, os, shutil, sys, time
root, req_age, res_age, held, name, testing = sys.argv[1:7]
shutil.rmtree(root, ignore_errors=True)
for d in ("queue", "results", "lanes", "hold"):
    os.makedirs(os.path.join(root, d), exist_ok=True)
p = os.path.join(root, "queue", name)
json.dump({"id": name[:-4]}, open(p, "w"))
t = time.time() - float(req_age) * 60
os.utime(p, (t, t))
if res_age != "none":
    r = os.path.join(root, "results", "1-done")
    os.makedirs(r, exist_ok=True)
    rt = time.time() - float(res_age) * 60
    os.utime(r, (rt, rt))
for lane in ("thor", "nova"):
    open(os.path.join(root, "lanes", lane), "w").write("1\n")
    if held == "1":
        open(os.path.join(root, "hold", lane), "w").close()
os.environ["DISPATCH_DIR"] = root
sys.path.insert(0, testing)
import fleet
stalled, all_held = fleet.queue_stall()
print("stall=%s held=%s" % (bool(stalled), all_held))
PY
}

check "passed over: waited long AND the fleet completed work after it -> FAIL" \
      test "$(qs 300 60 0 1-arms-x.req)" = "stall=True held=False"
# The three that must stay SILENT. Each one is a board window per tick if it
# regresses, which is why they are checks and not comments.
check "backlog: waited long but nothing completed since -> quiet" \
      test "$(qs 300 400 0 1-arms-x.req)" = "stall=False held=False"
check "normal: recently queued on a working fleet -> quiet" \
      test "$(qs 5 1 0 1-arms-x.req)" = "stall=False held=False"
check "sweep: z-* is idle priority and waits by design -> quiet" \
      test "$(qs 999 1 0 z-sweep-Blend.req)" = "stall=False held=False"
# Out of service on purpose is reported, but it is not a wake-up.
check "held: every serving lane held -> flagged held, not a fault" \
      test "$(qs 300 60 1 1-arms-x.req)" = "stall=True held=True"

# The live tree must parse and answer, or the checks above prove nothing about
# the file the board actually runs.
check "fleet.py queue_stall is importable from the live tree" \
      python3 -c "import sys;sys.path.insert(0,'$TESTING');import fleet;fleet.queue_stall()"
