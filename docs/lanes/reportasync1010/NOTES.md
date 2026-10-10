# lane.reportasync1010: the occlusion report written after the fence, off the pacing thread (#433, 0.5)

Step 2 of `docs/lanes/nfs30plan1010/PLAN.md`. Base: master @ 9fd2608f8f (perdraw1009 and perdrawon1010
folded), merged forward to master @ c829b64c8e (60a04cc81b: pfifowait1009, nfsframe1010, nfs30plan1010 and
forzasurf1010 folded; `reports.c` auto-merged, pfifowait's default-off `HAKUX_PFIFOWAIT` kept, unset in every run
here). The both-switches pair (brief step 5) runs on `lane/reportasync1010-ts` @ 3cd9d6b7e3: this branch @
ba9a6df8fc merged with `origin/lane/texscan1010` @ 227a161cc2, because texscan1010 has not folded. That branch is a
build ref only, with no PR of its own; nothing from it folds through this PR.

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

### Why this is not pfifowait1009 (the third removal of this wait that lost fps)

pfifowait1009 (`HAKUX_PFIFOWAIT=1`, its NOTES.md section 7) dropped `pfifo.lock` around the STALLED finish. The
PFIFO thread still waited for the fence; only the vCPU's DMA_PUT store could go on meanwhile. Its two legs both
failed. On Amped 2 the vCPU's `pgraph.lock` wait doubled (2.4-3.4 -> 5.5-6.5 ms/frame) and fps fell at every
matched-work bin, so the wait was not removed: it moved to the next lock the vCPU reaches. On the pixel disc,
`Stencil_ZERO_ST_DT*` moved by 30,000 px, attributably, so a lock released in the middle of method processing let
state change under it.

This design changes neither of those:

- **The wait leaves the pacing thread instead of being shared out.** With the switch on, the finishing thread
  does no fence wait and no `vkGetQueryPoolResults` for reports (pilot: 0 report waits vs 4,114 and 18.4 s on the
  sync run; section 2). The fence wait runs on `nv2a.vk.reports`, which nothing waits for except rule 3's gate
  (7 waits, 1.0 ms in the whole pilot run). Nothing new runs in the time saved: the PFIFO thread simply goes on to
  the next method, as it does after any finish without reports.
- **No lock is released.** The finish runs with the same locks held, in the same order, as before. The reader
  thread takes only its own mutex (and the trace's, when tracing). It touches no PGRAPH or PFIFO state, only the
  query pool, its slot's fence, and the 16 guest bytes whose address the finishing thread already resolved. So
  there is no mid-method window for state to change in, which is what moved Stencil.
- **What does change for the guest is when the 16 bytes land.** That is the step-1 question, measured below.

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

### Pilot (brief step 1): when the guest consumes the report

Two runs on 2e9f535300, NFS MW, route `nfs-mw-quickrace`, 500 s, Nova, both with `HAKUX_REPORT_TRACE=1`:
`1-1791656656-reportasync1010-4183629` (async, `HAKUX_REPORT_ASYNC=1`) and `1-1791656657-reportasync1010-4184121`
(sync). Both reached all 12 race starts. Each figure below is per GET_REPORT, from the trace windows that fall in a
race start (mark-2 .. mark+12 s), read with `raread.py <async> <sync>`.

**The step-1 table:**

| per GET_REPORT, race starts | sync (`-4184121`) | async (`-4183629`) |
|---|---|---|
| reports written | 4,114 | 3,787 |
| queued -> handed to the write, < 2 ms / < 4 ms | 59.6 / 99.6 % | 50.5 / 99.6 % |
| queued -> written, < 8 ms / < 16.7 ms | 95.6 / 100.0 % | 94.2 / 99.9 % |
| flips between queue and write: 0 / 1 / 2+ | 100 / 0 / 0 % | 1.2 / 98.8 / 0 % |
| **`late`: written after a flip that the hand-off preceded** | **0 %** | **98.8 %** |
| queued -> next flip, < 4 ms / < 8 ms | (the flip waits behind the write) | 93.8 / 99.9 % |
| queued -> next GET_REPORT at the same offset | >= 66.7 ms in 100 % | >= 66.7 ms in 100 % |
| `reuseb4w`: offset reused before the previous write landed | 0 | 0 |
| `armed`: status word nonzero when GET_REPORT came | 100 % (all `ffffffff`) | 99.9 % (all `ffffffff`) |
| `tsours`: slot still held our timestamp at GET_REPORT | 0 | 0 |
| finishing thread: report waits, total | 4,114, 18,352 ms | **0** |
| finishing thread: rule-3 gate waits, total | 0 | 7, 1.0 ms |

**Verdict on the brief's criterion: over 1 %.** On the async path the guest flips before the result lands on
98.8 % of reports. The write lands as soon after GET_REPORT as on the sync path (95 % within 8 ms either way), but
the frame no longer waits for it. So by the brief's rule, the async write needs `done` honoured by the guest, or
it stays opt-in.

**What the guest does with the report** (the trace sees the guest's writes, not its reads):

- NFS arms the status word to `0xffffffff` before every GET_REPORT, and rewrites the timestamp too (`tsours` 0).
  This is the D3D notifier pattern: the status reads "in progress" until the GPU, here the reader, writes 0 last,
  after the count.
- It cycles at least four report slots: the same offset comes back no sooner than 66.7 ms later, and never before
  the previous write landed (`reuseb4w` 0).

So NFS polls the status word rather than reading the count blind, and it never reuses a slot early. A read that
comes before the write sees "in progress", not a wrong count: what it costs is a result one frame later, not a
stale one. Whether that is visible is what the pixel checks answer:

- **Route frames:** the `go` frames at the start line (`framecmp.py`, async vs sync pilot, against two plain
  sync runs as the noise floor). Median region difference: sky 9.2 vs 6.4, road 9.1 vs 7.3, player 8.4 vs 5.7,
  HUD place 10.8 vs 7.8, map 1.6 vs 0.9 (0-255). Looked at side by side, every difference is per-run scene
  content that the floor pair also shows:
  - the opponent cars' liveries (randomized per run);
  - the countdown digit caught by the shot;
  - the tree swaying in the sky;
  - the HUD's place order.

  No car or prop is missing or popping. The `s*-g11` frames (11 s past GO) show a moving player at every valid
  start (28-90 mph) on both runs. They are not region-comparable (different driving lines), and none shows a
  missing car or a popping prop.
- **The ZPass pixel suite** is the case of a guest that does not poll the status word: it waits for a semaphore
  and PGRAPH idle, then reads. It is the first leg of the queued batch.

**Period** (trace on, not scored: the trace adds a lock and stores per GET_REPORT; `raread.py --starts`):

| run | starts used | cold start 1 | warm countdown | warm v2 / v3 / v4 | post-GO warm |
|---|---|---|---|---|---|
| async `-4183629` | 10 of 12 (go4, go9 dropped) | 52.8 ms | 38.2 ms | 73 / 25 / 1 % | 35.4 ms |
| sync `-4184121` | 12 of 12 | 47.1 ms | 40.6 ms | 57 / 40 / 1 % | 40.5 ms |

Two async starts were dropped because a route input hung in adb:

- go4: `press A 120` took 9.7 s;
- go9: `axis HATX min` took 10.1 s and failed (rc 1).

Both "races" then ran from a menu. The frames show it: s4-g11 is the restart-confirm dialog, s9-g11 is STANDINGS.
Before this change, `raread.py` scored those menu windows as race starts. It now drops any start whose route input
failed or took over 3 s, on both arms (`bad_starts()`), and the re-registered prediction requires >= 10 valid
starts per run. Separately, the sync run's s10-g11 screenshot failed (22 s in adb). Its inputs were all on time and
its go10 pace matches its other starts, so the start is kept.

### Runs of this lane

| request | what | ref | env | state |
|---|---|---|---|---|
| `1-1791656656-reportasync1010-4183629` | pilot, step-1 trace, async | 2e9f535300 | `HAKUX_REPORT_TRACE=1 HAKUX_REPORT_ASYNC=1` | done, above |
| `1-1791656657-reportasync1010-4184121` | pilot, step-1 trace, sync | 2e9f535300 | `HAKUX_REPORT_TRACE=1` | done, above |
| `1-1791659693-reportasync1010-543406` | pixel leg B, 27 suites | ba9a6df8fc | `HAKUX_REPORT_ASYNC=1` | queued 10-10 |
| `1-1791659700-reportasync1010-546194` | pixel leg A, 27 suites | ba9a6df8fc | none | queued 10-10 |
| `1-1791659702-reportasync1010-546475` | NFS A/B off1 | ba9a6df8fc | none | queued 10-10 |
| `1-1791659703-reportasync1010-547266` | NFS A/B on1 | ba9a6df8fc | `HAKUX_REPORT_ASYNC=1` | queued 10-10 |
| `1-1791659705-reportasync1010-547898` | NFS A/B on2 | ba9a6df8fc | `HAKUX_REPORT_ASYNC=1` | queued 10-10 |
| `1-1791659706-reportasync1010-548438` | NFS A/B off2 | ba9a6df8fc | none | queued 10-10 |
| `1-1791659722-reportasync1010-552321` | both-switches off1 | 3cd9d6b7e3 | none | queued 10-10 |
| `1-1791659723-reportasync1010-552662` | both-switches on1 | 3cd9d6b7e3 | `HAKUX_TEXSCAN=1 HAKUX_REPORT_ASYNC=1` | queued 10-10 |
| `1-1791659725-reportasync1010-552924` | both-switches on2 | 3cd9d6b7e3 | `HAKUX_TEXSCAN=1 HAKUX_REPORT_ASYNC=1` | queued 10-10 |
| `1-1791659726-reportasync1010-553359` | both-switches off2 | 3cd9d6b7e3 | none | queued 10-10 |
| `1-1791659727-reportasync1010-553973` | trace, texscan + async (not scored) | 3cd9d6b7e3 | `HAKUX_TEXSCAN=1 HAKUX_REPORT_ASYNC=1 HAKUX_REPORT_TRACE=1` | queued 10-10 |
| `1-1791659729-reportasync1010-554366` | trace, texscan + sync (not scored) | 3cd9d6b7e3 | `HAKUX_TEXSCAN=1 HAKUX_REPORT_TRACE=1` | queued 10-10 |

ba9a6df8fc runs the same code as 60a04cc81b (the commits after it change only docs). The pilot verdict is in
`$DISPATCH_DIR/pilots/reportasync1010.ok`. Device time for the batch: 12 x (500 s, or the disc's run, + 90 s of
setup), about 2 h, so the lane's total stays under the 3 h allowance. Judges:

- pixels: `ab_compare.py --a <A> --b <B> --expect docs/testing/predictions/reportasync1010-pixels.json --allow-same-binary`;
- NFS: `raread.py off1 on1 on2 off2 --expect docs/testing/predictions/reportasync1010-nfs.json`;
- both switches: `raread.py off1 on1 on2 off2 --expect docs/testing/predictions/reportasync1010-both.json`.

The two trace runs on the `-ts` ref answer the addendum's question. With texscan on, the report wait is the
largest it has been measured (~10.5 ms/frame, texscan1010's frametrace). The texscan + sync run measures it with
this lane's instrument, and the texscan + async run shows whether any of it stays on the finishing thread
(`wait=`, `gate=`).

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
4. Step 5 (both switches on vs both off): texscan1010 is ready but not folded, so the pair runs on
   `lane/reportasync1010-ts` (this branch merged with `origin/lane/texscan1010`; a merge, not a rebase), with
   `docs/testing/predictions/reportasync1010-both.json` (warm countdown on <= 34 ms, post-GO on <= 34 ms, v2 up
   >= 15 points), 2 runs per arm, plus one report-trace run per path with texscan on.
5. Re-registration (attempt 2): the pixel and NFS legs were registered on 2e9f535300 before the merge. They are
   re-registered on ba9a6df8fc with the same thresholds. The one change is the direction-neutral start-validity
   rule above. The pilot's sync cold start (47.1 ms) sits below the NFS leg's registered off band for cold
   (54-64 ms). The band is kept as registered; if the off arms read the same, C fails on its off band, and PR.md
   says so.

## 4. For the next lane

- A route input that hangs in adb (WSL vsock) loses the input but not the run, and the start then races from a
  menu (pilot go4, go9). Read `run.log` for a ROUTE press/axis line followed by a gap over 3 s, or one marked
  failed. `raread.py`'s `bad_starts()` does it. A pace reader that does not check this scores a menu as a race
  start.
- The trace's `next` histogram tops out at 66.7 ms. NFS's report slots come back later than that, so the
  bucket says only ">= 4 frames".

- `phaseread.py` (nfs30plan1010) prints nothing on the plain build: it returns before the pace line when no
  phase line is in the window. `raread.py` reads pace alone.

## 5. Attempts

- **Attempt 1 (2026-10-10) did not finish because it was waiting on the pilot, as it should have.** It built
  both switches, registered the pixel and NFS predictions on 2e9f535300, queued the two step-1 trace runs, and
  ended its turn with them in `WAITING`. The pilot gate allows no more than 30 min of device time before a
  reviewed pilot, and the scored arms needed the pilot's answer first: does the async path survive 12 starts, and
  what does step 1 say. Nothing failed.
- **Attempt 2 (this one), on resume:**
  - read the pilot (section 2) and wrote the pilot verdict;
  - merged master forward (pfifowait1009 folded);
  - fixed `raread.py`'s scoring of hung-input starts;
  - re-registered both legs on the merged ref;
  - built `lane/reportasync1010-ts` for step 5 and registered its pair;
  - queued the 12-run batch above;
  - ended waiting on it (`WAITING`).
