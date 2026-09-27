# lane.flip474 -- the GPU timestamp period, measured at start-up (#474, Addendum 5)

This is its own PR (#504), off master, because the addendum asked for one.
The lane's investigation is in `NOTES.md`; sections 16 and 17 are on this
PR too.

**Status, 2026-09-27 22:30Z: the first cut was wrong on the Thor, and the
change on this branch is a second cut.** The first cut (`902cf1ab53`) read
4636.591 ns per tick at start-up on the Thor, 89 times the true period. The
second cut (`36d2a6faaf`, merged head `253148451f`) has not run on a device
yet.

## Why the sessions before this one did not finish

- The session that built the first cut ended on a wait, correctly, for four
  device requests and the pgraph arm.
- The session before that had finished its brief; Addendum 5 arrived one
  minute after it ended.

## The change (`hw/xbox/nv2a/pgraph/vk/renderer.c`, `gpu_ts_calibrate`)

- **What was wrong.** `gpu_ts_period_ns` came from
  `limits.timestampPeriod`. On the Nova that is 33.11 ns (30.2 MHz), while
  `o4clock.py` fitted the ticks at 52.083 ns (19.200 MHz) against the CPU
  clock, under load (NOTES.md section 15). So every `hakuX-phase` GPU, R and
  X figure from the Nova read 0.636 of the true value.
- **The measurement (second cut).** It runs at init, in perflog builds only,
  before any guest work.
  - Each sample records one `vkCmdWriteTimestamp` on the aux command buffer
    (`pgraph_vk_begin/end_single_time_commands`), which submits and waits on
    its fence. The CPU clock is read before and after. The tick was written
    inside that window, so the sample's time is the window's middle.
  - Samples are taken back to back for about 120 ms. Windows over four times
    the narrowest are dropped.
  - The second half of the span sleeps 300 us after every sample, and the
    first half does not.
  - The period is the least-squares slope of CPU time over ticks.
- **The checks it makes on itself.** Any failure keeps the reported period
  and logs the reason.
  - The ticks only rise.
  - The two halves' slopes agree within 2%. A counter that stops in a short
    idle gap gives the gapped half a longer period.
  - No kept sample is further from the line than 2% of the span.
- **The choice.** The measured period is used only if it also differs from
  the reported one by more than 2% and by more than its own scatter. So a
  driver that reports correctly keeps its value.
- **The log line:**
  `init: GPU timestamp period reported=%.3f ns measured=%.3f ns (+-%.2f%%, span %.1f ms, samples %d of %d, halves differ %.2f%%) using=%.3f ns (measured|reported[; not measured: <why>])`.
  A build without perflog logs the old line,
  `init: GPU timestamps enabled (period=%.2f ns)`, and measures nothing.
- **What reads the period.** Only `gpu_ts_readback` (draw.c) reads it, into
  `g_nv2a_stats.phase_working.gpu_*`. `profile.c` prints those, and nothing
  else consumes them.
- **Why pixels cannot move.**
  - The calibration uses its own one-query pool, created and destroyed
    inside `gpu_ts_calibrate`. It is not `gpu_ts_pool`.
  - The aux command buffer and its fence are reset by the helpers on every
    use.
  - No render state, pipeline, surface or guest register is touched.
  - A build without perflog does not run it at all.
- **Why not VK_EXT_calibrated_timestamps.** Enabling it is a
  device-creation change in `instance.c`, which is not on this lane's row.
  Two calibrated samples with an idle GPU between them would also have the
  first cut's fault.
- **Cost.** About 120 ms, once, at start-up, in perflog builds.

## The first cut, and what refuted it

The first cut took four samples, slept 100 ms, and took four more.

| run | device | the start-up line |
|---|---|---|
| `1-1790540677-flip474-2313275` | Thor | `reported=33.113 ns measured=4636.591 ns (+-0.16%, span 109.7 ms) using=4636.591 ns (measured)` |

- 109.7 ms at 4636.591 ns a tick is 23,660 ticks. At 19.2 MHz that is 1.2 ms:
  about the time the eight command buffers kept the GPU working. **The
  counter did not advance while the GPU was idle.**
- The line's own uncertainty, 0.16%, came from the width of the sample
  windows. It could not see this.
- On the title's unattended screen (two render passes) the run read GPU 28
  to 30 ms of a 32.5 ms frame. The A run read 0.2 ms there.
- `o4clock.py`'s fit holds to 0.1 ms over 110 s of DOA's fight, where the
  GPU idles about 1 ms a frame. So the counter keeps time through short
  gaps under load and not through 100 ms of idle. Where between those it
  stops is not known; the second cut's gapped half tests 300 us.

**The first cut's predictions, judged as far as they ran:**

| file | run | verdict |
|---|---|---|
| `flip474-tsperiod-crimson-thor.json` | A `1-1790540677-flip474-2313064`, B `...-2313275` | **M0 void:** both routes were refused (`ROUTE ABORTED: not foreground`, Daijishou held display 0), so there is no gameplay window. **K0 holds** (one line). **K1, the labelled guess, is refuted**: 4636.591, not 52.08. **K2 holds**, which is the problem: the code used what it measured. G1 and G2 are not judged without a window; the unattended screen's 28 to 30 ms is reported above |
| `flip474-tsperiod-doa-nova.json` | A `1-1790540673-flip474-2311172` ran; B `...-2311288` is queued | not judged. B is left in the queue: what the first cut reads on the Nova says whether the Nova's counter stops too |
| `flip474-tsperiod-pgraph-inert.json` | the arms job's pair, queued | not judged; it is about `902cf1ab53` |

## What the driver's source says

The Nova's and the Thor's driver is a Turnip build. The Mesa series it is
built from (`~/hakux-work/mesa-turnipfork`, `4c18636110`, pinned by
lane.turnipfork) reports `timestampPeriod` as 1e9 / 19.2e6 = 52.083 ns, with
the comment "CP_ALWAYS_ON_COUNTER is fixed 19.2 MHz"
(`tu_device.cc:1179-1296`). That is the fitted value to five figures. The
build on the devices reports 33.11 ns, so the wrong period is that build's,
not the hardware's or upstream's.

## Checks

- `ndkcheck.py`: renderer.c passes in NV2A_PERF_LOG 0 and 1, with 0 errors
  and 0 warnings in the file.
- `caltest.py` compiles `gpu_ts_calibrate`'s own text, cut out of
  renderer.c, against stubs that simulate a counter. It passes:

  | world | driver reports | must use | result |
  |---|---:|---:|---|
  | a free-running 19.2 MHz counter | 33.113 | 52.083 | measured 52.083 |
  | the same, an honest driver | 52.083 | 52.083 | reported kept |
  | a counter that runs only while the GPU works, and 50 us after | 33.113 | 33.113 | refused: the halves differ 268% |
  | a counter that stops 5 ms into an idle stretch | 33.113 | 52.083 | measured 52.083 |
  | a counter that restarts halfway | 33.113 | 33.113 | refused: the counter went back |
  | one sample in nine preempted for 3 ms | 33.113 | 52.083 | measured 52.082, 184 of 206 samples kept |
  | mutant: the first cut's sampling, in the two stopping worlds | | | slope 4082 and 871 ns, as the Thor's 4636; refused |
  | mutant: the 300 us gap removed, in the 50 us world | | | **accepts 54.705**: the gap is the check that refuses that world |

- `preflight.sh --allow-tracker` passes.
- Not built on the desktop, because this host has no desktop build.

**What the checks cannot see.** A counter that stops within tens of
microseconds of idle and restarts cleanly would bias both halves, the gapped
one more; that is refused. A counter whose rate is wrong by the same factor
in both halves would be accepted. K1 and G1 on the devices are the check on
that.

## Predictions for the second cut (A = master `57e2a7107c`, B = `253148451f`)

Registered before any arm, by `tsperiod2_register.py`.

| file | device | what it checks |
|---|---|---|
| `flip474-tsperiod2-pgraph-inert.json` | arms | 12 pgraph suites, every capture identical |
| `flip474-tsperiod2-doa-nova.json` | Nova, DOA, 300 s, B only | K1: measured 52.08 ns +-1%. K3, a guess at 70%: the self-checks pass. G1: B's phase GPU is within 8% of B's own cdef, the same interval on the CPU clock |
| `flip474-tsperiod2-thor.json` | Thor, Crimson, 120 s, B only | K1 and K3 as guesses. G3: the unattended screen reads under 1 ms, where the first cut read 28 to 30. The route need not play |

G1 replaces the first cut's B/A ratio. The route is blind and DOA draws its
opponent per run, so two runs are not the same scene; GPU and cdef in one
run are. On `795ea6b3af` the ratio read 0.65, 0.65 and 0.66 in three runs.

## Waiting

See the PR's newest `[lane.flip474] waiting:` comment for the request ids.

## Not done here

- Addendum 5, item 2 is in `NOTES.md` section 16.
- The instrument's R and X: both of a pass's timestamps are written inside
  the pass, so on a tiler X is not transfer time (section 16). Writing them
  outside the pass is a draw.c change.

## Do not repeat

- Do not calibrate a GPU counter across an idle GPU. It stops.
- Do not take a measurement's uncertainty from the width of its samples
  alone. The first cut's line said +-0.16% on a figure 89 times too large.
- Do not put a lane's second PR in a second worktree outside the session's
  primary directory. The sandbox blocks writes there. Switch the primary
  tree's branch instead, once the first PR is pushed.
