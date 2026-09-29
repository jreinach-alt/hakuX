# lane.kabukistall: the Kabuki Warriors / DOA flipless stall (#507 rank 5, #433)

Brief: find why Kabuki Warriors (43560001) stops flipping for 20-130 s with about
2 cores busy, and fix it. PR #616.

## 1. Answer

**The stall is cold graphics-pipeline compilation on the PFIFO thread, #569's stall.**

- Each fight brings about 300 new pipelines (262-334 per run, below). The pipelines are compiled inline by `vkCreateGraphicsPipelines`, at about 350-390 ms each.
- The draw that needs a pipeline waits for it, so the guest stops getting flips and sits in its idle loop.
- The busy cores:
  - one core is Turnip compiling on the PFIFO thread;
  - one core is the vCPU spinning in the guest's idle loop, because the idle halt is off.
- **K1 (section 8), on master with B1 in and a cold cache:** 199 ms per create, half of the pre-B1 cost. The fight stall is still there: 68.6 s, 333 creates, and 97% of the window is `vkCreateGraphicsPipelines` by the driver's own clock. About 3/4 of misses change the vertex program or the fixed-function vertex state.
- A warm `vk_pipeline_cache.bin` removes the stall. Five same-APK runs, in queue order: the first two stall 114-131 s, the last three do not stall. One of those three meets 627 misses and serves them in 2-3 s windows.
- **energymap507's "no shader misses" is wrong for these runs.** `[shd413]` reads dpm 82-329 per stall window in every Kabuki stall below (section 2).

This is not a hang in the sense of a deadlock, a timeout, a lost interrupt, DMA, audio or a CPU-GPU fence. Section 3 lists what was checked.

## 2. Measured (Nova, all runs on disk under `$DISPATCH_DIR/results/`)

Tool: `docs/lanes/kabukistall/ks_windows.py <result dir>` prints one row per 60-guest-frame perf window. The row joins the `hakuX-perf gfps=` line, `hakuX-pace ms=`, `[shd413]` dph/dpm/dsh/dsm and the `hakuX-phase` Shd/Pipe/Tot ms/frame. `t_mark` is the window's end, in seconds from `mark gameplay`. Only windows over 1.5 s print.

### 2a. The stall windows

| run | cache | t_mark (end) | window s | dpm (pipeline misses) | Shd ms/f | Pipe ms/f | G max ms |
|---|---|---|---|---|---|---|---|
| `1-1790639272-lane.gmem474-125693` (a1) | kept (same APK; Kabuki's first run on it) | +23.2 | 34.0 | 110 | 917.5 | 927.0 | 10010 |
| | | +77.0 | 53.7 | 142 | 243.5 | 246.5 | 10153 |
| | | +120.0 | 43.0 | 82 | 683.2 | 689.6 | 10071 |
| `1-1790639273-lane.gmem474-125740` (b) | kept | +135.2 | 114.5 | 329 | 2163.6 | 2184.7 | 8495 |
| `1-1790618696-lane.idlehaltdefault-845673` | cleared | +22.1 | 32.7 | 115 | 451.8 | 457.3 | 9617 |
| | | +83.7 | 61.6 | 147 | 245.3 | 249.6 | 10065 |
| `1-1790618748-lane.idlehaltdefault-846115` | kept | +153.8 | 118.2 | 296 | 3192.8 | 3221.0 | 8098 |
| `0-0-x-1-1790650269-hostops-energymap507-p1` (P1) | cleared | +44.0 | 53.3 | 182 | 429.3 | 436.4 | 9750 |
| | | +107.4 | 63.4 | 125 | 1.1 | 1.8 | 10122 |

- dsm equals dpm in every stall window: each pipeline miss comes with a new shader binding, not only new render state.
- The ms/frame figures are over the window's 60 frames, so they are the scale, not a per-miss time.
- Stall seconds over misses gives the per-miss cost. This is inferred, since it assumes the stall is compile time:
  - a1: 130.7 s / 334 = 391 ms;
  - b: 114.5 / 329 = 348 ms;
  - P1: 116.7 / 307 = 380 ms.
- #569 measured DOA directly at 359-394 ms per create before B1 (shaderfb569 NOTES:149, :176; PR #607).
- G max of 8-10 s is the longest gap between two guest flips inside a window: about 25 misses between two flips. **No timeout exists on this path.** `vk/compile_worker.c` and `vk/draw.c:2783-2866` show an inline create with no wait, and grep finds no 10 s constant in `hw/xbox/nv2a`.

### 2b. Warm cache, a natural experiment: gmem474's five Kabuki runs on APK b400e9693dd7, in queue order

| run | env | gameplay windows > 1.5 s | stall |
|---|---|---|---|
| a1 `125693` | TU_DEBUG=startup | 3 windows of 34-54 s, 334 misses | **131 s** |
| b `125740` | +sysmem | 1 window of 114.5 s, 329 misses | **114 s** |
| c `125795` | +gmem,forcebin | 0-6 misses per window, all under 3 s | none |
| d `125996` | autotune profiled | 152 + 131 + 90 + 254 misses in windows of 1.8-3.3 s (Pipe 0.7-56 ms/f) | none |
| a2 `126084` | TU_DEBUG=startup | 0-6 misses per window | none |

- The CPU's fighters are random (the kabuki-warriors route's header, in each request.json), so b met content a1 had not compiled.
- d's 627 misses cost 2-3 s in all: the pipeline cache served them. So a miss that hits `vk_pipeline_cache.bin` costs a few ms.
- The TU_DEBUG settings differ between the runs. Render mode does not enter a pipeline's compile, but this table is a natural experiment, not an arm.

### 2c. What the threads do: P1's simpleperf, split by time

hostops recorded `simpleperf record --app -e cpu-clock -f 1000 --call-graph none` for 130 s, from mark +32 s to +162 s (`/home/justin/hakux-work/perf/energymap507-p1/perf.data`, 254,828 samples, 0 lost).

hostops read the window as "almost all flipping" from the 1 s gfps figures. **The perflog says otherwise.** From +32 to +107 s the window is inside the two P1 stall windows of 2a: 60 frames took 53 s and then 63 s. gfps is the rate of the last second before the line, not the window's.

I binned the samples with `simpleperf report-sample` (host NDK 29), in 5 s bins, cores = samples / 5000:

| mark + s | all threads | vCPU 32060: JIT / libxemu / vdso | PFIFO 32070: Turnip / other / libxemu |
|---|---|---|---|
| 32-107 (stall) | 2.15-2.21 | 0.14-0.93 / 0.04-0.71 / 0.00-0.13 (sum ~0.97) | **0.81-0.87** / 0.10-0.13 / 0.00-0.01 |
| 107-122, 132-162 (flipping) | 1.36-1.69 | ~0.93 total | **0.02-0.23** / 0.03-0.12 / 0.11-0.19 |
| 122-132 (the 11.3 s window, 20 misses) | 2.09-2.17 | ~0.97 | 0.70-0.87 |

- **PFIFO in the stall:** of 74,312 samples, the top symbols are NIR/ir3 compiler passes: `match_expression` 4,873, `nir_algebraic_impl` 2,721, `_mesa_hash_table_search` 2,370, `nir_block_cf_tree_next` 2,208, `dce_cf_list` 1,695, `ir3_legalize` 1,550. This is the shader compiler, not command recording or a fence wait.
- **vCPU in the stall:** of 73,708 samples, `cpu_exec_loop` has 24,416, JIT code at `+708373f0b0..f124` about 15,000, `__kernel_clock_gettime` 5,594, `cpu_tb_exec` 3,164 and `rr425_pc_note` 1,447. That is a two-TB loop exiting to the dispatcher on every pass: the guest's idle loop.
- **The guest idle loop, from the perflog.** In a1's stall `[rr425w] idlepc=8001b02e`, and idle_us/(idle+busy) is 0.95-0.96 (w=108-112, 06:07:41-06:07:49). While flipping it is 0.30-0.56 (06:09:51-06:10:19). The `[rr425pc]` top pair `e:8001b02e:fb9090` / `e:8001b02f:9090fa` (sti; nop; nop) is 27.80M + 27.80M executions of `it=55631705` per 2 s: 99.9% of the guest's executed TBs.
- The idle halt (#566) would stop that second core burning. It saves energy, not frames.

## 3. Checked against, and not the cause (a1's stall, 06:07:36-06:09:37 device time)

- **GPU / fence.** `hakuX-phase Fin:14.0(Sub:0.1 Fen:13.8)` and `GPU: R 11.1 X 11.5` ms/f against Pipe 927 ms/f (06:07:59.995). `cblat ... mdraw=5375.2 of span=5376.2` (06:07:48.749): the PFIFO is inside a draw method for the whole window, which is the inline create.
- **The pusher.** `hakuX-cpu Push:937.0ms [Pull:936.4(... Mth:935.4)]` per frame is method time: the same draw.
- **`[tlb68]`.** Flat, `ff=0 pf=0` in most windows, with a burst at w=118 when content loads.
- **Audio.** `hakuX-audiocap starve: 0/703 callbacks short` (06:08:06.717).
- **`fifoskew`.** kicks 0-727 per window, `bound=0 held(n=0)`. The FIFO is not blocked on its own flow control; it has no consumer while the draw compiles.
- **`hakuX-stall` Finish.** `stl9 stlDef69` per 60 frames, the same in flipping windows.

## 4. DOA

The same mechanism, measured by #569:
- The fight load is 21 misses, 8,277 ms (shaderfb569 NOTES:149, :182).
- 78% of create time is the VS, #224's lit helpers, and 20% the GS, #223's wedge (shaderfb569 NOTES:186).
- The vCPU spins in the guest idle loop meanwhile (shaderplan569 NOTES:24-26, :236-237).

On the cold master-path run `0-0-x-0-1790657057-litcompile569-206765`, the largest compile windows are 13.6 s (26 misses) and 5.2 s (10 misses, Shd 806 ms/f). DOA's misses come in tens per load. Kabuki's come in hundreds per fight, which is why Kabuki's stalls reach 100+ s.

## 5. What fixes it, ranked by probability x size of the win

| # | approach | win on Kabuki | p | status |
|---|---|---|---|---|
| 1 | Remove the first-time compile. The ubershader or uber libraries under GPL (#569 P6/P5, PR #581, PR #594) fit the hardware and are proven in comparable emulators | the stall goes to ~0 (a fast link is ~0 ms, PR #581) | 0.5 | in flight on #569. Kabuki is **not** among their titles |
| 2 | Pre-build a per-title pipeline key set at boot (#569 P3). Kabuki's route spends ~210 s in menus before a fight | full for covered keys. 2b shows a cache hit costs ms | 0.6, given the key set of the whole roster | planned in shaderplan569 §P3, not dispatched |
| 3 | B1, cheaper lit helpers (#580, merged 2026-09-29 05:40Z) | ~2x per create on DOA (359 -> 181 ms, PR #607): a 130 s stall becomes ~65 s, still a hang | 0.9 that it halves; ~0 that it ends the hang | on master; **no Kabuki run includes it** (all runs above predate 36ebaac1e5) |
| 4 | Async compile (#567) | none: the draw still waits (shaderplan569 NOTES:145-149) | ~0 | - |

- A fix to the compile cost is #569's territory: `hw/xbox/nv2a/pgraph/vk/*`, `glsl/*`, owned by those lanes. This lane does not write a second copy.
- What this lane adds:
  - Kabuki is the worst-case title for #569: about 300 misses per fight, against DOA's 21.
  - Kabuki's route should be a leg in #569's arms.
  - Kabuki's Playable verdict cannot pass on a cold cache until #1 or #2 lands.

## 6. The one device run: K1

**K1**: Kabuki, Nova, from `lane/kabukistall` (code = master 2fcb228749, which has B1), `--perflog`, route `kabuki-warriors`, 600 s. A lane ref builds its own APK, so the dispatcher clears the shader caches (`result.json shader_cache: cleared`). If it reads `kept`, K1 is not a cold read.

It decides two things:
- **B1's effect on Kabuki.** The #569 P1 fields (`dpc_ms`, `dpn`, `dvs/dgs/dfs_ms`) give the per-create ms.
- **Which #569 remedy covers Kabuki.** `kd=` gives the ShaderState class that differs on each miss: VP/FF/CB/TX/FL/PO/GE.
  - Mostly FF (fixed-function vsh, the lit path): B1 and the VS side of GPL.
  - Mostly CB (combiner): P6's pixel-shader ubershader.

What a hit looks like, written before the run:
- At least one gameplay window of 20 s or more with dpm of 50 or more. Kabuki's content is cold, so the stall should still be there.
- Per create (dpc_ms / dpn over the stall windows): 150-230 ms, against 348-391 ms before B1.
- The stall about halves for the same miss count: at 300 misses, 45-70 s.
- If the stall is absent with dpm of 100 or more, the per-create figure decides. Under 50 ms would mean something besides B1 changed the cost, and the anatomy above would need re-reading.

Status (2026-09-29): queued as `1-1790702688-lane.kabukistall-194847` from `a5b4e27bc7`, release tier via #433 and pinned to the Nova, 600 s. Posted: #507, #433 and #569 (Kabuki proposed as a leg for P5/P6/P3). Result: section 8.

## 8. K1's result: B1 halves the create, the hang stays

Run `1-1790702688-lane.kabukistall-194847`: Nova, APK 41ac0041b93d, `shader_cache: cleared: apk 4db6cd5e6973 -> 41ac0041b93d`, so a cold read. Tool: `docs/lanes/kabukistall/ks_creates.py <result dir>`. It prints each `[shd413]` line with dpn >= 10: dpc_ms, the mean per create, the stage ms and the `kd=` classes.

| t_mark (end) | window s | dpn | dpc_ms | ms per create | dvs_ms | dgs_ms | dfs_ms |
|---|---|---|---|---|---|---|---|
| +4.4 | 20.1 | 162 | 18,637 | 115 | 8,988 | 6,754 | 362 |
| +19.8 | 15.4 | 72 | 14,098 | 196 | 6,619 | 5,268 | 276 |
| +30.2 | 10.5 | 41 | 9,262 | 226 | 4,386 | 3,438 | 179 |
| +40.8 | 10.6 | 46 | 9,355 | 203 | 4,460 | 3,438 | 182 |
| +60.7 | 5.9 | 24 | 4,781 | 199 | 2,212 | 1,830 | 95 |
| **+151.2** | **68.6** (gfps 0, G max 3.9 s) | **333** | **66,283** | **199** | 31,277 | 24,899 | 1,291 |
| gameplay total | | 678 | 122,417 | 181 | 57,941 (47%) | 45,628 (37%) | 2,386 (2%) |

- **Hit, as written before the run (section 6).** The 68.6 s window has 333 misses (the stall is still there); per create is 199 ms, in the 150-230 band, against 348-391 before B1; 68.6 s is inside the 45-70 s band.
- **The stall is create time, now measured rather than inferred.** In the 68.6 s window dpc_ms sums to 66.3 s: 97% of the window is `vkCreateGraphicsPipelines`. Section 2a's per-miss figures were stall seconds over misses; this one is the driver's own clock.
- **Where the create time goes:** VS 47%, GS 37%, FS 2% over gameplay. The rest is link and pipeline assembly.
- **What differs on each miss** (`kd=` over gameplay, 678 misses; a miss counts once per differing class): VP 505, FF 489, CB 365, TX 300, PO 377, GE 211, FL 175, NONE 0. So 72-75% of misses change the vertex program or the fixed-function vertex state, and 54% change the combiner. A pixel-only ubershader (#569 P6) would leave most misses paying the VS+GS compile. The vertex side must be covered too: GPL uber libraries (P5) or the key-set prebuild (P3).
- **Kabuki is still not Playable on a cold cache.** A 68.6 s window with no flip is a hang under the criterion. B1 did what it could: it halved the cost of each create, and it did not remove the compiles.

## 9. Attempt 2 (2026-09-29, resumed by handback)

Attempt 1 ended correctly: it was waiting on K1, a device request outside the session. Its one gap was that it left no `[lane.kabukistall] waiting:` comment, so handback resumed it on the quiet clock. Attempt 2 read K1 (section 8), added `ks_creates.py`, posted the result, and marked #616 ready. There is no emulator change in this PR. The fix belongs to #569's lanes (section 5), so there is no arm and no prediction.

## 7. For the next lane

- Do not read gfps as a window's rate. It is the last second's. Use `hakuX-pace ms=` for the window's span, or `ks_windows.py`.
- Do not look for a timeout. The 8-10 s G max is about 25 inline creates between two flips.
- A Kabuki run on an APK that has already met the same fighters reads warm and shows no stall (2b). A verdict run should say which it was.
