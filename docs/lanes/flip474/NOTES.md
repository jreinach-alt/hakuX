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

## Why attempt 3 did not finish, and attempt 4 (2026-09-27)

Attempt 3 did finish the definition of done. It judged every leg (section 8),
posted on #474 and #462, and marked #475 ready at 15:56Z. After that, two
things arrived that it never read. The first was audit pass 1
(`docs/audits/2026-09-27-flip474-pass1.md`, four LOW findings, each needing a
logged decision). The second was lane.local's 09:17 PDT addendum asking for
the next lever with a bound for each option; attempt 3 gave it one line.
Attempt 4 does both. It re-measures nothing and extends no arm.

### Audit pass 1: a decision for each LOW

Audit pass 2 (`docs/audits/2026-09-27-flip474-pass2.md`) landed while
attempt 4 was writing these remedies. It found the tree clean on
`e3138297ee`, carried the four LOWs as follow-ups, and labelled #475
`fold-ready`. A push of `hw/` edits after that would put code the audit
never read into the fold. So the remedies below are **written but not on
this branch**. They belong in the next change that touches these files
(the O1 lane below). This PR carries only docs.

| LOW | decision |
|---|---|
| 1: the comments name the ISR reads as DOA's wait | **follow-up, text ready.** `pgraph_read`'s comment should say PATT_COLOR0 (0xb10) is 0.55-0.65 of the wait, the ISR's INTR/NSOURCE/TRAPPED_* reads the rest, "so do not narrow this to the interrupt registers". `wait_frame_fence`'s comment should say the same in one line |
| 2: release assumes the lock is held | **no guard.** Every PFIFO-thread caller of `surface_update` is a method under the batch hold; pass 2 re-enumerated them. This is the third instance of the mid-method drop already made by `pgraph_context_switch` and NO_OPERATION. The guard belongs with any change that adds a lockless PFIFO path into surface_update |
| 3: `len` in `lock474_log` is unchecked | **follow-up, one line.** Add `&& len < sizeof(regs)` to the loop condition. Perflog-only; both passes show it cannot truncate today (at most ~210 of 256 bytes) |
| 4: the exemption is "all but two" | **follow-up, text ready.** Beside the exemption, say: a window read returns a register as the method left it before its surface_update. That linearises only while every method writes PGRAPH registers on one side of surface_update (SET_CONTROL0: after; the diag FLIP_INCREMENT_WRITE: before) |

The written remedies passed `ndkcheck.py` on pgraph.c and vk/surface.c in
both NV2A_PERF_LOG modes before they were set aside.

### The next lever: the PFIFO thread's own wait (`cdef`)

`phaseread.py` (hakuX-phase medians over 151-288 s; GPU is the per-frame
span from GPU timestamps):

| run | Tot (PFIFO ms/frame) | Surf | Draw | Fin | GPU span | cdef |
|---|---|---|---|---|---|---|
| A1 | 65.0 | 54.9 | 8.3 | 1.7 | 34.8 | 52.3 |
| A2 | 74.0 | 62.6 | 9.1 | 1.8 | 39.9 | 61.6 |
| B1 | 61.7 | 51.8 | 8.1 | 1.8 | 33.0 | 51.0 |
| B2 | 62.1 | 51.8 | 8.1 | 1.8 | 33.0 | 50.4 |

Read with B's numbers. The PFIFO thread's frame is about 62 ms. Of that,
about 51 ms is the wait at the first surface_update after the flip, for the
flip's command buffer, and about 11 ms is its own work. The GPU's span for
that buffer is only 33 ms. The PFIFO thread and the GPU therefore take
turns: the thread records a frame, submits at the flip, then waits for the
whole of it before it records the first draw of the next frame. So the
overlap is near zero, and the frame is roughly CPU + latency + GPU, not the
max of them. The wait is also about 18 ms longer than the GPU span. That gap is
submit latency through the render thread, queue start, or GPU clock ramp
after an idle gap. It is not measured, and it is not split.

The completion is unconditional (`pgraph_vk_surface_update`, vk/surface.c,
the `download_surface_complete_deferred` call after `part`). It does not
ask whether the surface being bound, or anything the method reads,
overlaps a staged download.

Options, with a **bound** for each. A bound is a ceiling, not a prediction
(GPU span and CPU work held at B's values):

- **O1, complete lazily.** Leave `display_predownload_pending` set across
  draws. Complete only when a consumer needs the VRAM:
  - a trapped CPU access to a staged surface (`surface_access_callback`
    already kicks downloads);
  - a texture or surface upload from an overlapping range;
  - the scanout read;
  - or, at the latest, the next flip's pre-record, which returns early
    while one is pending.

  Frame bound = max(CPU 11, GPU 33) ≈ 33 ms, **<= 30 fps**, from 15. The
  real ceiling is lower if the GPU span grows once the GPU runs back to
  back. The frame-slot rotation (3 slots, draw.c) still caps in-flight
  work at two frames. Risk: a consumer this path misses reads a stale
  frame (the DOA display surface is read only by scanout), so the
  consumers must be enumerated before any code.
- **O2, complete off the PFIFO thread.** The render thread (or a
  completion worker) waits on the fence and copies the staged downloads.
  The PFIFO thread goes on at once, and VRAM consumers wait on a
  per-surface completion. Same bound as O1, **<= 30 fps**. It has more
  hazards than O1: the copy races guest writes to the same VRAM. It is
  the general form of #414's "complete off the PFIFO thread", so
  Forza/Blinx 2's synchronous SURFACE_DOWN path could share it.
- **O3, gate the wait on overlap.** Keep the completion in surface_update,
  but run it only if the surface being bound or read overlaps a staged
  download range. Otherwise defer it as in O1. This is O1 restricted to
  one call site. Bound: **<= 30 fps** if DOA's first-draw surfaces never
  overlap the flip's staged downloads; **no gain** if they do (the display
  surface re-bound as the next back buffer is exactly that case, and it is
  not measured).
- **O4, shorten the wait without overlap.** Attack the ~18 ms between the
  wait and the GPU span: submit latency, queue start, clock ramp. Frame
  bound = 62 - 18 = 44 ms, **<= 22.7 fps**. A cheaper first measurement
  than O1-O3 is a CPU timestamp at the flip's `vkQueueSubmit` against the
  command buffer's first GPU timestamp (same clock domain via
  `VK_EXT_calibrated_timestamps`, or its absence noted). It also decides
  whether O1's ceiling is 33 ms or smaller.

Recommendation: measure O4's split first (perflog-only, one pilot). Then
enumerate O1's consumers by reading, and implement O1 against a prediction
whose legs are cdef -> ~0, Tot <= 45 ms, and the pgraph suites
bit-identical. Two things to watch: the `R`/`X` halves of the GPU span come
out almost equal in every run, which looks like an instrument artefact
before anyone relies on it, and `GPU` is a per-frame sum over command
buffers.

## Why the last session did not finish, and this one (2026-09-27, from 09:23 PDT)

The last session did finish what it had. It logged the audit decisions and
the next lever, pushed `117b3b56d1` at 16:21Z and left #475 ready. One
minute later the host's delivery on #474/#414 (09:22 PDT) asked for three
more things: a DOA A/B on lane.forza414's fix build, the O4 split pilot, and
a check of the R/X artefact. No session was running to read it.

#475 folded at 16:30Z as `bf60a2b5b8` and the fold deleted the lane branch.
This session fast-forwarded to master and works on a **second PR** from the
same branch name. Its net diff is docs only.

### 9. lane.forza414's fix and DOA: the same call, not the same branch

The delivery's premise is that DOA's `cdef` and Forza's `surfupd` are the
same completion, so one fix frees both. Read against `94f002d309`, they are
the same call in `pgraph_vk_surface_update` and different branches of
`download_surface_complete_deferred` (vk/surface.c):

| branch | who waits there | what 94f002d309 does |
|---|---|---|
| `display_predownload_pending`: wait on the flip's submitted command buffer | **DOA**: #475's B released the lock only around the fence waits and the vCPU's wait went 0.69 -> 0.004; surf413 `fin` is 0.00 ms in all four runs | nothing: `surface_update_may_defer_downloads()` returns false when the flag is set |
| `deferred_downloads_frame >= 0`: wait on an earlier finish's fence | neither, measurably | nothing: the gate returns false, "a fence wait, not a finish" |
| neither: `pgraph_vk_finish(SURFACE_DOWN)` | **Forza**: `[sdcall]` surfupd fin 7.0 per frame, 20.9 ms | defers it unless a binding is about to upload |

So by reading, `94f002d309` completes DOA's flip download exactly where its
base does. The A/B is registered on that reading
(`flip474-doa-forza414-ab.json`): C1 says cdef does **not** fall (B/A >= 0.8),
and B/A <= 0.5 kills the reading. It is one run per arm, because the two
outcomes are ~51 ms and ~0. Both refs print `[sdcall]`, which no DOA run has
had, so G0 measures the branch directly.

What DOA needs is the deferral extended to the first row: leave
`display_predownload_pending` set across draws and complete on a consumer
(O1). That is a second gate in the same function, in lane.forza414's file.
This lane does not write a second copy of the deferral.

### 10. What the logs on disk already say about the ~18 ms (`o4read.py`)

| DOA fight, 151-288 s | A1 | B1 | A2 | B2 |
|---|---|---|---|---|
| cdef, ms/frame | 52.3 | 51.0 | 61.6 | 50.4 |
| dfF, the completion's wait | 53.7 | 51.0 | 62.1 | 50.8 |
| dfR, the staged copy and flags | 0.4 | 0.2 | 0.4 | 0.2 |
| GPU span | 34.8 | 33.0 | 39.9 | 33.0 |
| R, inside render passes | 17.4 | 16.5 | 20.0 | 16.5 |
| X, outside them | 17.4 | 16.4 | 19.9 | 16.6 |
| MxG, the longest gap between two passes | 16.8 | 16.2 | 19.5 | 16.3 |
| wait / R | 3.09 | 3.09 | 3.10 | 3.08 |

- **The excess is not the copy.** dfR is 0.2 to 0.4 ms.
- **It is not the render thread's submit.** `pgraph_vk_finish(FLIP_STALL)`
  spins until `frame_submitted` is set, which `process_finish`
  (render_thread.c) does after `vkQueueSubmit` returns. The wait cannot start
  before that.
- **It scales with the frame's work.** The wait is 3.08 to 3.10 x R in all
  four runs, A2's replay scene included. A fixed wake-up or queue latency
  would not scale. This is a pattern, not an explanation.

### 11. The R/X check: the equality is real, and it is DOA's long-wait scenes

| run | device | X/R per line, median (p10 to p90) |
|---|---|---|
| DOA fight, four runs | Nova | 0.99 to 1.01 (0.93 to 1.01) |
| DOA, scenes with no long gap (B1, 08:35:28-40) | Nova | 0.03 to 0.05 |
| Crimson Skies A, B | Thor | 0.09 (0.07 to 0.17) |
| Forza, two runs | Nova | 0.13, 0.20 (0.11 to 0.62) |

- The instrument does not force X = R: the same code reads 0.09 and 0.13
  on other titles, and 0.03 on DOA's own scenes without the long wait.
- In DOA, every line with one large gap (`g:n/0/1`) has X = R within 2%,
  from the menus (R 6.4 ms) to the fight (R 18.1 ms), and every such line
  has the long `Surf` wait. Lines with no large gap have neither.
- X is one gap: MxG is X less 0.3 ms. So one gap between two render passes
  is as long as all the passes together.
- Not decided here: whether the GPU does the passes' work twice, or whether
  timestamps written inside a pass misplace it, as they can on a tiling GPU.
  Until the pilot's S2 answers, **do not use the phase line's R/X split for
  DOA**. The span (first to last timestamp) does not depend on the passes'
  timestamps and is kept.

### 12. The O4 pilot

- `3112e410db` is master `bf60a2b5b8` plus the `[o4]` probe (vk/surface.c,
  vk/renderer.c, perflog only). `e8ed36413e` reverts it: vk/surface.c is
  lane.forza414's file, and the probe is for one pilot.
- One line per waited flip: the PFIFO thread's clock around the flip's
  finish and the fence wait, the command buffer's first and last GPU
  timestamp raw, and each render pass as an offset.
- No extension is needed to compare the clocks. A command buffer cannot end
  after its fence was seen signalled, so the smallest (fence seen - last
  timestamp) in the window is the offset plus the smallest signal latency.
  `start` is an upper bound by that much; K0 checks drift.
- `ndkcheck.py` passes on both files in both NV2A_PERF_LOG modes, and a
  `#error` placed in the block fails perflog=1 and passes perflog=0, so the
  check does compile it. `check_android_guards.py` ok.
- `o4read.py --selftest` recovers a synthetic split (every part a different
  size, GPU clock 7 s off) and drops a short and a malformed line.
- Legs in `flip474-o4-pilot.json`: M0, K0, S0, S1 (start or end; a labelled
  guess), S2 (is gap = R per flip), P4 (probe cost).

### Waiting (this session)

Three Nova requests, priority 1, each 300 s, survey route, perflog:

| request | ref | prediction |
|---|---|---|
| `1-1790527182-flip474-1639694` | `4b22f2526b` (A) | `flip474-doa-forza414-ab.json` |
| `1-1790527188-flip474-1640231` | `94f002d309` (B) | `flip474-doa-forza414-ab.json` |
| `1-1790527190-flip474-1640480` | `3112e410db` (pilot) | `flip474-o4-pilot.json` |

Queued 16:40Z on PR #485, behind about sixteen requests. The priority
prefix is set with `env HAKUX_RELEASE_PRIO=1 bash docs/testing/request.sh`;
the bare `VAR=1 bash ...` spelling is refused by this session's command
check.

When they land: `o4read.py --show` on each, judge every leg, read the shots
for the scene, post on #474, #414 and #462, and mark the PR ready. The three
are 19.5 min of device time with setup, under the pilot rule's 30.

## Why the last session did not finish, and this one (resumed 2026-09-27 17:22Z)

The last session ended on a wait, correctly: the three Nova requests above
had been queued at 16:40Z, outside the session. At 17:23Z all three were
still in the queue, seventh to ninth, behind tbflip424, retreason425's arms
and forza414. The resume notice named #475, which had folded at 16:30Z; the
live PR is #485. This session merged master (23 behind; no hw/ change) and
built Addendum 3's instrument while the DOA runs wait.

### 13. `[cblat]`: kick -> push-buffer callback, split by the PFIFO thread's waits

The request (host delivery on #474, 17:22Z): retreason425 found AUF, Blinx and
Blinx 2 idle until the PGRAPH ERROR interrupt that `NV097_NO_OPERATION` with a
parameter raises. So their frame is set by how soon the puller dispatches that
callback after the guest publishes it.

`dad7864b73` plus `76cba82fd2`, pfifo.c only, compiled only in Android perflog
builds. It writes
one `hakuX-perf cblat` line per 2 s window.

- **Which kick.** A 128-entry ring of (DMA_PUT, time, split snapshot) is filled
  at the vCPU's DMA_PUT store (the `fsk_note_submit` site). It is retired as
  the pusher's DMA_GET walks past each put: a linear step retires the puts in
  (before, after]; a jump, call or return retires only a put equal to its
  target. Reaching DMA_PUT retires everything. At a callback's dispatch, the
  oldest unretired entry is the submission that made the marker visible.
- **The split.** This is cumulative time per category, kept by the PFIFO
  thread. Every update and both snapshots are under `pfifo.lock`: the kick
  holds it (user.c), and the thread holds it at each park and method boundary.
  So a snapshot sees an in-progress category from its published start.
  - Parks, by the reason at park time: `pflip` (waiting_for_flip), `pnop`
    (waiting_for_nop, i.e. the previous callback unacknowledged), `pidle`.
  - Method dispatches by class, each including its `pgraph.lock` wait:
    `mflip`, `msema` (semaphore release), `mclear`, `mdraw` (SET_BEGIN_END),
    `mother`.
  - `rest` is the remainder.
  - Nested and overlapping: `dl` is surf_working df_flush+df_read, i.e.
    `download_surface_complete_deferred`: DOA's cdef and Forza's surfupd finish.
    `fin` is phase finish_ns, which is every `pgraph_vk_finish`.
  - The profile's per-flip reset happens inside FLIP_STALL, so that method's
    nested time is dropped (`rst` counts it).
  - A method in progress at the kick has its nested wait counted whole, so
    `dl` and `fin` are each capped at the interval's method time.
- **Non-overlapping.** A callback's split starts at the later of its kick and
  the previous callback's dispatch (`shared` counts those), so the per-frame
  sums cannot exceed the frame. `lat` is the full kick -> dispatch.
- `dup` is read before the dispatch, because the NOP handler sets the ERROR bit
  itself. It counts callbacks the Android handler drops.
- A callback is stamped after its own dispatch (`76cba82fd2`). The first cut
  stamped it before, while the counters already held the NOP method's time
  (its BQL wait included), so `rest` would have read negative by that much.
  Both predictions were re-registered on `76cba82fd2`, and the two requests on
  `dad7864b73` were withdrawn unrun.
- **Checks.** `ndkcheck.py` passes on pfifo.c in both NV2A_PERF_LOG modes with
  no warnings in the file; it now prints the file's warnings too. A `#error`
  in the block fails perflog=1 and passes perflog=0. `check_android_guards.py`
  is ok. `cblread.py --selftest` passes, and the reader parses a line generated
  from the C format string itself.
- **Not checked.** The desktop build (none on this host). Off Android, the
  only added code is two locals and a flag the macros cast to void.
- **Predictions:** `flip474-cblat-auf.json`, `flip474-cblat-blinx.json` (one
  arm each; M1 ties the count to retreason425's ERROR interrupts per frame; M2
  is the no-overlap check; S1 is labelled a guess).

### 14. O1's consumers (lazy completion of the flip's display download), by reading

This is the list promised to lane.forza414 on #474. O1 would keep
`display_predownload_pending` set across draws and complete on a consumer.
Line numbers are this branch's (master 5ec9b2267f + pfifo.c). An Explore pass
did the read; rows 2 and 4 were checked by hand (draw.c:3590 tags
`deferred_downloads_frame` only while it is < 0, and a record goes into
`r->command_buffer`, draw.c:3981).

**O1 is not a one-gate change.** The completion assumes the display download
is completed within a method of the flip:

| # | where | what breaks if completion is later |
|---|---|---|
| 1 | surface.c:4673 `pgraph_vk_surface_update` (today's site) | must still complete when this update itself recorded downloads (evict 4360/4428, overlap 2626, 4513, expire 3103): the uploads at 4692/4706 read VRAM |
| 2 | surface.c:972-980, display branch of `download_surface_complete_deferred` | waits only on the flip's fence, then copies ALL staged entries, including ones recorded after the flip into the unsubmitted current CB: stale bytes, and 912-916 clears `draw_dirty`. 1010-1013 marks the display surface clean at its *current* generation, overriding 912-916. Reachable today when `update_surface_part` records before 4673; O1 makes it the normal case |
| 3 | surface.c:392 `pgraph_vk_download_surfaces_in_range_if_dirty` (texture.c:1938, vertex.c:50, blit.c:558/560/900) | calls `pgraph_vk_complete_staged_downloads` raw: the flag stays set; 436 later waits on the old fence (row 2) |
| 4 | draw.c:3590 finish | never re-tags post-flip entries; the cause of row 2 |
| 5 | draw.c:3785-3797 rotation into the flip's slot (and 3656, 3724) | completes staging but never clears `display_predownload_*`: prerecord is off for good (1665), and the next completion waits on a reused slot `fi`. With 3 slots and several finishes a frame, O1 hits this nearly every frame |
| 7 | surface.c:1660-1716 prerecord at the next flip (renderer.c:2309) | a second flip finds the flag set and records nothing; entries pile toward MAX 64 (470) |
| 11 | surface.c:2186-2200 access callback, write to a shelved/invalid surface | clears `draw_dirty`, then the late staged copy overwrites the guest's write |
| 12 | surface frees: 3078, 2647, 3131, 4900; reuse 3058+4405 | `deferred_downloads_clear_surface` (825) does not clear `display_predownload_surface`: use-after-free at 996-1013 |
| 17 | renderer.c:377-420 `diag_download_surface` | writes staging offset 0 without completing (diagnostic only) |

Already complete first, and so are as correct as row 2: `download_surface_to_buffer`
(1036, retry 1649), `pgraph_vk_process_pending_downloads` (1751, from the vCPU access
callback and the display thread's wait), `pgraph_vk_download_dirty_surfaces` (1834,
savevm and scale), expire (3114), fdump (renderer.c:2192), reset/post_load flush.
Unaffected: scan-out reads the VkImage (display.c:1729); `surface_handoff_partner`
(3920) only declines longer.

**What O1 needs, in order:** (a) row 2/4: split the display entry from later
entries, each completed on its own fence, and drop 1010-1013's override; (b)
row 3: go through `download_surface_complete_deferred`; (c) rows 5/6: clear the
display bookkeeping at slot rotation, which is also the natural lazy completion
point, since that fence has just been waited; (d) row 7: complete before the next
prerecord; (e) row 1: complete when the update recorded downloads; (f) rows 11,
12, 17.

### Waiting (resumed session, from 17:36Z)

Five Nova requests, priority 1, perflog, survey route:

| request | ref | what | read with |
|---|---|---|---|
| `1-1790527182-flip474-1639694` | `4b22f2526b` | DOA A, forza414's base | `o4read.py --from 151 --to 288` |
| `1-1790527188-flip474-1640231` | `94f002d309` | DOA B, forza414's fix | same |
| `1-1790527190-flip474-1640480` | `3112e410db` | DOA O4 pilot | same, `--show` |
| `1-1790530526-flip474-2801414` | `76cba82fd2` | AUF `[cblat]`, 420 s | `cblread.py --from 299 --to 420 --show` |
| `1-1790530526-flip474-2807172` | `76cba82fd2` | Blinx `[cblat]`, 420 s | `cblread.py --from 255 --to 411 --show` |

The pilot gate admitted the last two on `pilots/flip474.ok` (36 min held).
When they land: judge every leg of the five predictions, post on #474, #462,
#414 (DOA) and #425 (cblat), then mark #485 ready.

## Why the last session did not finish, and this one (resumed 2026-09-27 20:15Z)

The last session ended correctly, waiting on the five Nova requests above.
All five were outside the session, and all were done by 13:10 PDT. The resume
notice named #475 again, which had folded; the live PR is #485. This session
read the five runs, judged every leg, merged master (42 behind; the only
conflict was `nv2a_index.json`, rebuilt with `nv2a_index.py build --tests
fold-pins/nxdk_pgraph_tests --support fold-pins/pbkitplusplus`, and `check`
with both passes), and posted the results.

### 15. The five Nova runs

Read with `cblread.py`, `o4read.py`, `o4clock.py` (new), `lockread.py`,
`crashcheck.py` and `tailcheck.py` (`judge5.sh` runs them all). Each route's
play shots were checked by eye: every window is level play or the fight.

**`[cblat]`, AUF `0-0-x-1790530526-flip474-2801414`, 299-420 s, and Blinx
`...-2807172`, 255-411 s.** Units are ms per frame over non-overlapping intervals.

| | AUF | Blinx |
|---|---:|---:|
| gfps median (frame, ms) | 14 (71.4) | 16 (62.5) |
| callbacks per flip (retreason425's ERROR/frame) | 1.67 (1.97) | 14.24 (14.66) |
| kick -> dispatch, p50 / p90 of lines | 93.5 / 100.3 | 19.6 / 46.9 |
| span | 67.4 | 44.5 |
| **mdraw** (SET_BEGIN_END, with its lock wait) | **50.1** | **36.8** |
| pflip (FLIP_STALL parked on the VBLANK) | 11.3 | 0.00 |
| mflip | 2.6 | 0.00 |
| mother | 2.1 | 5.8 |
| rest | 1.2 | 1.4 |
| pnop (previous callback unacknowledged) | 0.02 | 0.35 |
| msema | 0.04 | 0.05 |
| dl, nested (deferred download) | 19.3 | 0.4 |
| fin, nested (every `pgraph_vk_finish`) | 0.00 | 0.10 |

| leg | AUF | Blinx |
|---|---|---|
| M0 instrument | holds (59 lines, all parse) | holds (78) |
| M1 same event as retreason425 | holds (1.67 is within 25% of 1.97; nokick 0) | holds (14.24 against 14.66; nokick 0) |
| M2 no double counting | holds (67.4 <= 75.0) | holds (44.5 <= 65.6) |
| S1 the guess | **held**: method time 54.8 of 67.4 | **refuted**: pnop 0.35, the smallest part; mdraw 36.8 is the largest |
| P probe cost | holds (14 against 14.96) | holds (16 against 17.32) |

- **For both titles, the callback is late because the PFIFO thread is
  still dispatching the frame's draws.** Neither is waiting on the guest.
  Every AUF callback, and 78% of Blinx's, is `shared`: it was kicked
  before the previous one was dispatched. So the split covers the puller's
  frame nearly end to end.
- **AUF:** of mdraw's 50.1 ms, 19.3 is the nested deferred download.
  `fin` is 0.00, so that download is a fence wait, not a finish of its own,
  and lane.forza414's deferral (whose gate excludes fence waits) does not
  reach it. #474's lazy completion (O1) does, **bound 19.3 ms/frame**. Flip
  pacing is **bound 11.3** (pflip). The rest, about 31 ms, is the draws'
  own work on the PFIFO thread.
- **Blinx:** dl 0.4, fin 0.1, msema 0.05, pflip 0. **None of O1, #488,
  flip pacing or forza414's deferral has more than 0.5 ms/frame to take.**
  What sets Blinx's callback is the PFIFO thread's draw dispatch: 36.8 of
  a 62.5 ms frame.
- **Silicon** (lane.xbox, #474 comment 5859096857): from kick to handled is
  13-14.5 us, whether the frame is empty or has 500 quads, and the puller
  resumes 8 us after the handler. On hakuX the resume leg is already that
  order (6.8-31.7 us). The gap is the time before dispatch, which grows with
  queued draws: here 19.6 ms (Blinx) and 93.5 ms (AUF) at p50. On silicon the
  whole 500-quad frame, first draw to semaphore, takes 6.4 ms.
- **The next lever for both** is the per-draw cost of SET_BEGIN_END on the
  PFIFO thread. slowdown462's `hakuX-phase` Draw is the place to split it.
  This instrument ends there.

**DOA on lane.forza414's fix: A `...-1639694` on `4b22f2526b`, B
`...-1640231` on `94f002d309`, 151-288 s.**

| leg | A | B | verdict |
|---|---:|---:|---|
| M0: surf413 / sdcall / gfps lines | 31/31/31 | 29/29/29 | holds; both windows show the fight, with no KO replay in either |
| G0: sdcall surfupd pre per frame, fin per frame | 0.98, 0.000 | | holds: DOA waits in the display-predownload branch |
| G1: su_deferred per frame | | 0.000 | holds: the deferral never fires on DOA |
| C1: cdef median, ms | 56.0 | 59.9 | **holds: B/A 1.07 (>= 0.8)**. cdef did not fall, as predicted |
| T1: Tot median, ms | 67.9 | 73.6 | holds (1.08) |
| P1: gfps median | 13 | 12 | holds, at the edge (B >= A - 1) |
| H0: longest gap / lines to end / crash | 2.1 s / 300.7 of 301.8 / 0 | 2.1 s / 299.3 of 300.6 / 0 | holds |

The reading of section 9 stands: `94f002d309` does not reach DOA. DOA
needs O1, for which section 14 lists the consumers.

**O4 pilot `...-1640480` on `3112e410db`, 151-288 s.**

| leg | verdict |
|---|---|
| M0 | holds: 1128 long-wait flips, fight in the shots |
| K0 clocks | **FAILS**: offset drift 0 / 11,825 / 22,943 ms by third. The cause is below |
| S0 | holds: wait 63.1 against dfF 62.9. The span, 40.5, agrees with phase GPU 40.4 because both use the same period |
| S1 the guess (start-dominant) | **the premise is refuted: there is no excess to place** |
| S2 R/X structural | holds: gap within 5% of R on 96% of flips, and after pass 0 on 93.1% |
| P4 probe cost | **FAILS as written**: gfps 12 (range 13-17), cdef 62.5 (range 43-59). Today's unprobed arms read 13 and 12 gfps, and 56.0 and 59.9 ms, so most of the miss is the day's frame and not the probe. The probe's own cost is not separable in one run |

**The GPU timestamp period on the Nova is wrong by a factor of 1.573.**
`o4clock.py` fits the lower envelope of (fence seen - last timestamp)
against the CPU clock. Its slope is 0.364 ns per ns, and it goes flat,
with residuals of -0.06 to +0.10 ms over 22 five-second bins, at **52.083
ns per tick, which is 19.200 MHz**. The period printed in the line, from
`limits.timestampPeriod` (renderer.c:263 `gpu_ts_period_ns`), is 33.11 ns
(30.2 MHz). 19.2 MHz is the rate of Adreno's always-on counter. With the
fitted period:

| DOA fight, O4 pilot | ms |
|---|---:|
| the flip's finish plus the fence wait | 64.7 |
| GPU span, first to last timestamp | **63.7** |
| GPU start after the finish began | 0.9 |
| fence seen after the last timestamp | 0.1 |

- **The ~18 ms "excess" of sections 7 to 10 was this factor**, not time
  before or after the command buffer. The GPU is busy for the whole wait.
  This also explains "wait = 3.09 x R": 2 x R x 1.573 = 3.15 x R.
- **DOA on the Nova is GPU-bound at about 64 ms of GPU work a frame.** That
  is a ceiling of about 15.7 fps for the current GPU work, whatever the CPU
  side does. The brief's "<= 26 fps" came from the misread 34 ms span. **O4's
  bound is about 1 ms, not 18.** O1 (the lazy completion) moves the wait
  off the PFIFO thread but cannot shorten it. With O1, the frame would be
  bounded by max(GPU ~64 ms, the PFIFO thread's ~10 ms of Draw and Fin).
  Today it is Tot 67.9 ms, gfps 13. So O1's bound for DOA is **about 15.6
  fps, +1 to +2**, not the 26 fps ceiling. The lever that remains is the
  GPU work itself.
- **Every `hakuX-phase` GPU, R and X figure from the Nova reads 0.636 of
  the true value.** That covers slowdown462's and forza414's too, and
  every figure in this file before this section. The Thor was not checked:
  no `[o4]` run exists there. The fix is to calibrate `gpu_ts_period_ns` at
  start-up (vkGetCalibratedTimestampsEXT, or a fit like this one), in
  renderer.c. That is an instrument change, and this lane has not made it.
- **R/X, a hypothesis labelled as one.** In corrected units, pass 0 is
  about 30 us, then there is a gap of 30.6 ms, then pass 1 runs 30.6 ms. A
  tiler replays a render pass's commands once per bin. A timestamp written
  inside the pass is then overwritten by each bin, so it keeps the last
  bin's value. With two equal bins, the gap is the first bin, which is X = R
  exactly. The test is to read the pass's bin count (render area against
  GMEM) or to move the timestamp outside the pass.

## Why the last session did not finish, and this one (resumed 2026-09-27 21:27Z)

The last session ended on a wait, correctly. It had built the timestamp-period
calibration (#504, `tsperiod.md`), registered three predictions and queued four
priority-1 device requests, all outside the session. At 21:28Z none had run:
the Nova was on lane.forza414's Blinx pair and the Thor was held for a title
push and then for lane.titleroutes. Addendum 6 arrived at 21:15Z, after that
session had ended.

This session merged master (60 behind, no conflict) and did the parts of
Addenda 5 and 6 that need no device: sections 16 and 17. It registered and
queued one new A/B (section 16). #504's own legs are judged in `tsperiod.md`.

### 16. DOA's GPU cost per render pass (Addendum 5, item 2)

`passread.py --period 52.083 0-0-x-1790527190-flip474-1640480` reads the O4
pilot's `[o4]` lines over 151-288 s and restates them with the fitted period.
896 of the 1128 waited flips have nine passes; the table is over those. Times
are ms, medians, true units.

| pass | starts at | gap before it | inside it | gap + inside |
|---:|---:|---:|---:|---:|
| 0 | 0.00 | 0.00 | 0.04 | 0.05 |
| **1** | 31.28 | **31.23** (p10-p90 30.57-31.91) | **31.09** (30.49-32.03) | **62.33** |
| 2 | 62.40 | 0.02 | 0.02 | 0.04 |
| 3 | 62.42 | 0.00 | 0.31 | 0.31 |
| 4 | 62.74 | 0.00 | 0.07 | 0.07 |
| 5 | 62.80 | 0.00 | 0.03 | 0.04 |
| 6 | 62.84 | 0.00 | 0.01 | 0.02 |
| 7 | 62.85 | 0.00 | 0.01 | 0.01 |
| 8 | 62.87 | 0.00 | 0.42 | 0.43 |
| command buffer | | | | span 63.62, tail after the last pass 0.40 |

**One pass is 98% of the GPU's frame: 62.3 of 63.6 ms.** What that bounds,
for each suspect the addendum named:

| suspect | bound, ms per frame | from |
|---|---:|---|
| render-pass breaks (9.2 a frame, `hakuX-rpbrk`) | <= 0.97 | the eight small passes, gap + inside, summed |
| loadOp/storeOp on those eight passes | <= 0.97 | the same rows; a load or a store is inside its pass's row |
| resolve and download after the last pass | <= 0.40 | the tail |
| pass 1's own load and store | not separable | inside its 62.3 |
| the draws of pass 1 | <= 62.3 | what is left |

So no change to pass structure, load/store ops or downloads can take more
than about 1.4 ms of DOA's 63.6. The cost is the draws of one pass, or how
the driver executes them.

**The driver and its timestamps.** The Nova's driver is a Turnip build
("PurpleVK public driver", Mesa 26.3.0-devel, in the logcat's start-up lines).
lane.turnipfork pinned the Mesa series it is built from at
`~/hakux-work/mesa-turnipfork` (`4c18636110`). That source, not the binary,
is what was read:

- `tu_query_pool.cc:2108-2112`: a timestamp written inside a render pass goes
  into the pass's draw command stream. Its comment: "just write the timestamp
  multiple times so that the user gets the last one if we use GMEM".
- `tu_cmd_buffer.cc:3802` calls that stream once per tile in GMEM rendering,
  `:2773` once more in the binning pass when there is one, and `:4165` once
  in sysmem rendering.
- `tu_util.cc:509`: the binning pass runs only when the pass has more than two
  tiles. With one or two tiles every tile executes every draw.
- `tu_device.cc:1179-1296`: upstream reports `timestampPeriod` as 1e9 / 19.2e6
  = 52.083 ns, and its comment says the counter is fixed at 19.2 MHz. That is
  the value `o4clock.py` fitted. The build on the Nova reports 33.11 ns.

hakuX writes both of a pass's timestamps inside the pass (draw.c:3279-3300).
So under GMEM, `hakuX-phase`'s **R is the last replay of each pass, and X is
everything before it**: the binning pass if there is one, the earlier tiles,
and the loads and stores. X is not transfer time. That is section 15's
"replay" hypothesis, and the source says it is the driver's design.

**The guess this makes for DOA, labelled as one.** Pass 1's two halves are
equal within 2% at p10 and p90 over 896 flips of a fight. Two executions of
the same draw stream would be, if the stream's cost does not depend on which
tile it is clipped to. Two halves of the screen would not be. So the guess is
two replays of about 31 ms each, and the cost per replay is per draw or per
vertex, not per pixel.

Not established by reading: the tile count of DOA's pass (it needs the
attachment sizes and the device's usable GMEM), and which render mode the
driver's autotuner picks.

**The A/B, registered before any arm ran:**
`docs/testing/predictions/flip474-doa-rendermode.json`, one binary
(`795ea6b3af`), the env is the variable.

| arm | request | env |
|---|---|---|
| base | `1-1790540673-flip474-2311172` (#504's A arm, the same sha) | none |
| sysmem | queued this session, see Waiting | `TU_DEBUG=sysmem` |
| gmem | queued this session | `TU_DEBUG=gmem` |

- S1, the guess: sysmem's GPU span is at most 0.70 of the base's (60%).
- S2: sysmem's X/R is at most 0.25, against 0.98.
- G1: gmem equals the base, so the default is GMEM.
- F1: the frame follows, Tot down 12 ms or more and gfps up 2 or more.
- R0: if all three agree, the run cannot tell "no effect" from "this build
  ignores `TU_DEBUG`". lane.turnipfork showed `--env` reaches this driver's
  driconf options; nothing has shown it for `TU_DEBUG`.

**The result (2026-09-27, 21:41 to 21:57Z, the Nova, one session, MAX
regimen).** `phaseread.py`, `lockread.py` and `gfpsseries.py` over 151-288 s.
GPU, R and X are as printed, with the reported period; true ms is x 1.573.

| arm | request | gfps median (min-max) | Tot | cdef | GPU | R | X | X/R |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| base | `1-1790540673-flip474-2311172` | 16 (1-28) | 58.1 | 47.7 | 31.2 | 15.7 | 15.5 | 0.99 |
| gmem | `0-0-x-1790545474-flip474-43429` | 14 (11-17) | 64.4 | 53.1 | 34.4 | 17.0 | 17.4 | 1.02 |
| **sysmem** | `0-0-x-1790545474-flip474-43379` | **21** (18-40) | **41.0** | 29.8 | **19.6** | 19.3 | **0.3** | **0.02** |

| leg | verdict |
|---|---|
| M0 | holds: 35, 33 and 54 phase lines; the shots show the fight in every arm |
| E0 | holds: `env: TU_DEBUG=sysmem` and `env: TU_DEBUG=gmem` in their logcats, none in the base's |
| T0 | **fails for the base as written**: one line at 1 gfps, at 274.7 s. It is the KO, not a thermal collapse: the shots go fight, REPLAY, CONTINUE. sysmem (18 of 21) and gmem (11 of 14) hold. By the rule the base is void and is rerun once: `1-1790546289-flip474-398286` |
| S1 | **holds against gmem: 19.6 / 34.4 = 0.57.** Against the void base it is 0.63 |
| S2 | **holds: X/R 0.02.** The gap outside the passes is gone |
| G1 | holds against the void base: GPU 1.10 of it, X/R 1.02. The default is GMEM |
| F1 | **holds against gmem: Tot -23.4 ms, gfps +7.** Against the void base: -17.1 ms, +5 |
| R0 | not needed: the arms differ, so `TU_DEBUG` reaches this driver |
| H0 | holds in all three: longest gap 2.0, 1.5 and 1.2 s, lines to the end, no crash marker |

- **GMEM rendering executes DOA's draw stream twice, and sysmem once.** X
  equals R in every scene of the two GMEM arms (fight 15.5/15.7 and
  18.3/18.3, replay 15.3/15.0, the screen after it 8.2/8.2, CONTINUE
  12.8/12.6), whatever is on screen.
- On the CONTINUE screen, which all three arms reach, R is the same in both
  modes and only X goes: base 12.6 + 12.8, gmem 12.7 + 13.1, sysmem 12.4 +
  0.3. The three are at different spots of the same stage, so this is a
  like scene, not the same frame.
- In the fight one sysmem execution (19.3) is dearer than one GMEM replay
  (15.7 to 17.0). The opponents differ by run (Zack, Gen Fu, Tina), so that
  difference is not attributed.
- **What the windows are not:** the same fight. The survey route is blind and
  the opponent is drawn per run. A faster arm also reaches the KO sooner:
  the sysmem arm's fight ends at 265 s and its last 23 s are the screens
  after the KO, at 30 to 40 gfps. Its fight alone reads 21 to 22 gfps.
- The frame is still serial. In sysmem, cdef is 29.8 of Tot 41.0: the PFIFO
  thread still waits out the GPU's whole frame (section 14's O1).

lane.turnipfork ran the same three modes on Crimson Skies and found them flat
at 29 gfps. Crimson sits at its 30 Hz cap, so that run could show a cost and
not a gain. Its notes say to reopen "when a profile puts GPU time on the
critical path of an uncapped title". DOA is that title.

**Candidate fixes. Each figure is a bound, not a prediction,** except F-a's
first row, which is now measured.

| fix | what it takes | bound for DOA on the Nova |
|---|---|---|
| F-a: render in sysmem | **measured with the env: 14 to 16 -> 21 gfps, Tot 58 to 64 -> 41 ms.** The env is a test, not a fix. The app would have to ask per driver, at instance creation (`instance.c`, not this lane's file). Before that: the pgraph suites identical under `TU_DEBUG=sysmem`, and the other titles measured, because sysmem is the mode a tiler avoids for fill-heavy passes | measured, not a bound |
| F-a with O1 (section 14's lazy completion) | both | frame >= max(GPU 30.8 true, CPU 11) ms, **<= 32 fps**, from 21 |
| F-b: the cost of one replay | not measured. 31 ms over about 760 surface updates a frame (`[surf413] up`, roughly one per draw) is 41 us each; silicon draws the frame in under 16 ms. The next instrument is a per-pass count of draws, vertices and pipeline binds beside the pass's GPU time. It is in draw.c, which is not on this lane's row | unknown until counted |
| F-c: write a pass's timestamps outside it | draw.c `begin_render_pass` / `end_render_pass`, perflog only. R then means "inside passes" on a tiler too | an instrument fix; it moves no frame time |

### 17. lane.notify488's render-target-switch lead (Addendum 6)

The lead: on master, a rep of 500 quads and one render-target switch costs
93.7 ms in submit when the previous back buffer was not CPU-read, and 8.9 ms
when it was. Both figures are medians.

**Both tests have the same two humps. The medians are which hump holds more
than half the reps.** `stmodes.py` reads the suite's raw rows per rep
(A = master `0-0-x-1790531584-notify488-3150101`, B =
`0-0-x-1790529854-notify488-2739010`; a rep is slow when its submit is over
40 ms):

| run, test | slow reps | submit, fast hump | submit, slow hump | kick -> semaphore, fast / slow | slow after a slow rep | slow after a fast rep |
|---|---:|---:|---:|---|---:|---:|
| A `ST_Done_DOA` | 235 of 300 (78%) | 8.5 ms | 96.6 ms | 5.9 ms / 15 us | 74% | 97% |
| A `ST_Done_DOA_Read` | 75 of 300 (25%) | 8.5 ms | 95.0 ms | 8.2 ms / 13 us | 15% | 28% |
| B `ST_Done_DOA` | 299 of 300 | 7.1 ms | 99.0 ms | | | |
| B `ST_Done_DOA_Read` | 293 of 300 | 11.4 ms | 94.5 ms | | | |

- The CPU read does not reset a state that makes the next rep cheap. A quarter
  of the reps after a read are slow, and a fifth of the reps without one are
  fast. The read changes the odds.
- In a fast rep the guest submits in 8.5 ms, near silicon's 6.4, and then waits
  6 to 8 ms for the semaphore. In a slow rep the guest is held for about 88 ms
  more while it submits, and the semaphore is there 15 us after its last kick.
  So a slow rep is the PFIFO thread taking about 95 ms over the same 500
  quads and keeping pace with the guest, not falling behind it.

**A mechanism that fits, by reading. It is a hypothesis.**

- The suite kicks after every method, seven times a quad: pbkitplusplus's
  `Begin`, `SetDiffuse`, `SetVertex` and `End` each open and close their own
  pushbuffer block (nv2astate.cpp:332-342, 579-583, 641-645), and closing one
  is `pb_end`.
- When the PFIFO thread has caught up with the guest (`DMA_GET == DMA_PUT`)
  and the command buffer holds a draw, `pgraph_vk_process_pending_reports`
  calls `pgraph_vk_finish(VK_FINISH_REASON_STALLED)` (vk/reports.c:184-190).
- That finish ends the render pass and submits (draw.c:3513-3600). It does not
  wait for its own fence, but the rotation to the next of the three frame
  slots waits for that slot's (draw.c:3771-3790).
- So while the PFIFO thread keeps pace with the guest, every quad is its own
  command buffer and its own render pass, with a load and a store of the
  640x480 colour and depth, and the thread runs at the GPU's pace two
  submissions behind. (96.6 - 8.5) / 500 is 176 us a quad.
- When the thread starts a rep behind the guest, the kicks pile up, it never
  catches up mid-rep, and the 500 quads go in a few passes. That is the fast
  hump. Whether it starts behind is a race, and what the previous rep left to
  do at the first `surface_update` moves the odds.

What would confirm it: the suite run on a perflog build, reading `stl` in
`hakuX-stall` per rep. It should be about 500 in a slow rep and under 5 in a
fast one. Neither run above was a perflog build.

**It is not DOA's cost, and it names no path in vk/surface.c.**

| title (run) | stalled finishes per 60 flips (`stl`) | per frame |
|---|---:|---:|
| DOA (`0-0-x-1790527190-flip474-1640480`) | 0, 1, 0 | 0 |
| AUF (`0-0-x-1790530526-flip474-2801414`) | 0 | 0 |
| Blinx (`0-0-x-1790530526-flip474-2807172`) | 72 to 84 | 1.2 to 1.4 |

DOA's frame has no stalled finish and one expensive pass (section 16). The
500-quad rep has up to 500 cheap ones. So this case does not belong in DOA's
per-pass table, and there is nothing here to hand to lane.forza414. For
Blinx, 1.3 finishes a frame each add a submit and a pass's load and store;
that is not priced here.

**Other titles, from runs on disk. X/R says which are rendered twice.**

| title (run, window) | GPU | R | X | X/R |
|---|---:|---:|---:|---:|
| DOA (above) | 31.2 | 15.7 | 15.5 | 0.99 |
| AUF (`0-0-x-1790530526-flip474-2801414`, 299-420 s) | 29.1 | 14.4 | 14.6 | 1.01 |
| Blinx (`0-0-x-1790530526-flip474-2807172`, 255-411 s) | 24.1 | 20.0 | 2.5 | 0.13 |
| Forza (`0-0-x-1790533007-forza414-3417242`, 125-240 s) | 24.2 | 19.3 | 4.8 | 0.25 |

AUF reads like DOA. Blinx and Forza do not: most of their GPU time is in
the last execution of their passes. What sysmem does to each is not
predicted from this table; it is the next measurement.

### Waiting (this session)

See `tsperiod.md` for #504's requests. Section 16's base rerun is
`1-1790546289-flip474-398286`.

## Why the last session did not finish, and this one (resumed 2026-09-28 01:02Z)

The last session ended waiting on the sysmem batch, which was on the
device. That was the right call. All twelve requests finished by 00:59Z,
and #504 folded at 01:12Z.

## 17. Turnip's render mode: measured, and the default taken back (#516)

Everything is in `sysmem.md`. In short:

| | |
|---|---|
| pixels, no env against `TU_DEBUG=sysmem` (Thor, 1059 captures) | 46 differ: 37 in the env run alone (every `ZPass_pixel_count` capture prints a ZPASS report of 65,536 instead of 40,960, and `GPUAAWriteAfterCPUWrite`), 9 run to run |
| pixels, master against the default `1a8f16ef16` (Nova, 1059 captures) | 6 differ, all run to run; **none of the 37 moved** |
| AUF, Nova | GPU 0.53 x, gfps 16 -> 24 |
| DOA, Nova, the default with no env | X/R 0.02, gfps 13 -> 21 |
| Forza, Thor | GPU 0.91 x, gfps 14 -> 15 |
| Blinx, Thor | GPU 1.05 x, gfps 16 -> 14, not separated from the view |
| Crimson, Thor, capped | GPU 1.00 x, gfps 29 -> 27, not separated from run order |

A global default is not shown pixel-inert, so `1a8f16ef16` is reverted. The
policy the data supports is per title, and the app has the place for it
(per-game overrides). That is lane.rendermode474's since board wave 271.

**What moved the 37 captures is open.** The env run on the Thor was also
the only run that started from a kept shader cache, and the default build's
arm on the Nova, which sets the same flag, moved none of them. `sysmem.md`,
"The second pair", has the evidence and the two short runs that separate
the causes. The ZPASS report being a constant is #527.

## Why the last session did not finish, and this one (resumed 2026-09-28 01:57Z)

The last session ended waiting on the arms job's pair for
`flip474-sysmemfix-pgraph.json`, which was queued behind lane.drain474's
arms. That was the right call. The pair finished at 01:56Z. This session
read it, corrected the cause named from the first pair, and took #516 to
ready. Nothing of this lane's is queued or running.

Open, for whoever is next on the render mode:

- The two runs in `sysmem.md` ("The two runs that separate it").
- `Surface_pitch::Swizzle` has four contents in the four runs of the
  27-suite disc. The 18 earlier runs on disk have three, and repeats of one
  apk agree (`12cad8c22f69`, six runs). So it began to vary run to run on
  this disc or since 2026-09-26. Nobody holds it.
- Blinx and Crimson under sysmem, with the sysmem arm first.

## Do not repeat

- Do not read a median of timing reps without looking at the rows. The
  Signal timing suite's 500-quad reps have two humps 88 ms apart, and a
  median reports only which one is larger (`stmodes.py`).
- Do not read `hakuX-phase`'s R and X as render and transfer on a tiler. Both
  of a pass's timestamps are inside the pass, and the driver keeps the last
  tile's.
- Do not trust `limits.timestampPeriod` on Adreno. Fit it against the CPU
  clock first (`o4clock.py`): the Nova reports 30.2 MHz and ticks at 19.2.
  A drift check (K0) is what caught it. Keep a drift check on any
  cross-clock reading.

- Do not read "the same call site" as "the same fix". A completion with three
  branches has three waits; check which branch each title takes before
  measuring one title on another's fix.
- Do not make every PGRAPH read lockless without knowing the polled register:
  STATUS always reads idle, so the lock is the only thing holding an idle
  poll off mid-batch.
- Do not attribute a vCPU lock wait to the puller phase where the wait
  *began* and stop there: the wait lasts until the method ends. Read
  `[surf413]`/`hakuX-phase` in the same logcat for what the method spent.
- Do not rank a counter's registers by count when the question is wait.
- Do not compare fps across A/B runs without looking at the shots: DOA's
  survey route can land a window on a KO replay (A2), and that moves gfps.
