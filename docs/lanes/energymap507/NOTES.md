# lane.energymap507: where hakuX's joules go (#507)

Energy per frame is the heat lever, and it is spent in our code. This lane
maps J/frame per benchmark title from the soaks already on disk. It splits
each frame's time across the threads and the GPU, converts that time to
joules as far as the data allows, and ranks the code paths by
J/frame saved x titles affected x probability.

No device runs were queued. Section 4 names six runs for lane.local.

## 0. Method, and what the instruments can and cannot see

- **Source.** 149 result dirs in `dispatch/results/` have a `thermal.jsonl`.
  - I copied them to `scratch/runs/` without the frames and ran
    `title_verdict.py` on each copy (`em_verdicts.py`).
  - 93 of them carry a `power.j_per_frame`. Every run cited below is a
    `dispatch/results/<id>`.
- **Window.** Every per-thread and GPU number is taken inside
  `title_verdict.py`'s scored window: `mark gameplay`, or `mark play` on the
  survey route, to `soak end` (`em_extract.py`).
  - A first pass that also counted boot put Blinx's GPU at 0.5 ms/frame. The
    real figure is 32.9.
- **Fields, and the log line each comes from** (semantics read in the source):

  | column | log line | meaning |
  |---|---|---|
  | fps, net W, J/frame | `verdict.json` `power` (#523) | `net_w` x scored s / guest flips |
  | vCPU ms/f, share | `W/hakuX [tlb68] cpu= dt=` (`accel/tcg/cputlb.c:263`) | vCPU thread `CLOCK_THREAD_CPUTIME_ID` / wall; ms/f = share x 1000/fps. `[idlehalt] run_us/span_us` (schedstat) agrees to 0.1 ms |
  | guest idle | `W/hakuX [rr425w] idle_us= busy_us=` (`cpu-exec.c:1317`) | share of vCPU wall time the guest spends in its idle loop |
  | render ms/f | `hakuX-perf [rdc] tcpu= f=` | render thread CPU. Printed only on lane/dirtytlb builds (#549, not merged) |
  | display, process ms/f | `hakuX-lane [pace526] thr_cpu_ms= proc_cpu_ms= flips=` (`ui/xemu.c:1935`) | display thread CPU, and whole-process `CLOCK_PROCESS_CPUTIME_ID`, per flip. Only on builds after #529 |
  | PFIFO busy (Draw/Surf/Fin) | `hakuX-phase Surf: ... Idle: \| Tot:` (`profile.c:791`) | PFIFO thread **wall** ms/frame, EMA a=0.2. Busy = Tot - Idle. Fin (Sub/Fen) is waiting, not CPU |
  | GPU (R) | same line, `GPU:x(R:y X:z` | Vulkan timestamp span per frame, EMA. Includes gaps inside command buffers, so it over-reads busy time |

- **What cannot be seen, anywhere on disk:**
  - The CPU time of the audio (`mcpx.apu_thread`, `voice_worker`), compile
    (`pgraph.vk.compile`) and submit threads. No line reports them.
  - **Which core or cluster** any thread ran on. No line logs
    `sched_getcpu` or per-core time, so a true per-cluster energy split cannot
    be made from the logs. Section 2 uses a calibrated model instead.
  - The render thread outside dirtytlb builds, and process CPU before #529.
- **GPU clock caveat.**
  - Runs before `902cf1ab53` (09-27 13:22) read the Nova's GPU at x0.636 (flip474).
    Every run in the table below is after that commit except Forza pre-leak.
  - Forza pre-leak (`53c81b1a7a`) is a Thor run, and the Thor's factor before
    the fix was never checked.
- **Noise floor. One pair cannot see less than about 5% on the Thor or 10%
  on the Nova.**
  - Thor Crimson, MAX, 5 runs: net 5.82 +/- 0.25 W, J/frame 0.198 +/- 0.007 (3.6%).
  - Nova AUF, halt on, MAX, `6554f06175`, 5 runs: 5.86 +/- 0.68 W, J/frame
    0.334 +/- 0.036 (10.6%).
  - This is why dirtytlb read "no visible watts" for 3.7 ms/flip of process
    CPU: the model below puts that at 1-2%.

## 1. The energy map

One representative run per title: the newest run with the most fields. MAX
regimen and idle halt off unless the row says otherwise. ms are per guest
frame.

| title | device, regimen | result dir | ref | fps | net W | J/frame | vCPU ms (share) | guest idle | render | display | process | PFIFO busy (Draw/Surf/Fin) | GPU (R) |
|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|---|
| AUF | nova max | `1-1790582079-idlehalt-2124199` | 40fabbaacc | 19.9 | 7.27 | 0.365 | 30.4 (0.61) | 0.41 | - | - | - | 14.8 (9.1/2.2/2.9) | 39.6 (19.9) GMEM |
| AUF | nova defaults | `1-1790593206-lane.sustain507-3238659` | 9d777502fa | 21.9 | 6.55 | 0.299 | 23.4 (0.51) | 0.22 | - | - | - | - | - |
| Blinx | nova max | `1-1790582080-idlehalt-2124441` | 40fabbaacc | 19.2 | 8.32 | 0.434 | 38.4 (0.74) | 0.43 | - | - | - | 24.9 (14.9/2.7/6.8) | 32.9 (31.4) |
| Blinx | thor defaults | `1-1790593205-lane.sustain507-3238578` | 9d777502fa | 18.9 | 4.96 | 0.262 | 32.1 (0.61) | 0.17 | - | - | - | - | - |
| Crimson Skies | thor max | `1-1790620928-lane.dirtytlb-1387249` | 249ea8fd05 | 29.5 | 5.88 | 0.200 | 31.9 (0.94) | 0.15 | 18.4 | 2.0 | 64.3 | 12.6 (10.8/0.6/1.6) | 6.7 (6.1) |
| DOA1U (sysmem) | nova max | `1-1790575472-rendermode474-966037` | 61e0edf87c | 34.2 | 8.36 | 0.245 | 25.6 (0.88) | 0.55 | - | - | - | 25.8 (5.3/**17.4**/1.7) | 18.9 (18.2) |
| Kabuki Warriors | nova max | `1-1790618696-lane.idlehaltdefault-845673` | 3a5d79e3ea | 27.6 | 7.95 | 0.288 | 34.7 (0.96) | 0.46 | - | 1.5 | **88.1** | 2.4 (1.3/0.2/0.8) | 10.8 (6.1) |
| Otogi | thor max | `1-1790609660-lane.slowtier2-otogi762702` | 97a6fa2b51 | 29.3 | 4.86 | 0.166 | 33.7 (0.99) | **0.85** | - | - | - | 2.1 (0.6/0.1/1.3) | 1.5 (0.5) |
| Forza (pre-leak) | thor max | `1-1790561602-forza414-3260817` | 53c81b1a7a | 20.2 | 5.39 | 0.267 | 45.2 (0.91) | 0.05 | - | - | - | 38.4 (15.2/9.3/13.1) | 16.3 (13.9), old period |
| Forza (leak) | thor max | `1-1790619761-forza414-1092523` | b991fb4c21 | 4.7 | 5.55 | **1.190** | 177.3 (0.83) | 0.00 | - | - | - | 141.8 (96.0/37.5/12.2) | 23.7 (21.9) |
| GTA SA | thor defaults | `1-1790565677-lane.sustain507-1257857` | f82e7e87fe | 22.8 | 5.57 | 0.244 | 35.6 (0.81) | 0.01 | - | - | - | - | - |
| 007 Nightfire | thor max | `1-1790563604-titleroutes-373432` | 4fcbe0262e | 25.1 | 6.37 | 0.254 | 30.6 (0.77) | 0.06 | - | - | - | - | - |
| Azurik | thor max | `1-1790560999-titleroutes-2862460` | e884ad260e | 29.9 | 5.59 | 0.187 | 32.0 (0.96) | 0.66 | - | - | - | - | - |
| D&D Heroes | thor max | `1-1790560999-titleroutes-2862610` | e884ad260e | 14.5 | 5.71 | 0.395 | 54.9 (0.79) | 0.18 | - | - | - | - | - |
| Alien Hominid | thor max | `1-1790572033-lane.pacing-1078761` | ead1086cb5 | 60.0 | 5.01 | 0.084 | 16.3 (0.98) | 0.37 | - | 1.0 | 28.7 | - | - |
| MechAssault 2 | thor defaults, **paused** | `1-1790572031-lane.sustain507-4131051` | f82e7e87fe | 12.2 | 3.95 | 0.322 | 62.7 (0.77) | 0.01 | - | - | - | - | - |

**PFIFO Draw breakdown** (`em_breakdown.py`, ms/f; `Pipe.Sh` is shader bind
plus uniform update per draw, `vk/draw.c:2229-2246`):

| title | Draw | Pipe (Tx / **Sh** / Lu) | Syn | Fin: Sub / Fen |
|---|---:|---|---:|---|
| Blinx nova | 14.9 | 9.2 (0.6 / **7.1** / 1.0) | 1.0 | 0.1 / **6.7** |
| Blinx thor (`3065294`, halt on) | 21.0 | 16.3 (**6.4** / **7.5** / 1.2) | 1.3 | 0.2 / **7.3** |
| Forza pre-leak | 15.2 | 8.1 (1.6 / **5.3** / 0.9) | 0.9 | **12.6** / 0.3 |
| Forza leak | 96.0 | 24.4 (18.5 / 4.1 / 0.7) | **64.4** | 11.9 / 0.3 |
| AUF nova (`2124125`) | 8.4 | 3.7 (0.1 / 2.9 / 0.5) | 0.4 | 0.1 / 1.4 |
| Crimson | 7.2 | 3.9 (1.7 / 1.8 / 0.3) | 0.8 | 0.3 / 0.9 |
| DOA sysmem | 5.35 | 2.2 (0.4 / 1.5 / 0.3) | 1.0 | 0.1 / 1.65 |

### Which titles lack a field, and the run that fills it

| missing | titles | run that fills it |
|---|---|---|
| PFIFO phases and GPU span | GTA SA, MechAssault 2, Nightfire, Azurik, D&D Heroes, Alien Hominid | a `--perflog` soak on master, one per title, same route |
| render-thread CPU | everything but Crimson | `[rdc]` ships only on lane/dirtytlb (#549). Once it merges, any perflog soak |
| process CPU (`[pace526]`) | AUF, Blinx, DOA (sysmem), Otogi, Forza, GTA, MA2, Nightfire, Azurik, D&D | any soak on a build after #529 (master has it) |
| audio / compile / submit thread CPU | all | no log line exists. `simpleperf record` per thread (profile P1) |
| core placement (cluster) | all | none on disk. `simpleperf record --cpu`-attributed samples, or `report --sort tid,cpu` (P1) |
| AUF and DOA on master (sysmem **and** 40fab's surface cut together) | AUF, DOA | a master perflog soak each (P4 covers DOA) |
| Thor watts per spinning vCPU core | all Thor titles | a same-build halt on/off pair (P2) |

## 2. Converting time to joules (inferred, with the model)

**Every number in this section is inferred.** The model is in
`em_split.py`:

- **idle** = P_idle / fps. P_idle is the median `cool` sample in
  `thermal.jsonl`, screen on, before launch: Thor 1.97 W (92 samples), Nova
  3.40 W (76). This is the only measured term.
- **vCPU** = share x k_v / fps. k_v is dW / d(vCPU share) from same-build
  idle-halt pairs, read here:

  | pair (halt off -> on) | device, regimen | d share | d W | k_v W/core |
  |---|---|---:|---:|---:|
  | `2124199` -> `2124125` AUF | nova max | 0.36 | 1.25 | 3.5 |
  | `2278164` -> `2274611` AUF | nova max | 0.63 | 2.28 | 3.6 |
  | `2124441` -> `2124356` Blinx | nova max | 0.37 | 1.83 | 4.9 |
  | `3064828-r2` -> `3064707` Blinx | nova max | 0.41 | 2.17 | 5.3 |
  | `3238659` -> `3238806` AUF | nova defaults | 0.16 | 0.59 | 3.7 |
  | `3238578` -> `589340` Blinx | thor defaults | 0.16 | 0.13 | 0.8, inside noise |

  - The Nova's 3.5-5.3 W per core is what an X3 prime core near 3.2 GHz
    draws, plus the uncore that rides on it.
  - **The Thor's single pair reads 4-6x lower.** That is either a real device
    difference (the vCPU off the prime core; vcpuprime428 saw the Thor eject
    a pinned vCPU to little cores under heat) or one pair's noise. The Thor
    range used below is 0.8-3.5. Profile P2 decides it.
- **other CPU** = (process - vCPU) ms/f x 1.0-1.5 W per busy core. These are
  mid cores near max clock, from public SoC figures, not measured here. Where
  there is no process CPU, the PFIFO busy wall time is used, and the term is
  a lower bound.
- **GPU** = GPU span x 3-5 W while busy, from public Adreno 740 figures, not
  measured here. The span over-reads busy time.

| title | measured J/f | idle | vCPU | other CPU | GPU | model sum |
|---|---:|---:|---|---|---|---|
| AUF nova max | 0.365 | 0.171 | 0.106-0.161 | >= 0.015-0.022 | 0.119-0.198 | 0.41-0.55 |
| Blinx nova max | 0.434 | 0.177 | 0.135-0.204 | >= 0.025-0.037 | 0.099-0.164 | 0.44-0.58 |
| Crimson thor max | 0.200 | 0.067 | 0.025-0.112 | 0.032-0.049 | 0.020-0.034 | 0.15-0.26 |
| DOA sysmem nova max | 0.245 | 0.100 | 0.090-0.136 | >= 0.026-0.039 | 0.057-0.094 | 0.27-0.37 |
| Kabuki nova max | 0.288 | 0.123 | 0.121-0.184 | 0.053-0.080 | 0.032-0.054 | 0.33-0.44 |
| Otogi thor max | 0.166 | 0.067 | 0.027-0.118 | >= 0.002 | 0.005-0.007 | 0.10-0.20 |
| Forza pre-leak thor | 0.267 | 0.097 | 0.036-0.158 | >= 0.038-0.058 | 0.049-0.082 | 0.22-0.40 |
| Alien Hominid thor | 0.084 | 0.033 | 0.013-0.057 | 0.012-0.019 | - | 0.06-0.11 |

What the model says, and where it fails:

1. **The idle floor is 25-50% of every title's J/frame.**
   - It is the one term that falls with frame rate alone.
   - On a title below its cap, every fps gained cuts J/frame by
     P_idle/fps^2, at no extra cost. So a speedup on an uncapped title
     (AUF, Blinx, D&D, Forza, GTA, Nightfire) is an energy win, whichever
     thread it comes from.
2. **The vCPU is the largest dynamic term on every title.**
   - On the Nova its range is 30-45% of J/frame.
   - How much of that is the guest's own idle loop is the `guest idle` column:
     0.85 Otogi, 0.66 Azurik, 0.55 DOA, 0.46 Kabuki, 0.43 Blinx, 0.41 AUF.
   - **With the halt off, any vCPU work saved on a title below 100% guest
     busy becomes idle-loop spin and saves no joules.** This is why dirtytlb's
     ~3 ms/flip of vCPU walks (3.55 -> 0.58) removed nothing measurable on
     Crimson.
   - The idle halt is therefore the gate on every vCPU lever for capped titles.
3. **The GPU is the second dynamic term on AUF, Blinx and DOA**, 25-45% of
   J/frame in the model. It is small on Crimson and Otogi.
4. **The model does not close on the Nova at MAX.** Its low end is 5-13% above
   the measurement on AUF and DOA. P_idle (3.40 W; the `cool` samples range
   2.29-4.91) is the least certain term. On the Thor the measurement sits
   inside the model's range.

## 3. Ranking: J/frame saved x titles x probability

The score is the % J/frame saved per title x the titles affected (of the 13
mapped) x p. Every probability is stated with its evidence.

| # | code path | owner, state | J/frame saved | titles | p | score |
|---|---|---|---|---|---:|---:|
| 1 | Forza's `invalid_surfaces` leak (#517 regression) | #583 forzadecay414-fix, draft; Nova runs queued | **-77%** measured bound: 1.12-1.19 -> 0.267 J/f (`3088454`/`1092424`/`1092523` vs pre-leak `3260817`). PFIFO Draw 96 ms/f, of which Syn 64, vs 15 | 1 (no other title's `[surf413] invalid=` exceeds 11 in any soak) | 0.85: known mechanism, fix restores a measured state. Not yet confirmed on device | 65 |
| 2 | **Idle halt default-on** | #566 idlehaltdefault, draft, judging | Measured: Nova defaults -10% (AUF); Nova MAX -18% / -25% (AUF / Blinx); Thor defaults -3% (Blinx, guest idle 0.17). Bound for Otogi and Azurik (guest idle 0.85 / 0.66, never measured with the halt): 0.7-3.0 W of 4.9-5.6, -14% to -55%, depending on the Thor's k_v (P2) | 9 with guest idle >= 0.15 (AUF, Blinx, DOA, Kabuki, Otogi, Azurik, AH, Crimson, D&D). Not GTA, MA2, Nightfire, Forza (<= 0.06) | 0.8: measured on two titles and both devices, in flight | ~58, and it gates #6-#7 on capped titles |
| 3 | **GPU in-pass time: shader execution** (#224 lighting helpers in every lit VS; #223's wedge GS, attached to every `TRIANGLES`/`LINES` draw, `glsl/geom.c:81-94`) | **Unowned** for execution cost. #580 litcompile569 owns the lit helpers' compile time; #581 is the P6 ubershader spike | Unmeasured. R ms/f: Blinx 31.4 (60% of its 52 ms frame, with PFIFO waiting 6.7 ms/f on the fence), AUF sysmem 21.0, DOA sysmem 18.2, Forza 13.9, Crimson 6.1, Kabuki 6.1. If execution is a third of R, Blinx saves 10 ms/f of GPU: -0.03 to -0.05 J/f (-7 to -12%), more if it lifts fps | 6 with R >= 6 ms/f | 0.25. Against: nv2a-era geometry is light, so the ALU needed is small. For: the VS is 4.5-5.8x and the GS 2.6-11x longer (turnipcost569), and a GS stage on a tiler also runs in the binning pass. P3 decides it | ~15 |
| 4 | **vCPU code quality**: guest JIT, indirect TB lookup, softmmu, exec-loop exits | **Unowned** (no open PR on `accel/tcg` besides #549/#575) | On vCPU-bound titles J/f falls about as 1/fps. A 15% vCPU speedup is about -13%. Headroom evidence: guest JIT 52.9% of GTA's vCPU (gta482:72-76); indirect lookup 27.9% (slowdown462:729, Black); TB lookup 12-14% and softmmu slow path 9.1% (perfarch:93-99) | 4 bound now (GTA, MA2, Nightfire, Forza: guest idle <= 0.06), +2 near-bound (Crimson 0.15, D&D 0.18); all 13 once #2 lands | 0.25: churn and lookup lanes have tried (jcache425; tbchurn424's `TCG424_RANGE=1` read 0.309 vs 0.278 J/f on Blinx Thor, worse) | ~13-20 |
| 5 | **Kabuki / DOA stall burn**: 1.8-2.25 cores busy while flips fall to 0-17 per 10 s | **Unowned, unexplained** | Kabuki `845673`: 22.0-22.3 s process CPU per 10 s at 1-31 flips, vs 14-16 s at 450-590 flips. DOA `1078334-r2`: 17.9-22.5 s per 10 s at 0-17 flips, vs 12.4-12.7 at 600. `[shd413] dpm=0` throughout (no pipeline misses), so it is not the compiler. In that stretch a frame costs about 8 J | 2 seen (Kabuki, DOA). Any title that stalls | ?: which thread, and whether it spins, is exactly what the logs cannot say. P1 decides it | profile first |
| 6 | **PFIFO draw path CPU**: `Pipe.Sh` (shader bind + uniform update) 7.1-7.5 ms/f Blinx, 5.3 Forza, 2.9 AUF; `Pipe.Tx` 6.4 Blinx-Thor | **Unowned.** #474's uniform-hash skip was inert on Blinx (forza414:1277) | The PFIFO thread sleeps when idle, so CPU saved is joules at 1.0-1.5 W/core. Halving Pipe on Blinx: -4.6 ms/f = -0.004 to -0.007 J/f (-1 to -2%). More if it lifts fps: Blinx's guest idles 43% of the time | 5 (Blinx, Forza, AUF, Crimson, DOA) | 0.5 | ~5 |
| 7 | **Render-thread TLB walks** | #575 dirtytlb-rd, draft | Crimson measured: render 18.4 -> 15.1 ms/f, process 64.3 -> 60.6 ms/f (`1387249` -> `1386630`); J/f 0.1995 -> 0.1977 (-1%, inside the 3.6% noise). Bound -2 to -2.5%. Black's walks are 17 ms/flip offline (dirtytlb:449) | 2 (Crimson, Black); Blinx has 0.3 ms | 0.9 | ~4 |
| 8 | **Render-pass structure beyond AUF and DOA** | #582 gmem474 owns AUF, DOA and Crimson by J/frame. **Kabuki is unowned** | Banked by #530: AUF -33%, DOA -49% (measured). The GMEM signature (X/R >= 0.8, sysmemjudge D1) holds only on Kabuki (10.8 GPU, R 6.1, X/R 0.77): X 4.7 ms/f x 3-5 W = -5 to -8%. Blinx X/R 0.05, Forza 0.17, Crimson 0.10: no signature. Crimson's sysmem arm was flat (`flip474-1819312`/`1819530`) | 1 (+6 titles with no GPU field) | 0.5 | ~3 |
| 9 | Surface path (`Surf`) on DOA | unowned; likely already cut | DOA sysmem Surf 17.4 ms/f on `61e0edf87c`, a branch off an old base. AUF read 23.2 there and 2.2 on `40fabbaacc`, so the same drop probably reached DOA on master. If it did not, DOA is PFIFO-bound (25.8 of 29 ms) | 1-2 | 0.4 that anything is left. P4 decides | ~2 |
| 10 | `vk/draw.c` `sched_yield` waits -> block | #572 pacing-spin, draft | Crimson wait CPU 0.783 -> 0.276 ms/flip = 0.015 core, under 0.5% (bound). The one-pair 0.2055 -> 0.1936 (-6%) is inside noise | 13 | 0.9 | ~5, bounded small per title |
| 11 | Texture hash and swizzle (NEON) | none | TxH 1.1 ms/f on Crimson, <= 0.2 elsewhere. `txu swz` is small. Bound < 1% | 1-2 | 0.5 | < 1 |
| 12 | Display/present thread | done (#529) | 1.0-2.7 ms/f remaining; < 1% | - | - | - |

What the ranking says:

- **In flight, measured or bounded:** #583 (Forza -77%), #566 (halt, -3 to
  -25%), #575 (-1 to -2.5%), #572 (under 0.5%), #582 (render mode by J/frame
  on three titles), #580 (lit compile time; its execution effect unmeasured).
- **Unowned and worth a lane:**
  - #3, shader execution on the GPU: the largest unmeasured term on the
    GPU-heavy titles, and the one that fits the platform.
  - #4, vCPU code quality: the largest time bucket in every title.
  - #5, the stall burn: unexplained, possibly cheap once seen.
  - #6, the PFIFO bind/uniform path.
  - Kabuki's render mode.
- **The order of #3 and #4 is set by P3 and P2.** P3 says whether GPU
  execution is a material share of R. P2 says what a vCPU ms is worth in watts
  on the Thor.

## 4. Profiles where the logs cannot decide (not queued; lane.local slots them)

At most six device runs. Each names what it decides.

| # | title, device, route | build and counters | runs | decides |
|---|---|---|---:|---|
| P1 | Kabuki Warriors, Nova, `kabuki-warriors` (targets.toml) | master `--perflog`. `simpleperf record -e cpu-clock -f 1000 --call-graph none -p <pid>` over the scored window, split into the stall stretch and the flipping stretch by timestamp. `report --sort comm,tid,cpu,dso,symbol` | 1 | Which thread burns the extra 0.8-1 core while flips stop (#5), and whether it spins. It also gives the first per-thread CPU split for audio, compile and submit, and the cluster placement, for every row of section 2 |
| P2 | Otogi, Thor, `otogi` | master, defaults regimen, cold start (xo <= 50 C, thor-regimen-does-not-matter), `HAKUX_IDLE_HALT=1` vs unset, perflog; `thermal.jsonl pw`, `[idlehalt]`, `[rr425w]` | 2 | The Thor's watts per spinning vCPU core (k_v 0.8 vs 3.5-5.3). Guest idle is 0.85, so dW is 5x the noise if k_v >= 1.5. This sets the value of #2 on the Thor and of every vCPU lever (#4). Coordinate with #566: skip it if idlehaltdefault already has a Thor same-build pair on a high-guest-idle title |
| P3 | Blinx, Nova, survey route (as `2124441`) | A = master perflog; B = a **measurement-only** apk from master with the geometry stage skipped for filled smooth triangles (`pgraph_glsl_need_geom`; pixels will move, not shippable). `hakuX-phase GPU:(R X)`, `Fin(Fen)`, J/frame | 2 | Whether the per-triangle GS (#223 wedge) is a material share of Blinx's 31 ms/f in-pass GPU time (#3). If R falls >= 25%, the wedge's execution cost is a top lever and the next lane reshapes it (bit-exact, cheaper, or only when a w <= 0 vertex is possible). If R holds, #3 drops, and #580's straight-line lighting is the remaining execution question |
| P4 | Dead or Alive 1 Ultimate, Nova, survey route as `966037` | master perflog (sysmem from #530 plus 40fab's surface path) | 1 | Whether the Surf 17.4 ms/f survives on master (#9). If it does, DOA is PFIFO-bound and Surf is its lever. It is also the first master J/frame for DOA |

Not in the six, for later: perflog soaks for the six titles with no
PFIFO/GPU field (section 1). One soak each fills the GPU column that #8 needs.

## 5. For the next lane: do not repeat

- **Window your numbers.** Medians over the whole logcat include boot and
  menus. The survey route marks `mark play`, not `mark gameplay`.
- **Do not judge a CPU saving by one power pair.** One pair resolves about 5%
  on the Thor and 10% on the Nova. Price it with the model (section 2) and
  confirm with multi-run arms, or with fps on an uncapped title.
- **A vCPU saving on a capped title is worth zero joules while the halt is
  off.** Check the `[rr425w]` guest-idle share before pricing any vCPU work.
- **Correct pre-`902cf1ab53` Nova GPU fields by x1.573.** The Thor's
  pre-fix factor is unchecked.
- **GMEM vs sysmem has a signature.** X/R >= 0.8 marks a title sysmem can
  help. R-heavy titles (Blinx) are a different problem.
- **The scripts are here, and they run on COPIES:**
  `em_verdicts.py` (verdicts), `em_extract.py` (per-run fields in the window),
  `em_summary.py` (all runs), `em_split.py` (the representative rows and the
  joule model), `em_breakdown.py`, `em_baseline.py` (idle watts),
  `em_invalid.py` (the leak census). Point `ENERGYMAP_RUNS` at the copies.
