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

### Nova ee317437, 2026-09-27 15:03 PDT, idle (nothing in running/ for it)

The bindings match the Thor's. `thermal-pause-F8` (cooling_device9 on
the Nova) is bound to xo-therm trip 2 at **78.0 C, hyst 8 C**, to
pm8550vs_c_tz at 95 C, and to socd at 99. Trip 3 at 80 C hotplugs cpu3-7. The
per-cluster pause devices trip at 108 C (big cores) and 110 C (cpu-0-1 and
cpu-0-2). Idle readings: xo-therm 41.3 C, hottest zone 46 C.

- **socd read 76 on the Nova (battery 24%) against 18 on the Thor (82%).** Its
  trip is 99, and it drives the same `thermal-pause-F8` and kgsl devfreq. If
  socd tracks battery drain, a low-battery Nova may pause without being hot.
  Unverified. thermal.jsonl records socd in every sample, so the first Nova run
  that pauses with a cool xo-therm will answer it.

## Pilot soak: blocked, and it cannot exercise this PR before the fold

- Dispatcher workers run `soak_title.sh` from the main tree at master
  (`TREE=/home/justin/hakuX`, snapshot to `$SNAP`), not from a request's ref.
  The soak-side wiring can only run on a device after #508 folds and the
  dispatcher's update window re-snapshots. The selftest's soak leg (fake adb)
  covers it until then.
- To test the instrument on real data before that, two Thor soaks were queued
  (GTA SA, gta-sa route, 600 s, MAX, battery 82%). A host-side loop ran
  `thermal_state.py` every 30 s beside them (`.scratch/pilot_sampler.py`, not
  committed).
  **Both aborted at ~45 s on #495's foreground guard**:
  `0-0-x-1790542932-thermal507-3310387` and `0-0-x-1790545608-thermal507-66494`.
  Each logged `not-foreground: com.magneticchen.daijishou (... display 0 ...)`
  with hakuX running (perf lines, audio). They were the first two Thor soaks
  since the guard went live (~14:34 PDT), and so far every Thor route soak
  aborts this way. Reported on #495 (comments 5860115223, 5860169304). Their
  thermal samples (3 per run) were all clean and prove nothing about the pause.
- The request id gains a `0-0-x-` prefix when promoted. A watcher keyed on the
  queued id never sees it run: glob `running/*<id>.req`.
- **Pilot to run after the fold:** one Thor GTA SA soak, gta-sa route, 600 s,
  MAX, battery >= 30%. Its `thermal.jsonl` should show `thermal-pause-F8` 1/1
  from ~4-6 min, `run.log` should carry `THERMAL: pause ...`, and verdict.json
  should be `void: thermal-pause: ...` if the pause lands after the mark
  (~225 s). Only if that is clean: fan_mode 5 vs 4, time to pause (report only;
  the regimen is perfregimen's).

### Post-fold pilot (session 3, 2026-09-27 16:30 PDT)

- Why session 2 did not finish: the pilot could not exercise the soak
  wiring before #508 folded (above), so it ended waiting on the fold. #508
  folded as 8a54dcf1b2 at 16:20 PDT. The dispatcher update window started at
  16:26 PDT to put the merged scripts in the workers' snapshot.
- Queued `1790551730-thermal507-2943941`: GTA SA, gta-sa route, 600 s, Thor,
  ref 8a54dcf1b2. It claims after the update window.

### The first field records (flip474's Thor soaks, 16:38-17:01 PDT, merged tree)

The three flip474 soaks queued ahead of the pilot ran the merged sampler.
Samples came every ~33 s: 30 s plus the read.

| run | title, s | xo-therm at pause | pause | THERMAL line |
|---|---|---|---|---|
| 1818830 | Forza, 423 | 77.3 -> 78.1 C (+269/+302 s) | set by +337 s, held to end (xo 73.8) | `began after +303 s and by +337 s` |
| 1819047 | Forza, 427 | 77.4 -> 78.0 C (+304/+337 s) | **paused at start** (the previous run's heat) until +172 s (xo 70.2 -> 71.3); set again by +373 s | two episodes |
| 1819312 | Crimson Skies, 248 | peak 75.9 C | none | `no thermal-pause device above 0` |

- The trip is **xo-therm 78.0 C**, set within one sample of reaching it, and
  cleared near 70 C (hyst 8), as the trip read above predicted. The hottest
  CPU zone then drops from ~95 C to ~84 C, the cpu3-7 pause.
- At MAX from ~62-67 C, xo-therm climbs ~2 C/min, so reaching 78 C takes
  5-6 min. A run queued right after a hot run starts paused. So a benchmark's
  exposure depends on its **queue neighbour**, not only its length.
- `title_verdict.py` on a copy of 1818830 (flip474's own dir left untouched):
  `FAIL(void: thermal-pause: thermal-pause-F8 1/1 began after +49 s and by
  +83 s ... relative to the mark)`, `thermal.in_window: true`, every fps
  field null. The whole chain works on a real run.
- A 4th run, 1819530 (Crimson Skies, 248 s), started at xo 75.1 C, 4 s after
  the previous soak. It paused at +238..250 s. **Even a 240 s benchmark pauses
  when it follows a hot run.**
- The GTA pilot did not claim. At 17:03 PDT the owner took an OWNER hold on
  the Thor to move it to a rear USB port. Only the owner lifts it.

### Addendum item 3: older readings, from their saved traces (no thermal record)

Method: 30 s fps bins from `soak start` (`.scratch/bins.py`) and the Thor's
previous run with the gap before it (result mtimes). Rule from the field
records: from a cool start the pause needs 5-6 min at MAX; a run within
seconds of a hot one can pause in 2-4 min. Once set, it holds for minutes (8 C
hysteresis). A fall that clears within one or two bins is not the pause.

| reading | run | before it | trace | verdict |
|---|---|---|---|---|
| MechAssault 2 20-min, ~11/~30 | lanelocal-1258823 | GTA 500 s MAX, **gap 4 s** | 11 fps +150..+540 s, 30 fps +540..+780 (4 min), 11 fps +810..+1500 | **consistent with the pause**: hot start; the 30 fps spell lasts as long as 70 -> 78 C takes (~4 min); 2.7x fall |
| MechAssault 2 530 s | titleroutes-681960 | gap 632 s | 30 fps flat after the mark | no pause |
| Midtown Madness 3, 3.1 | titleroutes-1032854 | Alien Hominid, **gap 4 s** | 60 -> 12 -> 3 at +120..+180 s (before the mark at +323), 3 to the end | hot start, so a pause is possible, but a 20x fall exceeds the pause's 5-7x. **The pause alone does not make 3 fps** |
| Black, 7.45 | titleroutes-3358750 | gap 1387 s (cool) | 30 -> 4 at +210 s (same second in 3347838 and titleplay-p1-black: content), 7-9 fps +510..+780 s after the mark at +493 | the +210 fall is content. The post-mark 7-9 falls where a cool start reaches 78 C, so **undecidable** |
| #462 Nova soaks (DOA, AUF x2, Blinx x2, Forza) | slowdown462-* | Nova, not read | falls at +60..+120 s, the same second per title | too early for the pause, and they recur: **content** |
| GTA (#482's 4-5 fps) | slowdown462-3573620 | Crimson, **gap 2 s** | 19-28 fps to +270 s, then 3-5 to the end | **the #507 shape**: hot start, 5-7x fall, held |
| GTA | slowdown462-1484367 | gap 2543 s | low before and just after the mark, 27 fps +300..+450, 5 in the last bin | mixed, no clean pause |

### GTA pilot: one abort, retry queued (17:16 PDT)

- `0-0-x-1790551730-thermal507-2943941` claimed at 17:13, the moment the
  owner lifted their hold. It aborted `not-foreground: com.odin.settings`
  before any input. Settings was left open from the port move, and the guard
  worked as designed. Its thermal.jsonl has only pre-launch samples.
- The retry is `1790554531-thermal507-3751184` (same route, 600 s). It is not
  promoted. About 2 h of Thor work is ahead of it (six titleroutes soaks of
  500-780 s, forza414, drain474). Those soaks record thermal.jsonl too, which
  is more field data for the verdict.
- The brief's Proof is already met by flip474-1818830 (thermal.jsonl shows the
  pause; the verdict is `void: thermal-pause`). The GTA run is what #482 asks
  for. After it: the optional fan_mode 5 vs 4 comparison, as the brief allows.
- Session 3 ended **waiting on `1790554531-thermal507-3751184`** (a dispatch
  request, outside this session).

### The GTA pilot's result (session 4, 2026-09-27 17:35 PDT)

- Why session 3 did not finish: it ended correctly, waiting on the dispatch
  request `3751184`. That request finished at 17:27, and handback resumed
  this lane.
- `0-0-x-1790554531-thermal507-3751184`: this is the brief's Proof, and it
  is clean. The run started cool (xo-therm 54.3 C, after the owner's ~10 min
  port move). xo-therm rose 59.3 (+40 s), 66.2 (+138), 69.8 (+204), 72.9
  (+271), 75.1 (+337), 77.0 (+437) and 78.03 (+538). The rate fell from
  ~2.3 to ~0.7 C/min but never flattened. `thermal-pause-F8` read 1/1 by
  +573 s (device 17:26:59) and held to the end. The hottest CPU zone went
  95.8 -> 85 C. run.log: `THERMAL: pause ... began after +535 s and by +569
  s`. verdict: `void: thermal-pause`, fps fields null.
- fps in 30 s bins, with the mark at +226 s: 28 28 26 28 26 23 25 26 24 21
  (mean 25.5) over +240..+540 s, then 4 4 while paused (6.4x).
- **A 20-min soak at MAX/fan 4 cannot be valid**: it gets ~9 min clean from
  cool, then a pause/unpause cycle (70 -> 78 C takes ~5.5 min at MAX), and
  #508 voids the whole window. A cool-down gate fixes short benchmarks only.
- Posted on #507 (5861276514) and #482 (5861276643).

### The cool-down gate (commit 4124a609e9)

- `soak_title.sh`, before `perf_enter` (MAX) with the title stopped: it
  samples (`cool` lines in thermal.jsonl) every THERMAL_COOL_EVERY_S (20 s)
  while xo-therm >= THERMAL_COOL_C (65) or any pause device is set, for at
  most THERMAL_COOL_MAX_S (360 s). One `COOLDOWN:` line goes to run.log, in
  the words of hostops' spec (#507 comment 5861274869):
  `COOLDOWN: waited <s> s, xo <start> -> <end> C [...]` (0 s when the first
  read was cool), `COOLDOWN: gave up at <C> C after <s> s, ...; starting
  hot`, or `COOLDOWN: not gated ...` for a missing zone or an unread sample.
  `THERMAL_COOL_C=off` disables it.
- **The cap is 360 s, not the spec's 10 min.** harness_health.py calls a
  soak overrunning at `seconds` + 10 min from the run's first artifact, and
  its remedy line tells the reader to force-stop a hung guest. A 10 min wait
  plus the soak would cross that line on every run that reached the cap.
  `THERMAL_COOL_MAX_S=600` selects the spec's cap once the overrun rule
  counts a logged cool-down as expected time. A run that is still hot at
  the cap starts anyway, and says so; the verdict voids it if it pauses.
- devwatch (lane.local, 17:35 PDT) holds a device from xo-therm 74 C until
  65 C once nothing runs. That is the first gate; this one is the backstop
  for a request claimed between 65 and 74 C, and the record in the run.
- Why 65 C: hostops' ask (hostops-inbox 17:14). At MAX, 66 -> 78 C took
  ~6.7 min in the pilot, so a title gated at 65 C gets ~3 min of scored
  window after GTA's ~4 min route. From 54 C it gets ~5 min. A lower limit
  buys more scored time for a longer wait. The pilot measured the paused
  device cooling at ~2-3 C/min just below 78 C. How fast an idle device
  cools from 75 to 65 C is not measured yet; the gate's `cool` lines will
  measure it.
- `thermal_state.py --cool FILE ZONE C` is the check. The summary and
  `--window` now count offsets from the `start` sample, so the cool samples
  do not shift them.
- selftest 99: the --cool legs (cool, hot at the limit, paused below it, no
  zone, unread) and three fake-adb soaks (it waits: three `cool` samples
  before the first perf write and am start; at once: a 54 C read starts
  with a 0 s wait; the cap: gives up at 2 s and starts). Siblings 84, 89,
  97, 99-display-covered and 99-iso-roots pass.
- Live only after this PR folds and a dispatcher update window runs.

### The regimen comparison (addendum item 4), queued 17:44 PDT

- `soak_title.sh` offers only `PERF_REGIMEN=max|rest|off`. fan_mode comes
  from device_rest.conf (Thor: 4 at MAX and at REST). **fan 5 cannot be
  selected without a regimen edit**, which this lane may not make. So the
  comparison is MAX/fan 4 against REST (perf 0)/fan 4.
- `1790555882-thermal507-352176` (REST) then `1790555883-thermal507-352252`
  (MAX): GTA gta-sa, 1200 s, ref 8a54dcf1b2, the pilot's apk. The master
  soak has no gate yet, so each start temperature is whatever its queue
  neighbour left. thermal.jsonl records it; compare from the start
  temperature. pilots/thermal507.ok admits the 43 min.
- Read: sustained fps after the mark, paused minutes, time to pause, and
  xo-therm at start. Then report on #507, with the data for perfregimen's
  successor.
- **WITHDRAWN 17:47 PDT (session 5), both unclaimed.** The brief's addenda
  (hostops 17:31, lane.local 17:45) say the comparison must not start: it
  waits on the owner's reply about the fan and on an engineering review of
  mobile thermal practice that may change the modes compared. The requests
  are in `queue/withdrawn/` with a `.why` each. Do not re-queue them until
  the brief says which modes to compare.

### Session 5 (2026-09-27 17:45 PDT)

- Why session 4 did not finish: it marked #519 ready, which was right, but
  left two things against the brief. It queued the regimen comparison the
  addenda hold back (withdrawn, above). And it built the gate from the
  hostops-inbox ask, not from the 17:31 spec, so run.log said
  `THERMAL: cool-down:` every 30 s where the spec names `COOLDOWN:` lines
  every 20 s. Both are fixed in this session; the cap stays at 360 s (see
  the gate section for why). The power addendum (17:45) arrived after it
  ended.
- Power and energy per frame go in their own PR, from branch
  `lane/thermal507-power`, so #519 (the gate hostops waits on for
  MechAssault 2) can fold without it.

### Power and J per frame (PR #523, branch `lane/thermal507-power`)

- `thermal_state.py`: the same single adb call now also reads battery
  `status`, `capacity`, `current_now`, `voltage_now`; the USB input's
  `online`, `usb_type`, `current_now`, `voltage_now`, `current_max`,
  `input_current_limit`; and `dumpsys -t 3 thermalservice`'s `Thermal
  Status`. They land in the sample as `pw`. A field that did not read is
  left out, never 0. `--power FILE LO HI` prints the window's averages, and
  the `THERMAL:` line in run.log gains `battery +x W (+ is discharging),
  usb in y W, net z W`. soak_title.sh is unchanged: it already runs the
  sampler and the summary.
- **Sign: battery W is + while discharging, - while charging.** The
  kernel's `current_now` runs the other way on both handhelds (AGENTS.md
  and docs/testing/device-power.md: below zero under the emulator), so
  battery W = -(current_now x voltage_now) / 1e12.
- Net W = battery W + USB input W, the device's draw. The USB input is
  `usb/current_now` x `usb/voltage_now` when both read. With only
  `input_current_limit`, it is limit x 5 V and `usb_from` calls it an upper
  bound.
- The average is time-weighted: linear between samples, flat outside them,
  integrated over the window. With samples 30 s apart a mean of the
  in-window samples ignores up to 30 s at each edge.
- `title_verdict.py`: a `power` block over the scored window (battery_w,
  usb_w, usb_from, net_w, scored_s, flips, j_per_frame,
  j_per_frame_battery, sign_suspect, thermal_status_max) and
  `thermal.first_pause_s` {after, by}, counted from the `start` sample.
  Reported, never judged; no bar exists yet.
- J per frame is null in a void run (the flips are not the title's) and in
  a window with a `sign_suspect` reading: the battery charging at more
  than 0.25 W with no USB input. That row cannot happen under the sign
  above, so it is the check for a kernel with the other sign.
- selftest `99-power-per-frame.sh`, 11 legs, each with the world it fails
  in. The fixture is -2 A at 4 V with 0.5 A at 5 V of USB over a 60 fps
  run: battery +8.0 W, net 10.5 W, 2340 flips in 39.0 s, 0.175 J per
  frame. A sign mutant turns the drain leg red.
- On a copy of the GTA pilot (3751184, recorded before `pw` existed):
  `first_pause_s` after 535, by 569, as the run.log line says, and
  `power.measured` false.
- **Not yet run on a device.** The `ps` and `ths` lines were parsed from a
  fake adb. The sysfs paths are the ones measured on 09-10 and 09-26; the
  `Thermal Status:` line is AOSP's dumpsys format and is unverified on
  these two devices. The first soak after the fold and a dispatcher update
  window is the check: its thermal.jsonl must carry `pw` with a battery
  current, and its verdict `power.measured` true. If `thermal_status` is
  missing there, the dumpsys line differs on this firmware.
- For the next lane: 30 s samples of an instantaneous `current_now` are
  coarse. A 240 s benchmark has about five readings in its window. Compare
  J per frame between runs of at least 5 min, and read `power.samples`.

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
