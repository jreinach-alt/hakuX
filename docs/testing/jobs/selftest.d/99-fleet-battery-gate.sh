# Sourced by ../selftest.sh: $T, $TESTING, ok/bad/check. No shebang, no exit.
#
# fleet.py: a queue a live worker refuses on its battery level is not a stall
# (#507's per-request admission). On 2026-09-29 06:53Z the nova sat at 36 %,
# dispatcher.log said `BATTERY: skip <id>: level 36 < need 39.7 (...)` for
# every queued request, and fleet.py FAILed all 42 as "passed over by every
# live claimer ... Nothing will claim it". The nova would have claimed each
# one the moment its charge covered the run.
#
# THE LEGS, one dispatch dir each: request 0-long queued 300 min ago, the nova
# live (lanes/nova holds this shell's pid), running/ empty, the nova's last
# level read in .battery_level.nova. What differs is dispatcher.log:
#   (a) gated     `skip 0-long on nova: level 36 < need 39.7`, 200 min ago,
#                 level still 36: battery_gated, not stalled; fleet.py prints
#                 the queue line on stdout and has no stall FAIL.
#   (b) no line   the same fixture with an empty log: stalled, and the FAIL.
#                 The check is narrowed, not disabled.
#   (c) thor      the same skip line naming thor: the nova's silence is not
#                 answered by another device's refusal. Stalled.
#   (d) unlabeled the pre-#606 wording (`skip 0-long: level ...`): cannot be
#                 attributed, so it is not evidence. Stalled.
#   (e) older     the skip line predates the request (a re-queue): stalled.
#   (f) cleared   the line holds, but the nova last read 45 >= need 39.7: it
#                 should have admitted, so its silence is back to a stall.
#   (g) admitted  a skip, then `admit 0-long on nova`: the newest line wins.
#                 Stalled.
#   (h) hold      `hold for head 0-big on nova ...: not backfilling 0-long`
#                 while 0-big is still queued: battery_gated.
#
# SELFTEST_FLEET_SRC points fleet.py/affinity.py at another directory (a
# mutant, or master's), so the legs can be seen to fail.

echo "== fleet: a request a live worker refuses on battery is battery-gated, not stalled"
FB="$T/fleet-battgate"; rm -rf "$FB"; mkdir -p "$FB/board"
FBSRC="${SELFTEST_FLEET_SRC:-$TESTING}"
cp "$FBSRC/fleet.py" "$FBSRC/affinity.py" "$TESTING/board_files.py" \
   "$TESTING/gh_rest.py" "$TESTING/devices.sh" "$FB/board/"
printf '[free]\nnote = "x"\n' > "$FB/board/territory.toml"
printf '[issue.1]\ntitle = "t"\nstatus = "closed"\n' > "$FB/board/nv2a_issues.toml"

# fb_build <log-lines-json> <level>: a fresh dispatch dir. Each log line is
# [minutes-ago, text]; the stamp is dispatcher.sh's `date '+%m-%d %H:%M:%S'`.
fb_build() {
    python3 - "$FB/dispatch" "$1" "$2" <<'PY'
import json, os, shutil, sys, time
root, lines, level = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3]
shutil.rmtree(root, ignore_errors=True)
for d in ("queue", "running", "results", "lanes", "hold", "logs"):
    os.makedirs(os.path.join(root, d))
now = time.time()
def touch(p, minutes):
    t = now - minutes * 60
    os.utime(p, (t, t))
for name, age in (("0-long", 300), ("0-big", 400)):
    p = os.path.join(root, "queue", name + ".req")
    open(p, "w").write('{"title": "Fixture.iso", "seconds": 2100}\n'); touch(p, age)
# Live as long as the shell that sourced this fragment is.
open(os.path.join(root, "lanes", "nova"), "w").write("%d\n" % os.getppid())
for d in ("lanes/nova", "lanes", "hold"):
    touch(os.path.join(root, d), 600)
with open(os.path.join(root, "logs", "dispatcher.log"), "w") as fh:
    for ago, text in lines:
        fh.write("%s %s\n" % (time.strftime("%m-%d %H:%M:%S",
                                            time.localtime(now - ago * 60)), text))
open(os.path.join(root, ".battery_level.nova"), "w").write("%d %s\n" % (now - 30, level))
PY
}
# fb_qs: "stalled=<ids> gated=<ids>" from queue_stall() over that dir
fb_qs() {
    DISPATCH_DIR="$FB/dispatch" python3 - "$FB/board" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import fleet
r = fleet.queue_stall()
stalled, gated = r[0], (r[3] if len(r) == 5 else [])
print("stalled=%s gated=%s" % (",".join(x[0] for x in stalled),
                               ",".join(x[0] for x in gated)))
PY
}
fb_is() {   # <label> <expected>: one check, with the actual on a miss
    local got; got=$(fb_qs 2>&1)
    if [ "$got" = "$2" ]; then ok "$1"; else bad "$1 -- got: $got"; fi
}
fb_main() {   # sets fb_rc, fb_fail (its ^FAIL lines) and fb_out (stdout)
    fb_out=$(env HAKUX_BOARD_REF= DISPATCH_DIR="$FB/dispatch" \
             python3 "$FB/board/fleet.py" 2>"$FB/err"); fb_rc=$?
    fb_fail=$(grep '^FAIL' "$FB/err" || true)
}

SKIP='BATTERY: skip 0-long on nova: level 36 < need 39.7 (floor 30 + margin 5 + rate 10.5 %/h fallback n=0, 1 x (2100s + overhead 1607s learned n=10)); head, refused for 0s'

# 0-big is older than 0-long and has no battery line in (a)-(g): it is the
# control that must stay stalled in every leg, and (a) shows it does not drag
# 0-long along or get dragged.
fb_build "[[200, \"$SKIP\"]]" 36
fb_is "(a) refused on battery by the only live worker: battery_gated" "stalled=0-big gated=0-long"
fb_build "[[200, \"$SKIP\"], [200, \"BATTERY: skip 0-big on nova: level 36 < need 60.0 (x)\"]]" 36
fb_main
check "(a) the whole queue gated: fleet.py exits 0" test "$fb_rc" = 0
check "(a) ...has no stall FAIL" test -z "$fb_fail"
check "(a) ...and says so on stdout, with the line's own numbers" \
      grep -q '^queue: 2 request(s) a live claimer refused on its battery level, and no live claimer will take sooner -- oldest 0-big, queued .* ago: nova: level 36 < need 60.0. Deliberate, not a stall' <<< "$fb_out"

fb_build "[]" 36
fb_is "(b) no battery line: still stalled" "stalled=0-big,0-long gated="
fb_main
check "(b) ...and the stall FAIL, exit 1" test "$fb_rc" = 1
check "(b) ...naming both" grep -q '^FAIL: 2 dispatch request(s) passed over by every live claimer -- oldest 0-big' <<< "$fb_fail"
check "(b) ...and no battery line on stdout" test -z "$(grep 'battery' <<< "$fb_out")"

fb_build "[[200, \"${SKIP/on nova/on thor}\"]]" 36
fb_is "(c) the refusal names another device: stalled" "stalled=0-big,0-long gated="
fb_build "[[200, \"${SKIP/ on nova/}\"]]" 36
fb_is "(d) an unlabeled refusal: stalled" "stalled=0-big,0-long gated="
fb_build "[[310, \"$SKIP\"]]" 36
fb_is "(e) a refusal older than the request: stalled" "stalled=0-big,0-long gated="
fb_build "[[200, \"$SKIP\"]]" 45
fb_is "(f) the level has since cleared the need: stalled" "stalled=0-big,0-long gated="
fb_build "[[200, \"$SKIP\"], [150, \"BATTERY: admit 0-long on nova: level 40 >= need 39.7 (x)\"]]" 36
fb_is "(g) admitted after the refusal: stalled" "stalled=0-big,0-long gated="
fb_build "[[200, \"BATTERY: hold for head 0-big on nova (refused for 1900s >= 1800s): not backfilling 0-long, level 50 >= need 39.7\"]]" 50
fb_is "(h) held for a head still queued: battery_gated" "stalled=0-big gated=0-long"
unset FB FBSRC SKIP fb_rc fb_fail fb_out
