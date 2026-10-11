# lane.reportasync1010: the occlusion report written after the fence, off the pacing thread (#433, 0.5)

Step 2 of `docs/lanes/nfs30plan1010/PLAN.md`. Base: master @ 9fd2608f8f (perdraw1009 and perdrawon1010
folded), merged forward to master @ c829b64c8e (60a04cc81b: pfifowait1009, nfsframe1010, nfs30plan1010 and
forzasurf1010 folded; `reports.c` auto-merged, pfifowait's default-off `HAKUX_PFIFOWAIT` kept, unset in every run
here), and again to master @ d758e39a59 (f111e7227d) before the armed gate (477893cdbf, section 1), and to
master @ c271f515b4 (a21a3361d9) for the addendum-2 frametrace pair; `git diff 477893cdbf a21a3361d9` touches no
emulator code. After the pair ran it was merged to master @ 071aea27ff (140930dc16). That merge brings
gpupass1010's `kTitleRenderModes` row, which renders NFS Most Wanted in sysmem; no run in this lane had it. The both-switches pair (brief step 5) runs on `lane/reportasync1010-ts` @ 3cd9d6b7e3: this branch @ ba9a6df8fc merged
with `origin/lane/texscan1010` @ 227a161cc2, because texscan1010 had not folded when the pair was queued. That
branch is a build ref only, with no PR of its own; nothing from it folds through this PR.

**Where this stands (attempt 5): done, `State: ready`.**

- The NFS A/B fails its registered prediction on one check of six, by 0.2 ms. The warm countdown on is 38.2 ms
  against a bound of <= 38.0.
- The both-switches pair fails 4 of 8. Async takes the race start from about 41 to about 37.5 ms: it removes the
  report wait in texscan's configuration too, but it does not reach the plan's 34 ms (section 2).
- The pixel leg fails mechanically, on the two rows known to flicker. Its runs=3 determinism check reads every
  mover as flicker inside one arm, none as the switch. ZPass is byte-identical.
- The armed gate (477893cdbf) holds: its ZPass check PASSES (72 of 72 byte-identical, the gate engaged on
  every ZPass report), and the gated NFS run keeps 0 report waits on the finishing thread over 12 valid starts.
- The three conditions of the default-on recommendation hold (section 6).
- Addendum 2's frametrace pair (`-3857080` alone, `-3857196` with `HAKUX_REPORT_ASYNC=1 HAKUX_TEXSCAN=1`)
  fails its prediction 4 of 5. F fails because the rule counted the slot-rotation fence along with the report
  fence; the report fence's own sites are gone from the pacing thread on B (section 2, "Addendum 2").
- **Once the report wait is gone, on-CPU work on the pacing thread is over half the period**: 58 % of a heavy
  warm frame (`p_run` 27.5 of 47.3 ms), with recording (`Draw`) about half of that. Waiting for the guest
  (`pidle`) is 32 %. Cube faces are 0, other fences and waits 8 %.
- The pacing thread alone overruns 2 VBLANKs on only a third of B's heavy frames. The guest overruns on 58 %:
  it now waits 7.3 ms per heavy frame for `pfifo.lock` to store DMA_PUT, against 0.09 ms on A. That wait has
  no measured holder. It is the next lane's measurement (section 4).

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

### The armed gate (477893cdbf): only reports the guest will poll are deferred

The step-1 trace (section 2) settled what the async write costs a guest. The write lands after the guest's next
flip on 98.8 % of NFS's reports, so the async path is safe only for a guest that waits for the status word.
NFS does: it writes `0xffffffff` to the status word before every GET_REPORT. A guest that leaves the status
at 0 has nothing to wait on, and if it reads the count after a semaphore or a PGRAPH idle wait, it can read
it before the reader has written it. The ZPass pgraph test is that guest: it zeroes the report memory
(`zpass_pixel_count_tests.cpp:81`) and never arms it. It came out byte-identical on the ungated build
(section 2), but by timing, not by any guarantee.

So the finish now reads each report's status word as it hands the batch over (`ra_internal()`; the guest
address is already resolved there). A batch holding any report whose status word is 0 (DONE) when the finish
runs is not handed to the reader. The finishing thread first waits for the reader to go idle, then for that
batch's own slot fence, then writes the batch before the finish returns. That is the synchronous path's
order, minus its wait on every other submitted frame. Rule 1 still holds: a batch reads only its own
slot, after its own slot's fence. The trace counts this wait as `wait=` (with `HAKUX_REPORT_TRACE=1`). Armed
batches go to the reader as before.

What it costs: one 32-bit guest load per report at the finish. On NFS nearly every report is armed: 4,692 of
4,692 on the texscan + async trace (`1-1791659727-reportasync1010-553973`), 99.9 % on the async pilot. So the gate
should engage only on that 0.1 %, a handful of batches per run. It does:

- On NFS (`1-1791667691-reportasync1010-3049912`, gated build, trace on), the finishing thread made 0 report waits
  and 2 slot-gate waits (0.1 ms in all) over 4,583 reports. Every start was valid (12 of 12), and `armed` was
  4,581 of 4,581.
- On the ZPass test (`reportasync1010-gate-zpass.json`, PASS), every `[rtrace] w` line of B
  (`1-1791667684-reportasync1010-3047961`) reads `armed=0` and `wait=` equal to its report count (for example
  `n=5 ... wait=5/1691`). The gate wrote every report synchronously, and all 72 captures are byte-identical to A.

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
  SEMAPHORE_RELEASE, `WaitForGPU`, spin on the semaphore, print the report). The armed gate covers a guest
  that leaves the status at 0. **It does not cover a guest that arms the status word and then reads the count
  without polling it**, or one that arms a slot again before the previous write landed: such a guest could see
  the old count, or a stale DONE. NFS does neither (`reuseb4w` 0 on every trace run; it polls). No other
  title has been traced.
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
  and PGRAPH idle, then reads. It was byte-identical on the ungated build ("Pixel leg" below), and the armed
  gate (section 1) now makes that a guarantee rather than a matter of timing.

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

### Pixel leg (27-suite disc, ba9a6df8fc, one binary, on vs off)

`ab_compare.py --a 1-1791659700-reportasync1010-546194 --b 1-1791659693-reportasync1010-543406 --expect
docs/testing/predictions/reportasync1010-pixels.json --allow-same-binary` gives **FAIL: 8 of 1,060 checks
violated**. Every mover is in a row this disc is known to flicker on within one state (perdrawon1010 NOTES 3;
pfifowait1009 NOTES 7a), named in the registered prediction:

| capture | A (off) | B (on) |
|---|---|---|
| Stencil/Stencil_REPLACE_ST_DT | 30,000 | 0 |
| Stencil/Stencil_REPLACE_ST_DT_ZB | 30,000 | 0 |
| Vertex_shader_rounding_tests/GeometrySuperscreen_0.0010 | 800 | 0 |
| ..._0.4999 / _0.5624 / _0.5626 | 0 / 0 / 0 | 800 / 400 / 570 |
| ..._0.9990 / _1.0000 | 285 / 0 | 570 / 570 |

**ZPass_pixel_count: all 72 captures byte-identical.** The pfifowait mover (`Stencil_ZERO_ST_DT*`, 30,000 px,
attributable) did not move. The registered prediction requires a runs=3 determinism check on both arms before
any mover is read as the switch.

**The determinism check: every mover is flicker.** It ran `1-1791667080-reportasync1010-2775483` (A, off) and
`1-1791667081-reportasync1010-2775900` (B, `HAKUX_REPORT_ASYNC=1`): Stencil and Vertex shader rounding tests,
runs=3, ba9a6df8fc. `ab_compare.py --allow-same-binary` reports no capture moved outside its measured band (0
better, 0 worse, 63 same, 4 noise of 67). Differing pixels per run, for every capture that moved in either check
(A0/B0 are the pixel leg's single runs):

| capture | A1 | A2 | A3 | B1 | B2 | B3 | A0 | B0 |
|---|---|---|---|---|---|---|---|---|
| Stencil_REPLACE | 40,000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Stencil_REPLACE_ST | 30,000 | 0 | 0 | 0 | 0 | 0 | 30,000 | 30,000 |
| **Stencil_REPLACE_ST_DT** | 30,000 | 30,000 | 30,000 | 30,000 | 30,000 | 30,000 | 30,000 | **0** |
| **Stencil_REPLACE_ST_DT_ZB** | 0 | 30,000 | 30,000 | 30,000 | 30,000 | 30,000 | 30,000 | **0** |
| Stencil_REPLACE_ST_ZB | 30,000 | 0 | 0 | 0 | 0 | 0 | 30,000 | 30,000 |
| Stencil_ZERO | 40,000 | 40,000 | 0 | 0 | 0 | 0 | 40,000 | 40,000 |
| Stencil_ZERO_DT | 0 | 0 | 40,000 | 40,000 | 40,000 | 40,000 | 40,000 | 40,000 |
| Stencil_ZERO_ST | 0 | 0 | 0 | 0 | 30,000 | 0 | 30,000 | 30,000 |
| Stencil_ZERO_ST_DT | 30,000 | 0 | 30,000 | 0 | 30,000 | 30,000 | 30,000 | 30,000 |
| Stencil_ZERO_ST_DT_ZB | 30,000 | 0 | 30,000 | 0 | 0 | 30,000 | 30,000 | 30,000 |
| Stencil_ZERO_ST_ZB | 0 | 0 | 0 | 0 | 0 | 0 | 30,000 | 30,000 |
| **GeometrySuperscreen_0.0010** | 0 | 0 | 0 | 0 | 400 | 0 | **800** | 0 |
| **GeometrySuperscreen_0.4999** | 0 | 0 | 0 | 0 | 0 | 112 | 0 | **800** |
| GeometrySuperscreen_0.5000 | 0 | 0 | 0 | 0 | 0 | 400 | 0 | 0 |
| **GeometrySuperscreen_0.5624** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **400** |
| **GeometrySuperscreen_0.5626** | 0 | 0 | 285 | 0 | 0 | 0 | 0 | **570** |
| **GeometrySuperscreen_0.9990** | 0 | 0 | 570 | 0 | 0 | 0 | 285 | **570** |
| **GeometrySuperscreen_1.0000** | 0 | 0 | 0 | 426 | 285 | 0 | 0 | **570** |

The pixel leg's eight movers are in bold. None separates the arms: each takes both values within one arm,
or the six determinism runs agree with each other and only the pixel leg's single run differs.

- **Stencil_REPLACE_ST_DT** is 30,000 on all six determinism runs, on and off. B0's 0 was the outlier.
- **Stencil_REPLACE_ST_DT_ZB** takes 0 on A1 and 30,000 on A2 and A3, within the off arm.
- **The GeometrySuperscreen captures** differ on one or two runs, in either arm, and match on the rest: 0.0010
  on B2, 0.4999 on B3, 0.5626 and 0.9990 on A3, 1.0000 on B1 and B2. 0.5624 differs on none of the six.

So the leg's registered verdict stays FAIL, 8 of 1,060, and every mover is flicker, not the switch.

### NFS A/B (brief step 4, ba9a6df8fc, plain build, off/on/on/off)

`raread.py off1 on1 on2 off2 --expect docs/testing/predictions/reportasync1010-nfs.json` gives **FAIL: 5 of 6
checks hold**. Every run reached 12 valid starts.

| run | arm | cold start 1 | warm countdown | warm v2 / v3 / v4 | post-GO warm |
|---|---|---|---|---|---|
| `1-1791659702-reportasync1010-546475` | off1 | 62.4 ms | 41.8 ms | 52 / 45 / 2 % | 39.9 ms (25.1 fps) |
| `1-1791659703-reportasync1010-547266` | on1 | 51.4 ms | 38.0 ms | 73 / 24 / 1 % | 35.2 ms (28.4 fps) |
| `1-1791659705-reportasync1010-547898` | on2 | 51.9 ms | 38.4 ms | 71 / 27 / 1 % | 35.5 ms (28.1 fps) |
| `1-1791659706-reportasync1010-548438` | off2 | 57.6 ms | 41.2 ms | 54 / 43 / 2 % | 39.0 ms (25.6 fps) |

| check | registered | measured | |
|---|---|---|---|
| W warm off | in [39, 44] | 41.5 ms | PASS |
| **W warm on** | **<= 38.0** | **38.2 ms** | **FAIL, by 0.2 ms** |
| W on - off | <= -2.5 | -3.3 ms | PASS |
| C cold off | in [54, 64] | 60.0 ms | PASS |
| C cold on | <= 55 | 51.6 ms | PASS |
| H warm v2 share | +10 points | 53 -> 72 %, +19.4 | PASS |

Post-GO warm (not a registered check) goes from 39.45 to 35.35 ms pooled, 25.3 -> 28.3 fps.

**Frames.** The `s*-g11` frames of all four runs (48 starts) show a moving player at every mark, 33-84 mph.
None shows a missing car or a popping prop.

### Both switches (brief step 5, 3cd9d6b7e3: `HAKUX_TEXSCAN=1 HAKUX_REPORT_ASYNC=1` vs both off)

`raread.py off1 on1 on2 off2 --expect docs/testing/predictions/reportasync1010-both.json` gives **FAIL: 4 of 8
checks hold**. Every run reached 12 valid starts.

| run | arm | cold start 1 | warm countdown | warm v2 / v3 / v4 | post-GO warm |
|---|---|---|---|---|---|
| `1-1791659722-reportasync1010-552321` | off1 | 58.2 ms | 41.0 ms | 55 / 42 / 1 % | 40.8 ms (24.5 fps) |
| `1-1791659723-reportasync1010-552662` | on1 | 47.4 ms | 37.2 ms | 70 / 21 / 2 % | 35.1 ms (28.5 fps) |
| `1-1791659725-reportasync1010-552924` | on2 | 50.3 ms | 37.9 ms | 69 / 22 / 2 % | 35.3 ms (28.3 fps) |
| `1-1791659726-reportasync1010-553359` | off2 | 60.6 ms | 41.1 ms | 55 / 41 / 2 % | 39.9 ms (25.1 fps) |

| check | registered | measured | |
|---|---|---|---|
| W warm off | in [39, 44] | 41.0 ms | PASS |
| **W warm on** | **<= 34.0** | **37.5 ms** | **FAIL** |
| **W on - off** | **<= -5.0** | **-3.5 ms** | **FAIL** |
| C cold off | in [44, 64] | 59.4 ms | PASS |
| C cold on | <= 55 | 48.8 ms | PASS |
| **H warm v2 share** | **+15 points** | **55 -> 70 %, +14.8** | **FAIL** |
| P post-GO warm off | in [37, 43] | 40.3 ms | PASS |
| **P post-GO warm on** | **<= 34.0** | **35.2 ms** | **FAIL** |

**Frames.** In the `s*-g11` frames, 46 of 48 starts show a moving player (35-91 mph). The two that do not are
both cold first starts: off1 s1 reads 0 mph and on2 s1 reads 9 mph (the car is against the wall or recovering).
Neither enters a scored warm or post-GO window: start 1 is scored only on its countdown, before GO.

**What this says about texscan's default.** The plan's step 1 + 2 prediction was 30 fps (<= 34 ms) at the
warm countdown and post-GO. It does not hold. The two pairs ran on different refs at different times, so the
comparison below is not matched, but their off arms agree to within 0.5 ms warm and 0.9 ms post-GO:

| | async alone (NFS A/B on) | texscan + async (both on) | difference |
|---|---|---|---|
| warm countdown | 38.2 ms | 37.5 ms | -0.7 ms |
| post-GO warm | 35.35 ms | 35.2 ms | -0.15 ms |

With async on, texscan no longer costs anything; it gains at most 0.7 ms, which is inside the run-to-run spread
of a pair. Without async, it costs about 5 ms: the texscan + sync trace run below reads 45.8 ms warm, and the
sync pilot 40.6 ms, both with the trace on. texscan1010 measured the same loss (46.6 -> 49.2 ms). So texscan's
default must follow async's. Turning texscan on alone loses fps on NFS. Turning it on with async is neutral at
the race start, with the cube-face downloads gone.

What holds the race start at about 37 ms once the report wait is gone: addendum 2 below.

### The addendum's question: does async remove the wait with texscan on

Two trace runs on 3cd9d6b7e3, both with `HAKUX_TEXSCAN=1 HAKUX_REPORT_TRACE=1`, not scored. Read with
`raread.py <async> <sync>`, race starts only:

| per GET_REPORT | texscan + sync (`1-1791659729-reportasync1010-554366`) | texscan + async (`1-1791659727-reportasync1010-553973`) |
|---|---|---|
| reports written | 3,490 | 4,692 |
| queued -> written, < 16.7 / < 33.3 ms | 46.1 / 100 % | 49.5 / 100 % |
| `late` | 0 % | 97.3 % |
| `reuseb4w` | 0 | 0 |
| `armed` | 3,491 of 3,491 | 4,692 of 4,692 |
| **finishing thread: report waits** | **3,490, 50,642 ms (14.5 ms each)** | **0** |
| finishing thread: rule-3 gate waits | 0 | 285, 22.2 ms |
| warm countdown / post-GO warm (trace on) | 45.8 / 48.0 ms | 36.9 / 35.3 ms |

**Yes.** With texscan on, the sync report wait is 14.5 ms per report, larger than texscan1010's ~10.5 ms
frametrace figure. This lane's instrument times the whole wait, including `vkGetQueryPoolResults`. Async takes it
to zero on the finishing thread. What is left there is the rule-3 gate: 285 waits, 22 ms over all 12 starts.

### Addendum 2: where the ~37 ms period goes once the report wait is gone

Two NFS race-start soaks on a21a3361d9 (the armed gate, merged with master), route `nfs-mw-quickrace`, 500 s,
Nova, perflog, `--pull 'frametrace_*'`:

- A, `1-1791671433-reportasync1010-3857080`: `HAKUX_FRAMETRACE=1`;
- B, `1-1791671434-reportasync1010-3857196`: `HAKUX_FRAMETRACE=1 HAKUX_REPORT_ASYNC=1 HAKUX_TEXSCAN=1`.

Registered before either ran: `docs/testing/predictions/reportasync1010-ftpair.json` (2026-10-10T22:31:00Z),
judged by `ftpair.py` (this dir). The judge splits the PFIFO thread's frametrace row, which sums to the period, as
in nfsframe1010's and nfs30plan1010's tables:

    P = p_run + p_rq + p_blk,  p_blk = pidle + p_c_rep + p_oth_hk + unhooked

The brief's four buckets map onto it like this:

| brief's bucket | row | what it is |
|---|---|---|
| recording | `p_run`, phase `Draw` (`phaseread.py`) | on-CPU method processing and Vulkan recording on the pacing thread |
| cube faces | `unhooked` | the sd finishes' `finish_event` wait (gone on B, where texscan has no sd finishes), plus `wait_frame_submitted` and the rule-3 gate |
| other fences | `p_oth_hk`, and `p_c_rep` (the report fence) | hooked waits at fence, submit, download and lock sites |
| vblank quantization | `pidle` | waiting for the guest's next frame: the VBLANK grid, plus guest CPU work |

Predicted (rules F, U, P, R):

- **F:** the report fence `p_c_rep` is >= 2.5 ms/frame on A and <= 0.5 on B, at the warm countdown.
- **U:** `unhooked` falls by >= 4 ms/frame from A to B.
- **P:** the period falls by >= 2.5 ms.
- **R:** on B, `p_run` is >= 50 % of the period: the residual is CPU work on the pacing thread, not a wait.
  Recording is its largest named part, `pidle` the second-largest row, other fences <= 1 ms.

**Verdict: FAIL, 4 of 5.** Both runs DONE, 12 of 12 marks, 0 bad starts. Every `s*-g11` frame of both runs (24
starts) shows a moving car, at about 30 mph or more.

| check | registered | measured (warm countdown, all frames) | |
|---|---|---|---|
| V | 12 marks, >= 10 valid starts, >= 300 warm frames, env, perflog | 12 / 12 marks, 0 / 0 bad, 721 / 859 frames | PASS |
| **F** | **`p_c_rep` A >= 2.5, B <= 0.5** | **A 4.43, B 0.92** | **FAIL** |
| U | `unhooked` A - B >= 4.0 | 9.64 - 2.49 = 7.14 | PASS |
| P | period B - A <= -2.5 | 53.60 -> 44.81, -8.78 | PASS |
| R | B `p_run` / P >= 50 % | 27.08 / 44.81 = 60 % | PASS |

**Why F fails: the rule's row is a context, not a site.** `p_c_rep` is every hooked wait the PFIFO thread
makes inside `pgraph_process_pending_reports`. The frametrace site table (`[hakuX-ft1] site ... row=p` in each
`logcat.txt`) shows what is in it:

- A: the report fence, `pgraph_vk_process_pending_reports_internal+0xd54` (#1) and `+0xc8c` (#26), and the slot
  rotation fence, `pgraph_vk_finish+0x1330` (#55);
- B: the rotation fence only, `pgraph_vk_finish+0x1330` (#34). That is `vkWaitForFences` on the next frame
  slot (draw.c:5234), in the end-of-frame finish that `pgraph_process_pending_reports` runs. Neither report-fence
  site appears on B's PFIFO row.

So the report fence is off the pacing thread on B. What F measured on B is the rotation fence, at 0.92 ms. The
verdict stands as registered: re-registering the rule on the site would fit it to the data.

**The two runs in nfsframe1010's window table** (`raread.py`, pace lines; perflog builds):

| window | A (`-3857080`), frametrace alone | B (`-3857196`), + async + texscan |
|---|---|---|
| cold start, countdown | 52.9 ms (18.9 fps), v2/v3/v4 38/23/38 % (1 line) | 50.9 ms (19.6 fps), 34/50/16 % (2 lines) |
| warm restarts, countdown | 47.7 ms (21.0 fps), 30/54/15 % (13 lines) | 41.7 ms (24.0 fps), 49/42/3 % (13 lines) |
| post-GO warm | 44.3 ms (22.6 fps), 38/53/7 % (43 lines) | 38.0 ms (26.3 fps), 59/31/1 % (53 lines) |

The perflog + frametrace build runs about 4 ms slower than this lane's plain-build runs with the same switches:
both-switches on read 37.5 ms warm and 35.2 ms post-GO (`-552662`, `-552924`).

**Per heavy frame (vb >= 3), side by side** (`ftpair.py` and `ftbuckets.py`, ms per frame; share = B's share
of its period):

| row | A warm | B warm | B share | A post-GO | B post-GO | B share |
|---|---|---|---|---|---|---|
| frames | 711 | 499 | | 1,378 | 864 | |
| **P, the period** | **53.68** | **47.34** | 100 % | **48.88** | **42.43** | 100 % |
| *PFIFO thread (paces the frame)* | | | | | | |
| `p_run`, on CPU | 28.18 | 27.48 | **58 %** | 24.84 | 24.12 | **57 %** |
| `p_rq`, runnable | 0.72 | 0.81 | 2 % | 0.57 | 0.82 | 2 % |
| `pidle`, waiting for the guest's next push | 10.66 | 15.21 | 32 % | 10.51 | 15.27 | 36 % |
| `p_c_rep`, hooked waits in pending_reports | 4.44 | 1.06 | 2 % | 4.74 | 0.93 | 2 % |
| `p_oth_hk`, other hooked waits | 0.04 | 0.02 | 0 % | 0.04 | 0.06 | 0 % |
| `unhooked` | 9.64 | 2.76 | 6 % | 8.18 | 1.24 | 3 % |
| busy, P - `pidle` | 43.0 | 32.1 | | 38.4 | 27.2 | |
| *guest vCPU* | | | | | | |
| work, `v_run` - `gidle` + `v_rq` | 24.0 | 25.8 | | 21.9 | 22.2 | |
| `gidle`, the guest's idle loop | 24.0 | 11.8 | | 21.3 | 12.3 | |
| `v_blk` | 5.7 | 9.8 | | 5.7 | 8.0 | |
| of which `lockw` (DMA_PUT, `pfifo.lock`) | **0.09** | **7.31** | | **0.08** | **5.57** | |
| busy, work + `v_blk` | 29.7 | 35.6 | | 27.6 | 30.1 | |
| *off the pacing thread* | | | | | | |
| `o_fence` (render thread; on B also the reader) | 9.62 | 27.79 | | 8.24 | 23.55 | |
| GPU busy | 13.04 | 19.36 | 41 % | 11.78 | 16.08 | 38 % |
| v2 / v3 / v4+ | 0/78/22 % | 0/94/6 % | | 0/90/10 % | 0/97/3 % | |

The phase line has no per-frame form: its fields are per-flip EMAs over every frame in the window, heavy or not
(`phaseread.py --window=-2,1.5` and `--window=1.5,12`). Heavy frames are 58 % of B's warm frames and 99 % of A's,
so B's phases below understate its heavy frames a little:

| phase (all frames, EMA) | A warm | B warm | A post-GO | B post-GO |
|---|---|---|---|---|
| G, the phase lines' period | 54.3 | 45.1 | 42.9 | 36.7 |
| Surf | 1.8 | 1.8 | 1.3 | 1.3 |
| **Draw, recording** | **15.0** | **14.1** | **11.4** | **10.6** |
| of which Syn / Pipe (Sh) / Desc / Setup / Mfp | 3.9 / 5.7 (3.6) / 0.5 / 1.1 / 1.9 | 3.6 / 5.1 (3.3) / 0.6 / 1.0 / 1.8 | 2.8 / 4.6 (2.8) / 0.4 / 0.9 / 1.2 | 2.6 / 4.2 (2.6) / 0.4 / 0.8 / 1.2 |
| Fin (Sub / Fen) | 15.7 (9.9 / 1.2) | 2.6 (0.2 / 2.4) | 12.3 (7.0 / 1.1) | 1.9 (0.1 / 1.7) |
| Idle (Fr / St) | 11.5 (10.3 / 1.2) | 13.2 (12.1 / 1.1) | 10.3 (9.3 / 1.1) | 14.4 (13.1 / 1.2) |
| outside every phase, G - Tot | 10.2 | 13.3 | 7.4 | 8.5 |
| GPU (R / X) | 13.1 (12.6 / 0.5) | 19.2 (12.7 / 6.5) | 10.0 (9.5 / 0.5) | 13.1 (9.3 / 3.9) |
| finishes per 60 frames: sd / stl | 90 / 73 | 0 / 89 | 90 / 74 | 0 / 83 |
| texture sync downloads, ms/frame | 4.2 | 0.0 | 4.2 | 0.0 |

**Where B's period goes, by the brief's four buckets** (per heavy warm frame, P 47.34 ms; post-GO heavy, P 42.43,
in brackets):

| bucket | ms | share | evidence |
|---|---|---|---|
| **recording and the rest of the pacing thread's CPU work** (`p_run`) | 27.48 [24.12] | **58 % [57 %]** | over half |
| of which recording (`Draw`) | about 14.1 [10.6] | about 30 % [29 %] of G | phase line, all frames |
| of which the rest: method parsing and the pusher, `Surf`, finish CPU | about 13.4 | about 28 % | `p_run` - `Draw` |
| **vblank quantization, and waiting for the guest** (`pidle`) | 15.21 [15.27] | 32 % [36 %] | `Fr` 12.1 of `Idle` 13.2 is after a flip |
| **cube faces** (sd finish waits) | 0 | 0 % | sd 0 per 60 frames, from 90 on A |
| **other fences and waits** | 3.84 [2.23] | 8 % [5 %] | |
| of which the slot rotation fence (#34, draw.c:5234) | 1.06 [0.93] | 2 % | `p_c_rep` |
| of which `wait_frame_submitted` and the rule-3 gate | 2.76 [1.24] | 6 % [3 %] | `unhooked`: B has no sd finish |
| run queue (`p_rq`) | 0.81 [0.82] | 2 % | |

`p_run`'s share is an upper bound for the plain build: the perflog clock reads sit on the pacing thread. If the
whole ~4 ms perflog gap (41.7 against 37.5 ms warm) came out of `p_run`, the share would still be 56 %.

**Which side misses the second VBLANK** (`ftbuckets.py`, heavy frames). Per frame, each thread's busy time
(PFIFO: P - `pidle`; guest: work + `v_blk`) against 2 VBLANKs of that frame's own VBLANK period:

| share of heavy frames whose busy time > 2 VBLANKs | A warm | B warm | A post-GO | B post-GO |
|---|---|---|---|---|
| PFIFO thread | 100 % | 33 % | 84 % | 17 % |
| guest | 18 % | 58 % | 6 % | 30 % |
| guest, `lockw` taken out (a bound) | 17 % | 8 % | 5 % | 5 % |
| either | 100 % | 72 % | 84 % | 37 % |
| either, `lockw` taken out (a bound) | 100 % | 37 % | 84 % | 19 % |

- On A, the pacing thread alone overran 2 VBLANKs on every warm heavy frame: 43 ms busy, with the report fence
  and the cube-face round trips inside it.
- On B it overruns on a third. The guest overruns on 58 %, and the difference is `lockw`. The vCPU now waits
  7.3 ms per heavy frame to take `pfifo.lock` and store DMA_PUT (user.c:92-95), against 0.09 ms on A. On A the
  guest pushed its frame and waited (`gidle` 24 ms). On B it runs alongside the PFIFO thread and meets the lock
  that thread holds for three things:
  - while it parses the pushbuffer (`pfifo_run_pusher`, pfifo.c:2133; the fast dispatch
    `pgraph_method_try_fast` runs with the lock held, pfifo.c:1768-1778);
  - in `pgraph_process_pending` (2125);
  - in the end-of-frame finish inside `pgraph_process_pending_reports` (2163), rotation fence and
    `wait_frame_submitted` included.
- A second instrument agrees. The perflog `hakuX-cpu` line's `Lw` is the same `lock_wait_ns`, as a per-flip EMA
  (profile.c:128-185). It reads about 6.6 ms per frame on B's warm countdown and 3.0 post-GO, and 0.0 on A.
  `phaseread.py` prints these as 0.11 and 0.05 because it divides by 60 again (section 4).
- Frametrace attributes no holder to this wait (`hakux_ft_attribute`: "the DMA_PUT wait seen only by
  lock_wait_ns ... UNATTR (no holder)"). So which of those holds costs the guest is not measured. The
  "`lockw` taken out" rows are a bound: they assume the wait would vanish with nothing in its place.
- On B post-GO, 63 % of the heavy frames have neither thread over 2 VBLANKs. Those lose the third VBLANK at the
  handoff: the guest's push arrives too late in the frame for the PFIFO thread's work to finish in time.

**Two more readings, neither a limit:**

- **The GPU** is 41 % of B's heavy warm frame (19.4 ms). Its render passes are unchanged (R 12.6 -> 12.7). Time
  outside render passes rises from 0.5 to 6.5 ms (X): one command buffer per frame now carries the copies the
  sd finishes used to submit on their own. This reader does not split X further.
- **Frametrace's `cls` column is not comparable between A and B.** It judges each frame against D = `ireq` x
  VBLANK. `ireq` is inferred: the smallest VBLANK count that at least 5 % of the last 256 flips used
  (profile.h `ft_ireq`). B's flips take 1 VBLANK often enough (6 % warm, 9 % post-GO), so `ireq` reads 1 on 86 %
  of B's heavy frames, against 2 on 97 % of A's. D halves to 16.7 ms, and any frame with guest work over that
  reads RUN (87 % of B's heavy frames). The guest's work did not change (24.0 -> 25.8 ms). The deadline the
  class compares it to did.

**The HUD at g11 is not the switch.** The race HUD's leaderboard (top right) reads differently by arm in this
lane's `s*-g11` frames:

- async-on runs show racer names: 12 of 12 starts in `-547266`, `-552662` and `-552924`, 11 in `-547898`, about 10
  in B;
- async-off runs mostly show "+NN FT" gaps: 12 of 12 in A, `-546475` and `-552321`. The two off2 runs are mixed:
  `-548438` shows names at about 4 starts, `-553359` at 1.

Four fast async-off runs from another lane separate "the switch" from "the pace": drawrec1010's `-3707918`,
`-3708043`, `-3708870` and `-3709079`, at 36-38 ms post-GO with no `HAKUX_REPORT_ASYNC`. They show names at g11 in
19 of their 20 starts s3-s7; the 20th shows an empty list. So the leaderboard follows how far the race has got
when the shot is taken, not the switch. A fixed wall time after GO is more frames on a faster run.

### Runs of this lane

| request | what | ref | env | state |
|---|---|---|---|---|
| `1-1791656656-reportasync1010-4183629` | pilot, step-1 trace, async | 2e9f535300 | `HAKUX_REPORT_TRACE=1 HAKUX_REPORT_ASYNC=1` | done, above |
| `1-1791656657-reportasync1010-4184121` | pilot, step-1 trace, sync | 2e9f535300 | `HAKUX_REPORT_TRACE=1` | done, above |
| `1-1791659693-reportasync1010-543406` | pixel leg B, 27 suites | ba9a6df8fc | `HAKUX_REPORT_ASYNC=1` | done: pixel FAIL 8/1,060, known-flaky rows |
| `1-1791659700-reportasync1010-546194` | pixel leg A, 27 suites | ba9a6df8fc | none | done: pixel leg A |
| `1-1791659702-reportasync1010-546475` | NFS A/B off1 | ba9a6df8fc | none | done: NFS FAIL 5/6 |
| `1-1791659703-reportasync1010-547266` | NFS A/B on1 | ba9a6df8fc | `HAKUX_REPORT_ASYNC=1` | done |
| `1-1791659705-reportasync1010-547898` | NFS A/B on2 | ba9a6df8fc | `HAKUX_REPORT_ASYNC=1` | done |
| `1-1791659706-reportasync1010-548438` | NFS A/B off2 | ba9a6df8fc | none | done |
| `1-1791659722-reportasync1010-552321` | both-switches off1 | 3cd9d6b7e3 | none | done: both FAIL 4/8 |
| `1-1791659723-reportasync1010-552662` | both-switches on1 | 3cd9d6b7e3 | `HAKUX_TEXSCAN=1 HAKUX_REPORT_ASYNC=1` | done |
| `1-1791659725-reportasync1010-552924` | both-switches on2 | 3cd9d6b7e3 | `HAKUX_TEXSCAN=1 HAKUX_REPORT_ASYNC=1` | done |
| `1-1791659726-reportasync1010-553359` | both-switches off2 | 3cd9d6b7e3 | none | done |
| `1-1791659727-reportasync1010-553973` | trace, texscan + async (not scored) | 3cd9d6b7e3 | `HAKUX_TEXSCAN=1 HAKUX_REPORT_ASYNC=1 HAKUX_REPORT_TRACE=1` | done: report waits 0 |
| `1-1791659729-reportasync1010-554366` | trace, texscan + sync (not scored) | 3cd9d6b7e3 | `HAKUX_TEXSCAN=1 HAKUX_REPORT_TRACE=1` | done: 14.5 ms per report |
| `1-1791667080-reportasync1010-2775483` | pixel determinism A, Stencil + VS rounding, runs=3 | ba9a6df8fc | none | done: no mover outside its band |
| `1-1791667081-reportasync1010-2775900` | pixel determinism B, Stencil + VS rounding, runs=3 | ba9a6df8fc | `HAKUX_REPORT_ASYNC=1` | done |
| `1-1791667684-reportasync1010-3047961` | gate ZPass B (`reportasync1010-gate-zpass.json`) | 477893cdbf | `HAKUX_REPORT_ASYNC=1 HAKUX_REPORT_TRACE=1` | done: PASS, 72/72 |
| `1-1791667685-reportasync1010-3048190` | gate ZPass A | 477893cdbf | none | done |
| `1-1791667691-reportasync1010-3049912` | gate on NFS, trace (not scored: `wait=` ~0, 12 starts) | 477893cdbf | `HAKUX_REPORT_ASYNC=1 HAKUX_REPORT_TRACE=1` | done: 0 report waits, 12 of 12 starts |
| `1-1791671433-reportasync1010-3857080` | addendum 2, frametrace A (`reportasync1010-ftpair.json`) | a21a3361d9 | `HAKUX_FRAMETRACE=1` (perflog) | done: ftpair FAIL 4/5 (F: rotation fence) |
| `1-1791671434-reportasync1010-3857196` | addendum 2, frametrace B | a21a3361d9 | `HAKUX_FRAMETRACE=1 HAKUX_REPORT_ASYNC=1 HAKUX_TEXSCAN=1` (perflog) | done: `p_run` 58 % of a heavy frame |

The gated NFS run (`-3049912`, trace on, not scored) reads 44.6 ms cold, 38.1 ms warm countdown (v2 71 %),
36.0 ms post-GO warm, the same as the ungated async runs. Its `s*-g11` frames show a moving player at all 12 starts
(every speedometer reads over 40 mph, sparks off the wall on some), with no missing car or popping prop.

ba9a6df8fc runs the same code as 60a04cc81b (the commits after it change only docs). The pilot verdict is in
`$DISPATCH_DIR/pilots/reportasync1010.ok`. Device time: the 12-run batch was 12 x (500 s, or the disc's run, + 90 s
of setup), about 2 h. The five attempt-3 requests added about 25 min: two short-suite runs=3 pairs, two one-suite
discs, one 500 s soak. The addendum-2 pair adds 2 x (500 + 90) s, about 20 min, for about 2 h 45 min in all, inside
the 3 h allowance. Judges:

- pixels: `ab_compare.py --a <A> --b <B> --expect docs/testing/predictions/reportasync1010-pixels.json --allow-same-binary`;
- NFS: `raread.py off1 on1 on2 off2 --expect docs/testing/predictions/reportasync1010-nfs.json`;
- both switches: `raread.py off1 on1 on2 off2 --expect docs/testing/predictions/reportasync1010-both.json`.
- determinism: `ab_compare.py --a 1-1791667080-reportasync1010-2775483 --b 1-1791667081-reportasync1010-2775900
  --allow-same-binary`, and each arm's three runs against each other: a mover that flickers within an arm is noise;
  one that separates the arms on every run is the switch;
- gate ZPass: `ab_compare.py --a 1-1791667685-reportasync1010-3048190 --b 1-1791667684-reportasync1010-3047961
  --expect docs/testing/predictions/reportasync1010-gate-zpass.json --allow-same-binary`, then
  `grep '\[rtrace\] w' <B>/logcat*.txt` for `wait=` > 0;
- gate on NFS: `raread.py 1-1791667691-reportasync1010-3049912`: `report waits` about 0, 12 valid starts.
- addendum 2: `ftpair.py $D/1-1791671433-reportasync1010-3857080 $D/1-1791671434-reportasync1010-3857196 --expect
  docs/testing/predictions/reportasync1010-ftpair.json` (`D=$DISPATCH_DIR/results`; the readers want full
  paths), then `docs/lanes/nfs30plan1010/phaseread.py <run> --window=-2,1.5` and `--window=1.5,12` on each run,
  for the recording (`Draw`) part of `p_run`, and `ftbuckets.py <A> <B>` for the vCPU row, `lockw` and the
  2-VBLANK table.

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
   (54-64 ms). The band is kept as registered. The off arms read 60.0 ms, so C passed.
6. The armed gate (attempt 3, 477893cdbf): after the step-1 table and the ungated pixel leg, unarmed batches
   are written synchronously (section 1). Registered `reportasync1010-gate-zpass.json` on 477893cdbf before
   any run of it. Queued the ZPass pair, one NFS trace run on the gated build, and the pixel leg's determinism
   check. All three hold (attempt 4).
7. Addendum 2 (attempt 4): the frametrace pair on a21a3361d9, registered as `reportasync1010-ftpair.json`
   before it was queued. Done (attempt 5): judged FAIL 4 of 5. The heavy-frame table and each bucket's share
   are in section 2 ("Addendum 2") and PR.md.

## 4. For the next lane

- A route input that hangs in adb (WSL vsock) loses the input but not the run, and the start then races from a
  menu (pilot go4, go9). Read `run.log` for a ROUTE press/axis line followed by a gap over 3 s, or one marked
  failed. `raread.py`'s `bad_starts()` does it. A pace reader that does not check this scores a menu as a race
  start.
- The trace's `next` histogram tops out at 66.7 ms. NFS's report slots come back later than that, so the
  bucket says only ">= 4 frames".

- `phaseread.py` (nfs30plan1010) prints nothing on the plain build: it returns before the pace line when no
  phase line is in the window. `raread.py` reads pace alone.
- **The next measurement: who holds `pfifo.lock` while the guest waits to store DMA_PUT.** With async and
  texscan on, the vCPU waits 7.3 ms per heavy warm frame at user.c:92-95 (0.09 without them). On B, that wait
  is what puts the guest over 2 VBLANKs on most of the heavy frames that miss (section 2, addendum 2). Frametrace
  names no holder. The PFIFO thread holds the lock for three things:
  - the pusher's parsing, and the fast dispatch with it (pfifo.c:1768-1778, 2133);
  - `pgraph_process_pending` (2125);
  - the end-of-frame finish inside `pgraph_process_pending_reports` (2163).

  A per-hold timer on those three, read against `lock_wait_ns`, decides the remedy. If the finish's waits hold
  it, the finish can drop the lock while it waits. If the parsing holds it, the guest's store needs no lock, as
  `user_read` already does (user.c:26-38). Expected size: "either thread over 2 VBLANKs" falls from 72 % to at
  most 37 % of B's heavy warm frames if the wait vanished (a bound, `ftbuckets.py`). None of this is in this
  lane's territory: user.c and pfifo.c.
- **Recording is the largest named part of the pacing thread's CPU once the waits are gone**, about 14 of
  27.5 ms per heavy warm frame (`Draw`, all-frame EMA). The other ~13 ms is method parsing, the pusher and the
  rest outside every phase timer. drawrec1010's and the vCPU JIT's lines are the ones that move it.
- `phaseread.py` (nfs30plan1010, and gpupass1010's copy) prints `hakuX-cpu`'s `Push`, `Pull` and `Lw` 60 times
  too small. Those fields are already per flip: profile.c:128-185 smooths each flip's counters and resets them.
  The reader divides by 60 as if they summed 60 flips (phaseread.py:143-145). Multiply its output by 60.
- A frametrace rule keyed on a context (`p_c_rep`) counts every wait made inside it. addendum 2's F rule caught
  the slot rotation fence (draw.c:5234) along with the report fence. Key a rule on the site's `sym=` in the
  site table instead.
- Frametrace's `cls` is judged against an inferred `ireq` (profile.h `ft_ireq`). A change that makes 5 % of
  flips take one VBLANK flips `ireq` from 2 to 1 and reclassifies most frames as RUN. Compare `ireq` before
  comparing `cls` across two runs.
- Master now renders NFS Most Wanted in sysmem (gpupass1010's `kTitleRenderModes` row, folded at 071aea27ff).
  No run here had it. GPU busy was 41 % of B's heavy frame, so it should not move the buckets above. A new
  race-start measurement on master still runs a different build from these.
- The pixel disc's Stencil and GeometrySuperscreen rows flicker run to run with no switch at all (the
  determinism table, section 2). A one-run A/B of any switch on that disc will show movers there. Ask for runs=3
  on both arms before reading one.
- Do not run texscan without async on NFS: texscan + sync reads 45.8 ms warm against 40.6 for sync alone
  (both with the trace on; texscan1010 measured the same loss). It only pays together with async.
- The NFS A/B misses its warm bound by 0.2 ms (38.2 vs <= 38.0), with every other check holding. The bound came
  from the plan's arithmetic. Re-registering a looser bound and re-running the same pair would only fit the bound
  to the data; the direction and size (-3.3 ms warm, -4.1 ms post-GO, +19 points v2) are already measured.
- The trace's `[rtrace] w` lines go to `hakuX-lane`. In a disc run they land in `logcat1.txt`; in a soak they
  land in `logcat.txt`. `raread.py` reads only `logcat.txt`.

## 5. Attempts

- **Attempt 1 (2026-10-10) did not finish because it was waiting on the pilot, as it should have.** It built
  both switches, registered the pixel and NFS predictions on 2e9f535300, queued the two step-1 trace runs, and
  ended its turn with them in `WAITING`. The pilot gate allows no more than 30 min of device time before a
  reviewed pilot, and the scored arms needed the pilot's answer first: does the async path survive 12 starts, and
  what does step 1 say. Nothing failed.
- **Attempt 2 (2026-10-10), on resume:**
  - read the pilot (section 2) and wrote the pilot verdict;
  - merged master forward (pfifowait1009 folded);
  - fixed `raread.py`'s scoring of hung-input starts;
  - re-registered both legs on the merged ref;
  - built `lane/reportasync1010-ts` for step 5 and registered its pair;
  - queued the 12-run batch above;
  - ended waiting on it (`WAITING`).
- **Attempt 2 did not finish because it was waiting on its 12 Nova runs, as it should have.** They were queued
  behind texscan1010's and drawrec1010's runs, and the session could not outlive them. Nothing failed.
- **Attempt 3 (this one), on resume:**
  - read all 12 runs and judged the three predictions: NFS FAIL 5/6 (by 0.2 ms), both switches FAIL 4/8,
    pixels FAIL on the known-flaky rows (section 2);
  - answered the addendum: async removes the 14.5 ms-per-report wait with texscan on;
  - checked the moving player in every scored start from the g11 frames;
  - queued the pixel leg's determinism check, as its prediction requires;
  - added the armed gate (477893cdbf), so that a guest that does not poll the status word keeps the synchronous
    write, after merging master @ d758e39a59;
  - registered the gate's ZPass prediction and queued it, with one NFS trace run on the gated build;
  - ended waiting on those five runs (`WAITING`).
- **Attempt 3 did not finish because it was waiting on its five Nova runs, as it should have.** Its last commit
  (ef01dfd3b5, 14:34 PDT) put them in `WAITING`. The brief's addendum 2 (14:51 PDT) came after that commit, so
  the frametrace pair it asks for was not yet part of the work. Nothing failed.
- **Attempt 4 (this one), on resume:**
  - read the five runs: the determinism check reads every pixel-leg mover as flicker; the gate's ZPass
    prediction PASSES; the gated NFS run keeps 0 report waits at 12 valid starts, with a moving player at every
    start (section 2);
  - merged master @ c271f515b4 (a21a3361d9);
  - wrote `ftpair.py` and registered `reportasync1010-ftpair.json` on a21a3361d9;
  - queued the addendum-2 frametrace pair, and ends waiting on it (`WAITING`).
- **Attempt 4 did not finish because it was waiting on its two frametrace runs, as it should have.** Both were
  queued on the Nova (`WAITING`) and could not finish inside the session. Nothing failed.
- **Attempt 5 (this one), on resume:**
  - judged the pair: FAIL 4 of 5. F caught the rotation fence; the report-fence sites are gone from B's
    pacing thread;
  - wrote the heavy-frame tables and the bucket shares (section 2, addendum 2). `p_run` is 58 % of B's heavy
    warm frame, over half;
  - added `ftbuckets.py` for the vCPU row, which found the guest's 7.3 ms `pfifo.lock` wait. A second
    instrument (`hakuX-cpu` `Lw`) agrees;
  - checked the HUD leaderboard difference at g11 against four fast async-off runs: it follows pace, not the
    switch;
  - merged master @ 071aea27ff (140930dc16), removed `WAITING`, ran preflight, and set `State: ready`.

## 6. Recommendation: default-on

**This lane recommends `HAKUX_REPORT_ASYNC=1` default-on, with the armed gate.** The three checks it was waiting
on all hold (section 2):

- the determinism check (`-2775483` / `-2775900`) reads every pixel-leg mover as flicker, not the switch;
- `reportasync1010-gate-zpass.json` PASSES: 72 of 72 byte-identical, and `wait=` equals the report count on
  every B window;
- the gated NFS run (`-3049912`) shows 0 report waits and 2 slot-gate waits (0.1 ms), over 12 valid starts.

This PR still ships the switch off (`Release note (none)`). The default flip belongs in a one-line PR of its
own, so that a regression bisects to it.

**The reason is the step-1 table** (section 2: pilot `-4183629` / `-4184121`, and the texscan traces `-553973` /
`-554366`). The brief's rule says: over 1 % `late`, the switch needs `done` honoured, or it stays opt-in.

- `late` is 98.8 % (pilot) and 97.3 % (texscan + async). So the async write needs the guest to honour `done`.
- **NFS honours it.** `armed` is 100 % on three of the four trace runs and 99.9 % on the fourth: the guest
  writes `0xffffffff` to the status word before GET_REPORT. `tsours` is 0: it rewrites the timestamp too. `reuseb4w` is 0: it never
  reuses a slot before the previous write landed. The async write puts the status word last, after a write
  barrier, so the guest sees "in progress" until the count is in memory. A late write costs it a result one
  frame later, never a wrong one.
- **With the gate, that holds by construction.** Only reports whose status word the guest armed are deferred. A
  guest that leaves it at 0 has nothing to poll, so it gets the synchronous write, waiting only on its own slot.

**What it buys, on NFS Most Wanted's race start** (NFS A/B, `-546475` `-547266` `-547898` `-548438`):

- warm countdown 41.5 -> 38.2 ms;
- post-GO 39.45 -> 35.35 ms (25.3 -> 28.3 fps);
- cold start 60.0 -> 51.6 ms;
- v2 share 53 -> 72 %.

With texscan on, the finishing thread's report waits go from 50.6 s over the 12 starts to 0. Under frametrace
(addendum 2, `-3857080` / `-3857196`, texscan on in B too), the report fence's sites leave the pacing thread. Its
waits in the report context fall from 4.4 to 0.9 ms per frame, and what is left is the rotation fence. The warm
period falls from 53.6 to 44.8 ms.

**What it does not cover:** a guest that arms the status word and then reads the count without polling it, or
re-arms a slot before the previous write lands (section 1, known limits). Only NFS has been traced. Before or
with the default flip, trace two or three report-heavy titles with `HAKUX_REPORT_TRACE=1` and read `armed` and
`reuseb4w`.

**texscan's default follows this one.** On with async, it is neutral at the race start (-0.7 ms warm, inside
pair noise) and removes the cube-face downloads. On without async, it loses about 5 ms.

**What a player sees does not change.** The race HUD's leaderboard reads differently at g11 between the arms,
but four fast async-off runs show the same thing, so it follows the pace (section 2, addendum 2). ZPass is
byte-identical, and the pixel leg's movers are flicker.
