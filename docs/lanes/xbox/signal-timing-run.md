# #462 / #474: when the NV2A delivers the end-of-frame signals, console vs hakuX

**Status: PRE-REGISTERED.** This file, [`signal_timing_table.py`](signal_timing_table.py) and the tests patch
[`signal-timing462.patch`](signal-timing462.patch) were committed and pushed before the hakuX dry run and before the
console run.

## Why

#462 found the slow titles waiting, not computing:
- AUF's exec-loop time is the guest's idle loop (`sti; nop`; retreason425 on #425).
- DOA's vCPU waits on `pgraph.lock` while PFIFO waits for the previous frame's display download (flip474 on #474).

A game cannot be observed on the console: there is no XBDM on this BIOS and no capture. The signals games wait for
can be timed, though. The same program then runs under hakuX, so the emulator gets hardware-true targets for each
signal.

## What runs

- **The XBE:** nxdk_pgraph_tests `6743b6a` plus [`signal-timing462.patch`](signal-timing462.patch) (tests branch
  `hakux/signal-timing462`). The patch adds a `Signal timing` suite, registered after `AlphaFuncTests`.
  - Tests commit `4fd5b45`. XBE sha256 `eb8f78ea2bc0…`, ISO `58d29c766c74…`
    (`hardware/runs/2026-09-27-timing462/`). The dry run uses hakuX `c6e2be0936`.
- **The clock:** every time is `KeQueryPerformanceCounter`, at the rate `KeQueryPerformanceFrequency` reports. Each
  test writes `<test>.txt` beside its capture: a summary, then every raw sample in counter ticks.

| test | what it times, 300 or more times |
|---|---|
| `ST_Calibrate` | the counter against the kernel's interrupt time, rdtsc and the vblank count, over 2 s |
| `ST_VBlank_Spin` | 301 vblanks, seen by spinning on `pb_get_vbl_counter()` (pbkit's vblank DPC increments it) |
| `ST_VBlank_Event` | 301 vblanks, seen by waking from `pb_wait_for_vbl()` (the event that DPC pulses) |
| `ST_Done_Tiny` | one quad, then `BACK_END_WRITE_SEMAPHORE_RELEASE` and a write-only `NOTIFY`: last kick -> each visible to the CPU |
| `ST_Done_DOA` | the same after 500 quads, one draw call each, with one render-target switch (250 to a 256x256 target, 250 to the back buffer) |
| `ST_Done_DOA_Read` | the same, then the CPU reads the whole back buffer |
| `ST_Flip` | `pb_finished()` -> the vblank ISR's write of `NV_PCRTC_START` (polled, read only) -> the vblank DPC's counter increment |

- **The session:** `Alpha func::AlphaFuncAlways_Disabled` runs first (PR #348), then the seven tests in the table's
  order. Shutdown on completion is off, networking is off, and the progress log is on.
- **The order:** a hakuX dry run goes through the dispatcher first (the Nova or no device pin; lane.local, 09-27).
  The console runs through `tools/xbox/pgraph_run.py` only after the dry run completes cleanly. The title pipeline is
  PAUSEd for the console session.

### Why it is safe on the console

- pbkit calls and pushbuffer methods only. The one MMIO access added is a **read** of `NV_PCRTC_START`. There are no
  PVIDEO accesses of any kind.
- The semaphore and notifier contexts are pbkit DMA objects over the suite's own uncached pages, the pattern
  `gpu_m2m.cpp` runs on the console. pbkit's own bindings (semaphore 8, notifies 2) are restored in `Deinitialize`.
- `NOTIFY` is type 0, write only, so it raises no interrupt. The NOTIFY *interrupt* is a later build (below).
- The render-target switch is `texture_render_target_tests.cpp`'s sequence, which has run on the console.
- Every poll is bounded (100-250 ms), and a test stops early when a signal stops arriving. The exception is
  `pb_wait_for_vbl()`, which has no timeout, so `ST_VBlank_Event` runs only after `ST_VBlank_Spin` has seen all
  301 vblanks arrive.

## Instrument legs

If a leg fails, the run's timings say nothing about the signals.

- **I1, the clock:** in `ST_Calibrate`, `counter_over_interrupt` is within 0.995..1.005. The performance counter
  agrees with the kernel's interrupt time over 2 s. This must hold on both machines.
- **I2, the vblank rate (console):** 59.94 +/- 0.05 Hz. The console's EEPROM is NTSC-M
  (`hardware/xbox-eeprom-2026-09-19.TXT`).
- **I3, vblank arrival (console):** `ST_VBlank_Spin` has 0 timeouts and a median interval of 16683 +/- 20 us.
- **I4, the semaphore arrives (console):** `ST_Done_Tiny` has 0 semaphore timeouts. A NOTIFY timeout is a finding
  about NOTIFY, not an instrument failure.
- **I5, the flip (console):** `ST_Flip` has 0 `NV_PCRTC_START` timeouts.

Under hakuX only I1 is an instrument leg. Everything else there is the measurement: a hakuX timeout, or a vblank rate
that is not 59.94 Hz, is a finding.

No values are predicted. This run measures targets; it does not test a hypothesis.

## What is reported

`signal_timing_table.py --console DIR --hakux DIR --device NAME` checks the legs and prints one table. For each
signal it gives the console's median and p95 against hakuX's, with the handheld named. The table is recomputed from
the raw samples. It is posted on #462 and #474, and the raw files are committed beside this file.

## Next, if retreason425 names the PGRAPH / NOTIFY interrupt as AUF's waking source

A private nxdk copy puts a counter timestamp inside pbkit's DPC for the NOTIFY interrupt. The suite then adds a
write-then-awaken NOTIFY and times kick -> interrupt handled. That is a separate build with its own dry run.
