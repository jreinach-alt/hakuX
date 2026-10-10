# lane.nfs30plan1010 -- NOTES

What has to be reworked for NFS Most Wanted's race start to hold 30 fps (#433, 0.5). Owner's escalation
10-10 ~09:10 PDT: "Everything is on the table, JIT, Driver changes, all of it." Analysis and plan lane; the
plan is `PLAN.md`, the first lanes are `briefs/`. This file is the record: the architecture as found at
`07937793af` (master at branch time), every instrument's format and blind spot, the corpus figures with
their sources, this lane's own measurements, and what the next lane should not repeat.

Build under test: `ab1acc4154` (perflog). `git diff --stat ab1acc4154 origin/master -- hw/ accel/ target/`
is empty; the two differ only in docs and jobs, so the emulator measured is master's. It contains the GPU
stamp double-count fix 5c35880d0a, SURFGPU default-on 7d574ece8b, 16784acb80 and b387f4971a. It does NOT
contain lane/perdraw1009's `HAKUX_UNI_*` (4ad1154e55, not folded at branch time), so the measured per-draw
cost is the pre-perdraw1009 one; perdrawon1010 measured the switch's effect at this scene (section 4.3).

## 1. The scene, and what "30 fps" means here

NFS MW 3-racer sprint start, perdrawon1010's route (`nfs-mw-quickrace.route`, copied into this dir): Quick
Race, Custom, Sprint, Diamond & Union, Fiat Punto, 2 opponents, Auto; 12 starts per boot, `mark gameplay` /
`mark goN` ~1.5 s before GO, RT (gas) held from before GO through GO+11.

30 fps = every frame presented within 2 VBLANKs (33.3 ms) of the one before. Today, at the countdown, the
title takes 4 or more VBLANKs per frame (`hakuX-pace v4=59` of 60 frames, OFF1 run 1-1791644405 at
08:12:53, 71.6 ms/frame). The owner's bar for driving a full race is a start that holds 28-30.

## 2. Architecture at 07937793af (file:line)

### 2.1 Threads

| thread | created | what it does | what it waits on |
|---|---|---|---|
| vCPU (TCG) | system/cpus.c | runs the guest; writes DMA_PUT (`hw/xbox/nv2a/user.c:92-95`, takes `pfifo.lock`, `Lw`); reads PFIFO USER registers (vcpuwait433: a read can wait out a GPU batch); page-watch faults download surfaces on this thread | `pfifo.lock` on DMA_PUT; MMIO reads that block; the guest's own idle loop at 0x8001b02e is a SPIN (HAKUX_IDLE_HALT default off, `system/cpus.c:575-580`), so idle is on-CPU |
| PFIFO (`pfifo_thread`, `hw/xbox/nv2a/pfifo.c:2115-2170`) | nv2a init | takes `pfifo.lock` (:2119), `pgraph_process_pending` (surface/flip requests from other threads), `pfifo_run_pusher` (:1848; DMA fetch, method parse), puller `pfifo_run_puller` (:1671) -> `pgraph_method` (:1720/1736/1795/1815) under `pgraph.lock`; Kelvin methods take the lockless fast path `pgraph_method_try_fast` (`pgraph.c:816-840`); broadcasts `fifo_drained_cond`; `pgraph_process_pending_reports` (:2163) STILL HOLDING `pfifo.lock` | the render thread (finish, section 2.3); `pfifo_stall_for_flip` (`pfifo.c:1645-1658`, phase `Flip`); idle `Fr`/`St` (`pfifo.c:2238-2246`) |
| render (`pgraph.vk.render`, `hw/xbox/nv2a/pgraph/vk/render_thread.c:189-320`) | renderer init | pops RenderCommands: finish (vkQueueSubmit :151, fence wait :157 when not deferred or when a post-fence callback exists :163-167, `completion` event :170), vertex RAM updates (:175-195), display sync (:254-258, :304-310 -> `pgraph_vk_render_display` `display.c:1940`) | the GPU (vkWaitForFences) |
| submit worker (`pgraph.vk.submit`, `submit_worker.c:25-86`) | renderer init | the older async submit path: vkQueueSubmit + fence wait (:59-74), `complete_event` (:80) | the GPU |
| compile workers (`HAKUX_COMPILE_WORKERS`, default 3) | renderer init | pipeline compiles off the PFIFO thread; ubershader (`HAKUX_GPL_DEFAULT` 3) and prebuild (`HAKUX_PREBUILD` on) keep the PFIFO thread off vkCreateGraphicsPipelines | work queue |
| UI/display (SDL) | main | `ui/xemu.c:2355-2375`: glFlush, `nv2a_release_framebuffer_surface`, `SDL_GL_SwapWindow` (swap_ms into `pacing.swap_ms`) | the compositor |
| VBLANK timer | QEMU timer thread, `nv2a_vblank_timer_cb` `hw/xbox/nv2a/nv2a.c:957` | fires the guest's VBLANK IRQ at `nv2a_calc_vblank_period_ns` (:239; `HAKUX_VBLANK_HZ` diagnostic override), adaptive deferral up to ~1.25 periods after the last FLIP when the game is rendering; `READ_3D` advances so `is_flip_stall_complete` (`pfifo.c:1626`) turns true | wall clock |
| audio voice threads (4) + DSP | mcpx | lane.local's 10-09 profile: 4 x ~5% + 5.7% of one core (section 5.3) | - |

Locks: `pfifo.lock` (DMA_PUT write from the guest, the PFIFO loop, pending-report processing); `pgraph.lock`
(method execution; released around SURFACE_DOWN finishes on the PFIFO thread since #796, `draw.c:5162-5170`);
`render_thread.lock` (queue); BQL is NOT held on Android in the UI refresh path (`ui/xemu.c:2355`).

### 2.2 A guest frame's path

1. Guest builds its pushbuffer in RAM and writes DMA_PUT (`user.c:92`). Under `pfifo.lock`; the wait is
   `lock_wait_ns`, reported as `Lw:` on `hakuX-cpu` and `lw` on `[hakuX-ft1]`.
2. PFIFO pusher reads the pushbuffer (`pfifo_run_pusher` :1848), the puller dispatches methods. A Kelvin
   method goes through `pgraph_method_try_fast` (lockless, `pgraph.c:816-840`) or `pgraph_method` under
   `pgraph.lock`.
3. A draw: `pgraph_vk_draw_end` (`draw.c:8078`) -> nop-draw filter (:8090-8100) -> reorder window / merge
   queue (both default OFF: `g_xemu_draw_reorder`, `g_xemu_draw_merge` = false, `draw.c:31-34`) ->
   `pgraph_vk_flush_draw` (:9750) -> `flush_draw_one_pass`: surface update, texture binding
   (`create_texture`, section 2.4), shader lookup, `create_pipeline` (:2428), `bind_descriptor_sets` (:3398),
   `begin_render_pass` (:3608), vertex upload, vkCmdDraw*. Every one of these is on the PFIFO thread; that is
   the `Draw` phase (`Vtx Syn Prw Pipe(Tx Sh Lu) Desc Setup Cmd`).
4. A finish (`pgraph_vk_finish` :4881; reasons :4884-4895: vertex buffer dirty, surface create, surface
   down, buffer space, framebuffer dirty, presenting, flip stall, flush, stalled) closes the command buffer
   and hands it to the render thread (`finish_submit` :5021-5187, `qemu_event_wait(&finish_event)` :5167 =
   frametrace's old draw.c:4319), then rotates the frame slot and waits for the slot's previous fence
   (`finish_fence` :5189-5364, `vkWaitForFences(&r->frame_fences[next_frame])` :5234-5236 = old :4386; 3
   slots, `g_xemu_submit_frames = 3`, `draw.c:37`). #804's tail drains pending occlusion reports
   (`pgraph_vk_process_pending_reports_internal` :5373 -> `reports.c:213`, fence wait :259, query WAIT
   :265-273) still inside `Fin`. A STALLED finish (`reports.c:374`, DMA_GET == DMA_PUT) releases no lock.
5. FLIP_STALL (`pgraph.c:2714`): surface_update, `flip_stall` (a finish with reason FLIP_STALL),
   `waiting_for_flip = true`, frame-time EMA. The PFIFO thread then stalls in `pfifo_stall_for_flip`
   (`pfifo.c:1645`) until the VBLANK timer advances READ_3D. Phase `Flip`.
6. VBLANK (`nv2a.c:957`) raises the IRQ; the guest's VBLANK handler advances its frame; the guest starts the
   next frame. The render thread's display sync (`render_thread.c:254-258`) renders the scanout surface for
   the UI thread, which swaps (`ui/xemu.c:2372`).

So the PFIFO thread is the serial spine: every method, every draw's Vulkan recording, every finish wait,
and the flip wait run on it in order. The vCPU runs in parallel to it but the two meet at DMA_PUT
(`pfifo.lock`), at PFIFO USER reads, and at the VBLANK IRQ. The render thread and the GPU run in parallel to
the PFIFO thread except where a finish is not deferred or has a post-fence callback (every surface download,
every report, every `Finish sd`).

### 2.3 Where the PFIFO thread waits (the corpus, verified against HEAD lines)

| wait | line (HEAD) | phase bucket | seen on |
|---|---|---|---|
| finish_event after submit (render thread's fence) | `draw.c:5167` | `Fin.Sub` | Forza, Nightfire (frametrace: 12.56 / 7.41 ms per frame, section 4.4) |
| frame-slot fence rotation | `draw.c:5234-5236` | `Fin.Fen` | Simpsons (frametrace: 8.06 ms; lockw 7.90 = 32% of a 24.5 ms frame) |
| pending reports under `pfifo.lock` | `pfifo.c:2163` -> `reports.c:259,265-273` | `Fin` tail (#804) | pmucounters R3 #1; `HAKUX_OCCL_WAIT=0` arm 4.39 ms/frame gap |
| flip stall | `pfifo.c:1645-1658` | `Flip` | every title at a frame boundary |
| nothing to do (DMA_GET == DMA_PUT) | `pfifo.c:2238-2246` | `Idle.Fr` (after a flip) / `Idle.St` | NFS: Idle 10.3 of 44 ms (lane.local, section 4.1) |

Three removals of the finish wait lost fps (brief item 4): simp2's lock release (c2dfca18a1, reverted; fps
40.05 -> 36.22, the PFIFO sleep moved 8 -> 21.3 ms), gpunonrender's `HAKUX_STALLFIN=reports` (30.3 -> 25.8),
pfifowait1009's bracket (lost fps, Stencil moved 30,000 px). In each case the wait MOVED to the next
synchronization point rather than disappearing, because the thing being waited for (the GPU finishing the
previous batch) was still needed by the next operation (a download, a report, a reuse of the frame slot).
The lesson the plan must respect: a wait is removed by removing its CONSUMER's need for the result on this
thread, not by releasing the lock around it.

### 2.4 create_texture() and the surface-to-texture route (texture.c)

A texture whose memory overlaps a surface's dirty range makes `create_texture` call
`pgraph_vk_download_surfaces_in_range_if_dirty` (texture.c ~2109): a GPU finish plus a readback per
overlapping surface, on the PFIFO thread, then a CPU upload of the texture. NFS MW binds a 128x128 swizzled
A8R8G8B8 cube map whose six faces are render targets (`[txdl794] why=cube` in perdrawon1010's logs);
`check_surface_to_texture_compatiblity` refuses cube maps, so each face takes the download route: `txr dl`
sync finish 0.5/frame at 3.73 ms/frame (NOT counted on `[sdcall]`), plus the range scan 1 finish + 4
downloads per frame at 3.91 ms/frame, together ~7.6 ms/frame average and ~18 ms at peak (perdrawon1010
run 1-1791644405, lane.local's `[sdcall]`/`[txdl794]` read). `ct` (create_texture) 8.6 ms/frame; 1.5 GPU
drains per frame (`Finish sd 90` per 60 frames). lane.texscan1010 is building a GPU-side route behind
`HAKUX_TEXSCAN` (section 6).

### 2.5 The GPU side

Turnip (Mesa, T30 PurpleVK 26.3.0-devel) loaded through adrenotools (`MainActivity.kt:60-90`,
`GpuDriverHelper.kt`, `xemu_android.cpp:1988-2030`, `instance.c:207-215`); the fork at
`~/hakux-work/mesa-turnipfork` is pinned and unpatched (turnipfork NOTES). Driver CPU was 7.2% of the PFIFO
thread on Crimson Skies (adreno-driver-feasibility.md, old build; ~2 ms) and 4.5% at the NFS race start
(lane.local's 10-09 profile, section 5.3). GMEM tiling replays every draw once per bin; sysmem rendering
halved DOA3/NG Black's pass (31 -> 59 gfps, gmem474/turnipcost569); `TU_AUTOTUNE_ALGO=profiled` matched the
best mode on those titles but Forza lost. NFS's pass census (draws per pass, passes per frame) was unmeasured
before this lane; `HAKUX_GPUXFR=1` prints it (`XFR rpc`, `draw.c:4372`).

## 3. Instruments: formats and blind spots

All on logcat unless noted. The dispatcher's LOGCAT_SPEC (`jobs/dispatcher.sh:2167`) keeps hakuX-lane,
xemu-gpu, hakuX, hakuX-phase, hakuX-stall, hakuX-cpu, hakuX-pace, hakuX-perf, xemu-work, hakuX-route.

| line | source | cadence | fields | cannot see |
|---|---|---|---|---|
| `hakuX-perf gfps= G:ms(min-max) D: S: J: Df Vd Ul Vpf Ri Tq` | profile.c:794-807, pacing string :934 | printed every 60 flips; `G:` is an EMA alpha 0.2 of the flip-to-flip period updated EVERY flip (profile.c:774) | guest fps; `G` = the period the phase line below was measured at | `Tq` is not draws (it is a pacing field). Draws per frame are `xemu-work BE:` (profile.c:1247, begin/end count of the last COMPLETED frame before the print, once a second) |
| `hakuX-pace f= v0..v4 vb= max= ms=` | profile.c:802 | 60 flips | flip count, VBLANKs-per-frame histogram, `ms=` the exact wall span of the 60 flips | which frame was the slow one; at 12-20 fps a 60-flip span is 3-5 s and straddles a menu or GO |
| `hakuX-phase Surf Tex [TxH] Shd Draw [Vtx Syn Prw Pipe(Tx Sh Lu) Desc Setup Cmd [Sfp Mfp FTx]] Fin(Sub Fen) Flip Idle(Fr St) \| Tot GPU(R X RP Pre Post MxG g:)` | profile.c, perflog build only | printed every 60 flips, but every field is an EMA alpha 0.2 updated EVERY flip (`snapshot_phase_timing` profile.c:66-80, called from the flip hook at :415). A line is therefore a sample of the ~5-10 frames before its print, NOT a 60-flip mean; its matched period is `G:` on the `hakuX-perf` line of the same timestamp, not `pace ms=/60`. Do not try to invert the EMA across lines (this lane did; the result was garbage) | PFIFO-thread wall time per phase; `Draw` excludes finish; `Fin` includes the #804 tail | anything on another thread; the ms per frame no phase covers (G - Tot: 8-13 ms here, section 5.4) -- PFIFO time outside any timer: method parsing, pusher, lock waits, runqueue wait, logging |
| `hakuX-cpu CPU: K: W:K M:(Fh: Ni:) Push:ms [Pull:(Lk: Mth: Fst:)] SpH:% TbH:% Lw:` | pfifo.c / cpu-exec.c | 60 flips | pusher ms, puller ms (lock, method, fast path), TB hit rates, DMA_PUT lock wait | per-method cost |
| `xemu-gpu GPU: Tot Rnd Xfr RP` | draw.c, timestamps | 60 flips | GPU busy per frame | GMEM in-pass stamps mark the last tile (render vs transfer misattributed); double count fixed 5c35880d0a; sanity Tot x fps <= 1 |
| `xemu-gpu XFR nr/sites/rp/rpc` | draw.c:4324-4372, `HAKUX_GPUXFR=1` | window | readback count, render-pass pairs, pass census | - |
| `hakuX-stall RPBreaks Finish(vtx sc sd buf fb pres flip flu stl stlDef stlBat) ...` | draw.c:998 | 60-frame deltas | finish reasons | the duration of each |
| `[sdcall] ...` | surface.c:1598-1734 | per call | surface download callers (range/tobuf/.../reuse/record/prerec) | `txr dl` is not counted |
| `txw[...]` | texture.c:117 | per event | texture writes | - |
| `[rr425w] w= idlepc=8001b02e idle_us= busy_us= n= nb= drop= KEY:n:idle:busy:ih:bh:...` | cpu-exec.c:1169-1215, 1342 | 2 s | vCPU wall time in the guest idle loop vs everything else; per-wake-vector split (0x33 = NV2A IRQ, 0x30 = timer) | WHAT the busy time is (JIT body, TLB, helper, MMIO wait all count as busy); sub-window variance |
| `[pmu433] s= dt= fr= ... p=NAME gN=RUNMS:v,...` | hakux-pmu.c.inc:1141, `HAKUX_PMU=1` (count) / 2 (sample) | window | per-thread cycles/instructions/cache/branch counters | wall-clock waits |
| `[hakuX-ft1] n= rt_ms= t_ms= I= vbp= pm= late= pml= p50 p95 p99 max gpu50 gpu95 mhz crit vrun vgw vgi vrq vblk vw=(bql,pfl,pgl,halt,idle,fence,submit,rthr,dl,oth) vh=(unk,run,gpu,rnd,idle,wait) vho nw lw prun prq pblk pidle pw= pc= rrun rblk sl50 sl05 vb= ins insmax wcpu_us [mmio...] fw= sites` + `[hakuX-ft]` hitch blocks + `frametrace_<ts>.csv` | profile.h:1596-1700, `HAKUX_FRAMETRACE=1` | per window + per hitch | per-thread run/wait split for the vCPU (`v*`), PFIFO (`p*`), render (`r*`); the wait sites; `crit` = which thread the critical path was on | the GPU's own timeline beyond gpu50/gpu95; `qemu_event_wait` at draw.c:5167 is visible only as `pw=` (no Vulkan hook) |
| simpleperf (lane.local's `go.sh`, direct adb under a hold) | APK symtab | one capture | on-CPU sample share per thread and symbol | off-CPU time entirely; JIT code is "unknown dso" (31.4% of the vCPU thread); rounding on short captures |
| `route-frames/` | dispatcher screencaps | per route shot | whether the player moved | fps |

The frametrace line's `crit` is the only instrument that names the critical path directly; the rest are
per-thread or per-phase totals that have to be reconciled by hand against `hakuX-pace ms=` (the period).

## 4. Corpus findings this plan builds on (sources)

### 4.1 Phase split at the race start (lane.local's read; brief item 1)
perdrawon1010 runs `1-1791644405` (off) and `1-1791645060` (on), window [GO, GO+10.5], rows with Tot >=
40 ms, fix off: Draw 15.0 (12.6 on), Fin 17.0 (Sub 11.0, Fen 0.9), Idle 10.3 (Fr 9.9), Surf 1.8, GPU 14.2,
Tot 44.1; pace period 56.2 ms at 3.37 VBLANKs/frame; ~12 ms per frame outside every phase. Per 60 frames:
Finish sd 90, flip 60, stl 73 (all deferred).

### 4.2 Countdown window (this lane's `startread.py --window -4,1.5`, 4 fixed arms, 48 starts)
off: 18.0 gfps, 55.4 ms, 1,602 draws, Tot 43.8, Idle 10.6, 9.60 us/draw (Draw phase); on: 19.5 gfps,
51.3 ms, 1,560 draws, Tot 40.0, Idle 10.3, 7.79 us/draw. Matched on-off: +1.58 gfps, -4.4 ms, -1.86 us/draw.
Frame-time fit over the fixed arms: off 21.9 ms + 20.52 us/draw, on 23.2 ms + 18.01 us/draw (n 72/74).
The intercept (~22 ms a frame that has nothing to do with draw count) is the first thing the plan has to
explain: at 2,000 draws the slope is ~41 ms (off) and the intercept ~22 ms; both have to shrink.

### 4.3 Per-draw CPU cost
perdraw1009: ~11 us/draw, cut 15-22% by `HAKUX_UNI_*` (branch lane/perdraw1009, 4ad1154e55). perdrawon1010
at this scene: -2.0 us/draw moving, -1.86 us/draw at the countdown (4.2). S4 of its NOTES: the start does
not hold 28-30 with the switches on.

### 4.4 PFIFO waits
frametrace (docs/lanes/frametrace/NOTES.md): Forza 12.56 ms and Nightfire 7.41 ms per frame at the old
draw.c:4319 (now :5167); Simpsons 8.06 ms at the rotation fence (old :4386, now :5234). pmucounters R3 #1:
write occlusion reports when the fence signals, dropping both locks, P 0.8; `HAKUX_OCCL_WAIT=0` arm shows a
4.39 ms/frame gap. The three failed removals: section 2.3.

### 4.5 vCPU and JIT
vcpuplan (GTA SA profile a593d8eb85): JIT 53.9% (TLB compare 17.4, preamble 8.5, body 22.7), TB lookup 22.8%
(stale; 17-20% after tbflip/tbsize), softmmu slow path 7.9%. memfast F1 rejected: one alias saves <= 1.5%.
ibcache (`HAKUX_IBC`, default off): cuts helper calls 92.6% but the freed time became idle spin without idle
halt. vcpu60: no JIT combination reaches 60 on any title; its top item was a GPU-side sleep (DMA_PUT under
pfifo.lock) at P 0.4. Rule from vcpuplan: price a vCPU change by a measured removal, not by sample share.
Nobody had measured NFS's vCPU at the race start before this lane (section 5.1).

### 4.6 Surfaces and textures
surfgpu1009 (default on since 7d574ece8b) moved surface downloads to the GPU for the cases it covers;
async794: deferring a download to the guest's next sync point does not help when the consumer is our own
texture upload (the cube-map case above IS that consumer). surfdl1008/dmasurf277/surfwatch382: page-watch
downloads on the vCPU thread.

### 4.7 Shaders
shaderplan569/fb569/prebuild569: ubershader default (`HAKUX_GPL_DEFAULT` 3), prebuild on; a first-time
compile stall is removed with no dropped draw. NFS `Shd` at the race start: in this lane's phase lines.

## 5. This lane's measurements

### 5.1 vCPU at the countdown, before the runs (OFF1 run 1-1791644405, start 1 at 08:12:53)
`[rr425w]`: idle_us 0.75-1.09 s per 2 s window, i.e. the guest sat in its idle loop 38-55% of wall time and
was busy 45-62%. `hakuX-cpu`: Lw 0.1-0.9 ms per 60 frames (DMA_PUT lock wait is nothing), Push 25-54 ms per
60 frames (0.4-0.9 ms/frame of pusher), Pull Mth 20-45 ms per 60 frames (0.3-0.75 ms/frame of method
dispatch under the lock). `hakuX-pace f=11340 v3=1 v4=59 ms=4293.9` = 71.6 ms/frame, every frame 4+
VBLANKs. Read: the vCPU is NOT the critical path at the countdown; it is idle about half the time, waiting
on VBLANK (the guest is frame-locked to the flip handshake) while the PFIFO thread works. `vcpuread.py`
(this dir) does this read per window and splits busy time by wake vector.

### 5.2 lane.local's 10-09 simpleperf at the race start (45 s, 13 fps, ~1,650 draws, build 1b1fec978d-perflog, `~/hakux-work/lanelocal-scratch/nfs-race-1009/prof/split.txt`)
vCPU thread 0.86 cores on-CPU: cpu_exec_loop 29%, JIT code 31.4% (unknown dso), tb_lookup + qht + helpers
~13%, clock_gettime 7.6% (the perflog build's timers). PFIFO thread 0.42 cores on-CPU: pfifo_thread self
22.3% (perflog clock reads), memcpy 15.3%, tlb_reset_dirty 4.3%, ubosz_note_upload 4.2%, surface_update 3.9%,
apply_uniform_updates 3.7%, memcmp 3.7%, Turnip 4.5%. Audio 4 x ~5%, DSP 5.7%. Caveat: on-CPU share only;
the PFIFO thread's other 0.58 cores are the waits in section 2.3, and this capture is from a 13 fps session
driven by hand, not the route.

### 5.3 Runs queued (Nova, both ref ab1acc4154 --perflog, 500 s, route nfs-mw-quickrace, env HAKUX_FRAMETRACE=1 HAKUX_PMU=1 HAKUX_GPUXFR=1, --pull frametrace_*)
- `1-1791649387-nfs30plan1010-2138210` (run 1)
- `1-1791649388-nfs30plan1010-2138879` (run 2)
Queue at 16:31 UTC: texscan1010 running; nfsframe1010 run 1 ahead of mine; nfsframe1010 run 2 and the two
forzasurf1010 arms behind. Results land in `~/hakux-work/dispatch/results/<id>/` (logcat.txt, run.log,
route-frames/, pulled/frametrace_*.csv). Reads planned: moving player from `route-frames/s*-g11.png`;
`phaseread.py --window=-2,1.5` and `--window=1.5,12` (not `startread.py`: it needs the `[perdraw433]`
state line that only perdraw1009's build prints, and fails "one state missing" on every other build);
`vcpuread.py`; `docs/lanes/frametrace/ftread.py <dir>` (window from `mark gameplay`) and `rtjoin.py`;
`[pmu433]`; `XFR rpc` pass census; `[sdcall]`; `hakuX-stall`; `hakuX-phase`. Then the per-thread
heavy-frame table (section 5.5).

### 5.4 The PFIFO thread at the countdown, from the free perflog run (texscan1010's `1-1791648919-texscan1010-2004607`)
Build 4784750c3c = master + the `[tsc]` census (no switch), `--perflog`, no env, same route, 12 starts,
ROUTE finished, player moving on every `s*-g11.png`. Reader: `phaseread.py` (this dir), one sample per
phase line printed in [mark-2, mark+1.5] (the countdown proper), period = `G:` of the same print.

| start | G ms | fps | Draw | Fin (Sub) | Idle (Fr) | Tot | G - Tot | GPU (R X) |
|---|---|---|---|---|---|---|---|---|
| 1 (cold: menus -> load -> race) | 74.3 | 13.5 | 21.6 | 25.9 (18.7) | 11.1 (9.2) | 61.2 | 13.1 | 22.7 (15.3 7.4) |
| 2 | 63.0 | 15.9 | 20.4 | 17.5 (12.1) | 10.9 (10.1) | 50.9 | 12.1 | 14.6 (14.2 0.4) |
| 4-12 (warm restarts, 10 samples) | 53.2-58.0 | 17-19 | 16.2-18.1 | 14.4-15.9 (9.2-10.1) | 9.1-12.3 | 42.5-47.6 | 9-11 | 11.7-13.0 |
| pooled, 12 samples | 56.6 | 17.7 | 17.5 | 16.0 (10.6, Fen 1.5) | 11.1 (9.7, St 1.4) | 46.5 | 10.1 | 13.2 (12.3 0.9) |

Pooled detail: Surf 1.7, Syn 3.9, Pipe 5.4 (Sh 3.4), Desc 2.1, Setup 1.1, Mfp 3.0; draws/frame 1,577
(`BE`), so Draw is 11.1 us/draw; Push 0.67, Pull 0.62, Lw 0.00 ms/frame; `txw` bind 8.6 and
create_texture 8.5 ms/frame, of which sync-dl 3.7 (0.5/frame, the cube's face 0) and range-scan 3.9 (286
scans/frame, 1 finish + 4 downloads/frame); finishes per 60 frames sd 90, flip 60, stl 70, total 220.
Same reader, [mark+1.5, mark+12] (post-GO): G 47.6 (21 fps), Draw 14.3, Fin 13.3, Idle 10.5, Tot 39.7,
G - Tot 8.0, GPU 10.7, 1,172 draws/frame (12.2 us/draw), create_texture 10.1 (sync-dl 4.4, scan 4.6).

Read:
- **The cold first start is the owner's 13 fps.** Only start 1 reaches 74 ms, and its extra over a warm
  restart is Sub (+8 ms: first-use texture uploads, X 7.4 = GPU transfers) and Draw (+4 ms at ~1,900
  draws, `BE` 1929/1846 at that start against ~1,577 later). The owner's by-hand runs are always cold
  starts (and a downtown track); the route's restarts are warm. The plan has to hold 30 at the cold start.
- **GPU is not the limit**: GPU x fps = 0.23 pooled, 0.31 cold. Rendering is 12-15 ms of GPU per frame.
- **Draw (recording) is 17.5 ms = 11 us/draw**, the same per-draw cost perdraw1009 measured; at 2,000
  draws it is 22 ms by itself, two thirds of the 33.3 ms budget before anything else runs.
- **Fin 16 ms is mostly the two synchronous texture-coherence paths**: sync-dl 3.7 + scan 3.9 = 7.6 ms
  inside create_texture, each a `pgraph_vk_finish` plus a GPU->CPU copy, plus the flip finish (60/60) and
  the deferred-stall finishes (70/60). Sub 10.6 is the submit+wait part of those finishes.
- **Idle.Fr ~10 ms every frame, hot or cold, cold or warm**: the PFIFO thread waits for the guest's next
  frame after the flip for ~10 ms regardless of load. That is the serial alternation: guest frame, then
  our frame, not overlapped (5.1 shows the guest half idle in the same windows).
- **G - Tot = 8-13 ms outside every phase timer.** Frametrace's `prq`/`pblk`/`pw=` on this lane's runs
  (5.5) say what it is.
- `vcpuread.py` on the same run, [mark-2, mark+1.5]: 53.8 ms/frame, vCPU busy 28.0, idle 25.8 per frame
  (52% busy), of which 22.2 ms is work done after an NV2A wake and 4.4 after a timer wake.
  nfsframe1010's run 1 (`1-1791649039-nfsframe1010-2037292`, ref 07937793af, **no perflog**, same route):
  countdown 45.6 ms/frame, busy 27.4, idle 18.2 (60%); post-GO 38.4 ms/frame, busy 24.5, idle 13.9 (64%).
  So the guest's own frame costs ~27 ms of vCPU wall time at the countdown on both builds, and the
  **perflog build is ~8-10 ms/frame slower than the plain build at the countdown** (45.6 vs 53.8 ms;
  post-GO 38.4 vs 47.2). Every phase figure in this section carries that instrument cost; the plan's budget
  is set against the plain build's period (45.6 ms countdown warm, 13 fps = ~74 ms cold by the owner).
  Caveat: rr425w busy is wall time outside the idle loop, so a vCPU MMIO wait on our side counts as busy;
  frametrace's `vw=` split (5.5) separates it.

### 5.5 The heavy frame, per thread
(filled in from this lane's runs, 5.3; until then the end-to-end numbers are 4.1, 4.2 and 5.4)

## 6. Coordination

- **lane.nfsframe1010** (Sonnet): [GO, GO+10.5] window, master's head, two queued runs
  (`1-1791649039`, `1-1791649724`) WITHOUT perflog and WITHOUT env, so they carry no phase lines, no
  frametrace, no PMU, no census. They answer "does the vCPU idle after GO" from `[rr425w]`. This lane's runs
  carry perflog + frametrace + PMU + census on the same emulator; I read nfsframe1010's results for the
  post-GO rr425w and do not re-run that question. Its run 1 is read in 5.4: the plain build's period is
  45.6 ms (countdown) / 38.4 ms (post-GO) with the vCPU 60-64% busy. Its NOTES section 2 is a good
  independent check of the instrument semantics, except that it calls the phase line "per-~1s-window
  averaged": it is a per-flip EMA (section 3 here).
- **lane.texscan1010** (Opus): `HAKUX_TEXSCAN` GPU-side range scan. The cube-map `txr dl` route is a
  different path (section 2.4) and is NOT covered by its switch as described; PLAN.md says so.
- **lane.perdrawon1010**: done measuring; its result is 4.2/4.3.
- **lane.forzasurf1010**: SURFGPU on/off on Forza; off NFS's path.

## 7. What the next lane should not repeat
- Do not release `pfifo.lock` or `pgraph.lock` around a finish wait and call it a fix: three lanes did,
  all lost fps (2.3). The wait moves.
- Do not price a vCPU change by sample share (4.5). At the countdown the vCPU is half idle (5.1).
- Do not run this route without `--perflog` if the question is where the PFIFO thread's time goes; the
  non-perflog build prints pace/perf/cpu/rr425w only.
- `startread.py` needs `PERDRAW1009_REF` to a reachable sha AND a build that prints the `[perdraw433]`
  state line; on any other build it fails "one state missing". `phaseread.py` here reads any perflog run.
- A `hakuX-phase` line is a per-flip EMA, not a window mean (section 3). Select lines by print time and
  pair each with its own `G:`; never divide `pace ms=` by 60 to get the period of a phase line, and never
  try to de-EMA.
- The perflog build costs ~8-10 ms/frame at this scene (5.4). Price a rework against the plain build's
  period, and judge an A/B on the plain build when the switch does not need phase lines.
- The route copy that request.sh resolves must sit in `docs/testing/titles/routes/` of the tree you run
  it from; that copy is outside this lane's territory and is not committed here.
