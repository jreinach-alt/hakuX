# Sourced by ../selftest.sh: $T, $TESTING, ok/bad/check. No shebang, no exit.
#
# fleet.py: a request pinned to a handheld that is off USB is not a stall
# (#598). On 2026-09-28 17:40 PDT the owner unplugged both handhelds to
# charge, the Thor's worker exited with its device, and fleet.py FAILed the
# 17 Thor-pinned requests as "Nothing will claim it". The board read that as
# a dead worker and opened an issue. The device was on a charger.
#
# THE LEGS, one dispatch dir (a request pinned to thor, queued 300 min ago;
# lanes/thor holding a dead pid, nova live), three stub adbs:
#   (a) empty    adb lists nothing: the `queue: ... not on adb` line on
#                stdout, and no stall FAIL. Fails if queue_stall() does not
#                ask adb (the mutant: step 1 removed).
#   (b) attached adb lists the Thor as `device`: the worker is dead with its
#                handheld on USB, which IS a stall. FAIL, and no absent line.
#   (c) broken   adb exits non-zero: cannot tell, so FAIL as before, and the
#                FAIL says adb could not be read. Fails if "cannot tell" is
#                read as "absent".
#   (d) offline  adb lists the Thor as `offline`: absent, and the line says
#                what adb called it.
# Asserted on board.sh's own pipeline (`fleet.py 2>&1 >/dev/null | grep
# '^FAIL'`), against a scratch board, as 98-fleet-queue-stall.sh does.
#
# SELFTEST_FLEET_SRC points the fleet.py/affinity.py copies at another
# directory (a mutant), so the legs can be seen to fail.

echo "== fleet: a request pinned to a handheld that is not on adb is absent, not stalled"
FA="$T/fleet-absent"; rm -rf "$FA"; mkdir -p "$FA/board" "$FA/bin"
FASRC="${SELFTEST_FLEET_SRC:-$TESTING}"
cp "$FASRC/fleet.py" "$FASRC/affinity.py" "$TESTING/board_files.py" \
   "$TESTING/gh_rest.py" "$TESTING/devices.sh" "$FA/board/"
printf '[free]\nnote = "x"\n' > "$FA/board/territory.toml"
printf '[issue.1]\ntitle = "t"\nstatus = "closed"\n' > "$FA/board/nv2a_issues.toml"
python3 - "$FA/dispatch" <<'PY'
import os, subprocess, sys, time
root = sys.argv[1]
for d in ("queue", "running", "results", "lanes", "hold"):
    os.makedirs(os.path.join(root, d))
now = time.time()
def touch(p, minutes):
    t = now - minutes * 60
    os.utime(p, (t, t))
p = os.path.join(root, "queue", "1700-soak-thor.req")
open(p, "w").write('{"device": "thor"}\n'); touch(p, 300)
dead = subprocess.Popen(["true"]); dead.wait()
# nova is "live" as long as some pid survives the check: this shell's parent.
open(os.path.join(root, "lanes", "thor"), "w").write("%d\n" % dead.pid)
open(os.path.join(root, "lanes", "nova"), "w").write("%d\n" % os.getppid())
for d in ("lanes/thor", "lanes/nova", "lanes", "hold"):
    touch(os.path.join(root, d), 600)
PY

fa_run() {   # <adb stub body>: sets fa_fail (the ^FAIL lines) and fa_out (stdout)
    printf '#!/usr/bin/env bash\n%s\n' "$1" > "$FA/bin/adb"; chmod +x "$FA/bin/adb"
    fa_fail=$(env PATH="$FA/bin:$PATH" HAKUX_BOARD_REF= DISPATCH_DIR="$FA/dispatch" \
              FLEET_ADB_TIMEOUT_S=10 python3 "$FA/board/fleet.py" 2>&1 >/dev/null | grep '^FAIL' || true)
    fa_out=$(env PATH="$FA/bin:$PATH" HAKUX_BOARD_REF= DISPATCH_DIR="$FA/dispatch" \
             FLEET_ADB_TIMEOUT_S=10 python3 "$FA/board/fleet.py" 2>/dev/null || true)
}
fa_stall()    { grep -q '^FAIL: 1 dispatch request(s) passed over by every live claimer -- oldest 1700-soak-thor' <<< "$fa_fail"; }
fa_no_stall() { ! grep -q 'dispatch request(s) passed over' <<< "$fa_fail"; }
fa_absent()   { grep -q '^queue: 1 request(s) can only run on thor, which is not on adb -- oldest 1700-soak-thor, queued .* ago. Needs hands or a re-pin, not a claimer fix.' <<< "$fa_out"; }
fa_no_absent() { ! grep -q 'which is not on adb' <<< "$fa_out"; }

fa_run "printf 'List of devices attached\n\n'"
check "(a) adb lists nothing: the absent line on stdout" fa_absent
check "(a) ...and no stall FAIL" fa_no_stall

fa_run "printf 'List of devices attached\nbdc158a5\tdevice\nee317437\tdevice\n\n'"
check "(b) the Thor on adb as device, its worker dead: the stall FAIL" fa_stall
check "(b) ...which says the Thor is on adb" grep -q 'thor is on adb as `device`' <<< "$fa_fail"
check "(b) ...and no absent line" fa_no_absent

fa_run "echo 'adb: cannot connect to daemon' >&2; exit 1"
check "(c) adb unreadable: the stall FAIL as before" fa_stall
check "(c) ...which says adb could not be read" grep -q 'adb could not be read to tell whether thor is on USB' <<< "$fa_fail"
check "(c) ...and no absent line" fa_no_absent

fa_run "printf 'List of devices attached\nbdc158a5\toffline\n\n'"
check "(d) the Thor on adb as offline: absent, naming adb's word" \
      grep -q '^queue: 1 request(s) can only run on thor, which is not on adb as a device (adb says `offline`)' <<< "$fa_out"
check "(d) ...and no stall FAIL" fa_no_stall
unset FA FASRC fa_fail fa_out
