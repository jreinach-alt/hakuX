# lane.thermal507 (#507): the Thor's thermal pause in title benchmarks

## What was built

- `docs/testing/thermal_state.py`: one `adb shell` call reads every
  `/sys/class/thermal/cooling_device*` (type, cur_state, max_state), every
  `thermal_zone*` (type, temp), the device clock and uptime; prints one JSON
  line. Modes: `--diff A B` (cooling devices whose cur_state rose), `--summary`
  (run.log line), `--window FILE LO HI` (could a pause overlap LO..HI s after
  the first sample?), `--trips SERIAL` (read-only trip points and zone ->
  cooling-device bindings).
  The device-side read is `hoststate.sh`'s thermal block (lane.gta482), reading
  every device instead of only the non-zero ones. A clean baseline is what
  bounds a pause's onset.
- A pause is any `thermal-pause-*` (mask) or `pause-cpuN` (per-core) device
  with cur_state > 0. The Thor has both kinds, all 0/1.
- `soak_title.sh`: samples to `thermal.jsonl` beside the capture: once before
  `am start`, every `THERMAL_EVERY_S` (30 s) from the existing hold loop, and
  once after `soak end`. Writes a `THERMAL:` summary line to run.log. If an
  older snapshot lacks the script, it says so (`THERMAL: not recorded`), and no
  thermal.jsonl then reads as unread, not as clean.
- `dispatcher.sh`: `thermal_state.py` is added to `SCRIPT_DEPS` and
  `snapshot_scripts`. Without it a worker's snapshot has no sampler.
- `title_verdict.py`: a pause episode that may overlap the scored window
  (`mark gameplay` .. `soak end`, device time) makes the run `void:
  thermal-pause: ...`, with every fps field null, the same shape as #495's
  `display-covered`. Every episode is recorded in `verdict.thermal`, inside
  the window or not. A run with no thermal.jsonl is judged as before, with
  `thermal.measured: false`.
- Bounds: sampled every 30 s, a pause's onset is only known to lie between
  the last clean sample and the first paused one. The span it may cover runs
  from the clean sample before it to the clean sample after it. A failed read
  is not clean, so it widens the span. That is why the brief's fixture (pause
  first seen at +250 s, window 90..240 s) is flagged: the last clean sample was
  at +220 s.
- `selftest.d/99-thermal-pause.sh`: onset / later / none / unread / all-fail /
  per-core / not-pause / --diff legs, a first-seen mutant, a soak leg against a
  fake adb, and three verdict legs. Each leg's header names the world in which
  it fails.

## What trips the pause (READ-ONLY read, `thermal_state.py --trips`)

### Thor bdc158a5, 2026-09-27 13:57 PDT, no request running (titleroutes held it)

`thermal-pause-F8` (cooling_device10: pauses cpu3-7) is bound to three zones:

| zone | type | trip | temp | hyst | reading then |
|---|---|---|---|---|---|
| tz90 | xo-therm | 2 | **78.0 C** passive | 8.0 C | 77.2 C |
| tz84 | pm8550vs_c_tz | 0 | 95.0 C passive | 0 | 75.9 C |
| tz82 | socd | 2 | 99 (not a temperature) | 0 | 18 |

- **xo-therm at 78 C is the trigger** in practice. It is the only binding
  near its trip at MAX. With 8 C of hysteresis, the pause holds until
  xo-therm falls below 70 C, which is why the pause lasts minutes rather than
  flickering.
- The same xo-therm trip 2 also drives kgsl devfreq (the `5/8` in #507).
  Trip 3, at 80 C, hotplugs cpu3-7 (`cpu-hotplug3..7`), and trips 4-7 drive
  `display-fps`.
- The per-cluster devices (`thermal-pause-8`, `-10`, `-20`, `-40`, `-80`,
  `-2`, `-4`) are bound to their own cpu zones at 108 C, far above the 85-95 C
  cores read at MAX.
- `socd` is the battery's state-of-charge-drop monitor (percent, not C). Its
  trip is at 99.
- The Thor read hot (cpu-1-9 95 C, xo-therm 77.2 C) with nothing in running/.
  titleroutes' nav.py session was active on it.

### Nova ee317437

(pending: the Nova was running notify488's arm, then held for the host update)

## Pilot soak

(pending)

## Existing Thor title benchmarks (brief item 4)

Posted on #507 (comment 5859894811). 122 Thor title soaks of the last 48 h
were binned at 30 s from `soak start`. A run is flagged when, at 200 s or
later, the median of the three preceding bins is >= 10 fps and every later bin
is < a third of it. Each flagged run is then checked against other runs of the
same title past the same second.

Probable pause: slowdown462-3573620 (GTA, 270 s), titleplay-p1-crimson
(300 s), **titleroutes-1074940 Blood Wake (300 s; its verdict scored the
paused windows: share 0.295, and 37-40 fps before the fall)**,
titleroutes-1523259 (BF2, 480 s), and two Forza runs (ambiguous: 2 of 3
Forza runs fall at 240-300 s). vcpuprime428-3939754 sits just under the
threshold, at 390 s.

Not the shape: falls before `mark gameplay` (loads), falls that recur at the
same second across runs (Blinx and PGR at 180 s), and 0-fps bins (no perf
line). Midtown Madness 3 holds 3 fps from before its mark; this trace cannot
tell a hot device from the title.

- A fps-only detector without the same-title check flags every Blinx run
  (60 -> 12 at ~100-200 s, content). Always compare against sibling runs.

## For the next lane

- Do not look for the pause in cpu/online, cpusets, scaling_cur_freq or
  thermalservice. Only the cooling device's cur_state shows it.
- `cdevN_trip_point` lives in the zone directory, not behind the `cdevN`
  symlink (`$c/..` resolves to the cooling device's parent). The first trips
  read came back empty that way.
