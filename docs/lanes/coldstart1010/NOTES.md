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

## 8. Stack A/B verdict, posted store on, depth 2 vs 3 (coldstart1010-stack.json): FAIL on K by 0.29 ms, C/W/G/M pass

| run | arm | cold 1 | warm | post-GO | cold v2 | cold ms blk/f | valid | shader cache |
|---|---|---|---|---|---|---|---|---|
| 1-1791702188-coldstart1010-3912216 | A | 35.7 | 33.6 | 33.4 | 74 % | 2.56 | 12/12 | kept |
| 1-1791703833-coldstart1010-4017651 (B1') | B | 33.8 | 33.6 | 33.4 | 82 % | 0.21 | 10/12 | cleared |
| 1-1791703256-coldstart1010-3982841 | B | 35.9 | 33.6 | 33.3 | 63 % | 0.11 | 12/12 | kept |
| 1-1791703257-coldstart1010-3982899 | A | 35.8 | 33.5 | 33.4 | 69 % | 2.32 | 12/12 | kept |
| 1-1791704340-coldstart1010-4043569 | A | 37.2 | 33.6 | 33.4 | 77 % | 3.08 | 12/12 | cleared |
| 1-1791704340-coldstart1010-4043654 | B | 34.7 | 33.6 | 33.4 | 64 % | 0.28 | 12/12 | kept |
| **mean A** | | **36.28** | **33.59** | **33.36** | 73.3 % | **2.66** | | |
| **mean B** | | **34.79** | **33.58** | **33.36** | 69.7 % | **0.20** | | |

| leg | rule | measured | |
|---|---|---|---|
| V | as section 7, plus `[postput] on` on every run | all six runs; the g11 frames by eye below | PASS |
| K | cold B <= 34.5, or cold v2 B - A >= +15 | 34.79; v2 -3.6 points | **FAIL** (0.29 ms short) |
| C | cold B - A <= -0.5 | **-1.49** | PASS |
| W | warm B - A <= +0.3 | -0.01 | PASS |
| G | post-GO B - A <= +0.3 | -0.00 | PASS |
| M | cold ms/f blocked in rotation, B <= 0.5 x A | 0.20 against 2.66 (0.08 x) | PASS |

Validity, run by run:
- **B1 (1-1791702189-coldstart1010-3912403) is void.** At the Quick Race menu (`qr-custom`), the route's one
  `HATX` right was held 194 ms and moved the cursor two items, onto Split Screen. The route then drove nothing:
  every start's frames show the split-screen "select player order" screen, and the pace is 16.7 ms throughout.
  This is a menu input slip, not the arm: B2 ran the same environment through the menu correctly. One rerun,
  B1'.
- **B1' is valid at the cold start.** Its gameplay frame shows GO, and s1-g11 shows the car moving. Two host adb
  hangs (WSL `accept4` 110) made two route inputs fail, so the reader drops go4 and go9, leaving 10 valid starts
  (the minimum is 10). By eye, start 5 also failed: s4-g11 shows race 3 still running (go4's OK never landed),
  and s5-g11 shows the restart dialog, not a race. The reader keeps go5. Dropping it moves this run's warm figure
  by +0.03 ms and its post-GO by 0.00, so W and G stand either way.
- A3 had one adb hang that broke no route input (12/12). In every other g11 frame of the six runs, the car moves
  (23-89 mph).

**The two remedies add.** All four configurations are on one binary (786f82d4bb, apk 52aa370cd4d3, plain
build), each 3 runs. Within each A/B the arms are interleaved; across the two A/Bs the batches are not (the
depth A/B ran 22:41-00:11 PDT, the stack 00:11-01:32).

| configuration | cold 1 | vs six | warm | post-GO | cold ms blocked in rotation /f |
|---|---|---|---|---|---|
| six switches (depth 2) | 37.93 | | 33.75 | 33.40 | 2.91 |
| + depth 3 | 36.42 | -1.51 | 33.63 | 33.39 | 0.92 |
| + posted store (depth 2) | 36.28 | -1.65 | 33.59 | 33.36 | 2.66 |
| + posted store + depth 3 | **34.79** | **-3.14** | 33.58 | 33.36 | 0.20 |

- Depth 3 gives the same -1.5 ms with or without the posted store. The posted store gives -1.65 here, against
  postput1010's -2.17 on its own pair.
- So the prediction's mechanism was wrong in one place. It held that with the store posted, depth 3 would help
  only where the PFIFO thread's own lateness paces the frame, and put B - A at -0.6. It came out at -1.49.
- That says the PFIFO thread's lateness does pace the cold frame once the guest stops waiting on the lock. The
  2.46 ms a frame that depth 3 removes from the PFIFO thread's rotation waits comes back as 1.49 ms of pace.
- Warm countdown and post-GO do not move in either A/B: both run at the 33.3 floor already.

The point estimate was B 35.0 (34.79 measured) and A 35.6 (36.28 measured). The posted store's gain was smaller
on this ref than in postput1010, and depth 3's gain on top of it larger.

What the cold start still waits on with both on: section 9.

## 9. Residual census: the stacked configuration against the depth-2 base

Runs:
- Stacked: two plain runs of six switches, posted store and depth 3, with `HAKUX_FRAMETRACE=1 HAKUX_PROBE_WAITS=1`
  (1-1791704357-coldstart1010-4044114, 1-1791704358-coldstart1010-4044180; ref 786f82d4bb). Both runs are 12/12
  valid, log `[postput] on, skew bound mode 0`, and have no boot input failure. In the g11 frames the car moves
  (s1 39 mph in the second).
- Base: drawrec1010's two plain runs of the same six switches with the same instruments, at depth 2 without the
  posted store (1-1791672296-drawrec1010-4030728, 1-1791672308-drawrec1010-4034875; older ref bf43e8c4ef).

All four runs are read by `census.py` with the window at `mark` -2 .. +1.5 s. Each cell is run 1 / run 2, in ms
per frame unless marked.

| | base, cold | stacked, cold | stacked, warm |
|---|---|---|---|
| pace, cold start 1 or warm countdown (`coldread.py`) | 39.4 / 37.9 | 34.2 / 34.5 | 33.5 / 33.5 |
| P (frametrace, PFIFO thread's frame) | 41.96 / 40.11 | 34.85 / 35.27 | 33.31 / 33.37 |
| PFIFO `p_run` | 19.61 / 18.94 | 19.93 / 20.02 | 17.81 / 17.81 |
| PFIFO fence waits `p_fence` (inside process_pending_reports, pfifo.lock held: `p_c_rep`) | 6.14 / 6.27 (6.14 / 6.13) | 0.22 / 0.03 (0.19 / 0.00) | 0.16 / 0.15 (0.02 / 0.01) |
| PFIFO busy; frames past 2 VBLANKs | 26.2 / 25.6; 19 / 15 % | 21.9 / 22.8; 0 / 1 % | 16.4 / 16.4; 0 % |
| PFIFO idle, waiting for the guest (`pidle`) | 15.73 / 14.51 | 12.93 / 12.43 | 16.89 / 16.94 |
| GPU busy (`gpu`) | 12.45 / 11.82 | 10.70 / 10.89 | 8.32 / 8.39 |
| render passes (`rp`) | 61.0 / 62.1 | 52.5 / 51.4 | 26.8 / 26.8 |
| vCPU on CPU (`v_run`) | 30.1 / 28.9 | 29.8 / 30.5 | 30.2 / 30.2 |
| guest work | 26.8 / 26.1 | 23.6 / 23.8 | 19.9 / 19.8 |
| guest lockw (pfifo.lock, `lock_wait_ns`) | **9.41 / 8.65** | **2.19 / 2.35** | 0.72 / 0.81 |
| vCPU pgraph.lock waits, holder PFIFO (`vh_*`) | 0.84 / 0.81 | 0.74 / 0.76 | 0.87 / 0.79 |
| guest idle (`gidle`) | 3.5 / 3.1 | 6.3 / 6.8 | 10.3 / 10.5 |
| guest busy (without lockw) | 38.5 (29.1) / 37.0 (28.3) | 28.5 (26.3) / 28.5 (26.2) | 23.0 (22.3) / 22.9 (22.1) |
| frames past 2 VBLANKs, either thread (without lockw) | 60 (24) / 52 (23) % | **24 (5) / 27 (4) %** | 3 (1) / 2 (1) % |

The two stacked runs agree with each other on every row. Their cold paces, 34.2 and 34.5, are not part of the
registered verdict; they sit inside the B arm's range of 33.8 to 35.9.

What it says:
- **The renderer no longer paces the cold frame.**
  - The PFIFO thread runs past 2 VBLANKs on 0-1 % of cold frames, against 15-19 % in the base.
  - The fence waits it made under pfifo.lock are gone: `p_c_rep` was 6.1, now 0.0-0.2.
  - The GPU is busy 10.8 ms of a 33.3 ms frame.
  - The 2x render passes (52 against 27; the rain's `srf` breaks and surface-to-texture copies, section 6) cost
    +2.1 ms of PFIFO run and +2.4 ms of GPU, and neither is on the critical path any more.
- **What is left is the guest waiting for pfifo.lock.**
  - lockw is 2.2-2.35 ms a frame cold, against 0.7-0.8 warm and 8.7-9.4 in the base.
  - Without it, the cold guest is busy 26.2 ms and only 4-5 % of frames run past 2 VBLANKs. With it, 24-27 % do.
    Those frames are the gap between the cold start's ~34.5 and the warm countdown's 33.5.
- **The guest's own cold work is +3.9 ms** (23.7 against 19.85). That is the scene (section 6), and it fits:
  26.2 ms busy without lockw is under the 33.3 ms frame.

**Where that lockw is counted.** `lock_wait_ns` is added in exactly two places (`git grep lock_wait_ns`):
- `pfifo_post_kick` (pfifo.c:1646-1654). After a posted DMA_PUT store, if `parked` reads true, the vCPU takes
  pfifo.lock to broadcast `fifo_cond`. If the PFIFO thread has woken and re-taken the lock by then, the vCPU waits
  out whatever the PFIFO thread does next while it holds the lock.
- `user_write`'s locked branch (user.c:108-113). Every USER store that is not a postable DMA_PUT (REF, GET) takes
  the lock and waits for it.

With the posted store on and skew bound mode 0, a DMA_PUT store never waits at its trylock. Neither site starts
a frametrace wait, so frametrace books no holder for this lockw. Profile.h:336 calls it UNATTR. The `vh_*` split,
0.74-0.76 ms, is a different wait, on pgraph.lock, and it is flat from cold to warm.

These runs cannot say which of the two sites holds the 2.2 ms, or what the PFIFO thread was doing while it held
the lock. Section 10 prices the remedy with that uncertainty in P.

## 10. Remedies priced, and the ranked next step

The expected win (E) is P x win, in ms per frame at cold start 1. They are ranked by E.

| # | remedy | win | P | E | cost | evidence | files |
|---|---|---|---|---|---|---|---|
| 1 | posted DMA_PUT store on by default (`HAKUX_POSTED_PUT`) | 1.65 | 0.9 | 1.5 | a default flip; the switch exists | sections 7 and 8: the A arms, depth 2, -1.65, 3 runs each; postput1010's own pair -2.17 | pfifo.c, user.c (postput1010's switch) |
| 2 | submit ring depth 3 as the Android native default | 1.5 | 0.9 | 1.35 | one line, `xemu_android.cpp:1188`, pref 2 to 3, which matches the settings screen | two registered A/Bs, -1.51 and -1.49, the second with #1 on | Android (fastpaths1010's) |
| 3 | a pfifo.lock-free wake for the posted store, plus the same for the remaining USER stores if they hold the wait | ~1.0, from about 34.6 to the warm countdown's 33.5-33.9 | 0.5 | 0.5 | medium: the PFIFO thread parks on an event outside pfifo.lock, every `fifo_cond` waker sets it (`pfifo_kick` and its callers in pgraph.c and surface.c, `nv2a_lock_fifo`, `nv2a_exitfn`), and the no-lost-wakeup argument is written down | section 9: lockw 2.2-2.35 ms; slow cold frames 24-27 % with it and 4-5 % without. P is 0.5 because which site holds it is not measured | pfifo.c, user.c (not this lane's) |
| 4 | the guest's cold work (rain) | - | - | 0 for the renderer | - | +3.9 ms, and it fits in the frame (section 9) | not the renderer |
| 5 | fewer render passes at the cold start (`srf` / S2T) | < 0.2 | 0.3 | < 0.1 | large: the scene asks for them | the PFIFO thread is past 2 VBLANKs on 0-1 % of frames, and the GPU is busy 10.8 of 33.3 ms | surface.c |
| 6 | `tlbmap.mbox` vertex walks | <= 0.2 of PFIFO run | 0.3 | ~0 | medium | it is PFIFO run, and that no longer paces (section 9) | draw.c |
| 7 | first-use pipeline creation | 0 | - | 0 | - | `[shd413]` 0.02 creates a frame, 0.00 ms (section 6) | - |

#1 and #2 add. Together they measured -3.14 ms (37.93 to 34.79), on one binary, 3 runs per configuration.

**Ranked next step.**
1. **lane.local / fastpaths1010: make #1 and #2 the player's defaults.**
   - The native `submit_frames` default goes from 2 to 3. It is the one-line change at `xemu_android.cpp:1188`,
     and with it the native default matches what the settings screen already shows.
   - The posted store goes on by default. postput1010 kept it opt-in because the PFIFO thread's run did not fall.
     Section 8 shows that with depth 3 the pair moves the cold start by -3.14 ms, and neither moves warm or
     post-GO. Whether it is safe on the other titles is postput1010's audit, not something this lane measured.
   - `HAKUX_SUBMIT_FRAMES` (this PR) stays as the A/B override.
2. **A lane on pfifo.c and user.c for #3.**
   - First a cheap step that decides which site holds the wait:
     - give each of the two `lock_wait_ns` sites its own counter;
     - wrap each in a frametrace wait with holder `HAKUX_FT_PFIFO`, so that `vh_*` books what the PFIFO thread
       was doing while it held the lock;
     - run two plain runs of the stacked configuration.
   - If it is the post_kick site, build the lock-free wake behind a default-off switch. Register it against the
     stacked configuration, with K at cold <= 34.5.
   - Expected: cold start 1 at about 33.6-33.9.

**What the next lane should not repeat.**
- Do not judge depth or the posted store by the cold v2 share. The game presents a catch-up frame after one
  VBLANK, so a pace gain moves frames from v3 to v1 (section 7).
- Do not chase pipeline creation, texture uploads or the pass count for this window. All three were measured
  at or near zero on the critical path (sections 6 and 9).
- Perflog builds slow the PFIFO thread enough to change the regime (section 6). Measure lock and fence waits on
  plain builds with `HAKUX_FRAMETRACE=1`.
