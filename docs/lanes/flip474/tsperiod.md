# lane.flip474 -- the GPU timestamp period, measured at start-up (#474, Addendum 5)

This is its own PR, off master, because the addendum asked for one. The
lane's investigation stays in `NOTES.md` on #485. This file is named so it
does not collide with that file when both fold.

## Why the last session did not finish

It had finished its brief. It judged the five Nova runs and posted them on
#474 and #462 at 20:17Z, with #485 ready. Addendum 5 (13:18 PDT, 20:18Z)
arrived one minute after it ended. This session does Addendum 5, item 1.

## The change (`hw/xbox/nv2a/pgraph/vk/renderer.c`, `gpu_ts_calibrate`)

- **What was wrong.** `gpu_ts_period_ns` came from
  `limits.timestampPeriod`. On the Nova that is 33.11 ns (30.2 MHz), while
  `o4clock.py` fitted the ticks at 52.083 ns (19.200 MHz) against the CPU
  clock (NOTES.md section 15). So every `hakuX-phase` GPU, R and X figure
  from the Nova read 0.636 of the true value.
- **The measurement.** It runs at init, where the old line was logged,
  before any guest work.
  - Each sample records one `vkCmdWriteTimestamp` on the aux command buffer
    (`pgraph_vk_begin/end_single_time_commands`), which submits and waits on
    its fence. The CPU clock (`get_clock`) is read before and after.
  - The tick was written inside that window, so the sample's time is the
    window's middle, uncertain by half its width.
  - It takes four samples, then sleeps 100 ms, then takes four more. The
    narrowest window of each group is kept.
  - period = CPU span / tick span. The relative uncertainty is the mean
    half-width over the span.
- **The choice.** The measured period is used only if both of these hold:
  - its uncertainty is under 5%;
  - it differs from the reported period by more than 2% and by more than
    its uncertainty.

  So a driver that reports its period correctly keeps it exactly.
- **The log line.** There is one line at start-up:
  `init: GPU timestamp period reported=%.3f ns measured=%.3f ns (+-%.2f%%, span %.1f ms) using=%.3f ns (measured|reported)`.
  If there is no query pool or no usable sample, the line says "not
  measured" and the reported period is kept.
- **What reads the period.** Only `gpu_ts_readback` (draw.c:3328-3367) reads
  it, into `g_nv2a_stats.phase_working.gpu_*`. `profile.c` prints those, and
  nothing else consumes them. No tool parsed the old "GPU timestamps
  enabled" line.
- **Why pixels cannot move.**
  - The calibration uses its own one-query pool, created and destroyed
    inside `gpu_ts_calibrate`. It is not `gpu_ts_pool`, so the frame
    readback can never see a calibration tick.
  - The aux command buffer and its fence are reset by the helpers on every
    use.
  - No render state, pipeline, surface or guest register is touched.
- **Why not VK_EXT_calibrated_timestamps.** The addendum preferred the
  extension. Enabling it is a device-creation change in `instance.c`, which
  is not on this lane's row. It is also not inert by construction, since it
  adds an extension to every device. The fit needs neither, and it gives
  about 0.1-1% over 100 ms, which is enough to tell 30.2 MHz from 19.2.
  If a finer period is ever needed, the extension belongs in a separate
  change to `instance.c`.
- **Cost.** About 100 ms, once, at start-up.

## Checks

- `ndkcheck.py`: renderer.c passes in NV2A_PERF_LOG 0 and 1, with 0 errors
  and 0 warnings in the file.
- Not built on the desktop, because this host has no desktop build. The
  pgraph arm below is the inertness check.

## Predictions (registered before any arm; A = master `795ea6b3af`, B = `902cf1ab53`)

| file | device | what it checks |
|---|---|---|
| `flip474-tsperiod-pgraph-inert.json` | arms | 12 pgraph suites, every capture identical |
| `flip474-tsperiod-doa-nova.json` | Nova, DOA, 300 s | K1: measured 52.08 ns +-1%; G1: B/A phase GPU is 1.573 +-15%; G2: GPU <= 1.05 x Tot |
| `flip474-tsperiod-crimson-thor.json` | Thor, Crimson, 240 s | K1 is a guess, labelled (same as the Nova); K0/K2/G1/G2 test the mechanism whatever the Thor's value is |

`tsperiod_register.py` writes the two device files. The inert file came from
`ab_compare.py --register`.

## Not done here (Addendum 5, item 2)

DOA's GPU cost per pass waits on B's corrected period. After that, the
per-pass GPU table can be read in true units. The R/X "replay" test is to
move the timestamp outside the pass or to read the bin count.

## Do not repeat

- Do not put a lane's second PR in a second worktree outside the session's
  primary directory. The sandbox blocks writes there. Switch the primary
  tree's branch instead, once the first PR is pushed.
