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

## Waiting

On `1790491858-flip474-658414`. When it lands: `lockread.py` on it, judge the
pilot legs, write `pilots/flip474.ok`, then pick R or F by P1-P3, register
`flip474-ab.json` (A = 7f13054916, B = the fix) and only then write the fix.

## Do not repeat

- Do not make every PGRAPH read lockless without knowing the polled register:
  STATUS always reads idle, so the lock is the only thing holding an idle
  poll off mid-batch.
