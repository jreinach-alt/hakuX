# lane.gpl569 (#569 P5: Vulkan graphics pipeline libraries)

Issue #569, PR #594. Branched from master at 1922ce1cad.

## Step 0: does the fleet's Turnip support it? Yes (posted on #569)

- **The fleet driver.** Every handheld loads `vulkan.purple.so`, which reports
  `PurpleVK-public Adreno (TM) 740 (git-62ac221a33)`. That is T30, a fork of
  Mesa 26.3.0-devel.
- **The T30 binary** (`~/hakux-work/drv/T30/vulkan.purple.so`, unstripped)
  contains `tu_pipeline_builder_parse_libraries`, Turnip's library-link path.
- **Upstream Turnip at `4c18636110f0`**, the tree `tools/turnip/build.sh`
  pins, sets all four in `tu_device.cc` unconditionally:
  `EXT_graphics_pipeline_library`, `graphicsPipelineLibrary`,
  `graphicsPipelineLibraryFastLinking` and
  `graphicsPipelineLibraryIndependentInterpolationDecoration`.
- **hakuX's own extension dump could not answer this,** because it lists only
  the extensions hakuX enables. `instance.c` now logs
  `[gpl569] ext= lib= fast= interp= requested= mode=` (tag `hakuX-build`) on
  every start, whatever the switch says.

## The change (6aaa1142ad; default on in a84fda7ed4, off again in 442167bcb7)

- **Switch:** `HAKUX_GPL` in the environment, or `HAKUX_GPL_DEFAULT` at build
  time.
  - 0 is the monolithic path, unchanged.
  - 1 fast-links from libraries.
  - 2 does the same, then links the same libraries again with LTO on the
    compile worker and swaps that pipeline in.
  - The extension and feature are requested only when the mode is non-zero.
- **Four libraries,** each cached in a `GHashTable` keyed by the bytes of a
  zeroed struct (`vk/compile_worker.c`):

  | Library | Key |
  |---|---|
  | VI | bindings, attributes, topology |
  | PR | vs id, gs id, rasterizer fields, attachment formats |
  | FS | fs id, depth/stencil state (whole struct from `flags` on), formats |
  | FO | blend attachment, formats; blend constants only when they are not dynamic |

  Every key also carries the dynamic-state list.
- **Module id** is a hash of the module's SPIR-V plus its length
  (`ShaderModuleInfo::gpl_id`), not the `VkShaderModule` handle, which can be
  reused after a module is freed.
- **Render pass for the libraries:** one per (color format, zeta format),
  obtained through `get_render_pass()` with the load ops zeroed. Every hakuX
  render pass with the same formats is identically defined, because
  `create_render_pass()` reads only the formats.
- **One fixed pipeline layout** (`pgraph_vk_gpl_layout`) carries the full
  16-attribute vertex push range. `push_template_index()` returns 16 for a
  binding under it, so descriptors are pushed with the template built from an
  identically defined layout.
  - **No `INDEPENDENT_SETS`.** Every library gets the same whole layout, which
    is the case the flag exists to relax. This departs from the plan's R6
    wording, deliberately.
- **Fallback:** a failed library or link falls back to a monolithic create
  under the same layout, and is counted as `fb=`.
- **LTO swap (mode 2):** the fast-linked pipeline is kept alive in
  `gpl_retired_pipeline` until the entry is evicted, since a command buffer
  in flight may use it. `pre_evict` refuses an entry whose LTO job is pending,
  and `finalize_pipeline_cache` waits for LTO jobs first.
- **Async compile on:** the worker builds the libraries and the link (the same
  `PipelineCreateParams`, with `gpl` set).
- **The fragment slot, for lane.uberspike569:** FS is its own library, so a
  prebuilt fragment ubershader library can be linked against any PR library.
  To do that, create it with `r->gpl.layout` and the per-format-pair render
  pass, and insert it in `r->gpl.libs[GPL_FS]` under its own key.
- **Instrument:** `[gpl569] mode= links= link_ms= link_fail= fb= new=vi/pr/fs/fo
  hit= fail= lib_ms= libs= flush= lto=done/fail/swapped lto_ms= heap_mb=`
  (tag `hakuX-perf`), with running totals.
  - It prints on every link that created a library, and on every 32nd link.
  - Library and link creates go through
    `pgraph_vk_create_graphics_pipeline_fb()`, so `[shd413]` dpc_ms is still
    the render thread's whole create time.
  - LTO creates bypass that wrapper, because they are not a stall.

## Checks done without a device

- All four changed files type-check with the NDK clang line from
  `compile_commands.json` (`-Wall`). They add no new warnings.
- `check_android_guards.py`: ok.
- **Desktop build: not run.** This host has no desktop build tree (AGENTS.md,
  "Building").

## Legs (registered before any run)

- **`gpl569-pixels-inert.json`** (arms job, 2 runs per arm): the full 27-suite
  sweep, A 6aaa1142ad against B a84fda7ed4, every capture inside its measured
  band. B's logcat must show mode=1 and links > 0.
- **`gpl569-doa-soak.json`**, hand-queued: cold DOA perflog soaks on the
  Nova, in the order A, B, then B2 (b_ref with `HAKUX_GPL=2`). The judge is
  `gpljudge.py`.

  | Leg | Registered |
  |---|---|
  | S1 | create ms per miss, B/A <= 0.70 (flagged if below 0.23, GPL's bound) |
  | S2 | first load after play, B/A <= 0.70 |
  | S3 | PR library hit share >= 0.50 |
  | D1 | GPU Tot ms B/A <= 1.10 and gfps >= 0.90 |
  | D2 | B2 GPU ms / A <= 1.03, with swaps > 0 |
  | MEM | a reading: library counts and device-local heap |

- **`gpl569-blinx-soak.json`**: the same three arms on Blinx, for D1 and D2.

## Runs

- **Queued 2026-09-28 17:37 PDT**, all on the Nova, which is on hostops' charge
  hold until about 18:00-19:00 PDT. All three are `--perflog`, survey route,
  440 s, `HAKUX_RELEASE_PRIO=1`:
  - `1-1790642263-gpl569-834655`: DOA A (6aaa1142ad, off), cold.
  - `1-1790642270-gpl569-837983`: DOA B (a84fda7ed4, mode 1), cold.
  - `1-1790642271-gpl569-838619`: DOA B2 (a84fda7ed4, `--env HAKUX_GPL=2`),
    warm.
  - These are the pilot, about 26.5 min of device time. They must be reviewed,
    and `pilots/gpl569.ok` written, before the Blinx trio goes in.
  - A plain-priority duplicate of A (`1790642249-gpl569-828024`) was queued
    first by mistake and removed from the queue unclaimed. To get release
    priority on an issue without the 0.5 label, pass `HAKUX_RELEASE_PRIO=1`.
- **Pixel arm:** `gpl569-pixels-inert.json`, pushed at 6dd14f86f6; the arms
  job queues it.
- **Preflight** (`--allow-tracker`): passed at 6dd14f86f6.

### Results (read 2026-09-29, session 3)

- **Pixel arm: PASS.** `[job.arms]` verdict on #594, 10:16 PDT. All 1059
  registered checks hold: 1052 same, 7 noise inside the measured band, exact
  598 -> 598. Surface_pitch/Swizzle differs byte for byte, inside its band.
  A fast link of specialised libraries does not move a capture.
- **The DOA soaks ran on the Thor, not the Nova**, 05:10-05:40 PDT. The
  device came from the queue, not from this lane. Every arm started cool, at
  82-81% battery. `gpljudge.py` output is in `doa-judge.json`, next to this
  file.
- **The Thor's thermal pause (`thermal-pause-F8`) was on within 30 s of
  `mark play` in all three arms** (A 30 s before, B 10 s after, B2 at the
  mark). Each arm also has 1-13 play samples. **D1 and D2 are void**, so they
  are not a result either way.
- **The stall legs fail by far more than any thermal difference.** B's pause
  came 30 s later than A's.

  | Leg | A (off) | B (mode 1, cold) | B2 (mode 2, warm) | Registered | Verdict |
  |---|---|---|---|---|---|
  | S1 create ms per miss | 570 (51.3 s / 90) | 667 (162.8 s / 244) | 195 | B/A <= 0.70 | **FAIL, 1.17** |
  | S2 first load after play | 8.7 s, 3 misses | 144.9 s, 154 creates | 10.6 s | B/A <= 0.70 | **FAIL, 16.6** |
  | S3 PR library hit share | | 0.56 (147 hit, 114 new) | 0.67 | >= 0.50 | pass |
  | D1 GPU ms, gfps | 61.4 ms, 5 | 104 ms, 1 (n=1) | | <= 1.10, >= 0.90 | void (thermal) |
  | D2 LTO GPU ms / A | | | 60.8 (n=1), 228 swaps | <= 1.03 | void (thermal) |

- **Where B's time goes**, from the `[gpl569]` counters:

  | Per create | B (cold) | B2 (warm, LTO running) |
  |---|---|---|
  | VI library | 0.02 ms | 0.02 ms |
  | **PR library (VS + GS)** | **1607 ms** (183.2 s / 114) | **922 ms** (157.6 s / 171) |
  | FS library | 12.4 ms | 5.3 ms |
  | FO library | 0 | 0 |
  | fast link | **0.06 ms** (15.5 ms / 261) | 0.05 ms |
  | LTO link (worker) | | 571 ms (194.6 s / 341) |

- **What this says:**
  - **The fast link is free, and the FS library nearly so.** GPL's mechanism
    works on T30.
  - **A pre-raster library costs about 2.8x a whole monolithic pipeline**
    (1607 against 570 ms). The vertex stage was already 78% of stage time
    (P1, C3). So a new VS costs more under GPL than without it, and at the
    fight load most misses bring a new PR key.
  - An LTO link costs what a monolithic create does (571 against 570 ms), as
    expected: it compiles again from the retained NIR.
  - The B2 warm cache did not make PR libraries cheap (922 ms each). Either
    T30's pipeline cache does not serve libraries, or the LTO jobs on the
    worker competed for the CPU. This run cannot separate the two.
  - **S1's unit differs between the arms.** A's `pm` counts pipelines, while
    B's counts library and link creates through the same wrapper. The summed
    create time, 51 s against 163 s, is the comparison that counts, and it
    fails the same way.
  - **MEM:** `heap_mb` read 2586.8 in both B arms, which is the heap's size,
    not what the library cache uses. The cache held 190 libraries (B) and 251
    (B2) at the end. This instrument cannot size it in bytes.
- **Not run:** the Blinx trio. With the stall legs refuted and D1/D2 void on
  the Thor, it would price a default that is not shipping.
- **Consequence: the default is off again** (442167bcb7). The code lands as
  the opt-in switch `HAKUX_GPL=1|2` and as the base for uber libraries,
  whose first sight never builds a PR library on the draw path (D3, D4).

## Session 2 (2026-09-29, 03:15 PDT): why session 1 stopped, and the addendum

- **Session 1 did not fail; it ended waiting.** The code, legs and judge were
  pushed and the three DOA soaks were queued. Its last word on PR #594 was a
  `[lane.gpl569] waiting:` comment (00:38 UTC). The Nova then went on hostops'
  charge hold, the Thor on a title push, and the queue is about 30 requests
  deep. None of the runs has started, and none has been re-queued or re-pinned.
- **This session is design only. It changes no code under `hw/`.** The
  registered refs (6aaa1142ad, a84fda7ed4) are what the queued arms measure.
  Code that lands on this branch now would go unmeasured into the PR the legs
  approve. The uber hooks below land with the uber build and its own arm, on
  a stacked branch (`lane/gpl569-uber`) or in lane.uberspike569's build PR.

## Design: uber libraries as first-class GPL cache entries

This is the target that lane.uberspike569's NOTES section 8.3 sets: a first
sight fast-links libraries that already exist, and the specialised libraries
build behind it and swap in. Below is what the cache in
`vk/compile_worker.c` needs for that, measured against the code at a84fda7ed4.

### D1. An uber library is already a distinct entry; it needs no new table

- **The FS and PR keys are keyed by module id.** That id is
  `ShaderModuleInfo::gpl_id`, the SPIR-V hash.
- **An uber module's SPIR-V differs from every specialised module's.** So its
  library gets its own key in the same `r->gpl.libs[GPL_FS]` or
  `libs[GPL_PR]` table, with the same refcount, flush and heap accounting.
- **Missing: a way to name it without a draw.** The build needs two entry
  points beside `gpl_get_lib()`:
  - `gpl_find_lib(kind, key)`: a lookup that never creates, for the
    first-sight choice (D3);
  - `gpl_prebuild_lib(kind, key, info)`: queued as a new
    `COMPILE_JOB_GPL_LIB` on the worker. At boot it builds each uber library
    from the persisted family list, and after a first sight it builds the
    specialised library. A second worker thread is worth adding with it, so
    that a long pre-raster build does not queue behind LTO links.
- **Uber entries must be exempt from the whole-table flush** at
  `GPL_MAX_LIBS`, or a flush throws away the libraries that make a first
  sight free. Flag them `pinned` in `GplLib`, and have
  `gpl_flush_locked()` skip pinned entries. DOA needs about 3 PR and 11-34 FS
  uber entries, so pinning cannot grow the table unboundedly.

### D2. The key split: take dynamic state out of the keys

Today every key carries the dynamic-state list, and the stage's fields are
keyed **even when the draw sets them dynamically**:
- **PR** keys `cull_mode` and `front_face`, which are always dynamic
  (`draw.c:2747-2748`).
- **FS** keys the whole depth/stencil struct, whose test, write, compare and
  stencil-op fields are dynamic under EDS (`draw.c:2753-2757`).
- **FO** keys the blend attachment, whose enable, equation and write mask are
  dynamic under EDS3 (`draw.c:2760-2762`).

For specialised libraries this costs only hit rate: two draws that differ in
a dynamic field build two identical libraries. S3 will show how much.

**For uber libraries it decides whether build-ahead works at all.** An uber
FS library built at boot cannot know the depth state of the draw that will
first need it. If depth state is in its key, it is never hit. So:
- **Mask each dynamic field to zero** in both the key and the create info.
  The spec ignores a dynamic field's static value, so the library is the same
  object. Make `gpl_dynamic()` the one test that both use.
- **What is left in each key after masking:**

  | Library | Key after masking |
  |---|---|
  | VI | bindings, attributes, topology |
  | PR | vs id, gs id, polygon mode, depth clamp, discard, depth bias enable, line width, formats |
  | FS | fs id, formats, has_zeta, depth bounds and the static stencil masks (EDS off only) |
  | FO | formats, has_color; the blend attachment only when EDS3 is off |

- **FO and VI collapse to a few entries per title,** and cost 0 ms (uberspike
  8.2).
- **The formats** stay in every key. They are fixed per render target, and
  DOA uses few pairs. With `dynamicRendering` they could leave the keys too,
  but hakuX uses render passes today.

### D3. The fast-link path: choose per stage, specialised first

`pgraph_vk_gpl_create_pipeline()` today gets or creates all four libraries
on the calling thread, then links them. With uber entries it chooses per
stage, and never builds an expensive library on the draw path when an uber
one exists:

1. **VI, FO:** get or create, as today. They take 0 ms.
2. **PR:** `gpl_find_lib` on the specialised key. If it is found, use it.
   Otherwise, if the uber PR library for (vertex family, GS kind) exists, use
   that and queue the specialised build. Otherwise create the specialised
   library inline, as today; that is a first-session miss of a new family.
3. **FS:** the same, with the fragment family's uber library.
4. **Link fast.** Record on the `PipelineBinding` which of PR and FS are
   uber (`gpl_provisional`, 2 bits).

**The binding also records which FS and VS modules its pipeline carries.**
This is the part that is easy to miss. The uber FS reads the combiner
program from its uniform block (uberspike `uber_comb_loc`), and the uber VS
will read the vertex program from its own block. So the uniform data a draw
writes must use the layout of the module that the **bound pipeline** links,
not the layout of the specialised `ShaderBinding`.
- `pgraph_vk_update_shader_uniforms()` must take its `module_info` from the
  pipeline binding's current modules.
- The swap (D4) changes pipeline and modules together, at bind time, on the
  render thread. So a draw never pairs one module's pipeline with another's
  uniform layout.

**What the fixed layout already covers:** the uber blocks sit in the same
set and binding as the specialised ones, in UBOs whose size is not part of a
layout. Samplers are combined image samplers whatever their dimension. So
`pgraph_vk_gpl_layout` needs no change for the uber paths.

**The stage interface** across independent libraries matches by location.
The uber VS must write every output any family FS reads, which is allowed.
The interpolation decorations may differ between the two, because the device
reports `graphicsPipelineLibraryIndependentInterpolationDecoration` (uberspike
8.2 on the host; this lane's `[gpl569] interp=` line on the device).

### D4. The swap path: one ladder, not one special case

At a84fda7ed4 the only swap is mode 2's LTO:
- one `gpl_lto_pipeline` slot;
- one `gpl_retired_pipeline`, kept until eviction.

Uber libraries add a rung below it, so the swap becomes a ladder:

| Rung | Pipeline | Built by |
|---|---|---|
| 0 | fast link, uber PR and/or FS | the draw thread, ~0 ms |
| 1 | fast link, all specialised | the worker, once the libraries are built |
| 2 | LTO link, all specialised (mode 2) | the worker, after rung 1 |

**The generalisation:**
- `gpl_lto_pending` and `gpl_lto_pipeline` become `gpl_next_pending` and
  `gpl_next_pipeline`, plus the rung it carries.
- `create_pipeline()`'s check becomes "a better rung is ready: take it".
- `gpl_retired_pipeline` becomes a short array (at most 2), destroyed at
  eviction as today.
  - A better release point is once the binding's `last_use_cb` has
    completed. That frees the uber-linked pipeline within a frame or two, not
    at eviction. `last_use_cb` exists only under `NV2A_PERF_LOG` today, so
    this moves it out of that guard.
- `pre_evict`'s refusal and `finalize_pipeline_cache`'s wait cover any
  pending rung, not only LTO.
- **One job may skip a rung.** In mode 2, the worker that finishes the last
  specialised library can LTO-link directly and skip rung 1.

**What a rung-0 draw costs** is the uber stages' GPU time (uberspike 8.4,
item 3), paid only between the first sight and the swap. The instrument needs
`uber_links=`, `swaps=` and the time spent on rung 0 in the `[gpl569]` line,
so that a soak can price it.

### D5. How a swap stays exact: `NoContraction` on both paths

A rung swap changes the machine code under a draw that the goldens already
fixed. Two effects can move a pixel at the swap:
- **uber against specialised:** constants that the specialised shader folds,
  and the uber shader reads at run time. NIR then reassociates or contracts
  differently (uberspike 4.1: 1-2 ulp, one 8-bit LSB on a BIAS boundary);
- **fast link against LTO or monolithic:** a fast link does no cross-stage
  optimisation, so an LTO link may fold differently at the boundary between
  stages.

**The guarantee is the same for both:**
- Emit the combiner and vertex arithmetic `precise`, which is SPIR-V
  `NoContraction`, in `psh.c`/`vsh.c` **and** in `psh-uber.c`/`vsh-uber.c`.
- NIR then applies no inexact rewrite (reassociation, factoring, fma
  contraction) to either path. Two op-for-op identical expressions round
  identically, whatever the compiler knows about their inputs, and whatever
  link built the pipeline.

**Scope:**
- **It changes the default path's own output.** It needs its own pixel arm
  against the goldens and its own fps price. It lands with the uber build,
  not here.
- **This lane's pixel arm checks the other half:** that a fast link of
  specialised libraries is pixel-inert against the monolithic create.
  - If `gpl569-pixels-inert` passes, cross-stage folding does not move a
    capture.
  - If it fails only on arithmetic-heavy suites, that is the same mechanism,
    and `precise` is the remedy there too.
- **Exactness of the uber FS at rung 0 is already measured:** uberspike 6.1,
  305 of 305 combiner captures byte-identical on the device, forced.

### D6. The order of the build (the uber lane's section 8.4, mapped onto this cache)

1. **This PR's legs pass.** Then GPL is on by default, and the libraries are
   the unit that is cached.
2. **The key masking (D2).** A small change with its own S3-style reading:
   the hit share before and after, on the same DOA soak. Pixel-inert by
   construction, because the spec ignores the masked values.
3. **`gpl_find_lib`, `gpl_prebuild_lib`, pinning and the swap ladder (D1,
   D3, D4),** with the uber FS as the first rung-0 library. `psh-uber.c`
   exists; the family list comes from the persisted module keys.
4. **The uber pre-raster library,** once `vsh-uber.c` is exact enough
   (uberspike 8.4, item 3).
5. **`precise` on both paths (D5),** with its own pixel arm.

### D7. After the soaks: what the uber build must change here

- **`r->gpl.lock` is held across `vkCreateGraphicsPipelines`** in
  `gpl_get_lib()`. There is one compile worker, so today that serialises
  only the worker against the render thread. Once D3's prebuild runs on the
  worker, a render-thread lookup would wait out a 1-1.6 s PR build under
  that lock. Before the uber build lands, create outside the lock: look up
  under it, create unlocked, then insert-or-discard under it again.
- **A first sight must never build a PR library on the draw path.** The
  soaks priced that at 1.6 s. Rung 0 has to be a prebuilt uber PR library,
  as D4 already says. Without one, a miss should take the monolithic create
  (570 ms), not the library path.

## Session 3 (2026-09-29, ~10:30 PDT): why session 2 stopped, and the verdict

- **Session 2 did not fail either; it ended waiting**, on the three DOA soaks
  and the pixel arm (`[lane.gpl569] waiting:` on #594, 10:12 UTC). Both
  have now resolved: the soaks finished on the Thor at 05:40 PDT, and the
  arms job posted PASS at 10:16 PDT.
- This session read them (section "Results" above), turned the default off
  again (442167bcb7), merged master (814e092fc9, clean), and re-ran the NDK
  type-check on the four changed files (rc=0, no new warnings).
- **Next, in order of expected impact:**
  1. **lane.uberspike569's uber PR library, prebuilt (D6, items 3-4).** This
     is the only route to a stall-free first sight, since a specialised PR
     library costs more than the pipeline it replaces.
  2. **Why a PR library costs 2.8x, on the host Turnip harness** (drm-shim
     A740, offline). Compile one DOA VS+GS as a library and as part of a
     monolithic pipeline, and count the ir3 variants each builds. Likely
     causes are no cross-stage varying elimination, and variants the library
     compiles because it does not know the FS. The count tells whether a
     create flag, or a VS that writes fewer outputs, recovers it. That
     decides the background cost of the specialise-then-swap rung, and on a
     device that thermal-pauses, that cost matters.
  3. **D1/D2 on the Nova, or on a Thor that has not yet paused**, only when
     a default flip is proposed again.

- Do not read the Turnip `.so` string table for extension support. It is
  Mesa's whole generated registry. The symbol `tu_pipeline_builder_parse_libraries`
  and upstream `tu_device.cc` are the evidence; the `[gpl569]` init line is
  the proof.
- `git log -S` on `~/hakux-work/mesa-turnipfork` is a blobless clone, so it
  fetches from the network and runs for minutes. Grep the checked-out tree
  instead.
- **Do not turn on GPL by default on its own.** Refuted on DOA: 163 s of
  creates against 51 s, and a 145 s first load against 8.7 s.
- **Do not read fps or GPU ms from a Thor soak past `mark play`** without
  checking `thermal.jsonl` for `thermal-pause-F8`. All three arms here had
  paused by then.
- **Do not compare `[shd413] pm` across GPL modes.** Under GPL it counts
  library and link creates, not pipelines.
