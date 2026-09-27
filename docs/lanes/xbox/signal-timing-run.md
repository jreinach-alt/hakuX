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

## Result (2026-09-27)

- **Console:** 09:49-09:50 PDT, 89 s, "Testing completed normally", 16 files.
- **hakuX:** the dry run `0-0-x-1790526930-xbox-timing462-dry-1549920` on the **Thor**, hakuX `c6e2be0936` (apk `17eff0363df9`), completed normally.
- The raw files are in [`signal-timing/console`](signal-timing/console) and [`signal-timing/hakux-thor`](signal-timing/hakux-thor). The table is in [`signal-timing/table.md`](signal-timing/table.md).

**Instrument legs:**
- I1 holds on both machines (1.000001 and 1.000018).
- I3, I4 and I5 hold on the console.
- **I2, as registered, FAILS (59.9999 Hz). The leg was mis-specified.** A 2 s count of vblanks (120) resolves only +/- 0.5 Hz. The rate from the 300 spin intervals is **59.9401 Hz on the console** (16683.33 us mean), and **59.9390 Hz on hakuX**. I3 is the leg that checks the rate, and it holds.

**Not run:** `ST_VBlank_Event` ran in neither run. The suite runs its tests in name order, so it ran before `ST_VBlank_Spin` and its guard skipped it. A fixed build, whose event test checks vblanks itself, gets its own dry run.

**Amendments:**
1. After the dry run, before the console run: the table script's file matching also accepts the dispatcher's flattened names (`Signal_timing::ST_x.txt`). No computation changed.
2. After the console run: the second flip row's label says what it measures. It is from seeing the `NV_PCRTC_START` change to the NEXT vblank counter tick. On the console that is one frame (16.68 ms), because the vblank ISR's write and the DPC's counter increment come from the same interrupt, before the loop reads the counter.

### What the table says

- **vblank:** the same mean rate on both, but the console's intervals vary by 1.8 us p5-p95, and hakuX's by 391 us. hakuX's intervals range from 14.17 to 18.93 ms; the console's from 16.672 to 16.695 ms.
- **GPU completion:** on silicon, the semaphore release is visible **2.7 us** after the last kick, and the NOTIFY write 4.1 us after it. That holds for 1 quad and for 500 quads with a render-target switch alike: the GPU finishes the frame while the CPU is still submitting it (6.38 ms).
  - On hakuX the same 500-quad frame's semaphore arrives a median **13.8 ms** after the last kick (p95 16.9 ms), after a submission of 11.0 ms.
- **NOTIFY:** hakuX never wrote the NV097 write-only NOTIFY notifier, 0 of 900 times. Silicon wrote it every time.
- **CPU read of the 640x480 back buffer:** 31.07 ms on silicon, 23.27 ms on hakuX.
- **Flip:**
  - On silicon, `pb_finished()` takes effect at the next vblank: the start register changes 16.18 ms after the request, and the next counter tick comes one frame later.
  - On hakuX the start register changes **24.1 ms** after the request, and the next counter tick comes **8.25 ms** after that. The write is not on a vblank boundary. The mechanism is not established here.

## v2: the vblank event wake (PRE-REGISTERED before its dry run)

- **The change:** `ST_VBlank_Event` guards itself. Before the untimed `pb_wait_for_vbl()`, it sees three vblanks arrive by spinning, each within 100 ms. The tests commit is `27c602e` on `hakux/signal-timing462`, and the updated [`signal-timing462.patch`](signal-timing462.patch) replaces the first.
- **The files:** XBE sha256 `7f85e8489424…`, in `hardware/runs/2026-09-27-timing462v2/`.
- **The session:** `Alpha func::AlphaFuncAlways_Disabled`, then `ST_VBlank_Event` only. The same order applies: a hakuX dry run first, then the console.
- **The leg:** under hakuX, the table's two event rows (the interval, and its jitter as the woken thread sees it) are the measurement. On the console, I6 applies: 0 intervals spanning a missed vblank, and a mean interval 16683 +/- 20 us over the 300 intervals.

### v2 result (2026-09-27)

- **hakuX:** the dry run `0-0-x-1790528078-xbox-timing462v2-dry-2128991` completed normally on the **Nova**.
- **Console:** 09:59-10:00 PDT, 58 s, completed normally.
- **I6 holds:** 0 missed vblanks, and a mean interval of 16683.33 us.
- **The result:** a thread woken by `pb_wait_for_vbl()` sees vblank intervals that vary by 0.3 us p95 on silicon, and by 141.6 us p95 on hakuX (range 16303-17107 us).
  - The Nova's event-wake spread is smaller than the Thor's spin spread (v1). That is two devices and two methods, so the two figures are not compared.
- The raw files are in `signal-timing/console-v2` and `signal-timing/hakux-nova-v2`.

## v3: the push-buffer callback (PRE-REGISTERED before its dry run)

**Why:** retreason425 (#425, 09-27 10:20 PDT) found that AUF, Blinx and Blinx 2 wake at the PGRAPH ERROR interrupt. It comes from `NV097_NO_OPERATION` with a non-zero parameter: the puller raises it at that marker and stalls until the guest's handler clears it. Nobody has measured the time from the guest's kick to the callback being handled, or from the handler to the puller's resume. flip474's host-side `[cblat]` stops at the puller dispatching the NOP.

**The private pbkit:** pbkit already routes NOP-with-data to `pb_subprog()` in its DPC. [`pbkit-timestamp462.patch`](pbkit-timestamp462.patch) adds one case:
- `PB_TIMESTAMP` (0xFA0) stores `KeQueryPerformanceCounter()` into `pb_callback_time[seq & 63]` and increments `pb_callback_seq`. RAM stores only, with no register access.
- The copy is `~/nxdk-cb462`. Only `libpbkit.lib` was rebuilt there; the pristine nxdk is untouched.
- The existing IDs were no use: SETOUTER and SETNOISE write registers, FINISHED changes the flip state, and an unknown ID runs debugPrint in the DPC.

**The tests** (tests branch `hakux/signal-timing462-cb`, commit `509fe90`, patch [`signal-timing462-cb.patch`](signal-timing462-cb.patch); XBE sha256 `11f5cb27e78d…`, ISO `58ffba708d48…`, in `hardware/runs/2026-09-27-callback462/`), 300 repetitions each:
- `ST_CB_1_Empty`: one callback with no drawing, then a semaphore release.
- `ST_CB_2_DOA`: 500 quads with one render-target switch, then one callback and the semaphore.
- `ST_CB_3_DOA15`: the same 500 quads with 15 callbacks interleaved (Blinx takes 14.66 a frame), then the semaphore.

Each callback's kick time is taken just BEFORE its kick, so no callback can precede its own kick. The measured legs are:
- kick -> callback handled in the DPC;
- the last callback handled -> the semaphore behind it visible (the puller resumed after the handler cleared it);
- the frame, from first draw -> semaphore visible;
- the overhead per extra callback, (15-callback frame - 1-callback frame) / 14.

**The session:** `Alpha func::AlphaFuncAlways_Disabled`, then `ST_CB_1_Empty`, `ST_CB_2_DOA`, `ST_CB_3_DOA15`, `ST_Calibrate` (name order). The same order applies: a hakuX dry run on the Nova first, then the console, with PAUSE. If the console stops answering, stop, do not retry, and tell lane.local.

**Instrument legs** (console; under hakuX only I1):
- **I1:** the clock, as before.
- **I7:** `ST_CB_1_Empty` has 300 reps, 0 timeouts and 0 stale callback times. Every callback's DPC time is newer than the one before it (the must-move check).
- **I8:** `ST_CB_3_DOA15` has 300 reps, 0 timeouts and 0 stale times, and all 15 callbacks seen in every frame.

No values are predicted.

### v3 amendment, before any silicon: the dry run bugchecked the guest; v3b

- **What happened:** the v3 dry run `0-0-x-1790531870-xbox-callback462-dry-3197659` (Thor) ran `ST_CB_1_Empty` to completion and wrote `ST_CB_2_DOA.txt`. Then the guest bugchecked: 0x1E, access violation, CR2 `0x3d78616d`, which is the bytes "max=".
- **The cause is the suite's own `Finish()`, not the callback.** It printed the whole summary through `pb_printat()`, which formats into a 512-byte stack buffer with `vsprintf` (`pbkit_print.c`). v3's longer summaries overflowed it. v1 and v2 stayed under 512 bytes.
- **v3b:** only the test name goes on screen. The measurement code is unchanged. Tests commit `c9a473c`, XBE sha256 `d4796af3d408…`, ISO `1b5ffbabae6e…`, in `hardware/runs/2026-09-27-callback462b/`, with output `e:/callback462b`.
- The legs, the session and the order are as registered above. A new dry run comes first.
- The v3 dry run's `ST_CB_1_Empty` numbers stand as hakuX data. Its I7 fields held there too: 300 reps, 0 timeouts, 0 stale.
