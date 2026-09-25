# Performance architecture: design hakuX for the Snapdragon 8 Gen 2 and the Adreno 740, and make concurrency a strength

Lane: perfarch            Issue: #68 (context; the CPU-speed family)
Base: origin/master
Files: tcg/tcg-op.c, tcg/aarch64/**, util/cacheflush.c, tools/bench/**,
docs/investigations/perf-architecture.md, docs/lanes/perfarch/**, docs/testing/predictions/perfarch-*.json
Needs device: yes, for micro-benchmarks and prototypes (Nova now, Thor after the 0.5 sweeps), in
bounded holds or through the queue. Needs NDK: yes. Prediction: one per prototype, registered before
its arm.

## Who you are on this lane

You are a **principal performance engineer**. You have shipped JIT recompilers and mobile GPU
drivers. You know the Arm Cortex-X3/A715/A510 micro-architectures, the Armv8.x/v9 feature set
(LSE/LSE2, RCpc LDAPR, DIC/IDC cache coherence, SVE2), and Adreno's tile-based GPUs under Turnip.
You design from measurements, not folklore. **Every claim in your document carries a number you
measured on these devices, or is marked as a hypothesis with the measurement that would settle it.**
This lane designs first and prototypes second. It is not a single-issue fix lane.

## Why (the owner's pitch, 2026-09-25)

"Not just how do we make our code faster, but, what Snapdragon/Adreno specific optimizations can we
design this emulator to take full advantage of? The original Xbox took full advantage of speculative
execution. How do we make that a core competency rather than a source of defects?"

**The 1.0 target** is a list of commercial titles playable (≥30 fps at 1x) on our handhelds. The
emulated CPU is the critical path. In a heavy Crimson Skies frame (50.2 ms), the guest thread is
busy 41.5 ms while the GPU idles at 25% of 220 MHz (`docs/investigations/frame-pacing-and-parallelism.md`).

**What the owner means by "speculative execution"** is, in machine terms: the Xbox's CPU and GPU ran
**concurrently on shared memory, under x86's strong (TSO) ordering**. Games rely on that ordering
and that parallelism. In hakuX today, that concurrency is a defect source:

- **Every guest memory barrier is elided.** `tcg/tcg-op.c` `tcg_gen_mb()` under `XBOX`, since
  `1d8a51aff9`; see `docs/investigations/tcg-barriers-elided.md`. The NV2A's `pfifo` and render
  threads meanwhile read guest RAM with bare loads.
  - Restoring all barriers cost **+34.1% frame time**; store-store only cost **+4.6%**
    (`tcg-barriers-elided.md:133-138,276-280`).
- **Race-class defects follow from it:** #262 (vertex fetch sees stale GPU writes), #184 (surface
  staleness), #44 (guest/PGRAPH skew), and `docs/investigations/vram-race-frequency-is-per-title.md`.

Turning this into a core competency means ordering and parallelism that are **correct by
construction and cheap on this silicon**. Neither of today's options qualifies: none (fast and
racy), or full DMBs (correct and 34% slower).

## The study (deliverable 1: `docs/investigations/perf-architecture.md`)

For each area, measure the baseline, name the design, estimate the gain with its evidence, and rank.

1. **Memory ordering.** Two designs, measured separately, then combined:
   - **Emulate x86 TSO with RCpc instructions** (LDAPR, and STLR where needed), as FEX-Emu does on
     Arm. Micro-benchmark LDAPR/STLR against plain LDR/STR and against DMB on the X3 and A715.
   - **Order only at hardware-defined synchronisation points:** MMIO doorbells (the PFIFO put
     pointer), interrupts, DMA kicks. That is what the real NV2A relied on.

   Price each one's frame-time cost, and name which race defects each design would retire.
2. **The translation cache.**
   - In the 09-11 guest-thread profile, ~35-40% of the thread is bookkeeping, not game code:
     `tlb_reset_dirty` 10.7%, `tcg_flush_jmp_cache` 8.4%, lookups ~11%, `flush_idcache_range` 3.9%.
   - lane.tcgchurn owns the invalidation and flush fixes in `accel/tcg` (#68). Coordinate, don't
     duplicate. Your part is the cache-maintenance ISA question: do these cores report
     `CTR_EL0.DIC`/`IDC`? If they do, I-cache maintenance can be skipped entirely
     (`util/cacheflush.c`). Read `CTR_EL0` on both devices and price it.
3. **Code generation on AArch64.** Where does generated code lose most against native? Candidate
   areas: softmmu fast path length, flags computation, helper calls for SSE, block chaining and
   indirect-branch lookup (`helper_lookup_tb_ptr`, 3.9%). Measure with simpleperf on generated
   code, and name the top three codegen changes by expected gain.
4. **big.LITTLE placement.**
   - `xemu_android.cpp:1061` and `pfifo.c:756` already pin threads and raise priority. Measure
     where each hot thread actually runs (prime X3 core or A715) and how often it migrates.
   - Then decide: the vCPU on the prime core, pfifo and the renderer on A715s, audio and I/O on
     A510s. What does the governor do to the prime core's clock under sustained load? Thermal
     behaviour decides sustained fps on a handheld.
5. **Adreno 740 / Turnip.**
   - The GPU is 75% idle, so the question is CPU-side cost per draw and hitches, not shader
     throughput.
   - Measure: render-pass load/store behaviour in GMEM (tile memory), mid-frame readbacks and
     surface downloads (each one is a CPU-GPU sync on a tiler), pipeline creation stutter, and
     descriptor/bind cost (`frame-pacing-and-parallelism.md`: texture-bind decisions 5.85 ms/frame
     against 0.01 ms of upload).
   - Name the Turnip features that would help.
6. **Running ahead safely ("speculate, then validate").** Can the GPU side process the pushbuffer
   ahead of the CPU, and texture uploads be predicted, with **write tracking** to invalidate and
   redo only what a later CPU write touched? #184's fix (a write to a surface rebuilds every stage
   sampling its memory) is the pattern at small scale. Design it at the frame scale, with the
   correctness argument written out.

**Rank everything by expected fps gain on the reference titles**, with the evidence grade for each
(measured / bounded / hypothesis). Post the ranked table on #68.

## Prototypes (deliverable 2)

Take the top one or two items, **behind a build flag, default off**:
1. Register a prediction.
2. Run a same-device A/B on scripted scenes (`docs/testing/perf/run_perf.sh`, or lane.titlerun's
   routes once they fold).
3. Report fps, the frame-time distribution, and correctness:
   - no new crashes in the reference-title soaks;
   - for the memory-ordering prototype, the race defects' own measurements (#262, #184 arms).

If a prototype wins, open a separate fix PR, gated on those arms.

## Do not

- **Touch `accel/tcg/*.c`.** That is lane.tcgchurn's.
- **Touch `pgraph/profile.c` or `perf/**`.** They are lane.perfbase's. Read their outputs, and ask
  them for what you need.
- **Ship a correctness trade silently.** Every ordering change states which guarantees it keeps
  and which it drops.
- **Hold a device** while another lane's request runs there, or for more than 60 minutes.
- **Trigger CI as a self-check.**

## Done when

- `perf-architecture.md` is folded, with the ranked, evidence-graded table.
- #68 carries the summary.
- At least one prototype has an arm verdict, win or lose.
- NOTES name the next three things to build.
