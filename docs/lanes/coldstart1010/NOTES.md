# lane.coldstart1010: NFS MW's first race start after loading (#433, 0.5)

Brief: `briefs/coldstart1010.md`. The question is what holds cold start 1 at 35-39 ms when the warm countdown
runs 33.4-33.8 ms against a 33.3 ms floor, with all six switches on. Then build the largest fix.

## 1. What existing runs already show

Base: the drawrec1010 probe runs at six switches, plain build, `HAKUX_PROBE_WAITS=1` and `HAKUX_FRAMETRACE=1`
(4030728, 4034875). Read with reportasync1010's `ftpair.py` and `ftbuckets.py`. Cold is mark `gameplay` -2..+1.5 s;
warm is go2..go12.

| per frame (ms) | cold (2 runs) | warm |
|---|---|---|
| PFIFO P (run + runq + blk) | 42.0 / 40.1 | 34.4 |
| PFIFO p_run | 19.6 / 18.9 | 16.7 / 16.9 |
| PFIFO pidle | 15.7 / 14.5 | 16.0 |
| p_c_rep (waits inside process_pending_reports, pfifo.lock held) | 6.1 (9.9-11.7 in heavy frames) | 2.2-2.4 |
| GPU busy | 12.45 / 11.82 | 9.6 / 9.9 |
| guest work | 26.8 | 21.7 |
| guest lockw (DMA_PUT store waiting on pfifo.lock) | 9.41 / 8.65 (13.7-14.0 heavy) | 4.06 / 3.80 |
| guest busy (work + lockw) | 38.5 | 28.2 |

Frames past 2 VBLANKs on either thread: 60% cold. With lockw removed, 24%.

So the cold start is paced by the guest, and most of its excess is `lockw`. The PFIFO thread is busy about 26 ms
and does not pace the frame. That lockw is the guest's DMA_PUT store waiting while the PFIFO thread holds
pfifo.lock.

`[probe1010]` rotation counts (drawrec1010 `proberead.py`):

| | rotations/frame | blocking rotations/frame | ms/frame blocked | ms per block |
|---|---|---|---|---|
| cold | 3.8-6.3 | 1.2-2.3 | 3.5-8.2 | 2.6-3.9 |
| warm | 2.3-2.5 | 0.55-0.75 | 1.7-2.5 | |

## 2. Mechanism: the ring is 2 deep on the Nova, not 3

`NUM_SUBMIT_FRAMES` is 3 (renderer.h). That is the compiled maximum. The runtime depth `num_active_frames` comes
from `xemu_get_submit_frames()` (command.c, draw.c), and Android sets it from the `submit_frames` pref, **default
2** (`xemu_android.cpp`, `GetPrefInt(..., "submit_frames", 2)`, from commit 5a047fd645 in March 2026: "Triple
buffering tanks performance"). Every Nova run logs `submit frames: 2`, including all the postput1010 and
drawrec1010 runs.

The path:

1. The guest runs slower cold, so the PFIFO thread catches up to DMA_PUT more often.
2. Each catch-up with an open command buffer and new draws takes a STALLED finish in
   `pgraph_vk_process_pending_reports` (reports.c). That finish runs with pfifo.lock held.
3. Every finish on the PFIFO thread rotates the frame slot and waits on `frame_fences[next]` (draw.c, rotation).
4. At depth 2, `next` is the slot submitted at the finish before this one. When the GPU has not finished that
   command buffer yet, the wait is a whole command buffer's GPU time.
5. The wait happens with pfifo.lock held, so the guest's DMA_PUT store (`user_write`) waits too. That is lockw.

Cold takes 4-6 rotations a frame against 2.3-2.5 warm, so the waits multiply.

**Correction to a premise several lanes carried.** These sources read the 3 at draw.c:37 (the desktop default)
as the depth:
- frametrace NOTES ("Three slots ..., the command buffer this thread submitted two finishes earlier");
- nfs30plan1010 NOTES section 2 ("3 slots, `g_xemu_submit_frames = 3`");
- the HAKUX_STALLFIN comment in reports.c ("the slot two finishes back");
- this lane's brief ("`NUM_SUBMIT_FRAMES` is 3").

On the Nova the depth is 2: Android calls `xemu_set_submit_frames()` with the pref before `qemu_init`. Every run
logs `submit frames: 2`. accuracy804 NOTES section 17 recorded `submit_frames` = 2 from the dump sessions. So
each rotation waits for the command buffer one finish back, not two.

The frametrace columns of the same probe runs, cold vs warm, ms per frame:
- PFIFO `p_fence` is 6.14 / 6.27 cold against 2.39 / 2.17 warm. All of it is `p_c_rep`, so every PFIFO fence
  wait happens inside process_pending_reports, with pfifo.lock held.
- The guest's lockw is 9.41 / 8.65 cold against 4.06 / 3.80 warm. The part that is not a fence wait (lockw -
  p_c_rep, the lock held while the PFIFO thread parses and dispatches) is about 3.3 cold and 1.7 warm.
- `rp` is 61.0 / 62.1 cold against 27.6 / 27.5 warm.
- The GPU clock is 615 MHz throughout.

The STALLED-finish rate is set by the PFIFO thread's speed. On reportasync1010's REPORT_ASYNC + TEXSCAN base
(2647298, perflog), cold p_c_rep was 1.44 ms per frame and lockw 5.36. DRAWREC and the uniform switches make
the PFIFO thread faster, so it catches up with the guest more often, takes more STALLED finishes, and waits
more often on the ring. The six-switch base shows p_c_rep 6.1 and lockw 9.4.

Already priced, not repeated here: removing the STALLED submit (`HAKUX_STALLFIN=reports`, gpunonrender: Simpsons
30.3 -> 25.8 fps) and releasing pfifo.lock across the finish (`HAKUX_PFIFOWAIT`, pfifowait1009: lost fps and
moved Stencil). In both, the wait moved to the next consumer of the GPU's result. A third ring slot removes the
consumer instead: the next slot to reuse is the one submitted two finishes back.

## 3. Render passes, cold vs warm (older perflog run 2647298, before the switches)

The cold phase runs from the end of loading to about 6 s past the mark (the intro cinematic and the countdown).

| | cold | after it | warm |
|---|---|---|---|
| render passes/frame | ~70 | ~33 | 26.5 |
| `srf` breaks/frame (surface switch, surface.c rp_break_surface) | 56-61 | | |
| S2T copies/frame | 48-54 | | |
| PGen / SGen (pipeline / shader creation) | 0 | 0 | 0 |
| surface creations | 0 | | |

The extra passes are render-target switches with surface-to-texture copies. The guest draws them: the cold frames
show rain streaks and a dark sky, which later frames do not. Nothing is created: no pipelines, shaders or surfaces.
So the 2.6x is the guest's scene (weather and intro effects), not a renderer first-use cost. The GPU is
under-used at 12-16 ms a frame. The step 1 census runs below re-measure this on the six-switch base.

## 4. The remedy built: `HAKUX_SUBMIT_FRAMES=N`

In draw.c, `xemu_set_submit_frames()`: when `HAKUX_SUBMIT_FRAMES` is 1..`NUM_SUBMIT_FRAMES`, it overrides the
pref. It logs `[coldstart1010] submit_frames=N (HAKUX_SUBMIT_FRAMES; pref P)` once per set. When unset or out of
range, the pref decides as before, so it is inert when off. Android calls the setter before `qemu_init`, so
buffer_init and the command ring both see the overridden depth.

Depth 3 is the shipped remedy as a player would get it from the pref, so it carries buffer.c's depth-3 sizing:

- a 128 MB uniform buffer instead of 64;
- larger per-frame staging caps (on the Nova, from the memory budget: idx 30, vtx 128, uni 92, stg 184 MB, against
  16/64/64/128 at depth 2).

All three slots are allocated at either depth. The B arm therefore changes depth and staging sizes together. The
`[probe1010]` blocking-rotation count separates the depth effect, and buffer_init's `(3 frames, ...)` line confirms
the sizing.

If depth 3 wins, the player-facing change is the pref default in `xemu_android.cpp` (2 to 3). That file is
fastpaths1010's, so this lane does not touch it.

**The app disagrees with itself about the default.** Three places hold one:
- the settings screen's: 3 (`SettingsActivity.kt`: `intDefaults` `"submit_frames" to 3`, and the picker's
  `setupIntPicker(..., "submit_frames", 3, ...)`);
- the native one: 2 (`xemu_android.cpp:1188`, `GetPrefInt(..., "submit_frames", 2)`);
- the per-game screen's: 2 (`PerGameSettingsActivity.kt`, `globalValue("submit_frames", "2", ...)`).

History:
- 5a047fd645 (2026-03-23) set all of them to 2, with the comment "Triple buffering tanks performance" and no
  measurement.
- Two days later, f534b0bb51 ("vk: triple-buffer frame slots and batch redundant stalls") raised
  `NUM_SUBMIT_FRAMES` to 3 "to reduce fence back-pressure during scene transitions". It restored 3 as the
  settings UI's default, but not the native `GetPrefInt` default.

So a player who never saves the setting runs depth 2, the depth the later commit meant to replace. The settings
screen still shows "Triple (3)" for that player: `setupIntPicker` labels the button from `pgInt(key, 3)` when the
pref is unset.

On desktop the setter is never called, and the default there is already 3.

## 5. The A/B, registered

`docs/testing/predictions/coldstart1010-depth.json` (sha256 37d06242...). Both refs are 786f82d4bb. A runs the
six switches with `HAKUX_PROBE_WAITS=1`; B adds `HAKUX_SUBMIT_FRAMES=3`. Plain build, 3 runs per arm, queued
A B B A A B. The judge is `coldread.py` (this directory). It reuses postput1010's ppread.py for pace and
validity, and drawrec1010's proberead.py for the `[probe1010]` lines.

| leg | rule | P |
|---|---|---|
| K | cold B <= 34.5 ms, or cold v2 share up >= 15 points | ~35 % |
| C | cold B - A <= -1.0 ms | ~65 % |
| W | warm countdown B - A <= +0.3 ms | ~85 % |
| G | post-GO B - A <= +0.3 ms | ~85 % |
| M | cold ms/frame blocked in the rotation wait, B <= 0.5 x A | ~70 % |

The reader run on drawrec1010's probe base (4030728, 4034875; same configuration as A, older master), without
a prediction:

| run | cold 1 | warm | post | cold v2 | cold rot/f | blk/f | ms blk/f | warm ms blk/f |
|---|---|---|---|---|---|---|---|---|
| 4030728 | 39.4 | 34.3 | 33.5 | 62 % | 3.78 | 1.22 | 4.16 | 1.42 |
| 4034875 | 37.9 | 34.1 | 33.6 | 50 % | 3.92 | 1.23 | 4.39 | 1.28 |

## 6. Step 1 census: cold start 1 against the warm countdown (six switches, ref 786f82d4bb)

Runs: 1-1791695413-coldstart1010-2905497 and 1-1791695414-coldstart1010-2905728. Configuration:
- perflog build, six switches, `HAKUX_FRAMETRACE=1 HAKUX_PROBE_WAITS=1`;
- read with `census.py` (this directory), window `mark` -2 .. +1.5 s; `[probe1010]` -4 .. +3.5 s.

Validity:
- 12/12 marks in both runs; 12 and 11 valid starts (run 2 dropped go3: `pad.sh axis HATX` timed out);
- no boot input failure;
- the g11 frames show the car moving (s1 33 mph, s12 66 mph);
- `submit frames: 2` and `(2 frames` logged.

Pace: cold start 1 42.0 / 43.4 ms, warm 34.6 / 34.4. Values are the mean of the two runs.

**PFIFO thread, ms per frame.** Schedstat (frametrace) and the phase timers. `busy` = P - pidle.

| | cold | warm | cold - warm |
|---|---|---|---|
| recording (phase Draw) | 11.53 | 9.14 | +2.39 |
| finishes (phase Fin) | 2.03 | 2.21 | -0.18 |
| ... of which fence waits (Fen) / submit (Sub) | 1.85 / 0.13 | 2.00 / 0.15 | |
| ring fence waits: rotation, `[probe1010]` ms blocked (inside Fen) | 0.83 | 0.30 | +0.53 |
| ring fence waits inside process_pending_reports, pfifo.lock held (`p_c_rep`) | 0.96 | 0.41 | +0.55 |
| lock waits on this thread (hakuX-cpu Pull Lk) | 0.02 | 0.01 | 0 |
| pipeline and shader creation (phase Shd; `[shd413]` 0.02 creates/frame, 0.00 ms) | 0.00 | 0.00 | 0 |
| texture uploads (phase Tex; xemu-work TexU 0) | 0.00 | 0.00 | 0 |
| surface uploads, downloads and S2T (phase Surf) | 2.53 | 1.67 | +0.86 |
| untimed (busy - Draw - Fin - Surf - Tex - Shd) | 14.94 | 10.73 | +4.21 |
| busy (p_run 27.64 / 22.40 + p_rq 1.16 / 0.73 + fence and other blocking 2.22 / 0.61) | 31.02 | 23.74 | +7.28 |
| idle, waiting for the guest (pidle) | 13.23 | 11.25 | +1.98 |
| **P, the frame (= busy + idle)** | **44.25** | **34.99** | **+9.26** |

**Alongside, per frame.**

| | cold | warm |
|---|---|---|
| GPU busy (frametrace `gpu`) | 16.35 | 12.83 |
| render passes (frametrace `rp`; rpbrk 60-flip count) | 51.8 (70.3) | 27.0 (26.9) |
| ... `srf` breaks (surface switch) / `clr` / `qry` / `fin` / `nd` | 57.1 / 6.5 / 2.0 / 1.7 / 3.0 | 14.9 / 5.6 / 2.0 / 1.4 / 3.1 |
| S2T (surface-to-texture) / PGen / SGen / TexU / Clr (xemu-work) | 48 / 0 / 0 / 0 / 7.0 | 8.1 / 0 / 0 / 0 / 6.1 |
| draws (`[probe1010]`) | 1713 | 1339 |
| vCPU on CPU (`v_run`) | 36.25 | 30.15 |
| guest work (ftbuckets) | 27.55 | 21.70 |
| guest lockw (DMA_PUT store waiting on pfifo.lock) | 4.41 | 1.95 |
| guest busy (work + all v_blk) | 34.25 | 26.0 |
| frames past 2 VBLANKs, either thread (without lockw) | 59 % (33 %) | 9 % (5 %) |

**What sums and what does not.**
- The frametrace rows sum to P exactly: they are the PFIFO thread's schedstat.
- The phase timers cover 16.1 ms of the cold 31.0 busy, and 13.0 of the warm 23.7.
- The untimed rest (14.9 cold, 10.7 warm) is code outside every phase timer: the pusher's pushbuffer fetch,
  method dispatch for state methods (transform constants, inline data) and report handling, plus the perflog
  build's own counters. It scales with the draw count: 1.28x the draws cold, 1.39x the untimed.
- The two fence rows overlap Fen and each other: a rotation wait inside a STALLED finish counts in all three.

**Instrument cost.** This build is perflog. The PFIFO thread's `p_run` is 27.6 cold and 22.4 warm here,
against 19.3 and 16.8 in drawrec1010's plain probe base (section 1; older ref bf43e8c4ef). The cold pace is 42-43
ms here against 37.9-39.4 plain.

The slower PFIFO thread changes the regime this lane is about:
- it catches up with the guest less often, so it takes 1.2-1.3 rotations a frame instead of 3.8, and blocks
  0.8 ms a frame instead of 4.2;
- `p_c_rep` is 1.0 instead of 6.1, and the guest's lockw is 4.4 instead of 9.0.

So the perflog census says where the PFIFO thread's time goes. Only the plain runs (section 1, and the A arm
of the A/B) measure the lock waits a player gets. The A arm runs plain on this ref, so it also gives the
instrument's cost on the pace.

**Where the cold excess is, in the plain build** (section 1). Cold start 1 runs 38.7 ms against 34.2 warm.
The guest's busy time is 38.5 against 28.2:
- guest work is +5.1 ms. This is the guest's own cold work, and the renderer cannot remove it.
- lockw is +5.35 ms. This is the renderer's share: fence waits and a longer parse under pfifo.lock.

Without lockw the cold guest is busy 29.1 ms, under 33.3. The share of frames past 2 VBLANKs falls from 60 % to
24 %. So the renderer's share is the larger lever at the cold start, and step 2 goes ahead.

**Why the cold start runs 2.6x the render passes.**
- The extra passes are `srf` breaks: 57 against 15 a frame. Each is a render-target switch, with 48 against 8
  surface-to-texture copies a frame (S2T: the guest renders to a surface, then samples it).
- No pipeline or shader is created (PGen, SGen and `[shd413]` all 0), no texture is uploaded (TexU 0), and
  no surface is created. Clears are +0.9 a frame.
- The frames say why. At `mark gameplay` in both runs (`route-frames/*-gameplay.png`), the first race runs in
  rain, with streaks and a wet, reflective road. The restart at `go2` is dry, with the same street, cars and
  camera.
- So the 2.6x passes, the 1.28x draws and most of the +5 ms of guest work are the game's weather on the first
  start. That is the scene, not a renderer first-use cost. The renderer pays for it through recording (+2.4),
  Surf (+0.9), untimed method work (+4.2) and the GPU (+3.5, still well under the frame).

## 7. Depth A/B verdict: FAIL on K, C/W/G/M pass (coldstart1010-depth.json)

Runs, in queue order A B B A A B. B1 (1-1791697259-coldstart1010-3142391) was void: a boot `press A 120`
took 10.3 s before `mark gameplay` on a host adb liveness failure (WSL `accept4` 110), so it was replaced by
one rerun, 1-1791698423-coldstart1010-3252234.

| run | arm | cold 1 | warm | post-GO | cold v2 | cold rot/f | blk/f | cold ms blk/f | warm ms blk/f | shader cache |
|---|---|---|---|---|---|---|---|---|---|---|
| 1-1791697258-coldstart1010-3142274 | A | 38.3 | 33.8 | 33.4 | 57 % | 3.84 | 1.29 | 3.01 | 0.63 | cleared |
| 1-1791698423-coldstart1010-3252234 | B | 36.4 | 33.6 | 33.4 | 62 % | 1.83 | 0.18 | 0.69 | 0.09 | cleared |
| 1-1791697260-coldstart1010-3142465 | B | 37.0 | 33.7 | 33.4 | 47 % | 2.22 | 0.31 | 1.06 | 0.06 | kept |
| 1-1791697260-coldstart1010-3142523 | A | 37.7 | 33.8 | 33.4 | 60 % | 2.61 | 0.67 | 2.84 | 0.44 | kept |
| 1-1791697261-coldstart1010-3142581 | A | 37.8 | 33.7 | 33.4 | 62 % | 2.16 | 0.60 | 2.90 | 0.38 | cleared |
| 1-1791697262-coldstart1010-3142647 | B | 35.8 | 33.6 | 33.4 | 63 % | 2.12 | 0.23 | 0.99 | 0.16 | kept |
| **mean A** | | **37.93** | **33.75** | **33.40** | 59.4 % | | | **2.91** | | |
| **mean B** | | **36.42** | **33.63** | **33.39** | 57.5 % | | | **0.92** | | |

| leg | rule | measured | |
|---|---|---|---|
| V | every run valid, switch lines, depth lines, 12 marks, g11 frames | all six; the car moves in every g11 frame (24-96 mph, by eye) | PASS |
| K | cold B <= 34.5, or cold v2 B - A >= +15 | 36.42; v2 -1.9 points | **FAIL** |
| C | cold B - A <= -1.0 | **-1.51** | PASS |
| W | warm B - A <= +0.3 | -0.12 | PASS |
| G | post-GO B - A <= +0.3 | -0.01 | PASS |
| M | cold ms/f blocked in rotation, B <= 0.5 x A | 0.92 against 2.91 (0.32 x) | PASS |

What it says:
- Depth 3 does what the mechanism said. Blocking rotations at the cold start fall from 0.85 to 0.24 a frame,
  and ms blocked from 2.91 to 0.92. The cold start is 1.5 ms faster, and the warm countdown and post-GO do not
  move (both arms are at the 33.4 floor after GO).
- It does not reach the brief's target alone: 36.4 against 34.5.
- The v2 share is the wrong instrument for this gain. The cold window holds one or two 60-flip pace lines, and
  the game presents a catch-up frame after one VBLANK when a frame runs long. Depth 3 moves frames from three
  VBLANKs to one: v3 18.8 to 16.3 a line, v1 4.8 to 7.3. The v2 count does not change (A 28-40, B 28-38).
  So K's v2 leg cannot see a pace gain of this shape.
- The shader cache does not confound the result. It was cleared before A1, A3 and B1' (each followed a
  different APK on the device) and kept before the rest. A cleared 38.3 / 37.8 against kept 37.7; B cleared
  36.4 against kept 37.0 / 35.8.

The player-facing change is the native pref default (`xemu_android.cpp:1188`, 2 to 3), which makes the native
default match the settings screen's. That file is fastpaths1010's (section 4). A pixel leg is not needed:
depth changes only which slot's command buffer and staging a finish records into, not what any draw draws.

## 8. Stack A/B, posted store on, depth 2 vs 3 (coldstart1010-stack.json): in progress

Runs so far:

| run | arm | cold 1 | warm | post-GO | cold ms blk/f | note |
|---|---|---|---|---|---|---|
| 1-1791702188-coldstart1010-3912216 | A | 35.7 | 33.6 | 33.4 | 2.56 | |
| 1-1791702189-coldstart1010-3912403 | B | - | - | - | - | **void** (below) |
| 1-1791703256-coldstart1010-3982841 | B | 35.9 | 33.6 | 33.3 | 0.11 | |
| 1-1791703257-coldstart1010-3982899 | A | 35.8 | 33.5 | 33.4 | 2.32 | |

Stack B1 is void. At the Quick Race menu (`qr-custom`) the route's one `HATX` right, held 194 ms, moved the
cursor two items, onto Split Screen. The route then drove nothing: every start's frames show the split-screen
"select player order" screen, and the pace is 16.7 ms throughout. This is a menu input slip, not the arm's
effect: B2, with the same environment, went through the menu correctly. Its one rerun is
1-1791703833-coldstart1010-4017651. A3 and B3 are queued after it.

Residual census, queued after the stack: two plain runs of the stacked configuration (six switches, posted
store, depth 3) with `HAKUX_FRAMETRACE=1` (1-1791704357-coldstart1010-4044114, 1-1791704358-coldstart1010-4044180).
They measure what the cold start still waits on with both on. The comparison is drawrec1010's plain depth-2 runs
(4030728, 4034875), read by `census.py`: cold guest work 26.8 / 26.1 against 21.7 / 21.5 warm, lockw 9.4 / 8.7,
guest idle 3.5 / 3.1.
