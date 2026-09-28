# lane.fanduty507 (#507): a per-request fan duty for soaks

Built the knob #507 D.3 needs: a title soak can hold the fan at a given PWM
duty. lane.sustain507 runs D.3 with it; this lane measured nothing about fps.

## What it does (soak_title.sh THE FAN DUTY, devices.sh device_fan_*)

- `FAN_DUTY=<pwm>` reaches the soak the way `PERF_REGIMEN` does: the shell's
  value, else the running request's top-level `fan_duty` (an integer), else a
  `FAN_DUTY=<n>` entry in the request's `env`. The soak reads the request from
  `running/<id>.req`, found from CAPTURE_LOG; dispatcher.sh is not changed.
- Checked before the cool-down gate: a whole number, at most the node's
  `period` (read from `/sys/class/gpio5_pwm2`). Otherwise the soak is refused
  before anything is set or started: `fan-duty-refused: <why>` in run.log,
  exit 6. The reason: a run at a fan other than the one asked for measures
  the wrong arm and looks like the right one.
- After the cool-down gate and the regimen (so both D.3 arms start from the
  same gate-admitted temperature), before `am start`: `settings put system
  fan_mode 6; sleep 1; echo <duty> > duty`, then a read-back.
- After every hold-loop thermal sample: one adb call that reads the duty and
  then writes it again. The sample reads first, so thermal.jsonl shows whether
  the last write held for the interval, not the write just made. A moved duty
  logs `FAN: duty read [<x>] at <s>s, not <duty>; written again`.
- From release(), so on every exit the EXIT trap sees (end of hold, guest
  exit, adb failure, TERM, INT): `settings put system fan_mode <DEVICE_FAN_REST>`
  and no duty write; the firmware takes the node back (see the probe).
  `FAN: restored=[mode duty period] fan_restored=true|false rewrites=N moved=M`.
  SIGKILL is the one exit it cannot see. soak_title.sh's regimen comment says
  host-tools' device_reality.sh restores REST on an idle handheld every 10
  min; that tool is not in this repository and this lane did not check that
  it writes fan_mode.
- `perf_regimen.json` gains `fan_duty`: `requested`, `period`, `refused`,
  `ran` and `restored` (`fan_mode`, `duty`, `period` as read back),
  `fan_restored`, `rewrites`, `moved`. It is `null` when no duty was asked
  for. `fan_mode` at the top level reads 6 on a fan-duty run.
- Nothing about MAX/REST changed; no device default moved.

## How a lane requests it

Today (once this is folded and the host's update window has restarted the
dispatcher, which serves its own snapshot of soak_title.sh):

    docs/testing/request.sh --title <iso> --seconds 1800 --who lane.<name> \
        --purpose "..." --env FAN_DUTY=50000 [--env PERF_REGIMEN=default]

The env entry also lands in the app's env_vars pref, where an unknown name is
harmless (as PERF_REGIMEN's does). The field path the soak prefers is the
request JSON's top level: `"fan_duty": 50000`. request.sh has no flag for it
yet; it is lane.toolsmith's, so a board request asks for `--fan-duty <n>`
writing that field (board-requests/fanduty507.md).

## The probe (step 2): 50000 holds with no re-write

Nova (ee317437), under `hold.sh take nova lane.fanduty507`, idle, screen off,
battery 34%, 2026-09-28 16:46-16:53 UTC. `probe.sh ee317437 300 15`, full output
in probe-nova.md:

| t | fan_mode | duty | rpm | xo-therm |
|---|---|---|---|---|
| before | 4 | 12000 | 5700 | 41.8 C |
| set +0 s | 6 | 50000 | 12600 | 41.3 C |
| +17 s .. +314 s (19 reads) | 6 | 50000 every read | 13800-14400 | 38.6 -> 32.4 C |
| fan_mode 4, +1 s | 4 | 12000 | 6000 | 32.4 C |
| +44 s | 4 | 12000 | 5100 | 32.7 C |

Answer: under mode 6, 50000 held for 5 min with no re-write; the firmware did
not touch it. Putting fan_mode back to 4 returns the node to SMART's 12000
within a second, so the restore needs no duty write. The re-write stays: it
is one adb call per 30 s that ALSO reads the duty, and the probe was idle and
cool, not a hot device under load where a firmware thermal policy could act.
If D.3 shows `moved` 0 across its runs, it could be dropped.

## Proof

### The fragment passes, and fails with the restore removed

`env SELFTEST_ONLY=99-fan-duty bash docs/testing/jobs/selftest.sh`:

    ok   set: the soak ran to its deadline
    ok   set: the title started at fan_mode 6, duty 50000
    ok   set: adb got MAX (line 6), then `fan_mode 6; sleep 1; echo 50000 > duty` (line 9), then `am start` (line 12)
    ok   rewrite: 3 re-writes of 50000 in a 3 s hold at one per second
    ok   rewrite: the first re-write follows `am start`
    ok   set: perf_regimen.json requested 50000, ran 6/50000 of 50000, fan_mode 6, moved 0, rewrites >= 2
    ok   set: left at fan_mode 4, and run.log says FAN: restored=[4 ...]
    ok   firmware: run.log names the duty read at 25000, and perf_regimen.json counts moved >= 2
    ok   end: adb log: `settings put system fan_mode 4` is the last fan_mode write and follows the last duty write
    ok   end: the device reads fan_mode 4
    ok   end: run.log: FAN: restored=[4 12000 50000] fan_restored=true
    ok   end: perf_regimen.json fan_duty.fan_restored true
    ok   killed: adb log: `settings put system fan_mode 4` is the last fan_mode write and follows the last duty write
    ok   killed: the device reads fan_mode 4
    ok   killed: run.log: FAN: restored=[4 12000 50000] fan_restored=true
    ok   killed: perf_regimen.json fan_duty.fan_restored true
    ok   killed: no duty write after the restore; the firmware's 12000 is on the node
    ok   refused: FAN_DUTY=60000 exits 6 with `fan-duty-refused: fan_duty 60000 is above the node's period 50000; not...`, no am start, no mode or duty write
    ok   refused: FAN_DUTY=fast exits 6 with `fan-duty-refused: fan_duty 'fast' is not a whole number; nothing was s...`, no am start, no mode or duty write
    ok   none: no FAN_DUTY writes no duty and no mode 6; the title started at the regimen's fan 5
    ok   request: {"title":"x","fan_duty":50000,"env":["HAKUX_X=1"]} starts the title at 6/50000
    ok   request: {"title":"x","env":["HAKUX_X=1","FAN_DUTY=30000"]} starts the title at 6/30000
    ok   path: devices.sh writes /sys/class/gpio5_pwm2, thermal_state.py samples /sys/class/gpio5_pwm2
    ok   mutant 'no fan_leave in release()' is caught by end and killed (8 red)
    selftest: 24 passed, 0 failed

With `    fan_leave` deleted from release() in the real soak_title.sh (restored
after), the same fragment:

    FAIL set: left at fan_mode [4]; FAN: duty=50000 of 50000 running=[6 50000 50000]
    FAIL end: red adb log: last duty write line 14, last fan_mode 4 line none, last fan_mode line 7
    FAIL end: red the device reads fan_mode [6]
    FAIL end: red run.log has no FAN: restored=[4 ...] true line: FAN: duty=50000 of 50000 running=[6 50000 50000]
    FAIL end: red perf_regimen.json fan_duty.fan_restored None
    FAIL killed: red adb log: last duty write line 13, last fan_mode 4 line none, last fan_mode line 7
    FAIL killed: red the device reads fan_mode [6]
    FAIL killed: red run.log has no FAN: restored=[4 ...] true line: FAN: duty=50000 of 50000 running=[6 50000 50000]
    FAIL killed: red perf_regimen.json fan_duty.fan_restored None
    FAIL killed: duty write line 13 after restore line ; node reads 50000
    FAIL mutant: the fan_leave/perf_leave anchor is gone from release() -- update the mutant
    selftest: 13 passed, 11 failed

The `end` and `killed` legs run at PERF_REGIMEN=off on purpose: at MAX the
regimen's own restore also writes fan_mode 4, and would pass a release() that
lost the fan restore. The neighbouring soak fragments (84-perf-regimen,
89-title-verdict, 99-default-regimen, 99-display-covered, 99-thermal-pause,
99-iso-roots, 99-usb-dialog) pass with this change: 191 passed, 0 failed.

### A real 3-minute soak at fan_duty 50000

Nova, same hold, right after the probe: this worktree's soak_title.sh run
by hand (proof-run.sh; the dispatcher's snapshot does not have the change
yet), Blinx, 180 s, PERF_REGIMEN=rest (battery was 34%; the fan is what is
tested), FAN_DUTY=50000. Files in proof-nova/ (run.log as run-log.md).

thermal.jsonl, per sample:

| label | device time | duty | rpm | xo-therm |
|---|---|---|---|---|
| cool | 09:53:18 | 12000 | 4800 | 32.9 C |
| start | 09:53:22 | 50000 | 12900 | 33.7 C |
| hold | 09:53:56 | 50000 | 14400 | 37.0 C |
| hold | 09:54:30 | 50000 | 14100 | 37.9 C |
| hold | 09:55:05 | 50000 | 14400 | 38.6 C |
| hold | 09:55:39 | 50000 | 14100 | 40.7 C |
| hold | 09:56:14 | 50000 | 14100 | 40.6 C |
| end | 09:56:27 | 50000 | 14400 | 40.5 C |

(`cool` is the gate's read before the fan is set; the summary line's
`fan duty 12000-50000` counts it.) run.log:

    FAN: duty=50000 of 50000 running=[6 50000 50000]
    THERMAL: no thermal-pause device above 0; 8 samples, 0 unread, hottest zone 70.1 C; battery +5.03 W (+ is discharging), usb in 2.11 W, net 7.14 W; fan duty 12000-50000 of 50000
    held 4D530013-Blinx_The_Time_Sweeper.xiso.iso for 182s
    FAN: restored=[4 12294 50000] fan_restored=true rewrites=5 moved=0
    PERF: restored=[0 4] perf_restored=true

The device read back 5 s after the soak:

    after +5s: fan_mode=4 performance_mode=0 duty=12000 battery=33

perf_regimen.json `fan_duty`: requested 50000, period 50000, ran 6/50000,
restored 4/12294 (the firmware already ramping to its curve), fan_restored
true, rewrites 5, moved 0.

## For the next lane

- Do not write the duty before fan_mode 6: the mode change is where the
  firmware puts its own value; devices.sh waits a second between the two.
- Do not write a duty on the way out; fan_mode 4 alone returns the node to
  the firmware within a second (probe).
- `grep -qF` with a two-line anchor matches either line; 84-perf-regimen's
  multi-line mutant anchors have that blind spot (the fragment here checks
  its anchor in python).
- The Nova probe was idle and cool. Whether a hot device under a game moves
  the duty is what `moved` in D.3's perf_regimen.json will say.
