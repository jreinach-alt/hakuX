# lane.gpuclock (#433): is the GPU clock-limited?

Brief: owner 2026-10-05 ~08:3x PDT, "Either the CPU or GPU is waiting on the other chip ... Let's get
that data." One controlled experiment per title: GPU ms per frame and fps against the Adreno clock,
same device, same build, same route, the clock the only thing moved.

## 1. The knobs (from the record; no new device probe needed for the floor)

Both handhelds carry the same OEM settings library (devices.sh, perfregimen NOTES 1-5).
`settings put system performance_mode N` is the only GPU clock knob a shell or the app can turn,
and it moves the **floor**, not the clock:

| performance_mode | kgsl min_clock_mhz (min_pwrlevel) | big-core policy7 floor | read back on |
|---|---|---|---|
| 0 NORMAL (device default) | 401 (4) | 1843 MHz | Nova 09-26 x4, Thor 09-26 x5 (perfregimen 5a, 5d) |
| 1 STANDARD | 550 (2) | 2477 MHz | Nova, Thor |
| 2 HIGH (soak MAX regimen) | 615 (1) | 3187 MHz | Nova, Thor |

The actuator is the vendor perf service (`pservice: cpu_init ... cpugpumode=`), which writes kgsl
`min_pwrlevel`. `max_clock_mhz` is not moved by any mode: the ceiling is 680 MHz on both, except
when the Thor's thermal mitigation lowers it to 348 (162 of 2063 Thor samples). devfreq
`min_freq`/`max_freq` and CPU `scaling_min_freq` are root-only (perfregimen 2). So:

- **No pin.** A floor is all a user or the app can set. The governor (msm-adreno-tz) may still run
  above it, up to 680. "Pinned high" here means floor 615; there is no pinned-low knob, the device
  default (floor 401) is the low end.
- **The knob is not GPU-only.** Each mode also raises the CPU floors. Under game load the vCPU's
  core already sits at its maximum (near30: cpu7 at 3187 on every run), so the CPU floor should
  not move the vCPU; the per-run CPU clocks are recorded so that is checked, not assumed.
- **Through the queue** the modes are `--env PERF_REGIMEN=default` (0/4) and `max` (2, fan 5 on
  the Nova, 4 on the Thor). Mode 1 (floor 550) has no regimen; a third rung needs either a
  `standard` regimen in soak_title.sh (not this lane's file) or the governor's own excursions.
- ADPF / PerformanceHintManager: not in master's app (no APerformanceHint call anywhere outside
  docs). #544's probe (`1-1790572033-adpf-2928981`, `HAKUX_ADPF=probe`) found the HAL ignores the
  hints (vcpuplan NOTES); ADPF hints are CPU uclamp hints in any case. Not a GPU knob.

### What the stock governor already does (30 s samples, every run on disk; `clockdist.py 3000`)

| device, mode | runs | samples | time at each step (share of 30 s samples) | ceiling read |
|---|---|---|---|---|
| Nova pm=0 | 97 | 2301 | **401: 88.4%**, 475: 2.4%, 550: 2.3%, 615: 1.5%, 680: 5.4% | 680 |
| Nova pm=2 | 315 | 3276 | 401: 6.1%, **615: 84.1%**, 680: 9.7% | 680 |
| Thor pm=0 | 43 | 521 | 348: 11.9%, **401: 77.7%**, 475: 6.3%, 550: 2.5%, 615: 1.2%, 680: 0.4% | 680 (348 when hot) |
| Thor pm=2 | 178 | 1542 | 348: 6.5%, 401: 7.9%, **615: 81.3%**, 680: 4.3% | 680 (348 when hot) |

All kinds of runs pooled (menus, loads, gameplay). The governor sits on whatever floor it is
given 78-88% of the time and rarely reaches 680. The 401 samples under pm=2 are the seconds
before the regimen took hold or after it was restored. Tron alone (`survey.py tron`): 13 plain runs at
pm=0 read 401 on every gameplay sample; at pm=2 every sample is 615 or 680.

A 30 s sample cannot show the governor's step response or the GPU's busy share under it, and
no build prints GPU ms per frame outside perflog. Hence the instrument (section 2).

## 2. The instrument (telemetry only): `[gpuclk433]`, hw/xbox/nv2a/pgraph/profile.c

One always-on line at the hakuX-pace cadence (every 60 guest frames):

    [gpuclk433] f=<frame> frames=<n> fr=<n with GPU time> gms=<GPU ms/frame> grn=<render-pass ms/frame>
                floor=<min_clock_mhz> ceil=<max_clock_mhz> ns=<samples> dr=<dropped> seq=<mhz>/<busy>,...

- `gms` is the sum of the command buffers' GPU timestamps over the window (gpu_ts_readback, which
  runs in every build) divided by the frames flipped. Not the perflog EMA.
- `seq` is every 100 ms sample of kgsl `gpuclk` and `gpu_busy_percentage` since the last line,
  taken by a thread in the app. busy is kgsl's last accounting window, the governor's own input.
- `init` line once: the period, floor, ceiling, devfreq governor, and the errno of any node the
  app may not read (that field then reads -1/0, never a plausible value).

Cost: one thread waking at 10 Hz for two preads; one snprintf per 60 frames. Type-checked with the
dispatcher's NDK compile command at NV2A_PERF_LOG 1 and 0 (`synchk.py`).

Whether the app's SELinux context may read kgsl sysfs is unknown until the first run: the
adb shell can (thermal.jsonl), the app has never tried. If it cannot, the init line says so and
the ladder still has `gms` plus thermal.jsonl's 30 s clock.

### 2b. The CPU side (added in attempt 3, same file, telemetry only)

`cseq=c7/c3/p,...`, one entry per `seq` sample: cpu7's and cpu3's `scaling_cur_freq` (MHz) and
the core the busiest thread last ran on (field 39 of its `/proc/self/task/<tid>/stat`). `vt=tid/comm`
names that thread: the one with the most utime+stime over the previous line's window, re-chosen at
every line (the vCPU, ~97% of a core). The app pins nothing (no `pinned to` line in any run's
logcat; XEMU_OPT_THREAD_AFFINITY is off), so the vCPU's core is read, not assumed. Reader:
`gpuclock.py` prints the thread, its core shares, its core's clock distribution, and a `vmhz`
TSV column; `fixture.py` plants a 25/25/50 split (core 7 at 1843 / core 4 at 2803 / core 7 at
3187) and the reader returns it exactly. Type-checked at NV2A_PERF_LOG 1 and 0 (`synchk.py`).

## 3. The experiment, registered before any run

Per title: arms at `PERF_REGIMEN=default` (floor 401) and `PERF_REGIMEN=max` (floor 615), same
device, same ref (this branch, the instrument), same route, the fan mode equal across the arms,
order randomised and then interleaved (A B B A when there are four).

**The control (an inert pin is not a result):** an arm counts only if its gameplay-window mean
clock from `seq` (thermal.jsonl's gpuclk if seq does not read) is <= 450 MHz in a default arm and
>= 600 MHz in a max arm. If the default arm's governor runs at 600+ by itself, the two arms did not
differ and the pair says nothing about the clock.

**Validity:** a thermal pause (cpu3-7) or a ceiling under 680 inside the window voids the arm.
Start temperature (xo / hottest zone) and battery state are recorded per arm. A pair whose arms
start more than 5 C apart, or whose in-window heating rates differ by more than 0.5 C/min, is
void for fps (the GPU ms reading stands: timestamps do not care about temperature unless the clock
moved, and the clock is measured).

**Answer a, clock-limited or not.** Elasticity e = ln(gms_low / gms_high) / ln(MHz_high / MHz_low),
from window means. Per window, a fit of gms = c + k/MHz over every gameplay window of both arms,
residual reported. Written in advance:
- **clock-limited:** e >= 0.6 (GPU ms moves at least 60% of the clock ratio). From 401 to 615 MHz
  that is gms_high <= 0.79 x gms_low.
- **not GPU-execution-bound by clock:** e <= 0.2 (gms_high >= 0.93 x gms_low).
- between: partly clock-limited (a memory-bound share); the fit's constant c says how much.

**Answer b, fps.** The frame follows the GPU if F_low - F_high >= 0.6 x (gms_low - gms_high) (F =
1000/fps over the same windows). If not, the pacer is named from the vCPU split (decompose.py's
v_run / v_blk, guest idle, renderer idle).

**Answer c, the stock governor.** From the default arms' `seq`: time at each step over the window;
mean busy%; the share of samples at busy >= 90% while the clock is under the ceiling; and the step
response: after a sample at busy >= 90%, how many 100 ms samples until the clock rises a step.
"A governor that holds 401 while the GPU runs 90% busy" is that share being large.

Prior (written now): Forza and Simpsons, whose renderer waits on GPU fences (vcpu60, vcpusleep),
e 0.5-0.8 and fps following partly; Tron, whose vCPU is the long pole (near30), e high but fps
flat; Nightfire unknown. The governor holds the floor because the GPU idles while the CPU works
(serialized frames), so busy% stays under its up-threshold: P 0.6 that busy >= 90% at the floor is
under 10% of samples.

### 3b. Registered before the attempt-3 runs (Tron and Forza on the cseq build)

**Tron, the CPU confound.** Scene-match the pair (align.py lag), then split the matched bins by the
stock arm's vCPU core clock from `cseq` (`vmhz` >= 3100: core at max; < 2500: core low). The max
arm's core is expected at 3187 throughout (if not, the split is void and says so).
- In core-at-max bins only the GPU floor differs. **The GPU explains Tron's fps** if dF/dGPU there
  is <= 1.3 (registered band: the frame follows the GPU about 1:1, as in Nightfire).
- **The CPU floor explains the excess** if dF/dGPU in core-at-max bins is <= 1.3 AND in core-low
  bins >= 2.
- **Neither** if dF/dGPU in core-at-max bins stays >= 2: the excess then comes from something the
  floor moves other than either clock we read (the DDR vote that follows the GPU level, or a sync
  wait whose latency is not GPU execution time), and it is named as unexplained.
- Fewer than 15 matched bins in either class: no verdict on that class.

**Forza, the replicate.** Reversed order (default first). Same rule as section 3; the two pairs'
e are reported side by side, not pooled, and the 0.59 of pair 1 is called clock-limited only if
pair 2's e is >= 0.6 as well. cseq checks that cpu7 is at its maximum in both arms (pair 1's 30 s
samples: 13/14 and 15/15).

## 4. Device plan

- Thor (superseded 10-05 10:45, see Log): Forza Motorsport (the Thor's copy), `forza.drive.route` with `mark` instead of `find`
  (`drive forza 400 mark`: drives and marks gameplay at 6 s of confirmed play). <= 480 s per run,
  cold slot by lane.local's hakux-thor-coldconfirm.
- Nova: Nightfire (`nightfire.route`), Tron (near30's `tron-newgame.route`), queued in pathfind's
  gaps. Simpsons has no route: host-run under a pathfind hold (lane.local), as vcpusleep did.

## 5. Results

### Nightfire, Nova, pair 1 (pilot; default then max, 300 s each, ref 521ea8a93e)

`gpuclock.py --pair 1-1791215562-lane.gpuclock-2286132 1-1791215567-lane.gpuclock-2286266`:

| arm | windows | MHz (100 ms samples) | busy % | gms | grn | fps (median window) | fps (frames/time) | net W | J/frame |
|---|---|---|---|---|---|---|---|---|---|
| default (floor 401) | 151 | 401: 100% of 2735 | 42 | 11.23 | 9.93 | 34.2 | 33.1 | 7.44 | 0.225 |
| max (floor 615) | 166 | 615: 100% of 2674 | 34 | 7.67 | 6.54 | 39.5 | 36.9 | 8.20 | 0.223 |

- The app reads kgsl sysfs: init `err=none`, governor msm-adreno-tz, ceiling 680. The control
  holds: the clock moved exactly as set, and never left the floor in either arm.
- **a.** e = 0.89 (gms x0.683 for MHz x1.534): CLOCK-LIMITED by the registered rule. The window fit
  (c 1.47 ms, k 3567) has R^2 0.09, RMS 4.91 ms: across windows the scene changes gms far more
  than the clock does (the prologue's sections), so the per-window fit is not the reading; the
  elasticity on medians is. The ladder (three levels, section 3) is the fit with a residual that
  means something.
- **b.** F 29.2 -> 25.3 ms against dGPU 3.6 ms: fps FOLLOWS (dF/dG 1.08). But **fps VOID** by the
  registered validity rule: the hottest zone fell 0.64 C/min in the default arm (it started at
  94.7 C after the previous run) and was flat in the max arm. xo rose 1.6 and 2.1 C in each.
  Pair 2 (reversed order) is queued to settle it. Within each run, F does not track gms across
  windows (r -0.09 and -0.23), so the frame is not simply CPU + GPU in series scene by scene.
- **c.** The stock governor at floor 401: **401 MHz in 100% of 2735 samples**. GPU busy per 100 ms
  sample: 0-19% 33%, 20-39% 18%, 40-59% 48%, 60-79% 0.6%, >= 80% 0.0%. No sample reached 90, so the
  step response has nothing to measure: the governor never had a reason to ramp. The GPU is idle
  more than half of every frame and still, adding clock shortens the frame. That is what a
  serialized frame looks like (the GPU waits on the CPU's submission, the CPU waits on the GPU's
  fence): utilisation stays at ~40%, under the governor's up-threshold, while GPU time sits on the
  critical path. A utilisation governor cannot see that.
- Cost: +0.76 W net (+10%) for +11% frames/time: J/frame unchanged (x0.99). Battery 80%, status
  Charging in the default arm (net draw 7.4 W exceeds the USB input, so the battery discharged
  anyway: +0.91 W and +1.67 W).

### Pairs 2-4 (Nova, ref 521ea8a93e; `out/*.out` is each reader output as printed)

`gpuclock.py --pair LOW HIGH` medians (out/<pair>.out), and `align.py` (new): both arms' windows in
2 s bins from the mark, the high arm shifted by the lag that best correlates the two log-gms series,
then per-bin ratios. Scripted content (a cutscene, a blind route) replays at the same pace in both
arms, so once the lag is found equal time is the same scene; a correlation under 0.5 means the arms
did not replay the same content. `align_decomp.py` puts near30's `decompose.py` vCPU split through
the same lag (out/<pair>.adecomp.out).

| title (content) | pair, order | clock (100 ms samples) | gms low -> high | e (medians / scene-matched, corr) | F low -> high | dF / dGPU | validity | J/frame |
|---|---|---|---|---|---|---|---|---|
| Nightfire (prologue), pair 1 | default, max | 401 100% / 615 100% | 11.23 -> 7.67 | 0.89 / - | 29.2 -> 25.3 | 1.08 | fps void (stock arm cooled 0.64 C/min) | 0.225 -> 0.223 |
| Nightfire, pair 2 | max, default | 401 100% / 615 100% | 11.24 -> 7.38 | **0.98 / 0.76 (0.88)** | 29.0 -> 25.0 | **1.03** (matched 0.84) | ok | 0.220 -> 0.212 |
| Tron (in-engine intro, near30's path) | default, max | 401 99.4% / 615 100% | 5.50 -> 4.02 | 0.73 / 0.95 (0.86) | 21.1 -> 17.3 | 2.5 (matched 2.9) | fps void (1.97 vs 5.37 C/min); **cpu7 confound** | 0.137 -> 0.151 |
| Forza (race, blind drive) | max, default (3.5 h apart) | 401 100% / 615 100% | 24.47 -> 19.02 | **0.59** / 0.66 (0.27: not matched) | 40.5 -> 37.2 | 0.61 | ok | 0.322 -> 0.305 |

Frames checked: Forza's window is the race in both arms (8th place, lap 1/2) but the blind drive
leaves the car in different places, so the scenes differ (corr 0.27; per 30 s segment e runs from
-0.26 to 1.15). Tron's window is the in-engine intro, not play: the default arm ended in a loading
screen, the max arm reached the "basic training" prompt 256 s after the mark. near30's 615-vs-401
reading was the same intro.

**Where the clock goes in the frame (scene-matched vCPU split).** In Nightfire and Forza the vCPU
thread is on-CPU ~97% of the frame either way; the guest's *busy* time does not move (Nightfire
15.0 -> 18.1 ms, Forza 25.2 -> 25.9) and its *idle*, woken by the timer, shrinks (Nightfire 13.5 ->
6.9 ms, Forza 15.1 -> 11.6). The guest finishes its CPU work and then waits for the GPU; a faster
GPU shortens the wait. That is the serialized frame, measured: F = guest CPU work + wait on GPU.
Nightfire's segment 90-150 s (GPU 0.6 ms/frame, busy 5%: a scene with almost no GPU work) is the
built-in check: there the clock should not help and does not (F 34 -> 38-40 ms, guest busy = F).

**The knob is not GPU-only, and in Tron that decides it.** `cpu7share.py` (new; out/cpu7share.out),
from thermal.jsonl's 30 s samples:

| arm | cpu7 (prime core) at 3187 | cpu3 (mid cluster) at 2803 |
|---|---|---|
| Nightfire default x2 | 9/9, 9/9 | 2/9, 5/9 |
| Nightfire max x2 | 9/9, 9/9 | 9/9, 9/9 |
| Tron default | **7/14** (the rest 1843) | 3/14 |
| Tron max | 15/15 | 15/15 |
| Forza default | 13/14 | 3/14 |
| Forza max | 15/15 | 15/15 |

In Nightfire and Forza the prime core sits at its maximum in both arms, so their dF is the GPU's
(and dF <= dGPU, so the mid cluster's floor adds nothing visible). In Tron the guest never idles
(gidle 0), the frame is the vCPU's, and the stock arm's prime core read 1843 MHz in half its
samples: the knob moved the vCPU's clock too. Tron's v_run fell 24.8 -> 18.4 ms and v_blk 6.7 ->
3.3 ms (matched); dF is 2.9x dGPU. Tron's fps gain cannot be given to the GPU from these runs. The
30 s samples cannot say which bins ran at 1843, so the instrument now samples the CPU side too
(section 2b) and Tron is re-run on it.

### What a third rung needs

performance_mode 1 (floor 550) has no PERF_REGIMEN, so a queued soak cannot reach it. The Simpsons
host session can: `capture_simpsons_gpuclock.sh` now switches 0 2 1 / 1 0 2 / 2 1 0 (9 x 60 s,
each mode once in each third), and `gpuclock.py --blocks` adds a ladder section: the three
levels' medians, each step's e, and gms = c + k/MHz fitted on the three medians with its residual
(fixture `ladder` leg: planted c 4 / k 6000, read c 3.81 / k 6087, residual 0.07 ms; the 550 -> 615
step is short, x1.12, so its e carries +-0.1 from 0.3 ms of noise).

## 6. The answers so far (attempt 3; Simpsons and the Tron/Forza re-runs pending)

**a. GPU ms vs MHz: clock-limited in every title measured.** e (window medians, floor 401 -> 615):
Nightfire 0.89 and 0.98, Forza 0.59, Tron 0.73 (scene-matched 0.95). The rule set before the
runs is e >= 0.6; Forza sits on the line with scenes unmatched (replicate queued). The fit
gms = c + k/MHz over windows: Nightfire c 1.40 ms / k 3508, Forza c 7.38 / k 6598, Tron c 0.46 /
k 2491. Its R^2 is 0.09-0.27 (RMS 2.9-4.8 ms): across windows the scene moves gms far more than
the clock does, so the per-window fit does not read the clock. The scene-matched per-bin ratios
do (Nightfire: the high arm's gms is lower in 92% of matched bins; Tron 95%). The clock-scaled
share of GPU time at 401 MHz is 86% (Nightfire), 69% (Forza) and 93% (Tron). Forza's constant
(7.4 ms) is the part that does not scale with the core clock: memory-bound work.

**b. fps vs MHz: the frame follows the GPU where the vCPU's clock stayed put.** Nightfire (pair 2,
valid): F 29.0 -> 25.0 ms against GPU 11.24 -> 7.38 (dF/dG 1.03; matched 0.84), fps +16%. Forza:
F 40.5 -> 37.2 against GPU 24.5 -> 19.0 (0.61), fps +9%. In both, the clock shortens the guest's
timer-woken idle and leaves its busy time alone. The frame is CPU work plus a wait for the GPU, in
series. Tron: fps +22% with dF 2.9x dGPU and the prime core's clock moved too: not attributable yet
(3b).

**c. The stock governor during play: it never leaves the floor.** 401 MHz in 100% (Nightfire x2,
Forza) and 99.4% (Tron) of the 100 ms samples. Mean GPU busy is 42% / 57% / 43%. Not one sample
reached 90% (0 of ~10,700 stock-arm samples), so the step response has nothing to measure. This
is not "a governor that holds 401 while the GPU runs 90% busy". The GPU is idle about half of
every frame because it waits for the CPU, and the CPU then waits for it. Utilisation stays under
the up-threshold while GPU time sits on the critical path. A utilisation governor cannot see that.
The CPU governor did the same thing to Tron's prime core (1843 MHz in 7 of 14 samples).

**Cost.** J/frame at floor 615 vs 401: Nightfire 0.220 -> 0.212 and 0.225 -> 0.223, Forza 0.322 ->
0.305 (net +0.07-0.76 W for more frames), Tron 0.137 -> 0.151 (+11%, CPU floor raised too).
xo rose 1.8-2.4 C per run in either condition; no thermal pause, no ceiling cut on the Nova.

### Ranked next steps (P x win, from these numbers)

1. **Take the GPU off the frame's critical path** (hand to lane.frametrace): the guest waits for
   the GPU every frame, 13.5 ms of Nightfire's 29.5 ms and 15.1 of Forza's 41.0 at 401 MHz (guest
   idle, timer-woken). Win if the wait were overlapped with the next frame's CPU work: Nightfire
   F -> ~15-18 ms, Forza -> ~25 ms, about +60% fps. P ~0.25: what the guest waits on (which
   fence or flag it reads) is not identified by these runs, and an emulator can report GPU
   completion early only where the guest does not read what the GPU wrote. Expected ~+15%.
2. **Hold the GPU floor at 615 during play.** Measured win +16% (Nightfire), +9% (Forza), with
   J/frame unchanged or lower. P that the shipped app can do it legitimately: the only knob found is
   `performance_mode`, a vendor key in Settings.System. Since API 23 an app may write only
   public System keys, so the app cannot set it. The Simpsons host session now probes the
   platform's own paths, Game Mode (`cmd game mode performance`) and fixed-performance mode. P
   ~0.3 that one of them moves the kgsl floor. Expected ~+4%. A user can turn the device's
   performance mode on today, at no cost and with no shipped change.
3. **Tron: the prime core's clock** (pending 3b). If the cseq re-run gives the excess to the CPU
   floor, Tron's v_run fell 26% when the core was held at 3187. That is the CPU governor doing to
   the vCPU what the GPU governor does to the GPU.

## Log

- 10-05: knobs from the record (section 1); natural experiment on disk (`survey.py`,
  `clockdist.py`); instrument written and type-checked; grant asked for profile.c.
- 10-05 ~08:51: Thor Forza pair (`1-1791215407-...-2263904` max, `1-1791215412-...-2264219` default)
  both ABORTED at 10 s: `not-foreground: io.github.lime3ds.android` (input focus on display 4, the
  Thor's second screen). Non-performance cause, named; not re-queued until the Thor is free.
- 10-05 ~09:05: Nova Nightfire pilot pair queued, order drawn at random (default then max), both
  FAN_MODE=smart, 300 s (mark at ~85 s: ~215 s of play). Simpsons: host request to lane.local
  (`capture_simpsons_gpuclock.sh`, in-session 60 s blocks A B B A A B B A). Tron route ready
  (`tron-gpuclock.route`, memfast's text). Reader `gpuclock.py` passes its known-answer fixture
  (`fixture.py`: e 0.76 vs 0.75 planted; fit c 3.8 / k 6100 vs 4 / 6000; the blocks leg drops a
  planted menu stretch, residual 0.29 = the planted noise).
- 10-05 ~10:35 PDT, **attempt 2**. Attempt 1 did not fail: it ended correctly in a waiting state
  (WAITING named the two Nova pilot runs; the grant, the Thor focus problem and the Simpsons host
  capture were outside the session). The handback resumed the lane when the pilot pair was DONE.
  Pilot read (section 5): Nightfire clock-limited, e 0.89. Pilot verdict written to
  `pilots/lane.gpuclock.ok`. Queued: Nightfire pair 2 reversed (`1-1791220908-...-2641880` max,
  `1-1791220912-...-2642033` default), Tron pair (`1-1791220914-...-2642143` default,
  `1-1791220916-...-2642242` max, 480 s, Nova), Forza pair re-queued on the Thor
  (`1-1791220919-...-2642382` max, `1-1791220921-...-2642489` default, 480 s): the Lime3DS focus
  was gone by 16:07 UTC (lane.frametrace's Forza runs reached display 0), though both of those
  exited early with Daijishou in front (42 s, 25 s), cause not identified. Order drawn at random
  (Tron default first, Forza max first). Reader: J/frame over the window
  (thermal_state.power_over); three-level ladder for the Simpsons blocks. Grant for profile.c
  still unanswered; Simpsons host capture not yet run.
- 10-05 ~10:45 PDT: **Forza on the Thor is out.** The re-queued pair died like the first:
  `-2642382` (max) at 7 s ("hakuX is not the focused app", route-died) and `-2642489` (default) at
  26 s ("xemu is gone ... not-foreground: com.magneticchen.daijishou"), both in the intro video.
  Every Thor Forza run since 10-05 has ended this way: 6 of 6, refs 521ea8a93e and 606bbf1ee1
  (lane.frametrace), 7-42 s, no fault line in the hakuX tags; the logcat ends in ordinary
  telemetry (`[gpuclk433]` at 401/40%, gfps 29). A process exit with no tombstone, Thor only. The
  hakuX tags cannot show the cause (the logcat spec is a tag list); sent to lane.local for
  identification (OUTBOX), not re-run. Forza moved to the Nova on ibcache's blind drive route
  (`forza-nova-gpuclock.route`; drive.py stuck on the Nova's menus on 10-03): `-2660089` (max)
  then `-2660193` (default), order drawn at random.
- 10-05 ~16:00 PDT, **attempt 3**. Why attempt 2 did not finish: it did not fail; it ended,
  correctly, in a waiting state on six queued Nova runs (WAITING), the profile.c grant and the
  Simpsons host capture, all outside the session. The handback resumed the lane when the last run
  (Forza default, `-2660193`, which waited ~3.5 h behind pathfind) was DONE. Merged origin/master
  (8522288a77). Read pairs 2-4 (section 5): Nightfire replicates (e 0.98, fps follows 1:1, valid);
  Forza e 0.59 with scenes unmatched; Tron e 0.73-0.95 but its fps gain is confounded with the
  prime core's clock (stock arm at 1843 MHz in 7 of 14 samples). New: `align.py`,
  `align_decomp.py`, `cpu7share.py`; the instrument samples the CPU side (2b). Grant for
  profile.c: still no answer (no row change on origin/board). Simpsons host capture: not run (no
  `perf/2026-10-05-gpuclock/`).
