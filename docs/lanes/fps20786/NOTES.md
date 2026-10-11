# lane.fps20786: why a class of titles runs at ~20 fps on the Nova (#786, #747)

Brief (2026-10-03): name the bound once for NBA Live 2004/05/06/07, Top Spin,
Counter-Strike and Midnight Club 3. Telemetry, not retests: one `--perflog` soak
per title, decomposed with the near30 method. No fix in this lane.

## Method

`decompose.py` here is docs/lanes/near30/decompose.py plus two things: `--mark
HH:MM:SS` for a held run (pathfind) whose run.log has no ROUTE mark, and two
columns for the render (PFIFO) thread:

| column | source | meaning, per guest frame of F ms |
|---|---|---|
| Ri | hakuX-perf `Ri:` | render thread parked waiting for a kick. This includes the flip stall waiting for VBLANK: the pusher exits on `waiting_for_flip` and the thread parks (pfifo.c 2186-2236) |
| rcpu | `[rdc] tcpu/dt` x F | render thread on-CPU (CLOCK_THREAD_CPUTIME_ID of the thread that prints [rdc], tid checked) |
| rblk | F - Ri - rcpu | render thread neither parked nor on-CPU: blocked. The GPU fence wait at each flip lands here: `pgraph_vk_flip_stall` calls `pgraph_vk_finish(VK_FINISH_REASON_FLIP_STALL)` (vk/renderer.c 2557) before the next frame's methods are read |

The other columns (gbusy/gidle, wake classes, v_run/v_blk, lockw, ph_*) are
near30's; see docs/lanes/near30/NOTES.md "Method".

## Registered before any run (2026-10-03, this commit): what each bound looks like

Read on the slow windows (2-s rows below 28.5 fps) of each title.

| bound | signature | owner |
|---|---|---|
| vCPU (guest code) | gbusy >= 0.85 F, or for a title that never reaches its idle loop v_run >= 0.85 F with v_blk small; Ri >= 0.3 F (renderer waiting for the guest) | lane.memfast #507 (fastmem); TLB / re-translation if `[tlb68]`/`[jc425]` flush counts lead (lane.flushstall787 #787) |
| GPU | ph_GPU >= 33 ms per flip; Ri < 0.2 F; rblk large and ph_Fin (finish wait) carrying it | #474 |
| render thread CPU | rcpu >= ~30 ms per frame with ph_GPU < 33; Ri < 0.2 F | new (renderer CPU) |
| serial renderer (CPU then GPU, at the flip) | neither rcpu nor ph_GPU alone reaches 33, but rcpu + rblk (= F - Ri) > 33.3; Ri < 0.2 F; guest idle large | new: the flip-stall finish serialises the frame |
| lock / sync | lockw >= 5 ms per frame, or Ri >= 0.3 F AND gidle >= 0.3 F together (both sides waiting on each other) | #474 lock work |

The 20-fps number itself: when frames take exactly 3 VBLANKs (hakuX-pace `v3`
dominant), a frame cost anywhere in (33.3, 50] ms reads as 20.0 fps. So the
cost that matters is F - Ri, not F, and a fix pays nothing until it lands
under 33.3 ms.

Predictions per title, before its run:

| title | evidence before the run | predicted bound | P |
|---|---|---|---|
| NBA Live 2005 | always-on lines of pathfind's 609-s hold (below) | serial renderer; GPU alone < 33 | 0.6 (GPU-bound 0.25, render CPU 0.15) |
| NBA Live 2004/06/07 | same engine (EA, same publisher family) | as NBA 2005 | 0.5, untested |
| Top Spin | one 20-fps frame (pathfind 10-02) | serial renderer or GPU | 0.5 |
| Counter-Strike | one 13-fps frame | vCPU | 0.4 (GPU 0.3) |
| Midnight Club 3 | 09-30 soak below: near 30, slow rows guest-busy | vCPU in its slow windows; not a 20-fps title | 0.6 |

## Step 1: what the existing logs already say (offline, no device)

### NBA Live 2005: pathfind's held run, 2026-10-03 16:37-16:47 PDT (Nova)

`docs/lanes/pathfind/runs/nba-live-2005-hold` (lane/pathfind; logcat copied to
scratch here, not committed). Debug app, device defaults (HAKUX_GPL default 3),
12-minute quarters, 609 s of play, verdict 19.97 fps window median, 0.0% at 30.
Decomposed with `--mark 16:37:00` (the logcat starts at the hold):

| rows | fps | F | gbusy | gidle (timer-woken) | Ri | rcpu | rblk | v_run | v_blk | lockw |
|---|---|---|---|---|---|---|---|---|---|---|
| 304 (all below 28.5) | 19.96 | 50.1 | 22.0 | 28.3 (24.3) | 8.2 | 26.4 | 15.5 | 48.5 | 1.6 | 0.9 |
| slowest quarter (77) | 19.18 | 52.1 | 22.8 | 29.2 (25.3) | 8.1 | 26.7 | 17.3 | 49.7 | 2.0 | 1.1 |

hakuX-pace: 48 of 56 frames per line take exactly 3 VBLANKs (v3). Read:

- **Not vCPU.** The guest runs code 22 ms of a 50-ms frame and sits in its
  idle loop for the other 28 (v_run is 48.5 only because the idle loop is
  spun, `[idlehalt] on=0`). A guest that needs 22 ms could make 30 fps.
- **Not lock.** vCPU waits on pgraph.lock 0.9 ms per frame.
- **Renderer.** The render thread is parked only 8.2 ms of 50 (and that
  includes the wait for the third VBLANK), so its own cost is ~42 ms per frame:
  26.4 ms on-CPU plus 15.5 ms blocked. 42 is in (33.3, 50], hence 3 VBLANKs,
  hence 20.0 fps on every row.
- Open: whether the 15.5 ms blocked is the GPU (the flip's finish wait) or
  something else. That is what the perflog run's ph_GPU / ph_Fin answer.

### Midnight Club 3: 1-1790734333-titleroutes-3037624 (2026-09-30, Nova, Arcade street)

| rows | share >= 28.5 | fps | F | gbusy | Ri | rcpu | rblk | v_blk |
|---|---|---|---|---|---|---|---|---|
| all 145 | 0.86 | 29.7 | 33.7 | 28.3 | 12.6 | 14.5 | 6.9 | 7.2 |
| below 28.5 (20) | -- | 22.9 | 43.6 | 34.9 | 12.2 | 20.1 | 11.4 | 9.2 |

MC3 in Arcade mode is a near-30 title, not a 20-fps one: 86% of its 2-s rows
are at or above 28.5. Its slow rows are guest-busy (gbusy 35 of 44 ms).
Pathfind's "22 fps" (10-02) was one overlay reading on a different route.

## Step 2: runs (lane.fps20786, Nova, --perflog, HAKUX_GPL=3)

Routes: `routes/fps786-*.route`, generated by `make-routes.sh` /
`steps2route.py` from pathfind's recorded runs (each step's input at the
step's own time + 4 s, then a 600-s genre loop). All on ref 70ebd4435d's
perflog build (binary 622a9be57356). `extras.py` gives the VBLANK histogram,
the render thread's dirty walks, the vCPU's pgraph.lock wait by register and
the perflog medians.

| run | title | route | result |
|---|---|---|---|
| 1-1791080537-lane.fps20786-2538884 | Top Spin | fps786-topspin | pilot; reached the match, 307 rows |
| 1-1791081646-lane.fps20786-2876934 | NBA Live 2005 | fps786-nba2005 | reached play (12-min quarters, 11:45 1st), 310 rows |
| 1-1791081646-lane.fps20786-2876984 | Counter-Strike | fps786-cs | reached play at 21:00:17; from ~21:00:57 stood on a "Press A to continue" card the loop had no A for (route defect, mine) |
| 1-1791081681-lane.fps20786-2878057 | Midnight Club 3 | midnight-club-3.returning | reached the Arcade street race on schedule, 322 rows |
| 1-1791086565-lane.fps20786-3338415 | Counter-Strike | fps786-cs2 (loop leads with A) | live rounds (a cobblestone map, the clock running 7:00 -> 6:24, rounds restarting) with the weapon wheel open: pathfind closed it with B, which the loop does not press. 330 rows |

### Top Spin (2538884): not a 20-fps title on this build; vCPU-side lock wait behind surface downloads

The route reached the Melbourne match on schedule. Step 24's START landed in
play and paused it; the loop's first A took "Resume game" (frame 192900). A
rally was in play from 19:31 (frame 193136).

| rows | share >= 28.5 | fps | F | gbusy | Ri | rcpu | rblk | v_run | v_blk | lockw | ph_GPU | ph_Draw | ph_Fin | ph_Tot |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all 307 | **0.89** | 32.5 | 30.8 | 29.5 | 0.1 | 16.0 | 14.4 | 17.0 | 13.8 | 13.6 | 10.6 | 8.3 | 15.5 | 25.8 |
| below 28.5 (34) | -- | 27.1 | 36.9 | 35.4 | 0.1 | 18.5 | 17.8 | 20.4 | 17.3 | 17.7 | 13.1 | 9.6 | 19.8 | 31.6 |

VBLANKs per flip: v1 0.26, v2 0.67, v3 0.06. That is 30-plus fps with
60-fps stretches, under perflog (which costs the render thread ~1.2 ms per
frame, lane.alwaystelemetry). Top Spin is a near-30 title one share point
under the bar (0.89 vs 0.90), not a 20-fps one. The 10-02 "20 fps" was one
overlay reading on an older build.

What binds its slow windows is **lock/sync**:

- The guest never reaches its idle loop (gbusy = F), yet the vCPU thread is
  asleep 13.8 ms per frame (v_blk), and `[lock474]` accounts for it: it waits
  13.6 ms per frame for pgraph.lock, 99% of that on one register, PGRAPH
  0xb10. That register is read ~20 times per flip (1300 per 2 s), 850-940 ms
  of every 2 s, all in phase "other", not in the flip.
- The render thread never parks (Ri 0.1). Each frame is 8.3 ms of draw
  building plus 15.5 ms of finish (ph_Fin; Sub 14.2). The finishes are not the
  flip's: `hakuX-stall` counts `Finish:1530 (sd1470 ... flip49)` per 2 s, which
  is ~30 **surface downloads** per frame (`dlSrc dirtyIf1470`, `xemu-work`
  Fin:Sd30). Each one is a submit plus a fence wait, taken holding
  pgraph.lock. The GPU itself is busy only 10.6 ms per frame (RP 148 render
  passes).
- So the guest's per-draw poll of 0xb10 waits out the render thread's
  surface-download fence waits. In the slow rows, guest busy (35.4) is the
  frame, and 17.7 of it is that lock wait.

Owner: #474 (pgraph.lock). The surface-download count (30 per frame) is the
lever on the render side. On the vCPU side the lever is
`pgraph_lock_release_for_fence()` (pgraph.h 422). Its one call site is
`wait_frame_fence` (vk/surface.c 1188), reached only from the predownload
and coalesced branches of `download_surface_complete_deferred_at`
(surface.c 1218-1231). Top Spin's download-if-dirty finishes
(surface.c 2133) go through `pgraph_vk_finish(SURFACE_DOWN)` and keep the
lock. rd_unl = 0 in every line, so no read was ever served across a
released fence.

### NBA Live 2005 (2876934): the serial renderer, as registered

The route replayed pathfind's path exactly: Exhibition, 12-minute quarters,
the Palace of Auburn Hills, live play at 11:45 in the 1st (frames s13, hold).

| rows | share >= 28.5 | fps | F | gbusy | gidle | Ri | rcpu | rblk | v_blk | lockw | ph_GPU | ph_Draw | ph_Fin (Sub+Fen) | ph_Idle |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all 310 | 0.07 | 24.2 | 41.3 | 21.1 | 19.9 | 5.7 | 24.5 | 10.8 | 2.8 | 2.4 | 18.5 | 8.9 | 13.8 (9.9+3.9) | 5.5 |
| below 28.5 (288) | -- | 24.1 | 41.5 | 21.1 | 20.2 | 6.1 | 24.7 | 11.0 | 2.7 | 2.3 | 18.5 | 9.0 | 13.9 | 6.1 |
| slowest quarter (73) | -- | 20.4 | 49.0 | 19.8 | 29.1 | 10.7 | 26.9 | 11.3 | 1.7 | 1.0 | 19.5 | 10.1 | 14.4 | 10.7 |

VBLANKs per flip: v2 0.44, v3 0.49. 645 draws per frame, 13 render passes,
two finishes per frame (`hakuX-stall` Finish: sd59 + flip59 per 2 s; every
flip deferred, stlDef59). Read on the slow rows:

- **Not vCPU**: the guest runs 21 ms of a 41.5-ms frame and idles 20.
- **Not lock**: 2.3 ms per frame (0xb10 2.1, 0x71c 0.3).
- **Not GPU alone**: 18.5 ms per frame.
- **Not render CPU alone**: 24.7 ms on-CPU, perflog's ~1.2 ms included.
- **The two in series**: the render thread spends 13.9 ms of every frame in
  finish, waiting on the GPU (Sub 9.9 + Fen 3.9), and is idle only 6.1. Its
  non-idle cost per frame is F - Ri = 35.4 ms: 24.7 on-CPU and 11.0 blocked.
  That is just over the 33.3 ms of two VBLANKs, so half the frames take three.
  If the GPU ran under the render thread's next frame instead of after it,
  the renderer's cost would be ~max(24.7, 18.5) + slack, under 33.3.

This run reads 24.2 fps, where pathfind's hold read 19.97. Both soaks ran
the dispatcher's "max" regimen (perf_mode 2, fan 5), and the GPU sat at
615 MHz the whole run ("gpu 615-615 of 680"). The hold ran on the device's
defaults with no thermal record. A serial renderer pays twice for a slow GPU
clock: the GPU idles while the CPU records, so the governor lowers its clock,
and every GPU millisecond is on the critical path. near30 saw the same 401-MHz
floor on Tron's plain runs. Same bound either way; the regimen moves where in
(33.3, 50] the frame lands.

Row by row (310 rows): renderer cost F - Ri rises from 32.1 to 38.6 ms
across the frame-time bands. Render CPU (22.6 to 27.0) and GPU time (17.5
to 19.5) both rise with it. Their sum, 42.8 ms (median), exceeds the renderer
cost of 35.3 by only ~7.5 ms, so only about 7.5 ms of GPU time overlaps the
render thread's work. Guest busy falls as frames slow (r = -0.42 with F): the
guest waits, it does not work.

### Counter-Strike (2876984): the serial renderer again, heavier on both sides

The route reached the Airstrip map at 21:00:17 (frame s13). About 40 s later
a tutorial card came up and stayed for the rest of the run, because the hold
loop had no A. That is a route defect, fixed in fps786-cs2 for the retry. The
3D scene behind the card kept rendering at the same cost as the 40 s of play
before it: rows t = 1.5-39 s match the rest.

| rows | fps | F | gbusy | gidle | Ri | rcpu | rblk | v_blk | lockw | ph_GPU | ph_Draw | ph_Fin | draws/frame |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all 342 (play + card) | 25.8 | 38.8 | 20.6 | 18.2 | 1.6 | 22.8 | 14.3 | 9.2 | 0.3 | 24.6 | 13.3 | 13.8 | 1957 |

- Not vCPU (guest 20.6 of 38.8 ms), not lock (0.3 ms).
- The renderer never parks (Ri 1.6). Its cost is 37 ms: 22.8 on-CPU, 13.3 of
  that building 1957 draws, and 14.3 blocked, almost all of it the finish
  wait (13.8).
- The GPU takes 24.6 ms per frame: under 33.3 alone, but in series with the
  render CPU it is not.
- 10-02's "13 fps" was one overlay reading on device defaults. This run used
  the "max" regimen.

The retry (3338415) played live rounds on a different map, with the weapon
wheel up over a near-static view. B closes it, and the loop has no B. Its
numbers repeat the first run's to the tenth: 330 rows, 25.9 fps, F 38.7,
gbusy 20.7, Ri 2.0, rcpu 22.5, rblk 14.2, GPU 24.4, Draw 13.3, Fin 13.7,
lockw 0.3. VBLANKs per flip: v2 0.68, v3 0.32. Two download-if-dirty finishes
per flip (sd118 dirtyIf118 per 2 s). Both runs are a standing view of a 3D
map with a HUD overlay, not moving play. Moving play would change the draw
count and the GPU time. It would not change the finish waits, which are per
flip.

### Midnight Club 3 (2878057): on the 33.3-ms edge; the shared signature, tipped by perflog

| rows | share >= 28.5 | fps | F | gbusy | gidle | Ri | rcpu | rblk | lockw | ph_GPU | ph_Draw | ph_Fin | draws/frame |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all 322 | 0.01 | 25.4 | 39.4 | 21.3 | 18.1 | 7.2 | 22.5 | 9.8 | 1.0 | 14.2 | 10.6 | 11.2 | 758 |

VBLANKs per flip: v2 0.62, v3 0.36. One staged surface download per flip,
completed by a synchronous finish (`hakuX-stall` sd60 cDef60 per 2 s), the same kind as NBA's. Renderer
cost F - Ri = 32.2 ms, right at the 33.3 edge, so a third of the frames take
three VBLANKs.

This disagrees with the 09-30 plain soak (Step 1: 0.86 share, 29.7 fps, slow
rows guest-busy, rcpu 14.5). Two things moved between them. Perflog costs
the render thread ~1.25 ms per frame at Castlevania's method count, +30% CPU
(lane.alwaystelemetry), and that cost scales with methods per frame; MC3 has
758 draws per frame. The build also moved three days. Which one tipped MC3 is
not measured here; a plain soak on today's build is the test (not run: the
5-run cap). Read MC3 as a borderline member: it makes the synchronous
download every frame and sits within a few ms of the edge.

The same caveat applies to every perflog row in this lane: the render CPU it
reports is high by at least ~1.2 ms. It does not change NBA Live 2005's
verdict. Pathfind's plain-build hold of NBA (Step 1) has the renderer
critical at 20 fps with no perflog in the build.

## Step 3: the shared bound -- synchronous surface-download finishes

All three measured titles make **surface-download finishes every frame**
(`hakuX-stall` Finish sdN; `xemu-work` Fin:SdN):

| title | sd per flip | source | ph_Fin ms | GPU ms | what waits |
|---|---|---|---|---|---|
| NBA Live 2005 | 1 | `sd_complete_def` (cDef): staged downloads not yet submitted, surface.c 1232 | 13.8 | 18.5 | render thread |
| Counter-Strike | 2 | download-if-dirty (`sd_dirty_dl`), surface.c 2133 | 13.8 | 24.6 | render thread |
| Top Spin | ~26-30 | download-if-dirty, surface.c 2133 | 15.5 | 10.6 | render thread, and the vCPU behind pgraph.lock |
| Midnight Club 3 | 1 | cDef, surface.c 1232 | 11.2 | 14.2 | render thread (on the edge) |

Both sources end in the same call, `pgraph_vk_finish(pg,
VK_FINISH_REASON_SURFACE_DOWN)`. That reason is not in the deferred set
(draw.c 4169-4177). So each call ends the command buffer, submits everything
recorded so far, and blocks the PFIFO thread on `qemu_event_wait` until the
GPU has finished it (draw.c 4239-4301), with pgraph.lock held. The GPU's work
for the frame so far then runs while the render thread waits, not while it
records the rest. That is the serial renderer of NBA, Counter-Strike and MC3.
Top Spin takes it ~30 times a frame, and its vCPU's PGRAPH reads (0xb10, ~20
per flip) queue behind the lock (#474's mechanism). NBA's guest reads 0xb10
about once per flip, which is why NBA's lock wait is only 2.3 ms on the same
held lock. The lock-releasing `wait_frame_fence` serves only the predownload
and coalesced branches (surface.c 1218-1231), and none of these four titles
takes either.

**The natural experiment across titles** (`sdsurvey.py`, every perflog soak
of the last 10 days, 31 titles; `sdsurvey-by-title.tsv`). Every title with
no surface-download finish spends at most 2.5 ms per frame in finish: Crimson
Skies 1.1, DOA Ultimate 0.8, Agent Under Fire 0.5, GTA SA 2.5, BF2 0.3, Otogi
1.0, Black 0.9. The ten titles with one or more per flip spend 8-26 ms there:
ToeJam 25.9, BloodRayne 14.7, Counter-Strike 13.8, Blinx 2 13.7, NBA Live
2005 13.6, Top Spin 13.5, Burnout 12.9, Forza 11.2, Midtown Madness 3 10.1,
Nightfire 9.9; then Azurik 7.8, Halo 7.1. The medians cover whole logcats,
menus included, so they rank titles; they judge none of them.

### The answer for the class (filed as #794)

**One bound, new: synchronous surface-download finishes put the GPU's frame
in series with the render thread.** Component: the Vulkan renderer's surface
download path (hw/xbox/nv2a/pgraph/vk/surface.c download paths and
draw.c `pgraph_vk_finish`). It is not the vCPU (guest busy 21 ms of 41 on
NBA, 21 of 39 on Counter-Strike), not TLB/re-translation (vCPU on-CPU tracks
only its idle-loop spin), and not the GPU alone (18.5 and 24.6 ms, both under
33.3). Top Spin's form of it also lands on #474 (the lock held across the
wait).

### Fixes, by P x win (not started here)

| # | fix | P (evidence) | win | titles |
|---|---|---|---|---|
| 1 | **Asynchronous surface downloads**: record the copy into the frame's command buffer (staged downloads are already recorded into the aux CB; their completion is the synchronous part) and wait for it only where the guest can observe the memory, i.e. at its next sync point (notifier / semaphore release / the flip / a PGRAPH idle poll), not at the download. On the NV2A a render target's memory is coherent for the CPU only after such a sync, so this is the hardware's own contract | 0.4 (the mechanism removes exactly the measured 13.8-ms wait; the risk is a title that reads a surface without syncing, and a wait that moves to frame-slot reuse rather than vanishing) | NBA: renderer 35.4 -> ~24-26 ms, under 33.3, so two VBLANKs (30 fps). CS: 37 -> ~25 vs GPU 24.6, so 30 | NBA 2005 (+ 04/06/07 if they share it), Counter-Strike; plus 8-14 ms per frame on the near-30 set: Blinx 2, Forza, Burnout, MM3, Nightfire, BloodRayne, ToeJam, Top Spin |
| 2 | **#474 extension**: release pgraph.lock across the SURFACE_DOWN finish's wait too, as `wait_frame_fence` already does for the predownload and coalesced waits | 0.6 (lock wait 13.6 ms/frame measured on 0xb10, rd_unl 0 today) | Top Spin: frees ~13 ms of vCPU per frame; 0.89 -> above 0.90 likely | Top Spin; any title that polls PGRAPH during downloads |
| 3 | #426 split capture from translation (lane.remote): Pipe+Desc+Setup+Cmd = 5.5 ms of NBA's render thread off the PFIFO thread | 0.3 alone (35.4 - 5.5 = 29.9, under 33.3 only if nothing else moves) | NBA to ~30 on its own at best; compounds with 1 | the renderer-bound set |

Fix 1 is the one that fits the measured cause, and it ranks first on both
P and win. Fix 2 is smaller and surer, but it covers one title.

## For the next lane: what not to repeat, and what is still open

- **Do not re-measure the class to find its bound.** It is named above. The
  next step is fix 1 (#794), with an arm on NBA Live 2005 and
  Counter-Strike. Its falsifier is that ph_Fin stays above ~8 ms per frame,
  or that the wait reappears in Sub/Fen at the flip or at frame-slot reuse.
- **Read a renderer-bound title's render CPU under perflog as high.** Perflog
  costs the render thread >= ~1.2 ms per frame (lane.alwaystelemetry). For a
  title on the 33.3-ms edge (MC3), that decides the verdict. The always-on
  lines (decompose.py columns Ri, rcpu, rblk, gbusy, v_blk, lockw) give the
  bound without perflog; only ph_GPU and ph_Fin need it.
- **Route loops built from pathfind steps** (`steps2route.py`): a hold loop
  needs the buttons that dismiss the title's cards. Counter-Strike needs A
  ("Press A to continue") and B (the weapon wheel at round start); both CS
  runs here stood on one of them. Top Spin's step-24 START pauses the match
  when the match loads a step early; the loop's A resumes it.
- **Open, not measured here:**
  - NBA Live 2004 / 06 / 07: no path or route. Held runs were asked of
    lane.pathfind on #785. Their always-on lines are enough: a renderer-bound
    title shows Ri < 0.2 F with gbusy well under F.
  - MC3 on today's build without perflog: is it under the edge? One plain
    soak on midnight-club-3.returning, read with decompose.py.
  - Top Spin at the bar with the #474 extension (fix 2).
  - Pathfind holds run on device defaults while dispatcher soaks run the
    "max" regimen. The same title then reads 20 or 24 fps depending on which
    tool measured it (NEW ISSUE line in OUTBOX).
