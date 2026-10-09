# cloud-527 NOTES

Issue #527: the ZPASS_PIXEL_CNT report prints 40,960 on the handhelds whatever
the test draws. Cloud lane, no device. Base: master @ f82e7e87fe.

## 1. The two separating runs were never queued

lane.flip474 proposed two runs on #474 (02:10Z) to separate `TU_DEBUG=sysmem`
from a kept shader cache: ZPass + Antialiasing, sysmem first on a cleared
cache, then no env on the kept cache. It retired at 02:40Z without queuing them.
lane.local asked lane.rendermode474 to queue them (02:45Z). At 03:15Z neither
the dispatch queue nor any result dir holds them. rendermode474's four queued
requests are its DOA pilot and its 27-suite arms pair, which change neither
factor on the ZPass suite. So there is nothing to read for goal 1, and after
section 2 the runs are no longer needed to explain the constant.

## 2. What the constant is: a stale report, not a count

`nxdk_pgraph_tests/src/tests/zpass_pixel_count_tests.cpp`:

- The report buffer (`report_context_object_`, 4 x 16 bytes) is allocated
  and zeroed once, in `Initialize()`, and shared by every test in the suite.
- Tests run in `std::map` order, so `ZPass` runs first.
- `ZPass` expects 2.5 quads of 128 x 128 in its first report:
  16,384 x 2.5 = **40,960**. Its second report, at 0x10, expects 49,152.
- Every other test calls `GET_REPORT` at offset 0, then restores pbkit's
  report context (`SET_CONTEXT_DMA_REPORT, 12`) in the same push, releases
  a semaphore, waits for the GPU, and prints slot 0.

The captures, read by eye:

| run | ZPass report 0 | ZPass report 1 (0x10) | ZPassLineWidth-0x0000 (expects 16,384) |
|---|---|---|---|
| `1-1790549941-arms-flip474-base-2298159`, Nova | 40,960 PASS | **0** | 40,960 |
| `0-0-x-1790549039-flip474-1817704`, Thor, sysmem + kept cache | 65,536 | **0** | (65,536 per #474) |
| `z-tip-099-ZPass_pixel_count`, `0026f00534`, 2026-09-13 | 49,152 | **0** | 49,152 |

So:

- The semaphore reads PASS in every test, so the pushbuffer ran to the end.
- Report 1 of ZPass is never written in any run: it stays at the zero from
  `Initialize()`.
- Every later test prints whatever ZPass left in slot 0. That is why it is
  one value per run, and why the value follows ZPass's first report:
  40,960, 65,536, 49,152.
- The "constant" is not a counter stuck at one value. 35 of 36 reports
  never reach the test's buffer.

## 3. Why they never land (vk/reports.c)

- `pgraph_vk_get_report` only queues a `QueryReport` (`clear`, `parameter`,
  `query_count`). It records no DMA object.
- `pgraph_vk_process_pending_reports_internal` writes each queued report
  through `pgraph_write_zpass_pixel_cnt_report`. That maps `pg->dma_report`
  as it is **when the queue is processed**. It runs only at the end of
  `pgraph_vk_finish`.
- `SET_CONTEXT_DMA_REPORT` (pgraph.c) calls `ops.process_pending_reports`
  before it rebinds, which is right. GL's version writes everything queued.
  Vulkan's version (`pgraph_vk_process_pending_reports`) finishes only when
  `DMA_GET == DMA_PUT`, a command buffer is open, and a draw happened since
  the last stall finish. In mid-push none of that holds, so the report stays
  queued. It is written at the next idle finish, to pbkit's default report
  buffer.
- ZPass's first report lands because its push ends right after `GET_REPORT`
  (`Pushbuffer::End(true)`). The FIFO goes idle, a stall finish runs, and the
  test's DMA object is still bound.

`pgraph_write_zpass_pixel_cnt_report` itself is sound. It writes a 64-bit
timestamp, the 32-bit result at +8 and `done` at +12, at the requested
offset. Nothing in it is hardcoded.

The brief's falsifier ("every case stuck at the value, including ones with
different draw content, argues for the report path") is met by the report path
through the DMA rebind, not by the write function.

## 4. The fix, and what it does not settle

`9e19e81a05`: in `pgraph_vk_process_pending_reports`, after the existing stall
check, anything still queued is written now. With a command buffer open that
takes a synchronous `VK_FINISH_REASON_FLUSH`. Without one, the queue is
processed directly: no queries can be in flight outside a command buffer.

- The block runs only when a report is queued, so only on `GET_REPORT`
  users. Among the pgraph suites that is ZPass alone (grep of
  nxdk_pgraph_tests/src).
- In games the extra flush happens when a report DMA is rebound, or at FIFO
  idle, while a report is still queued. Games normally keep one report
  context bound, so it should be rare. That is not measured: Blinx is the
  title to price it on, because it ends render passes for occlusion queries
  in every line (#474).
- Compiled `-fsyntax-only` against the Android build tree's
  `compile_commands.json` (arm64 Release). `check_android_guards.py`
  passes. Desktop is not built on this host (AGENTS.md, a known gap).

**Not settled: whether the counter is right.** ZPass's own first report
differs by build and mode: 40,960 (correct), 49,152 (`0026f00534`) and
65,536 (Thor B). The fix exposes each test's own count, and that is the
brief's falsifier: counts that track geometry mean the counter works. Two
readings to check before blaming the driver:

- `occlusionQueryPrecise` is requested but is optional (`instance.c`). Without
  it, `begin_query` passes no `PRECISE_BIT`, and a driver may return any
  non-zero value for a passing query.
- 65,536 is four whole quads: the depth-hidden quad plus the half that is off
  screen. 49,152 is three.

Only ZPass's first report is affected so far. The sysmem-vs-cache runs matter
for that report alone now.

## 5. Prediction

`docs/testing/predictions/cloud527-zpass-report.json`, A `f82e7e87fe`, B
`9e19e81a05`. It covers ZPass_pixel_count, Antialiasing_tests, Clear and
Depth_buffer. `must_not_move`: the three other suites and
`ZPass_pixel_count/*_ZB`.

The movers are read by hand from the captures:

- In B, ZPass's second report is non-zero.
- In B, the 35 later tests do not all print one value.
- Refuted if B still prints 40,960 in all of them.

## Do not repeat

- Do not look for the constant in the counter or the driver first. The value
  never reaches the guest's buffer. Read report 1 of `ZPass`: 0 means the
  write went elsewhere.
- The sysmem-vs-cache pair explains only ZPass's first report. It does not
  explain the constant.

## State at session end (2026-09-28 ~03:40Z)

Waiting on the arms pair for `cloud527-zpass-report.json` and CI. PR #535 stays a draft until the verdict is read.
