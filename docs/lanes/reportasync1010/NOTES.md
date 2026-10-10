# lane.reportasync1010: the occlusion report written after the fence, off the pacing thread (#433, 0.5)

Step 2 of `docs/lanes/nfs30plan1010/PLAN.md`. Base: master @ 9fd2608f8f (perdraw1009 and perdrawon1010
folded; pfifowait1009 not folded, so `HAKUX_PFIFOWAIT` is not on this base and nothing here touches it).

## 1. What the code does

All in `hw/xbox/nv2a/pgraph/vk/reports.c`. Two switches, both read once when the renderer starts, both off
unless set to `1`. With both off, the only code that runs is one `if (ra.started)` and one `if (rt.on)` per
finish and per GET_REPORT; the query pool, the report write and #804's wait are what master has.

### `HAKUX_REPORT_ASYNC=1`

- **A reader thread, `nv2a.vk.reports`, does the wait and the write.** The end of every finish
  (`pgraph_vk_process_pending_reports_internal`, called from `pgraph_vk_finish`) hands the reports queued
  since the last finish to it in one batch and returns without touching a fence. The reader waits for the
  fence of the frame slot whose command buffer counted the queries, reads them (`vkGetQueryPoolResults`,
  WAIT_BIT), keeps the running count, and writes each report: timestamp, count, then the status word, after
  a write barrier.
- **Each frame slot has its own range of the query pool**: 3 slots x 1,024 queries (the pool grows from
  1,024 to 3,072 entries with the switch on). `begin_query` (draw.c) takes its index from
  `num_queries_in_flight`; the finish sets that to the base of the slot the next command buffer records
  into, and `max_queries_in_flight` to the end of the range, so draw.c's existing assert still bounds it.
- **The guest address of each report is taken on the finishing thread**, from `pg->dma_report` at the
  finish, exactly when the synchronous path takes it (`pgraph_write_zpass_pixel_cnt_report` maps it at the
  write, inside the finish). A `SET_CONTEXT_DMA_REPORT` after the finish does not move it.
- **The count is the same 32-bit running count** (`zpass_pixel_count_result` is `uint32_t`; the reader's
  `sum` is too), divided by the surface scale squared taken at the finish.
- **The bytes written are the bytes the synchronous path writes**: `0x0011223344556677`, the count,
  `0`. In the NV notifier layout the last word is the status, 0 = DONE_SUCCESS; xemu has always written 0.
  The brief proposes `done=1`; that would make the async arm write a different word from the off arm (a
  guest that reads it, and the ZPass pgraph test prints it as `.reserved`, would see 1 where it saw 0), so
  the async write keeps 0 and orders it last: a guest that arms the status word before GET_REPORT and polls
  it sees "done" only after the count is in memory.
- **No file outside reports.c changes**: not render_thread.c, renderer.h, draw.c or pgraph.c.

### Why a thread of its own and not the render thread

The brief says the render thread "already waits on this fence (render_thread.c:157/:163)". It waits only
when a finish carries a `post_fence_cb`; the deferred finishes that make up the race start (FLIP_STALL,
STALLED, PRESENTING, SURFACE_DOWN_FLUSH) submit and return. And the render thread is the submitter: a fence
wait there delays the next submission, which is the third kind of attempt the corpus lost with (a wait
moved to another site the frame depends on). The reader paces nothing: no thread waits for it except at
the gate below, which in a 3-slot rotation finds the reader long done.

### How #804's guarantee is kept: the count written is this command buffer's, never the slot's previous one

#804: a query is reset by `vkCmdResetQueryPool` inside the command buffer; until the GPU executes that
reset, the query still reads as available with the count from the last command buffer that used the same
index (Turnip keeps availability in GPU memory), so WAIT_BIT returns the old count at once. The fix waits for
every submitted frame before reading. The async path keeps the property with three rules:

1. **A batch reads only its own slot's range, after its own slot's fence.** The fence is the one the
   finish submitted that command buffer with, so once it signals, that command buffer's resets and counts
   are done; no other command buffer writes that range while the batch is outstanding (rule 3).
2. **A batch is handed over only after its command buffer was submitted.** A deferred finish waits for the
   render thread's `vkQueueSubmit` (`wait_frame_submitted`) before the rotation and the reports; the
   others submit and wait for the fence before returning. So the reader never waits on a fence that is
   unsignalled because nothing was submitted (which would hang) or that still holds an earlier signal.
3. **A slot is not reused while a batch on it is outstanding.** Before the next command buffer starts in
   slot S, the finish waits until no batch on S is queued or running (`ra.pending[S]`). Only then can that
   command buffer reset S's queries, and its finish reset S's fence. In the normal 3-slot rotation
   `pgraph_vk_finish` has just waited S's fence itself, so this waits only for the read of three finishes
   ago; a finish that does not rotate (the render-thread finishes: DOWNLOADS, SYNC_DISPLAY, FLUSH) waits for
   its own batch, whose fence it has already waited.

Reports keep queue order: batches run in FIFO order on one thread, and a batch with reports but no new
queries (a GET_REPORT after the last draw of a command buffer) carries the running count forward the same
way. If the submit-frames setting changes under an open command buffer (`desired_frames`, draw.c:4921), the
slot it recorded into is no longer the slot it is submitted with: that one batch runs on the finishing
thread after the reader is idle, waiting for every submitted fence, as #804 does.

### Known limits

- A guest that reads the report without honouring the status word, after something that told it the GPU
  is done (a semaphore it polls, a PGRAPH idle wait), can read it before the reader has written it. The
  synchronous path writes it before the finish returns, with pfifo.lock held, so such a read then waits
  behind the lock. The ZPass pgraph test is that shape (`zpass_pixel_count_tests.cpp:157-200`: GET_REPORT,
  SEMAPHORE_RELEASE, `WaitForGPU`, spin on the semaphore, print the report): the pixel leg answers whether
  it reads too early. Whether NFS is that shape is the step-1 question (section 2).
- Savevm: neither path writes reports still queued when the snapshot is taken; the async path can also have
  one batch in the reader. Not exercised by any run here.

### `HAKUX_REPORT_TRACE=1`: when does the guest consume the report

Per GET_REPORT (`pgraph_vk_get_report`), on both paths: the time it was queued, the time the finish handed
it to the write (sync: the finish's report processing; async: the batch push), the time its fence passed,
the time it was written, the guest frame counter (`pg->frame_time`) at each, the time of the next flip and
of the next GET_REPORT at the same offset, and the status word and timestamp the guest had left in the
report before it. A flip's time is the end of the finish that first sees the frame counter move.

Printed on `hakuX-lane`, one line per 2 s (`[rtrace] w`): histograms (edges 0.25 0.5 1 2 4 8 16.7 33.3
66.7 ms) of queued -> hand-off (`e`), -> fence passed (`f`), -> written (`w`), -> next flip (`flip`), ->
next GET_REPORT at the offset (`next`); flips between queue and hand-off (`fle`) and between queue and write
(`flw`), 0/1/2/3+; `late` (written after a flip that the hand-off preceded: zero by construction on the sync
path, the async path's exposure); `flipb4w` (the flip after the GET_REPORT came before its write);
`reuse`/`reuseb4w` (offset used again; used again before the previous value was written, i.e. the guest
moved on without it); `armed` (status word nonzero when GET_REPORT came: the guest arms it), `stchg`,
`tsours` (the slot still held our timestamp); `gate` (count/us the finishing thread waited at rule 3) and
`wait` (count/us the finishing thread waited for the GPU: the sync path's #804 wait, or the async
settings-change fallback). Plus up to four sampled records a second (`[rtrace] r`). Reader:
`raread.py` (this dir).

**The criterion** (brief step 1): if, on the async trace run, more than 1% of the reports are `late`
(guest flipped between the point where the sync path would have written and the write), or `reuseb4w` is
not ~0, the async write needs the guest to honour the status word; `armed` says whether NFS does. Then the
switch stays opt-in.

## 2. Measurements

### Baseline (existing runs, plain build, read with `raread.py`, window mark-2 .. mark+1.5)

nfsframe1010's plain runs at 07937793af (perdraw1009's switches are default-off, so master's head runs the
same code at the race start):

| run | cold start 1 | warm starts 2-12 | warm v2 / v3 / v4 | post-GO warm |
|---|---|---|---|---|
| `1-1791649039-nfsframe1010-2037292` | 56.3 ms | 41.4 ms | 54 / 43 / 2 % | 39.5 ms |
| `1-1791649724-nfsframe1010-2219502` | 58.5 ms | 40.2 ms | 52 / 41 / 1 % | 39.5 ms |
| pooled | 57.4 ms (2 lines) | 40.7 ms (31 lines) | 53 / 42 / 1 % | 39.5 ms |

### Runs of this lane

Code ref for every run: `2e9f535300` (the commits after it change docs and the generated index only).

| request | what | env | state |
|---|---|---|---|
| `1-1791656656-reportasync1010-4183629` | pilot: step-1 trace, async path, NFS 500 s | `HAKUX_REPORT_TRACE=1 HAKUX_REPORT_ASYNC=1` | queued 10-10 |
| `1-1791656657-reportasync1010-4184121` | pilot: step-1 trace, sync path, NFS 500 s | `HAKUX_REPORT_TRACE=1` | queued 10-10 |

Waiting on those two (listed in `WAITING`). On resume: `raread.py <async> <sync>` for the step-1 table and the
period of each; frames `route-frames/s*-g11.png` for a moving player and for a missing or popping car; then the
pilot verdict to `$DISPATCH_DIR/pilots/reportasync1010.ok` and the rest of section 3 (pixel pair B then A, NFS
off/on/on/off).

## 3. Plan

1. Pilot (step 1, <= 30 min): two plain NFS runs, route `nfs-mw-quickrace`, 500 s, both
   `HAKUX_REPORT_TRACE=1`, one with `HAKUX_REPORT_ASYNC=1`. Gives the step-1 table on both paths, and shows the
   async path survives 12 starts. Not scored (`--no-expect`): the trace adds a lock and a few stores per
   GET_REPORT.
2. Pixel leg: the 27-suite disc (ZPass_pixel_count included, 72 captures) on vs off, one binary,
   `docs/testing/predictions/reportasync1010-pixels.json`, must_not_move every suite; any mover gets a runs=3
   determinism check before it is read as the switch.
3. NFS A/B, `docs/testing/predictions/reportasync1010-nfs.json`: plain build, 2 runs per arm, off, on, on,
   off; judged by `raread.py --expect`; route frames at the 12 marks compared on vs off by region.
4. texscan1010 is not on this base (only on its own branch, runs pending), so the step-5 pair is not run.

## 4. For the next lane

- `phaseread.py` (nfs30plan1010) prints nothing on the plain build: it returns before the pace line when no
  phase line is in the window. `raread.py` reads pace alone.
