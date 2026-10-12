# What has to be reworked for NFS Most Wanted's race start to hold 30 fps (#433, 0.5)

lane.nfs30plan1010, 2026-10-10. Figures are from this lane's runs `1-1791649387-nfs30plan1010-2138210` and
`1-1791649388-nfs30plan1010-2138879` (instrumented build), lane.nfsframe1010's `1-1791649039-nfsframe1010-2037292`
and `1-1791649724-nfsframe1010-2219502` (the plain build, same route), and lane.texscan1010's
`1-1791648919-texscan1010-2004607` (census), unless a source is named. NOTES.md section 5 holds the readings and the
readers. A figure with no source is marked **(assumption)**.

**Revised 10-10 (attempt 2) on two results:** the placement probe (NOTES 5.6: freeing the X3 lengthened the frame
2-4 ms, F failed; step 4 is dropped) and texscan1010's NFS A/B (NOTES 5.7: the GPU-side copy ALONE costs +2.6 to
+7 ms/frame; the structural fact in section 3 is confirmed and steps 1 and 2 are one step, landed in the order
2 then 1). Section numbers are unchanged; other lanes cite them.

## 0. Owner summary

**The frame is not slow in one place. It is slow because one thread, the PFIFO thread, does everything in series:
it reads the guest's commands, records every draw into Vulkan, and then stops three times a frame to wait for the
GPU.** At the race start that thread accounts for the whole period: the GPU is busy 20-30% of the time, the guest
CPU is idle half the time, and the frame is 56-62 ms cold, 41-42 ms warm, on the build players run.

What a heavy cold-start frame (plain build, ~59 ms) is made of, on that one thread:

| block | ms (plain build, see section 2 for how these were derived) | can it go? |
|---|---|---|
| recording ~1,900 draws into Vulkan (12 us each) + parsing the guest's commands + surface work | 24-30 | shrink by a third with state/descriptor work; move off the thread entirely with a recorder thread |
| waiting for the GPU to finish and copy back the car's environment-map faces, 1.5 times a frame | 10-17 | **yes, entirely**: copy on the GPU (lane.texscan1010's switch, queued now) |
| waiting under the FIFO lock for the GPU's occlusion-query results | 4-7 | yes: write the result when the GPU is done, instead of waiting for it |
| waiting for the next emulated VBLANK after the frame is done (frames are quantized to 16.7 ms steps) | 0-12 | not removable; it is why 34 ms of work becomes a 50 ms frame. The work must fit in 33 ms every frame |

The two GPU waits are one pool, not two: the GPU only receives work at those stops, so removing the
environment-map stops alone makes the occlusion-query stop wait for the whole frame's GPU work instead.
**texscan1010's A/B measured exactly that (NOTES 5.7): with the copy on and nothing else, the frame got 2.6 ms
LONGER over the start and 7 ms longer at the countdown** (the 10.8 ms of face waits left, 13.7 ms arrived at the
query fence, and the GPU did 3-5 ms more work per frame on the copy route). They have to go together, and the
order is:

Step numbers are kept as first written (other lanes cite them); the LANDING order is 2, then 1.

1. **The GPU-side environment-map copy (texscan1010): built, ready, default-off; it lands on top of step 2,
   never alone.** The pair's A/B (reportasync1010's step 5) decides its default. Together: warm start and
   post-GO at 30 fps (every frame in 2 vblanks), cold start 25-28 (model). P 0.7 that the copy is correct (its
   pixel leg), **P 0.5 that the pair reaches the warm-start model**, lowered from 0.7 because the copy route
   costs the GPU 3-5 ms/frame that the model had not priced (NOTES 5.7).
2. **Stop waiting for occlusion-query results on the FIFO thread** (lane `reportasync1010`, dispatched 10-10,
   pilot pair queued): the GPU writes the report when it is done, as the hardware does. Alone: 50-55 cold /
   37-38 warm (model). P 0.6. **This is the step that lands first.**
3. **Cut the per-draw recording cost** (lane `drawrec1010`, dispatched 10-10, census run on the Nova): first a
   census of what changes between consecutive draws, then descriptor/uniform/pipeline-state caching; the drastic
   form is a recorder thread so the FIFO thread only parses. This is what holds 30 at the cold start and on
   heavier tracks. P 0.5 for -30%, P 0.4 for the recorder thread, 10-25 lane-days.
4. **Thread placement: dropped.** The probe (HAKUX_IDLE_HALT=1, `nfs30plan1010-idlehalt.json`, NOTES 5.6) freed
   the X3 for a third of wall time and the FIFO thread's frame grew 2-4 ms. Its brief is not dispatched.
5. **GPU work and the guest JIT are not on the path** at this scene (GPU 13-22 ms of a 33 ms budget; the guest
   needs 24-29 ms of vCPU time and spends the rest spinning), so a JIT rewrite and a driver fork are priced in
   section 6 but not scheduled. They become the path only after steps 1-3, on heavier scenes. One change from
   the A/B: with the copy on the GPU is 18 ms/frame at the cold countdown (instr.), so the GPU pass work
   (`gpupass1010`) moves up to "with the pair" from "after".

What to stop: nothing that is running. texscan1010 is step 1's switch (it covers all six cube faces, not only the
range scan); it went ready default-off and must NOT go default-on alone. nfsframe1010's two plain runs are the
baseline arm; it is ready. perdrawon1010 is folded; its -1.8 us/draw is real and small, and its switches go
default-on as a part of step 3, not as a fix. forzasurf1010 is off NFS's path (Forza's surface wait is a
different call) and should finish for Forza's sake only. Idle halt: NFS gets no title-table entry for it (the
probe read +2-4 ms/frame at this scene).

Risk, in one line: steps 1 and 2 remove waits, so they are low-risk to pixels (the bytes are the same) and
medium-risk to timing (a guest that reads the report or the face before the GPU is done). Step 3 touches the
hottest code in the renderer and is the one that can regress pixels; it goes behind a switch with the 27-suite
pixel disc as the gate.

## 1. What to stop, what to keep (the four NFS lanes)

| lane | verdict | why |
|---|---|---|
| **texscan1010** | **done; ready, default-off. It is step 1's switch, on only with step 2.** | Its census (`1-1791648919`, NOTES section 3 of that lane) shows every synchronous download at the race start is a face of one 128x128 cube environment map: face 0 through the SDL block (30/60 frames), faces 1-5 through the range scan (60+60+60+30+30 per 60 frames), 7.3 ms/frame inside `create_texture` on the perflog build, and `HAKUX_TEXSCAN=1` copies all six on the GPU. This lane's frametrace puts the same waits at 17.3 ms/frame cold, 10.1 warm (NOTES 5.5). **Its A/B (NOTES 5.7, three valid runs; `-2622720` void, a menu): period +2.6 ms over the start, +7 at the countdown; `Sub` 10.8 -> 0.2 and the fence's remainder 4.1 -> 17.8; GPU 13.4 -> 18.0 instr.** The copy works and the wait moved, as section 3 said it would; the switch stays off until reportasync1010's pair. |
| **nfsframe1010** | **ready; no further device time.** | Its runs `1-1791649039`/`1-1791649724` are the plain-build baseline this plan is priced against (and the A arm of the placement probe). Its three questions are answered here: the ~12 ms between `Tot` and the period is PFIFO time outside every phase timer (method parsing, texture-bind bookkeeping, pending-report processing, clock reads; NOTES 5.5), the ~10 ms post-flip idle is the wait for the next VBLANK grid line (section 4.3), and the other 5-6 ms of `Sub` is the two cube-face finishes plus the flip finish's submit (NOTES 5.4-5.5). Its NOTES section 11 says so. |
| **perdrawon1010** | **folded (9fd2608f8f).** | -1.76 us/draw (-17%) on the race start, 18.9-20.9 fps on vs 17.9-20.0 off at the owner's draw counts (its PR.md). Real, and 2-4 ms of a 59 ms frame. Its three switches are on master, default-off (`perdraw_env_flag`, shaders.c:1809), and are part of step 3's baseline; drawrec1010 runs with them on. |
| **forzasurf1010** | **finish for Forza; off NFS's path.** | NFS's surface-to-texture wait is the cube map (above), which `HAKUX_SURFGPU` does not take (`check_surface_to_texture_compatiblity` refuses `shape->cubemap`, texture.c:1402). Its A2/B2 runs decide Forza only. |

## 2. The budget

**Target.** 30 fps on this device is **every frame in 2 emulated VBLANKs** (33.3 ms). The guest's frame loop
waits for the VBLANK interrupt that follows its FLIP_STALL; the kernel's ISR advances the display read index
(`NV_PGRAPH_INCREMENT_READ_3D`, pgraph.c:1232-1240), and only then does the PFIFO puller leave the flip stall
(`is_flip_stall_complete`, pfifo.c:1626). So a frame that needs 34 ms of PFIFO-thread time takes 3 VBLANKs (50
ms, 20 fps), and the adaptive deferral in `nv2a_vblank_timer_cb` (nv2a.c:957-1160) stretches a VBLANK by at most a
few ms for a game that "barely missed". The plain build's countdown histogram (nfsframe1010's two runs, pace
`v2/v3/v4` over the 60-flip windows in [mark-2, mark+1.5]): **v2 49-51%, v3 42-44%, v4 4%**; post-GO v2 58-59%,
v3 37-38%. Half the warm frames are already at 2 VBLANKs. The job is the other half, and the cold start.

**The budget is set against the plain build** (no perflog, no env), because every instrument this lane ran costs
PFIFO-thread time: like-for-like, the first 60-flip window after `mark gameplay` is 61.8 ms/frame plain against
74.9-79.0 instrumented (NOTES 5.5, "Instrument cost"). The owner's 13 fps (brief) was a perflog build on a
downtown track by hand, i.e. this lane's instrumented cold start (74-78 ms), not the plain build's.

| window (route `nfs-mw-quickrace`, 12 starts/run) | plain build (nfsframe1010, 2 runs) | instrumented (this lane, 2 runs) |
|---|---|---|
| cold start 1, countdown [mark-2, mark+1.5] | **56.3 / 58.5 ms** per frame (one 60-flip window each); 61.8 for the window after the mark | 75.5 / 76.3 (frametrace), G 77.7-78.1 (phase) |
| warm restarts, countdown | **41.2-42.4 ms** mean over 14-19 windows (min 34.8, max 58.5) | 56.2-57.1 (go4-12) |
| post-GO [mark+1.5, mark+12] | **40.0 ms** (both runs) | 46.1 |
| guest vCPU work per frame (`[rr425w]` busy) | 27.4 countdown / 24.5 post-GO | 25-28 |

**How the plain-build blocks in section 0 were derived (assumption, stated once).** The instrumented account of
the PFIFO thread is exact for that build (NOTES 5.5). For the plain build: CPU time is scaled by 0.8 (the ratio
of the two builds' periods at the same window, 61.8/77 and 42/56); waits on the GPU (the sd round trips and the
report fence) are kept as measured, since the GPU work they drain is the same; the VBLANK wait is the remainder
to the observed period. The split is not measurable on the plain build by construction (it carries no
instruments), which is why every lane below judges its switch on the plain build's **period and v2/v3/v4
histogram**, not on a phase line.

**What has to come off.** Warm: the v3 frames need ~5-9 ms less PFIFO time (42 -> ~33 with the grid). Cold:
~25-30 ms (56-62 -> 33.3 at p95, since a 2-VBLANK frame rate needs every frame under the line, not the mean).

## 3. The heavy frame, per thread (instrumented build; NOTES 5.5 has the full tables)

Cold start, frames ending in [mark-2, mark+1.5], 46 frames per run; period 75.5 ms; frametrace `cls` pgraph
78-83%; `crit` 61 ms. **The PFIFO thread is the critical path**; its 75.5 ms is:

    38.0 on CPU  +  17.3 sd-finish round trips  +  6.7 report fence  +  12.6 waiting for the VBLANK/guest  +  0.9 runqueue

| thread | on CPU | blocked | what it says |
|---|---|---|---|
| **PFIFO (critical path)** | 38.0: ~23 draw recording (1,860-1,930 draws, 11.9 us/draw: Syn 4.6, Pipe 6.4 of which Sh 4.1, Desc 2.7, Setup 1.4, Mfp 3.9), ~2 surface, ~2 inside finishes, ~10-13 under no timer (method parsing Push 0.7 + Pull 0.65, texture-bind bookkeeping, pending-report processing, perflog clock reads) | 36.6 = 12.6 `pidle` (FIFO empty after the flip: the VBLANK grid) + 6.7 pending-report fence under `pfifo.lock` (site #54, 1.0/frame) + 17.3 unhooked = the two cube-face finishes' `finish_event` waits (1.5/frame) | the whole frame |
| render | not registered (no row); its `vkWaitForFences` in `process_finish` is 16.7 ms at 1.5 calls/frame, booked as `o_fence` | | it waits on the GPU for the PFIFO thread's synchronous finishes; otherwise idle |
| vCPU | 66.6 of which 37.6 is the guest idle loop SPINNING (`HAKUX_IDLE_HALT` off), guest work ~29 | 8.2 (BQL 1.7; 6.5 MMIO/unhooked) | not the path; holds the X3 core 88% of wall (PMU) doing nothing useful for 38 ms/frame |
| main loop | 3.0 | 72.2 idle | not the path |
| GPU | busy 21.7 (cold; 12.8 warm); 69 render passes/frame cold (26.5 warm), 24.9 pass pairs, 20 MB GMEM load + 20 MB store; 615 MHz constant | | not the path, 2.6x the passes at the cold start |
| present | 4.5 VBLANKs/frame cold, 3.4 warm | | the quantization |

Warm (go4-12): 56.2-57.1 = 30.4 on CPU + 10.1 sd round trips + 4.3 report fence + 11.0 VBLANK/guest wait + 0.6.

What no instrument saw (NOTES 5.5): the render thread's own run time; the PFIFO thread's `finish_event` and
`wait_frame_submitted` waits (only as the unhooked remainder); the vCPU's MMIO waits; which core the PFIFO thread
ran on; and the phase sub-fields are per-flip EMAs, not window means.

**One structural fact the rest of this plan turns on.** Draws are recorded into the current command buffer and
submitted to the GPU only at a finish (`pgraph_vk_finish`, draw.c:4881). At this scene there are 220 finishes per
60 frames: `sd` 90 (the cube faces), `flip` 60, `stl` 70, `buf` 0 (NOTES 5.4). So the GPU gets the frame's draws
in three or four pieces, and the first two pieces are the cube-face finishes. Remove those and nothing submits
until the end-of-frame STALLED finish, whose fence the report path then waits on for the WHOLE frame's GPU work.
The two GPU waits in the table above are not independent: removing one grows the other. Section 5 prices them in
that order for that reason.

## 4. Per subsystem: what has to be reworked

Each entry: measured cost on the critical path (with its source), the design, what it removes and whether the
critical path moves, P(lands) with the evidence for it, lane-days, accuracy risk, the pixel check, dependencies.
"Plain" figures use section 2's scaling assumption; "instr." figures are measured on the perflog build.

### 4.1 Surface/texture coherence: the cube-map faces (step 1, lane.texscan1010, built and ready; lands after 4.2)

**Measured 10-10 (NOTES 5.7), overriding the model below:** alone, `HAKUX_TEXSCAN=1` reads **+2.6 ms** on the
period over the start (texscan1010's reader, matched-work gfps -1.40) and **+7 ms at the countdown** (this
lane's reader; pace 46.2 -> 53.3, one valid A run against two B). `Sub` fell 10.8 -> 0.2 and Fin's remainder,
the report fence, rose 4.1 -> 17.8; GPU busy rose 13.4 -> 18.0 (`X` 0.8 -> 5.8, MxG 0.1 -> 2.4) and submits per
frame fell 3.1 -> 1.2-1.4. The model's "-4 to -8 alone" was wrong in sign for two reasons it did not price:
with no mid-frame submit the GPU's work no longer overlaps the recording (the fence waits for all of it after
the FIFO runs dry), and the copy route costs the GPU 3-5 ms/frame more than the readback did. Removes 10.1-17.3
ms of waits only together with 4.2; "with 4.2 the full amount" still stands, less the 3-5 ms of GPU the copy
adds, which is on the path only when the GPU is (4.6).

- **Cost on the path:** 17.3 ms cold / 10.1 warm instr. (PFIFO `finish_event` waits for the `sd` finishes,
  1.5/frame; NOTES 5.5), same on plain (a GPU wait). The CPU side of the download (swizzle, memcpy into the
  texture) is another 7.3 ms/frame instr. inside `create_texture` (texscan census), ~5.8 plain.
- **What it is:** `create_texture` (vk/texture.c) finds the 128x128 A8R8G8B8 cube environment map @352a080
  overlapping dirty surfaces; face 0 through the SDL block, faces 1-5 through `download_surfaces_in_range_if_dirty`;
  each download is a synchronous finish + GPU readback + CPU copy. `check_surface_to_texture_compatiblity`
  refuses `shape->cubemap` (texture.c:1402), so the surface-to-texture route (`HAKUX_SURFGPU`) never takes it.
- **Design (texscan1010's, already built, `HAKUX_TEXSCAN=1`):** `vkCmdCopyImage` from the surface image into
  the cube face of the texture image on the GPU, inside the current command buffer, with the surface's dirty
  state left as "downloaded later if the CPU reads it". No finish, no readback, no CPU copy. What this plan
  adds: the face-0 SDL path and the five range-scan faces must both take it (the census says they do), and
  the deferred download must still happen before any CPU/guest read of that VRAM (the switch's rule 2).
- **Removes:** 10.1-17.3 ms of waits + ~6 ms of CPU, **but** see the structural fact above: with the `sd`
  finishes gone the STALLED finish's fence (4.2) absorbs the GPU work the `sd` finishes used to drain. Alone,
  the period moves by the CPU part plus the difference between the GPU wait it removes and the GPU wait it
  creates: model says **-4 to -8 ms, not -16 to -23**. With 4.2 it is the full amount. The critical path does
  not move (PFIFO).
- **P(lands) 0.7.** Built; the census matched every download at the scene to one object; the mechanism is a
  pure wait removal. The 0.3 is coherence corners (a CPU read of the face's VRAM later, a format the GPU copy
  cannot do) and the pixel suite's verdict, pending in its six runs.
- **Lane-days:** 0 remaining for the switch; 1-2 to make it default-on if the pixel leg is byte-identical.
- **Accuracy risk:** low for pixels (the same bytes, copied on the GPU) if the copy honours the swizzled cube
  layout; the cube-face suites decide. Timing risk: none for the guest (the guest never reads this VRAM at
  this scene; the census shows no CPU-side consumer).
- **Pixel check:** texscan1010's pixel leg (`1-1791650753`/`-757`): every texture/surface/cube suite on vs
  off, byte-identical.
- **Dependencies:** none to build; 4.2 to realise the full win.

### 4.2 GPU sync: the pending-report fence (step 2, new lane `reportasync1010`)

- **Cost on the path:** 6.7 ms cold / 4.3 warm instr., 1.0/frame, site `#54` `p_fence` under `pfifo.lock`
  (NOTES 5.5); the same on plain (a GPU wait). After 4.1 it grows to the GPU time outstanding at GET==PUT:
  up to 21.7 cold / 12.8 warm (the frame's GPU busy; section 3).
- **What it is:** NV097_GET_REPORT only queues the report (reports.c:100). When the pusher catches up
  (`dma_get == dma_put`) with draws recorded, `pgraph_vk_process_pending_reports` (reports.c:361-380) issues a
  deferred STALLED finish; `pgraph_vk_process_pending_reports_internal` (reports.c:213, called from pfifo.c:2163
  under `pfifo.lock` and from SET_CONTEXT_DMA_REPORT under `pgraph.lock`) then waits on every submitted frame
  fence when a query is in flight (#804, reports.c:257-262), reads the query pool with WAIT_BIT, and
  `pgraph_write_zpass_pixel_cnt_report` (pgraph.c:5610-5631) writes 16 bytes into guest RAM through the report
  DMA object. The write is `timestamp, result, done=0`: today the guest cannot be polling `done` (it is never
  set), so the guest reads the result some time after issuing GET_REPORT and the emulator pays for the GPU to
  be finished at the moment the FIFO runs dry, on the thread that paces the frame.
- **Design:** move the report write to the render thread, after the fence, which is also what the hardware does
  (the GPU writes the report when it reaches the GET_REPORT in the stream).
  - At finish time (draw.c `pgraph_vk_finish`, the STALLED or any finish with queries in flight), snapshot the
    pending reports into the `RenderCommand`: for each, the DMA target (host pointer from `nv_dma_map` of
    `pg->dma_report` + offset, taken on the PFIFO thread so no guest-memory mapping happens on the render
    thread), the query index, and the frame slot. Clear `report_queue` and `num_queries_in_flight` on the PFIFO
    side at that point.
  - In `process_finish` (render_thread.c:116-171), after `vkWaitForFences` on this command's fence (the
    deferred branch already waits when `post_fence_cb` is set, :163), read the query pool for the snapshotted
    indices (no WAIT_BIT needed: the fence covers them, and fences on one `VkQueue` signal in submission order,
    so #804's "wait for every earlier submitted frame" is implied) and write the three fields to the host
    pointer, `result` before `done`, with a release store on `done`. Set `done = 1`: that is the hardware
    value, and it is the only way a guest that does poll it can ever proceed.
  - `pgraph_vk_process_pending_reports_internal` keeps its CPU-side work (query reset bookkeeping) but no
    longer waits; it runs under `pfifo.lock` for microseconds instead of 4-7 ms.
  - Switch `HAKUX_REPORT_ASYNC=1`, default off in the lane; the A/B is the switch.
  - Files: `hw/xbox/nv2a/pgraph/vk/reports.c`, `renderer.h` (RenderCommand finish fields :778-791),
    `render_thread.c`, `draw.c` (finish enqueue), `pgraph.c` (the report write, to take a host pointer).
- **Removes:** 4.3 warm / 6.7 cold now; with 4.1, all of the GPU wait that would otherwise move onto this
  fence (the GPU's work then overlaps the PFIFO thread's next frame and the VBLANK wait). After 4.1 + 4.2 the
  PFIFO thread waits on the GPU only at slot rotation (draw.c:5234; 3 slots at 2.2 finishes/frame = 1.4 frames
  of slack, so a wait only when the GPU is >1.4 frames behind). **The critical path stays PFIFO but is now
  PFIFO on-CPU + VBLANK grid, with the GPU in parallel.**
- **P(lands) 0.6.** The mechanism matches the measured cause exactly (one wait, one site, 1.0/frame). The
  evidence against: the corpus has seven finish-deferral attempts (NOTES 2.3), of which the ones that moved a
  wait to another PFIFO site lost fps, and the one that let the GPU run (`g_sg_held`, SURFGPU) won +18-24 gfps
  on NBA; this design is the second kind. The 0.4 is (a) a guest that reads the report before the GPU is done
  and acts on a stale `result` (an occlusion test that was wrong for one frame: popping, not corruption), (b)
  the render thread writing guest RAM without the BQL (the pointer is stable, the bytes are 16; the risk is a
  torn read, which the write order bounds), (c) #804's ordering re-derived on the render thread.
- **Lane-days:** 3-5.
- **Accuracy risk:** pixels none (the report is not a pixel). Guest behaviour: medium. Measure before deciding
  the default: instrument the gap between the fence and the guest's next GET_REPORT/flip; if the guest flips
  before the result landed on >1% of frames, the design needs the `done` flag honoured by the guest (check by
  reading the guest's poll pattern on the report address with a watchpoint build) or stays opt-in.
- **Pixel check:** the "ZPass pixel count" suite (nv2a_issues.toml:843, 2963) on vs off, then the 27-suite
  disc; NFS race-start frames at the 12 marks compared region by region on vs off (missing or popped cars and
  props are what a wrong report looks like).
- **Dependencies:** none. Makes 4.1 whole.

### 4.3 Pacing/present: the VBLANK grid

- **Cost on the path:** 12.6 ms cold / 11.0 warm instr. (`pidle`: FIFO empty after the flip), the remainder
  on plain (section 2).
- **What it is:** quantization, not work. The guest waits for the VBLANK that follows its FLIP_STALL;
  `nv2a_vblank_timer_cb` (nv2a.c:957-1251) may defer a VBLANK by up to `poll_interval * defer_cap` =
  period/8 x 4 = **8.3 ms** when locked (nv2a.c:1127-1143) for a frame that nearly made it. So a frame of
  33-41 ms of PFIFO work lands in 2 VBLANKs at a stretched period, and a frame of 42+ ms takes 3. That is why
  the plain warm countdown is 49-51% `v2` at a 41-42 ms mean period: the `v2` frames are deferred ones.
  **30 fps means pace ms/60 <= 33.3, i.e. PFIFO work <= ~33 ms at p95 WITHOUT deferral**, not "v2 at 100%".
- **Design:** none that is a fix. Unlocking the frame rate (`HAKUX_FORCE_UNLOCK`, `unlock_framerate`,
  xemu_android.cpp:642/916) removes the grid and would turn 41 ms of work into 24 fps unquantized rather than 20;
  lane.vblank65 priced it and it is the owner's call (a game whose physics step is tied to VBLANK changes
  behaviour). It is a pacing remedy, not a rework, and is not scheduled here.
- **Removes / P / days:** 0 / n.a. / 0. Its contribution to the plan is the budget line.

### 4.4 Vulkan recording and state (step 3, new lane `drawrec1010`)

- **Cost on the path:** ~23 ms cold instr. (1,860-1,930 draws x 11.9 us: `Syn` 4.6, `Pipe` 6.4 of which `Sh`
  4.1, `Desc` 2.7, `Setup` 1.4, `Mfp` 3.9; NOTES 5.5), ~18 plain; warm ~17 instr. / ~14 plain. perdraw1009's
  profile at the same scene splits the per-draw cost further (ms/frame at ~1,630 draws): pipeline lookup
  `create_pipeline` inclusive 7.51, `update_shader_uniforms` 4.43 (of which `uniform_copy` 2.84), descriptor
  sets 3.42 (ubosz hook 1.39, memcmp 0.79, memcpy 0.68), textures bind/create 2.33/2.12, vertex setup 1.59.
  perdrawon1010's three uniform switches took 1.76 us/draw (-17%) off the race start and are the baseline
  for this step.
- **What it is:** every draw walks `begin_pre_draw_inner` (draw.c:5452): ~20 compares + a memcmp of the vertex
  attributes against the bound pipeline's key (:5580-5592), then textures, `update_shader_uniforms` (:5755),
  `update_descriptor_sets` (:5756); `create_pipeline` (:2428) derives the shader and pipeline key from PGRAPH
  registers on every draw (`pipe_bind_tex`, `pipe_bind_shd`, hash + LRU :2518-2520); `begin_draw` (:6045)
  binds the pipeline, diffs dynamic state (:6174-6356), binds set 1 with two dynamic offsets (:3398), pushes
  constants (:3245). Nothing is skipped on the grounds that the previous draw had the same state, except the
  pipeline handle itself and the dynamic-state diff. No two guest draws are ever merged (`g_xemu_draw_reorder`
  / `g_xemu_draw_merge` are off, draw.c:33-34, and RCMD_DRAW is never enqueued, :5940-5942).
- **Design, in order:**
  1. **Census instrument (1-2 lane-days, decides the rest).** On the plain build at the race start, for each
     consecutive draw pair, which inputs changed: PGRAPH register ranges feeding the shader key (combiner,
     vertex-attribute formats, texture state, lighting), bound textures, the uniform block (hash of the bytes
     that `uniform_copy` would copy), dynamic state, surface. One histogram per window. If >=50% of consecutive
     draws differ only in vertex data and transform/material uniforms, steps 2 and 3 pay; if every draw changes
     the key, only step 4 does. Default off, prints to logcat, no behaviour change.
  2. **Dirty-tracked state reuse (5-10 lane-days).** Method dispatch already knows which registers a draw
     touched; set dirty bits per key-feeding range in `pgraph_method` and skip `pipe_bind_shd`/key derivation,
     the vertex-attribute memcmp, texture re-bind and descriptor-set rebuild when the range is clean since the
     last draw. Uniform upload becomes a per-range copy of only the dirty ranges (the extension of perdraw1009's
     F1-F3). Expected on the census's assumption: `Pipe` 6.4 -> ~2.5, `Desc` 2.7 -> ~1.2, `Mfp` 3.9 -> ~2.5,
     `Syn` unchanged: **-30% of recording, ~-5.5 ms plain cold, -4 warm.** Data structure: a 32-bit dirty mask on
     `PGRAPHState` keyed by the key-derivation inputs, plus the last-bound pipeline/descriptor/uniform-range
     handles on `PGRAPHVkState`.
  3. **Push constants for the per-draw dynamic offsets** (bf2stall433's suspect, 1-2 lane-days): removes a
     `vkCmdBindDescriptorSets` per draw when only the offsets changed. ~-0.5 to -1 ms. Inside step 2's switch.
  4. **Recorder thread (the drastic form; 15-25 lane-days; section 6).**
  Switch `HAKUX_DRAWREC=1` for steps 2-3, default off; the A/B is the switch; perdrawon1010's three switches on
  in both arms (they are part of this step, not of the baseline).
  Files: `hw/xbox/nv2a/pgraph/vk/draw.c`, `shaders.c` (uniforms, descriptor update), `pgraph.c` (method
  dispatch dirty bits), `renderer.h`.
- **Removes:** ~-5.5 ms plain cold / -4 warm for steps 2-3 (-30% of recording). Critical path does not move.
- **P(lands) 0.5 for -30%.** For: perdraw1009's F1-F3 took 15% off with the narrowest form of the same idea,
  and NFS draws are many small material-repeating draws (cars, barriers, road segments). Against: the #474
  uniform-hash skip was inert on Blinx (energymap507): a title whose state churns every draw gives this
  nothing, and the census is the only way to know which NFS is. P 0.8 that the census is informative.
- **Lane-days:** 1-2 + 5-10 (+1-2).
- **Accuracy risk:** medium. A missed dirty bit is a wrong pipeline or stale uniform on a draw. Every such bug
  is a pixel-suite failure, which is why the 27-suite disc is the gate and the switch stays off until it is
  byte-identical.
- **Pixel check:** 27-suite disc on vs off, byte-identical; NFS frames at the 12 marks region-compared.
- **Dependencies:** none; its win is additive to 4.1/4.2 (CPU, not GPU wait).

### 4.5 PFIFO command path: parsing and the untimed 10-13 ms

- **Cost on the path:** `Push` 0.7 + `Pull` 0.65 ms/frame instr. are the only timed parts; the untimed
  remainder of PFIFO on-CPU is 10-13 ms cold instr. (NOTES 5.5: method dispatch outside the draw timers,
  texture-bind bookkeeping, pending-report processing, perflog clock reads at 1.65 ms/frame). Plain: ~7-9 ms
  **(assumption: the perflog clock reads leave with the build, the rest scales)**. lane.local's 10-09 simpleperf
  of the PFIFO thread (NOTES 5.2, perflog build, by hand) names the on-CPU shares: `pfifo_thread` self 22.3%
  (clock reads), memcpy 15.3%, `tlb_reset_dirty` 4.3%, `ubosz_note_upload` 4.2%, `surface_update` 3.9%,
  `apply_uniform_updates` 3.7%, memcmp 3.7%, Turnip 4.5%.
- **Design:** measurement first: one simpleperf of the plain build on the route (PFIFO thread only, 45 s over
  two race starts, 0.5 lane-day) attributing the untimed bucket to functions. The candidates and their fixes:
  `memcpy`/`tlb_reset_dirty` are vertex-RAM sync (`sync_vertex_ram`, 1.59 ms/frame in perdraw1009): a dirty-page
  bitmap per vertex buffer instead of `tlb_reset_dirty` per draw; method dispatch per inline vertex-array word
  (NFS pushes vertex data inline): a fast path that copies the inline array in one memcpy per method run
  instead of per word.
- **Removes:** -2 to -4 ms plain cold if the profile confirms the two candidates. Critical path does not move.
- **P 0.3** that the profile names a fixable 3 ms; the account above says most of this bucket is the draw
  path's own bookkeeping, which 4.4 already covers.
- **Lane-days:** 0.5 to measure; 3-5 to fix. **Accuracy risk:** low (vertex sync correctness is covered by
  every suite). **Pixel check:** 27-suite disc. **Dependencies:** run the profile inside `drawrec1010`'s census
  step; do not open a lane for it.

### 4.6 GPU work: render passes and GMEM

- **Cost on the path:** none today. GPU busy 21.7 ms cold / 12.8 warm per frame, 69 render passes cold (26.5
  warm), 20 MB GMEM load + 20 MB store (this lane's `XFR rpc` census, NOTES 5.5). After 4.1 + 4.2 the GPU runs
  in parallel with the PFIFO thread, so the GPU is on the path only when its busy time exceeds the PFIFO
  thread's: not at this scene (21.7 vs ~30 cold, 12.8 vs ~24 warm), possibly on heavier tracks at night/rain.
- **What the corpus says (gmem474, rendermode474, flip474):** GMEM mode runs the draw stream twice (X/R ~1);
  sysmem mode cut GPU time 60.0 -> 28.6 ms on DOA and 40.1 -> 21.5 on AUF, and is the default for those two
  titles through `kTitleRenderModes` (xemu_android.cpp:796-810). `TU_AUTOTUNE_ALGO=profiled` (arm D) was as
  good. Nothing measured NFS's X/R or passes under sysmem.
- **Design:** one A/B, NFS title id added to `kTitleRenderModes` as sysmem vs default, plain build, judged by
  GPU ms and the period (0.5 lane-day of device time, no code beyond the table row). The 2.6x cold-start pass
  count is the cube-face traffic (each face copy ends a pass); 4.1 keeps the copy but may not reduce the
  breaks; the census after 4.1 says.
- **Removes:** 0 from the period today; up to 9 ms of GPU busy cold if NFS behaves like AUF, which is margin
  for 4.1/4.2's overlap on heavier scenes. **P 0.6** that sysmem cuts GPU ms (two of three titles did; Kabuki
  did not); **P 0.2** that it moves NFS's period now. **Lane-days:** 0.5-1. **Accuracy:** none (render mode is
  a driver tiling choice; pixels PASS 1059 on rendermode474). **Pixel check:** rendermode474's suites.
  **Dependencies:** after 4.1 + 4.2, when the GPU can be the path at all.

### 4.7 Driver (Turnip)

- **Cost on the path:** inside 4.4's recording: Turnip's draw-time state emission is part of `Setup`/`Mfp`
  (perdraw1009 could not split it). The only driver share measured is Crimson's: 7.2% of PFIFO on-CPU, ~2 ms/
  frame (turnipfork); NFS by hand: 4.5% (NOTES 5.2). **(assumption: ~1.5-2.5 ms of NFS's cold frame.)**
- **What exists:** a build of Turnip from pinned Mesa (`tools/turnip/build.sh`, 17.7 MB, not reproducible);
  PurpleVK T30 ships unpatched; one known driver bug (`timestampPeriod` 33.11 vs 52.08 ns) is worked around in
  hakuX (`gpu_ts_calibrate`); drvab77 refuted a driver effect on the stipple; turnipcost569 put 96% of the
  pipeline-compile stall in Turnip's NIR/ir3, which uberdefault569 and shaderprebuild569 now hide.
- **Design, if ever:** fork to (a) trim draw-time state emission for the state hakuX never changes between
  draws (Turnip re-emits per `vkCmdBindDescriptorSets`/dynamic-state call), (b) a cheaper
  `vkGetQueryPoolResults` path. Both are bounded by the ~2 ms share. A fork also owns every future Mesa merge.
- **Removes:** <= 2 ms cold plain. **P 0.2** (no profile puts driver time on the path; the fork's build is not
  reproducible). **Lane-days:** 10-20 + maintenance. **Expected impact 0.4 ms: not scheduled.** Reopen only when
  a plain-build profile after 4.4 shows >10% of PFIFO on-CPU inside `libvulkan_freedreno`.

### 4.8 Guest JIT and memory (vCPU)

- **Cost on the path:** none today at this scene: the vCPU holds the X3 88% of wall but the guest's work is
  24.5-27.4 ms/frame (`[rr425w]` busy, plain, nfsframe1010) and the rest is the idle loop spinning. `cls pgraph`
  78-83% (frametrace) says the FIFO, not the guest, paces. **After 4.1 + 4.2 + 4.4 the PFIFO thread is at
  ~24-25 ms cold and the guest's 27.4 ms becomes co-critical at the cold start**: the frame is then
  max(PFIFO, vCPU) + sync, and the vCPU is the larger term.
- **What the corpus prices (vcpuplan, NOTES 4.5; all unbuilt unless named):** fastmem P 0.40 for 12-20% of
  guest time; IBC+RAS P 0.50 for 8-13%; drop the TB preamble P 0.80 for 4-8%; inline scalar SSE P 0.70 for
  2.5-4%; superblocks P 0.25 for 5-10%. Landed: W1, JC, RD, memfast phase 1. vcpu60: 20.6 host insns per guest
  insn against a 14-16 ceiling for TCG. vcpuprime428 (pin the vCPU to the prime core) lost 21.5% because the
  vCPU was ejected to the little cores; the next form is `uclamp.min` or a big+prime mask.
- **Design (step 6):** in P x win order: drop preamble (P 0.8 x 6% = 1.6 ms), IBC+RAS (0.5 x 10% = 1.4 ms),
  fastmem (0.4 x 16% = 1.8 ms), SSE (0.7 x 3% = 0.6 ms). Together, if all land: guest 27.4 -> ~19-21 ms
  (-25 to -30%, not summed: fastmem and IBC overlap on memory-bound blocks). Files per vcpuplan's NOTES
  (`tcg/aarch64/`, `accel/tcg/cputlb.c`, `accel/tcg/cpu-exec.c`).
- **Removes:** 0 from the period today; after steps 1-3, up to 6-8 ms off the cold start's then-critical term.
  **P:** per item above; 0.5 that two of four land in the 0.5 window. **Lane-days:** 3-5 (preamble), 8-12
  (IBC+RAS), 15-25 (fastmem). **Accuracy risk:** high class (JIT correctness) but covered by the existing
  guest-visible test set and every title's boot; the pixel suites catch a wrong JIT only indirectly.
  **Dependencies:** none to build; on the path only after 4.1 + 4.2 + 4.4.
- **A different JIT backend:** section 6.

### 4.9 Threading and placement (step 4: dropped; `placement1010` not dispatched)

**Probe result (NOTES 5.6):** F FAILED on both B runs. With the vCPU halting instead of spinning (its on-CPU
share 50-52% of wall against ~100%, 506-558 halts/s, X3 free 35-38% of wall), the countdown pace read 43.5 and
43.7 ms/frame against 41.7 pooled for the plain baseline (B/A 1.04-1.05; the bound was 0.92); post-GO 44.0
against 40.0; the guest's own busy time per frame rose 3.3 ms at the same idle share. Freeing the X3 does not
shorten the PFIFO thread's frame at this scene, and the halted vCPU runs its work slower. **P <= 0.2 for the 4-5
ms below; none of it is counted in section 5; the brief is not dispatched.** What is still unmeasured is the
PFIFO thread's CPU id per frame (the brief's step 1); it is worth a lane only if a later step leaves the cold
start within ~5 ms of 33.3 with PFIFO on-CPU the remaining term. Idle halt stays opt-in and NFS gets no
title-table entry for it.

- **Cost on the path:** unknown (the pre-probe text follows). The vCPU spins on the X3 88% of wall (PMU, NOTES 5.5); which core the PFIFO
  thread runs on was not recorded (blind spot). If the PFIFO thread runs on an A715 while the X3 spins idle,
  its 30.4 ms plain cold on-CPU is ~1.2x what the X3 would take: **~5 ms cold / ~4 warm (assumption, the
  A715/X3 ratio)**.
- **Probe (queued now):** `nfs30plan1010-idlehalt.json`, requests `1-1791652213-nfs30plan1010-2992539` and
  `1-1791652214-nfs30plan1010-2992731`: `HAKUX_IDLE_HALT=1` as an instrument (the vCPU halts instead of
  spinning, freeing the X3) against nfsframe1010's two plain runs. F: B's pooled countdown pace <= 0.92 x A.
- **Design if F passes:** pin by role: the PFIFO thread to the prime core, the vCPU to a big+prime mask with
  `uclamp.min` (not a bare prime pin: vcpuprime428), the render thread to a big core; a title-table entry for
  idle-halt (NFS only) rather than the default (idlehaltdefault's opt-in verdict stands). Files:
  `android/app/src/main/cpp/xemu_android.cpp` (the dead `XEMU_OPT_THREAD_AFFINITY` path), `util/qemu-thread-posix.c`
  (a named-thread affinity hook), `hw/xbox/nv2a/pfifo.c` (thread start).
- **Removes:** 4-5 ms cold if the probe says so; 0 if not. **P unknown until the probe**; the corpus is split
  (idlehalt fps within 1.3% on other titles, i.e. the X3 did not help them; this scene is PFIFO-bound and may
  differ). **Lane-days:** 3-5. **Accuracy:** none. **Pixel check:** none needed (placement does not touch
  pixels). **Dependencies:** the probe.

## 5. The combination, in order, with the expected period after each step

The model: plain period = PFIFO on-CPU + PFIFO GPU waits + VBLANK remainder, quantized to 16.7 ms steps with
up to 8.3 ms of deferral. Inputs: cold on-CPU 30.4, waits 24.0 (17.3 sd + 6.7 fence), GPU busy 21.7; warm
on-CPU 24.3, waits 14.4, GPU busy 12.8 (sections 2-3; on-CPU scaled x0.8). Each row removes only what the
previous rows left. **Every "expected" figure is a model output, not a measurement; the step's A/B replaces
it.** Current, measured: cold 56-62, warm 41-42, post-GO 40.0 (nfsframe1010).

| step | what it removes from the PFIFO thread | cold start (ms/frame) | warm restarts | note |
|---|---|---|---|---|
| 0 now | | **56-62** (meas.) | **41-42** (meas.) | v2 ~50% warm |
| 2 first: `reportasync1010` alone | the report fence 6.7 / 4.3 | 50-55 | 37-38 | v2 ~65% warm; the sd finishes still drain the GPU mid-frame |
| 1: texscan1010 on top | sd waits 17.3 / 10.1 and ~6 / ~4 CPU; nothing new waits (the fence is gone) | PFIFO 24-25 -> **35-40** (2-3 VBLANKs, mixed) | PFIFO ~20 -> **33.3** (every frame in 2 VBLANKs without deferral) | **warm start at 30 fps; post-GO at 30**; cold start 25-28 fps |
| 1 alone (if 2 is not done) | sd waits, but the fence absorbs the frame's GPU work AND the copy adds 3-5 ms of GPU | **MEASURED: +7 at the countdown (46.2 -> 53.3, instr.), +2.6 over the start** | +2 to +4 post-GO (instr.) | texscan1010's A/B (NOTES 5.7). The model row said 52-58 / 38-40, i.e. a small gain; the sign was wrong. Never ship 1 without 2 |
| 3: `drawrec1010` steps 2-3 | -30% recording: 5.5 / 4 | PFIFO 19-20 -> **33.3** at p50, 2-3 VBLANKs at p95 | PFIFO ~16 -> 33.3 with 17 ms of margin | **cold start at 30 at p50**; GPU (21.7 cold instr., +3-5 with the copy) now the second-largest term |
| 4: placement | DROPPED: the probe read +2 to +4 ms with the X3 freed (NOTES 5.6) | | | p95 margin at the cold start now comes from step 3's recorder-thread form or step 6, not from placement |
| 5: GPU sysmem / passes for NFS (`gpupass1010`) | GPU busy 21.7 -> ~13 if AUF-like; with the copy on, 18 ms instr. at the cold countdown | no period change until GPU > PFIFO; with steps 1+2 that is ~24-25 cold PFIFO vs 18-25 GPU: **close at the cold start** | | moved up to "with the pair": the pair's on-run carries `HAKUX_GPUXFR=1` |
| 6: JIT items | guest 27.4 -> 19-21 | the vCPU is co-critical from step 3 on (27.4 vs PFIFO 19-20); this is what keeps the cold start at 30 when the guest, not the FIFO, is the larger term | | |

Reading the table: **steps 2 + 1 together (the fence first, then the copy) are what brings the warm start and
post-GO to 30 fps; step 3 brings the cold start to 30 at the median; steps 5-6 are what holds it at p95 and on
heavier scenes; step 4 is gone.** The owner's 13 fps was a perflog build by hand (section 2); the plain build
is at 16-18 cold and 24 warm now. The cold-start GPU margin after the pair is thin (18-25 ms of GPU against
24-25 of PFIFO, instr.), which is why `gpupass1010` runs with the pair rather than after it.

Not summed: 4.1 and 4.2 share the GPU-wait pool (the table takes them together); 4.4 and 4.5 share the
untimed bookkeeping (4.5 is inside 4.4's lane); 4.8's items overlap each other on memory-bound blocks; 4.9's
gain scales 4.4's and 4.5's remaining on-CPU time, not the waits.

## 6. Drastic measures, priced

| measure | what it would remove | critical path after | P(lands) and evidence | lane-days | accuracy risk | verdict |
|---|---|---|---|---|---|---|
| **Recorder thread** (threading model): PFIFO parses methods and snapshots each draw's state (as the reorder window does at enqueue, `try_snapshot_*`); a recorder thread does `begin_pre_draw`/`begin_draw`/flush and the finishes in the same ring (RenderCommand already carries finishes) | the recording that does not read guest memory: pipeline lookup, descriptors, uniforms, command recording ~60-70% of 4.4 = 12-15 ms cold plain. Texture upload and vertex-RAM sync stay on PFIFO (the skew-bound guarantee, draw.c:6837-6863: every guest-memory read must happen inside method processing) | max(PFIFO parse + upload ~15, recorder ~15, GPU 21.7) + grid: **the GPU becomes the path at the cold start** | **0.4.** For: the queue (DRAW_QUEUE_MAX 128, RCMD_DRAW) and the render thread exist; the reorder window proves snapshot-at-enqueue. Against: RCMD_DRAW was never on by default, the merge queue breaks the skew bound, and surface updates/finishes must stay ordered with draws across two threads; three lanes lost fps moving work across threads (NOTES 2.3) | 15-25 | high: ordering of surface_update vs draws, dirty-bit reads at the wrong time; the full disc is the gate | **schedule as 4.4 step 4 only if the census says state reuse cannot reach -30%**, or when 30 fps needs more than steps 1-4 give |
| **JIT backend** (replace TCG for x86->arm64 with a block-linking translator that allocates registers across blocks and maps guest flags to NZCV natively, FEX/box64-class) | guest 27.4 -> ~14 ms/frame **(assumption: FEX-class translators run 2-3x TCG on x86 guests; no hakuX lane has measured one on this title)**; 20.6 host insns per guest insn -> ~8-10 | the guest leaves the path for good; PFIFO alone paces | **0.1 within the 0.5 window**, 0.4 ever: months of work, every guest-visible bug is a correctness regression, and no lane has priced it (NOTES 4.5: "no lane priced a different JIT backend") | 60-120 | highest in the project | **not scheduled for 30 fps at this scene**: the guest is not on the path until step 3, and 4.8's four items cover the gap at a fifth of the cost. Price it again when a title is guest-bound after steps 1-4 |
| **Driver fork** (Turnip) | <= 2 ms (4.7) | unchanged | 0.2 | 10-20 + maintenance | low | **not scheduled** (expected 0.4 ms) |
| **Batching guest draws** (merge consecutive draws with identical pipeline + descriptors + uniforms into one `vkCmdDraw`, concatenating vertex ranges; `g_xemu_draw_merge` is the shell of it) | per merged draw: `Setup` + `Mfp` + the bind calls, ~6-8 us; at 40% mergeable (**assumption pending the census**): -4 to -6 ms cold plain | unchanged | 0.3: the merge queue exists but is off because it defers guest reads past the skew bound; the fix is to snapshot at enqueue, which is the recorder-thread work in another form | 5-8 | medium: a merged draw with a state difference the key missed | **inside `drawrec1010` after the census**, as an alternative to step 2 if reuse is low but mergeability is high |
| **Unlock the frame rate** (pacing) | the grid: 41 ms of work becomes 24 fps unquantized instead of 20 | unchanged | owner's decision (vblank65) | 0 | changes game timing | **not a rework; not scheduled** |

## 7. Open measurements (what must be read before the plan's numbers firm up)

1. **Placement probe: DONE, F FAILED** (`1-1791652213-nfs30plan1010-2992539`, `1-1791652214-nfs30plan1010-2992731`;
   NOTES 5.6). 4.9 is dropped; `placement1010` is not dispatched.
2. **texscan1010's four NFS runs: DONE** (`1-1791650940-…-2621346/-2621780`, `1-1791650941-…-2622254`;
   `1-1791650942-…-2622720` void; NOTES 5.7). The structural fact held in full (the wait moved to the fence), and
   the period moved the WRONG way (+2.6 / +7): 4.2 is what makes 4.1 whole, and 4.1 adds 3-5 ms of GPU the
   model had not priced. 4.1 and 5 are re-priced above.
3. **Consecutive-draw state census** (drawrec1010 step 1, run `1-1791656193-drawrec1010-4097387` on the Nova at
   this writing): sets 4.4's P and chooses between reuse, batching, and the recorder thread.
4. **Plain-build PFIFO-thread simpleperf on the route** (inside drawrec1010): names the untimed 7-9 ms.
5. **Render-thread row in frametrace** (instrument request to the board: `profile.h`/`render_thread.c`
   registration; this lane cannot edit them): until then the render thread's run time and the PFIFO thread's
   `finish_event`/`wait_frame_submitted` waits are only the unhooked remainder.
6. **Report consumption timing** (reportasync1010 step 1): fence-to-guest-read gap; decides 4.2's default.
7. **NFS GPU X/R and passes under sysmem** (4.6's A/B): needed only after steps 1-2.
8. **Where the copy route's extra GPU time goes** (new, 10-10): one `HAKUX_TEXSCAN=1` run with `HAKUX_GPUXFR=1`
   on the perflog build, inside reportasync1010's pair (its on-arm), to split the +3-5 ms of GPU between the
   copy's transitions (`Tr` 1236 -> 1916 per 60 frames) and the inter-pass gap (MxG 0.1 -> 2.4). Decides whether
   `gpupass1010`'s first item is the copy's layout transitions rather than the render mode.

## 8. Briefs written (docs/lanes/nfs30plan1010/briefs/)

| brief | step | dispatch when |
|---|---|---|
| `reportasync1010.md` | 2 (lands first) | **dispatched 10-10** by lane.local (`origin/lane/reportasync1010`; pilot `1-1791656656-reportasync1010-4183629` async+trace, `1-1791656657-reportasync1010-4184121` trace). Its design puts the report write on a reader thread of its own, not the render thread; same mechanism as 4.2 (the fence leaves the PFIFO thread) |
| `drawrec1010.md` | 3 | **dispatched 10-10** by lane.local (`origin/lane/drawrec1010`; census run `1-1791656193-drawrec1010-4097387`) |
| `placement1010.md` | 4 | **NOT dispatched**: the probe's F failed on both B runs (NOTES 5.6); the brief's header says so |
| `gpupass1010.md` | 5 | with reportasync1010's pair (NOTES 5.7: GPU 18 ms instr. at the cold countdown with the copy on), not after it; the pair's on-run carries `HAKUX_GPUXFR=1` (section 7.8) |

Steps 1 (texscan1010) and 6 (vcpuplan's items) have briefs already (`briefs/texscan1010.md`; vcpuplan's
NOTES); nothing is re-dispatched here. Model per the 10-10 table: Opus for engineering, Sonnet when usage
is Low.

## 9. Sources

- This lane: runs `1-1791649387-nfs30plan1010-2138210`, `1-1791649388-nfs30plan1010-2138879` (perflog + frametrace
  + PMU + census, ref ab1acc4154); readers `ftwin.py`, `phaseread.py`, `vcpuread.py`; NOTES.md sections 2-5.
- lane.nfsframe1010: `1-1791649039-nfsframe1010-2037292`, `1-1791649724-nfsframe1010-2219502` (plain build,
  07937793af): the baseline period, histogram and `[rr425w]`.
- This lane's placement probe: `1-1791652213-nfs30plan1010-2992539`, `1-1791652214-nfs30plan1010-2992731` (plain
  build 07937793af, `HAKUX_IDLE_HALT=1`); prediction `docs/testing/predictions/nfs30plan1010-idlehalt.json`;
  NOTES 5.6.
- lane.texscan1010: `1-1791648919-texscan1010-2004607` (census, free perflog run); its NOTES section 3. Its NFS
  A/B (ref e654516849 perflog): `1-1791650940-texscan1010-2621346` (off), `1-1791650940-texscan1010-2621780` and
  `1-1791650941-texscan1010-2622254` (on), `1-1791650942-texscan1010-2622720` (off, VOID: menu); its NOTES 8-11;
  NOTES 5.7 here.
- lane.perdraw1009 (`origin/lane/perdraw1009`): per-draw sub-phases, F1-F3; lane.perdrawon1010: `1-1791644405`,
  `1-1791645060`, `-726861`: us/draw and the draw-count fit.
- lane.local 10-09 simpleperf (`~/hakux-work/lanelocal-scratch/nfs-race-1009/prof/split.txt`).
- Corpus digests (NOTES section 4): vcpuplan, vcpu60, vcpuprime428, vcpusleep, idlehalt*, jcache425, memfast,
  frametrace, async794, forza414, vcpuwait433, gpunonrender, vblank65, kabukistall, bf2stall433, turnipfork,
  turnipcost569, gpl569, shaderplan569, shaderprebuild569, shaderfb569, uberdefault569, uberspike569,
  litcompile569, pipeline413, gmem474, rendermode474, flip474, drvab77, energymap507, sustain507, thermal507.
- Code at 07937793af: `hw/xbox/nv2a/pgraph/vk/{draw,reports,renderer,render_thread,texture,shaders}.c`,
  `hw/xbox/nv2a/pgraph/pgraph.c`, `hw/xbox/nv2a/pfifo.c`, `hw/xbox/nv2a/nv2a.c`,
  `android/app/src/main/cpp/xemu_android.cpp`.
