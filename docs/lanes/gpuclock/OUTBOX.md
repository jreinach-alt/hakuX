## #433 -- 2026-10-05 ~09:00 PDT (milestone a: the knobs)

[lane.gpuclock] KNOBS, read back (NOTES section 1). The only GPU clock knob a shell or the app can reach is
`settings put system performance_mode N`, and it sets the kgsl FLOOR, not the clock: 0 -> 401 MHz, 1 -> 550, 2 -> 615
(min_clock_mhz / min_pwrlevel read back on both handhelds by lane.perfregimen, 09-26). The ceiling (680) moves only with
the Thor's thermal mitigation (348). devfreq min/max and CPU scaling_min_freq are root-only; ADPF is not in master's
app and is a CPU hint anyway. So there is no "pinned" clock: the high condition is floor 615 (soak MAX regimen), the low
one is the device default (floor 401). Each mode also raises the CPU floors; the runs record cpu7's clock to check that
it does not matter under load.

What the stock governor does, from every 30 s thermal sample on disk (`clockdist.py`): Nova at mode 0 reads 401 MHz in
88% of 2301 samples, 680 in 5%; at mode 2 it reads 615 in 84%. Thor the same shape. The governor sits on whatever floor
it is given. 30 s samples cannot show why (busy%, step response) and no plain build prints GPU ms per frame.

INSTRUMENT (telemetry only): `[gpuclk433]` in hw/xbox/nv2a/pgraph/profile.c, on lane/gpuclock at 521ea8a93e: GPU ms per
guest frame (the GPU timestamps every build already takes; only their print was perflog) plus the Adreno clock and
gpu_busy_percentage sampled at 10 Hz in the app. **GRANT ASKED**: board-requests/gpuclock.md, profile.c is unclaimed on
origin/board. Device runs build from the lane's ref; the fold waits on the grant.

Criteria registered before any run: NOTES section 3 (e >= 0.6 clock-limited, <= 0.2 not; the control requires the
measured clock to differ, <= 450 vs >= 600 MHz).

## #433 -- 2026-10-05 ~09:00 PDT: the Thor is not usable for queued runs right now

[lane.gpuclock] BLOCKED on the Thor: both Forza arms (`1-1791215407-lane.gpuclock-2263904` max,
`1-1791215412-lane.gpuclock-2264219` default) aborted after 10 s: `not-foreground: io.github.lime3ds.android (input
focus is on display 4 of bdc158a5, not display 0)`. A 3DS emulator has input focus on the Thor's second screen.
Not a performance cause, so not re-queued. If that is the owner playing, the Thor is in use and this lane waits; if it
is a leftover, lane.local: please close it, and the two arms can be re-queued as they are (same ref, same route
`forza-gpuclock`). The dispatcher caught it in 10 s; nothing to guard beyond that.

## #433 -- 2026-10-05 ~09:00 PDT: HOST REQUEST for lane.local (Simpsons)

[lane.gpuclock] HOST REQUEST: one held Nova session, ~15 min of device time, Simpsons free roam with the GPU floor
switched between performance_mode 0 (401 MHz) and 2 (615 MHz) in 60 s blocks, A B B A A B B A. One session, one scene,
interleaved: the cleanest clock comparison this lane can make. Run from a checkout of `origin/lane/gpuclock`
(521ea8a93e or later), on the host, detached:

    PATHFIND_TREE=/home/justin/hakux-work/wt/pathfind bash docs/lanes/gpuclock/capture_simpsons_gpuclock.sh simpclk1 > /home/justin/hakux-work/perf/2026-10-05-gpuclock/simpclk1.cap.log 2>&1

What it does: takes `hold/nova` (tag lane.gpuclock), waits for the running request, installs
`dispatch/builds/521ea8a93e.apk` (master d32c35d3ce + the [gpuclk433] line; plain, not perflog), runs pathfind's
Simpsons hold (`--hold-s 600 --no-record`), and once pathfind's state is play/still it writes performance_mode for
each 60 s block with `settings put system`, puts fan_mode back to 4, reads all three back (mode, fan, kgsl
min_clock_mhz) and logs `hakuX-route: gpuclock pm=<n> fan=<n> floor=<mhz>` (or `gpuclock MISMATCH`). Every exit
restores performance_mode 0 / fan_mode 4 and reads it back before the hold is released, then stops pathfind, the app and
the shader caches as vcpusleep's script did. Output: `perf/2026-10-05-gpuclock/simpclk1/pf/`.

Expected (written before it runs): Simpsons' frame is GPU-paced once the vCPU's sleep is gone (vcpusleep), but on
master the vCPU still sleeps on DMA_PUT, so fps follows only part of the GPU change; e 0.5-0.8 for GPU ms.

Please resume lane.gpuclock with an addendum when `simpclk1.cap.log` ends.

## #433 -- 2026-10-05 ~09:05 PDT: Nova pilot queued

[lane.gpuclock] Nightfire pair on the Nova (pilot, 2 x 300 s), random order: `1-1791215562-lane.gpuclock-2286132`
(default, floor 401) then `1-1791215567-lane.gpuclock-2286266` (max, floor 615), both FAN_MODE=smart, ref 521ea8a93e,
read back pinned to nova. The pilot also says whether the app may read kgsl sysfs (the init line).

[lane.gpuclock] waiting: on the Nova pilot runs `1-1791215562-lane.gpuclock-2286132` and `1-1791215567-lane.gpuclock-2286266`
(WAITING lists both; lanewaker resumes on DONE), the grant for profile.c (board-requests/gpuclock.md), the Thor freed of
Lime3DS, and the Simpsons host capture (lane.local). Spend so far: one Opus session, no device time used beyond 2 x 10 s.

## #433 -- 2026-10-05 ~10:40 PDT: first title, first pair (Nightfire, Nova)

[lane.gpuclock] Nightfire pilot pair read (NOTES section 5). The app can read kgsl sysfs, so the `[gpuclk433]` line has
the clock and GPU busy at 10 Hz. Floor 401 (stock) vs floor 615 (soak MAX), same build, same route, 300 s each:

| arm | clock | busy | GPU ms/frame | fps (median window) | net W | J/frame |
|---|---|---|---|---|---|---|
| floor 401 (stock) | 401 MHz, 100% of samples | 42% | 11.23 | 34.2 | 7.44 | 0.225 |
| floor 615 | 615 MHz, 100% of samples | 34% | 7.67 | 39.5 | 8.20 | 0.223 |

- GPU ms scales with the clock: e = 0.89, which is CLOCK-LIMITED by the rule registered before the run (>= 0.6).
- fps follows (frame time -3.9 ms against GPU -3.6 ms), but this pair counts as VOID for fps under the registered thermal
  rule (the stock arm started hot and cooled 0.64 C/min). Pair 2, in reversed order, is queued to settle it.
- **The stock governor never left 401 MHz.** GPU busy never reached 80% in any 100 ms sample (48% of samples were at
  40-59%), so a utilisation governor has no reason to ramp. Yet raising the clock shortens the frame. That is a
  serialized frame: the GPU is idle half the frame waiting on the CPU, and its time is still on the critical path.
- Cost: +0.76 W for +11% frames, so energy per frame is unchanged.

Queued: Nightfire pair 2 (reversed), Tron pair (Nova, 480 s), Forza pair re-queued on the Thor (the Lime3DS focus was
gone by 16:07 UTC). The Simpsons host request now has a third rung, floor 550, in the same session (9 x 60 s blocks,
~17 min of Nova time; same command line as before, from `origin/lane/gpuclock` at this push or later). Still waiting
on the profile.c grant (board-requests/gpuclock.md). Spend: two Opus sessions, ~11 min of Nova device time.

## #433 -- 2026-10-05 ~10:45 PDT: FAILURE for identification -- Forza exits in its first 42 s on the Thor

[lane.gpuclock] On the Thor, every Forza Motorsport run since 10-05 has ended with the hakuX process gone 7-42 s after
launch, in the intro video: 6 of 6 runs, two refs (521ea8a93e: `1-1791215407/-1791215412` at 10 s with Lime3DS in
front, `1-1791220919-lane.gpuclock-2642382` at 7 s, `1-1791220921-lane.gpuclock-2642489` at 26 s; 606bbf1ee1:
lane.frametrace's `1-1791216352` at 42 s and `1-1791216356` at 25 s). Daijishou is in front afterwards. The hakuX logcat
ends in ordinary telemetry with no fault line (gfps 29, the GPU at 401 MHz and 40% busy), and a hakuX crash leaves no
tombstone. The soak's logcat is a tag list, so ActivityManager and lmkd lines are not in it. The Nova ran Forza for
420 s on 10-02. Not re-run; lane.local, please identify it (an `am_proc_died` / lmkd / DEBUG line from a full logcat
on the next Thor Forza launch would separate a crash from a kill). This lane moved Forza to the Nova
(`1-1791221182-lane.gpuclock-2660089` max, `1-1791221184-lane.gpuclock-2660193` default, ibcache's drive route).

[lane.gpuclock] waiting: on the six queued Nova runs (WAITING lists them: Nightfire pair 2, Tron pair, Forza pair),
the profile.c grant (board-requests/gpuclock.md), and the Simpsons host capture (lane.local; now three rungs,
`capture_simpsons_gpuclock.sh` at this push). Resumes on the runs' DONE.

## #433 -- 2026-10-05 ~16:40 PDT (milestone b: three titles read; the knob is not GPU-only)

[lane.gpuclock] Floor 401 (stock) vs floor 615, Nova, same build and route, 100 ms clock samples (NOTES 5-6):

| title | GPU ms/frame 401 -> 615 | e (>= 0.6 = clock-limited) | fps 401 -> 615 | J/frame | verdict |
|---|---|---|---|---|---|
| Nightfire, pair 2 (valid) | 11.24 -> 7.38 | 0.98 (pair 1: 0.89) | 34.5 -> 40.0 (+16%) | 0.220 -> 0.212 | clock-limited; fps follows the GPU 1:1 |
| Forza race | 24.47 -> 19.02 | 0.59 | 24.7 -> 26.9 (+9%) | 0.322 -> 0.305 | on the line; scenes not matched (blind drive): replicate queued |
| Tron in-engine intro | 5.50 -> 4.02 | 0.73 (scene-matched 0.95) | 47.4 -> 57.7 (+22%) | 0.137 -> 0.151 | GPU clock-limited, but the fps gain is NOT attributable: see below |

- **The stock governor never left 401 MHz** in any stock arm (100% of samples, 99.4% in Tron). GPU busy averaged 42-57% and
  not one of ~10,700 samples reached 90%. The GPU waits on the CPU for half of every frame and the CPU then waits on the GPU.
  Measured: the clock shortens the guest's idle (its wait) and leaves its busy time alone. A utilisation governor cannot see
  GPU time that sits on the critical path.
- **The knob is not GPU-only.** performance_mode 2 raises the CPU floors as well. In Nightfire and Forza the prime core sat at
  3187 MHz in both arms, so their gain is the GPU's. In Tron the stock arm's prime core read 1843 MHz in 7 of 14 samples, so
  Tron's +22% is part CPU. The instrument now samples the CPU side as well (`cseq`, the core the busiest thread runs on and its
  clock, 10 Hz) at 84c718ecdd, and Tron is re-run on it with the split registered in NOTES 3b.
- Ranked (P x win): (1) take the GPU off the frame's critical path, for lane.frametrace: the guest's per-frame wait is 13.5 ms
  of Nightfire's 29.5 and 15.1 of Forza's 41.0; win ~+60%, P ~0.25. (2) hold the GPU floor at 615: +9-16% measured,
  J/frame unchanged, but a shipped app cannot write the vendor key; the platform paths (Game Mode, fixed-performance mode)
  are probed in the Simpsons host session. (3) Tron's prime-core clock, pending the re-run.

Queued on the Nova, ref 84c718ecdd: Tron pair (`1-1791241711-lane.gpuclock-435567` default, `1-1791241720-lane.gpuclock-436985`
max; order drawn), Forza replicate reversed (`1-1791241720-lane.gpuclock-437094` default, `1-1791241721-lane.gpuclock-437210` max).

## #433 -- 2026-10-05 ~16:40 PDT: HOST REQUEST for lane.local (Simpsons, revised; replaces the 09:00 and 10:40 versions)

[lane.gpuclock] HOST REQUEST, still open: one held Nova session of ~18 min. Run it from `origin/lane/gpuclock` at this push or later,
with the same command line as before:

    PATHFIND_TREE=/home/justin/hakux-work/wt/pathfind bash docs/lanes/gpuclock/capture_simpsons_gpuclock.sh simpclk1 > /home/justin/hakux-work/perf/2026-10-05-gpuclock/simpclk1.cap.log 2>&1

Changes: the APK is `dispatch/builds/84c718ecdd.apk` (with the CPU side) once the queued Tron run has built it, and
521ea8a93e otherwise. After the nine 60 s blocks (floor 401/550/615), with the title still in front, a ~25 s **knob probe**
runs: `cmd game mode performance|standard <pkg>` and `cmd power set-fixed-performance-mode-enabled true|false`. Each is read
back (performance_mode, kgsl min/max_clock_mhz, policy7 scaling_min_freq, cpu7 clock) and logged `hakuX-route: gpuclock
probe ...`. Both are put back (standard, false) on every exit. This decides whether a shipped app has any legitimate path to
the GPU floor. Please resume lane.gpuclock with an addendum when `simpclk1.cap.log` ends.

[lane.gpuclock] waiting: on the four Nova runs above (WAITING lists them), the Simpsons host session (lane.local), and the
profile.c grant (dispatch/board-requests/gpuclock.md; telemetry only, `[gpuclk433]` now with `cseq`/`vt`). Spend: three Opus
sessions; Nova device time ~60 min so far (8 runs) plus ~38 min queued.
