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
Both sources agree that 3 is the high setting and 4 is Smart.

Chosen, and carried per device in `devices.sh` `device_env`:

| | performance_mode | fan_mode |
|---|---|---|
| MAX | 2 (HIGH) | 3 (PERFORMANCE / "High speed") |
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

(results pending: see below)

## Do not repeat

- `aapt`/`unzip` may be unavailable to a lane shell. `arsc_strings.py` reads
  resources.arsc with only the stdlib, and Python's zipfile extracts dex.
- The Thor's `gpio5_pwm2/speed` is always 0. Read `duty` there.
