# lane.adpf (#544)

ADPF Performance Hint sessions for the vCPU and PFIFO/render threads, opt-in
behind `HAKUX_ADPF`. Base: master @ 19d39f0a25. Module at 8a64c7d41e.

## What is built (8a64c7d41e)

`hw/xbox/adpf.c`, Android only (stubs elsewhere). `HAKUX_ADPF`:

| value | what runs |
|---|---|
| unset / `0` | nothing (default) |
| `log` | per-flip thread CPU times, uclamp, CPU placement and policy freqs logged; no session. The A arm. |
| `1` | two sessions, reported once per guest flip. The B arm. |
| `probe` | no emulator session; a probe thread for the pilot (below) |

- API 33 symbols by `dlopen("libandroid.so")` + `dlsym` (minSdk 29).
- Session 0 = the vCPU thread (registered in `mttcg_cpu_thread_fn`).
  Session 1 = PFIFO + the Vulkan render thread (both registered in
  `pfifo_thread` after `pgraph_init_thread`; the render tid comes from the
  renderer's `QemuThread` via `pthread_gettid_np`, because render_thread.c
  is not this lane's file). A session is created at the first flip after all
  its threads exist (no `setThreads` below API 34).
- Hook: `pfifo.c`, after the puller runs `NV097_FLIP_STALL`.
- Target = k x the guest VBLANK period (`nv2a_get_vblank_period_ns`), k = the
  fewest VBLANKs between flips over the last 5 windows of 2 s, clamped 1-4.
  A 30-capped title keeps k = 2; one that sometimes makes 60 gets k = 1.
  `HAKUX_ADPF_TARGET_US` fixes it.
- Actual = each session's thread CPU time since the previous flip
  (`pthread_getcpuclockid`); session 1 reports the larger of its two threads'
  deltas, since they run side by side (a sum would overstate the critical
  path). Never the flip interval.
- `[adpf]` line every 2 s (tag hakuX, WARN): mode, k, target, per session
  st/n/mean_us/max_us/err/um (uclamp.min from sched_getattr), tid@cpu per
  thread (`!` = its CPU clock no longer reads: dead), policy cur/min MHz.

### Why the pilot is a probe thread, not the emulator's sessions

The emulator's own threads confound the question: their load moves clocks
whatever the hint says. The probe thread runs a fixed light load (3 ms spin
per 16.67 ms) in its own session and cycles 10 s phases: none (no report),
low (reports target/4), high (reports 4 x target). If the HAL acts on hints,
`high` differs from `none` and `low` in the spin's iterations per us (a
faster clock or a bigger core), in the CPUs it ran on, in its uclamp.min, or
in the policies' min/cur MHz. Phases alternate over the whole soak, so the
title's own load is common to all three.

## What a lane cannot see

`dumpsys performance_hint` is not reachable through the dispatch queue:
soak_title.sh captures no dumpsys, and an app cannot run it. The session leg
is therefore read from the app's own log: `[adpf] session N: created
tids=...` (the create call returned a session), `err=0` on every window (the
service accepted each report), the tids matching the `hakuX-threads` role
lines, and no `!` (every thread alive). A host session can confirm with
dumpsys; that is not a lane's tool.

## Session 1 (2026-09-28)

- Draft PR #545. Type-checked adpf.c, pfifo.c, nv2a.c, mttcg.c with the NDK
  clang line from the shared tree's compile database (`tcheck.py` here): clean
  with -Wall.
- Pilot queued: `1-1790589652-adpf-2928981`, Thor, Crimson Skies, 240 s,
  `HAKUX_ADPF=probe PERF_REGIMEN=default HAKUX_IDLE_HALT=1`, ref 8a64c7d41e.
  ~28 critical-path requests were ahead of it, and the Thor was in a devwatch
  cool-down.
- No prediction registered yet, on purpose: committing one queues the arms,
  and the brief says to stop if the HAL ignores hints.

### Next

1. Read the pilot's `[adpf-probe]` lines: high vs none/low on ipus, cpu,
   um, p3/p7 cur/min. If there is no difference beyond phase-to-phase noise,
   the HAL ignores hints: write that on #544 and end the lane.
2. If it acts: register `adpf-pixels.json` (pgraph, unset vs `1`) and
   `adpf-<title>.json` fps/energy predictions (A `HAKUX_ADPF=log`, B
   `HAKUX_ADPF=1`, both `HAKUX_IDLE_HALT=1 PERF_REGIMEN=default`, >= 600 s,
   Thor: Crimson Skies content-capped; GTA San Andreas CPU-bound (the review's
   GTA 25 -> 3.6 fps throttle; its own busy-wait is 11.8% of JIT samples, so
   its vCPU session will read busy whatever the hint does). Not Blinx: the
   guest idles 52-66% of wall time there (idlehalt), so it is not CPU-bound.

### State at the end of session 1

Waiting on dispatch request `1-1790589652-adpf-2928981`; the waiting comment
is posted on #545. The PR stays a draft until the pilot is read and, if the
HAL acts on hints, the arms are read.

## Session 2 (2026-09-28, attempt 2): the pilot says the HAL ignores hints

### Why attempt 1 did not finish

It ended correctly on a `waiting:` for the pilot, a dispatch request outside
the session. Hostops then renamed the request to `1-1790572033-adpf-2928981`
to move it up the Thor queue and pushed an nv2a index regen (4c910092a3) onto
the branch. The pilot finished at 03:47 PDT; this resume reads it. Nothing
was lost.

### The pilot

`1-1790572033-adpf-2928981`: Thor, Crimson Skies, 240 s, ref 8a64c7d41e,
apk 02eb07c3bcdd, `HAKUX_ADPF=probe PERF_REGIMEN=default HAKUX_IDLE_HALT=1`
(perf_mode 0, fan_mode 4 per perf_regimen.json). 24 phases of 10 s, 8 of
each. Summary by `probe_summary.py` (this directory):

| phase | reports | ipus mean [range] | CPU share cpu0..7 (%) | uclamp.min | err | p3 cur MHz | p7 cur MHz | p3/p7 min |
|---|---|---|---|---|---|---|---|---|
| none | none | 297.8 [268.3-342.9] | 0/0/0/31/31/17/21/0 | 0 | 0 | 1831 | 2898 | 0/0 |
| low | target/4 | 292.8 [265.5-321.8] | 0/0/0/34/32/13/21/0 | 0 | 0 | 1774 | 2914 | 0/0 |
| high | 4 x target | 285.1 [266.8-305.0] | 0/0/0/32/33/25/10/0 | 0 | 0 | 1739 | 2948 | 0/0 |

`high - none` spin rate per cycle: -37.9 -7.0 -8.2 +8.2 -3.0 -49.1 -2.7
-1.5 (mean -12.7; higher in 1 of 8 cycles). The whole soak drifts down
(343 -> 268 over 4 min), which is the device warming, common to all phases.

Read against the stated test (a hint that acts makes `high` differ from
`none` and `low` in speed, placement, uclamp.min or the policy floors):

- **API: reachable.** `manager=ok`, `preferred_rate_ns=16666666`, the probe
  session created (`session=ok`), and `err=0` on all ~9600 reports. The
  service accepts the session and every report.
- **Speed: no.** The probe is not faster under `high`; if anything slower,
  inside the phase-to-phase noise.
- **uclamp.min: no.** 0 on the probe thread in every phase (readable: -1
  would mean it was not).
- **Floors: no.** scaling_min_freq on policy0/3/7 reads below 1 MHz in every
  phase; a QTI perf lock through cpufreq QoS would raise it.
- **cur MHz: no.** p3 is lower under `high`, p7 moves 50 MHz inside a
  2393-3187 range.
- **Placement: no promotion.** The probe never ran on cpu7 in any phase.
  cpu6 carries fewer of its periods under `high` (10% vs 21%), but cpu3-6
  are one policy (p3), so that is not a faster core.

**Result: on the Thor at device defaults, the QTI Performance Hint HAL
accepts sessions and reports and does nothing with them.** Per the brief,
the lane stops here: no prediction, no arms.

### What the next lane should not repeat

- Do not run fps/energy arms of `HAKUX_ADPF=1` on the Thor: with no HAL
  action they measure only the reporting overhead.
- The one unexplained reading: scaling_min_freq reads 0 (below 1000 kHz) on
  all three policies at defaults. It did not change between phases, which is
  all this test needs, but a host session with adb could confirm the raw
  value and run `dumpsys performance_hint` during a probe to see whether the
  service forwards sessions to a HAL at all.
- The Nova (a different SoC) is untested. `HAKUX_ADPF=probe` is the
  instrument: one 240 s soak, then `probe_summary.py <id>`.
- A future firmware or Android 14+ HAL could change this. The probe answers
  that in four minutes.

### The PR

The module stays opt-in and default off; outside Android it is a no-op.
The PR is marked ready with this result. The audit decides whether to fold
it as the probe instrument (the reason to keep it) or close it.
