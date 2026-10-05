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

## 4. Device plan

- Thor: Forza Motorsport (the Thor's copy), `forza.drive.route` with `mark` instead of `find`
  (`drive forza 400 mark`: drives and marks gameplay at 6 s of confirmed play). <= 480 s per run,
  cold slot by lane.local's hakux-thor-coldconfirm.
- Nova: Nightfire (`nightfire.route`), Tron (near30's `tron-newgame.route`), queued in pathfind's
  gaps. Simpsons has no route: host-run under a pathfind hold (lane.local), as vcpusleep did.

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
