# lane.perfarch NOTES

Brief: performance architecture for the Snapdragon 8 Gen 2 and Adreno 740
(#68 family). Base: master @ 724a0dd868. PR #308.
Deliverable 1: `docs/investigations/perf-architecture.md`.

## Attempt 2 (resumed 2026-09-25 ~23:00 UTC): still WAITING, PR kept draft

Attempt 1 did not finish because none of the nine Nova soaks had run: it
posted a `waiting:` comment and stopped, as the role asks. On resume, all
nine are still in `queue/` (positions 164-172 of 193), behind the rest of
the master sweep `0-a-now-8e683b3a26-*` (59), a `b` sweep (100), and
`xbox`/`vtxarr262` requests. Nothing to judge yet.

#308 stays **draft** on purpose. Marking it ready invites a fold, and a fold
that retires `lane/perfarch` can leave the soaks' refs `9181cb4c13` and
`5f4abcc368` unfetchable before the dispatcher builds them, voiding all
nine runs. The brief's done-when also needs one arm verdict. Next resume:
check `results/` for the nine ids, run the judges below, fill section 8,
post the table on #68, then `gh pr ready 308`.

## State at 2026-09-25 ~21:05 UTC: WAITING on the Nova

Nine requests are queued, all `--device nova`, behind a master sweep
(`0-a-now-8e683b3a26-*`):

| id | what | ref | env |
|---|---|---|---|
| 1790369070-perfarch-2147739 | survey | 9181cb4c13 | HAKUX_HOSTBENCH=1 HAKUX_TOPO=100,10 |
| 1790369082-perfarch-2154145 | TSO A1 | 9181cb4c13 | -- |
| 1790369083-perfarch-2156492 | TSO B1 | 9181cb4c13 | HAKUX_TCG_TSO=rcpc |
| 1790369085-perfarch-2158840 | TSO A2 | 9181cb4c13 | -- |
| 1790369086-perfarch-2160586 | TSO B2 | 9181cb4c13 | HAKUX_TCG_TSO=rcpc |
| 1790369349-perfarch-2361095 | place A1 | 5f4abcc368 | HAKUX_TOPO=200,10 |
| 1790369351-perfarch-2363587 | place B1 | 5f4abcc368 | HAKUX_TOPO=200,10 HAKUX_PLACE_VCPU=prime |
| 1790369352-perfarch-2365726 | place A2 | 5f4abcc368 | HAKUX_TOPO=200,10 |
| 1790369354-perfarch-2367970 | place B2 | 5f4abcc368 | HAKUX_TOPO=200,10 HAKUX_PLACE_VCPU=prime |

The arms job skips soak predictions, so these were queued by hand. To judge
them, run from this worktree, with dispatch result directories:

```
python3 tools/bench/hostbench_report.py $D/results/1790369070-perfarch-2147739
python3 tools/bench/tso_judge.py --expect docs/testing/predictions/perfarch-tso-rcpc-cost.json \
    --a $D/results/<A1> $D/results/<A2> --b $D/results/<B1> $D/results/<B2>
python3 tools/bench/place_judge.py --expect docs/testing/predictions/perfarch-vcpu-prime.json \
    --a ... --b ...
```

Then fill section 8 and the pending cells of the ranked table in
`perf-architecture.md`, post the table on #68, and mark #308 ready.

## What was measured offline (no device)

- **09-11 Crimson simpleperf capture** (`/home/justin/hakux-work/perf/perf.data`),
  tabulated per sample by `profile_categories.py`:
  - vCPU self time: JIT 29.4%; invalidation and re-arm 26.0%; TB lookup
    13.6%; softmmu slow path 9.1%; host runtime (emutls, PLT, outline
    atomics) 4.4%; I-cache 4.0%.
  - Placement: vCPU on the X3 **15.2%** of samples, 123 core changes/s.
    PFIFO on the X3 1.9%.
- **`XEMU_OPT_THREAD_AFFINITY` is compiled out**, and it would have pinned
  everything to cpu7 if it were on. The brief's premise that "xemu_android.cpp
  and pfifo.c already pin threads" is false for the shipped build.
- **CPU->GPU publication is already ordered** at `DMA_PUT` by the `pfifo.lock`
  pair (`user.c:83`). GPU->CPU is not: the semaphore release and report writes
  are plain stores after the surface download.

## Do not repeat

- `simpleperf report --sort symbol` rounds each one-sample row up to 0.01%.
  With about 3,900 JIT addresses, the JIT share reads 42% where the true
  figure is 29%. Count samples with `report-sample`, as
  `profile_categories.py` does.
- `simpleperf` has no `cpu` sort key in NDK 29. `simpleperf dump` carries a
  `cpu N` line per sample.
- Inside QEMU, bionic hides `cpu_set_t`, `sched_setaffinity` and
  `aligned_alloc`. `_GNU_SOURCE` is fixed at `osdep.h`'s first `<sched.h>`,
  and `aligned_alloc` needs API 28 against `minSdk` 26. Use raw syscalls
  and `posix_memalign` (see `hostbench.c.inc`).
- `first_cpu` is a QEMU macro. Do not use it as a struct field name.
- Shell `case`, `for` with `$VAR` and heredocs are refused by this session's
  command guard. Write a script file and run that.

## Next three things to build (after the arms)

1. **If the placement arm wins:** a fix PR that pins by role where each
   thread is created. vCPU to the prime core, PFIFO to the A715 pair, and
   render and compile to the A710 pair. It replaces the dead
   `XEMU_OPT_THREAD_AFFINITY` code, and must be gated on a 20-minute thermal
   soak (the sampler's p7 cap line) as well as the arm.
2. **The host build flags** (`minSdk 29`, `-march=armv8.2-a`,
   `-fvisibility=hidden`/`-Bsymbolic`). They need no device design, just
   one A/B for the 4.4%. The files belong to no lane: needs a territory
   grant for `android/app/build.gradle.kts` and
   `android/app/src/main/cpp/CMakeLists.txt`.
3. **GPU->CPU sync writes on the vCPU thread** (section 1.3, design B):
   `async_run_on_cpu` for the semaphore release and report stores in
   `pgraph.c`. First count them per frame with the method histogram.

Conditional: if the TSO arm shows STLR is the expensive half, a
`HAKUX_TCG_TSO=ldapr` variant (LDAPR loads, plain stores) keeps LD_LD and
LD_ST and drops only ST_ST. The doorbell lock pair already covers the
CPU->GPU direction where ST_ST mattered.
