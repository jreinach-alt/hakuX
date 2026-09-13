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
| simple VBLANK, no deferral | 17-29, cruise 33.2-33.9 ms | 0.0 ms* | 0 |

**\* CORRECTED 2026-09-12, see
[`guest-visible-vblank.md`](guest-visible-vblank.md) and #65.** That 0.0 ms is
not a clean VBLANK. The jitter figure is an exponential mean kept from
`s_last_vblank_fire_ns`, which the simple-VBLANK path never writes -- it
returns before the block that updates it -- so the cell reads its initial
value. And the row is measuring one of the two VBLANK sources live in that
mode: `simple_vblank` also fires from `nv2a_vga_gfx_update` on every host
display refresh, 90-120 Hz on these handhelds, and `pacing.vblank_fired` does
not count those either. So `simple_vblank` is not "equal or better on every
measure"; two of the measures could not see it.

**Both causes are fixed as of 2026-09-13** ("nv2a: one VBLANK source in simple
mode, and a jitter figure that is written"): the host-refresh assertion is gone,
so the mode has one source, and the jitter EWMA is updated from both paths, so
`J` means the same thing in either. This row therefore cannot be reproduced on
a current binary and must be re-measured rather than compared against -- and
re-measuring it needs a way to set the `simple_vblank` pref from a soak, which
`docs/testing/request.sh` does not have.

The conclusion about deferral below survives, and is now a number rather than
an impression: on Galleon the deferral machinery took the guest's VBLANK clock
5.6% slow, losing 3.83 s per minute of play. The cause was one token and the
fix recovered it to 0.136 s/min at no cost in frame rate.

Deferral is distorting the guest's timebase by several milliseconds per
refresh and buying nothing here. That is one title; the setting exists because
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
| s3tc workers | DXT decode | on demand — **but see the note below: this row is misleading** |
| QEMU main loop, AIO, SDL | housekeeping | 6-11% each |

So the emulator is already threaded in more places than the NV2A had engines.
The gap is specific: **method decode and Vulkan draw translation share one
thread, and that thread does the expensive half of the frame.**

**Correction 2026-09-13 on the s3tc row.** "s3tc workers, on demand" reads as a
background pool, and it is not one. `s3tc_decompress_2d` and `_3d` are
fork-join *on the calling thread*: they `pthread_create` up to three helpers,
run the last chunk on the caller, and `pthread_join` before returning. Below
`S3TC_MIN_BLOCKS_FOR_MT` (128 blocks, so anything up to about 64x64) they are
fully single-threaded on the caller. The caller is `upload_texture_image` <-
`create_texture` <- `pgraph_vk_bind_textures`, which is on
**`nv2a.pfifo_thread`** — the 48% row above, the one that does all the Vulkan
translation. So DXT decode is *on* the renderer critical path and blocks it,
not off it.

This matters for #6, whose ordered dither was landed for accuracy with its
throughput cost deferred to the performance stream on the understanding that it
ran on worker threads. It does not. Priced in
[`performance-next-three.md`](performance-next-three.md).

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

### What the guest thread is really doing: retranslating

A frame-pointer build (debug only, see `CMakeLists.txt`) made the call graph
recoverable, and it refutes the dirty-tracking theory this document carried
before. Two chains account for most of the thread, and neither is the texture
poll.

**Chain one, guest stores invalidating code.** Inclusive shares on the TCG
vCPU thread, which the profile now names outright as `mttcg_cpu_thread_fn`:

```
do_st4_mmu                     14.7%   a guest 4-byte store
  mmu_lookup                   21.2%   taking the slow path
    mmu_watch_or_dirty         15.2%
      notdirty_write           13.8%   the page holds translated code
        tb_invalidate_phys_range_fast  11.7%
```

**Chain two, the retranslation that follows, re-arming the detection:**

```
cpu_exec_loop                  24.6%
  tb_gen_code                  19.1%   generating code again
    tb_link_page               11.6%
      physical_memory_test_and_clear_dirty  11.3%
        tlb_reset_dirty_range_all          11.1%
          tlb_reset_dirty                  10.6% self
```

So the largest single symbol on the critical-path thread is reached from
**code generation**, at 99.7% attribution, and not from any NV2A dirty
tracking. The guest writes 32-bit values into pages QEMU believes contain
translated code; each store invalidates, the invalidation forces
regeneration, and regeneration re-arms code-write detection by clearing dirty
bits, which walks every CPU's TLB. A self-sustaining loop.

That also explains why raising the translation block cache from 128 MB to
512 MB changed nothing: this is not a capacity miss, it is invalidation. And
it fits the ~53% translation-block hit rate seen earlier.

### It is one page

The loop needs the guest to keep writing a page that keeps having code
generated on it. Counting those writes by page frame, over 120-frame windows
in Fuzion Frenzy:

| page frame | hits | behaviour |
|---|---|---|
| **0x42b4** | 924,000 cumulative, **+5,300 per 120 frames** | growing constantly |
| 0x43c8 | 35,900, +250 per window | growing slowly |
| 0x403a | 20,625 | static |
| 0x4403, 0x4402 | 5,180 each | static |
| 0x512e | 4,677 | static |
| 0x404c | 170 | static |

About 7,000 slow stores per 120 frames, roughly 58 a frame, and **one page is
about 71% of them** at some 44 hits a frame. Not spread across memory. One
page.

Two things follow that make this tractable rather than hopeless.

**~~The invalidation is already range-precise.~~ CORRECTED 2026-09-13 — it is
not, and this was the load-bearing claim.** `tb_invalidate_phys_range_fast`
does pass the exact written range down, and
`tb_invalidate_phys_page_range__locked` then ignores it. The range test is
wrapped in `#ifndef XBOX`, and `PAGE_FOR_EACH_TB` in the softmmu half of
`tb-maint.c` is just `TB_FOR_EACH_TAGGED` over `p->first_tb` — it never looks
at its `start`/`last` arguments. So that `if` was the only thing making the
invalidation range-precise, and without it **a guest store to a page holding
translated code discards every block on that page**, whatever was written.

It came from xemu commit `703566ce33`, "tcg: Invalidate all TBs on target
page" (Matt Borgerson, 2021-10-04), which carries no rationale in its message
and left no comment in the code. It predates this fork by four years and has
ridden through every QEMU merge since, which is why it reads as upstream
behaviour on a casual look — `git log -S` finds only merge commits, and the
originating commit is reachable only by following the `#ifndef` back through
`translate-all.c` before the file split.

Two things this changes downstream, and the second is the reason it matters:

- The paragraph below still stands. Code really is being regenerated on that
  page; nothing here weakens that.
- **It removes the mechanism the block-extent lever runs on.** Smaller blocks
  save work by letting a store *miss* a block. Under whole-page invalidation no
  store can miss one, so halving the extent halves nothing and pays more of the
  per-block generation cost — which is the larger half here: `tb_gen_code` is
  19.1% inclusive and `tb_link_page` alone is 11.6% of it. See section 2 of
  [`performance-next-three.md`](performance-next-three.md), which was scoped on
  the retracted claim.

The counters that size the difference are on the always-on `hakuX-pages` line
as of `5f98d1ee5a`, read by `docs/testing/perf/tcg_pages.py`, with the legs
pre-registered in `docs/testing/predictions/tcg-whole-page-invalidation.json`.
The prize is not the discarded code. `tb_page_add` arms code-write detection
only on a page's empty-to-non-empty transition and the invalidator disarms on
empty, so a store that empties a page buys a full arming TLB walk on the next
generation there — `tlb_reset_dirty`, the 10.6% self figure above — and a store
that leaves one block behind buys none.

**Which means code really is being regenerated on that page.** `notdirty_write`
removes the callback once the page is dirty, so for it to fire 44 times a
frame something must keep re-arming it, and the only thing that does is
`tb_link_page` after generating code there. So page 0x42b4 holds executed code
with hot data beside it, at a granularity where the writes overlap blocks.
That is an inference from the mechanism rather than a direct observation; the
direct version is to dump what the guest has mapped there.

That also rules out the guess worth ruling out: this is **not** the NV2A
pushbuffer. No code executes from the pushbuffer, so `page_find` would return
nothing, the helper would do nothing, and the callback would stay off after
the first write instead of re-arming.

### Where that page is, and why the obvious fix will not work

Logging the guest virtual address and the span of offsets written within each
page turns the inference above into an observation, and removes an idea.

| page frame | hits | guest address | offsets written |
|---|---|---|---|
| **0x42b4** | 888,000, +5,500 per 120 frames | **0x205f22** | **0x150 – 0xf3c** |
| 0x43c8 | 111,500, +1,000 | 0x3190ac | 0x78 – 0x1000 |
| 0x512e | 14,580, +350 | 0x8112ef00 | 0xec0 – 0xf0c |
| 0x403a | 20,434, static | 0x8003ad39 | 0x898 – 0xd3a |
| 0x4402, 0x4403 | 5,180 each, static | 0xd0089ffc, 0xd008affc | whole page |
| 0x404c | 165, static | 0x8004ce24 | 0xe24 – 0xe28 |

**The two growing pages are in the game's own image.** Guest addresses
0x205f22 and 0x3190ac sit about 2 MB and 3 MB into the address space, which is
where an XBE's sections live, not in the 0x80000000 kernel range or the
0xD0000000 aperture that the static entries occupy. So this is the title's own
code and data, which is consistent with the mechanism and confirms it is not
anything the renderer is doing.

**And the writes cover nearly the whole page**, 0x150 to 0xf3c on the hot one
and 0x78 to the end on the second. That kills the attractive fix. If the
written data sat in one corner of the page with the code in another, moving or
padding it would separate them. It does not; data and code are interleaved
across the page, so there is no boundary to move.

What remains is that **arming is per-page while invalidation is per-range**.
The callback is re-armed across a whole page whenever any code is generated on
it, then the next store anywhere in that page pays the entry cost even when no
translated block overlaps the bytes written. Finer-grained arming is the
lever, and that is core work on code-write detection with real correctness
risk, so it is flagged here and not started.

### It is real regeneration, which means it is largely not ours to fix

The counter that separates the two cases, per 120-frame window in Fuzion
Frenzy:

| | per 120 frames | per frame |
|---|---|---|
| slow stores | ~8,000 | 66 |
| reached the invalidator | ~6,300 | 53 |
| ~~translated blocks discarded~~ **VISITS, see below** | ~~~9,500~~ | ~~79~~ |
| ~~translated blocks generated~~ **CALLS, see below** | ~~~3,440~~ | ~~29~~ |

> **CORRECTED 2026-09-13. The bottom two rows do not measure what they say,
> and the correction goes the same way for both.**
>
> A Crimson Skies run on 2026-09-13 reported mean guest instructions per
> "generated block" of **0.38**. A block cannot hold less than one
> instruction, so that row was void rather than small — and per the
> instrument note in `AGENTS.md`, the impossible row was the finding.
>
> - **`hakux_tb_generated` counts calls to `tb_gen_code`, not generations.**
>   It is incremented at the top of the function, and a call that finds a
>   recycleable TB in `inv_htable` takes `goto recycle_tb` and never reaches
>   code generation. The measured recycle rate is roughly five to one, so
>   "3,440 generated" is a call count and the real generation rate is several
>   times lower.
> - **`hakux_tb_invalidated` counts TBs *visited* by the invalidation loop,
>   not discarded.** It is incremented before `tb_phys_invalidate__locked`,
>   which early-returns when `qht_remove` fails — before `tb_remove`. So a TB
>   that already carries `CF_INVALID` is counted, left on the page list, and
>   counted again on the next store to that page.
>
> The same run shows why that second one is not a rounding matter: about **one
> visit per invalidation event**, with the page emptying in only **6% of
> events**. Both cannot be true of live blocks, since a page holding one block
> that is really removed empties. The consistent reading is that the page
> lists carry dead TBs the early return refuses to unlink and every later
> store walks over them again.
>
> `hakux_tb_codegen` and `hakux_tb_discarded` now count the real events, and
> the sp/ov overlap split is restricted to blocks without `CF_INVALID`. The
> re-measurement is registered as
> `docs/testing/predictions/tcg-whole-page-invalidation-2.json`.

So the paragraph that followed — "most calls find real overlap and throw real
work away", and the 2.8:1 waste ratio built on it — **is not supported by these
two rows.** The ratio was visits over calls. Whether real discards exceed real
generations, and by how much, is what the re-measurement is for.

What does survive, and is worth more than the retracted ratio: **each
page-emptying event costs exactly one arming TLB walk.** Measured
`pr_per_em` = 1.000 / 1.000 / 1.000 across three Crimson Skies runs, within-run
0.987–1.018. The rate is 897 / 909 / 1,844 emptying events per 120 frames, so
7.5 to 15 arming walks a frame — and `tlb_reset_dirty` is the 10.6% self
figure at the top of this document. That is a mechanism with a measured
constant rather than an inferred ratio.

**And a noise floor, which this stream did not have.** Three runs of one ref:
`ev`, `sp` and `ov` reproduce within ±5%, but `em` and `pr` came in at
897 / 909 / 1,844 — **a factor of two.** Any claim about the arming-walk rate
has to beat 2x on an unattended soak.

The original strategic conclusion may still be right — the stores may genuinely
overlap translated code and discarding may be correct and unavoidable. It is no
longer *established* by the numbers above, which is a different thing, and the
distinction is the reason this document is being corrected rather than
extended.

The levers that remain are all about making the churn cheaper rather than
rarer: faster code generation, or smaller blocks on pages known to thrash so
less work is lost per store. QEMU already has machinery in this area, since it
falls back to a single-instruction block when a store modifies the currently
executing one. Both are core tuning with modest expected return.

**A correction on how to rank what is left.** An earlier draft of this
section ranked the renderer above the translation work on the grounds that the
renderer "is our code" and TCG is not. That reasoning is wrong: this is a fork
that takes no downstream updates, so every file in it is equally ours and
rebase cost is not a real constraint. The same mistake was behind calling the
diagnostic counters in the TCG files a maintenance burden; there is no rebase
for them to burden.

The line that does exist is **blast radius and testability**, which is not
about ownership. A change to code-write detection touches every guest
instruction in every title, and a subtle fault there is catastrophic and hard
to attribute to its cause. A change to texture binding touches textures, and
the golden suites will tell you within minutes whether it broke. That argues
for different verification, not for leaving the larger item alone.

With ownership out of the way, the translation work is back in scope and
plausibly worth more than the renderer:

| lever | evidence | expected size |
|---|---|---|
| ~~smaller blocks on thrashing pages~~ **withdrawn, see the correction above and `performance-next-three.md` section 2** | ~~9,500 discarded for 3,440 generated, a 2.8:1 waste ratio~~ — visits over calls, not discards over generations | ~~`tb_gen_code` is 19% of the thread; halving regeneration is ~4 ms~~ — and the mechanism needs a range test this fork does not have |
| audio voice lock off the guest thread | 5% of the critical-path thread | ~2 ms, and it is a lock held across threads rather than real work |
| renderer draw path | freeing it entirely bounds the frame at 41.5 ms | up to 8.7 ms, the part the guest spends blocked on it |

The block-size lever is the interesting one precisely because the discard
ratio is so lopsided. (**That reasoning is retracted**: the ratio was visits
over calls. See the correction above.) Discarding is correct, but discarding 79 blocks to
rebuild 29 says the block granularity is poorly matched to this title's write
pattern, and that granularity is a choice rather than a requirement.

Note on the addresses: the guest virtual address is the reliable half. The
page frame is a `ram_addr_t`, an offset across all memory blocks rather than a
console physical address, so it should not be read as a location in the
console's 64 MB.

**Correction recorded deliberately.** This document previously named the
per-draw texture dirty poll as the lead, on the strength of that poll issuing
about 1,480 dirty-bitmap test-and-clear calls per guest frame. That count is
real and still worth reducing, but it is on the renderer thread and is **not**
what costs the guest thread its 10.6%. The two were consistent and
independent, which is exactly how a plausible wrong answer looks. The call
graph is what separated them.

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
