# lane.flip474 -- the guest's PGRAPH reads blocked behind the flip (#474)

Base: master @ 84d2e83cef. Evidence from lane.slowdown462 (PR #463,
`docs/lanes/slowdown462/NOTES.md`, DOA1U): in DOA Ultimate's fight on the Nova
the vCPU spent 14.6 s of 30 s off-CPU in `qemu_mutex_lock(&pg->lock)` from
`pgraph_read`, and the PFIFO thread's sampled off-CPU time was 72% in the
driver's GPU-timestamp wait, 79% of those waits matched (by the last on-CPU
sample, median 0.9 ms earlier) to `pgraph_vk_finish` <- `pgraph_vk_flip_stall`.

## 1. The locking, read before any code

### Who holds `pgraph.lock` while the flip runs

- `pfifo.c:1427` -- the puller (PFIFO thread), batch mode
  (`XEMU_OPT_PFIFO_LOCK_BATCH 1`, pfifo.c:37): takes `pgraph.lock`, drops
  `pfifo.lock` (1433), runs `pgraph_method` over up to `num_words_available`
  words (1438), drops `pgraph.lock` (1450). So the lock is held for one
  `pgraph_method` call, which covers every method in the batch -- including a
  FLIP_STALL and everything it waits for. The lockless fast path
  (`pgraph_method_try_fast`, pfifo.c:1409) runs before it without the lock.
- `pgraph.c:2402` `NV097_FLIP_STALL`: `surface_update(d, false, true, true)`,
  then `renderer->ops.flip_stall(d)`, then `waiting_for_flip = true` -- all
  under the puller's hold.
- `renderer.c:2266` `pgraph_vk_flip_stall`: `pgraph_vk_prerecord_display_download`
  (2309), then `pgraph_vk_finish(FLIP_STALL)` (2311), then frame-skip
  bookkeeping and (diag only) a synchronous SURFACE_DOWN finish.
- `draw.c:3454` `pgraph_vk_finish`, FLIP_STALL is a *deferred* reason
  (3596): the command buffers go to the render thread (`RCMD_FINISH`,
  3673-3706) and the PFIFO spins with `sched_yield` until that submit is done
  (3712-3714; on-CPU, not a timestamp wait). The PFIFO thread's own GPU waits
  in this call are the **frame-rotation wait** on the next slot's fence
  (draw.c:3785, `vkWaitForFences(frame_fences[next_frame])`), followed by
  that slot's download completion, framebuffer/texture/surface release drains
  and the vertex-RAM catch-up memcpy (3790-3889). With 3 submit frames
  (draw.c:35) and every non-render-thread finish rotating the slot, the slot
  waited on is the one submitted two *finishes* ago, not two flips ago.

### Where the profile and the perflog disagree (not resolved here)

The perflog soak (e5db66fa37) put the frame's wall time in `Surf` (59.8 ms,
`surface_update`'s exclusive timer) and `Fin` at 1.6 ms (Fen 1.5). The off-CPU
profile (a593d8eb85, a different build and run) matched the waits to
`pgraph_vk_finish` <- `flip_stall`. The rotation wait is inside the `Fen`
timer, so the two cannot both describe the same wait at full size. Either way
the wait is under the puller's `pgraph.lock` hold; what differs is *which*
part of FLIP_STALL (surface_update or flip_stall) holds it. The counter below
splits the vCPU's wait by that phase.

### What `pgraph_read` needs the lock for (pgraph.c:892-928)

- `NV_PGRAPH_INTR`: `pg->pending_interrupts`, published by the NOP path
  (pgraph.c:2333-2339) together with `TRAPPED_ADDR`/`TRAPPED_DATA_LOW`/
  `NSOURCE`, then the lock is dropped before the IRQ. The lock's
  release/acquire is what orders those writes for a reader that polls INTR
  rather than taking the IRQ. (The context-switch path sets the bit under the
  BQL with `pg->lock` dropped, pgraph.c:1135-1140, so the field is already not
  lock-exclusive.)
- `NV_PGRAPH_RDI_DATA`: a read with a side effect (auto-increments
  `RDI_INDEX`) and reads RDI state the methods write. Needs the lock.
- Everything else: `pg->regs_[addr]`, a plain word. The lock does NOT make
  these reads exclusive of all writers already: the lockless fast path writes
  `regs_` with `pgraph_reg_w_atomic` (pgraph.h:510-516, pgraph.c:781-801) with
  no `pgraph.lock`, and `can_fifo_access` reads `regs_[NV_PGRAPH_FIFO]`
  lockless (pfifo.c:1261).

### The fact that decides the design: the lock is the guest's "busy" signal

`NV_PGRAPH_STATUS` is never written anywhere in `hw/xbox/nv2a` (grep), so it
always reads 0, "idle". A guest that polls a PGRAPH register to wait for the
engine is today held off by nothing but `pg->lock`: its read returns only
between two puller batches. Make that read lockless and the guest sees
"idle" while the puller is mid-batch -- possibly mid-draw, copying the
guest's vertex data -- and may overwrite memory the method is still reading.
Drop the lock across the flip's wait and the same poll returns while the
flip's surface downloads (staged into this submit, completed after the wait)
are still to land in VRAM.

So the narrowest *safe* change depends on which register DOA polls, and
nothing on disk says: `hakuX-mmio` (pgraph.c:931-948) is not in the
dispatcher's LOGCAT_SPEC and only logs kernel-range or IF=0 reads, and the
profile's host stack does not carry the MMIO address.

### Other `pgraph.lock` takers that would see the state unlocked mid-flip

- `pgraph_write` (pgraph.c:976), vCPU: INTR ack, INCREMENT (flip read
  index), FIFO access, CTX_SWITCH1, RDI. Register state only.
- `surface_access_callback` (vk/surface.c:2050-2163), vCPU on a trapped VRAM
  access: walks `r->surfaces`, sets `download_pending`/`upload_pending`,
  clears `draw_dirty` on shelved/invalid surfaces, then kicks the PFIFO for
  downloads. Mid-finish this would run between the submit of the flip's
  staged downloads and their completion (`complete_staged_downloads`, after
  the rotation wait) -- a state no reader can see today.
- `surface_watch_rearmed` (vk/surface.c:1971), vCPU safe work: reads
  `surface_addr_map`, may set `upload_pending`.
- `pgraph_vk_set_surface_scale_factor` (vk/surface.c:63-75), UI: sets
  pending flags only.
- Precedent for dropping `pg->lock` inside a method: `pgraph_context_switch`
  (pgraph.c:1135-1140) and the NOP interrupt (pgraph.c:2342-2346) both drop
  it to take the BQL, so the puller's callers already tolerate a mid-method
  release.

## 2. Plan

The two designs the brief names are not equivalent, and which is safe depends
on the polled register:

- **(R) lockless plain-register reads**, INTR and RDI_DATA still locked.
  Exposes `regs_` words mid-batch. Safe if the hot register carries no
  "engine idle" meaning (flip indices, context registers); UNSAFE if it is
  STATUS or anything the guest reads to decide the engine is done.
- **(F) drop `pg->lock` across the flip's GPU wait only.** Exposes the
  surface state between submit and download completion to the access
  callback, and returns an idle poll during the flip. Narrower in time, but
  only helps if the wait the vCPU blocks behind is that one.

So the counter first (perflog-only, `[lock474]` on `hakuX-perf`): per 2 s,
the vCPU's `pgraph_read` and `pgraph_write` lock-wait time, split by what the
puller was doing when the wait began (FLIP_STALL's surface_update, its
flip_stall op, anything else), and the top registers read with their wait.
The pilot reads it on the Nova; the A/B prediction is registered on that
answer, before the fix is written.

## 3. The counter and the pilot

- `523612b5de`: `[lock474]` in pgraph.c (perflog-only; shipping builds take
  the lock exactly as before). `7f13054916` re-spells its guard as a literal
  `defined(__ANDROID__)` for `check_android_guards.py`; same behaviour.
  Syntax-checked with the NDK compile command in both modes.
- `lockread.py` reads it over a window (default 151-288 s, slowdown462's
  fight). On slowdown462's own DOA soak it reads gfps 13.0 (their reader:
  13.19), so the window and the gfps parse agree.
- Pilot legs registered in `docs/testing/predictions/flip474-pilot.json`
  (M0 instrument, P0 premise >= 0.25 of wall, P1 behind FLIP_STALL >= 0.6,
  P2 op vs surface_update, P3 the register and the decision rule for design
  R, P4 counter cost).
- Queued `1790491858-flip474-658414` (Nova, 300 s, survey, perflog). At queue
  time the Nova carried lane.xbox's title-push hold and the owner's
  charger-swap hold before it; ten requests ahead.

## Attempt 1 ended waiting, attempt 2 resumed on the pilot

Attempt 1 did not finish because it ended, correctly, waiting on the pilot
`1790491858-flip474-658414` (Nova queue: ten requests and two holds ahead).
The pilot ran overnight and ended 01:02 PDT. Attempt 2 (2026-09-27) read it,
merged 51 master commits (`c5e7460372`, a merge, no rebase: the pilot's ref
is still in history), and continued.

## 4. The pilot's answer (`lockread.py --from 151 --to 288`)

The shots in the window show the fight (STAGE 01, FPS 12-13): M0 holds.

| leg | registered | measured | verdict |
|---|---|---|---|
| M0 | >= 30 lock / 20 gfps lines, fight on screen | 68 / 32, fight | PASS |
| P0 premise | read wait >= 0.25 of wall | **0.70** (96 s of 137) | PASS |
| P1 behind FLIP_STALL | fs + fo >= 0.6 of read wait | **0.18** (fs 0.17, fo 0.01) | **FAIL** |
| P2 guess | fo > fs | fo 0.01 < fs 0.17 | FAIL (either kept) |
| P3 register | top register >= 0.5 of wait | INTR 0.36; **0.64 unattributed** | instrument gap |
| P4 counter cost | gfps 11-16 | 13.0 | PASS |

- The premise is right: the vCPU waits on `pgraph.lock` for 70% of wall,
  about one slow (~54 ms) wait a frame (`rd_slow` ~26 per 2 s at ~13 fps).
- The brief's location is wrong for this build: FLIP_STALL is cheap
  (surface_update 0.0 ms, flip_stall op 1.8 ms per flip). Even if every flip
  millisecond blocked a reader it would cover ~4% of the wait.
- What holds the lock is in `[surf413]` (same logcat): **`cdef` 56.6 ms per
  frame**, the `pgraph_vk_download_surface_complete_deferred()` call in
  `pgraph_vk_surface_update()` (vk/surface.c, after `part`). The first
  surface_update after each flip waits there for the flip's pre-recorded
  display download (`display_predownload_pending`, fence of the flip's
  submit), i.e. for the GPU to finish the previous frame, inside a draw
  method, lock held. `hakuX-phase` agrees: `Surf` 57-61 ms, `Fin` 1-3 ms.
  So slowdown462's profile attribution (`<- flip_stall`) was the right
  *cause* (the flip's pre-record) at the wrong *call* (the wait is paid at
  the next frame's first draw).
- The waited reads are the guest's NOP-interrupt handler: INTR is read twice
  and NSOURCE, TRAPPED_ADDR, TRAPPED_DATA_LOW once per interrupt (3,499 each).
  One more register carried the other 64% of the wait at ~1 read per
  interrupt; the counter ranked by count and printed four, so it is not
  named. Its read rate says it is not a poll loop. Counter v2 ranks by wait.
- The PFIFO thread is behind the guest (fifoskew backlog mean ~210 KB), and
  its own frame is ~70 ms of which 56 is that GPU wait. Freeing the vCPU
  does not shorten the PFIFO thread's frame; see P2 in the A/B.

## 5. The design, and what becomes visible unlocked

Design F, moved to where the wait is: `ef66174066` releases `pgraph.lock`
across the two frame-fence waits in the deferred-download completion
(`wait_frame_fence()`, vk/surface.c), only when reached from
`pgraph_vk_surface_update()` and only on the PFIFO thread
(`qemu_thread_is_self(&d->pfifo.thread)`). The third branch (no submit yet:
`pgraph_vk_finish(SURFACE_DOWN)`) records and submits, and stays locked.
Every caller of surface_update is a method or the flip-stall path, all
holding the lock; the lockless fast path only writes the register table and
never reaches it.

`16b7e14ec9` is the plumbing, inert on its own (arm A): a flag
`lock_released_for_fence` and a cond in PGRAPHState (pgraph.h), and
`pgraph_lock_settled()`, which waits the window out. Who may run inside it:

| taker | in the window? | why safe / why not |
|---|---|---|
| `pgraph_read`, all but two registers | yes | reads `regs_`, `pending_interrupts`, `enabled_interrupts`. The puller writes none of them while it waits on a fence; values are those after the method's earlier register writes, as at the NOP interrupt's own mid-method release (pgraph.c NO_OPERATION) |
| `pgraph_read` RDI_DATA | settles | side effect: advances RDI_INDEX |
| `pgraph_read` 0x700 STATUS | settles | never written, reads idle; the register a guest would poll to learn the engine is done, so it is held off until the method ends, as before |
| `pgraph_write` INTR, INTR_EN, INCREMENT | yes | interrupt ack/enable and the flip read index; the puller mid-fence touches none of them; INCREMENT's RMW of NV_PGRAPH_SURFACE races no puller write (the methods that write it cannot run) |
| `pgraph_write`, anything else | settles | context loads, RDI writes, FIFO access, raw registers could change state the method reads after the wait |
| `surface_access_callback` | settles | the staged downloads are copied into VRAM only after the wait; a guest write let in first would be overwritten by that copy (shelved/invalid surfaces take no download wait) |
| `surface_watch_rearmed`, scale-factor flushes | settle | surface state |
| `pfifo_stall_for_flip`, renderer switch, `nv2a_lock_fifo` | n/a | the PFIFO thread itself, or after the FIFO is idle |

Lock order is unchanged (pfifo.lock before pgraph.lock; the batch puller
holds no pfifo.lock inside a method). A settled waiter sleeps on the cond
with the lock free and wakes after the retake, i.e. where it ran before.

Syntax-checked with the NDK compile command (`ndkcheck.py`, both
NV2A_PERF_LOG modes) for pgraph.c, vk/surface.c, pfifo.c, nv2a.c,
gl/surface.c; `check_android_guards.py` ok. **No desktop build**: this host
still has none (AGENTS.md's named gap), so step 4's "run it locally" is
replaced by the device pgraph arm in `flip474-pgraph-inert.json` (12 suites,
c5e7460372 vs ef66174066), queued by the arms job.

## 6. Does it reach Forza's download path? No.

slowdown462's Forza profile has the PFIFO wait in `pgraph_vk_finish <-
pgraph_vk_download_surface_complete_deferred` (18.1 ms/frame, ~6 uncoalesced
`sd_complete_def` per frame): the third branch, the synchronous
SURFACE_DOWN finish, which this change leaves locked. Forza's vCPU lock
wait is 3.3 ms/frame (9%). So no Forza A/B for this change; the Forza lever
is #414's (coalesce the completions, or complete them off the PFIFO thread).
Blinx 2's is the same synchronous shape (`download_surface` finish), vCPU
lock wait 2.6 ms/frame, at its 30 fps cap: not a target either.

## 7. The A/B, registered before any arm runs

- `flip474-doa-ab.json`: Nova, survey, 300 s, 2 runs per arm, A
  `16b7e14ec9`, B `ef66174066`. Legs: F0 B `rd_unl` >= 500 (A == 0); L1 lock
  wait B <= 0.5 x A, kill > 0.8; P1 gfps no regression; P2 rise < 2 fps
  (guess, PFIFO-bound); P3 cdef unchanged; H0 no gap > 3 s, no tombstone.
- `flip474-crimson-ab.json`: Thor, crimson-skies, 240 s, 1 run per arm;
  measures whether Crimson waits there at all, then no-harm.
- `flip474-pgraph-inert.json`: the suite arm, bit-identical.
- Pilot verdict written to `pilots/flip474.ok` (the batch is 37 min of
  device time with setup).

## Waiting (attempt 2, 2026-09-27 ~06:50 PDT)

On the six arms, queued 13:45Z: DOA A1 `1790516325-flip474-1235330`, B1
`1790516329-flip474-1235504`, A2 `1790516335-flip474-1235784`, B2
`1790516335-flip474-1235822` (Nova); Crimson A `1790516335-flip474-1235863`,
B `1790516335-flip474-1235910` (Thor); and the arms job's pgraph pair for
`flip474-pgraph-inert.json`. When they land: `lockread.py` on each pair,
judge every leg in `flip474-doa-ab.json` / `-crimson-ab.json`, read
`logcat -b crash`, post on #474 and #462, then ready the PR if L1 and H0
hold and the suite arm is identical. If F0 fails (B's `rd_unl` ~0), the wait
is at another completion call: find it with the v2 counter before touching
code again.

## Why attempt 2 did not finish

It ended correctly, waiting on the six soaks and the arms job's pgraph pair,
with a `[lane.flip474] waiting:` comment on #475. All of them landed while
no session was running. `jobs/handback.sh` resumed the lane (attempt 3) with
CI green on `9c96893b26` and the pgraph arm judged `verified`.

## 8. Results (attempt 3, 2026-09-27)

`lockread.py --from 151 --to 288` (DOA) and `--from 110 --to 240` (Crimson).
Crash markers from `crashcheck.py`, lines-to-the-end from `tailcheck.py`.

| run | ref | read lock wait / wall | rd_unl | gfps median | cdef ms/frame | longest gap | crash |
|---|---|---|---|---|---|---|---|
| DOA A1 `1-1790516325-flip474-1235330` | 16b7e14ec9 | 0.692 (93.9 s) | 0 | 14 | 52.3 | 1.9 s | 0 |
| DOA B1 `1-1790516329-flip474-1235504` | ef66174066 | **0.005** (0.64 s) | 2292 | 15 | 51.0 | 1.6 s | 0 |
| DOA A2 `1-1790516335-flip474-1235784` | 16b7e14ec9 | 0.698 (95.5 s) | 0 | 12 | 61.6 | 2.0 s | 0 |
| DOA B2 `1-1790516335-flip474-1235822` | ef66174066 | **0.004** (0.51 s) | 2314 | 15 | 50.4 | 2.0 s | 0 |
| Crimson A `0-0-x-1790516335-flip474-1235863` | 16b7e14ec9 | 0.047 | 0 | 29 | 0.5 | 1.4 s | 0 |
| Crimson B `0-0-x-1790516335-flip474-1235910` | ef66174066 | 0.054 | 283 | 28 | 0.5 | 1.5 s | 0 |

DOA legs (`flip474-doa-ab.json`):

- **M0 holds.** 66-67 `[lock474]` and 27-35 gfps lines per run. B1's shots in
  the window show STAGE 01 with two fighters. A2's shots include a KO
  **REPLAY** against a different opponent, so A2 was not in A1's scene (see P2).
- **F0 holds.** A has `rd_unl` 0 in both runs; B has 2292 and 2314 (the leg
  needs >= 500).
- **L1 holds by far more than the leg asks.** Pooled lock wait share: A 0.695,
  B 0.0042, so B/A = 0.006 (leg <= 0.5, kill > 0.8). The vCPU's 94 s of
  PGRAPH lock wait per 137 s became 0.6 s.
- **Q: the guess was wrong, and it does not matter for L1.** The hidden register
  is `0x0b10 PGRAPH_PATT_COLOR0`: 0.55 and 0.65 of A's read wait, n ~1700,
  about one read per frame, which is not an interrupt-service register. It
  is not STATUS. In B its wait is 0.11 s and 0.00 s.
- **P1 holds.** Median of the run medians: A 13, B 15.
- **P2, the labelled guess, is falsified at its boundary.** B - A = 2.0 and
  the leg said < 2. It is confounded, though. The same-scene pair A1/B1 is
  14 -> 15 (+1). A2's 12 comes from a window that includes a replay scene.
  The reading is +1 to +2 fps (7-15%). The PFIFO thread's own GPU wait
  still bounds the frame, as P3 shows.
- **P3 holds.** cdef in B is 51.0/50.4 ms against A's 52.3/61.6, so the
  PFIFO wait is unchanged.
- **H0 holds.** Gaps are <= 2.0 s, `[lock474]` lines run to 298.7/303.9 s of
  a 300 s soak, and no run has a crash marker.

Crimson (`flip474-crimson-ab.json`):

- **P0.** A's share is 0.047, below the 0.05 floor, so L1 is **not
  applicable**. It is not a pass. Crimson's vCPU waits 96% on `PATT_COLOR0`
  in "other" phases, not at a fence.
- **P1 holds.** 29 -> 28, and the leg allows >= A - 1.
- **H0 holds.**
- B's `rd_unl` of 283 shows that the release ran on this title too, without
  harm.

Suite arm (`flip474-pgraph-inert.json`, c5e7460372 vs ef66174066, 12 suites,
682 captures): **PASS**, labelled `verified`. 678 captures are byte-identical.
The 4 that differ are all `Vertex_shader_rounding_tests/GeometrySuperscreen_*`,
the one-run drift family that buildflags427 and dpforce345 already
documented. The prediction excluded that family.

**Merge.** origin/master (31 commits) was merged at `b38118c94a`, with no
rebase, so every prediction ref is still an ancestor. The only conflict was
`docs/testing/nv2a_index.json`, rebuilt with `nv2a_index.py build --tests
/home/justin/nxdk_pgraph_tests` (tests_commit 6743b6ab, as master's).
`nv2a_index.py check` and `preflight.sh` pass.

**What remains for DOA** is the PFIFO thread's own ~51 ms/frame wait for the
previous frame's GPU work (cdef). This change was never meant to touch it.
The next lever is that wait itself: complete the display download without
blocking the next method, or pipeline it a frame (#413/#414).

## Do not repeat

- Do not make every PGRAPH read lockless without knowing the polled register:
  STATUS always reads idle, so the lock is the only thing holding an idle
  poll off mid-batch.
- Do not attribute a vCPU lock wait to the puller phase where the wait
  *began* and stop there: the wait lasts until the method ends. Read
  `[surf413]`/`hakuX-phase` in the same logcat for what the method spent.
- Do not rank a counter's registers by count when the question is wait.
- Do not compare fps across A/B runs without looking at the shots: DOA's
  survey route can land a window on a KO replay (A2), and that moves gfps.
