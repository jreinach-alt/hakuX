# lane.collapse433 notes

#433 (0.5: 50 Playable). Brief: find why Battlefield 2: Modern Combat (and
Blood Wake) lose frame rate, with the Nova's data first; decide whether the
Thor's collapse is heat.

All reads are of COPIES of the result dirs (`scratch/`, not committed). Times
are device-log local time (PDT). Offsets are seconds after the run's
`ROUTE ... mark gameplay` line in `run.log`. Tools: `pacetab.py` and
`joinread.py` (this dir) bucket the always-on 2 s instrument lines against
that offset.

## 1. BF2 on the Nova (`1790877270-autoverdict-2187810`, ref ec244430e3)

verdict.json: gameplay 514.7 s, fps_ok_share 0.6655, fps_window_median 29.9,
min 16.47, `pace.late_per_100` 11.15, worst_stall 247.9 ms, no hang, audio
0.0% short, thermal measured (28 samples), no pause, regimen default.

**Shape: recurring dips that fade with time, not a collapse and not a flat
ceiling.** Per 30 s bucket after the mark (`joinread.py ... 30`):

| offset s | fps med | windows >= 29.5 | vbl Hz | main-loop timer late, max ms | deferred VBLANKs | grid clamps | TBs generated | guest idle % |
|---|---|---|---|---|---|---|---|---|
| 0-30 | 23.8 | 3/11 | 49.9 | 27.4 | 37 | 15 | 4307 | 4.8 |
| 30-60 | 27.1 | 4/12 | 54.3 | 23.0 | 20 | 6 | 1298 | 5.7 |
| 60-90 | 26.1 | 5/13 | 57.6 | 17.4 | 30 | 4 | 1004 | 13.3 |
| 90-120 | 29.3 | 6/13 | 59.9 | 6.5 | 12 | 0 | 562 | 15.3 |
| 150-180 | 28.9 | 5/13 | 59.5 | 10.2 | 21 | 1 | 314 | 6.7 |
| 180-210 | 27.6 | 6/14 | 57.8 | 19.4 | 16 | 2 | 257 | 12.9 |
| 210-240 | 26.8 | 4/13 | 55.8 | 23.3 | 21 | 4 | 207 | 10.8 |
| 300-330 | 30.0 | 13/15 | 59.9 | 1.6 | 0 | 0 | 122 | 20.4 |
| 360-390 | 30.0 | 15/15 | 59.9 | 3.8 | 1 | 0 | 101 | 22.8 |
| 420-450 | 30.0 | 15/15 | 59.9 | 5.6 | 0 | 0 | 93 | 23.8 |

Columns come from `hakuX-pace` (fps), `vbl n= ... rate=` (vbl Hz),
`vblphase ... nodef(max=)` / `def(n=)` / `clamp=`, `hakuX-pages inval ... cg=`,
and `[rr425w] idle_us/(idle_us+busy_us)`.

- The bad windows are the first ~300 s of the mission. After 300 s nearly
  every window is at 30. The game's pace is 2 VBLANKs per flip, i.e. 30 fps.
- In a bad window the VBLANK clock itself runs slow (50-58 Hz). The adaptive
  deferral in `nv2a_vblank_timer_cb` (hw/xbox/nv2a/nv2a.c) holds a VBLANK
  while the game is mid-frame. Late main-loop timers (17-32 ms) also trip the
  grid clamp, which discards the lateness. The deferral is the RESPONSE to a
  game frame slightly over 33.4 ms, not the cause. It turns a 35 ms frame
  into 28.5 fps instead of 20.
- **Guest idle is 5-13% in the bad windows and 20-24% in the good ones. BF2
  runs at the edge of the vCPU budget even when it holds 30.** This is the
  `[rr425w]` read that memory says to take first. A bad window is one where
  the guest's per-frame work goes over 33 ms.
- **The first minute is JIT warmup.** Translated blocks per window fall
  4307 -> 1298 -> 1004 -> 562 -> ... -> 65. In 0-60 s the sampled `[rr425]`
  estimators put 28-39% of vCPU wall time outside guest code (their
  `gapus`/`tbus` sum past 100% later, so they are only usable in the first
  minute). The 150-240 s dips have little codegen (200-300 TBs per window)
  and still show late main-loop timers and low guest idle. Warmup alone does
  not explain them.
- Scene weight is steady across the whole window: `[rdc]` vertex and texture
  upload counts, `Tq` and renderer idle `Ri` all hold flat. Renderer idle
  `Ri` is 15-24 ms per frame in every bucket, so **the renderer is not the
  bound.**
- Ruled out on this run: `ubo_ring_grow` reached its 16-pool cap at
  10:57:35, 3 min BEFORE the mark, and never logs again (the next log would
  be n256). `hitch_report.py`: 9 hitches, 2 shader-classified, both before
  9.2 s of offset. Only 8 inline pipeline creates (`[shd413] dpm`) in the
  whole 514 s, so not a per-window cost.
- **Frames: only the mark frame exists** (`110044-gameplay.png`: first
  person, mission clock 00:20, in the level). The request had
  `frames_every 0`, so nothing shows whether the player kept moving for the
  514 s. The route is a blind walk/turn/fire loop. Scene-weight counters are
  steady, consistent with staying in the same area, but they do not prove
  movement.

### 1a. In a dip, the vCPU is BLOCKED, not short of CPU

`badgood.py <copy> 90 300 28.5` labels every 2 s line in 90-300 s (after
the JIT warmup) by the pace window around it (bad: < 28.5 fps). It then
compares medians, bad (n=50) against good (n=55):

| field | bad | good | reads as |
|---|---|---|---|
| `[rr425w] idle_us` per 2 s | 168 ms | 329 ms | the guest is busier in a dip |
| `[tlb68] cpu=` (vCPU thread CPU) | 1660 ms | 1874 ms | yet the vCPU thread runs LESS |
| `[idlehalt] run_us` | 1649 ms | 1893 ms | same |
| `[idlehalt] rq_us` (run queue) | 4.3 ms | 3.8 ms | not waiting for a core |
| span - run - rq = blocked | ~347 ms | ~103 ms | **+244 ms blocked per 2 s, ~3.5 ms per frame** |
| `vblphase` clamp / def | 4 / 31 | 0 / 5 | main-loop timers late at the same moments |
| `[rdc] tcpu` (render thread CPU, 60 flips) | 669 ms | 842 ms | the renderer works less |

About 3.5 ms more blocked per frame is enough to push a 30 fps frame
(33.4 ms budget, 20% guest idle in good windows) over 2 VBLANKs. The vCPU
stops, the main loop stops, and the renderer's CPU drops, all at once. That
looks like everyone waiting on the same thing.

The candidate chain, read from the code:
- NV2A's MMIO regions keep QEMU's global locking. No
  `memory_region_clear_global_locking` appears anywhere in hw/xbox, so every
  guest NV2A register access runs with the **BQL** held. This build is MTTCG
  (`SDL_main: using accel tcg,thread=multi`, logcat line 62), so outside
  MMIO and interrupts the vCPU does not hold it.
- `pgraph_read` takes `pg->lock` (`pgraph_mmio_lock`). The batch puller holds
  that lock across a whole `pgraph_method` batch, GPU waits included. This
  is #474's mechanism (`docs/lanes/flip474/NOTES.md` section 1).
- So a guest poll of a PGRAPH register mid-batch waits on `pg->lock` WHILE
  HOLDING THE BQL. The main loop, which runs the VBLANK timer, then waits on
  the BQL. That would explain the late timers (17-32 ms), the grid clamps,
  and why the dip shows up as a slow VBLANK clock.
- `user_read` (DMA_GET/REF polling) takes `pfifo.lock` the same way, and
  nothing instruments it.

Ruled out by reading:
- **The APU.** `mcpx_apu_read`/`write` are lock-free (qatomic). The APU
  frame thread takes the BQL only for `update_irq`.
- **The display path.** On Android, `XEMU_OPT_REDUCE_BQL` keeps
  `sdl2_gl_refresh`'s blit and event poll off the BQL.
- **Round-robin TCG** holding the BQL: the build is MTTCG.

`[lock474]` (perflog builds only) measures the vCPU's `pg->lock` wait per
2 s and splits it by puller phase. That is what the soak in section 4 reads.

## 2. The Thor runs: heat, by signature (no thermal record exists)

Neither Thor run has `thermal.jsonl`. Both ran `regimen=max` (perf_mode 2,
`perf_regimen.json`).

| run | launch (route start) | collapse starts | after launch | before -> after |
|---|---|---|---|---|
| BF2 `1-1790517591-titleroutes-1523259` | 08:07:09.8 | ~08:15:19 (mark+95 s) | 8 m 10 s | 19-24 fps -> 3.8-4.8 fps |
| Blood Wake `1-1790508532-titleroutes-1074940` | 04:31:25.6 | ~04:36:21 (mark+94 s) | 4 m 56 s | 37-39 fps -> 5.8-6.4 fps |

- A single step to a rate 5-7x lower, with no recovery. That is the
  thermal-pause-F8 signature (cpu3-7 paused, everything on cpu0-2). It is
  documented as 5-6 min from a cool start at MAX, and "fps 5-7x" (#507).
- **The VBLANK clock stays clean (59.9 Hz, no clamps) through the Thor
  collapse.** The Nova's dips are the opposite: a slow clock with late
  timers. So these are two different mechanisms.
- vCPU thread CPU (`[tlb68] cpu=` / dt) falls 93-96% -> 73-77% at the step.
  The thread is runnable but not running, which is what a run queue on three
  little cores looks like.
- The Nova runs the same route past the same offsets (90-300 s) at 26-30 fps
  with no step.
- **Verdict: heat artifact, not an emulator defect.** This rests on the
  signature, not on a cooling-device read. The Thor runs predate
  `thermal.jsonl`. Their refs (`3ea9cd9a34`, `7e38a5628d`) are older than the
  Nova's (`ec244430e3`) and carry no `[rr425w]` line.

## 3. Blood Wake on the Nova (`1790876348-autoverdict-2155592`): most of the window is not play

The brief's secondary question was the 21-callback audio burst at 10:44:51.
That burst is mark+131 s, and it sits exactly on a state change that the
rest of the run never leaves:

| offset s | fps | guest idle % | TBs gen | `Tq` | `[rdc]` vtx | renderer idle Ri ms | deferred VBLANKs |
|---|---|---|---|---|---|---|---|
| 0-128 (live) | 54-60 | 5-30 | 15-40 | ~1200 | ~1370 | 0.4-11 | 43-88 |
| 128-136 | 59 | 16-30 | **853, 1273** | -- | -- | -- | 5 |
| 136-667 | 59.9 flat | **0.0** | 1-9 | **32** | **420** | 15.6 | 0 |

- After 136 s the guest spends 100% of its time in one user-mode loop.
  `[rr425pc]` top entry is `g:000d2410` at 51,867 per window, and `[rr425w]`
  books all 2.01 s to one class. The renderer is idle 15.6 of 16.7 ms.
  Texture-dirty queries fall 1200 -> 32 and vertex uploads fall to 30%. For
  531 s nothing moves in the counters.
- This looks like a static screen (mission-failed, pause or results) that
  the blind RT/stick loop does not leave. No frame after the mark exists
  (`frames_every 0`) to say which.
- **Consequence:** Blood Wake's accepted 99.47% (OWNER_ACCEPTED.txt) rests on
  ~131 s of gameplay plus ~536 s of what is very probably a menu or
  static screen. The audio burst is the transition into it: a code burst of
  853 + 1273 TBs at mark+128-136 s, the same shape as the pre-mark
  short-callback bursts at load transitions (10:40:13, 10:40:28, 10:41:51).
  It is not a gameplay stall.
- The Nova Blood Wake run therefore says little about a collapse past
  131 s. Its 0-131 s of live play ran 54-60 fps in unlock mode, past the
  Thor's 94 s collapse point.

## 4. Nova perflog soak (step 3): the dips are GPU time in heavy views

`1-1790919561-lane.collapse433-390126`, ref `8b45e7c15c` (= master
`8e3b1f2ad2` plus docs), perflog, `PERF_REGIMEN=default`, hard-pinned Nova,
420 s, frames every 20 s. Mark at 22:47:45, end at 22:48:48: **63 s of
gameplay** (the route spends ~355 s in menus and loads; the brief's 420 s
cap leaves this much). `render_mode: auto (default) title=45410062
TU_DEBUG=(unset)`. The GPU timestamp period is calibrated in this build
(`init: GPU timestamp period reported=33.113 ns measured=52.049 ns ...
using=52.049 ns`), so GPU ms are true.

**The player is playing.** Frames f00019-f00021 (mission clock 00:27, 00:48,
01:10) show the view moving and ammo falling 20|125 -> 14|100 -> 9|75
(firing and reloading). By 01:10 the player faces a building wall. Reserve
ammo falls ~25 per 20 s, so it runs out about two minutes in. A blind route
that ends facing a wall with an empty gun is a lighter scene than the
opening view, and that is the likely reason the 514 s run's dips fade after
~300 s (section 1). Its late 30 fps is probably not representative play.

The shape matches the 514 s run (slow VBLANK clock, late timers, low guest
idle), somewhat deeper, as perflog and frame captures cost frame rate.

**The PGRAPH-lock chain of 1a is refuted.** `[lock474] rd_wait_ms` is 34.5
ms per 2 s in bad windows and 30.9 in good (`badgood.py`, -40..64 s, n
45/7). That is about 1.7% of the window, and the same in both.

**What grows is draw load and GPU time** (`modecmp.py`, rows = 60-flip
windows binned by the last frame's begin/end draw count `BE`):

| BE (draws/frame) | windows | fps | GPU ms | Fin/Fen ms | Draw ms | renderer Idle ms | render passes | >= 29.5 fps |
|---|---|---|---|---|---|---|---|---|
| 600-1200 | 14 | 27.6 | 21.8 | 1.3 | 7.8 | 15.2 | 25 | 7/14 |
| 1800-2400 | 16 | 18.9 | 34.9 | 11.4 | 16.2 | 7.7 | 38 | 0/16 |
| 2400+ | 8 | 16.0 | 40.0 | 16.8 | 18.7 | 6.0 | 45 | 0/8 |

Bad vs good windows (`badgood.py`): methods per frame (`hakuX-cpu M`) 25.7K
vs 10.3K, pipeline binds 808 vs 270, shader binds 2182 vs 862.

- In the heavy views **GPU time per frame (35-40 ms) exceeds the 33.4 ms
  budget of 30 fps**. The PFIFO thread then waits on the frame fence
  (`Fen` 11-17 ms), and the renderer's Idle (waiting for the guest) falls to
  6-8 ms. This is a GPU-bound frame, not a vCPU-bound one.
- The vCPU-side symptoms of section 1 (blocked time, late main-loop timers,
  VBLANK deferral) follow from it. The guest waits for the GPU through the
  FIFO, and the adaptive VBLANK stretches to the late frame. Their exact
  path is not needed for the lever.
- Recording cost (`Draw` 16-19 ms) is inflated by perflog's per-method
  clock reads, so it is not priced here. The GPU figure is not inflated by
  them.
- 38-45 render passes a frame on a tiler is the case GMEM handles worst:
  each pass loads and stores its tiles. BF2 is not in the per-title
  render-mode table (`xemu_android.cpp:871`, AUF and DOA only), so it runs
  Turnip's GMEM default. Sysmem moved AUF 16 -> 24 and DOA 13 -> 21 gfps on
  the Nova (`docs/lanes/flip474/sysmem.md`).

## 5. Sysmem comparison (decides whether the fix is in reach)

`1-1790920235-lane.collapse433-601955`: the same request with
`--env TU_DEBUG=sysmem` (`render_mode: auto (default) title=45410062
TU_DEBUG=sysmem`). Mark 23:08:13, end 23:09:15, 62 s of gameplay.
`modecmp.py scratch/soak390126 scratch/soak601955 --from -45`:

| BE bin | GMEM: n / fps / GPU ms / Fen | sysmem: n / fps / GPU ms / Fen |
|---|---|---|
| 600-1200 | 14 / 27.6 / 21.8 / 1.3 | 17 / 28.3 / 16.3 / 1.3 |
| 1800-2400 | 16 / 18.9 / 34.9 / 11.4 | 10 / 23.9 / 35.5 / 9.2 |
| 2400+ | 8 / 16.0 / 40.0 / 16.8 | 12 / 16.8 / 34.2 / 16.2 |

**Sysmem does not remove the bound.** In the 1800-2400 draws bin, the views
that make the dips, GPU time is the same (35.5 vs 34.9 ms). In 2400+ it
drops 15% and fps does not move (16.0 -> 16.8). It saves 25% where the frame
is not GPU-bound (600-1200), which buys nothing there. So BF2's GPU time is
not GMEM tile overhead, unlike AUF and DOA. One run per mode; the view
differs run to run, which is why the bins exist.

Frames: f00019 (00:28) renders normally. **f00020 (00:49) and f00021
(01:10) show a near-black world with only the HUD**, while the score rises
to 750 and ammo falls (24|75 -> 15|25), so the player is in play. This is
either the player against a dark wall or a sysmem rendering difference; one
run does not separate them. It is a further reason not to put BF2 in the
sysmem table on this evidence.

## 6. The GPU clock: the default regimen holds the Nova's GPU at its lowest step

The bound in sections 4-5 is GPU time per frame at the clock the GPU
actually ran. `thermal.jsonl` samples `gpuclk` every ~33 s:
- BF2 on default: 401 MHz in most samples of all three runs. In gameplay
  (after the mark): 514 s run 401 x 8, 475 x 5, 550 x 1, 615 x 1; soak
  -390126 550, 401; sysmem soak -601955 401, 401.
  `throttling` is 0 throughout and no cooling device is engaged (`gpu`,
  `devfreq-...kgsl-3d0` at 0). The governor chose the step; nothing capped it.
- Every Nova run on disk with a thermal record (python scan of
  `$DISPATCH_DIR/results`, `hold` samples only):

| regimen (perf_mode) | runs | gpuclk samples, MHz |
|---|---|---|
| default (0) | 55 | 401 x 977, 475 x 39, 550 x 33, 615 x 13, 680 x 103 |
| max (2) | 206 | 615 x 1057, 680 x 245 (never below 615) |

So BF2's confirmation (`1790877270`, regimen default) ran a GPU-bound frame
on a GPU clocked at 59% of its maximum for most of the window. The GPU busy
share the governor sees is below 100% because the frame is serialized: the
PFIFO thread waits on the fence (`Fen` 11-17 ms), then the GPU idles while
the next frame records (`Draw` 16-19 ms). That is the textbook way a DVFS
governor under-clocks an emulator.

**Section 7 tests this directly**: the same soak under `PERF_REGIMEN=max`.

## 7. Max-regimen comparison

`1-1790921431-lane.collapse433-967641`: the same request with
`PERF_REGIMEN=max` (`perf_regimen.json`: max, perf_mode 2, fan_mode 5).
`gpuclk` was 615 MHz in every sample from start to end (the 401 in the
run.log summary is the pre-start `cool` sample). Mark 23:23:21, end
23:24:26, 65 s of gameplay.

| BE bin | default (-390126): n / fps / GPU / Fen / Tot | max (-967641): n / fps / GPU / Fen / Tot |
|---|---|---|
| 600-1200 | 14 / 27.6 / 21.8 / 1.3 / 27.6 | 13 / 26.1 / 15.7 / 1.4 / 26.3 |
| 1200-1800 | -- | 3 / 29.9 / 16.8 / 1.2 / 26.2 |
| 1800-2400 | 16 / 18.9 / 34.9 / 11.4 / 37.9 | 15 / 20.7 / 28.9 / 7.9 / 33.8 |
| 2400+ | 8 / 16.0 / 40.0 / 16.8 / 46.2 | 9 / 17.2 / 35.0 / 14.1 / 42.0 |

- At 1.53x the GPU clock, heavy-view GPU time falls only 12-17% and no
  heavy window reaches 30. **The default GPU governor is a contributor, not
  the cause.**
- Renderer `Tot` (one frame's renderer wall time, perflog-inflated `Draw`
  included) stays at 33.8-42 ms. Anything over 33.4 ms takes 3 VBLANKs,
  which is why these windows sit at 17-21 fps. Without perflog's per-method
  clock reads, `Draw` is smaller. The original non-perflog run's dips were
  24-27 fps, not 17-20. No non-perflog BF2 run under max exists, and the
  brief's three-run budget is spent.

### What GPU time follows (`gpufit.py`)

Least squares over the 38-40 rows of each soak, GPU ms against the last
frame's draws (BE) and render passes (RP):

| run | GPU ~ BE | resid sd | GPU ~ RP | resid sd |
|---|---|---|---|---|
| default, GMEM | 9.8 + 0.0119 x BE | 3.81 | 0.88 x RP | 4.15 |
| default, sysmem | 6.4 + 0.0121 x BE | 3.67 | -3.4 + 0.83 x RP | 6.24 |
| max (615 MHz) | -0.8 + 0.0142 x BE | 2.73 | -10.8 + 1.00 x RP | 4.61 |

**GPU time is ~12-14 us per draw**, and that per-draw term does not shrink
at 1.53x the clock or in sysmem. Only the constant moves. `GPU Tot` is the
span between each command buffer's own first and last timestamps
(`gpu_ts_readback`, vk/draw.c), summed per frame. CPU submission gaps are
therefore not in it, and this is GPU execution time.

A per-draw cost that does not scale with core clock or render mode is a
per-draw LATENCY on the GPU, not shader ALU work: a pipeline stall or wait
between draws, or a memory fetch per draw. 2,000 draws at 640x480 should
not cost an Adreno 740 35 ms.

## 8. Diagnosis (for the next lane)

**Battlefield 2: Modern Combat on the Nova does not collapse.** It dips
whenever the view draws ~1,800+ draws a frame (38-45 render passes). In
those frames the GPU spends 35-40 ms against the 33.4 ms that 30 fps
allows, frames take 3 VBLANKs, and the window reads 17-27 fps. Light views
(~900 draws) run at 30. The 514 s confirmation's 66.5% is that mix. Its
late all-30 stretch is very probably the blind route parked against a wall
with an empty gun (section 4), so a longer window of real play would
probably read worse, not better.

- Not heat: no pause, `throttling 0`, Nova.
- Not a lock or the vCPU: `[lock474]` flat (section 4). The guest-idle drop
  and late VBLANK timers are downstream of GPU-bound frames.
- Not shader or pipeline compiles: `[shd413] dpm` sums to 5 in the soak's
  63 s and 8 in the 514 s run (`[pb569]` lines 5 and 8). That is a handful
  of creates, not a per-frame cost. Not the UBO ring (capped 3 min before
  the mark).
- Not GMEM tile overhead: sysmem leaves the heavy-view GPU time unchanged.
- The default regimen's GPU clock (401 MHz) makes it worse, but 615 MHz
  alone does not clear it.
- **The lever is the ~12-14 us per draw of GPU time that does not scale
  with clock.**

What the next lane should do first. This is a measurement that decides
between causes, not a guess at a fix:
1. Find what the renderer emits per draw that the GPU must wait on. Count,
   per frame, the barriers, `vkCmdUpdateBuffer`/copies, descriptor and
   pipeline binds, and dynamic-state calls inside render passes (perflog
   counters exist for binds: `xemu-work PBnd/SBnd`). A pipeline barrier or
   event wait per draw would serialize the GPU at a fixed latency per draw,
   which fits the clock-insensitive slope.
2. Check where vertex data is fetched from. If draws read guest-RAM
   vertex data through a host-visible, uncached mapping, each draw pays
   memory latency the core clock does not shorten. `[rdc] vtx=` shows the
   vertex-RAM walks are active in every BF2 window.
3. Prove it with Turnip's per-draw GPU counters or an off-CPU or GPU
   profile in a held session (a lane cannot drive the device directly, so
   this needs a hostops or held-session grant).

If (1) or (2) finds a per-draw stall, the fix fits the hardware and helps
every draw-heavy title, not just BF2. Register its prediction against the
three soaks here, binned by `BE` (`modecmp.py`), on the default regimen.

## 9. Blood Wake's audio burst (secondary)

Answered in section 3: the 21-callback burst at 10:44:51 is the transition
into a state the route never leaves (a code burst of 853 + 1273 TBs, the
same shape as the pre-mark load-transition bursts). It is not a gameplay
stall. BF2's runs show no flip pause of that kind: worst flip 247.9 ms, in
the first 10 s, and audio 0.0% short. **What matters more:** the accepted Blood Wake run spent
~536 of its 667 s in what is very probably a static screen. Its Playable
rests on ~131 s of real play. It should be re-checked with frames
(`--frames-every`).

## Do not repeat

- Do not read the Thor's BF2/Blood Wake collapses as an emulator defect:
  MAX regimen, 5-8 min after launch, a 5-7x step with a clean VBLANK clock
  (section 2).
- Do not reopen the PGRAPH-lock (#474) chain for BF2: `[lock474]` wait is
  ~1.7% of wall time in bad and good windows alike.
- Do not put BF2 in the sysmem table on these numbers: heavy-view GPU time
  is unchanged, and the sysmem run's frames went near-black (unexplained).
- Do not compare BF2 runs by whole-window fps: the view sets the draw count
  and the route is blind. Bin by `BE` (`modecmp.py`).
- Do not trust a blind-route run's late stretch without frames: BF2 ends
  facing a wall with an empty gun, and Blood Wake ends on a static screen.
- `gapus`/`tbus` in `[rr425]` sum past 100% after the JIT warms; they are
  usable only in the first minute.

## Process notes

- The brief asks for the soak "under `hold.sh wait nova collapse433:$$ 900`".
  A hold makes the Nova's dispatcher claim nothing (`dispatcher.sh`, top of
  the serve loop), so a hold taken by the requester blocks its own request.
  I queued the request without a hold. It is hard-pinned to the Nova, and the
  queue serves one request at a time per device anyway.
- `request.sh` reads the issue's labels with `gh api` for release priority,
  and `gh` is down. `HAKUX_RELEASE_PRIO=1` skips the read: #433 is the 0.5
  issue.
