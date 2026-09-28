# lane.fanduty507 (#507): a per-request fan MODE for soaks

Built the knob #507 D.3 needs: a title soak can run at any fan setting a
player can select in the handheld's own menu, and at nothing else.
lane.sustain507 runs D.3 with it; this lane measured no fps.

## Attempt 4 (2026-09-28): why attempt 3 did not finish

Attempt 3 finished its work (the screen-wake fix, section 5) and ended at
19:11 UTC with the PR still a draft, waiting on CI for e63056ac50 and on the
Nova's battery hold. It held the PR for the Nova proof when it did not need
to. Addendum 3 (lane.local, 19:20 UTC) settled that: D.3 is Thor-only, so the
Thor proof is enough to mark #571 ready, and the Nova proof follows as a
queued request. Attempt 4 queued the Nova soaks (section 4, Nova) and marks
the PR ready on green CI. origin/master had not moved since attempt 3's merge
(6b7eb8b6a5), so there was nothing to merge.

## Attempt 3 (2026-09-28): why attempt 2 did not finish

Attempt 2 built and proved the fan-mode knob (below), pushed it, and ended
waiting on two things outside its session: CI on 105e8cbaf0, and the
Nova's battery hold. It never started Addendum 2 (the screen wake across
the cool-down gate). Nothing it pushed was lost. Attempt 3 added that fix as
its own commit (section 5), merged origin/master, and waits on the same two
things.

## Attempt 2 (2026-09-28): why attempt 1 did not land

Attempt 1 built `FAN_DUTY=<pwm>`, a raw write to the fan's PWM duty node
(PR #563, branch `lane/fanduty507`). It was finished, proven (Nova probe, a
3-minute soak at 50000, selftest pass and red-with-restore-removed) and
audited clean. The owner then closed it without merging (2026-09-28): "On the
fan, only use available modes. I don't want to test on a fan speed that's
user inaccessible." A raw duty is not a setting any player can pick. The
#563 notes stay on that branch. Two facts carry forward:

- Putting `fan_mode` back returns the duty node to the firmware within a
  second. Nothing needs to write the node on the way out (Nova probe,
  2026-09-28).
- `grep -qF` with a two-line mutant anchor matches either line; check a
  mutant's anchor in python.

This attempt (PR #571, `lane/fanduty507-mode`) replaces that knob with
`FAN_MODE=<name>`, and writes nothing to the duty node.

## 1. What a player can select (read from the APKs, checked on the Thor)

Sources: each handheld's SystemUI.apk and its OEM settings app
(`com.odin.settings` 2.0(20260205), sha256 2bbdf769...; `com.rp.settings`
2.0(20260720), 07c3627f...), pulled by lane.perfregimen and lane.local, read
with `dexdump -d` and the resource tables. No device was needed for this
part. Scratch tools: `.scratch/where.py`, `m.py` (not committed).

**The only fan-mode selector is SystemUI's Quick Settings fan tile**
(`qs/tiles/FanTile`, `qs/tiles/dialog/FanDialogView`, layout
`qs_fan_dialog_content_layout`), and it is the same on both handhelds. Each
row's `android:tag` is the `fan_mode` value it writes (`FanTile.onItemSelect`):

| row | fan_mode | shown at performance_mode |
|---|---|---|
| (tile switch) Off | 0 | NORMAL (0) only |
| Quiet | 1 | NORMAL (0), STANDARD (1); hidden at HIGH (2) |
| Smart | 4 | all |
| Sport | 5 | all |
| Customize | 6, plus a slider 0-100 written to `settings system fan_speed` | HIGH (2) only |

- Row visibility: `FanTile$$ExternalSyntheticLambda0.run` (Thor 0x145-0x17a,
  Nova 0x7f-0xb6). BALANCE (2) and PERFORMANCE (3) exist as strings and enum
  values, but no row writes them. The Thor's "Balanced" string is the audio
  EQ preset (`eq_balance`), not a fan option.
- Customize: `QSDetailSelectItem$2.onProgressChanged` calls
  `FanTile.onQSFanSpeedChange`, which sets `fan_mode` 6 if needed and then
  writes the slider position to `fan_speed`. The layout sets no max, so the
  slider is Android's default 0-100.
- The settings apps have no mode selector. `array/array_fan_speed` (Off,
  Quiet, Sport, High speed, Smart) is referenced by no code and no layout.
  Their one fan screen is the Smart curve editor
  (`FanTempControlCurveConfigActivity`), reached from the Smart row's edit
  link: always on the Thor, and on the Nova only when a framework bool
  (0x01110153, not resolved) is set.
- Changing `performance_mode` makes the tile rewrite `fan_mode`
  (`FanTile$1.onChange`). Thor: NORMAL -> 1, STANDARD -> 4, HIGH -> 4. Nova:
  NORMAL -> 0; STANDARD -> 1 unless the mode is 4; HIGH -> 5 from 0 or 1.
  Whether this fires with the Quick Settings shade closed was not tested.
  The soak reads back again after a settle (below).
- The OEM app sets `fan_mode` 4 when a charger's plug type changes, and puts
  the old mode back on unplug (`trigger/n$a.onReceive`). The soak checks
  every hold sample for this (below).

**What each mode drives.** The OEM settings app runs the fan: it writes
`/sys/class/gpio5_pwm2/duty` (period 50000) and re-evaluates Smart every 4 s
(`s1/b$c$a.run`). Decoded values, each checked on the idle Thor
(`modeprobe.sh`, `probe-thor.md`, 2026-09-28 18:41 UTC, battery 78%):

| option | Thor, decoded | Thor, measured idle | Nova, decoded |
|---|---|---|---|
| off | 0 | 0 | 0 |
| quiet | 12000 | 12000 | 12000 |
| sport | 25000 | 25000 | 25000 (the #563 probe read 25000) |
| customize:0 | 25000 | 25000 | 25000 |
| customize:50 | 25000 + 250 x 50 = 37500 | 37500 | 25000 + 100 x 50 = 30000 |
| customize:100 | 50000 | **50000** | 35000 |
| smart | the curve, below | 23000 at xo 65 C | fixed, below |

`fan_speed` outside 0-100 is used as a raw duty. The setting's default is
25000, which is why lane.sustain507 saw CUSTOM hold a fixed 25000 (D.1).
The Nova's Customize tops out at 35000; the Thor's reaches full fan.

**Smart.**
- Thor: the user's curve. Duty = 50000 x curve% at the CPU temperature
  (`fan_thermal_management_area`, default CPU).
- Nova: never the curve. The curve path is gated on "Retroid Pocket 6".
  Instead a fixed rule: 12000 below 48 C, (1.4 T - 19) x 250 from 48 to
  85 C, 25000 at 85 C and above.
- The Thor's Smart under real titles, from every soak's thermal.jsonl since
  #554 (`smart_duty.py` over `$DISPATCH_DIR/results`, 2026-09-28; the soaks
  whose perf_regimen.json reads fan_mode 4):

| xo-therm | samples | soaks | duty min / median / max |
|---|---|---|---|
| 50-55 C | 3 | 3 | 27000 / 28000 / 28000 |
| 55-60 C | 4 | 3 | 28500 / 30500 / 30500 |
| 60-65 C | 9 | 5 | 31500 / 33500 / 35500 |
| 65-70 C | 20 | 6 | 32500 / 35500 / 37500 |
| 70-75 C | 36 | 6 | 36000 / 38000 / 39500 |
| 75-80 C | 3 | 3 | 38500 / 39000 / 39000 |

  No Nova soak has run at fan_mode 4 since #554 (its MAX fan is 5), so there
  are no Nova rows.

**The answer D.3 needed first: near the trip the Thor's Sport (fixed 25000)
is well BELOW Smart (median 38000 at xo 70-75 C).** Sport would cool less
than the default. The one user option above Smart is Customize at 100
(50000), and the menu shows it only at HIGH, which is the MAX regimen's
performance mode.

**The curve** is stored in the settings app's own SharedPreferences (file
`config`, key `fan_temp_control_curve_point_key`), as Gson JSON. The shape
is `[{"a": <temp C>, "b": <speed %>}, ...]`, 7 points.
- Defaults: 0->20, 25->20, 45->20, 65->45, 85->70, 105->100, MAX_INT->100.
- The editor drags points 1-5 vertically only. Temperatures are fixed, and
  speed is clamped to 20-100%.
- Below 25 C the curve returns 0.
- It is **not** in a `settings` table. `adb shell settings` cannot write it,
  and the app's private storage needs root, so there is **no `FAN_CURVE`**.
  A Smart run on the Thor uses whatever curve is saved on the device, and no
  soak can read which one. Every sample's duty is on record instead.

## 2. The knob (soak_title.sh THE FAN MODE, devices.sh fan options)

- `FAN_MODE=<name>`: `off`, `quiet`, `smart`, `sport`, or `customize:<0-100>`,
  in any case. devices.sh `DEVICE_FAN_OPTIONS` holds the table above, per
  device (`name=mode[:lo-hi]@<performance modes>`).
- **Refused unless the menu shows it at the performance mode the title runs
  at:** the regimen's (max -> 2, rest/default -> 0), or the device's own
  under `PERF_REGIMEN=off`. So at MAX only `smart`, `sport` and
  `customize:<n>` run. A refusal writes `fan-mode-refused: <why> (shown: ...)`
  in run.log and exits 6 before the cool-down, with nothing set or started.
- Set after the cool-down gate and the regimen, before `am start`, in the
  tile's order: `settings put system fan_mode <m>[; settings put system
  fan_speed <n>]`. It is read back after `FAN_SETTLE_S` (2 s) and written
  once more if the tile moved it (`FAN: read [...] ... written again`).
- **No writes to the duty node.** thermal_state.py now also reads
  `fan_mode` at every sample (`fan.mode`, beside #554's duty), and the
  `THERMAL:` summary ends `... of 50000 at fan_mode 4/6`.
- After each hold sample, the soak compares that sample's `fan.mode` with
  the one asked for. A difference is named (`FAN: fan_mode read [4] at 90s,
  not 6`) and counted in `moved`, not written back: the run is then not the
  arm asked for, and the record says so.
- Restored from release(), so on every exit the EXIT trap sees (end of
  hold, guest exit, adb failure, TERM, INT). The prior `fan_mode` and, when
  the slider was used, the prior `fan_speed` go back; a never-written
  `fan_speed` is deleted again. Then the regimen's own restore, if it set
  anything, leaves fan_mode at REST as before. SIGKILL is the one exit it
  cannot see.
- `perf_regimen.json` gains `fan_request` (null when no fan mode was asked):
  `requested`, `want` {fan_mode, fan_speed}, `perf_mode`, `offered`,
  `refused`, `prior`, `ran`, `restored`, `fan_restored`, `moved`. The
  top-level `fan_mode` is the mode the title ran at.
- No MAX/REST default moved.

## 3. How a lane requests it

Once this is folded and the host's update window has restarted the
dispatcher (it serves its own snapshot of soak_title.sh):

    docs/testing/request.sh --title <iso> --seconds 1800 --who lane.<name> \
        --purpose "..." --env FAN_MODE=customize:100            # MAX regimen: HIGH
    ... --env PERF_REGIMEN=default --env FAN_MODE=sport          # NORMAL

The request JSON's top-level `"fan_mode": "sport"` is read first. request.sh
has no flag for it, and `--env` is enough, so no board request was filed.

## 4. Proof

### The fragment passes, and fails with the restore removed

`env SELFTEST_ONLY=99-fan-mode bash docs/testing/jobs/selftest.sh`: 33
passed, 0 failed (61 s). The legs, each with the world it fails in, are in
the fragment's header. The run:

    ok   set: FAN_MODE=customize:100 started the title at fan_mode 6, fan_speed 100
    ok   set: adb got MAX (line 6), then `fan_mode 6; fan_speed 100` (line 9), then `am start` (line 14)
    ok   set: perf_regimen.json requested customize:100 -> 6/100 at performance_mode 2 (shown: smart, sport, customize), ran 6/100, prior 4/null
    ok   sampled: every thermal.jsonl sample reads fan.mode 6 [start:6 hold:6 hold:6 hold:6 end:6]
    ok   sampled: the THERMAL summary names fan_mode 6
    ok   nullspeed: the slider never moved before the soak is deleted again; the device reads 4/null
    ok   rest: FAN_MODE=quiet at REST starts at fan_mode 1, writes no fan_speed; shown at 0: off, quiet, smart, sport
    ok   settle: a tile that moves fan_mode after the write is named, written again, and the title starts at 6/100
    ok   moved: a hold sample at fan_mode 4 is named in run.log and counted moved 2
    ok   end: adb log: `settings put system fan_mode 3; settings put system fan_speed 7` is the last fan write, after `am start`
    ok   end: the device reads the prior 3/7
    ok   end: run.log: FAN: restored=[3 7] to=[3 7] fan_restored=true
    ok   end: perf_regimen.json fan_request restored 3/7 of prior 3/7
    ok   killed: (the same four, after a TERM)
    ok   refused: max, FAN_MODE=turbo exits 6: `fan_mode 'turbo' is not a fan setting this device offers (shown at performance_mode 2: smart, sport, c...`
    ok   refused: max, FAN_MODE=6 ...; max quiet, max off (not shown at 2); rest customize:50 (not shown at 0); off at STANDARD, off (not shown at 1); customize:101, customize, customize:x, smart:5 (not a position)
    ok   none: no FAN_MODE writes no fan setting but the regimen's; the title started at MAX's fan 5
    ok   request: {"title":"x","fan_mode":"CUSTOMIZE:100",...} and {..."env":[...,"FAN_MODE=customize:100"]} start the title at 6/100
    ok   noduty: no soak in this fragment wrote to a /sys node
    ok   mutant 'no fan_leave in release()' is caught by end and killed (8 red)

With `    fan_leave` deleted from release() in the real soak_title.sh (restored
after):

    FAIL nullspeed: the device reads [4 100];
    FAIL end: red adb log: last restore line none, last fan write line 8
    FAIL end: red the device reads [6 100]
    FAIL end: red run.log has no FAN: restored=[3 7] true line: FAN: mode=customize:100 want=[6 100] at performance_mode 2 running=[6 100] prior=[3 7]
    FAIL end: red perf_regimen.json fan_request {... 'restored': None, 'fan_restored': None, 'moved': 0}
    FAIL killed: red adb log: last restore line none, last fan write line 8
    FAIL killed: red the device reads [6 100]
    FAIL killed: red run.log has no FAN: restored=[3 7] true line: ...
    FAIL killed: red perf_regimen.json fan_request {... 'restored': None, 'fan_restored': None, 'moved': 0}
    FAIL mutant: the fan_leave/perf_leave anchor is gone from release() -- update the mutant
    selftest: 23 passed, 10 failed

The `end` and `killed` legs run at `PERF_REGIMEN=off` from a prior of 3/7,
on purpose. The regimen's own restore also writes fan_mode, and REST (4) is
not 3, so only the fan restore can pass them. The neighbouring soak
fragments (84-perf-regimen, 89-title-verdict, 99-default-regimen,
99-display-covered, 99-thermal-pause, 99-iso-roots, 99-usb-dialog) pass with
this change: 200 passed, 0 failed with 99-fan-mode.

### Thor: a real 3-minute soak at customize:100 under MAX

Under `hold.sh take thor lane.fanduty507` (18:34-18:53 UTC, after the
running Forza request ended): this worktree's soak_title.sh run by hand
(`proof-run.sh`), Blinx, 180 s, PERF_REGIMEN=max, FAN_MODE=customize:100.
Files in `proof-thor/` (run.log as run-log.md).

| label | device time | fan_mode | duty | xo-therm |
|---|---|---|---|---|
| cool | 11:48:57 | 4 | 13500 | 47.7 C |
| start | 11:49:06 | 6 | 50000 | 47.8 C |
| hold | 11:49:43 | 6 | 50000 | 53.8 C |
| hold | 11:50:15 | 6 | 50000 | 57.6 C |
| hold | 11:50:48 | 6 | 50000 | 60.2 C |
| hold | 11:51:21 | 6 | 50000 | 62.4 C |
| hold | 11:51:54 | 6 | 50000 | 64.7 C |
| end | 11:52:12 | 6 | 50000 | 65.5 C |

(`cool` is the gate's read, before anything is set.) run.log:

    PERF: regimen=max before=[0 4] running=[2 4]
    FAN: mode=customize:100 want=[6 100] at performance_mode 2 running=[6 100] prior=[4 null]
    THERMAL: no thermal-pause device above 0; 8 samples, 0 unread, hottest zone 95.0 C; ...; fan duty 13500-50000 of 50000 at fan_mode 4/6
    FAN: restored=[4 null] to=[4 null] fan_restored=true moved=0
    PERF: restored=[0 4] perf_restored=true

Read back from the device 5 s after the soak:

    after +5s: performance_mode=0 fan_mode=4 fan_speed=null duty=24500 battery=78

### Nova: queued, pending the top-up

The Nova has been under hostops' battery hold since 18:10 UTC (14%; it lifts
at 80% on the 500 mA port, hours; the owner's top-up is about 18:00 PDT).
Per Addendum 3 the PR does not wait for it. Two 180 s Blinx soaks are queued,
pinned to the Nova, at ref ff9f8824ac (origin/master; the ref only picks the
APK):

| request | env | the menu shows it at | expect in every sample from `start` to `end` |
|---|---|---|---|
| `1-1790623244-lane.fanduty507-2553125` | `FAN_MODE=customize:100` (MAX) | HIGH (2) | fan_mode 6, duty 35000 (decoded, never measured) |
| `1-1790623251-lane.fanduty507-2563259` | `PERF_REGIMEN=default FAN_MODE=quiet` | NORMAL (0) | fan_mode 1, duty 12000 (decoded) |

The first is the discriminating one. The Nova's MAX fan is already Sport
(5), so `FAN_MODE=sport` under MAX would read the same with the knob and
without it.

**These soaks only count if the dispatcher serves this PR's soak_title.sh
when they run.** At 19:20 UTC the dispatcher's snapshot
(`$DISPATCH_DIR/bin/soak_title.sh`, 07:13 UTC) has no `FAN_MODE`. It gets
this code from the fold and the host's update window after it. How to read
each result:
- `perf_regimen.json` has a non-null `fan_request`: the knob ran. Read
  `ran`, `restored`, `fan_restored`, `moved`, and `fan.mode` and the duty in
  every thermal.jsonl sample.
- `perf_regimen.json` has no `fan_request` key: the old script served it and
  ignored `FAN_MODE`. The run says nothing about the knob. Queue it again
  after the update window.

A 35000 that reads otherwise is a wrong decode of the Nova's Customize
slope, not a broken knob: the knob's claim is the `fan_mode` and
`fan_speed` it sets and restores. Correct the table in section 1 from the
measured value. If the knob itself fails on the Nova, the fix goes in a new
PR on `lane/fanduty507-mode-nova`.

The idle reads of every mode on the Nova (`modeprobe.sh`) need a held device
and are still open. For when it is idle:

    docs/testing/jobs/hold.sh take nova lane.fanduty507 "<why>"
    bash docs/lanes/fanduty507/modeprobe.sh ee317437 20 3 5 smart=4 quiet=1 sport=5 \
        customize=6:0 customize=6:50 customize=6:100 off=0 > docs/lanes/fanduty507/probe-nova.md
    bash docs/lanes/fanduty507/proof-run.sh ee317437 $PWD/.proof/nova-sport sport default \
        /storage/E6C6-D7AA/Games/XBox/4D530013-Blinx_The_Time_Sweeper.xiso.iso 180
    docs/testing/jobs/hold.sh release nova lane.fanduty507

## 5. The screen across the cool-down gate (Addendum 2, its own commit)

**The bug.** soak_title.sh sent KEYCODE_WAKEUP, then ran the cool-down gate
(which can wait minutes), then `am start`. On 2026-09-28 the Thor's screen
timeout was 60 s. Two runs cooled for 77 s and 78 s, found the display OFF at
`am start` (`display at start {"0":"OFF","4":"OFF"}`), and aborted "not
foreground (unknown)": `1-1790606269-lane.dirtytlb-479803` and
`1-1790613195-forza414-3088504`.

**The fix** (dded7e06b1, `Release note (none): test harness.`):
1. force-stop, KEYCODE_WAKEUP, and the display check (`display_gate`). A
   covered display is still refused here, and no KEYCODE_SLEEP reaches the
   owner's screen, as #494 requires.
2. KEYCODE_SLEEP, then the fan-mode check and the cool-down gate, dark.
3. KEYCODE_WAKEUP, then `display_gate` again, immediately before
   `arm_audio`, `perf_enter`, `fan_enter` and `am start`. A cover that appears
   during the gate is refused here (exit 4, before anything is armed).

The brief asked for the sleep before the gate and the wake after it. It did
not ask for the first check. I kept it because otherwise the sleep would go
out before the covered-display refusal, and 99-display-covered's `covered` leg
(no KEYCODE_SLEEP over the owner's screen) would go red.

**Selftest `99-wake-after-gate.sh`.** The fake adb models a screen with a
1.5 s timeout. xo-therm reads 70 C for three samples, then 50 C, so the gate
waits about 3 s. The legs and the world each fails in are in its header. On
this branch:

    ok   on: the gate waited 3 s against a 1.5 s screen timeout, and the display read ON at am start
    ok   order: adb saw [wake sleep cool cool cool cool wake cool am cool cool sleep ]
    ok   recheck: a cover that appears during the gate is refused after it: exit 4, display-covered, no am start
    ok   covered: a display covered from the start is refused before any sleep; adb saw [wake ]
    ok   old-order mutant: the display is OFF at am start, and the on leg turns red
    selftest: 5 passed, 0 failed

Against the real old-order soak_title.sh (HEAD before the fix, copied back
after):

    FAIL on: display-OFF-at-am-start | ... COOLDOWN: waited 3 s, xo 70.0 -> 50.0 C ...
    FAIL order: adb saw [wake cool cool cool cool cool am cool cool sleep ], not wake, sleep, ...
    FAIL recheck: rc=0 at_start=OFF | ...
    ok   covered: ...
    FAIL old-order mutant: its anchors are gone from soak_title.sh -- update the mutant
    selftest: 1 passed, 4 failed

Neighbouring fragments on this branch, each run alone: 99-display-covered
23/0, 99-thermal-pause 16/0, 99-fan-mode 33/0, 84-perf-regimen 21/0,
89-title-verdict 81/0, 99-default-regimen 7/0, 99-usb-dialog 9/0,
99-iso-roots 10/0.

No real soak exercised this fix. The Thor was running
`1-1790620563-arms-dirtytlb-base-1288042` and the Nova was held. The next
dispatched soak on either device runs it, once the host's update window has
restarted the dispatcher.

## Status (2026-09-28, attempt 4)

- #571 is marked ready once CI is green on the pushed head (Addendum 3). CI
  on attempt 3's head e63056ac50: Desktop build, Android build and three of
  four selftest shards passed; the fourth was still running at 19:21 UTC.
- Open, outside this session: the two queued Nova soaks (section 4). They
  run after the Nova's battery hold lifts. Their reading goes on #507 as a
  follow-up, and the Nova column of the table in section 1 gets its
  measured values then.
- Open: the Nova's idle per-mode reads (`modeprobe.sh`), which need a hold.
- No real soak has run the screen-wake fix yet (section 5). The first
  dispatched soak after the update window does.

## For the next lane

- The fan menu lives in SystemUI, not in the OEM settings app. Read
  `FanTile` / `FanDialogView` before trusting a settings-app string array:
  `array_fan_speed` looks like a menu and is dead.
- The menu's options depend on performance_mode. A fan mode is only
  "user-selectable" together with the performance mode it runs beside.
- The Thor's Sport is not its maximum. Under load, Smart runs above it.
- Do not write the PWM node. Every user-reachable duty on the Thor,
  including full fan, is a `settings` write (`customize:100`).
- Do not put a KEYCODE_WAKEUP before anything that can wait. The screen
  timeout starts at the wake, and a soak needs the display lit at `am start`.
