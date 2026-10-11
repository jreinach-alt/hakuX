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
