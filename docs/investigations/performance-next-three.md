# The three remaining performance levers, scoped

Written 2026-09-11 from three read-only investigations run in parallel, after
the critical-path work in
[`frame-pacing-and-parallelism.md`](frame-pacing-and-parallelism.md). Nothing
here is implemented.

Ranked by expected return divided by blast radius, which is the only ranking
that makes sense in a fork that takes no downstream updates.

## 1. The audio voice lock — FIXED and validated (`01490afe3c`)

**This was a bug, not a tuning question.** Worth about 5% of the thread that
bounds the frame.

Each worker now releases a voice the moment `voice_process` returns for it,
instead of every voice being held until the last worker finishes. Two
independent measurements agree:

| | before | after |
|---|---|---|
| `voice_lock` share of the guest CPU thread | 4.98% | **1.41%** |
| Crimson Skies heavy-section frame time | 50.3 ms | **48.2 ms** |

The frame-time arm is three runs each side, alternating to spread thermal and
battery drift, filtered to samples where the title is missing its own 30 fps
target and so is genuinely emulator-bound. **All three "after" runs came in
faster than all three "before" runs** (48.2, 47.7, 49.3 against 49.5, 50.4,
50.3), which is the statistic worth quoting: comparing medians to the
within-arm spread of 1.6 ms alone would have been marginal.

Still outstanding: nobody has *listened* to it. This changes audio locking and
no measurement here substitutes for a person hearing a scene with many voices.

The original finding follows.

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

### 2026-09-13: implemented, and the premise above is retracted

**The trap dissolves, and the lever does not work for a different reason.**

*The trap.* Implemented in `5aa253f12a`. The block extent does not have to go
into cflags at all. `tb_gen_code` reads `CF_COUNT_MASK` into a local
`max_insns` and passes *that* by pointer to `setjmp_gen_code`; nothing writes
it back. Narrowing the local leaves the hash key bit-identical, so both lookup
sites find exactly the block they find today, and the reproducibility problem
never arises. The key is a statement about what was *requested*, not about what
was produced — which the tree already relies on, since the code-too-large path
halves `max_insns` and retranslates without touching cflags, and
`translator_loop` stops early on page crossings and I/O whatever maximum it was
given.

It is applied only when the request is the permissive default
(`CF_COUNT_MASK == 0`, "up to `TCG_MAX_INSNS`"). Every caller needing an exact
count sets a nonzero one — icount's `insns_left`, breakpoint pages, precise SMC
in `tb-maint.c` and `watchpoint.c`, `cpu_io_recompile` (n is 1 or 2), and the
untranslatable-page one-shot — and those pass through untouched. Narrowing a
permissive maximum is the one thing this cannot get wrong. The latch is kept
anyway, so a run's block-length profile depends on the build rather than on
history.

*The reason it does not work.* **The premise this section was scoped on is
false.** "The invalidation is already range-precise" — quoted from
[`frame-pacing-and-parallelism.md`](frame-pacing-and-parallelism.md), now
corrected there — is not true in this tree. The range test is wrapped in
`#ifndef XBOX` (xemu `703566ce33`, 2021-10-04, no rationale recorded), and
`PAGE_FOR_EACH_TB` in the softmmu half ignores its range arguments, so a guest
store discards **every** block on the page.

Smaller blocks save work by letting a store *miss* a block. No store can miss
one here. And the cost they add is real: on the profile, `tb_gen_code` is 19.1%
of the bounding thread and `tb_link_page` is 11.6% of that, so most of the cost
of generating a block is per-block, not per-instruction. Halving the extent
halves the smaller half and doubles the larger.

So `HAKUX_SMALL_BLOCK_INSNS` ships at **0, disabled**, and the arm that turns
it on is one commit changing one constant. It is committed off rather than not
committed because the arm is worth having ready and this is a prediction, not a
proof.

*What the lever actually is.* Restoring the range test, which is upstream
QEMU's own behaviour and what every non-xemu target does. The prize is not the
discarded code — it is that `tb_page_add` arms code-write detection only on a
page's empty-to-non-empty transition and the invalidator disarms on empty, so a
store that empties a page buys a full arming TLB walk on the next generation
there (`tlb_reset_dirty`, 10.6% self, the largest single symbol on the thread)
and a store that leaves one block behind buys none. **The two levers compose:
the range test is what lets a block survive, and smaller blocks make survival
more likely.** Neither pays alone.

That change is a five-year-old SMC hedge with no recorded reason, touching
every guest instruction in every title, so it is **not** made on this
reasoning. `5f98d1ee5a` adds the counters that size it — `sp` (blocks a range
test would spare) and `ws` (page-emptying events it would prevent) — on the
always-on `hakuX-pages` line, read by `docs/testing/perf/tcg_pages.py`, legs
pre-registered in
`docs/testing/predictions/tcg-whole-page-invalidation.json`. The counters
decide it; the code reading only says where to look.

*What would refute all of the above*, and it is one number: if `sp_share` comes
back near zero, pages hold about one block each at invalidation time, whole-page
and range-precise invalidation coincide in practice, and this section stands as
originally written. That is registered as L1 and it is the leg I am least sure
of.

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

### 2026-09-13: two further floors, and the one that is fixed

**A dispatcher soak injects no input.** `soak_title.sh` boots the title and
holds it. The `pad.sh mash` sequence that reaches Crimson Skies' heavy sections
lives in `run_perf.sh`, a hand-run script against an attached device — so the
one request path an agent may use cannot reach the scene with headroom at all,
and the heavy-section frame time the audio voice-lock fix was judged on is not
available from a soak. That fix's own filter is undocumented too: the `G > 35`
ms threshold had to be recovered by reproducing its six published numbers.
Also `--runs N` does nothing on the soak path (the dispatcher calls
`soak_title.sh` once), so three runs means three requests, and `--wait` raises
`KeyError: 'disc_id'` on a soak result.

**And a median gfps measures how busy the device is** — now demonstrated from
data already on disk rather than argued. Two Galleon soaks, both on the nova,
both reporting `gfps max=29 p90=29`, with medians of **27 and 17**. Identical
ceiling, median differing by ten.

**What was done about it.** Not a better average over frame time. For the
retranslation work the mechanism is *counted*, not timed — blocks discarded,
blocks a range test would spare, page-emptying events, arming walks, mean block
length — and those counts are on the always-on `hakuX-pages` line, independent
of what scene the title is in and of how busy the device is.
`docs/testing/perf/tcg_pages.py` reads them, and three things in it are the
actual instrument work:

- **It judges on ratios, not rates.** On those two soaks the absolute
  per-window counts vary three- to fivefold *inside one run* — `tossed` spanned
  1,434 to 4,985 — because they scale with how much the guest happens to be
  writing. Same failure as the median. `toss_per_gen` divides it out and
  separated 0.68 from 5.34 on the same pair, where every absolute count
  overlapped. (Incidentally: Galleon's waste ratio is under 1, where this
  document quotes 2.8:1 for Fuzion Frenzy. That ratio is a property of the
  title.)
- **The replicate is the run, not the window.** Per-run medians, every run in
  one arm against every run in the other — the audio fix's standard. An
  all-samples rule over windows would tighten with every window a longer soak
  produced, so one outlier in a 29-window arm would veto a real effect. Fewer
  than three runs an arm reports NOT JUDGED and prints the window spread as the
  noise floor, because one run cannot satisfy a rule about runs.
- **It refuses the pairings that have already cost controls**: arms spanning two
  handhelds, an arm mixing refs, and both arms on one ref — the last reported
  as a valid noise-floor run, since that is what it is.

Frame time is still read, as the cost leg, as a ceiling (max and p90 of `gfps`,
plus the floor of `G`), never as a median.

**Still not fixed:** reaching a headroom scene from a soak. That needs input
injection in `soak_title.sh`, which is shared dispatcher infrastructure and was
not touched with ninety requests in flight. Until then, any lever whose only
observable is frame time is unmeasurable through the request path, and the
levers worth taking are the ones with a counted falsifier.

## The debt handed over from the correctness work

Both items were landed for accuracy with their throughput cost explicitly
deferred here, and the reason recorded. Priced 2026-09-13.

### #59's 565 round-trip — REAL mechanism, UNPRICED, and the count is one printf away

An `R5G6B5` surface later sampled as a texture is refused the GPU-side view
bind at `pgraph/vk/texture.c:1290`, in `check_surface_to_texture_compatiblity`:
a converted format's host image does not hold the guest's bytes, so there is
nothing for `vkCmdCopyImage` to move or for the surface's own view to decode.
Correct, and the reason 565 is converted at all is that silicon's 5-to-8
expansion is spec-fixed to an exact ratio.

The cost per occurrence is not a copy. It is `vkCmdCopyImageToBuffer`, then
**`pgraph_vk_finish(VK_FINISH_REASON_SURFACE_DOWN)`** — which ends the render
pass, flushes the reorder window and the batched draw queue, submits, and
**waits on a fence**, on `nv2a.pfifo_thread`. `OPT_SURF_TO_TEX_INLINE` is 1, so
that wait is unconditional on this path. Then a full-texture CPU hash every
frame the surface is redrawn, then a scalar 565-to-RGBA8 decode, then a
double-size staging upload. From the same Crimson Skies instrumented run,
`Fin:3.1 (Sub:1.0 Fen:2.0)` ms covers 0.17 surface-downs plus a present and a
flip, which puts one forced surface-down sync at **order 1-2 ms**.

**So the verdict turns entirely on a count nobody has taken, and this is the
third place in the tree to say so** (`nv2a_issues.toml`,
`packed-texel-expansion.md`, and #59 itself). It is **theoretical iff the count
is 0 per frame**; at 1/frame it is 3-5% of frame time and at 5/frame 15-25%.
`Surface_clip/rt_*` proves the shape occurs seven times on a test disc; no
title has been counted.

Two things stand in the way of just counting it, and one is now removed:

- `NV2A_PROF_SURF_TO_TEX` and its `_FALLBACK` **have been incremented at four
  sites in `vk/texture.c` all along and printed nowhere** — the exact quantity
  #59 names as the one that would settle this, collected and discarded. Now
  printed as `S2T:` on the `xemu-work` line (`5f98d1ee5a`).
- It still will not reach a plain soak, because `nv2a_profile_inc_counter` is a
  no-op unless `NV2A_PERF_LOG`, which perturbs what it measures by clocking
  every puller method. An always-on increment belongs at
  `vk/texture.c:1627-1631` — beside the existing `trace_` call in the
  refused-alias branch — keyed on
  `surface->shape.color_format == NV097_SET_SURFACE_FORMAT_COLOR_LE_R5G6B5`.
  **Not** on surface creation (a 565 surface never sampled costs nothing) and
  **not** on texture bind (the clean-binding early-out returns before this
  point, so a bind counter over-counts by roughly 500x). `vk/*.c` is the
  renderer lane's, so that one line is handed over rather than taken.

Also worth knowing: `xemu-surf`'s `download_count` does **not** bound this. It
is incremented at exactly one site inside the `surface_update` swap path and
does not count the texture-path download at all — wrong event, not a subset.

### #6's DXT1 ordered dither — decode near-theoretical, cache pressure REAL and unmeasured

Three findings, and the middle one is a correction to this stream's own notes.

- **The decode is small.** Per texture-cache *fill*, not per draw:
  `s3tc_decompress_2d` is reached only from `upload_texture_image` <-
  `create_texture`, gated on `texture_dirty`. On the pre-fix Crimson Skies run
  `TexU` is **1.15 fills a frame, and zero in 19 of 46 sampled frames**, all
  formats pooled. A 256x256 DXT1 fill is order 0.1-0.5 ms, so **at most ~0.5 ms
  a frame and 0 ms in 41% of frames** — under 1.5% of a 37-40 ms frame.
- **But it is not off the critical path, which is what the deferral assumed.**
  The "s3tc workers" row in
  [`frame-pacing-and-parallelism.md`](frame-pacing-and-parallelism.md) reads as
  a background pool and is not one: `s3tc_decompress_2d` forks up to three
  helpers, runs the last chunk on the caller and joins before returning, and
  below 128 blocks is fully single-threaded on the caller — which is
  `nv2a.pfifo_thread`. DXT1 also lost its NEON path, deliberately, since the
  dither is scalar. Corrected in that document. So a load screen filling 50-200
  textures in one frame pays all of it serially on the thread that does every
  draw; `Tex:0.0` was steady-state gameplay only.
- **The unpriced number is 8x host bytes.** The fix routes DXT1 to software, so
  a DXT1 texture's host image goes from 0.5 B/px (BC1) to 4 B/px (RGBA8), and
  `estimate_texture_image_bytes` charges the cache by host format — so the
  eviction budget holds about eight times fewer DXT1 textures. A working set
  resident at 1.15 fills/frame can thrash post-fix, which moves the fill count
  itself. Nothing existing bounds that.

**Verdict: record the decode as theoretical, with `TexU ~= 1/frame` as the count
that makes it so. The cache-pressure risk is the real item and is unmeasured.**
The instrumentation for both is one array at `vk/texture.c:648` keyed on
`state->color_format`, plus resident bytes and eviction count from the trim
loop — again the renderer lane's file.

**A date caveat that applies to every number in this section.** Every log in
`docs/testing/perf/` is 2026-09-11. Both #59 arms and both #6 arms are
2026-09-12. So `Sd = 0.17/frame` is a *pre-fix* figure from a binary where 565
still took the direct view bind, and cannot bound the post-fix count; `TexU` is
format-agnostic and does bound fills from above, subject to the host image
sizes having changed. **No post-fix performance run of any kind exists.**
