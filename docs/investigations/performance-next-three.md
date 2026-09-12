# The three remaining performance levers, scoped

Written 2026-09-11 from three read-only investigations run in parallel, after
the critical-path work in
[`frame-pacing-and-parallelism.md`](frame-pacing-and-parallelism.md). Nothing
here is implemented.

Ranked by expected return divided by blast radius, which is the only ranking
that makes sense in a fork that takes no downstream updates.

## 1. The audio voice lock is a spinlock held across a whole frame

**This is a bug, not a tuning question.** Worth about 5% of the thread that
bounds the frame, roughly 2 ms.

`voice_lock()` in `hw/xbox/mcpx/apu/vp/vp.c:133` is not a mutex. It takes
`d->vp.voice_spinlocks[v]`, a `QemuSpin`, and `qemu_spin_lock` is a bare
exchange-and-`cpu_relax` loop with no futex and no yield. What it protects is
a 256-bit bitmask, `d->vp.voice_locked[4]`.

The audio thread acquires the spinlock of **every active voice** in
`voice_work_acquire_voice_lock_for_processing` (`vp.c:1642`) and returns still
holding them. They are released only in `voice_work_release_voice_locks`
(`vp.c:1666`), called after `qemu_cond_wait` on the workers finishing
(`vp.c:1747`). So the locks are held across the list walk, the worker
wake-ups, DSP and voice processing, and mixbin accumulation: hundreds of
microseconds, longer with fewer workers.

Meanwhile the guest CPU thread hits the same spinlock from `fe_method`
(`vp.c:646`) on five register paths, of which `NV1BA0_PIO_VOICE_LOCK`
(`vp.c:176`) is by far the most frequent and does no work at all beyond
setting a bit. DirectSound brackets every per-voice parameter update with a
lock and unlock pair, so it fires constantly. The vCPU then spins
uninterruptibly, burning a core rather than sleeping, for as long as the audio
frame takes.

Note the code already anticipates this: `vp.c:645` carries a TODO saying these
should queue commands instead. Two of the five sites mutate guest memory and
need ordering; none needs a spinlock held across a frame when only a bit test
is required.

## 2. Smaller translation blocks on thrashing pages, with one real trap

Worth about 4 ms, against `tb_gen_code` at 19% of the thread.

The hook exists. `tb_gen_code` (`accel/tcg/translate-all.c:326-336`) is the
one place that has both the physical page and still-mutable cflags, and it
already hosts a per-PC policy override for this fork's tier-1 mechanism at
`:451`. Block extent is controlled by `CF_COUNT_MASK`, the low nine bits of
cflags (`include/exec/translation-block.h:86`), consumed as `max_insns`.

Two things it needs. `PageDesc` (`accel/tcg/tb-maint.c:200`) is just a lock
and a `first_tb` pointer with no counters, and `page_find` is file-local, so
a per-page invalidation count means adding a field and exporting the lookup.

**And the trap: cflags is part of the TB hash key.** A page-derived
`CF_COUNT_MASK` has to be reproducible identically at both lookup sites,
`cpu_exec_loop` (`cpu-exec.c:1316`) and `helper_lookup_tb_ptr`
(`cpu-exec.c:749`), or lookups miss and the thrash gets worse rather than
better. That rules out a policy that varies as a counter climbs. It has to
latch: once a page is marked small-block it stays marked, never unlatching.
Implementable, but it is the whole design constraint.

There is no existing adaptive behaviour to build on. The only invalidation
bookkeeping in the tree is one global counter, `tb_phys_invalidate_count`.

## 3. The threaded draw path is much less built than it looked

**Correcting an earlier claim of mine.** I described this as a design that was
done with only the execution half missing. That was too generous. The
transport works; the state cut does not exist.

- `RCMD_DRAW` falls through `default: break;` (`render_thread.c:342`) and is
  silently freed. So do `RCMD_CLEAR_SURFACE`, `RCMD_IMAGE_BLIT` and
  `RCMD_SURFACE_UPDATE`.
- `r->active_snap` (`renderer.h:1069`) is **never assigned**, so the
  snapshot-aware `pgraph_vk_reg_r` always falls through to the live register
  file and the snapshot's 0x2000-word register copy is dead.
- Worse, the shared GLSL layer bypasses the snapshot by construction: the
  uniform setters take `PGRAPHState *` and read live state across roughly 93
  direct register reads in `pgraph/glsl/*.c`, called from inside the draw.
- The snapshot omits about ten fields the draw path reads, including line
  width, stipple pattern, back colour material, surface type and the texture
  matrix data, and the draw writes back into `pg` as well.
- Per-draw payloads are unpopulated, and `vertex_attributes` is copied by
  value so `inline_buffer` remains a live pointer into `pg`.
- `pgraph_vk_submit_worker_init` has no caller and is superseded by the
  semaphore chaining in `process_finish`. It is dead code.
- The existing draw queue does provide deferral, but by *temporarily
  overwriting* `pg->regs_` and seven generation counters and restoring them
  (`draw.c:3884-3907`). That is a same-thread trick which becomes a data race
  the moment replay moves off the pfifo thread.

So this is not a wiring job, it is a refactor of how the shared shader layer
reads state. **Recommend leaving it and taking the texture poll batching as
the renderer item instead**, which is contained and has a measured size.

## Prerequisite: the benchmark cannot yet show a 2 ms gain

Two Fuzion Frenzy runs agreed to 0.1 ms on the median frame time, which is
ample precision for effects of this size. But both landed in a scene that
**holds** 60 fps at 16.6-16.7 ms. A change that saves 2 ms shows nothing
against a vsync cap.

The four-player minigame observed earlier ran 21 ms and 43-47 fps, which is
where the headroom is. Reaching *that* scene reproducibly is a prerequisite
for measuring any of the three above, and the harness does not do it yet.
