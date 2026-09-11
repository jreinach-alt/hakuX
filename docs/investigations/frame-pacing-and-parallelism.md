# The 30 fps cap, and where the work could be split

Measured 2026-09-11. Retroid Pocket Nova, Adreno 740, Turnip T30. Builds
`33557e82ab` through `9edf95861d`. Harness in `docs/testing/perf/`.

Three questions: what holds Crimson Skies at 30 and can we override it; what
parallelising the renderer would involve; and whether this emulator spreads
work the way the NV2A's own engines did.

## 1. The cap is the game's

Three measurements, each ruling out one explanation.

**The floor is exact and it is not noise.** Crimson Skies' flip interval
floors at 33.2-33.3 ms in every run at every internal resolution, and when it
is there the emulator delivers exactly 2.00 VBLANKs per flip, ten samples
running. When it misses, the ratio goes to 2.5, 3.0, 3.5 and wanders with the
scene. A title that misses a deadline does not produce a stable 2.00; that is
an attractor, not a coincidence.

**It is not derived from counting VBLANKs.** Halving the emulated refresh to
30 Hz, with deferral off, left the interval at 33.3 ms and the rate at 29-31.
A title asking for every second VBLANK would have halved again to 15. So it
is pacing itself by elapsed time, not by refresh ticks.

**It is not a wall of ours.** Ninja Gaiden Black on the same build averages
25.9 to 31.4 ms and puts individual frames at 13.2 to 18 ms, which is 55 to 75
fps. The emulator can deliver intervals well under 33.3 ms. Crimson Skies does
not, because it does not ask to.

That last one matters more than it looks. The guest CPU thread runs at 85%
during Crimson Skies gameplay, and 85% of a 39.7 ms frame is 33.6 ms, which
sits close enough to the 33.3 ms floor to look like the cause. It is not: had
it been, no title on this build could beat it, and one does.

**Can we override it? Not from here.** The title's simulation advances on a
33.3 ms step measured in time. Forcing more presents would either show the same
frame twice or run the game fast. Changing that is a patch to the game, not a
setting in the emulator. **For this title the target is a locked 30**, which
we hold in light scenes and lose in heavy ones.

### What we found instead: the unlock machinery does not work on the case it was written for

There is an adaptive VBLANK deferral system in `nv2a_vblank_timer_cb` whose
comments are explicitly about titles getting "trapped at 30fps". It has an
unlock mode that widens the deferral window. Crimson Skies never enters it.

The entry condition is a frame time already under 1.5 refresh periods, and the
exit condition is 2.5 periods. **A title sitting at two periods can never
satisfy the entry condition, however much headroom appears.** The gate asks for
the state it exists to produce. Anything that starts slow, as this title does
through its boot and cutscenes, stays locked out for the session.

Forcing it on (`HAKUX_FORCE_UNLOCK=1`) does not help and does harm:

| | frame rate | VBLANK jitter | defers per 2 s |
|---|---|---|---|
| adaptive, as shipped | 17-29 | 1.7-2.2 ms | 43-57 |
| adaptive, unlock forced | 15-19 | 6.3-7.2 ms | 60-62 |
| simple VBLANK, no deferral | 17-29, cruise 33.2-33.9 ms | 0.0 ms | 0 |

Deferral is distorting the guest's timebase by several milliseconds per
refresh and buying nothing here. **On this title, `simple_vblank` is equal or
better on every measure.** That is one title; the setting exists because
others presumably benefit, and that should be measured before anything
changes. But the entry-condition flaw is worth fixing regardless.

## 2. The threading model as built

Thread identity had to be established by logging tids, because QEMU names its
threads only on request and everything it spawns otherwise reports the
parent's name. Roles are now tagged at startup under `hakuX-threads`.

| thread | role | gameplay load |
|---|---|---|
| TCG vCPU | guest CPU emulation | **85%** |
| `nv2a.pfifo_thread` | pusher, puller, PGRAPH methods, **all Vulkan translation** | **48%** |
| `pgraph.vk.render` | submit, fence wait, downloads, display sync | ~4% |
| `pgraph.vk.compile` | shader compilation | small |
| `mcpx.apu_thread` + voice workers | audio | small |
| s3tc workers | DXT decode | on demand |
| QEMU main loop, AIO, SDL | housekeeping | 6-11% each |

So the emulator is already threaded in more places than the NV2A had engines.
The gap is specific: **method decode and Vulkan draw translation share one
thread, and that thread does the expensive half of the frame.**

### Three pieces of the split already exist and none are connected

- `RenderCommandSnapshot` enumerates exactly which PGRAPH state a draw depends
  on, which is the hard part of the design. It is populated only under
  `#ifndef NDEBUG` and nothing consumes it.
- `RCMD_DRAW` is a render-command enum value with **no handler** in
  `render_thread.c`.
- `pgraph_vk_submit_worker_init` is implemented and **never called**, so that
  thread is never created.

The design was done and the execution half was not built.

## 3. What the NV2A did, and where it lands

| NV2A engine | what it was | where it goes here |
|---|---|---|
| PFIFO pusher and puller | fetch commands, feed PGRAPH | one thread, with the below |
| PGRAPH state and command | decode methods | same thread |
| 2 vertex units | vertex shading | host GPU |
| 4 pixel pipelines, 8 TMUs | raster, texture, blend | host GPU |
| PCRTC / PRAMDAC | scanout, VBLANK | QEMU timer |
| MCPX APU, 2 DSPs | audio voices | own thread plus voice workers |
| CPU, one core | game code | TCG vCPU thread |

**The data-parallel half maps correctly and is barely used.** Everything the
NV2A did across its pixel pipelines and vertex units is on the host GPU, which
sits at 25% busy pinned to 220 MHz of an available 680. That is roughly 8% of
the part.

**Mirroring the rest of the block diagram is not the goal.** The hardware's
pusher and puller ran concurrently to hide DRAM latency, not to add
throughput. Recreating that split with threads would buy synchronisation cost
and nothing else. The useful question is not "what did the chip do in
parallel" but "what in *our* pipeline has no data dependency on what".

## 4. Where the parallelism actually is

The draw path splits cleanly on one line: whether a step has to observe guest
memory at its exact point in the command stream.

**Ordered, guest-coupled. Must stay on the puller.** Method decode. Resolving
which texture and vertex memory a draw reads. Capturing vertex data. Validating
textures against the dirty bitmap. These see guest RAM the CPU thread is
concurrently writing, so their position in the stream is their meaning.

**Pure translation. Has no guest-memory dependency once the above has run.**
Pipeline key construction, pipeline cache lookup and creation, descriptor set
allocation and writing, command buffer recording. This is bookkeeping over
state already captured.

Against the measured 19.5 ms draw phase at 1x, the second group is most of
`Pipe` outside texture validation, plus `Desc`, `Setup` and `Cmd`. Call it 4
to 11 ms depending on where `pgraph_vk_bind_textures` falls, which needs a
finer timer to settle.

### Step 1 is done, and it reorders the rest

Measured 2026-09-11 with the always-on `Ri` figure, Crimson Skies, one run,
`simple_vblank` on. The title gives both populations: its cruise is self-paced
at 30 and says nothing about the ceiling, its heavy sections are missing its
own target and are genuinely emulator-bound. Only the second is read here.

| emulator-bound frames | ms |
|---|---|
| frame | 50.2 |
| guest CPU thread busy | 41.5 |
| renderer busy | 29.0 |
| renderer idle, waiting on the guest | 21.2 |

The two poles are far apart, and the bounds follow directly:

- **Renderer cost to zero** bounds the frame at the guest's 41.5 ms, which is
  24 fps against 20 now. About a fifth.
- **Guest cost to zero** bounds it at the renderer's 29.0 ms, which is 34 fps.

**The guest CPU emulation is the critical path.** The guest is busy 83% of the
wall clock and blocked on the renderer for the remaining 8.7 ms of the frame,
which is the whole of what renderer work can recover.

That is not what the ranking below assumed. Texture binding at 7.2 ms is still
the largest single renderer item, but it sits inside the smaller pole: even
removing all of it cannot beat the 24 fps bound, and would realistically
return a few percent. It stays worth doing, and it is no longer the thing to
do first.

### What the guest thread is doing

Profiled with simpleperf on the device, two independent runs of 20 and 25
seconds during the same gameplay sequence. A `user` build refuses
`perf_event_open` on a bare pid, but `--app` on a debuggable package with the
software `cpu-clock` event is permitted, which is how these were taken.
Reports in `docs/testing/perf/run-2026-09-11-crimson-profile-*.txt`.

Top of the critical-path thread, both runs agreeing to a tenth of a percent:

| share | symbol | what it is |
|---|---|---|
| 10.6% | `tlb_reset_dirty` | walks the TLB clearing dirty flags |
| 8.4% | `tcg_flush_jmp_cache` | translation block jump cache flush |
| 5.2% | `qht_lookup_custom` | translation block hash lookup |
| 5.0% | `voice_lock` | **audio voice lock, on the guest thread** |
| 3.9% | `flush_idcache_range` | icache flush after code generation |
| 3.9% | `helper_lookup_tb_ptr` | translation block lookup |
| ~2% | `tb_lookup_cmp`, `mmu_lookup1` | more of the same two families |

**The thread that bounds the frame is not mostly executing guest code.** The
two largest families are memory dirty tracking and translation-block
lookup and invalidation, and they are emulator bookkeeping rather than
emulated work. `voice_lock` at 5% is audio contention landing on the wrong
thread entirely.

Two caveats on reading this further. The build omits frame pointers and DWARF
unwinding did not recover userspace callers, so **which** call site drives
`tlb_reset_dirty` is not established here; a frame-pointer build would settle
it and is the obvious next step. And the per-symbol shares in the saved report
do not sum to 100, so treat the individual rows as sound and any grouping of
them as not yet validated.

What this does establish is that the dirty-tracking hypothesis below is the
right thing to test first, and it now has a number attached rather than being
a guess.

### The dirty-tracking lead, sized

`pgraph_vk_poll_bound_textures` runs **before every draw**, and for each bound
texture unit asks the dirty bitmap whether the guest rewrote it, plus a second
query for the palette. It exists for a correctness reason recorded in its own
comment: a CPU rewrite of texels changes no register and no generation counter,
so without the poll `Texture_CPU_Update` drew its second quad from the first
upload and every cube-map dot-product test sampled a stale cube.

Counted on device, Crimson Skies, always-on:

| | per guest frame |
|---|---|
| dirty-bitmap test-and-clear calls | **~1,480** |

At 18 fps that is about 27,000 a second. Each call goes
`memory_region_test_and_clear_dirty` → `physical_memory_test_and_clear_dirty`
→ `physical_memory_dirty_bits_cleared` → `tlb_reset_dirty_range_all`, which
walks **every CPU's TLB**. The *clear* is the expensive half, not the test.

That is consistent with `tlb_reset_dirty` being the largest single symbol on
the critical-path thread, though the two have not been causally linked: the
profile could not recover userspace callers, and a frame-pointer build did not
fix it because `add_compile_options` only affects targets declared after it and
the core library is declared earlier in that file. So treat this as two
measurements pointing the same way, not one proven chain.

**The remedy QEMU already provides** is the snapshot pair,
`memory_region_snapshot_and_clear_dirty` and
`memory_region_snapshot_get_dirty`, which exist so a caller can pay the clear
once over a whole region and then answer many per-range questions from the
snapshot for nothing. The display and migration paths use it for this exact
reason. Batching the poll through it would take the clears from ~1,480 a frame
to one per poll boundary.

The open design question, and the reason this is not a one-line change: where
the snapshot boundary sits. Per frame is cheapest and would reintroduce the
mid-frame-rewrite bug the poll was added to fix. Per draw preserves
correctness and still cuts the clears by the number of ranges queried, four to
eight. That needs measuring rather than choosing.

What the measurement points at instead is the guest side, and one lead is
already visible from the texture work: `memory_region_set_log(d->vram, true,
DIRTY_MEMORY_NV2A_TEX)` puts every guest write to video memory through
dirty-bitmap logging, and that cost lands on the guest thread, not the
renderer. Per-texture invalidation would then be worth more than its renderer
share suggests, because the same tracking is charged twice. That is a
hypothesis and has not been measured.

### The original ranking, with the caveat that produced the above

**The guest CPU thread is at 85% and the renderer thread at 48%.** Before
moving renderer work anywhere, establish which one actually bounds the frame,
because parallelising the second-busiest thread buys nothing. The renderer
already idles 15 ms per frame, 6.4 ms of it starved mid-frame waiting for the
guest. That points at the guest side, and one cheap hypothesis has already been
tested and rejected: raising the TCG translation block cache from 128 to 512 MB
changed nothing.

1. **Establish the critical path.** Per-frame, measure how long the puller
   blocks on the guest versus the guest blocking on the puller. Both numbers
   exist in pieces; neither is reported as a ratio. Everything below is
   conditional on this.
2. **Texture binding, 7.2 ms a frame.** The largest single item, roughly 32
   microseconds per pipeline bind, with no texture uploads happening at all,
   so it is validation and lookup. It is already gated on
   `texture_state_gen` and `texture_vram_gen`; the gate opens too often
   because `texture_vram_gen` is global, so a write anywhere in texture VRAM
   invalidates all four units. Making it per-texture is a contained change and
   needs no threading.
3. **Finish the draw pipeline that is already designed.** Feed
   `RenderCommandSnapshot` to a real `RCMD_DRAW` handler so translation
   overlaps decode. This is the structural fix and the largest change; do it
   after 1 says it is worth it.
4. **Fix the unlock-mode entry condition**, which cannot currently be reached
   by the titles it targets. Cheap, and independent of everything else.

None of this is upscaling work. 2x costs about two frames a second today
because the GPU is idle, so anything that buys frame time at 1x buys it at 2x.
