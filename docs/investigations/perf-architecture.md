# Performance architecture for the Snapdragon 8 Gen 2 and Adreno 740

lane.perfarch, #68. Opened 2026-09-25 on `724a0dd868`. Devices: Retroid Pocket
Nova and Ayn Thor, both SD 8 Gen 2 (1x Cortex-X3, 2x A715, 2x A710, 3x A510;
Adreno 740 under Turnip).

This document asks where this emulator should spend the silicon, not only how
to make each piece of code faster. Every number is graded:

- **M** (measured): read off a capture or a run on these devices. The source
  is cited.
- **B** (bounded): arithmetic on measured numbers. It is a ceiling or a floor,
  not a value.
- **H** (hypothesis): stated with the measurement that would settle it.

The reference scenes are Crimson Skies' heavy frames and Galleon's soak. Both
are guest-bound: the guest CPU thread is busy 41.5 ms of a 50.2 ms Crimson
frame (`frame-pacing-and-parallelism.md`), and the renderer idles about 27 ms
of a 52 ms Galleon frame (`tcg-barriers-elided.md`).

## Ranked table

Gains are on game frame time in a guest-bound scene. A gain in the vCPU
thread's time reaches the frame roughly one for one until the renderer, busy
29.0 ms of the Crimson frame, becomes the critical path.

| # | lever | owner | expected gain | grade | evidence |
|---|---|---|---|---|---|
| 1 | Stop code-write invalidation and dirty re-arm churn | lane.tcgchurn (#309) | up to 26% of vCPU time is this mechanism | M share, B gain | section 2 |
| 2 | TB lookup: fewer jump-cache flushes, inline indirect-branch probe | lane.tcgchurn (flushes); codegen follow-up | up to 13.6% of vCPU time | M share, B gain | section 3 |
| 3 | **Pin the vCPU thread to the X3 prime core** (`HAKUX_PLACE_VCPU=prime`) | this lane, prototype 2 | registered at -18% (band -5% to -35%); **re-bounded at 3-9% of vCPU time** | B; arm refused on validity (runs cut short; Galleon frame-capped) | 09-11 Crimson: vCPU on the X3 15.2% (M, 4.1). 09-25 Galleon: **72-88%** (M, 8.1, 8.3). Pinning verified at 100%, runqueue wait +3 ms/s. Arm `perfarch-vcpu-prime.json` |
| 4 | Host build: native ELF TLS (minSdk 29), inline LSE atomics, no intra-library PLT | build owner (outside every lane's files) | up to 4.4% of vCPU time, 3.7% of PFIFO time | M share, B gain | section 3.3 |
| 5 | I-cache maintenance: patch-free TB chaining | this lane | about a third of 4.0% of vCPU time | M share, B gain; IDC=1 DIC=0 measured, 209 ns per 4-byte flush on the X3 | sections 2.2, 8.1 |
| 6 | Renderer: split capture from translation (`RCMD_DRAW`, submit worker) | renderer lane | Crimson frame bounded at 41.5 ms (+21% fps) today; more once 1-3 land | B | `frame-pacing-and-parallelism.md` section 4 |
| 7 | Run ahead with copy-on-write snapshots instead of holding the guest (#44 class) | future lane | removes the skew bound's cost: Galleon ceiling 13 -> 29 gfps with the fix on | H | section 6 |
| 8 | x86-TSO from RCpc (`HAKUX_TCG_TSO=rcpc`) | this lane, prototype 1 | a **cost**, predicted +4% (band +1% to +12%); micro-mix +0% on the X3, +28% on an A715 | M micro; **not runnable as built: LDAPR/STLR fault on misaligned guest accesses, and there is no guard. The arm stopped at boot, 2 of 2**; frame cost unmeasured | sections 1, 8.1, 8.2; arm `perfarch-tso-rcpc-cost.json` |
| 9 | Order GPU->CPU sync writes on the vCPU thread (`run_on_cpu`) | pgraph owner | about 0 fps; closes the one ordering gap that is real today | H | section 1.3 |

Items 1 to 4 compound: they act on different parts of the same thread.
Item 3 speeds up every instruction on the thread, and 1, 2 and 4 delete work
from it. Placement was ranked first until the survey re-measured its premise
(section 8.1).

## 1. Memory ordering

### 1.1 What is measured, and which defects it touches

The fork elides every guest barrier (`tcg_gen_mb`, `1d8a51aff9`). Putting them
back was priced on Galleon/Nova (M, `tcg-barriers-elided.md:276-280`):

| regime | barriers emitted | game frame ms | cost |
|---|---:|---:|---:|
| elided (shipped) | 0 | 52.50 | -- |
| store-side only (DMB ISH before every store) | 80,411 | 54.90 | +4.6% |
| full revert (also DMB ISHLD before every load) | 347,473 | 70.40 | +34.1% |

So the **load-side** barrier carries about 29 of the 34 points.

None of the race defects the brief names is a memory-model defect:

- **#44**: the full revert left it at 6 of 10 failures. Its mechanism is the
  guest running ahead of PGRAPH: the draw reads a texture after the guest has
  started writing its successor. Real silicon races the same way and wins on
  speed (`guest-pgraph-skew.md`).
- **#262**: vertex fetch not seeing earlier renders into the same memory. The
  coherence it lacks is between the emulator's own surface cache and guest
  RAM.
- **#184**: surface staleness, the same class as #262.

**No ordering design retires #44, #262 or #184.** Those are timing and
cache-coherence defects (section 6). What ordering buys is latent correctness,
the class upstream warns about in the branch the fork bypassed: I/O threads
reading guest RAM that a vCPU is writing.

### 1.2 CPU -> GPU is already ordered at the doorbell (source-verified)

The guest publishes a pushbuffer by storing `DMA_PUT`. That store traps to
`user_write` (`hw/xbox/nv2a/user.c:83`), which takes `d->pfifo.lock`, writes
the register and kicks. The PFIFO thread reads `DMA_PUT` under the same lock.
A mutex unlock is a release and a lock is an acquire. So every guest store
that precedes the doorbell in program order is visible to the PFIFO thread
before it reads the pushbuffer, the textures or the vertex data. That holds
whatever TCG emitted for those stores.

This is the "order only at hardware synchronisation points" design, and in
this direction it is already built. It costs nothing, and it is why restoring
every barrier changed nothing for #44. Anything the PFIFO thread reads that the
guest wrote **after** the doorbell is a timing race, not an ordering one.
Silicon has it too.

### 1.3 GPU -> CPU is not ordered, on either side

`NV097_BACK_END_WRITE_SEMAPHORE_RELEASE` (`pgraph.c:4791`) calls
`surface_update`, which downloads dirty surfaces into guest RAM. It then
stores the semaphore with a plain `stl_le_p`. Report writes (`pgraph.c:5127`)
are three plain stores. On AArch64:

- **Device side:** nothing orders the surface bytes before the semaphore
  word. That needs a release: `smp_wmb()` or `qatomic_store_release`.
- **Guest side:** the guest polls the semaphore with a plain load, then reads
  the surface with plain loads. Those loads may be satisfied out of order
  (LD_LD). A device-side release alone does not fix this.

No symptom is attributed to this gap (**H**, not measured). The window is
nanoseconds against a poll loop.

**Design A, x86-TSO from RCpc (prototype 1).** Every guest load becomes
LDAPR and every guest store becomes STLR. This is FEX-Emu's mapping, and
it is exactly TSO:

- **LDAPR** gives LD_LD and LD_ST.
- **STLR** gives LD_ST and ST_ST.
- **An STLR followed by an LDAPR may reorder.** That is ST_LD, which x86
  permits too.

Guarantees under `HAKUX_TCG_TSO=rcpc`:

| | kept | how |
|---|---|---|
| LD_LD, LD_ST, ST_ST for JIT'd guest accesses | yes | LDAPR / STLR |
| 128-bit guest accesses (SSE) | yes | DMB ISH before the store pair, DMB ISHLD after the load pair (no RCpc pair form before FEAT_LRCPC3) |
| accesses that take the softmmu slow path (MMIO, TLB miss, code pages) | yes | DMB ISH before the store helper, DMB ISHLD after the load helper |
| MFENCE | yes | still emitted: the only request carrying ST_LD |
| LFENCE, SFENCE | elided | already implied by LDAPR/STLR for write-back memory |
| **guest accesses made inside C helpers** (x87 loads and stores, FXSAVE/FXRSTOR, string helpers) | **dropped** | plain C loads and stores; fixing them is in `accel/tcg` |
| **ST_LD across a LOCK-prefixed RMW** | **dropped** | on x86 a locked op is a full barrier; here it is LDAPR + op + STLR. Only a Dekker-style store->load handshake with a concurrent agent can observe it, and the NV2A and APU threads do not take part in guest locks. |
| **misaligned guest accesses** | **fault** | x86 accesses need no alignment, and the fast path accepts any address that does not cross a page. LDR/STR accept that; LDAPR/STLR raise an Alignment fault (without FEAT_LSE2 on any misalignment; with it, on crossing 16 bytes, or on any misalignment if `SCTLR_EL1.nAA` is clear). The prototype has no alignment test and no fallback. FEX-Emu handles this with a SIGBUS handler that backpatches the access. |

**The prototype is not runnable as built** because of the last row. A
runnable version needs one of two fixes. It can test `addr & (size-1)` (or
`addr & 15` under LSE2) and fall back to LDR + DMB ISHLD, or DMB ISH + STR,
on misalignment. Or it can backpatch from a SIGBUS handler, as FEX does. The
guard's cost belongs in the model and in the prediction band before a
re-arm. Micro-costs come from the `HAKUX_HOSTBENCH` survey below.

**Design B, ordering at the device's own sync points.** Design A is
guest-wide. B changes only the three places a device writes a sync word:
semaphore release, report, and notifier. It makes those writes **on the vCPU
thread**, via `async_run_on_cpu`:

- The device thread still downloads the surface bytes.
- It then queues the sync-word store to run on the vCPU. The queue hand-off
  is a lock pair, so it is release/acquire.
- The vCPU performs the store between translation blocks. Every later guest
  load is after it in program order on the same thread, so no guest load
  ordering is needed.

Cost: one `cpu_exit` round trip per sync write. That is microseconds, times
the number of semaphore releases and reports per frame, a count nobody has
taken yet (the method histogram under `NV2A_PERF_LOG` would give it).
**Grade H.** It closes 1.3 completely and 1.2 is already closed. The guest
path pays nothing.

**Recommendation.** B is the correct-by-construction design for the
emulated-hardware traffic, at near-zero cost. A is the answer only if some
guest-visible behaviour needs TSO against the device threads **outside** the
sync points, and nothing measured today does. A's arm is still worth having:
it settles whether full TSO is affordable on this core, and the owner asked
exactly that.

## 2. The translation cache

lane.tcgchurn owns the invalidation and flush mechanics in `accel/tcg`. This
section only sizes them from the one capture on disk and answers the ISA
question.

### 2.1 Where the vCPU thread's time goes (M)

These are self-time samples of the vCPU thread in the 09-11 Crimson capture
(`/home/justin/hakux-work/perf/perf.data`, 15,608 samples at 1 kHz, tid 20682).
They are counted per sample by `docs/lanes/perfarch/profile_categories.py`,
because `simpleperf report` rounds each of the JIT's roughly 3,900 one-sample
rows up to 0.01% and reads 42% where the true share is 29%.

| mechanism | share |
|---|---:|
| JIT code (the guest's own instructions, translated) | 29.39% |
| code-write invalidation and dirty re-arm (`tlb_reset_dirty` 14.4, `tcg_flush_jmp_cache` 8.7, invalidate, notdirty) | 25.95% |
| TB lookup and chaining (`qht_lookup_custom` 5.1, `helper_lookup_tb_ptr` 3.7, `tb_lookup_cmp` 2.0, ...) | 13.64% |
| softmmu slow path (`mmu_lookup*`, `probe_access`, `tlb_set_page`, ...) | 9.07% |
| host runtime: emutls, PLT stubs, outline atomics, pthread TLS | 4.40% |
| I-cache maintenance (`flush_idcache_range`) | 4.02% |
| kernel | 3.33% |
| guest-op helpers (softfloat SSE scalar, x87, flags) | 1.85% |
| `cpu_exec` loop and misc | 1.67% |
| audio `voice_lock` | 1.41% |
| code generation itself | 1.02% |
| other | 4.26% |

**Less than a third of the critical-path thread executes guest code.** The
capture is dated. It predates every #68 fix, and lane.perfbase (#310) is
taking the current baseline. The shape, not the digits, is what this document
relies on.

On the **PFIFO** thread in the same capture, `tlb_reset_dirty` is 21.56%.
That is the texture dirty test-and-clear walking the vCPU's TLB from another
thread. The texture poll rate has since fallen from about 1,480 per frame
(09-11) to `Tq:2` in a 09-25 Crimson soak. Passed to lane.tcgchurn on #309.

### 2.2 `CTR_EL0.DIC/IDC`: can I-cache maintenance be skipped?

`util/cacheflush.c` already honours both bits:

- **IDC=1** skips the D-cache clean.
- **DIC=1** skips `IC IVAU`.

The `HAKUX_HOSTBENCH` survey read it on every core: **IDC=1, DIC=0** (M,
section 8.1). So what remains is `IC IVAU` per
64-byte line, then `DSB ISH` and `ISB`. The `IC IVAU` is broadcast to all
eight cores' instruction caches.

Callers on the vCPU thread, among the half of the call chains that unwind
(M):

- `tb_gen_code`: 20%
- `tb_add_jump` (inlined in `cpu_exec_loop`): 15%
- invalidation unlinking (`do_tb_phys_invalidate`,
  `tb_remove_from_jmp_list`): 15%

The last two are **4-byte branch patches** (`tb_target_set_jmp_target`,
`tcg/aarch64`). Each pays a full `DSB; IC; DSB; ISB` sequence.

**Design: patch-free chaining.** The aarch64 backend already has an indirect
form of `goto_tb`: `LDR TMP0, jmp_target_addr[n]; BR TMP0`. It uses it when
the target is out of branch range. Always using that form makes chaining and
unchaining a plain data store, with no I-cache maintenance at all. The cost is
one L1-resident load on each chained exit, feeding a predicted indirect
branch.

- **Prize:** the chaining share of 4.0%. About a third, so roughly 1.3% of
  the vCPU (**B**).
- **Settle it:** the survey's `flush_ns b4` (the cost of one 4-byte flush),
  times the rate of chain and unchain events.

If DIC=1, the whole 4.0% goes instead, and this design is moot.

## 3. Code generation on AArch64

### 3.1 The softmmu fast path

- **Loads** already have an XBOX fast path (`prepare_host_addr`): CBZ X26,
  TST, B.NE, MOV, B, then the load. RAM loads skip the TLB.
- **Stores** do not. They take the full TLB compare (about 9 instructions)
  because code-write detection and NV2A dirty logging live in the TLB's
  `notdirty` bits.

A store fast path needs a per-page "direct-store-clean" bitmap that the
invalidation code maintains. That is lane.tcgchurn's territory, and with 26%
of the thread in that machinery it should follow their fix, not precede it.
**Grade H.** Settle it with the count of stores that take the slow path after
tcgchurn lands (`hakuX-pages` already reports `slow stores`).

### 3.2 Indirect branches

x86 `RET` and indirect `JMP`/`CALL` go through `helper_lookup_tb_ptr`. It
probes the jump cache and falls back to `qht_lookup`. `qht_lookup_custom` at
5.1% says the jump cache misses often. That is consistent with
`tcg_flush_jmp_cache` at 8.7%: the cache is being emptied.

Two levers, in order:

1. **Stop the flushes** (tcgchurn).
2. **An inline return-address prediction in generated code.** `CALL` pushes
   the host address of its fall-through TB onto a small shadow stack in
   `CPUX86State`. `RET` compares and branches directly, falling back to the
   helper on a mismatch. This is what FEX and Rosetta do.

- **Prize:** part of 13.6% (**B**).
- **Settle it:** the count of `helper_lookup_tb_ptr` calls split by source
  opcode (`RET` against the rest).

This lives in `target/i386/tcg` (tcgchurn's), so it is a follow-up there.

### 3.3 The host build itself (M share)

4.40% of the vCPU thread and 3.73% of the PFIFO thread are spent in code the
compiler added:

- **Emulated TLS** (`__emutls_get_address` 0.88%, `pthread_getspecific`
  0.58%). The app builds at `minSdk = 26`, and native ELF TLS needs API 29.
  QEMU keeps `tcg_ctx` and `current_cpu` in TLS, so every access in
  translation and in helpers is a function call.
- **Outline atomics** (`__aarch64_swp4_acq_rel` 0.66%,
  `__aarch64_ldset8_acq_rel` 0.37%). There is no `-march`, so every atomic is
  a runtime-dispatched call. Every SD 8 Gen 2 core has LSE.
- **PLT stubs** (1.08%): calls between functions inside `libxemu.so` go
  through the PLT because symbols have default visibility.

The fix is three build flags:

- `minSdk 29`: the Nova runs Android 13 (`android_sdk_version: 33` in the
  capture's metadata). The Thor's version is not checked here.
- `-march=armv8.2-a` (LSE inline). An SD 865-class floor still has it.
- `-fvisibility=hidden` or `-Wl,-Bsymbolic` for `libxemu.so`.

Those files belong to no lane. Prize up to 4.4% of the vCPU (**B**).

### 3.4 Flags and helpers

Lazy flags stay inline: `helper_cc_compute_*` does not appear in the top
symbols. Softfloat helpers for SSE scalar arithmetic are 1.85% on this title
(`helper_mulss` 0.51%, `helper_addss` 0.32%). Low here, but it is
title-dependent: a physics-heavy title may differ. Settle it with the same
categorisation on a Fuzion Frenzy or Ghoulies capture.

## 4. big.LITTLE placement

### 4.1 Where the hot threads run (M, 09-11 capture)

| thread | samples | X3 (cpu7) | A715/A710 (cpu3-6) | A510 (cpu0-2) | core changes/s |
|---|---:|---:|---:|---:|---:|
| vCPU (tid 20682) | 15,608 | **15.2%** | 84.6% | 0.3% | 123 |
| PFIFO (tid 20692) | 11,129 | 1.9% | 98.1% | 0.0% | 109 |

The core-change column is a **lower bound** on migrations. Two changes inside
one 1 ms sample interval read as none.

**The fork's own affinity code is compiled out.** `XEMU_OPT_THREAD_AFFINITY`
defaults to 0 in both `xemu_android.cpp:1022` and `pfifo.c:32`, and the
Android CMake never defines it. Had it been on, its threshold (CPUs at 90% or
more of the highest `cpuinfo_max_freq`) would have selected only cpu7, since
2.8/3.19 = 0.88. It applies that mask to qemu-main, so every thread qemu-main
spawns would have inherited it and shared one core.

### 4.2 The design

| thread | where | why |
|---|---|---|
| vCPU | **cpu7 (X3) alone** | the critical path. Roughly 1.4x an A715's work per second (**H**: clock 1.14x times IPC; the survey measures per-core throughput) |
| PFIFO (method decode + Vulkan translation) | cpu3-4 (A715) | second-busiest at 48%, and it feeds the GPU |
| `pgraph.vk.render`, `pgraph.vk.compile` | cpu5-6 (A710) | light (render about 4%) but latency-sensitive at the flip |
| APU, audio voices, AIO, SDL, main loop | cpu0-2 (A510) | small, periodic, must not steal the X3 |

Prototype 2 implements the first row only (`HAKUX_PLACE_VCPU=prime`, pinned
on the vCPU's first translation), because that row is where the predicted
gain is. The rest belongs to the files that create those threads.

### 4.3 Sustained clocks and thermal

A handheld's sustained fps is decided by the prime core's clock after
minutes, not seconds. The `HAKUX_TOPO` sampler reports each policy's
`scaling_cur_freq` (mean, min, max) and its `scaling_max_freq` cap every 10 s,
plus the thermal zones and GPU clock where the app may read them. The survey
run found no throttling in 240 s (section 8.1). Both arms of prototype 2 are
queued. The
prototype's P3 leg compares the late half of each run with its early half. A
240 s soak does not reach thermal equilibrium, so a pass is necessary and a
20-minute soak is the follow-up.

## 5. Adreno 740 under Turnip

### 5.1 The GPU is not the bottleneck (M)

The GPU is 25% busy at 220 MHz (its floor; the ceiling is 680) for 6.2 ms of
work per 1x frame. At 2x it is 36% busy and 9.1 ms
(`crimson-skies-performance.md:57-61`, `:99-102`). The PFIFO thread is 48%
busy and the render thread about 4%. So the questions are about **CPU cost
per draw** and **CPU-GPU synchronisation**, not shader throughput.

### 5.2 What is measured on the CPU side

- **Texture bind:** 5.85 ms of Crimson frame time (29.8% of the PFIFO
  thread's busy time) against 0.01 ms of upload (`guest-pgraph-skew.md:1556`).
  So it is validation and hashing, not transfer.
  - On 09-11, `fast_hash` was **22.28%** of the PFIFO thread's self time and
    `memcpy` 12.14% (`profile_categories.py` on tid 20692).
  - Of the draw phase, the steps that read guest memory are 53% and the
    steps after those reads are 37.5% (`guest-pgraph-skew.md:1534`).
- **Frame finish:** 3.1-3.6 ms, of which a 2.0-2.4 ms fence wait
  (`crimson-skies-performance.md:84`, `performance-next-three.md:328`).
- **Surface downloads:** 0.17 per frame, about 1-2 ms each. That predates a
  later fix, and there is no run since.
- **Submits:** about 1 per frame, with command buffers of 65.6 draws on
  average on Galleon (`diagdump77/NOTES.md:144`). No mid-frame submit churn.

### 5.3 What is not measured, and what would settle it (all H)

- **Render passes per frame, and GMEM load/store.** Every render pass is
  hard-coded to LOAD and STORE both colour and depth (`vk/draw.c:1543-1564`).
  `get_optimal_zeta_load_op` is dead code that only splits the render-pass
  cache key. On a tiler each LOAD is a full-attachment GMEM fill and each
  STORE a resolve, per pass. With the GPU 75% idle, that costs GPU time we
  have spare, until a pass count per frame says otherwise. `draw.c:1035`
  already prints `RP:` and `RPBreaks:` under `NV2A_PERF_LOG`, so reading
  them off one perf-log soak settles the count.
- **Pipeline-creation stutter.** One 2.9 ms compile sample exists, and
  nothing else. What settles it: a per-frame count of pipeline-cache misses
  and the maximum frame time in the same window.
- **Turnip features that would help, in order of the CPU cost they
  remove:**
  1. **`VK_EXT_descriptor_buffer`, or wider use of push descriptors:** cuts
     descriptor set allocation and update on the PFIFO thread. Push
     descriptors are already used when present (`vk/instance.c:502`).
  2. **`VK_EXT_graphics_pipeline_library`** (Turnip implements it): compiles
     vertex input, fragment output and shaders separately, so a new state
     combination links in microseconds instead of compiling. Removes
     stutter, not steady-state cost.
  3. **`VK_KHR_dynamic_rendering` with `VK_EXT_attachment_feedback_loop`:**
     removes render-pass objects from the cache key. On Turnip it keeps the
     same GMEM decisions.
  4. **Correct load/store ops** (`DONT_CARE` when a clear covers the
     attachment; depth `STORE_OP_DONT_CARE` when no later pass reads it):
     GPU-side, and only worth it once the GPU is busy. It becomes relevant
     at 3x-4x, where the GPU reaches 56-66%.

## 6. Running ahead safely: speculate, then validate

### 6.1 The measured problem

The PFIFO thread reads textures and vertex data synchronously with the
method, while the guest runs free. On Crimson Skies, **60.8% of texture
uploads raced** a guest write in flight (`Tr` 61,965/101,879, 6 runs, both
devices). On Galleon, 5.5e-05 of vertex reads did
(`vram-race-frequency-is-per-title.md`).

The skew bound holds the guest at each submission until PGRAPH catches up.
That zeroes both race sites, but it costs Galleon more than half its
frame-rate ceiling: `gfps` p90 falls 29 -> 13. Crimson Skies pays almost
nothing (`guest-pgraph-skew.md`, 1083 and 1346). Making the hold selective
did not help Galleon.

### 6.2 The design: snapshot, don't hold

Silicon reads the texture before the guest overwrites it because silicon is
fast, not because anything orders the two. So the emulator should reproduce
**the outcome of a fast GPU**: every draw sees guest memory as it was at the
doorbell that published it. It does not need to reproduce the timing.

1. **At the doorbell.** The selective bound's pre-scan already walks
   `[DMA_GET, DMA_PUT)` at a measured 0.03% of frame time. Extend it from "is
   there a draw" to "which pages will the draws read": the texture and
   vertex-array offsets, and their format-derived extents, set in the
   segment.
2. **Arm copy-on-write** on those pages for the vCPU. This reuses the
   `notdirty` TLB trap that code-write detection already uses, under a new
   dirty client, so the vCPU's next store to an armed page takes the slow
   path.
3. **On a trapped store**, copy the page's current contents to a snapshot
   pool, keyed by page and doorbell epoch, then let the store proceed. The
   guest never blocks.
4. **When the PFIFO thread reads** for a draw published at epoch *e*, it
   reads the snapshot if one exists for that page at or after *e*, else
   guest RAM.
5. **Disarm and free** when PGRAPH passes the segment's end.

**Correctness argument.** A draw's inputs are then a function only of guest
memory at its own doorbell, which is the most any guest can rely on:

- A guest that fences (semaphore, `BlockUntilIdle`) sees no difference,
  because nothing is outstanding when it writes.
- A guest that does not fence gets the fast-GPU outcome, which is what it
  was tested against on silicon.
- **What this does not cover:** data read by a draw but not named by any
  method in the segment. For example, a vertex array whose offset was set in
  an earlier segment. The pre-scan must carry PGRAPH's bound state forward,
  not only the segment's words. Whether it can do that exactly is the hole
  (**H**).

**Cost (H).** Three parts, each with the measurement that settles it:

- **The arming.** With per-page arming the prize is a per-page TLB flush on
  the vCPU (`tlb_flush_page`, delivered by `async_run_on_cpu`), not a
  `tlb_reset_dirty_range_all` walk, which is the 10-14% item in section 2.
  Settle it with a count of armed pages per doorbell (the pre-scan can print
  it).
- **The copies.** 4 KB per trapped store, at most once per page per epoch.
  On Crimson that is at most the 60.8% of uploads that raced. At 1-2
  texture fills per frame (`guest-pgraph-skew.md:1556`) and 77-189 kicks
  per 2 s window (`fifoskew` in the 09-25 gamecheck soak at `e48514f980`),
  that is a handful of pages per frame.
- **The reads.** One hash lookup per texture or vertex read, and only while
  a snapshot exists.

#184's fix, where a write to a surface rebuilds every stage sampling it, is
this pattern at the scale of one surface. The frame-scale version is what
lets **#44's fix ship on by default**. On Galleon, that is the difference
between 13 and 29 gfps at the ceiling.

## 7. Host characterisation instruments (this lane)

All three are off by default and cost one `getenv` each at TCG init. They are
selected per run with `request.sh --env` and log on tag `hakuX-lane` as
`perfarch ...`.

| env | what | reader |
|---|---|---|
| `HAKUX_HOSTBENCH=1` | Per CPU: the MIDR and `CTR_EL0` (IDC, DIC) read by that core. Throughput of LDR, LDAPR, LDAR, STR, STLR, DMB ISH, DMB ISHLD+LDR and DMB ISH+STR. Mixes (plain / rcpc / full revert). Store-then-reload (plain / rcpc / rcsc / revert). Cache-missing loads (plain / LDAPR / DMB ISHLD). `flush_idcache_range` at 4 B, 64 B, 1 KB and 4 KB. HWCAPs. About 5 s at boot. | `tools/bench/hostbench_report.py` |
| `HAKUX_TOPO=<ms>[,<s>]` | A little-core sampler of `/proc/self/task/*/{stat,schedstat}`. Reports per-thread busy %, core residency, core changes/s and runqueue wait, plus per-policy clocks and caps, GPU clock and busy %, and thermal. | `hostbench_report.py`, `place_judge.py` |
| `HAKUX_TCG_TSO=rcpc` | Prototype 1 | `tools/bench/tso_judge.py` |
| `HAKUX_PLACE_VCPU=prime\|<hexmask>` | Prototype 2 | `tools/bench/place_judge.py` |

`tools/bench/selftest.py` checks both judges and the report against synthetic
logcats. `tools/bench/build_check.py` compiles the bench for arm64 Android
and the build host.

## 8. Results

### 8.1 Host survey (M, Nova, `1790369070-perfarch-2147739`)

Galleon, 240 s, `9181cb4c13` (apk `2d7521670420`), `HAKUX_HOSTBENCH=1
HAKUX_TOPO=100,10`. Read with `tools/bench/hostbench_report.py`. The bench
could not pin itself to cpu6, so that core has no ISA row. The sampler saw
threads run on it.

**Cores and `CTR_EL0`.** cpu0-2 are A510 (`0xd46`), cpu3-4 A715 (`0xd4d`),
cpu5 A710 (`0xd47`) and cpu7 X3 (`0xd4e`). Every readable core reports
**IDC=1, DIC=0**. So I-cache maintenance cannot be skipped: `IC IVAU` per line
plus `DSB; ISB` stays. The patch-free chaining design in 2.2 stands.
`flush_idcache_range` of 4 bytes costs **209 ns on the X3** (177 on an A715,
157-161 on an A510), and 4 KB costs 608 ns.

**Ordering instructions, ns per op (throughput):**

| core | LDR | LDAPR | STR | STLR | DMB ISH | mix plain | mix rcpc | mix revert |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| X3 (cpu7) | 0.122 | 0.107 | 0.473 | 0.315 | 2.27 | 0.921 | **0.902** | 7.23 |
| A715 (cpu3) | 0.182 | 0.182 | 0.357 | 1.077 | 5.02 | 0.989 | 1.271 | 15.67 |
| A710 (cpu5) | 0.359 | 0.358 | 0.359 | 0.359 | 2.52 | 0.945 | 1.076 | 7.98 |
| A510 (cpu0) | 0.274 | 2.637 | 0.526 | 2.652 | 0.57 | 1.126 | 5.677 | 8.56 |

- **On the X3, TSO from RCpc costs nothing in the micro-mix** (0.902 against
  0.921 ns per unit). The barrier revert costs 7.8x.
- **On an A715 it costs +28%, on an A710 +14%.** The A715's STLR is the
  expensive half (3x STR).
- **An A510 must never run the vCPU under rcpc:** its LDAPR is 10x LDR.
- **Store-then-reload** (a store, then a load of the same address) on the X3:
  plain 1.894 ns, LDAPR after STLR 1.883, LDAR after STLR 5.04, revert 5.11.
  LDAPR keeps store-to-load forwarding and LDAR loses it. That is the RCpc
  point, measured.
- **Cache-missing loads** cost the same with LDR, LDAPR or DMB ISHLD+LDR on
  every core (X3: 3.62, 3.54, 3.58 ns).

**Placement (the premise of prototype 2, re-measured).** The busiest thread
(tid 21243, `qemu_main`, busy 80% mean, 25 windows of 10 s) ran on the X3
for **72% of its busy time**. It spent 28% on the A715/A710s and 0.2% on the
A510s. It averaged 3.5 core changes/s and a runqueue wait of 3.5 ms/s. Per window,
its X3 share ranged from 3% to 100%.

That contradicts the 15.2% and 123 changes/s of the 09-11 Crimson capture
(4.1), which prototype 2's prediction was built on. The two runs differ in
title, build and sampler. On Galleon, at the arm's own apk, the prize is
bounded by the 28% of busy time off the X3. If an A715 runs the thread 1.1x
to 1.5x slower (the X3/A715 ratio across the ALU and load rows above), pinning
saves **3% to 9% of the vCPU's busy time (B)**. That is below the registered
band (-5% to -35%, point -18%). The prediction is left as registered; the arm
judges it.

**Clocks and thermal.** The X3 policy averaged 2,975 MHz (minimum window
2,500) against a cap of 3,187 MHz, which never moved. The early half averaged
2,923 MHz and the late half 3,022. The A715 policy averaged 2,281 MHz. The
hottest CPU zone peaked at 82.8 °C. GPU busy averaged 8.7%. No throttling in
240 s. A 20-minute soak is still the test for sustained clocks.

### 8.2 Prototype 1, TSO from RCpc (`perfarch-tso-rcpc-cost.json`)

| run | env | outcome |
|---|---|---|
| A1 `1790369082-perfarch-2154145` | -- | 103 windows, game frame median 33.65 ms, `gfps` p50 29 |
| B1 `1790369083-perfarch-2156492` | `HAKUX_TCG_TSO=rcpc` | **did not boot**: `tso mode=rcpc ... -> ON`, then no app line after `qemu_main` in 240 s. No crash line, no tier-1 promotion, no frame |
| A2 `1790369085-perfarch-2158840` | -- | harness exit after 20 s (`UtilAcceptVsock`), 12 windows: invalid |
| B2 `1790369086-perfarch-2160586` | `HAKUX_TCG_TSO=rcpc` | **did not boot**, identically: 184 logcat lines, ending at `qemu_main` |

**Verdict: under the prototype as built, the guest never reached its first
frame, 2 of 2 runs.** The logs do not say whether the process hung or died
(below). The cost question is unanswered, because the arm never ran a frame. `tso_judge.py` refuses all three short runs on validity.

This is not a harness failure. The other Nova no-boots in the last 250 runs
(2) logged zero lines. Both B runs logged the whole init, up to the first
translation, and stopped at the same line. In A1 the next lines, 2 ms later,
are the first BIOS loop's tier-1 promotions. So **the guest does not get past
its first blocks under rcpc**, and no `tso rcpc emitted` line (one per 65,536
accesses translated) ever appears.

The encodings check out by reading (LDAPR{B,H,,X} `0x38bfc000` and the
rest, STLR{B,H,,X} `0x089ffc00` and the rest), and so does the UXTW index
fold (`MO_32` is option 2). TMP2 is X30, which is reserved. Correct
encodings do not make the emitter correct, though.

**Leading candidate: an Alignment fault on the first misaligned guest
access.** x86 accesses need no alignment, and the emitter sends every
fast-path access to LDAPR/STLR with no alignment test (section 1, last row).
A misaligned LDAPR or STLR faults, and the kernel delivers SIGBUS
(`BUS_ADRALN`). QEMU's `sigbus_handler` (`system/cpus.c`) replaces bionic's
debuggerd handler. For anything but an MCE it re-raises the signal under
`SIG_DFL`. So the process dies with no tombstone, no `Fatal signal` line and
no `F DEBUG` line, and the app's log just stops. That fits both B runs.
"No crash line" is therefore not evidence that the process stayed alive.
Neither the app's logcat nor `tso_judge.py`'s `CRASH` regex can see this
death.

Two other candidates are less likely, both in the emitter:

- LDAPR/STLR take `[Xn]` only, and register 31 there is SP, not XZR.
- The XBOX RAM fast path in `prepare_host_addr` may hand the direct emitter a
  `HostAddress` shape this code does not expect.

**The check that settles it** needs no new run. In the B runs' full
logcat, look for the app pid's ActivityManager `has died` or `Process ...
exited` line, or check process liveness at the end of the soak. If the
process died, the fault is the leading candidate. If it stayed alive for the
full 240 s, look at the other two. Dumping `out_asm` would not settle it: it
shows correctly encoded instructions either way. Before any re-arm, the
emitter needs the alignment guard from section 1, and the guard's cost must
go into the prediction band.

### 8.3 Prototype 2, vCPU on the prime core (`perfarch-vcpu-prime.json`)

Galleon, `5f4abcc368` (apk `d5a8ff869a9d`), `HAKUX_TOPO=200,10` on both
arms. Read with `place_judge.py`:

| run | env | held | windows | game frame median ms | gfps p50/p90 | vCPU on the X3 | core changes/s | runqueue wait ms/s |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A1 `...2361095` | -- | 30 s | 17 | 33.40 | 29/29 | 88% | 0.9 | 1.71 |
| A2 `...2365726` | -- | 120 s | 51 | 38.60 | 27/29 | 80% | 1.4 | 2.96 |
| B1 `...2363587` | `PLACE_VCPU=prime` | 40 s | 20 | 33.40 | 29/29 | **100%** | **0.0** | 5.95 |
| B2 `...2367970` | `PLACE_VCPU=prime` | 240 s | 102 | 33.40 | 29/29 | **100%** | **0.0** | 5.06 |

**Verdict: refused on validity, no frame-time answer.** Harness exits
(`UtilAcceptVsock`) cut A1, A2 and B1 short. Only B2 ran its 240 s, and A2
covers a different, shorter stretch of the soak, so the two are not
comparable.

What the arm does establish (M):

- **The mechanism works.** The vCPU was on the X3 100% of the time, with zero
  core changes, in both B runs.
- **Pinning has a cost:** runqueue wait on the X3 rose from 1.7-3.0 to 5.1-6.0
  ms/s, because whatever else the scheduler puts on cpu7 now delays the vCPU.
- **This scene cannot show the gain.** The game frame median is 33.40 ms, the
  30 fps cap, in three of four runs, on both arms. Galleon at 1x is
  frame-capped on the Nova with the vCPU already 80-88% on the X3. A faster
  vCPU shows up only as lower busy %, and the busy % did not fall (A 85%/85%,
  B 92%/85%).

The next arm for this lever needs an uncapped, guest-bound scene (Crimson
Skies' heavy frames, where the guest is busy 41.5 of 50.2 ms), and it needs
harness runs that hold their full length.
