# lane.perfregimen: MAX performance and fan during title soaks, REST on every exit

Brief (owner, 2026-09-26): switch the handheld to max performance and fan for
title soaks only (never pgraph/disc runs), put it back to rest on every exit
path, and record both in the result. Before this, the harness never set or
recorded the modes. The Thor sat at `performance_mode=0` and the Nova at `1`,
both with `fan_mode=4`, so every title-soak frame rate so far (#397: #372,
#412, #413, #414) carries an unrecorded mode difference between the devices.

## 1. What the two settings mean (read from the OEM code, not guessed)

Both are `settings system` integers. They are owned by
`com.android.settingslib.MoorechipSettingsLib` inside SystemUI.apk
(`/system_ext/priv-app/SystemUI/SystemUI.apk`, pulled from the Thor; the Nova
ships the same library). The enum static initialisers, read with `dexdump -d`:

| setting | 0 | 1 | 2 | 3 | 4 | 5 | 6 | default |
|---|---|---|---|---|---|---|---|---|
| `performance_mode` (PerformanceState) | NORMAL | STANDARD | HIGH | | | | | NORMAL (0) |
| `fan_mode` (FanState) | DISABLED | QUIET | BALANCE | PERFORMANCE | SMART | SPORT | CUSTOM | QUIET on Thor/RP6; the devices read 4 |

The OEM settings apps (`com.odin.settings` on the Thor, `com.rp.settings` on
the Nova) label fan indices 0-4 as `Off, Quiet, Sport, High speed, Smart`
(`array/array_fan_speed`, read from resources.arsc with `arsc_strings.py`).
The two sources disagree above 1 (the settings app's index 2 is "Sport", the enum's 2 is BALANCE), and only the enum is what `fan_mode` stores. Both agree that 4 is Smart. Which mode is the maximum was settled by measurement, not by labels (5a).

Chosen, and carried per device in `devices.sh` `device_env`:

| | performance_mode | fan_mode |
|---|---|---|
| MAX | 2 (HIGH) | 5 (SPORT). 3 was the first choice, and the idle probe (5a) showed it is not the fan's maximum |
| REST | 0 (NORMAL, the library default) | 4 (SMART, what both devices were found at) |

REST is the same on both devices, so the Nova no longer idles at STANDARD.

## 2. The readouts that should move (found read-only, before any write)

- **GPU floor:** `/sys/class/kgsl/kgsl-3d0/min_clock_mhz` and `min_pwrlevel`
  are world-readable. On 2026-09-26 the Thor at `performance_mode=0` read
  401 MHz (pwrlevel 4), and the Nova at `1` read 550 MHz (pwrlevel 2). The
  floor is a setting, not a load reading, so it tracks the mode directly.
- **Fan:** the OEM apps' dex strings name `/sys/class/gpio5_pwm2/{duty,state,speed}`.
  On both devices, `duty` is the PWM duty and moves with load (Thor 13500 to
  37000). `speed` is a tach: the Nova reads 4500-6600 rpm under a title, the
  Thor always reads 0, so on the Thor the readout is `duty`.
- CPU `scaling_min_freq` and the devfreq `min_freq` are root-only. `scaling_cur_freq`
  is readable and sampled.
- No hwmon, and no fan cooling_device, on either device.

## 3. The switch (soak_title.sh, devices.sh)

- `devices.sh`: `DEVICE_PERF_MAX/FAN_MAX/PERF_REST/FAN_REST` per row,
  `device_perf_values`, `device_perf_get`, `device_perf_set`. `device_perf_set`
  returns the device's read-back and succeeds only if that equals what was
  asked for.
- `soak_title.sh`: `perf_enter` runs before `am start`. `perf_leave` runs in
  `release()`, after the force-stop and before the screen sleeps. `release()`
  now runs from the EXIT trap alone: TERM exits 143 and INT exits 130
  through it. The old `trap release EXIT INT TERM` ran release on a TERM and
  then returned into the hold loop, which polled a stopped title until its
  deadline. `PERF_REGIMEN=max|rest|off` (default max). `rest` is the pilot's
  control arm, set explicitly rather than inherited.
- Recorded: `perf_regimen.json` beside `logcat.txt` in the result dir
  (`perf_mode`, `fan_mode`, `perf_restored`, plus before/restored/max/rest),
  and `PERF:` lines in run.log.
- **result.json** is written by dispatcher.sh, which is claimed by #440.
  `dispatcher-result-fields.patch` (12 lines, disjoint from #440's hunk)
  copies the fields in, and a board request asks for the file. Until it lands,
  the fields are in `perf_regimen.json` in every title-soak result dir.
- Not reachable from a trap: SIGKILL, and a host that loses the device
  mid-run. Those are what the host's `device_reality.sh` restore of REST
  on idle handhelds is for (values posted on the PR).
- pgraph/disc runs: `run_disc.sh` is untouched. selftest.d/84 asserts it
  calls no `device_perf_*`.

## 4. Selftest (selftest.d/84-perf-regimen.sh)

17 checks against a fake adb that keeps the two settings in a file. Each run
starts from 1/4 (the Nova's found state), so "left at REST" cannot pass by
never writing. The legs: exit 0, a non-zero exit (a copy that dies after
`am start`), TERM mid-hold (and it must exit promptly), MAX in force at the
moment of `am start`, the rest arm starting at REST, and ignored writes
recording `perf_restored: false`. Three mutants must each be caught: no
restore in release(), TERM returning into the loop, and no EXIT trap.
`run_fragment.sh` runs one fragment alone. selftest.d/89 (the same script
against a fake adb that knows no settings) stays 36/36.

## 5. Proof and pilot (device)

Registered before any write: `docs/testing/predictions/perfregimen-pilot-thor.json`.
It covers the idle probe (P1 GPU floor, P2 fan duty) and REST/MAX/REST Blinx
arms (P3 load readouts, P4 REST agreement, P5 non-inferiority, P6 a labelled
guess of +5%). Runner: `held_session.sh <label> <dir>`. Judge: `judge.py`.

### 5a. The Nova, held 15:43:29-16:13:31 PDT (raw records: `pilot-nova.md`)

**The writes reach the hardware.** Idle probe, 8 s settle per step, no title:

| performance_mode | kgsl min_clock_mhz (min_pwrlevel) | big-core cur (policy7) |
|---|---|---|
| 0 NORMAL | 401 (4), four times | 1843200 |
| 1 STANDARD | 550 (2) | 2476800 |
| 2 HIGH | 615 (1) | 3187200 |

| fan_mode | PWM duty | state | tach rpm |
|---|---|---|---|
| 0 DISABLED | 0 | 0 | 300 (spinning down) |
| 1 QUIET, 2 BALANCE, 3 PERFORMANCE, 4 SMART | 12000 | 1 | 4200-4800 |
| 5 SPORT | 25000 | 1 | 8100 |

The device log names the actuators: `pservice: cpu_init boot_completed cpugpumode=0`
writing kgsl `min_pwrlevel` (the vendor perf service, domain `pservice`),
and `FanBase: mSmartAction smartSpeed = 13519` (the SMART fan curve in the
OEM settings app).

**The registered prediction's P2 failed in the world it named.** Fan mode 3
is not the fan's maximum: at idle it holds the same duty as SMART, and 5
(SPORT) doubles it. So FAN_MAX is 5 (commit 1d828b45e4). A follow-up MAX
arm at 2/5 was registered (`perfregimen-pilot-nova-fan5.json`) before it ran.

**The first two sessions' arms were VOID, and the fault was mine.**
held_session.sh gave soak_title.sh a scratch lease. Every Claude session's
Stop hook (`stop-emulator.sh`) force-stops hakuX on any handheld whose
per-device lease (`/tmp/hakux-device-lease.<label>`) is stale. It does not
read `dispatch/hold/`, so other sessions' turn ends killed the arms 33-103 s
in. `watch_forcestop.py` caught one of those hooks (cloud-audit1-419's) in
the act. With the real lease, session 3 ran clean. The **hold gap in the
Stop hook** is the host's to decide (it is not this lane's file): a hold
alone does not protect a device from other sessions' Stop hooks. Only the
lease does.

**Session 3, REST / MAX(2/5) / REST, Crimson Skies hands-off, 250 s arms.**
Arm 3 was TERMed at 16:13:15 to keep the hold under 30 minutes. That is also
the TERM leg on real hardware: rc 143, REST restored, read back as 0/4.

| arm | fps 135-245 s (median gfps) | lines | ran at | restored | GPU MHz | GPU floor | fan duty | fan rpm | gpuss-0 |
|---|---|---|---|---|---|---|---|---|---|
| 1 rest | 29 | 55 | 0/4 | true | 401 | 401 | 13729 | 5700 | 46.7 C |
| 2 max | 29 | 55 | 2/5 | true | 615 | 615 | 25000 | 9000 | 48.9 C |
| 3 rest | 29 | 33 (TERM) | 0/4 | true | 401 | 401 | 15024 | 6300 | 50.1 C |

Verdict against `perfregimen-pilot-nova-fan5.json`: M0 through P5 pass, and P6
(the labelled +5% guess) fails. The mean gfps in every stretch of every arm
(0-60, 60-135 and 135-245 s) is 28.7-29.4: Crimson's hands-off stretch is
**content-capped at ~30 fps**, so no mode can move it. The regimen works (the
MAX arm really ran at MAX, and REST really came back). This title just cannot
show an fps effect. The informative fps pilot is the Thor's Blinx demo
(12-16 fps, under its cap).

**The reader changed after registration, and this says so.** The
registration names the blinx372c cadence reader (60 flips per gfps line).
On this APK, `gfps=` is printed every ~2 s with that window's fps as its
value, and 2 s apart is also what 30 fps at 60 flips per line looks like. So
the cadence reader returns ~30 whatever the rate, and judge.py reads the
value instead.

### 5b. The Thor: pending

At the time of writing the Thor was below the brief's 50% start floor (43%,
flat while serving the queue) and held by lane.xbox. Its values are the same
library's (the enums were read from the Thor's own SystemUI.apk), and its
read-only state agrees with the Nova's mapping (0/4 reads 401 MHz and
pwrlevel 4, exactly as the Nova does at 0). Its write proof and the Blinx
pilot (`perfregimen-pilot-thor.json`, fan MAX now 5) remain to run:
`launch_session.sh thor <dir>`.

**Why attempt 1 did not finish.** It ended at 16:20 PDT with the PR still in
draft, "waiting" for the Thor to be unheld, idle and at 50% or more. Nothing
could wake it for that: the Thor serves the 0.5 queue on a 500 mA port, and
its battery falls under load (43%, then 34% at 16:44, 33% at 17:1x). The
wait named a condition, not a signal, and the condition does not happen by
itself. It should have marked the PR ready then, as its own second bullet
said to. hostops' 16:45 addendum made that decision: the Thor pilot no
longer gates the PR.

### 5c. Attempt 2: the Thor pilot goes through the queue

- **A queued soak can choose its arm.** `request.sh --env PERF_REGIMEN=rest`.
  The dispatcher does not pass a request's env to soak_title.sh. It writes
  the env to the app's `env_vars` pref, where an unknown name does nothing.
  So soak_title.sh reads `PERF_REGIMEN` from the request the dispatcher is
  serving, at `$D/running/<id>.req`, found from `CAPTURE_LOG`
  (`$D/results/<id>/logcat.txt`). The shell's `PERF_REGIMEN` wins. Absent
  or unknown values mean max. Two selftest legs cover it (19/19): the rest
  request starts the title at 0/4, and a request with other env starts it at
  2/5.
- **The pair**, registered as `perfregimen-pilot-thor-queued.json` before
  either arm runs. REST and then MAX, Blinx, 300 s each, the same `--ref`
  (master at the fold). The exact `request.sh` lines are in its `requests`
  field. Judge: `judge_queued.py <REST result dir> <MAX result dir>`.
  Smoke-tested on the Nova session-3 arms, where it reproduces 5a's verdict
  (P5 PASS, P6 FAIL at 1.000). The host queues the pair when #444 folds.
- **The Thor write proof** (no title, idle probe only):
  `BATT_MIN=30 ARMS=' ' bash held_session.sh thor <dir>`, under a hold.
  The result is below (5d) if it ran.

## For the host: REST values for host-tools/device_rest.conf

    thor performance_mode=0 fan_mode=4
    nova performance_mode=0 fan_mode=4

## Do not repeat

- `aapt`/`unzip` may be unavailable to a lane shell. `arsc_strings.py` reads
  resources.arsc with only the stdlib, and Python's zipfile extracts dex.
- The Thor's `gpio5_pwm2/speed` is always 0. Read `duty` there.
- A hand-run soak on a held device MUST touch the device's real lease
  (`/tmp/hakux-device-lease.<label>`), or any session's Stop hook kills it.
  The hold does not protect it.
- A content-capped title cannot show a clock effect. Check the REST arm's
  fps against its cap (Crimson hands-off: ~30) before choosing a pilot title.
- Running `settings get` / `cat` on sysfs from `adb shell` logs `avc: denied`
  lines in permissive mode. They are harmless noise in the device log.
